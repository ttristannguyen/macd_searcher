"""SQL for the dashboard API.

Read-only SELECTs only. `asset_class` is joined inline from `asset_snapshots`
(the dashboard can't create the `signal_perf` view on a read-only connection).
Mirrors the immediate sections of docs/queries.sql (B, C, J).
"""

from __future__ import annotations

import sqlite3


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
        "s.fire_close, s.fire_macd, s.fire_macd_pct_of_price, s.fire_reduction_from_peak "
        "FROM signals s "
        "LEFT JOIN asset_snapshots a ON a.run_id = s.run_id AND a.symbol = s.symbol "
        "ORDER BY s.fired_at DESC LIMIT ?",
        (limit,),
    )


def by_stage_direction(conn: sqlite3.Connection) -> list[dict]:
    return _rows(
        conn,
        "SELECT stage, direction, COUNT(*) AS n FROM signals "
        "GROUP BY stage, direction ORDER BY n DESC",
    )


def by_asset_class(conn: sqlite3.Connection) -> list[dict]:
    return _rows(
        conn,
        "SELECT a.asset_class, COUNT(*) AS n "
        "FROM signals s "
        "LEFT JOIN asset_snapshots a ON a.run_id = s.run_id AND a.symbol = s.symbol "
        "GROUP BY a.asset_class ORDER BY n DESC",
    )


def top_symbols(conn: sqlite3.Connection, limit: int = 20) -> list[dict]:
    return _rows(
        conn,
        "SELECT symbol, COUNT(*) AS fires FROM signals "
        "GROUP BY symbol ORDER BY fires DESC LIMIT ?",
        (limit,),
    )


def signals_per_day(conn: sqlite3.Connection, days: int = 14) -> list[dict]:
    return _rows(
        conn,
        "SELECT substr(fired_at,1,10) AS day, COUNT(*) AS signals "
        "FROM signals GROUP BY day ORDER BY day DESC LIMIT ?",
        (days,),
    )


# ---------- counterfactual alert volume (section J) ----------


def proximity_headroom(conn: sqlite3.Connection) -> dict:
    row = conn.execute(
        "WITH per_run AS ("
        "  SELECT run_id, "
        "    SUM(macd_pct_of_price < 0.002) AS u02, "
        "    SUM(macd_pct_of_price < 0.005) AS u05, "
        "    SUM(macd_pct_of_price < 0.010) AS u10 "
        "  FROM asset_snapshots GROUP BY run_id"
        ") SELECT ROUND(AVG(u02),1), ROUND(AVG(u05),1), ROUND(AVG(u10),1) FROM per_run"
    ).fetchone()
    u02, u05, u10 = (row or (None, None, None))
    return {
        "avg_assets_under_0_2pct": u02,
        "avg_assets_under_0_5pct": u05,
        "avg_assets_under_1pct": u10,
    }
