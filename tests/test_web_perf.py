"""Tests for the /api/perf/* outcome endpoints.

Seeds a small, fully-deterministic set of finalized signals so we can assert
exact win-rates and returns, and verify the two corrections baked into perf.py:
  * per-asset-day dedup (a same-day repeat must not inflate stats), and
  * the `since` filter (drop pre-fix signals).

Skipped if the `web` extra isn't installed.
"""

from __future__ import annotations

import sqlite3

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from macd_searcher import db  # noqa: E402
from macd_searcher.signals import AssetMetrics, Signal  # noqa: E402
from macd_searcher.web.app import app, get_conn  # noqa: E402

# Post-fix dates (after DETECTOR_FIX_CUTOFF = 2026-06-09T14:00Z), so the
# endpoints' default post-fix filter keeps them.
DAY_A = "2026-06-12"
DAY_B = "2026-06-13"
# Before the cutoff: a contaminated pre-fix signal that must be excluded by default.
PRE_FIX = "2026-06-05"


def _metrics(name: str, macd_pct: float) -> AssetMetrics:
    return AssetMetrics(
        name=name, close=100.0, macd=-1.0, macd_signal=-0.5, hist=-0.5, atr=2.0,
        macd_pct_of_price=macd_pct, macd_shrinking_n_bars=2,
        live_close=101.0, live_hist=-0.4, live_hist_pct_of_price=0.004,
        hist_recent_peak=-1.0, hist_reduction_from_peak=0.6, hist_shrinking_n_bars=2,
    )


def _fire(conn, symbol, stage, direction, fired_at, fire_close, *,
          macd_pct=None, reduction=None, px_7d=None, mfe=None, mae=None,
          bars=None, finalized=False):
    sig = Signal(
        symbol, stage, direction, close=fire_close, macd=-0.5, hist=-0.1,
        macd_pct_of_price=macd_pct,
        hist_peak=0.5 if reduction is not None else None,
        reduction_from_peak=reduction,
    )
    db.insert_signals(conn, "r1", [sig], fired_at)
    conn.execute(
        "UPDATE signals SET px_1d=?, px_3d=?, px_7d=?, px_14d=?, "
        "max_favorable_move_pct=?, max_adverse_move_pct=?, bars_to_zero_cross=?, "
        "outcome_updated_at=? WHERE symbol=? AND fired_at=?",
        (px_7d, px_7d, px_7d, px_7d, mfe, mae, bars,
         (fired_at if finalized else None), symbol, fired_at),
    )
    conn.commit()


def _seed(path: str) -> None:
    conn = db.connect(path)
    db.init_schema(conn)
    db.start_run(conn, "r1", f"{DAY_A}T00:00:00+00:00", "abc123", "hash", "{}")
    db.finalize_run(conn, "r1", completed_at=f"{DAY_A}T00:05:00+00:00",
                    notify_status="sent")
    db.insert_snapshots(conn, "r1", {}, [
        _metrics("BTC", 0.0005), _metrics("ETH", 0.0025),
        _metrics("xyz:TSLA", 0.02), _metrics("SOL", 0.01),
    ])

    # Day A — BTC fires twice (same asset-day): dedup must keep only the
    # earlier 08:00 win and drop the 12:00 loss.
    _fire(conn, "BTC", "zero_line_proximity", "bullish", f"{DAY_A}T08:00:00+00:00",
          100.0, macd_pct=0.0005, px_7d=110.0, mfe=0.12, mae=-0.02, bars=3, finalized=True)
    _fire(conn, "BTC", "zero_line_proximity", "bullish", f"{DAY_A}T12:00:00+00:00",
          100.0, macd_pct=0.0005, px_7d=90.0, mfe=0.0, mae=-0.10, bars=1, finalized=True)
    # Day A — ETH loss, never crossed zero within horizon (bars NULL).
    _fire(conn, "ETH", "zero_line_proximity", "bullish", f"{DAY_A}T08:00:00+00:00",
          200.0, macd_pct=0.0025, px_7d=190.0, mfe=0.03, mae=-0.06, bars=None, finalized=True)
    # Day B — TSLA bearish win (1 - 380/400 = +5%).
    _fire(conn, "xyz:TSLA", "histogram_flattening", "bearish", f"{DAY_B}T08:00:00+00:00",
          400.0, reduction=0.6, px_7d=380.0, mfe=0.06, mae=-0.01, bars=2, finalized=True)
    # Day B — SOL still pending (no outcome yet).
    _fire(conn, "SOL", "zero_line_proximity", "bullish", f"{DAY_B}T08:00:00+00:00",
          50.0, macd_pct=0.001, finalized=False)
    # PRE-FIX — a contaminated Stage-1-era signal; must be excluded by default.
    _fire(conn, "OLD", "zero_line_proximity", "bullish", f"{PRE_FIX}T08:00:00+00:00",
          100.0, macd_pct=0.001, px_7d=130.0, mfe=0.30, mae=-0.01, bars=1, finalized=True)
    conn.close()


def _seed_multi(path: str) -> None:
    """One symbol firing on several post-fix days, so the scorecard has n>=3 with
    variance to exercise the Wilson + bootstrap intervals."""
    conn = db.connect(path)
    db.init_schema(conn)
    db.start_run(conn, "r1", f"{DAY_A}T00:00:00+00:00", "abc", "h", "{}")
    db.insert_snapshots(conn, "r1", {}, [_metrics("ACE", 0.001)])
    for day, px7 in (("2026-06-12", 110.0), ("2026-06-13", 105.0), ("2026-06-14", 98.0)):
        _fire(conn, "ACE", "zero_line_proximity", "bullish", f"{day}T08:00:00+00:00",
              100.0, macd_pct=0.001, px_7d=px7, mfe=0.1, mae=-0.02, bars=2, finalized=True)
    conn.close()


def _conn_to(path: str):
    def _get():
        conn = db.connect(path)  # read/write here is fine; route only SELECTs
        conn.row_factory = sqlite3.Row  # match the production web connection
        try:
            yield conn
        finally:
            conn.close()
    return _get


@pytest.fixture
def client(tmp_path):
    path = str(tmp_path / "perf.sqlite3")
    _seed(path)
    app.dependency_overrides[get_conn] = _conn_to(path)
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def multi_client(tmp_path):
    path = str(tmp_path / "multi.sqlite3")
    _seed_multi(path)
    app.dependency_overrides[get_conn] = _conn_to(path)
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_readiness(client):
    body = client.get("/api/perf/readiness").json()
    assert body["total"] == 5
    assert body["finalized"] == 4      # SOL pending
    assert body["have_7d"] == 4
    assert body["pending"] == 1
    assert body["oldest_pending"] == f"{DAY_B}T08:00:00+00:00"


def test_summary_dedup(client):
    rows = client.get("/api/perf/summary?horizon=7d").json()
    by = {(r["stage"], r["direction"]): r for r in rows}
    # BTC duplicate dropped → zero_line bullish = BTC(+10%) + ETH(-5%): n=2.
    z = by[("zero_line_proximity", "bullish")]
    assert z["n"] == 2
    assert z["win_pct"] == 50.0
    assert z["avg_ret_pct"] == 2.5
    assert z["best_pct"] == 10.0
    assert z["worst_pct"] == -5.0
    # TSLA bearish win.
    t = by[("histogram_flattening", "bearish")]
    assert t["n"] == 1
    assert t["win_pct"] == 100.0
    assert t["avg_ret_pct"] == 5.0


def test_by_horizon(client):
    rows = client.get("/api/perf/by-horizon").json()
    by = {r["stage"]: r for r in rows}
    assert by["zero_line_proximity"]["n_7d"] == 2
    assert by["zero_line_proximity"]["ret_7d"] == 2.5
    assert by["histogram_flattening"]["ret_7d"] == 5.0


def test_lead_time(client):
    rows = client.get("/api/perf/lead-time").json()
    by = {r["stage"]: r for r in rows}
    z = by["zero_line_proximity"]
    assert z["finalized_n"] == 2          # BTC#1 + ETH (dup dropped)
    assert z["crossed_n"] == 1            # only BTC crossed
    assert z["cross_rate_pct"] == 50.0
    assert z["avg_bars_to_cross"] == 3.0


def test_by_class(client):
    rows = client.get("/api/perf/by-class?horizon=7d&min_n=1").json()
    by = {(r["asset_class"], r["stage"]): r for r in rows}
    assert by[("crypto", "zero_line_proximity")]["n"] == 2
    assert by[("crypto", "zero_line_proximity")]["avg_ret_pct"] == 2.5
    assert by[("equity", "histogram_flattening")]["avg_ret_pct"] == 5.0


def test_thresholds(client):
    prox = client.get("/api/perf/thresholds?kind=proximity").json()
    buckets = {r["bucket"]: r for r in prox}
    assert buckets["a <0.1%"]["n"] == 1     # BTC at 0.0005
    assert buckets["c 0.2-0.3%"]["n"] == 1   # ETH at 0.0025
    red = client.get("/api/perf/thresholds?kind=reduction").json()
    assert {r["bucket"] for r in red} == {"c 0.6-0.8"}  # TSLA reduction 0.6 (not < 0.6)


def test_invalid_horizon_422(client):
    assert client.get("/api/perf/summary?horizon=5d").status_code == 422


def test_distribution_ret7d(client):
    rows = client.get("/api/perf/distribution?metric=ret_7d").json()
    by = {(r["stage"], r["direction"]): r for r in rows}
    # zero_line bullish: deduped BTC(+10%) + ETH(-5%), dup dropped.
    z = by[("zero_line_proximity", "bullish")]
    assert z["n"] == 2
    assert z["median"] == 2.5
    assert z["mean"] == 2.5
    assert z["min"] == -5.0 and z["max"] == 10.0
    assert z["metric"] == "ret_7d"
    # single-point group has no std.
    t = by[("histogram_flattening", "bearish")]
    assert t["n"] == 1 and t["median"] == 5.0 and t["std"] is None


def test_distribution_metric_switch(client):
    rows = client.get("/api/perf/distribution?metric=mfe").json()
    by = {(r["stage"], r["direction"]): r for r in rows}
    assert by[("zero_line_proximity", "bullish")]["median"] == 7.5  # BTC 12% / ETH 3%

    mae = client.get("/api/perf/distribution?metric=mae").json()
    by_mae = {(r["stage"], r["direction"]): r for r in mae}
    assert by_mae[("zero_line_proximity", "bullish")]["median"] == -4.0


def test_distribution_min_n_drops_small_groups(client):
    rows = client.get("/api/perf/distribution?metric=ret_7d&min_n=2").json()
    assert len(rows) == 1
    assert rows[0]["stage"] == "zero_line_proximity"


def test_distribution_invalid_metric_422(client):
    assert client.get("/api/perf/distribution?metric=sharpe").status_code == 422


# ---- detector-fix filter (pre-fix Stage 1 contamination is always excluded) ----


def test_pre_fix_signals_excluded(client):
    # OLD fired before DETECTOR_FIX_CUTOFF, so it never reaches the stats:
    # zero_line bullish stays BTC + ETH (would be 3 if OLD leaked in), and
    # readiness counts 5 of the 6 seeded signals.
    rows = client.get("/api/perf/summary").json()
    z = next(r for r in rows if r["stage"] == "zero_line_proximity" and r["direction"] == "bullish")
    assert z["n"] == 2
    assert client.get("/api/perf/readiness").json()["total"] == 5


# ---- per-symbol scorecard (Wilson + bootstrap, ranked by EV lower bound) ----


def test_scorecard_ranks_by_ev_lower_bound(client):
    rows = client.get("/api/perf/scorecard?min_n=1").json()
    # n=1 each → EV CI is degenerate, so ev_lo == ev_pct → ranks by EV: BTC>TSLA>ETH.
    assert [r["symbol"] for r in rows] == ["BTC", "xyz:TSLA", "ETH"]
    by = {r["symbol"]: r for r in rows}
    assert by["BTC"]["win_pct"] == 100.0
    assert by["ETH"]["win_pct"] == 0.0
    assert by["BTC"]["ev_lo"] == by["BTC"]["ev_pct"]  # degenerate at n=1


def test_scorecard_confidence_bounds(multi_client):
    # ACE: 3 finalized fires, returns +10% / +5% / -2% → 2 wins of 3.
    rows = multi_client.get("/api/perf/scorecard?min_n=3").json()
    assert len(rows) == 1
    r = rows[0]
    assert r["symbol"] == "ACE" and r["n"] == 3 and r["asset_class"] == "crypto"
    assert abs(r["win_pct"] - 66.7) < 0.1
    assert abs(r["ev_pct"] - 4.33) < 0.1                  # mean of 10/5/-2
    assert r["win_lo"] <= r["win_pct"] <= r["win_hi"]     # Wilson brackets the point
    assert r["ev_lo"] <= r["ev_pct"] <= r["ev_hi"]        # bootstrap brackets the mean


def test_scorecard_min_n_gate(multi_client):
    assert multi_client.get("/api/perf/scorecard?min_n=4").json() == []  # ACE has only 3
