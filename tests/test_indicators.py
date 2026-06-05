"""Tests for MACD and ATR.

Reference values are computed in pure Python below and cross-checked against
the pandas-based implementations in `indicators.py`. This guards against
accidental drift in either the pandas API or our function.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from macd_searcher.indicators import atr, macd


def _ema_adjust_false(values: list[float], span: int) -> list[float]:
    """Reference EMA with adjust=False, seeded at values[0]."""
    alpha = 2.0 / (span + 1)
    out = [values[0]]
    for v in values[1:]:
        out.append(alpha * v + (1 - alpha) * out[-1])
    return out


def _wilders_ewm(values: list[float], period: int) -> list[float]:
    """Reference Wilder smoothing matching pandas .ewm(alpha=1/period, adjust=False)."""
    alpha = 1.0 / period
    out = [values[0]]
    for v in values[1:]:
        out.append(alpha * v + (1 - alpha) * out[-1])
    return out


# ---------- MACD ----------


def test_macd_shape_and_columns():
    close = pd.Series(np.linspace(100, 200, 60))
    df = macd(close)
    assert list(df.columns) == ["macd", "signal", "hist"]
    assert len(df) == len(close)
    # invariant: hist == macd - signal
    np.testing.assert_allclose(df["hist"].values, (df["macd"] - df["signal"]).values, atol=1e-12)


def test_macd_constant_series_is_zero():
    """Constant prices ⇒ EMAs match price ⇒ MACD, signal, hist all 0."""
    close = pd.Series([100.0] * 50)
    df = macd(close)
    np.testing.assert_allclose(df["macd"].values, 0.0, atol=1e-12)
    np.testing.assert_allclose(df["signal"].values, 0.0, atol=1e-12)
    np.testing.assert_allclose(df["hist"].values, 0.0, atol=1e-12)


def test_macd_matches_reference():
    """Hand-rolled EMA must match pandas EWM with adjust=False."""
    prices = [100.0, 101.5, 103.0, 102.0, 105.5, 107.0, 106.0, 108.5, 110.0, 109.0,
              111.5, 113.0, 112.0, 114.5, 116.0, 115.0, 117.5, 119.0, 118.0, 120.5,
              122.0, 121.0, 123.5, 125.0, 124.0, 126.5, 128.0, 127.0, 129.5, 131.0,
              130.0, 132.5, 134.0, 133.0, 135.5]
    close = pd.Series(prices)
    df = macd(close, fast=12, slow=26, signal=9)

    ema12 = _ema_adjust_false(prices, 12)
    ema26 = _ema_adjust_false(prices, 26)
    expected_macd = [a - b for a, b in zip(ema12, ema26)]
    expected_signal = _ema_adjust_false(expected_macd, 9)
    expected_hist = [m - s for m, s in zip(expected_macd, expected_signal)]

    np.testing.assert_allclose(df["macd"].values, expected_macd, atol=1e-10)
    np.testing.assert_allclose(df["signal"].values, expected_signal, atol=1e-10)
    np.testing.assert_allclose(df["hist"].values, expected_hist, atol=1e-10)


def test_macd_uptrend_positive_after_warmup():
    """Strict uptrend ⇒ fast EMA leads slow EMA ⇒ MACD eventually > 0."""
    close = pd.Series(np.linspace(100, 300, 100))
    df = macd(close)
    # After warmup (~slow period), MACD should be solidly positive.
    assert df["macd"].iloc[-1] > 0
    assert df["macd"].iloc[50:].min() > 0


def test_macd_rejects_bad_params():
    close = pd.Series([100.0] * 50)
    with pytest.raises(ValueError):
        macd(close, fast=26, slow=12)  # slow not > fast
    with pytest.raises(ValueError):
        macd(close, signal=0)


# ---------- ATR ----------


def test_atr_constant_prices_is_zero():
    n = 50
    high = pd.Series([100.0] * n)
    low = pd.Series([100.0] * n)
    close = pd.Series([100.0] * n)
    out = atr(high, low, close, period=14)
    # TR[0] uses skipna max, so it falls back to H-L = 0. ATR is 0 throughout.
    np.testing.assert_allclose(out.values, 0.0, atol=1e-12)


def test_atr_matches_reference():
    """Cross-check pandas EWM against hand-rolled Wilder smoothing."""
    high = [10.0, 11.0, 12.0, 11.5, 13.0, 14.5, 13.5, 15.0, 16.0, 15.5,
            17.0, 18.0, 17.5, 19.0, 20.0, 19.5, 21.0, 22.0]
    low = [9.0, 10.0, 11.0, 10.5, 12.0, 13.0, 12.5, 14.0, 15.0, 14.5,
           16.0, 17.0, 16.5, 18.0, 19.0, 18.5, 20.0, 21.0]
    close = [9.5, 10.5, 11.5, 11.0, 12.5, 14.0, 13.0, 14.5, 15.5, 15.0,
             16.5, 17.5, 17.0, 18.5, 19.5, 19.0, 20.5, 21.5]

    # True range, hand-computed
    tr = [high[0] - low[0]]  # first bar: no prev_close → TR = H-L (matches our impl: NaN-shifted to H-L)
    for i in range(1, len(close)):
        tr.append(max(
            high[i] - low[i],
            abs(high[i] - close[i - 1]),
            abs(low[i] - close[i - 1]),
        ))

    expected_atr = _wilders_ewm(tr, period=14)

    out = atr(pd.Series(high), pd.Series(low), pd.Series(close), period=14)

    # Our TR[0] is NaN because (high - prev_close).abs() has prev_close = NaN, and max
    # of (H-L, NaN, NaN) is NaN. So the EWM at index 0 is NaN. Compare from index 1.
    np.testing.assert_allclose(out.iloc[1:].values, expected_atr[1:], atol=1e-10)


def test_atr_picks_up_volatility_spike():
    """A wide bar should bump ATR upward."""
    high = pd.Series([10.5] * 20)
    low = pd.Series([9.5] * 20)
    close = pd.Series([10.0] * 20)

    # Insert a wide bar
    high.iloc[10] = 15.0
    low.iloc[10] = 9.0
    close.iloc[10] = 14.0

    out = atr(high, low, close, period=14)
    before = out.iloc[9]
    after = out.iloc[10]
    assert after > before
    # And ATR should decay back as subsequent bars are quiet
    assert out.iloc[19] < after


def test_atr_rejects_bad_period():
    s = pd.Series([1.0, 2.0, 3.0])
    with pytest.raises(ValueError):
        atr(s, s, s, period=0)
