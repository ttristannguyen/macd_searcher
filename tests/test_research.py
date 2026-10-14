"""Tests for the research pipeline. Each pins a mistake that was actually made once:
a median benchmark, a survivor-only benchmark, repeat fires counted as independent,
features read from the fire day itself, and a report that drifts from the live rule."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from macd_searcher.research import dataset
from macd_searcher.research.inference import bh_qvalues, block_ci, per_episode
from macd_searcher.research.rules import RULES
from macd_searcher.signals import CONFIDENCE_MAX_REDUCTION, CONFIDENCE_MAX_SIG_ATR, Signal, is_high_confidence

DAY = "2026-07-01"


def _snaps(symbols, live=100.0, run="r1", day=DAY, cls="crypto", close=100.0):
    t = pd.Timestamp(f"{day}T00:00:00", tz="UTC")
    return pd.DataFrame({
        "run_id": run, "symbol": symbols, "asset_class": cls, "close": close,
        "live_close": live, "mark_px": live, "open_interest_usd": 1e6,
        "day_ntl_vlm_usd": 1e7, "started_at": t.isoformat(), "t": t, "day": day})


def _candle(symbol_closes: dict[str, float], day: str) -> dict[str, pd.DataFrame]:
    ts = pd.Timestamp(day, tz="UTC")
    return {s: pd.DataFrame({"ts": [ts], "open": [c], "high": [c], "low": [c], "close": [c], "volume": [1.0]})
            for s, c in symbol_closes.items()}


def _shift(day: str, n: int) -> str:
    return (pd.Timestamp(day) + pd.Timedelta(days=n)).strftime("%Y-%m-%d")


# ---------------------------------------------------------------- benchmark

def test_benchmark_is_the_mean_not_the_median():
    """One symbol doubles, eleven are flat. The median would say 0%; the mean says
    1/12. Only the mean makes a random pick score zero."""
    syms = [f"S{i}" for i in range(12)]
    closes = {s: 100.0 for s in syms} | {"S0": 200.0}
    bench = dataset.benchmark(_snaps(syms), _candle(closes, _shift(DAY, 7)), horizons=(7,))
    assert bench.loc[0, "bench_7d"] == pytest.approx(1 / 12)


def test_a_random_pick_scores_zero_alpha():
    syms = [f"S{i}" for i in range(12)]
    rng = np.random.default_rng(1)
    exits = dict(zip(syms, 100 * np.exp(rng.normal(0, 0.2, 12))))
    bench = dataset.benchmark(_snaps(syms), _candle(exits, _shift(DAY, 7)), horizons=(7,))
    alphas = [exits[s] / 100 - 1 - bench.loc[0, "bench_7d"] for s in syms]
    assert np.mean(alphas) == pytest.approx(0, abs=1e-12)


def test_snapshot_close_seen_on_day_d_is_the_close_of_d_minus_1():
    snaps = _snaps(["S0"], day=_shift(DAY, 8), close=123.0)
    closes = dataset.daily_closes(snaps)
    assert closes[("S0", _shift(DAY, 7))] == 123.0


def test_benchmark_keeps_assets_that_left_the_universe_when_candles_are_given():
    """S0 crashed and fell out of the liquidity filter, so no snapshot exists for it
    8 days later. Snapshot-only exits silently drop it (survivorship); candles keep it."""
    syms = [f"S{i}" for i in range(12)]
    entry = _snaps(syms)
    later = _snaps(syms[1:], run="r2", day=_shift(DAY, 8), close=100.0)   # S0 missing
    snaps = pd.concat([entry, later], ignore_index=True)

    survivors = dataset.benchmark(snaps, horizons=(7,))
    everyone = dataset.benchmark(snaps, _candle({"S0": 50.0}, _shift(DAY, 7)), horizons=(7,))
    r1 = lambda b: b.loc[b.run_id == "r1", "bench_7d"].item()  # noqa: E731
    assert r1(survivors) == pytest.approx(0.0)        # S0's −50% is invisible
    assert r1(everyone) == pytest.approx(-0.5 / 12)   # and counted once candles are used


def test_benchmark_needs_enough_symbols():
    syms = [f"S{i}" for i in range(dataset.MIN_BENCH_SYMBOLS - 1)]
    bench = dataset.benchmark(_snaps(syms), _candle({s: 110.0 for s in syms}, _shift(DAY, 7)), horizons=(7,))
    assert np.isnan(bench.loc[0, "bench_7d"])


def test_return_is_market_plus_alpha_for_both_directions():
    sig = pd.DataFrame({
        "run_id": "r1", "asset_class": "crypto", "direction": ["bullish", "bearish"],
        "fire_close": 100.0, "px_7d": [110.0, 110.0], "ret_7d": [0.10, -0.10]})
    bench = pd.DataFrame({"run_id": ["r1"], "asset_class": ["crypto"], "bench_7d": [0.04]})
    out = dataset.attach_outcomes(sig, bench, horizons=(7,))
    assert out["alpha_7d"].tolist() == pytest.approx([6.0, -6.0])
    assert (out["market_7d"] + out["alpha_7d"]).tolist() == pytest.approx(out["r_7d"].tolist())


# ---------------------------------------------------------------- episodes

def _fires(rows):
    df = pd.DataFrame(rows, columns=["symbol", "direction", "day"])
    df["fired_at"] = pd.to_datetime(df["day"], utc=True)
    return df


def test_consecutive_day_fires_are_one_episode():
    df = dataset.assign_episodes(_fires([
        ("A", "bullish", "2026-07-01"), ("A", "bullish", "2026-07-02"),
        ("A", "bullish", "2026-07-04"), ("A", "bearish", "2026-07-02")]), gap_days=1)
    assert df["episode_start"].tolist() == [True, False, True, True]
    assert df["episode"].nunique() == 3


def test_a_wider_gap_merges_episodes():
    df = dataset.assign_episodes(_fires([
        ("A", "bullish", "2026-07-01"), ("A", "bullish", "2026-07-04")]), gap_days=3)
    assert df["episode"].nunique() == 1


def test_per_episode_collapses_to_one_number_and_keeps_the_first_fire():
    df = pd.DataFrame({"episode": ["e1", "e1", "e2"], "a": [1.0, 3.0, 5.0], "week": ["w1", "w2", "w2"],
                       "month": "m", "oos": [False, True, True],
                       "fired_at": pd.to_datetime(["2026-07-01", "2026-07-02", "2026-07-02"], utc=True)})
    e = per_episode(df, "a")
    assert e.loc["e1", "a"] == 2.0 and e.loc["e1", "week"] == "w1" and not e.loc["e1", "oos"]


# ---------------------------------------------------------------- no look-ahead

def _series(n=120):
    ts = pd.date_range("2026-03-01", periods=n, freq="1D", tz="UTC")
    c = pd.Series(100 + np.sin(np.arange(n) / 5) * 10)
    return pd.DataFrame({"ts": ts, "open": c, "high": c + 1, "low": c - 1, "close": c, "volume": 1.0})


def test_features_come_from_the_bar_before_the_fire_day():
    candles = _series()
    fire_day = candles["ts"].iloc[100].strftime("%Y-%m-%d")
    sig = pd.DataFrame({"symbol": ["S"], "day": [fire_day]})
    before = dataset.attach_indicators(sig, {"S": candles})

    spiked = candles.copy()
    spiked.loc[100, ["close", "high"]] = 1_000.0          # the fire day itself: unknowable at fire
    after = dataset.attach_indicators(sig, {"S": spiked})
    pd.testing.assert_frame_equal(before, after)

    expected = dataset.indicators(candles).loc[candles["ts"].iloc[99].strftime("%Y-%m-%d"), "roc_7"]
    assert before.loc[0, "roc_7"] == pytest.approx(expected)


# ---------------------------------------------------------------- statistics

def test_block_ci_collapses_on_constant_data():
    m, lo, hi = block_ci([2.0] * 30, [i % 6 for i in range(30)])
    assert (m, lo, hi) == pytest.approx((2.0, 2.0, 2.0))


def test_block_ci_refuses_an_interval_with_too_few_blocks():
    m, lo, hi = block_ci([1.0, 2.0, 3.0, 4.0], ["a", "a", "b", "b"])
    assert m == 2.5 and np.isnan(lo) and np.isnan(hi)


def test_bh_qvalues():
    q = bh_qvalues([0.01, 0.04, 0.03, 0.5])
    assert q.tolist() == pytest.approx([0.04, 0.04 * 4 / 3, 0.04 * 4 / 3, 0.5])


# ---------------------------------------------------------------- rules

@pytest.mark.parametrize("direction,sig_atr,red", [
    ("bullish", CONFIDENCE_MAX_SIG_ATR - 0.01, CONFIDENCE_MAX_REDUCTION - 0.01),   # inside
    ("bullish", CONFIDENCE_MAX_SIG_ATR + 0.01, CONFIDENCE_MAX_REDUCTION - 0.01),   # sig/ATR too high
    ("bullish", CONFIDENCE_MAX_SIG_ATR - 0.01, CONFIDENCE_MAX_REDUCTION),          # reduction at the cap
    ("bearish", CONFIDENCE_MAX_SIG_ATR - 0.01, CONFIDENCE_MAX_REDUCTION - 0.01),   # wrong direction
])
def test_report_v2_rule_matches_the_live_marker(direction, sig_atr, red):
    atr, hist = 2.0, -0.1
    macd = sig_atr * atr + hist                 # signal line = macd − hist
    s = Signal("X", "histogram_flattening", direction, close=100.0, macd=macd, hist=hist,
               reduction_from_peak=red, atr=atr)
    frame = pd.DataFrame({"direction": [direction], "atr": [atr], "sig_atr": [(macd - hist) / atr],
                          "red": [red]})
    assert bool(RULES["v2 (live)"](frame).iloc[0]) == is_high_confidence(s)
