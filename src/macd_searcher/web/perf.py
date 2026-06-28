"""Performance / outcome SQL for the dashboard (docs/queries.sql sections D-I).

All performance queries read from a *deduped* view of `signals`: at most one
row per (symbol, stage, direction, UTC-day), keeping the earliest fire that day.
The scan runs every 4h, so the same setup can fire several times in a day;
counting each once stops same-day repeats from inflating win-rates
(statistical pseudo-replication).

Returns are direction-normalized so a POSITIVE number always means the
predicted move happened (bullish up / bearish down); a win is return > 0. This
mirrors the `signal_perf` view in docs/queries.sql, inlined here because the
dashboard connection is read-only and can't CREATE VIEW.

Every query filters to fired_at >= DETECTOR_FIX_CUTOFF — the pre-fix Stage 1
detector emitted false signals, so that data is simply excluded.
"""

from __future__ import annotations

import sqlite3
from typing import Literal

import numpy as np

from ..stats import summarize

# Horizon is whitelisted (not bound) because it names a column. The Literal is
# enforced at the FastAPI layer, so only these four values ever reach the SQL.
Horizon = Literal["1d", "3d", "7d", "14d"]
ThresholdKind = Literal["proximity", "reduction"]

# Metrics whose distribution can be summarized. Maps the API name to the column
# exposed by the `perf` CTE; whitelisted so only these reach the SQL.
Metric = Literal["ret_1d", "ret_3d", "ret_7d", "ret_14d", "mfe", "mae"]
_METRIC_COL: dict[str, str] = {
    "ret_1d": "ret_1d",
    "ret_3d": "ret_3d",
    "ret_7d": "ret_7d",
    "ret_14d": "ret_14d",
    "mfe": "max_favorable_move_pct",
    "mae": "max_adverse_move_pct",
}

# Boundary of the Stage-1 histogram-flattening fix (commit 59a3dee, deployed on
# the VM between the last pre-fix run at 2026-06-09T12:00Z and the first fixed
# run at 2026-06-09T16:00Z). Pre-fix Stage 1 fired false signals across zero
# crossings, so every perf query filters to fired_at >= this. Placed inside the
# deploy gap, in the DB's stored timestamp format.
DETECTOR_FIX_CUTOFF = "2026-06-09T14:00:00+00:00"


def _rows(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> list[dict]:
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def _base() -> tuple[str, list]:
    """CTE exposing `perf`: deduped, class-joined, direction-normalized signals,
    filtered to post-fix signals (fired_at >= DETECTOR_FIX_CUTOFF).

    Returns (cte_sql, params). Callers append a `SELECT ... FROM perf ...` and
    extend the param list.
    """
    params: list = [DETECTOR_FIX_CUTOFF]
    cte = f"""
    WITH first_fire AS (
        SELECT symbol, stage, direction, MIN(fired_at) AS first_fired
        FROM signals
        WHERE fired_at >= ?
        GROUP BY symbol, stage, direction, substr(fired_at, 1, 10)
    ),
    perf AS (
        SELECT s.*, a.asset_class,
            CASE WHEN s.direction='bullish' THEN s.px_1d /s.fire_close-1 ELSE 1-s.px_1d /s.fire_close END AS ret_1d,
            CASE WHEN s.direction='bullish' THEN s.px_3d /s.fire_close-1 ELSE 1-s.px_3d /s.fire_close END AS ret_3d,
            CASE WHEN s.direction='bullish' THEN s.px_7d /s.fire_close-1 ELSE 1-s.px_7d /s.fire_close END AS ret_7d,
            CASE WHEN s.direction='bullish' THEN s.px_14d/s.fire_close-1 ELSE 1-s.px_14d/s.fire_close END AS ret_14d
        FROM signals s
        JOIN first_fire f
          ON s.symbol=f.symbol AND s.stage=f.stage
         AND s.direction=f.direction AND s.fired_at=f.first_fired
        LEFT JOIN asset_snapshots a ON a.run_id=s.run_id AND a.symbol=s.symbol
    )
    """
    return cte, params


# ---------- outcome readiness (section D) ----------


def readiness(conn: sqlite3.Connection) -> dict:
    """How many signals are scored / finalized, and the oldest still-pending.

    Counts raw post-fix signals (no dedup) — this measures whether the
    update_outcomes job is keeping up, not performance. Filtered to
    fired_at >= DETECTOR_FIX_CUTOFF so the banner matches the rest of the tab.
    """
    p = (DETECTOR_FIX_CUTOFF,)
    row = conn.execute(
        "SELECT COUNT(*) AS total, "
        "COALESCE(SUM(outcome_updated_at IS NOT NULL), 0) AS finalized, "
        "COALESCE(SUM(px_1d  IS NOT NULL), 0) AS have_1d, "
        "COALESCE(SUM(px_3d  IS NOT NULL), 0) AS have_3d, "
        "COALESCE(SUM(px_7d  IS NOT NULL), 0) AS have_7d, "
        "COALESCE(SUM(px_14d IS NOT NULL), 0) AS have_14d "
        "FROM signals WHERE fired_at >= ?",
        p,
    ).fetchone()
    pend = conn.execute(
        "SELECT MIN(fired_at) AS oldest_pending, COUNT(*) AS pending "
        "FROM signals WHERE outcome_updated_at IS NULL AND fired_at >= ?",
        p,
    ).fetchone()
    out = dict(row)
    out.update(dict(pend))
    return out


# ---------- performance / edge (section E) ----------


def summary(
    conn: sqlite3.Connection,
    horizon: Horizon = "7d",
    min_n: int = 1,
) -> list[dict]:
    """E1 headline: win-rate and avg/worst/best return by stage x direction."""
    cte, params = _base()
    ret = f"ret_{horizon}"
    sql = cte + (
        f"SELECT stage, direction, COUNT(*) AS n, "
        f"ROUND(AVG({ret} > 0) * 100, 1) AS win_pct, "
        f"ROUND(AVG({ret}) * 100, 2) AS avg_ret_pct, "
        f"ROUND(MIN({ret}) * 100, 2) AS worst_pct, "
        f"ROUND(MAX({ret}) * 100, 2) AS best_pct "
        f"FROM perf WHERE {ret} IS NOT NULL "
        f"GROUP BY stage, direction HAVING n >= ? "
        f"ORDER BY stage, direction"
    )
    return _rows(conn, sql, (*params, min_n))


def by_horizon(conn: sqlite3.Connection) -> list[dict]:
    """E3: average return at each horizon by stage - does the edge grow or decay?"""
    cte, params = _base()
    sql = cte + (
        "SELECT stage, "
        "ROUND(AVG(ret_1d)  * 100, 2) AS ret_1d,  COUNT(ret_1d)  AS n_1d, "
        "ROUND(AVG(ret_3d)  * 100, 2) AS ret_3d,  COUNT(ret_3d)  AS n_3d, "
        "ROUND(AVG(ret_7d)  * 100, 2) AS ret_7d,  COUNT(ret_7d)  AS n_7d, "
        "ROUND(AVG(ret_14d) * 100, 2) AS ret_14d, COUNT(ret_14d) AS n_14d "
        "FROM perf GROUP BY stage ORDER BY stage"
    )
    return _rows(conn, sql, tuple(params))


# ---------- lead time (section F) ----------


def lead_time(conn: sqlite3.Connection) -> list[dict]:
    """F1: zero-cross timing by stage over FINALIZED signals only, so a NULL
    bars_to_zero_cross genuinely means 'never crossed within the horizon'."""
    cte, params = _base()
    sql = cte + (
        "SELECT stage, COUNT(*) AS finalized_n, "
        "COALESCE(SUM(bars_to_zero_cross IS NOT NULL), 0) AS crossed_n, "
        "ROUND(AVG(bars_to_zero_cross IS NOT NULL) * 100, 1) AS cross_rate_pct, "
        "ROUND(AVG(bars_to_zero_cross), 2) AS avg_bars_to_cross, "
        "MIN(bars_to_zero_cross) AS min_bars, MAX(bars_to_zero_cross) AS max_bars "
        "FROM perf WHERE outcome_updated_at IS NOT NULL "
        "GROUP BY stage ORDER BY stage"
    )
    return _rows(conn, sql, tuple(params))


# ---------- per-symbol reliability (section I) ----------


# ---------- per-symbol scorecard with confidence bounds (section I + CIs) ----------


def by_symbol_scorecard(
    conn: sqlite3.Connection,
    horizon: Horizon = "7d",
    min_n: int = 5,
) -> list[dict]:
    """Per-symbol reliability *with confidence bounds*, ranked by the lower bound
    of expected value so small-n luck can't top the list.

    For each symbol's deduped, direction-normalized returns: win-rate with a
    **Wilson** interval and expectancy (mean return) with a **BCa bootstrap**
    interval (both via scipy). EV is the plain mean — that *is* the expectation
    per trade; the CI carries the skew/uncertainty. Ranked by `ev_lo` desc.
    """
    # Lazy import: the idle dashboard never loads scipy until this endpoint runs.
    from scipy import stats as sps

    col = f"ret_{horizon}"
    cte, params = _base()
    sql = cte + (
        f"SELECT symbol, asset_class, {col} AS r FROM perf WHERE {col} IS NOT NULL"
    )

    groups: dict[str, dict] = {}
    for row in conn.execute(sql, tuple(params)):
        g = groups.setdefault(row["symbol"], {"cls": None, "rs": []})
        g["rs"].append(row["r"])
        if g["cls"] is None:
            g["cls"] = row["asset_class"]

    out: list[dict] = []
    for symbol, g in groups.items():
        arr = np.asarray(g["rs"], dtype=float)
        n = int(arr.size)
        if n < min_n:
            continue
        wins = int((arr > 0).sum())
        win_lo, win_hi = sps.binomtest(wins, n).proportion_ci(method="wilson")

        mean = float(arr.mean())
        ev_lo = ev_hi = mean  # degenerate fallback (n<2 or zero variance)
        if n >= 2 and np.ptp(arr) > 0:
            try:
                ci = sps.bootstrap(
                    (arr,), np.mean, method="BCa", random_state=0
                ).confidence_interval
                ev_lo, ev_hi = float(ci.low), float(ci.high)
            except Exception:
                pass  # keep the mean fallback; a stats edge case must not 500

        # Payoff ratio = avg win / avg |loss|. None when there are no losses
        # (undefined / infinite); 0 when there are no wins.
        pos, neg = arr[arr > 0], arr[arr < 0]
        if neg.size == 0:
            payoff = None
        elif pos.size == 0:
            payoff = 0.0
        else:
            payoff = float(pos.mean() / -neg.mean())

        # SQN (Van Tharp) = mean / std · √min(n,100): edge × consistency × sample.
        # None when std is 0 (all-identical returns) — quality undefined.
        std = float(arr.std(ddof=1)) if n >= 2 else 0.0
        sqn = float(mean / std * np.sqrt(min(n, 100))) if std > 0 else None

        out.append({
            "symbol": symbol,
            "asset_class": g["cls"],
            "n": n,
            "win_pct": round(wins / n * 100, 1),
            "win_lo": round(win_lo * 100, 1),
            "win_hi": round(win_hi * 100, 1),
            "ev_pct": round(mean * 100, 2),
            "ev_lo": round(ev_lo * 100, 2),
            "ev_hi": round(ev_hi * 100, 2),
            "payoff": round(payoff, 2) if payoff is not None else None,
            "sqn": round(sqn, 2) if sqn is not None else None,
        })

    out.sort(key=lambda d: d["ev_lo"], reverse=True)
    return out


# ---------- win-rate by asset class x stage (section E2) ----------


def by_class(
    conn: sqlite3.Connection,
    horizon: Horizon = "7d",
    min_n: int = 1,
) -> list[dict]:
    """E2: win-rate by asset class x stage - which markets does the model work on?"""
    cte, params = _base()
    ret = f"ret_{horizon}"
    sql = cte + (
        f"SELECT asset_class, stage, COUNT(*) AS n, "
        f"ROUND(AVG({ret} > 0) * 100, 1) AS win_pct, "
        f"ROUND(AVG({ret}) * 100, 2) AS avg_ret_pct "
        f"FROM perf WHERE {ret} IS NOT NULL "
        f"GROUP BY asset_class, stage HAVING n >= ? ORDER BY avg_ret_pct DESC"
    )
    return _rows(conn, sql, (*params, min_n))


# ---------- threshold tuning buckets (section G) ----------


def thresholds(
    conn: sqlite3.Connection,
    kind: ThresholdKind,
    horizon: Horizon = "7d",
) -> list[dict]:
    """G1/G2: win-rate by proximity-to-zero (Stage 3) or reduction-from-peak
    (Stage 1) bucket. If the tightest/deepest buckets win more, the threshold
    is loose."""
    cte, params = _base()
    ret = f"ret_{horizon}"
    if kind == "proximity":
        bucket = (
            "CASE WHEN fire_macd_pct_of_price < 0.001 THEN 'a <0.1%' "
            "WHEN fire_macd_pct_of_price < 0.002 THEN 'b 0.1-0.2%' "
            "WHEN fire_macd_pct_of_price < 0.003 THEN 'c 0.2-0.3%' "
            "WHEN fire_macd_pct_of_price < 0.005 THEN 'd 0.3-0.5%' "
            "ELSE 'e >=0.5%' END"
        )
        cond = "stage = 'zero_line_proximity' AND fire_macd_pct_of_price IS NOT NULL"
    else:  # reduction
        bucket = (
            "CASE WHEN fire_reduction_from_peak < 0.4 THEN 'a 0.3-0.4' "
            "WHEN fire_reduction_from_peak < 0.6 THEN 'b 0.4-0.6' "
            "WHEN fire_reduction_from_peak < 0.8 THEN 'c 0.6-0.8' "
            "ELSE 'd 0.8-1.0' END"
        )
        cond = "stage = 'histogram_flattening' AND fire_reduction_from_peak IS NOT NULL"
    sql = cte + (
        f"SELECT {bucket} AS bucket, COUNT(*) AS n, "
        f"ROUND(AVG({ret} > 0) * 100, 1) AS win_pct, "
        f"ROUND(AVG({ret}) * 100, 2) AS avg_ret_pct "
        f"FROM perf WHERE {cond} AND {ret} IS NOT NULL "
        f"GROUP BY bucket ORDER BY bucket"
    )
    return _rows(conn, sql, tuple(params))


# ---------- robust distribution (median + quantiles, not just the mean) ----------


def distribution(
    conn: sqlite3.Connection,
    metric: Metric = "ret_7d",
    min_n: int = 1,
    winsor: float = 0.05,
) -> list[dict]:
    """Quantile + robust-mean summary of one metric, per stage x direction.

    Returns deduped per-signal values through stats.summarize(), then scales
    every stat to percent points (matching the other perf endpoints). Groups
    with fewer than `min_n` scored signals are dropped — robust stats need a
    handful of points to mean anything.
    """
    col = _METRIC_COL[metric]
    cte, params = _base()
    sql = cte + (
        f"SELECT stage, direction, {col} AS v FROM perf "
        f"WHERE {col} IS NOT NULL"
    )

    groups: dict[tuple[str, str], list[float]] = {}
    for r in conn.execute(sql, tuple(params)):
        groups.setdefault((r["stage"], r["direction"]), []).append(r["v"])

    out: list[dict] = []
    for (stage, direction), vals in groups.items():
        s = summarize(vals, winsor=winsor)
        if s is None or s["n"] < min_n:
            continue
        scaled = {
            k: (None if v is None else round(v * 100, 2))
            for k, v in s.items()
            if k != "n"
        }
        out.append({"stage": stage, "direction": direction, "metric": metric,
                    "n": s["n"], **scaled})
    out.sort(key=lambda d: (d["stage"], d["direction"]))
    return out
