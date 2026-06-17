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

Optional `since` (an ISO date/time string) filters to signals fired at or after
it — set it to the deploy date of a detector fix to drop pre-fix noise.
"""

from __future__ import annotations

import sqlite3
from typing import Literal

# Horizon is whitelisted (not bound) because it names a column. The Literal is
# enforced at the FastAPI layer, so only these four values ever reach the SQL.
Horizon = Literal["1d", "3d", "7d", "14d"]
ThresholdKind = Literal["proximity", "reduction"]


def _rows(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> list[dict]:
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def _base(since: str | None) -> tuple[str, list]:
    """CTE exposing `perf`: deduped, class-joined, direction-normalized signals.

    Returns (cte_sql, params). Callers append a `SELECT ... FROM perf ...` and
    extend the param list.
    """
    where = "WHERE fired_at >= ?" if since else ""
    params: list = [since] if since else []
    cte = f"""
    WITH first_fire AS (
        SELECT symbol, stage, direction, MIN(fired_at) AS first_fired
        FROM signals
        {where}
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

    Counts raw signals (no dedup) — this measures whether the update_outcomes
    job is keeping up, not performance.
    """
    row = conn.execute(
        "SELECT COUNT(*) AS total, "
        "COALESCE(SUM(outcome_updated_at IS NOT NULL), 0) AS finalized, "
        "COALESCE(SUM(px_1d  IS NOT NULL), 0) AS have_1d, "
        "COALESCE(SUM(px_3d  IS NOT NULL), 0) AS have_3d, "
        "COALESCE(SUM(px_7d  IS NOT NULL), 0) AS have_7d, "
        "COALESCE(SUM(px_14d IS NOT NULL), 0) AS have_14d "
        "FROM signals"
    ).fetchone()
    pend = conn.execute(
        "SELECT MIN(fired_at) AS oldest_pending, COUNT(*) AS pending "
        "FROM signals WHERE outcome_updated_at IS NULL"
    ).fetchone()
    out = dict(row)
    out.update(dict(pend))
    return out


# ---------- performance / edge (section E) ----------


def summary(
    conn: sqlite3.Connection,
    horizon: Horizon = "7d",
    since: str | None = None,
    min_n: int = 1,
) -> list[dict]:
    """E1 headline: win-rate and avg/worst/best return by stage x direction."""
    cte, params = _base(since)
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


def by_horizon(conn: sqlite3.Connection, since: str | None = None) -> list[dict]:
    """E3: average return at each horizon by stage - does the edge grow or decay?"""
    cte, params = _base(since)
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


def lead_time(conn: sqlite3.Connection, since: str | None = None) -> list[dict]:
    """F1: zero-cross timing by stage over FINALIZED signals only, so a NULL
    bars_to_zero_cross genuinely means 'never crossed within the horizon'."""
    cte, params = _base(since)
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


# ---------- tradeability: MFE / MAE (section H) ----------


def excursions(conn: sqlite3.Connection, since: str | None = None) -> list[dict]:
    """H1: average favorable (MFE) and adverse (MAE) excursion by stage x direction."""
    cte, params = _base(since)
    sql = cte + (
        "SELECT stage, direction, COUNT(*) AS n, "
        "ROUND(AVG(max_favorable_move_pct) * 100, 2) AS avg_mfe_pct, "
        "ROUND(AVG(max_adverse_move_pct) * 100, 2) AS avg_mae_pct "
        "FROM perf WHERE max_favorable_move_pct IS NOT NULL "
        "GROUP BY stage, direction ORDER BY stage, direction"
    )
    return _rows(conn, sql, tuple(params))


# ---------- per-symbol reliability (section I) ----------


def by_symbol(
    conn: sqlite3.Connection,
    horizon: Horizon = "7d",
    since: str | None = None,
    min_n: int = 5,
) -> list[dict]:
    """I1: which tickers' signals you can trust (min_n scored signals)."""
    cte, params = _base(since)
    ret = f"ret_{horizon}"
    sql = cte + (
        f"SELECT symbol, MAX(asset_class) AS asset_class, COUNT(*) AS n, "
        f"ROUND(AVG({ret} > 0) * 100, 1) AS win_pct, "
        f"ROUND(AVG({ret}) * 100, 2) AS avg_ret_pct "
        f"FROM perf WHERE {ret} IS NOT NULL "
        f"GROUP BY symbol HAVING n >= ? ORDER BY avg_ret_pct DESC"
    )
    return _rows(conn, sql, (*params, min_n))


# ---------- win-rate by asset class x stage (section E2) ----------


def by_class(
    conn: sqlite3.Connection,
    horizon: Horizon = "7d",
    since: str | None = None,
    min_n: int = 1,
) -> list[dict]:
    """E2: win-rate by asset class x stage - which markets does the model work on?"""
    cte, params = _base(since)
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
    since: str | None = None,
) -> list[dict]:
    """G1/G2: win-rate by proximity-to-zero (Stage 3) or reduction-from-peak
    (Stage 1) bucket. If the tightest/deepest buckets win more, the threshold
    is loose."""
    cte, params = _base(since)
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
