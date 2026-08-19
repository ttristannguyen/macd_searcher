"""Tests for the SQLite logging layer. Uses in-memory databases."""

from __future__ import annotations

import sqlite3

from macd_searcher import db
from macd_searcher.hyperliquid import AssetMeta
from macd_searcher.signals import AssetMetrics, Signal


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys=ON")
    db.init_schema(conn)
    return conn


def test_init_schema_creates_tables_and_indexes():
    conn = _conn()
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"runs", "asset_snapshots", "signals"} <= tables
    indexes = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='index'")}
    assert "idx_signals_outcome_pending" in indexes


def test_init_schema_signals_has_rsi_column():
    conn = _conn()
    cols = {r[1] for r in conn.execute("PRAGMA table_info(signals)")}
    assert "fire_rsi_14" in cols


def test_init_schema_signals_has_peak_context_columns():
    conn = _conn()
    cols = {r[1] for r in conn.execute("PRAGMA table_info(signals)")}
    assert {"fire_hist_peak_ratio", "fire_hist_peak_pct", "fire_hist_top_n"} <= cols


def test_init_schema_migrates_a_db_predating_peak_context():
    """A signals table created before these columns existed picks them up on
    init_schema, non-destructively — existing rows keep their data."""
    conn = sqlite3.connect(":memory:")
    # Mirrors the pre-peak-context shape: the outcome columns already existed, so
    # init_schema's indexes still build.
    conn.execute(
        "CREATE TABLE signals (signal_id TEXT PRIMARY KEY, run_id TEXT, symbol TEXT, "
        "stage TEXT, direction TEXT, fired_at TEXT, fire_close REAL, fire_macd REAL, "
        "fire_hist REAL, outcome_updated_at TEXT)"
    )
    conn.execute("INSERT INTO signals (signal_id, symbol) VALUES ('old', 'BTC')")
    db.init_schema(conn)
    cols = {r[1] for r in conn.execute("PRAGMA table_info(signals)")}
    assert {"fire_hist_peak_ratio", "fire_hist_peak_pct", "fire_hist_top_n"} <= cols
    row = conn.execute(
        "SELECT symbol, fire_hist_peak_ratio FROM signals WHERE signal_id='old'"
    ).fetchone()
    assert row == ("BTC", None)   # pre-existing row survives, new column NULL


def test_insert_signals_stores_peak_context():
    conn = _conn()
    db.start_run(conn, "r1", "t0", None, None, None)
    db.insert_signals(conn, "r1", [
        Signal(name="ETH", stage="histogram_flattening", direction="bearish",
               close=100.0, macd=0.1, hist=0.2, hist_peak=0.5,
               reduction_from_peak=0.6, rsi_14=68.4,
               hist_peak_ratio=1.8, hist_peak_pct=82.0, hist_top_n=14),
    ], "2026-01-01T00:00:00+00:00")
    row = conn.execute(
        "SELECT fire_hist_peak_ratio, fire_hist_peak_pct, fire_hist_top_n "
        "FROM signals WHERE symbol='ETH'"
    ).fetchone()
    assert row == (1.8, 82.0, 14)


def test_insert_signals_peak_context_defaults_when_no_baseline():
    """A signal with no prior same-sign excursion stores NULL/NULL/0, not garbage."""
    conn = _conn()
    db.start_run(conn, "r1", "t0", None, None, None)
    db.insert_signals(conn, "r1", [
        Signal(name="SOL", stage="histogram_flattening", direction="bullish",
               close=100.0, macd=-0.1, hist=-0.2, hist_peak=-0.5,
               reduction_from_peak=0.6),
    ], "2026-01-01T00:00:00+00:00")
    row = conn.execute(
        "SELECT fire_hist_peak_ratio, fire_hist_peak_pct, fire_hist_top_n "
        "FROM signals WHERE symbol='SOL'"
    ).fetchone()
    assert row == (None, None, 0)


def test_finalize_run_records_confident_count():
    """Run-level count of high-confidence signals, so 'am I getting enough of these
    per week?' doesn't need a scan over `signals`."""
    conn = _conn()
    db.start_run(conn, "r1", "t0", None, None, None)
    db.finalize_run(conn, "r1", completed_at="t1", signals_count=7, confident_count=2)
    row = conn.execute(
        "SELECT signals_count, confident_count FROM runs WHERE run_id='r1'"
    ).fetchone()
    assert row == (7, 2)


def test_add_missing_columns_is_idempotent():
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE t (a INTEGER)")
    db._add_missing_columns(conn, "t", {"a": "INTEGER", "b": "REAL"})
    assert {r[1] for r in conn.execute("PRAGMA table_info(t)")} == {"a", "b"}  # b added, a kept
    db._add_missing_columns(conn, "t", {"a": "INTEGER", "b": "REAL"})  # no-op on re-run
    assert {r[1] for r in conn.execute("PRAGMA table_info(t)")} == {"a", "b"}


def test_insert_signals_stores_rsi():
    conn = _conn()
    db.start_run(conn, "r1", "t0", None, None, None)
    db.insert_signals(conn, "r1", [
        Signal(name="BTC", stage="histogram_flattening", direction="bearish",
               close=100.0, macd=0.1, hist=0.2, hist_peak=0.5,
               reduction_from_peak=0.6, rsi_14=68.4),
    ], "2026-01-01T00:00:00+00:00")
    row = conn.execute("SELECT fire_rsi_14 FROM signals WHERE symbol='BTC'").fetchone()
    assert row[0] == 68.4


def test_run_lifecycle_roundtrip():
    conn = _conn()
    db.start_run(conn, "r1", "2026-01-01T00:00:00+00:00", "abc123", "hash16", '{"a":1}')
    db.finalize_run(
        conn, "r1",
        completed_at="2026-01-01T00:01:00+00:00",
        duration_s=60.0,
        universe_total=312,
        universe_kept=144,
        signals_count=5,
        notify_status="dry_run",
    )
    row = conn.execute(
        "SELECT code_version, universe_total, universe_kept, signals_count, notify_status "
        "FROM runs WHERE run_id='r1'"
    ).fetchone()
    assert row == ("abc123", 312, 144, 5, "dry_run")


def test_finalize_run_records_failure():
    conn = _conn()
    db.start_run(conn, "r1", "t0", None, None, None)
    db.finalize_run(conn, "r1", completed_at="t1", notify_status="failed", error="ValueError: boom")
    row = conn.execute("SELECT notify_status, error, duration_s FROM runs WHERE run_id='r1'").fetchone()
    assert row == ("failed", "ValueError: boom", None)


def _metrics(name: str) -> AssetMetrics:
    return AssetMetrics(
        name=name, close=100.0, macd=1.0, macd_signal=0.5, hist=0.5, atr=2.0,
        macd_pct_of_price=0.01, macd_shrinking_n_bars=3,
        live_close=101.0, live_hist=0.4, live_hist_pct_of_price=0.004,
        hist_recent_peak=1.0, hist_reduction_from_peak=0.6, hist_shrinking_n_bars=2,
    )


def test_insert_snapshots_with_and_without_assetmeta():
    conn = _conn()
    db.start_run(conn, "r1", "t0", None, None, None)
    assets = {
        "BTC": AssetMeta("BTC", mark_px=60000.0, day_ntl_vlm_usd=1e9,
                         open_interest_coin=1000.0, open_interest_usd=6e7),
    }
    db.insert_snapshots(conn, "r1", assets, [_metrics("BTC"), _metrics("xyz:TSLA")])

    btc = conn.execute(
        "SELECT asset_class, mark_px, macd_shrinking_n_bars FROM asset_snapshots WHERE symbol='BTC'"
    ).fetchone()
    assert btc == ("crypto", 60000.0, 3)

    tsla = conn.execute(
        "SELECT asset_class, mark_px FROM asset_snapshots WHERE symbol='xyz:TSLA'"
    ).fetchone()
    # No AssetMeta supplied for TSLA → liquidity columns are NULL, class still derived.
    assert tsla == ("equity", None)


def test_insert_snapshots_is_idempotent_per_run():
    conn = _conn()
    db.start_run(conn, "r1", "t0", None, None, None)
    db.insert_snapshots(conn, "r1", {}, [_metrics("BTC")])
    db.insert_snapshots(conn, "r1", {}, [_metrics("BTC")])  # INSERT OR REPLACE
    count = conn.execute("SELECT COUNT(*) FROM asset_snapshots WHERE run_id='r1'").fetchone()[0]
    assert count == 1


def test_insert_signals_roundtrip_with_null_outcomes():
    conn = _conn()
    db.start_run(conn, "r1", "t0", None, None, None)
    sigs = [
        Signal(name="xyz:TSLA", stage="histogram_flattening", direction="bearish",
               close=400.0, macd=0.1, hist=-0.2, hist_peak=0.3, reduction_from_peak=0.5),
        Signal(name="ETH", stage="histogram_flattening", direction="bullish",
               close=2000.0, macd=-50.0, hist=-10.0, hist_peak=-25.0,
               reduction_from_peak=0.6),
    ]
    db.insert_signals(conn, "r1", sigs, "2026-01-01T00:00:00+00:00")

    rows = conn.execute(
        "SELECT symbol, stage, direction, fire_macd, fire_macd_pct_of_price, outcome_updated_at "
        "FROM signals ORDER BY symbol"
    ).fetchall()
    # fire_macd_pct_of_price is a legacy Stage-3 column — always NULL now.
    assert rows == [
        ("ETH", "histogram_flattening", "bullish", -50.0, None, None),
        ("xyz:TSLA", "histogram_flattening", "bearish", 0.1, None, None),
    ]
    # Each signal row gets a unique id.
    ids = [r[0] for r in conn.execute("SELECT signal_id FROM signals")]
    assert len(ids) == len(set(ids)) == 2


def test_foreign_key_rejects_orphan_signal():
    conn = _conn()
    sig = Signal(name="BTC", stage="histogram_flattening", direction="bullish",
                 close=1.0, macd=0.0, hist=0.0)
    try:
        db.insert_signals(conn, "missing_run", [sig], "t0")
        raised = False
    except sqlite3.IntegrityError:
        raised = True
    assert raised


def test_pending_signals_and_outcome_update_roundtrip():
    conn = _conn()
    db.start_run(conn, "r1", "t0", None, None, None)
    sigs = [
        Signal(name="BTC", stage="histogram_flattening", direction="bullish",
               close=100.0, macd=-0.1, hist=0.0, hist_peak=-0.3, reduction_from_peak=0.5),
        Signal(name="ETH", stage="histogram_flattening", direction="bearish",
               close=200.0, macd=0.1, hist=0.05),
    ]
    db.insert_signals(conn, "r1", sigs, "2026-01-01T00:00:00+00:00")

    # Both start unscored.
    pending = db.fetch_pending_signals(conn)
    assert len(pending) == 2
    assert {r["symbol"] for r in pending} == {"BTC", "ETH"}

    # Finalize the BTC one.
    btc_id = next(r["signal_id"] for r in pending if r["symbol"] == "BTC")
    db.update_signal_outcome(
        conn, btc_id,
        px_1d=101.0, px_3d=103.0, px_7d=107.0, px_14d=114.0,
        max_favorable_move_pct=0.15, max_adverse_move_pct=-0.05,
        bars_to_zero_cross=3, zero_cross_observed_at="2026-01-04T00:00:00+00:00",
        outcome_updated_at="2026-01-15T00:00:00+00:00",
    )

    # Now only ETH is pending.
    pending2 = db.fetch_pending_signals(conn)
    assert [r["symbol"] for r in pending2] == ["ETH"]

    row = conn.execute(
        "SELECT px_7d, bars_to_zero_cross, max_favorable_move_pct FROM signals WHERE signal_id=?",
        (btc_id,),
    ).fetchone()
    assert tuple(row) == (107.0, 3, 0.15)  # row_factory may be sqlite3.Row here


def test_partial_outcome_leaves_signal_pending():
    conn = _conn()
    db.start_run(conn, "r1", "t0", None, None, None)
    db.insert_signals(conn, "r1", [
        Signal(name="SOL", stage="histogram_flattening", direction="bullish",
               close=50.0, macd=-0.01, hist=0.0)
    ], "2026-01-01T00:00:00+00:00")
    sid = db.fetch_pending_signals(conn)[0]["signal_id"]

    # Partial: fill early prices but leave outcome_updated_at NULL (not finalized).
    db.update_signal_outcome(
        conn, sid,
        px_1d=51.0, px_3d=52.0, px_7d=None, px_14d=None,
        max_favorable_move_pct=0.04, max_adverse_move_pct=-0.02,
        bars_to_zero_cross=None, zero_cross_observed_at=None,
        outcome_updated_at=None,
    )
    # Still pending so it gets revisited next run.
    assert [r["symbol"] for r in db.fetch_pending_signals(conn)] == ["SOL"]
