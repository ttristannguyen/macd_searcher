"""Tests for the signal outcome-scoring logic.

`score_signal` takes the MACD series as an argument, so the zero-cross logic
can be tested with an injected, fully-controlled series.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd

from macd_searcher.update_outcomes import Outcome, score_signal


START = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _df(n: int, *, close, high=None, low=None) -> pd.DataFrame:
    """n daily bars starting at START. `close` may be a scalar or list."""
    closes = close if isinstance(close, list) else [float(close)] * n
    highs = high if isinstance(high, list) else closes
    lows = low if isinstance(low, list) else closes
    return pd.DataFrame({
        "ts": pd.date_range(START, periods=n, freq="1D", tz="UTC"),
        "open": closes,
        "high": highs,
        "low": lows,
        "close": closes,
        "volume": [1.0] * n,
    })


def _flat_macd(n: int, value: float = -1.0) -> pd.Series:
    return pd.Series([value] * n, dtype=float)


# A "now" far enough past START that a fire near START is fully finalizable.
NOW = START + timedelta(days=60)


# ---------- forward prices ----------


def test_forward_prices_picked_at_correct_offsets():
    closes = [100.0 + i for i in range(40)]  # bar k has close 100+k
    df = _df(40, close=closes)
    # fire on bar index 5 (date START+5, close 105)
    fired_at = START + timedelta(days=5)
    out = score_signal(df, _flat_macd(40), fired_at, fire_close=105.0,
                        direction="bullish", horizon_days=14, now_dt=NOW)
    assert out.px_1d == 106.0   # +1 day
    assert out.px_3d == 108.0   # +3
    assert out.px_7d == 112.0   # +7
    assert out.px_14d == 119.0  # +14


def test_forward_prices_null_when_bar_not_yet_available():
    closes = [100.0 + i for i in range(10)]  # only 10 bars
    df = _df(10, close=closes)
    fired_at = START + timedelta(days=5)
    # now is only 8 days after fire → 14d bar can't exist yet
    now = fired_at + timedelta(days=8)
    out = score_signal(df, _flat_macd(10), fired_at, fire_close=105.0,
                        direction="bullish", horizon_days=14, now_dt=now)
    assert out.px_1d == 106.0
    assert out.px_3d == 108.0
    assert out.px_7d is None     # bar at +7 (index 12) doesn't exist
    assert out.px_14d is None
    assert out.finalize is False  # 8 < 14 days


# ---------- MFE / MAE ----------


def test_mfe_mae_bullish_direction_normalized():
    n = 30
    closes = [100.0] * n
    highs = [100.0] * n
    lows = [100.0] * n
    # fire at idx 0; within the next 14 bars put a high of 120 and a low of 95
    highs[5] = 120.0
    lows[8] = 95.0
    df = _df(n, close=closes, high=highs, low=lows)
    out = score_signal(df, _flat_macd(n), START, fire_close=100.0,
                       direction="bullish", horizon_days=14, now_dt=NOW)
    assert out.max_favorable_move_pct == (120.0 - 100.0) / 100.0   # +20%
    assert out.max_adverse_move_pct == (95.0 - 100.0) / 100.0      # -5%


def test_mfe_mae_bearish_is_flipped():
    n = 30
    closes = [100.0] * n
    highs = [100.0] * n
    lows = [100.0] * n
    highs[5] = 120.0   # adverse for a short
    lows[8] = 95.0     # favorable for a short
    df = _df(n, close=closes, high=highs, low=lows)
    out = score_signal(df, _flat_macd(n), START, fire_close=100.0,
                       direction="bearish", horizon_days=14, now_dt=NOW)
    assert out.max_favorable_move_pct == (100.0 - 95.0) / 100.0    # +5% (price fell)
    assert out.max_adverse_move_pct == (100.0 - 120.0) / 100.0     # -20% (price rose)


# ---------- zero-line cross ----------


def test_bars_to_zero_cross_bullish():
    n = 20
    macd = [-3.0, -2.0, -1.0, -0.5, -0.2, 0.1, 0.5] + [1.0] * (n - 7)
    df = _df(n, close=100.0)
    # fire at idx 0 (macd -3); first non-negative macd is at idx 5
    out = score_signal(df, pd.Series(macd), START, fire_close=100.0,
                       direction="bullish", horizon_days=14, now_dt=NOW)
    assert out.bars_to_zero_cross == 5
    assert out.zero_cross_observed_at == df["ts"].iloc[5].isoformat()


def test_bars_to_zero_cross_bearish():
    n = 20
    macd = [3.0, 2.0, 1.0, 0.5, -0.1] + [-1.0] * (n - 5)
    df = _df(n, close=100.0)
    out = score_signal(df, pd.Series(macd), START, fire_close=100.0,
                       direction="bearish", horizon_days=14, now_dt=NOW)
    assert out.bars_to_zero_cross == 4


def test_no_cross_within_horizon_is_none():
    n = 20
    macd = [-1.0] * n  # never reaches zero for a bullish signal
    df = _df(n, close=100.0)
    out = score_signal(df, pd.Series(macd), START, fire_close=100.0,
                       direction="bullish", horizon_days=14, now_dt=NOW)
    assert out.bars_to_zero_cross is None
    assert out.zero_cross_observed_at is None
    assert out.finalize is True  # finalized with NULL == "never crossed in window"


def test_cross_already_at_fire_bar_is_zero():
    n = 20
    macd = [0.2] + [1.0] * (n - 1)  # already >= 0 at fire for a bullish signal
    df = _df(n, close=100.0)
    out = score_signal(df, pd.Series(macd), START, fire_close=100.0,
                       direction="bullish", horizon_days=14, now_dt=NOW)
    assert out.bars_to_zero_cross == 0


# ---------- finalization & guards ----------


def test_finalize_flag_tracks_horizon():
    df = _df(30, close=100.0)
    young = score_signal(df, _flat_macd(30), NOW - timedelta(days=5), 100.0,
                         "bullish", 14, NOW)
    assert young.finalize is False
    old = score_signal(df, _flat_macd(30), NOW - timedelta(days=20), 100.0,
                       "bullish", 14, NOW)
    assert old.finalize is True


def test_unscorable_when_fire_bar_missing():
    # All bars are AFTER the fire date → no bar at-or-before it.
    df = _df(10, close=100.0)  # starts at START
    fired_before_data = START - timedelta(days=30)
    out = score_signal(df, _flat_macd(10), fired_before_data, 100.0,
                       "bullish", 14, NOW)
    assert out.px_1d is None
    assert out.bars_to_zero_cross is None
    assert out.finalize is True  # old enough → caller will stop revisiting


def test_unscorable_when_fire_close_missing():
    df = _df(20, close=100.0)
    out = score_signal(df, _flat_macd(20), START, fire_close=None,
                       direction="bullish", horizon_days=14, now_dt=NOW)
    assert out == Outcome(finalize=True)
