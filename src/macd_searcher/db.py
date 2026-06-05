"""SQLite logging layer.

Three tables (see README "Data logging"):
  - runs            : one row per cron invocation; config snapshot + operational status
  - asset_snapshots : one row per (run, asset); detector intermediates for offline tuning
  - signals         : one row per fired alert; outcome columns filled in later by a separate job

All timestamps are stored as ISO-8601 UTC strings. Logging is best-effort —
the caller is expected to swallow exceptions so a DB problem never breaks a scan.
"""

from __future__ import annotations

import os
import sqlite3
import subprocess
import uuid
from typing import TYPE_CHECKING, Mapping

from .classify import classify_asset

if TYPE_CHECKING:
    from .hyperliquid import AssetMeta
    from .signals import AssetMetrics, Signal


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS runs (
    run_id          TEXT PRIMARY KEY,
    started_at      TEXT NOT NULL,
    completed_at    TEXT,
    duration_s      REAL,
    code_version    TEXT,
    config_hash     TEXT,
    config_json     TEXT,
    universe_total  INTEGER,
    universe_kept   INTEGER,
    signals_count   INTEGER,
    notify_status   TEXT,
    error           TEXT
);

CREATE TABLE IF NOT EXISTS asset_snapshots (
    run_id                    TEXT NOT NULL REFERENCES runs(run_id),
    symbol                    TEXT NOT NULL,
    asset_class               TEXT NOT NULL,
    mark_px                   REAL,
    day_ntl_vlm_usd           REAL,
    open_interest_usd         REAL,
    close                     REAL NOT NULL,
    macd                      REAL NOT NULL,
    macd_signal               REAL NOT NULL,
    hist                      REAL NOT NULL,
    atr                       REAL,
    macd_pct_of_price         REAL,
    macd_shrinking_n_bars     INTEGER,
    live_close                REAL,
    live_hist                 REAL,
    live_hist_pct_of_price    REAL,
    hist_recent_peak          REAL,
    hist_reduction_from_peak  REAL,
    hist_shrinking_n_bars     INTEGER,
    PRIMARY KEY (run_id, symbol)
);

CREATE TABLE IF NOT EXISTS signals (
    signal_id                 TEXT PRIMARY KEY,
    run_id                    TEXT NOT NULL REFERENCES runs(run_id),
    symbol                    TEXT NOT NULL,
    stage                     TEXT NOT NULL,
    direction                 TEXT NOT NULL,
    fired_at                  TEXT NOT NULL,
    fire_close                REAL NOT NULL,
    fire_macd                 REAL NOT NULL,
    fire_hist                 REAL NOT NULL,
    fire_macd_pct_of_price    REAL,
    fire_atr_multiple         REAL,
    fire_hist_peak            REAL,
    fire_reduction_from_peak  REAL,
    bars_to_zero_cross        INTEGER,
    zero_cross_observed_at    TEXT,
    px_1d                     REAL,
    px_3d                     REAL,
    px_7d                     REAL,
    px_14d                    REAL,
    max_favorable_move_pct    REAL,
    max_adverse_move_pct      REAL,
    outcome_updated_at        TEXT
);

CREATE INDEX IF NOT EXISTS idx_signals_symbol_fired ON signals(symbol, fired_at);
CREATE INDEX IF NOT EXISTS idx_signals_outcome_pending ON signals(outcome_updated_at);
CREATE INDEX IF NOT EXISTS idx_snapshots_symbol ON asset_snapshots(symbol);
"""


def connect(path: str) -> sqlite3.Connection:
    """Open (creating parent dirs as needed) a SQLite connection with WAL + FKs."""
    if path != ":memory:":
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA_SQL)
    conn.commit()


def git_short_sha() -> str | None:
    """Best-effort current commit SHA; None if not a git repo or git is missing."""
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=5,
        )
        if out.returncode == 0:
            return out.stdout.strip() or None
    except Exception:
        return None
    return None


def start_run(
    conn: sqlite3.Connection,
    run_id: str,
    started_at: str,
    code_version: str | None,
    config_hash: str | None,
    config_json: str | None,
) -> None:
    conn.execute(
        "INSERT INTO runs (run_id, started_at, code_version, config_hash, config_json) "
        "VALUES (?, ?, ?, ?, ?)",
        (run_id, started_at, code_version, config_hash, config_json),
    )
    conn.commit()


def finalize_run(
    conn: sqlite3.Connection,
    run_id: str,
    *,
    completed_at: str,
    duration_s: float | None = None,
    universe_total: int | None = None,
    universe_kept: int | None = None,
    signals_count: int | None = None,
    notify_status: str | None = None,
    error: str | None = None,
) -> None:
    conn.execute(
        "UPDATE runs SET completed_at=?, duration_s=?, universe_total=?, universe_kept=?, "
        "signals_count=?, notify_status=?, error=? WHERE run_id=?",
        (completed_at, duration_s, universe_total, universe_kept,
         signals_count, notify_status, error, run_id),
    )
    conn.commit()


def insert_snapshots(
    conn: sqlite3.Connection,
    run_id: str,
    assets_by_symbol: Mapping[str, "AssetMeta"],
    metrics: list["AssetMetrics"],
) -> None:
    rows = []
    for m in metrics:
        am = assets_by_symbol.get(m.name)
        rows.append((
            run_id, m.name, classify_asset(m.name),
            am.mark_px if am else None,
            am.day_ntl_vlm_usd if am else None,
            am.open_interest_usd if am else None,
            m.close, m.macd, m.macd_signal, m.hist, m.atr,
            m.macd_pct_of_price, m.macd_shrinking_n_bars,
            m.live_close, m.live_hist, m.live_hist_pct_of_price,
            m.hist_recent_peak, m.hist_reduction_from_peak, m.hist_shrinking_n_bars,
        ))
    conn.executemany(
        "INSERT OR REPLACE INTO asset_snapshots ("
        "run_id, symbol, asset_class, mark_px, day_ntl_vlm_usd, open_interest_usd, "
        "close, macd, macd_signal, hist, atr, macd_pct_of_price, macd_shrinking_n_bars, "
        "live_close, live_hist, live_hist_pct_of_price, hist_recent_peak, "
        "hist_reduction_from_peak, hist_shrinking_n_bars"
        ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        rows,
    )
    conn.commit()


def insert_signals(
    conn: sqlite3.Connection,
    run_id: str,
    signals: list["Signal"],
    fired_at: str,
) -> None:
    rows = []
    for s in signals:
        rows.append((
            uuid.uuid4().hex, run_id, s.name, s.stage, s.direction, fired_at,
            s.close, s.macd, s.hist, s.macd_pct_of_price, s.atr_multiple,
            s.hist_peak, s.reduction_from_peak,
        ))
    conn.executemany(
        "INSERT INTO signals ("
        "signal_id, run_id, symbol, stage, direction, fired_at, "
        "fire_close, fire_macd, fire_hist, fire_macd_pct_of_price, fire_atr_multiple, "
        "fire_hist_peak, fire_reduction_from_peak"
        ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        rows,
    )
    conn.commit()
