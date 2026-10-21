"""SQL for the dashboard API.

Read-only SELECTs only. `asset_class` is joined inline from `asset_snapshots`
(the dashboard can't create the `signal_perf` view on a read-only connection).
Mirrors the immediate sections of docs/queries.sql (B, C). All signal-composition
queries filter to stage = 'histogram_flattening' (Stage 3 was removed).
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone

from ..signals import (
    CONFIDENCE_V3_BEAR_MAX_PEAK_PCT,
    CONFIDENCE_V3_MAX_PEAK_PCT,
    CONFIDENCE_V3_MAX_REDUCTION,
)


def _rows(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> list[dict]:
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


# ---------- operational health (section B) ----------


def table_counts(conn: sqlite3.Connection) -> dict[str, int]:
    out = {}
    for name in ("runs", "asset_snapshots", "signals"):
        out[name] = conn.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]
    return out


def latest_run(conn: sqlite3.Connection) -> dict | None:
    row = conn.execute(
        "SELECT run_id, started_at, completed_at, duration_s, code_version, "
        "universe_total, universe_kept, signals_count, notify_status, error "
        "FROM runs ORDER BY started_at DESC LIMIT 1"
    ).fetchone()
    return dict(row) if row else None


def recent_runs(conn: sqlite3.Connection, limit: int = 20) -> list[dict]:
    return _rows(
        conn,
        "SELECT started_at, universe_total, universe_kept, signals_count, "
        "notify_status, duration_s FROM runs ORDER BY started_at DESC LIMIT ?",
        (limit,),
    )


def runs_per_day(conn: sqlite3.Connection, days: int = 14) -> list[dict]:
    return _rows(
        conn,
        "SELECT substr(started_at,1,10) AS day, COUNT(*) AS runs "
        "FROM runs GROUP BY day ORDER BY day DESC LIMIT ?",
        (days,),
    )


def notify_status_breakdown(conn: sqlite3.Connection) -> list[dict]:
    return _rows(
        conn,
        "SELECT notify_status, COUNT(*) AS n FROM runs "
        "GROUP BY notify_status ORDER BY n DESC",
    )


# ---------- signal volume & composition (section C) ----------


def recent_signals(conn: sqlite3.Connection, limit: int = 50) -> list[dict]:
    return _rows(
        conn,
        "SELECT s.fired_at, s.symbol, a.asset_class, s.stage, s.direction, "
        "s.fire_close, s.fire_macd, s.fire_reduction_from_peak, s.fire_rsi_14, "
        "s.fire_hist_peak_ratio, s.fire_hist_peak_pct, s.fire_hist_top_n "
        "FROM signals s "
        "LEFT JOIN asset_snapshots a ON a.run_id = s.run_id AND a.symbol = s.symbol "
        "WHERE s.stage = 'histogram_flattening' "
        "ORDER BY s.fired_at DESC LIMIT ?",
        (limit,),
    )


# ---------- recent fires by strategy leg ----------
#
# The v3 marker plus the legs of docs/profit_strategies.md B3, as live watch lists.
# v3 and the bearish low-peak leg take their thresholds from signals.py, so they
# can't drift from the Confidence tab. The two good-fire cuts were found on the
# 2023-26 history (exploratory), so they live here rather than in signals.py.
GOOD_BULL_MAX_PEAK_PCT = 25  # bullish, lowest peak_pct quarter: where v3's edge sits
PULLBACK_MIN_PEAK_PCT = 50   # bearish after a strong move: a pullback in a leader, taken LONG

# Order is the order the sections render in. Keys mirror models.StrategyRule.
STRATEGY_RULES: dict[str, str] = {
    "v3_bullish": (f"s.direction = 'bullish' AND s.fire_hist_peak_pct <= {CONFIDENCE_V3_MAX_PEAK_PCT} "
                   f"AND s.fire_reduction_from_peak < {CONFIDENCE_V3_MAX_REDUCTION}"),
    "bull_low_peak": f"s.direction = 'bullish' AND s.fire_hist_peak_pct <= {GOOD_BULL_MAX_PEAK_PCT}",
    "bear_pullback": f"s.direction = 'bearish' AND s.fire_hist_peak_pct >= {PULLBACK_MIN_PEAK_PCT}",
    "bear_low_peak": f"s.direction = 'bearish' AND s.fire_hist_peak_pct <= {CONFIDENCE_V3_BEAR_MAX_PEAK_PCT}",
}


def recent_by_strategy(conn: sqlite3.Connection, days: int = 7) -> list[dict]:
    """Each strategy leg's fires over the last `days`, one row per symbol.

    The scanner re-fires a setup on every run while it holds, so raw rows repeat a
    symbol many times a day. A watch list wants the symbol once: its latest fire,
    with the window's first fire and fire count beside it.
    """
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    sections = []
    for rule, condition in STRATEGY_RULES.items():
        rows = _rows(
            conn,
            "SELECT * FROM ("
            "  SELECT s.fired_at, s.symbol, a.asset_class, s.stage, s.direction, "
            "  s.fire_close, s.fire_macd, s.fire_reduction_from_peak, s.fire_rsi_14, "
            "  s.fire_hist_peak_ratio, s.fire_hist_peak_pct, s.fire_hist_top_n, "
            "  MIN(s.fired_at) OVER (PARTITION BY s.symbol) AS first_fired_at, "
            "  COUNT(*) OVER (PARTITION BY s.symbol) AS fires, "
            "  ROW_NUMBER() OVER (PARTITION BY s.symbol ORDER BY s.fired_at DESC) AS latest "
            "  FROM signals s "
            "  LEFT JOIN asset_snapshots a ON a.run_id = s.run_id AND a.symbol = s.symbol "
            f" WHERE s.stage = 'histogram_flattening' AND s.fired_at >= ? AND {condition}"
            ") WHERE latest = 1 ORDER BY fired_at DESC",
            (since,),
        )
        sections.append({"rule": rule, "rows": rows})
    return sections


def by_stage_direction(conn: sqlite3.Connection) -> list[dict]:
    return _rows(
        conn,
        "SELECT stage, direction, COUNT(*) AS n FROM signals "
        "WHERE stage = 'histogram_flattening' "
        "GROUP BY stage, direction ORDER BY n DESC",
    )


def by_asset_class(conn: sqlite3.Connection) -> list[dict]:
    return _rows(
        conn,
        "SELECT a.asset_class, COUNT(*) AS n "
        "FROM signals s "
        "LEFT JOIN asset_snapshots a ON a.run_id = s.run_id AND a.symbol = s.symbol "
        "WHERE s.stage = 'histogram_flattening' "
        "GROUP BY a.asset_class ORDER BY n DESC",
    )


def top_symbols(conn: sqlite3.Connection, limit: int = 20) -> list[dict]:
    return _rows(
        conn,
        "SELECT symbol, COUNT(*) AS fires FROM signals "
        "WHERE stage = 'histogram_flattening' "
        "GROUP BY symbol ORDER BY fires DESC LIMIT ?",
        (limit,),
    )


def signals_per_day(conn: sqlite3.Connection, days: int = 14) -> list[dict]:
    return _rows(
        conn,
        "SELECT substr(fired_at,1,10) AS day, COUNT(*) AS signals "
        "FROM signals WHERE stage = 'histogram_flattening' "
        "GROUP BY day ORDER BY day DESC LIMIT ?",
        (days,),
    )
