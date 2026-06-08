"""Tests for the dashboard API.

Skipped entirely if the `web` extra isn't installed, so the core test suite
stays green without FastAPI. Uses a seeded temp DB via dependency override.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from macd_searcher import db  # noqa: E402
from macd_searcher.hyperliquid import AssetMeta  # noqa: E402
from macd_searcher.signals import AssetMetrics, Signal  # noqa: E402
from macd_searcher.web.app import app, get_conn  # noqa: E402


def _metrics(name: str, macd_pct: float) -> AssetMetrics:
    return AssetMetrics(
        name=name, close=100.0, macd=-1.0, macd_signal=-0.5, hist=-0.5, atr=2.0,
        macd_pct_of_price=macd_pct, macd_shrinking_n_bars=2,
        live_close=101.0, live_hist=-0.4, live_hist_pct_of_price=0.004,
        hist_recent_peak=-1.0, hist_reduction_from_peak=0.6, hist_shrinking_n_bars=2,
    )


def _seed(path: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    conn = sqlite3.connect(path)
    db.init_schema(conn)
    db.start_run(conn, "r1", now, "abc123", "hash", "{}")
    db.finalize_run(conn, "r1", completed_at=now, duration_s=13.0,
                    universe_total=300, universe_kept=140, signals_count=2,
                    notify_status="sent")
    assets = {"BTC": AssetMeta("BTC", 60000.0, 1e9, 100.0, 6e6)}
    db.insert_snapshots(conn, "r1", assets,
                        [_metrics("BTC", 0.0001), _metrics("xyz:TSLA", 0.02)])
    db.insert_signals(conn, "r1", [
        Signal("BTC", "zero_line_proximity", "bullish", close=60000.0,
               macd=-0.5, hist=-0.1, macd_pct_of_price=0.0002),
        Signal("xyz:TSLA", "histogram_flattening", "bearish", close=400.0,
               macd=1.0, hist=0.2, hist_peak=0.5, reduction_from_peak=0.6),
    ], now)
    conn.close()


def _conn_to(path: str):
    def _get():
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
    return _get


@pytest.fixture
def client(tmp_path):
    path = str(tmp_path / "test.sqlite3")
    _seed(path)
    app.dependency_overrides[get_conn] = _conn_to(path)
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_health_ok(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"  # run seeded at "now"
    assert body["counts"] == {"runs": 1, "asset_snapshots": 2, "signals": 2}
    assert body["latest_run"]["notify_status"] == "sent"
    assert body["last_run_age_seconds"] is not None


def test_runs(client):
    r = client.get("/api/runs?limit=5")
    assert r.status_code == 200
    rows = r.json()
    assert len(rows) == 1
    assert rows[0]["notify_status"] == "sent"
    assert rows[0]["universe_kept"] == 140


def test_recent_signals_has_asset_class(client):
    r = client.get("/api/signals/recent?limit=10")
    rows = r.json()
    assert len(rows) == 2
    by_symbol = {row["symbol"]: row for row in rows}
    assert by_symbol["BTC"]["asset_class"] == "crypto"
    assert by_symbol["xyz:TSLA"]["asset_class"] == "equity"
    assert by_symbol["xyz:TSLA"]["direction"] == "bearish"


def test_by_stage_direction(client):
    rows = client.get("/api/stats/by-stage-direction").json()
    keys = {(r["stage"], r["direction"]): r["n"] for r in rows}
    assert keys[("zero_line_proximity", "bullish")] == 1
    assert keys[("histogram_flattening", "bearish")] == 1


def test_by_class(client):
    rows = client.get("/api/stats/by-class").json()
    counts = {r["asset_class"]: r["n"] for r in rows}
    assert counts["crypto"] == 1
    assert counts["equity"] == 1


def test_notify_status(client):
    rows = client.get("/api/stats/notify-status").json()
    assert {"notify_status": "sent", "n": 1} in rows


def test_top_symbols(client):
    rows = client.get("/api/stats/top-symbols?limit=10").json()
    fires = {r["symbol"]: r["fires"] for r in rows}
    assert fires["BTC"] == 1
    assert fires["xyz:TSLA"] == 1


def test_proximity_headroom(client):
    body = client.get("/api/stats/proximity-headroom").json()
    # Only BTC (0.0001) is under every band; TSLA (0.02) is under none.
    assert body["avg_assets_under_0_2pct"] == 1.0
    assert body["avg_assets_under_1pct"] == 1.0


def test_missing_db_returns_503(monkeypatch, tmp_path):
    # Use the real dependency, pointed at a non-existent DB.
    app.dependency_overrides.clear()
    monkeypatch.setenv("MACD_SEARCHER_DB_PATH", str(tmp_path / "nope.sqlite3"))
    r = TestClient(app).get("/api/health")
    assert r.status_code == 503
