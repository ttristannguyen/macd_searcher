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
from macd_searcher import signals  # noqa: E402
from macd_searcher.signals import AssetMetrics, Signal, is_high_confidence  # noqa: E402
from macd_searcher.web import perf  # noqa: E402
from macd_searcher.web.app import app, get_conn  # noqa: E402

# Post-fix dates (after DETECTOR_FIX_CUTOFF = 2026-06-09T14:00Z), so the
# endpoints' default post-fix filter keeps them.
DAY_A = "2026-06-12"
DAY_B = "2026-06-13"
# Before the cutoff: a contaminated pre-fix signal that must be excluded by default.
PRE_FIX = "2026-06-05"


def _metrics(name: str, macd_pct: float, atr: float | None = 2.0) -> AssetMetrics:
    return AssetMetrics(
        name=name, close=100.0, macd=-1.0, macd_signal=-0.5, hist=-0.5, atr=atr,
        macd_pct_of_price=macd_pct, macd_shrinking_n_bars=2,
        live_close=101.0, live_hist=-0.4, live_hist_pct_of_price=0.004,
        hist_recent_peak=-1.0, hist_reduction_from_peak=0.6, hist_shrinking_n_bars=2,
    )


def _fire(conn, symbol, direction, fired_at, fire_close, *,
          reduction=0.5, rsi=None, px_7d=None, mfe=None, mae=None,
          bars=None, finalized=False, macd=-0.5, hist=-0.1,
          peak_ratio=None, peak_pct=None, top_n=0):
    """Insert one histogram_flattening signal and backfill its outcome columns.

    `macd`/`hist` are overridable because the MACD-signal-line analysis derives its
    axis from them (signal = macd - hist); `peak_*`/`top_n` feed the peak-context
    analysis. Tests that care about neither get harmless defaults.
    """
    sig = Signal(
        symbol, "histogram_flattening", direction, close=fire_close,
        macd=macd, hist=hist, hist_peak=0.5, reduction_from_peak=reduction,
        rsi_14=rsi,
        hist_peak_ratio=peak_ratio, hist_peak_pct=peak_pct, hist_top_n=top_n,
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
    _fire(conn, "BTC", "bullish", f"{DAY_A}T08:00:00+00:00",
          100.0, reduction=0.5, px_7d=110.0, mfe=0.12, mae=-0.02, bars=3, finalized=True)
    _fire(conn, "BTC", "bullish", f"{DAY_A}T12:00:00+00:00",
          100.0, reduction=0.5, px_7d=90.0, mfe=0.0, mae=-0.10, bars=1, finalized=True)
    # Day A — ETH loss, never crossed zero within horizon (bars NULL).
    _fire(conn, "ETH", "bullish", f"{DAY_A}T08:00:00+00:00",
          200.0, reduction=0.5, px_7d=190.0, mfe=0.03, mae=-0.06, bars=None, finalized=True)
    # Day B — TSLA bearish win (1 - 380/400 = +5%), reduction 0.6.
    _fire(conn, "xyz:TSLA", "bearish", f"{DAY_B}T08:00:00+00:00",
          400.0, reduction=0.6, px_7d=380.0, mfe=0.06, mae=-0.01, bars=2, finalized=True)
    # Day B — SOL still pending (no outcome yet).
    _fire(conn, "SOL", "bullish", f"{DAY_B}T08:00:00+00:00", 50.0, finalized=False)
    # PRE-FIX — before DETECTOR_FIX_CUTOFF; must be excluded by default.
    _fire(conn, "OLD", "bullish", f"{PRE_FIX}T08:00:00+00:00",
          100.0, px_7d=130.0, mfe=0.30, mae=-0.01, bars=1, finalized=True)
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
        _fire(conn, "ACE", "bullish", f"{day}T08:00:00+00:00",
              100.0, px_7d=px7, mfe=0.1, mae=-0.02, bars=2, finalized=True)
    for day in ("2026-06-12", "2026-06-13"):
        _fire(conn, "WIN", "bullish", f"{day}T08:00:00+00:00",
              100.0, px_7d=105.0, mfe=0.05, mae=-0.01, bars=2, finalized=True)
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
    # BTC duplicate dropped → S1 bullish = BTC(+10%) + ETH(-5%): n=2.
    z = by[("histogram_flattening", "bullish")]
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
    # One stage now; deduped BTC(+10) + ETH(-5) + TSLA(+5) → mean 3.33 over n=3.
    assert by["histogram_flattening"]["n_7d"] == 3
    assert by["histogram_flattening"]["ret_7d"] == 3.33


def test_horizon_curve(client):
    rows = client.get("/api/perf/horizon-curve").json()
    by = {r["horizon"]: r for r in rows}
    # px_1d=px_3d=px_7d=px_14d in the seed, so every horizon is identical:
    # deduped BTC(+10) + ETH(-5) + TSLA(+5); SOL pending excluded.
    assert set(by) == {"1d", "3d", "7d", "14d"}
    for h in ("1d", "3d", "7d", "14d"):
        r = by[h]
        assert r["n"] == 3
        assert r["win_pct"] == 66.7
        assert r["avg_ret_pct"] == 3.33
        assert r["best_pct"] == 10.0
        assert r["worst_pct"] == -5.0
        assert r["median_pct"] == 5.0


def test_lead_time(client):
    rows = client.get("/api/perf/lead-time").json()
    by = {r["stage"]: r for r in rows}
    z = by["histogram_flattening"]
    assert z["finalized_n"] == 3          # BTC#1 + ETH + TSLA (BTC dup dropped)
    assert z["crossed_n"] == 2            # BTC (3 bars) + TSLA (2 bars); ETH never crossed
    assert z["cross_rate_pct"] == 66.7
    assert z["avg_bars_to_cross"] == 2.5


def test_by_class(client):
    rows = client.get("/api/perf/by-class?horizon=7d&min_n=1").json()
    by = {(r["asset_class"], r["stage"]): r for r in rows}
    assert by[("crypto", "histogram_flattening")]["n"] == 2
    assert by[("crypto", "histogram_flattening")]["avg_ret_pct"] == 2.5
    assert by[("equity", "histogram_flattening")]["avg_ret_pct"] == 5.0


def test_thresholds(client):
    red = client.get("/api/perf/thresholds").json()
    by = {r["bucket"]: r for r in red}
    assert set(by) == {"b 0.4-0.6", "c 0.6-0.8"}
    assert by["b 0.4-0.6"]["n"] == 2   # BTC + ETH at reduction 0.5 (dedup drops BTC dup)
    assert by["c 0.6-0.8"]["n"] == 1   # TSLA at reduction 0.6 (not < 0.6)


# ---- asset-class filter (?classes=) ----
# The seed is mixed-class: BTC/ETH/SOL = crypto, xyz:TSLA = equity.


def test_summary_class_filter(client):
    crypto = {(r["stage"], r["direction"]): r for r in client.get("/api/perf/summary?classes=crypto").json()}
    assert set(crypto) == {("histogram_flattening", "bullish")}  # BTC + ETH, no TSLA
    assert crypto[("histogram_flattening", "bullish")]["n"] == 2

    equity = {(r["stage"], r["direction"]): r for r in client.get("/api/perf/summary?classes=equity").json()}
    assert set(equity) == {("histogram_flattening", "bearish")}  # TSLA only
    assert equity[("histogram_flattening", "bearish")]["n"] == 1


def test_class_filter_combo_and_unknown_equal_all(client):
    allc = {(r["stage"], r["direction"], r["n"]) for r in client.get("/api/perf/summary").json()}
    combo = {(r["stage"], r["direction"], r["n"]) for r in client.get("/api/perf/summary?classes=crypto,equity").json()}
    unknown = {(r["stage"], r["direction"], r["n"]) for r in client.get("/api/perf/summary?classes=bogus").json()}
    assert combo == allc            # both classes = unfiltered
    assert unknown == allc          # unknown parsed to None = all, never empty


def test_readiness_class_filter(client):
    # Raw (no-dedup) post-fix S1 counts: crypto = BTC×2 + ETH + SOL = 4, equity = TSLA = 1.
    assert client.get("/api/perf/readiness?classes=crypto").json()["total"] == 4
    assert client.get("/api/perf/readiness?classes=equity").json()["total"] == 1
    assert client.get("/api/perf/readiness").json()["total"] == 5


def test_invalid_horizon_422(client):
    assert client.get("/api/perf/summary?horizon=5d").status_code == 422


def test_distribution_ret7d(client):
    rows = client.get("/api/perf/distribution?metric=ret_7d").json()
    by = {(r["stage"], r["direction"]): r for r in rows}
    # S1 bullish: deduped BTC(+10%) + ETH(-5%), dup dropped.
    z = by[("histogram_flattening", "bullish")]
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
    assert by[("histogram_flattening", "bullish")]["median"] == 7.5  # BTC 12% / ETH 3%

    mae = client.get("/api/perf/distribution?metric=mae").json()
    by_mae = {(r["stage"], r["direction"]): r for r in mae}
    assert by_mae[("histogram_flattening", "bullish")]["median"] == -4.0


def test_distribution_min_n_drops_small_groups(client):
    rows = client.get("/api/perf/distribution?metric=ret_7d&min_n=2").json()
    assert len(rows) == 1  # only S1 bullish has n=2 (BTC+ETH); bearish TSLA is n=1
    assert rows[0]["stage"] == "histogram_flattening"
    assert rows[0]["direction"] == "bullish"


def test_distribution_invalid_metric_422(client):
    assert client.get("/api/perf/distribution?metric=sharpe").status_code == 422


# ---- detector-fix filter (pre-fix Stage 1 contamination is always excluded) ----


def test_pre_fix_signals_excluded(client):
    # OLD fired before DETECTOR_FIX_CUTOFF, so it never reaches the stats:
    # zero_line bullish stays BTC + ETH (would be 3 if OLD leaked in), and
    # readiness counts 5 of the 6 seeded signals.
    rows = client.get("/api/perf/summary").json()
    z = next(r for r in rows if r["stage"] == "histogram_flattening" and r["direction"] == "bullish")
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


# ---- RSI-bucket signal-quality analysis ----


def _seed_rsi(path: str) -> None:
    conn = db.connect(path)
    db.init_schema(conn)
    db.start_run(conn, "r1", f"{DAY_A}T00:00:00+00:00", "abc", "h", "{}")
    db.insert_snapshots(conn, "r1", {}, [_metrics(f"RB{i}", 0.001) for i in range(1, 6)])

    # Bullish: RSI 25 win (+10%), RSI 35 loss (-5%), RSI 65 win (+8%).
    _fire(conn, "RB1", "bullish", f"{DAY_A}T08:00:00+00:00", 100.0, rsi=25.0, px_7d=110.0, finalized=True)
    _fire(conn, "RB2", "bullish", f"{DAY_A}T08:00:00+00:00", 100.0, rsi=35.0, px_7d=95.0, finalized=True)
    _fire(conn, "RB3", "bullish", f"{DAY_A}T08:00:00+00:00", 100.0, rsi=65.0, px_7d=108.0, finalized=True)
    # Bearish: RSI 75 win (price fell -> +12% normalized), RSI 45 loss (price rose -> -6%).
    _fire(conn, "RB4", "bearish", f"{DAY_A}T08:00:00+00:00", 100.0, rsi=75.0, px_7d=88.0, finalized=True)
    _fire(conn, "RB5", "bearish", f"{DAY_A}T08:00:00+00:00", 100.0, rsi=45.0, px_7d=106.0, finalized=True)
    # No RSI recorded (pre-RSI-change signal) — must be excluded entirely.
    _fire(conn, "RB6", "bullish", f"{DAY_B}T08:00:00+00:00", 100.0, rsi=None, px_7d=120.0, finalized=True)
    conn.close()


@pytest.fixture
def rsi_client(tmp_path):
    path = str(tmp_path / "rsi.sqlite3")
    _seed_rsi(path)
    app.dependency_overrides[get_conn] = _conn_to(path)
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_rsi_buckets_win_and_ev(rsi_client):
    rows = rsi_client.get("/api/perf/rsi-buckets").json()
    # px_1d=px_3d=px_7d=px_14d in _fire, so every horizon is identical.
    by = {(r["direction"], r["rsi_bucket"], r["horizon"]): r for r in rows}

    r = by[("bullish", "a <30", "7d")]
    assert r["n"] == 1 and r["win_pct"] == 100.0 and r["avg_ret_pct"] == 10.0

    r = by[("bullish", "b 30-40", "7d")]
    assert r["n"] == 1 and r["win_pct"] == 0.0 and r["avg_ret_pct"] == -5.0

    r = by[("bullish", "e 60-70", "7d")]
    assert r["n"] == 1 and r["win_pct"] == 100.0 and r["avg_ret_pct"] == 8.0

    r = by[("bearish", "f >=70", "7d")]
    assert r["n"] == 1 and r["win_pct"] == 100.0 and r["avg_ret_pct"] == 12.0

    r = by[("bearish", "c 40-50", "7d")]
    assert r["n"] == 1 and r["win_pct"] == 0.0 and r["avg_ret_pct"] == -6.0

    assert {r["horizon"] for r in rows} == {"1d", "3d", "7d", "14d"}


def test_rsi_buckets_excludes_signals_without_rsi(rsi_client):
    rows = rsi_client.get("/api/perf/rsi-buckets").json()
    # RB6 has no fire_rsi_14 → contributes to no bucket.
    total_n = sum(r["n"] for r in rows if r["horizon"] == "7d")
    assert total_n == 5


# ---- confidence cohort ----
#
# The cohort is derived in SQL from thresholds that live in signals.py. These tests
# pin the boundaries AND cross-check the SQL against is_high_confidence, which is the
# only thing stopping the two implementations from drifting apart.

# (direction, reduction, peak_pct, top_n) laid out around every boundary.
# (direction, reduction, macd, hist). _metrics pins atr=2.0, so the rule's axis
# sig/ATR = (macd - hist) / 2.0 is exactly half the raw signal line here.
_CONF_CASES = [
    ("bullish", 0.45, -2.2, -0.2),   # sig/ATR -1.00, red 0.45 -> in
    ("bullish", 0.59, -1.3, -0.2),   # sig/ATR -0.55, red 0.59 -> just inside both
    ("bullish", 0.60, -2.2, -0.2),   # reduction exactly at the cap -> out
    ("bullish", 0.45, -1.2, -0.2),   # sig/ATR exactly -0.50 -> out (strict <)
    ("bullish", 0.45, +1.8, -0.2),   # signal line above zero -> out
    ("bullish", 0.85, -0.3, -0.2),   # misses on both counts
    ("bearish", 0.45, -2.2, -0.2),   # would qualify but for direction
    ("bearish", 0.45, +3.2, +0.2),   # an ordinary bearish fire
]


def _seed_confidence(path: str) -> None:
    conn = db.connect(path)
    db.init_schema(conn)
    db.start_run(conn, "r1", f"{DAY_A}T00:00:00+00:00", "abc", "h", "{}")
    db.insert_snapshots(conn, "r1", {}, [
        _metrics(f"CF{i}", 0.001) for i in range(len(_CONF_CASES))
    ])
    # Alternating win/loss so win-rate and EV are non-degenerate in both cohorts.
    # Direction-normalized: bullish wants price up, bearish wants it down.
    for i, (direction, red, macd, hist) in enumerate(_CONF_CASES):
        up = i % 2 == 0
        px = (110.0 if up else 94.0) if direction == "bullish" else (90.0 if up else 106.0)
        _fire(conn, f"CF{i}", direction, f"{DAY_A}T08:00:00+00:00", 100.0,
              reduction=red, macd=macd, hist=hist,
              px_7d=px, mfe=0.12, mae=-0.03, finalized=True)
    conn.close()


@pytest.fixture
def confidence_client(tmp_path):
    path = str(tmp_path / "conf.sqlite3")
    _seed_confidence(path)
    app.dependency_overrides[get_conn] = _conn_to(path)
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_confidence_sql_matches_python_predicate(confidence_client, tmp_path):
    """The guard against drift: for the same rows, the SQL cohort must equal
    signals.is_high_confidence. If someone edits one rule and not the other — or
    changes a constant without re-deriving the SQL — this fails."""
    conn = sqlite3.connect(str(tmp_path / "conf.sqlite3"))
    conn.row_factory = sqlite3.Row
    cte, params = perf._base()
    sql = cte + (
        f"SELECT symbol, {perf._CONFIDENCE_SQL} AS cohort FROM perf"
    )
    from_sql = {r["symbol"]: r["cohort"] for r in conn.execute(sql, tuple(params))}
    conn.close()

    assert len(from_sql) == len(_CONF_CASES)
    for i, (direction, red, macd, hist) in enumerate(_CONF_CASES):
        # atr=2.0 matches what _metrics wrote to asset_snapshots, which is the value
        # the SQL divides by — the whole point of the closed-bar alignment.
        sig = Signal(f"CF{i}", "histogram_flattening", direction, close=100.0,
                     macd=macd, hist=hist, hist_peak=0.5, reduction_from_peak=red,
                     atr=2.0)
        expected = "confident" if is_high_confidence(sig) else "rest"
        assert from_sql[f"CF{i}"] == expected, f"CF{i} {(direction, red, macd, hist)}"


def test_confidence_summary_splits_cohorts(confidence_client):
    rows = confidence_client.get("/api/perf/confidence-summary?horizon=7d").json()
    by = {r["cohort"]: r for r in rows}
    assert set(by) == {"confident", "rest"}

    # Only the first two cases qualify (see _CONF_CASES).
    assert by["confident"]["n"] == 2
    assert by["rest"]["n"] == len(_CONF_CASES) - 2
    assert by["confident"]["share_pct"] == round(2 / len(_CONF_CASES) * 100, 1)
    # Shares of the two cohorts account for everything scored.
    assert by["confident"]["share_pct"] + by["rest"]["share_pct"] == pytest.approx(100.0, abs=0.2)
    for r in rows:
        assert r["horizon"] == "7d"
        assert r["mfe_pct"] == 12.0 and r["mae_pct"] == -3.0


def test_confidence_summary_payoff_none_without_losses(confidence_client, tmp_path):
    """Payoff is undefined, not infinite, when a cohort never lost."""
    path = str(tmp_path / "allwin.sqlite3")
    conn = db.connect(path)
    db.init_schema(conn)
    db.start_run(conn, "r1", f"{DAY_A}T00:00:00+00:00", "abc", "h", "{}")
    db.insert_snapshots(conn, "r1", {}, [_metrics("AW1", 0.001)])
    _fire(conn, "AW1", "bullish", f"{DAY_A}T08:00:00+00:00", 100.0,
          reduction=0.45, macd=-2.2, hist=-0.2, px_7d=110.0, finalized=True)
    conn.close()

    app.dependency_overrides[get_conn] = _conn_to(path)
    rows = TestClient(app).get("/api/perf/confidence-summary").json()
    app.dependency_overrides.clear()
    conf = next(r for r in rows if r["cohort"] == "confident")
    assert conf["win_pct"] == 100.0 and conf["payoff"] is None


def test_confidence_timeline_buckets_by_month(confidence_client):
    rows = confidence_client.get("/api/perf/confidence-timeline").json()
    assert rows, "expected at least one month"
    assert all(r["month"] == DAY_A[:7] for r in rows)
    assert {r["cohort"] for r in rows} == {"confident", "rest"}
    # Thin months are reported with their n rather than hidden.
    assert sum(r["n"] for r in rows) == len(_CONF_CASES)


def test_confidence_sensitivity_box_tiles_the_confident_cohort(confidence_client):
    """Cells are disjoint bands, and the boxed (`in_rule`) ones must add up to the
    confident cohort exactly — if they don't, the box on the tab is drawn around
    something other than what gets marked confident."""
    grid = confidence_client.get("/api/perf/confidence-sensitivity").json()
    assert len(grid) == 6 * 6

    box = [c for c in grid if c["in_rule"]]
    assert box, "the rule should cover at least one cell"
    # Every boxed band sits wholly below both thresholds.
    for c in box:
        assert c["sig_atr_hi"] is not None and c["sig_atr_hi"] <= signals.CONFIDENCE_MAX_SIG_ATR
        assert c["red_hi"] <= signals.CONFIDENCE_MAX_REDUCTION

    summary = confidence_client.get("/api/perf/confidence-summary").json()
    conf = next(r for r in summary if r["cohort"] == "confident")
    boxed_n = sum(c["n"] for c in box)
    assert boxed_n == conf["n"]
    boxed_ev = sum(c["n"] * c["ev_pct"] for c in box if c["n"]) / boxed_n
    assert boxed_ev == pytest.approx(conf["ev_pct"], abs=0.01)


def test_confidence_endpoints_respect_class_filter(confidence_client):
    """All seeded symbols classify as crypto, so 'equity' empties every panel."""
    for path in ("confidence-summary", "confidence-timeline", "confidence-sensitivity"):
        rows = confidence_client.get(f"/api/perf/{path}?classes=equity").json()
        if path == "confidence-sensitivity":
            assert all(c["n"] == 0 for c in rows)   # grid shape is fixed, cells empty
        else:
            assert rows == []


# ---- MACD signal line as a % of price ----
#
# Same metric as the ATR view, normalized by fire_close instead. Buckets are even
# 2%-wide steps, so with fire_close=100 a signal line of 3.0 lands in 'h 2..4'.


def _seed_macd_pct(path: str) -> None:
    conn = db.connect(path)
    db.init_schema(conn)
    db.start_run(conn, "r1", f"{DAY_A}T00:00:00+00:00", "abc", "h", "{}")
    db.insert_snapshots(conn, "r1", {}, [_metrics(f"MP{i}", 0.001) for i in range(1, 7)])
    at = f"{DAY_A}T08:00:00+00:00"

    # signal = macd - hist; with close=100 the bucket is just that value as a %.
    # Bearish, spanning the positive side.
    _fire(conn, "MP1", "bearish", at, 100.0, macd=3.2, hist=0.2, px_7d=88.0, finalized=True)   # +3.0 -> h 2..4
    _fire(conn, "MP2", "bearish", at, 100.0, macd=11.2, hist=0.2, px_7d=106.0, finalized=True) # +11.0 -> l >=10
    # Bullish, spanning the negative side.
    _fire(conn, "MP3", "bullish", at, 100.0, macd=-5.2, hist=-0.2, px_7d=110.0, finalized=True)  # -5.0 -> d -6..-4
    _fire(conn, "MP4", "bullish", at, 100.0, macd=-12.2, hist=-0.2, px_7d=95.0, finalized=True)  # -12.0 -> a <-10
    # A different price scales the same raw signal into a different bucket — the
    # whole point of this normalization.
    _fire(conn, "MP5", "bearish", at, 50.0, macd=3.2, hist=0.2, px_7d=44.0, finalized=True)    # +6.0 -> j 6..8
    conn.close()


@pytest.fixture
def macd_pct_client(tmp_path):
    path = str(tmp_path / "macdpct.sqlite3")
    _seed_macd_pct(path)
    app.dependency_overrides[get_conn] = _conn_to(path)
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_macd_signal_pct_buckets_win_and_ev(macd_pct_client):
    rows = macd_pct_client.get("/api/perf/macd-signal-pct-buckets").json()
    by = {(r["direction"], r["bucket"], r["horizon"]): r for r in rows}

    r = by[("bearish", "h 2..4", "7d")]
    assert r["n"] == 1 and r["win_pct"] == 100.0 and r["avg_ret_pct"] == 12.0

    r = by[("bearish", "l >=10", "7d")]
    assert r["n"] == 1 and r["win_pct"] == 0.0 and r["avg_ret_pct"] == -6.0

    r = by[("bullish", "d -6..-4", "7d")]
    assert r["n"] == 1 and r["win_pct"] == 100.0 and r["avg_ret_pct"] == 10.0

    r = by[("bullish", "a <-10", "7d")]
    assert r["n"] == 1 and r["win_pct"] == 0.0 and r["avg_ret_pct"] == -5.0

    assert {r["horizon"] for r in rows} == {"1d", "3d", "7d", "14d"}


def test_macd_signal_pct_normalizes_by_price(macd_pct_client):
    """MP5 carries the same raw signal line as MP1 (3.0) at half the price, so it
    lands two bands higher. Guards against the divisor being dropped."""
    rows = macd_pct_client.get("/api/perf/macd-signal-pct-buckets").json()
    by = {(r["direction"], r["bucket"], r["horizon"]): r for r in rows}
    assert by[("bearish", "j 6..8", "7d")]["n"] == 1
    assert by[("bearish", "h 2..4", "7d")]["n"] == 1


def test_macd_signal_pct_buckets_excludes_bad_fire_close(macd_pct_client, tmp_path):
    """fire_close of 0 would divide by zero; such a row contributes nowhere."""
    path = str(tmp_path / "zeroclose.sqlite3")
    conn = db.connect(path)
    db.init_schema(conn)
    db.start_run(conn, "r1", f"{DAY_A}T00:00:00+00:00", "abc", "h", "{}")
    db.insert_snapshots(conn, "r1", {}, [_metrics("ZC1", 0.001), _metrics("ZC2", 0.001)])
    _fire(conn, "ZC1", "bearish", f"{DAY_A}T08:00:00+00:00", 0.0,
          macd=3.2, hist=0.2, px_7d=88.0, finalized=True)
    _fire(conn, "ZC2", "bearish", f"{DAY_A}T08:00:00+00:00", 100.0,
          macd=3.2, hist=0.2, px_7d=88.0, finalized=True)
    conn.close()

    app.dependency_overrides[get_conn] = _conn_to(path)
    rows = TestClient(app).get("/api/perf/macd-signal-pct-buckets").json()
    app.dependency_overrides.clear()
    assert sum(r["n"] for r in rows if r["horizon"] == "7d") == 1


def test_macd_signal_pct_buckets_respects_class_filter(macd_pct_client):
    rows = macd_pct_client.get("/api/perf/macd-signal-pct-buckets?classes=equity").json()
    assert rows == []
    rows = macd_pct_client.get("/api/perf/macd-signal-pct-buckets?classes=crypto").json()
    assert sum(r["n"] for r in rows if r["horizon"] == "7d") == 5


# ---- peak-vs-own-history bucket analysis ----


def _seed_peak(path: str) -> None:
    conn = db.connect(path)
    db.init_schema(conn)
    db.start_run(conn, "r1", f"{DAY_A}T00:00:00+00:00", "abc", "h", "{}")
    db.insert_snapshots(conn, "r1", {}, [_metrics(f"PK{i}", 0.001) for i in range(1, 6)])
    at = f"{DAY_A}T08:00:00+00:00"

    # Bearish: a low percentile (modest peak for this token) wins, a high one loses —
    # the direction the measurement actually found.
    _fire(conn, "PK1", "bearish", at, 100.0, px_7d=88.0, finalized=True, peak_pct=10.0, top_n=8)
    _fire(conn, "PK2", "bearish", at, 100.0, px_7d=94.0, finalized=True, peak_pct=35.0, top_n=6)
    _fire(conn, "PK3", "bearish", at, 100.0, px_7d=106.0, finalized=True, peak_pct=90.0, top_n=7)
    # Bullish, mid band.
    _fire(conn, "PK4", "bullish", at, 100.0, px_7d=110.0, finalized=True, peak_pct=50.0, top_n=5)
    # top_n below the trust floor → excluded even though peak_pct is present.
    _fire(conn, "PK5", "bullish", at, 100.0, px_7d=130.0, finalized=True, peak_pct=15.0, top_n=1)
    # No peak context at all (never backfilled) → excluded.
    _fire(conn, "PK6", "bearish", f"{DAY_B}T08:00:00+00:00", 100.0, px_7d=70.0, finalized=True)
    conn.close()


@pytest.fixture
def peak_client(tmp_path):
    path = str(tmp_path / "peak.sqlite3")
    _seed_peak(path)
    app.dependency_overrides[get_conn] = _conn_to(path)
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_peak_context_buckets_win_and_ev(peak_client):
    rows = peak_client.get("/api/perf/peak-context-buckets").json()
    by = {(r["direction"], r["bucket"], r["horizon"]): r for r in rows}

    r = by[("bearish", "a <20", "7d")]
    assert r["n"] == 1 and r["win_pct"] == 100.0 and r["avg_ret_pct"] == 12.0

    r = by[("bearish", "b 20-40", "7d")]
    assert r["n"] == 1 and r["win_pct"] == 100.0 and r["avg_ret_pct"] == 6.0

    r = by[("bearish", "e 80-100", "7d")]
    assert r["n"] == 1 and r["win_pct"] == 0.0 and r["avg_ret_pct"] == -6.0

    r = by[("bullish", "c 40-60", "7d")]
    assert r["n"] == 1 and r["win_pct"] == 100.0 and r["avg_ret_pct"] == 10.0

    assert {r["horizon"] for r in rows} == {"1d", "3d", "7d", "14d"}


def test_peak_context_buckets_excludes_thin_baselines_and_nulls(peak_client):
    """PK5 has top_n=1 (below the trust floor) and PK6 has no peak context at all;
    neither may contribute, so only the four usable signals are counted."""
    rows = peak_client.get("/api/perf/peak-context-buckets").json()
    assert sum(r["n"] for r in rows if r["horizon"] == "7d") == 4


def test_recent_signals_exposes_peak_context(peak_client):
    """The feed carries the three fields so a live signal shows its peak context."""
    rows = peak_client.get("/api/signals/recent").json()
    by = {r["symbol"]: r for r in rows}
    assert by["PK1"]["fire_hist_peak_pct"] == 10.0
    assert by["PK1"]["fire_hist_top_n"] == 8
    assert by["PK6"]["fire_hist_peak_pct"] is None


# ---- MACD signal-line bucket analysis ----
#
# The axis is (fire_macd - fire_hist) / atr. Every symbol below uses atr=2.0, so a
# raw signal of -3.0 lands at -1.5 on the normalized axis.
#
# Buckets are equal-n octiles, not fixed bands, so there are no edges to sit away
# from — what matters is the ORDER of the values and the range each bucket reports.
# With fewer rows than octiles SQLite's NTILE gives the first k groups one row each,
# so these six signals produce one bucket per signal and every label reads
# `x.xx..x.xx` with its own value on both sides. That makes the labels exact enough
# to assert on, which is why the derivation test below can check a value rather than
# just a bucket name.


def _seed_macd_signal(path: str) -> None:
    conn = db.connect(path)
    db.init_schema(conn)
    db.start_run(conn, "r1", f"{DAY_A}T00:00:00+00:00", "abc", "h", "{}")
    db.insert_snapshots(conn, "r1", {}, [
        *[_metrics(f"MS{i}", 0.001) for i in range(1, 9)],
        _metrics("MS7", 0.001, atr=None),   # no ATR -> not normalizable
    ])
    at = f"{DAY_A}T08:00:00+00:00"

    # Bullish (hist < 0), spanning the negative half of the axis.
    _fire(conn, "MS1", "bullish", at, 100.0, macd=-3.2, hist=-0.2, px_7d=110.0, finalized=True)  # -1.5  win +10%
    _fire(conn, "MS2", "bullish", at, 100.0, macd=-1.7, hist=-0.2, px_7d=95.0, finalized=True)   # -0.75 loss -5%
    _fire(conn, "MS3", "bullish", at, 100.0, macd=-0.7, hist=-0.2, px_7d=108.0, finalized=True)  # -0.25 win +8%
    # Bearish (hist > 0), spanning the positive half. MS4's hist is large enough that
    # the MACD line alone (1.5/2 = 0.75) would report a different range — it pins the
    # label to the signal line, not the MACD line.
    _fire(conn, "MS4", "bearish", at, 100.0, macd=1.5, hist=1.0, px_7d=88.0, finalized=True)     # +0.25 win +12%
    _fire(conn, "MS5", "bearish", at, 100.0, macd=1.7, hist=0.2, px_7d=106.0, finalized=True)    # +0.75 loss -6%
    _fire(conn, "MS6", "bearish", at, 100.0, macd=3.2, hist=0.2, px_7d=90.0, finalized=True)     # +1.5  win +10%
    # NULL atr -> excluded entirely.
    _fire(conn, "MS7", "bullish", at, 100.0, macd=-0.7, hist=-0.2, px_7d=120.0, finalized=True)

    # Scored at 7d but NOT at 14d, and positioned between MS1 and MS2. It exists to
    # prove the octile edges are cut once over the whole population rather than
    # per-horizon: it must shift MS2/MS3 down a bucket in EVERY horizon, including
    # the one it is itself missing from.
    _fire(conn, "MS8", "bullish", at, 100.0, macd=-2.2, hist=-0.2, px_7d=103.0)                  # -1.0  win +3%
    conn.execute("UPDATE signals SET px_14d=NULL WHERE symbol='MS8'")
    conn.commit()
    conn.close()


@pytest.fixture
def macd_signal_client(tmp_path):
    path = str(tmp_path / "macdsig.sqlite3")
    _seed_macd_signal(path)
    app.dependency_overrides[get_conn] = _conn_to(path)
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_macd_signal_buckets_win_and_ev(macd_signal_client):
    rows = macd_signal_client.get("/api/perf/macd-signal-buckets").json()
    # px_1d=px_3d=px_7d in _fire, so those three horizons are identical.
    by = {(r["direction"], r["bucket"], r["horizon"]): r for r in rows}

    r = by[("bullish", "a -1.50..-1.50", "7d")]
    assert r["n"] == 1 and r["win_pct"] == 100.0 and r["avg_ret_pct"] == 10.0

    r = by[("bullish", "c -0.75..-0.75", "7d")]
    assert r["n"] == 1 and r["win_pct"] == 0.0 and r["avg_ret_pct"] == -5.0

    r = by[("bullish", "d -0.25..-0.25", "7d")]
    assert r["n"] == 1 and r["win_pct"] == 100.0 and r["avg_ret_pct"] == 8.0

    r = by[("bearish", "b +0.75..+0.75", "7d")]
    assert r["n"] == 1 and r["win_pct"] == 0.0 and r["avg_ret_pct"] == -6.0

    r = by[("bearish", "c +1.50..+1.50", "7d")]
    assert r["n"] == 1 and r["win_pct"] == 100.0 and r["avg_ret_pct"] == 10.0

    assert {r["horizon"] for r in rows} == {"1d", "3d", "7d", "14d"}


def test_macd_signal_buckets_label_their_own_range(macd_signal_client):
    """The bucket string is a sort prefix plus the range the bucket actually spans.

    The frontend has no hardcoded bucket list any more — it reads these labels off
    the rows — so the format ('a ' .. 'h ' then a signed 2dp range) is a contract,
    not cosmetics. Ordering must follow the prefix, ascending by signal value.
    """
    rows = macd_signal_client.get("/api/perf/macd-signal-buckets").json()
    bullish = sorted({r["bucket"] for r in rows if r["direction"] == "bullish"})

    assert bullish == [
        "a -1.50..-1.50", "b -1.00..-1.00", "c -0.75..-0.75", "d -0.25..-0.25",
    ]
    # Prefixes are consecutive from 'a', and every label carries an explicit sign on
    # both edges so a positive band can't be misread as a negative one.
    assert [b[0] for b in bullish] == ["a", "b", "c", "d"]
    assert all(b[2] in "+-" for b in bullish)


def test_macd_signal_buckets_uses_signal_line_not_macd_line(macd_signal_client):
    """MS4: signal = (1.5 - 1.0)/2 = +0.25. The MACD line alone would be 1.5/2 =
    +0.75. Because each bucket reports its own measured range, the label names the
    value outright — a stronger guard on the `macd - hist` derivation than a bucket
    name, which both values could have shared."""
    rows = macd_signal_client.get("/api/perf/macd-signal-buckets").json()
    by = {(r["direction"], r["bucket"], r["horizon"]): r for r in rows}

    r = by[("bearish", "a +0.25..+0.25", "7d")]
    assert r["n"] == 1 and r["win_pct"] == 100.0 and r["avg_ret_pct"] == 12.0
    # Nothing landed on the MACD-line value, which would be the bug's signature.
    assert not any(r["bucket"].endswith("+0.75..+0.75")
                   and r["direction"] == "bearish" and r["bucket"][0] == "a"
                   for r in rows)


def test_macd_signal_bucket_edges_are_cut_once_not_per_horizon(macd_signal_client):
    """A heatmap row must mean the same range in all four of its cells.

    MS8 is scored at 7d but not at 14d. Ranking within each horizon would re-cut the
    14d octiles over the three remaining bullish signals and relabel them; cutting
    once over the whole population leaves the labels fixed and simply drops MS8's
    cell. The second is what the heatmap needs.
    """
    rows = macd_signal_client.get("/api/perf/macd-signal-buckets").json()
    at = {h: {r["bucket"] for r in rows if r["direction"] == "bullish" and r["horizon"] == h}
          for h in ("7d", "14d")}

    assert "b -1.00..-1.00" in at["7d"]          # MS8 is scored here
    assert "b -1.00..-1.00" not in at["14d"]     # ...and not here
    # Every other label is untouched: MS2 stays 'c', MS3 stays 'd'. Per-horizon
    # ranking would have promoted them to 'b' and 'c'.
    assert at["14d"] == at["7d"] - {"b -1.00..-1.00"}


def test_macd_signal_buckets_excludes_signals_without_atr(macd_signal_client):
    rows = macd_signal_client.get("/api/perf/macd-signal-buckets").json()
    # MS7's snapshot has NULL atr -> normalization undefined -> contributes nowhere.
    # 7 of the 8 seeded signals remain; MS8 drops out again at 14d.
    assert sum(r["n"] for r in rows if r["horizon"] == "7d") == 7
    assert sum(r["n"] for r in rows if r["horizon"] == "14d") == 6


def test_macd_signal_buckets_respects_class_filter(macd_signal_client):
    """All seeded symbols classify as crypto, so 'equity' must return nothing while
    'crypto' returns the full set — the same classes threading as the other endpoints.

    The filter also re-cuts the octiles, since the quantiles are of the selected
    cohort; here the cohort is unchanged, so the labels must be too.
    """
    rows = macd_signal_client.get("/api/perf/macd-signal-buckets?classes=equity").json()
    assert rows == []

    rows = macd_signal_client.get("/api/perf/macd-signal-buckets?classes=crypto").json()
    assert sum(r["n"] for r in rows if r["horizon"] == "7d") == 7
    unfiltered = macd_signal_client.get("/api/perf/macd-signal-buckets").json()
    assert {r["bucket"] for r in rows} == {r["bucket"] for r in unfiltered}


# ---------- per-asset signal dataset (Scorecard drill-down) ----------
#
# The seed already contains everything this view has to get right: BTC fires twice
# on DAY_A (the dedup case), SOL is unscored (the pending case), xyz:TSLA carries a
# colon (the HIP-3 path-param case), and OLD is pre-fix (the exclusion case).


def test_asset_signals_measured_matches_scorecard_n(client):
    """The anti-confusion guarantee: the drill-down must count exactly what the
    Scorecard row above it claims, or the view creates doubt instead of removing it."""
    scorecard = {r["symbol"]: r["n"] for r in
                 client.get("/api/perf/scorecard?min_n=1&horizon=7d").json()}
    for symbol, n in scorecard.items():
        body = client.get(f"/api/assets/{symbol}/signals?horizon=7d").json()
        assert body["measured"] == n, f"{symbol}: {body['measured']} != scorecard {n}"


def test_asset_signals_dedups_and_reports_the_same_day_repeat(client):
    """BTC fired at 08:00 (win) and 12:00 (loss) on one day. Only the earlier
    survives, and the dropped one is reported rather than silently vanishing."""
    body = client.get("/api/assets/BTC/signals").json()
    assert len(body["rows"]) == 1
    assert body["same_day_excluded"] == 1
    row = body["rows"][0]
    assert row["fired_at"].startswith(f"{DAY_A}T08:00")   # the earlier fire
    assert row["ret_7d"] == pytest.approx(0.10)           # 110/100 - 1, the winner


def test_asset_signals_returns_pending_rows_flagged(client):
    """SOL has no outcome yet. It must still appear — an unscored signal that were
    omitted would look like it never fired, and one shown as 0.0 would read as a
    flat result rather than an unanswered question."""
    body = client.get("/api/assets/SOL/signals").json()
    assert len(body["rows"]) == 1
    assert body["measured"] == 0 and body["pending"] == 1
    row = body["rows"][0]
    assert row["finalized"] is False
    assert row["ret_7d"] is None


def test_asset_signals_carries_all_four_horizons(client):
    """The horizon profile is the point of the row; a single-horizon view hides it.
    The seed sets px_1d..px_14d identically, so all four returns match."""
    row = client.get("/api/assets/BTC/signals").json()["rows"][0]
    for h in ("ret_1d", "ret_3d", "ret_7d", "ret_14d"):
        assert row[h] == pytest.approx(0.10), h


def test_asset_signals_handles_colon_symbols(client):
    """HIP-3 symbols contain a colon. It is legal in a path segment, and the route
    must accept it both raw and percent-encoded."""
    for path in ("/api/assets/xyz:TSLA/signals", "/api/assets/xyz%3ATSLA/signals"):
        body = client.get(path).json()
        assert body["symbol"] == "xyz:TSLA"
        assert len(body["rows"]) == 1
        assert body["rows"][0]["direction"] == "bearish"
        assert body["rows"][0]["ret_7d"] == pytest.approx(0.05)  # 1 - 380/400


def test_asset_signals_excludes_pre_fix(client):
    """OLD fired before DETECTOR_FIX_CUTOFF. _base() drops it, so the drill-down
    shows nothing — and the excluded count must not go negative from the raw
    count picking it up."""
    body = client.get("/api/assets/OLD/signals").json()
    assert body["rows"] == []
    assert body["measured"] == 0
    assert body["same_day_excluded"] == 0


def test_asset_signals_unknown_symbol_is_empty_not_an_error(client):
    """The Scorecard only links symbols that exist, so a miss means a stale page.
    An empty table reads better there than a 404."""
    r = client.get("/api/assets/NOT_A_SYMBOL/signals")
    assert r.status_code == 200
    body = r.json()
    assert body["rows"] == [] and body["measured"] == 0 and body["pending"] == 0


def test_asset_signals_confident_flag_agrees_with_the_python_rule(macd_signal_client):
    """`confident` is computed by _CONFIDENCE_SQL; is_high_confidence is the Python
    original. They must agree row-for-row or the Telegram bolding and this table
    disagree about the same signal."""
    rows = macd_signal_client.get("/api/perf/scorecard?min_n=1").json()
    for sc in rows:
        body = macd_signal_client.get(f"/api/assets/{sc['symbol']}/signals").json()
        for row in body["rows"]:
            # atr=1 with macd=sig_atr and hist=0 reproduces the rule's axis
            # exactly: (macd - hist) / atr == sig_atr.
            sig_atr = row["sig_atr"]
            expected = is_high_confidence(Signal(
                sc["symbol"], "histogram_flattening", row["direction"],
                close=row["fire_close"],
                macd=sig_atr if sig_atr is not None else 0.0, hist=0.0,
                atr=1.0 if sig_atr is not None else None,
                reduction_from_peak=row["fire_reduction_from_peak"],
            ))
            assert row["confident"] is expected, f"{sc['symbol']} {row['fired_at']}"
