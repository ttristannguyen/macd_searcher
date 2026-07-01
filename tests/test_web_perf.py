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
    """Symbols firing on several post-fix days to exercise the scorecard stats:
    ACE has n=3 with a loss (real Wilson/bootstrap/payoff/SQN); WIN has two
    all-positive, identical fires (no losses, zero variance) for the None paths."""
    conn = db.connect(path)
    db.init_schema(conn)
    db.start_run(conn, "r1", f"{DAY_A}T00:00:00+00:00", "abc", "h", "{}")
    db.insert_snapshots(conn, "r1", {}, [_metrics("ACE", 0.001), _metrics("WIN", 0.001)])
    for day, px7 in (("2026-06-12", 110.0), ("2026-06-13", 105.0), ("2026-06-14", 98.0)):
        _fire(conn, "ACE", "zero_line_proximity", "bullish", f"{day}T08:00:00+00:00",
              100.0, macd_pct=0.001, px_7d=px7, mfe=0.1, mae=-0.02, bars=2, finalized=True)
    for day in ("2026-06-12", "2026-06-13"):
        _fire(conn, "WIN", "zero_line_proximity", "bullish", f"{day}T08:00:00+00:00",
              100.0, macd_pct=0.001, px_7d=105.0, mfe=0.05, mae=-0.01, bars=2, finalized=True)
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
    ace = next(r for r in rows if r["symbol"] == "ACE")
    assert ace["n"] == 3 and ace["asset_class"] == "crypto"
    assert abs(ace["win_pct"] - 66.7) < 0.1
    assert abs(ace["ev_pct"] - 4.33) < 0.1                    # mean of 10/5/-2
    assert ace["win_lo"] <= ace["win_pct"] <= ace["win_hi"]   # Wilson brackets the point
    assert ace["ev_lo"] <= ace["ev_pct"] <= ace["ev_hi"]      # bootstrap brackets the mean
    assert abs(ace["payoff"] - 3.75) < 0.01                   # avg win 7.5% / avg loss 2%
    assert abs(ace["sqn"] - 1.25) < 0.05                      # mean/std·√3


def test_scorecard_payoff_sqn_none_paths(multi_client):
    # WIN: two identical +5% fires → no losses (payoff undefined) and zero
    # variance (SQN undefined). Both must serialize as null, not crash.
    rows = multi_client.get("/api/perf/scorecard?min_n=2").json()
    win = next(r for r in rows if r["symbol"] == "WIN")
    assert win["win_pct"] == 100.0
    assert win["payoff"] is None
    assert win["sqn"] is None


def test_scorecard_min_n_gate(multi_client):
    assert multi_client.get("/api/perf/scorecard?min_n=4").json() == []  # max n is 3


# ---- counterfactual reduction buckets (snapshot self-join, below 0.3) ----

# Snapshot dates after SNAPSHOT_FIX_CUTOFF (2026-07-01); CF_PRE is before it.
CF_D0 = "2026-07-02"
CF_D7 = "2026-07-09"
CF_PRE = "2026-06-29"


def _snap(name, *, red, live_close, live_hist=-0.4, peak=-1.0, shrink=2) -> AssetMetrics:
    """Snapshot metrics for the counterfactual query. red/peak = None makes a pure
    forward price point (in the price map, but not a scorable entry)."""
    return AssetMetrics(
        name=name, close=live_close, macd=-1.0, macd_signal=-0.5, hist=-0.5, atr=2.0,
        macd_pct_of_price=0.004, macd_shrinking_n_bars=shrink,
        live_close=live_close, live_hist=live_hist, live_hist_pct_of_price=0.004,
        hist_recent_peak=peak, hist_reduction_from_peak=red, hist_shrinking_n_bars=shrink,
    )


def _snap_run(conn, run_id, started_at, metrics) -> None:
    db.start_run(conn, run_id, started_at, "abc", "h", "{}")
    db.insert_snapshots(conn, run_id, {}, metrics)


def _seed_cf(path: str) -> None:
    conn = db.connect(path)
    db.init_schema(conn)
    # Day 0 — AAA reduction 0.15 (bullish), BBB reduction 0.5 (bearish).
    _snap_run(conn, "cf1", f"{CF_D0}T08:00:00+00:00", [
        _snap("AAA", red=0.15, live_close=100.0, live_hist=-0.4, peak=-1.0),
        _snap("BBB", red=0.50, live_close=200.0, live_hist=0.4, peak=2.0),
    ])
    # Same day, later run — AAA reduction 0.9: dedup must drop it (keep the 08:00).
    _snap_run(conn, "cf2", f"{CF_D0}T12:00:00+00:00", [
        _snap("AAA", red=0.90, live_close=100.0, live_hist=-0.4, peak=-1.0),
    ])
    # Day +7 — forward price points only (red=None → not their own entries).
    _snap_run(conn, "cf3", f"{CF_D7}T08:00:00+00:00", [
        _snap("AAA", red=None, live_close=110.0, peak=None),  # +10% bullish → win
        _snap("BBB", red=None, live_close=190.0, peak=None),  # 1-190/200 = +5% bearish → win
    ])
    # Pre-fix — reduction 0.05 would land in 'a <0.1' but is before the cutoff.
    _snap_run(conn, "cf0", f"{CF_PRE}T08:00:00+00:00", [
        _snap("CCC", red=0.05, live_close=100.0, live_hist=-0.4, peak=-1.0),
    ])
    conn.close()


@pytest.fixture
def cf_client(tmp_path):
    path = str(tmp_path / "cf.sqlite3")
    _seed_cf(path)
    app.dependency_overrides[get_conn] = _conn_to(path)
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_reduction_counterfactual_buckets(cf_client):
    rows = cf_client.get("/api/perf/reduction-counterfactual?horizon=7d").json()
    by = {r["bucket"]: r for r in rows}
    # Only the two post-fix entries; dedup kept AAA's 0.15 (not the 0.9 → no 'g').
    assert set(by) == {"b 0.1-0.2", "e 0.4-0.6"}
    assert by["b 0.1-0.2"]["n"] == 1
    assert by["b 0.1-0.2"]["win_pct"] == 100.0
    assert by["b 0.1-0.2"]["ev_pct"] == 10.0          # AAA bullish +10%
    assert by["b 0.1-0.2"]["drawdown_proxy_pct"] == 10.0
    assert by["e 0.4-0.6"]["ev_pct"] == 5.0           # BBB bearish 1-190/200


def test_reduction_counterfactual_excludes_pre_fix(cf_client):
    rows = cf_client.get("/api/perf/reduction-counterfactual?horizon=7d").json()
    # CCC (reduction 0.05) fired before SNAPSHOT_FIX_CUTOFF → 'a <0.1' never appears.
    assert "a <0.1" not in {r["bucket"] for r in rows}


def test_reduction_counterfactual_unscorable_when_no_forward(cf_client):
    # 14d horizon: CF_D0 + 14 = 2026-07-16 has no snapshot, so nothing is scorable.
    assert cf_client.get("/api/perf/reduction-counterfactual?horizon=14d").json() == []
