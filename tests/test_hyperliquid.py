"""Tests for the pure helpers in hyperliquid (no network)."""

from __future__ import annotations

import pandas as pd

from macd_searcher.hyperliquid import trim_to_lookback

_DAY_MS = 86_400_000


def _daily(first: str, n: int) -> pd.DataFrame:
    return pd.DataFrame({
        "ts": pd.date_range(first, periods=n, freq="1D", tz="UTC"),
        "close": [float(i) for i in range(n)],
    })


def test_trim_keeps_the_bar_that_contains_the_start():
    """candleSnapshot returns the bar that opened before startTime but closes after
    it, so the trim must too, or the scan's first bar would silently change."""
    long = _daily("2026-01-01", 30)
    end_ms = int(pd.Timestamp("2026-01-30 00:00:05", tz="UTC").timestamp() * 1000)
    trimmed = trim_to_lookback({"BTC": long}, 10, end_ms)["BTC"]
    # start = 2026-01-20 00:00:05, inside the 2026-01-20 bar.
    assert trimmed["ts"].iloc[0] == pd.Timestamp("2026-01-20", tz="UTC")
    assert len(trimmed) == 11
    assert list(trimmed.index) == list(range(11))


def test_trim_drops_a_bar_that_closed_before_the_start():
    long = _daily("2026-01-01", 30)
    end_ms = int(pd.Timestamp("2026-01-30", tz="UTC").timestamp() * 1000)
    trimmed = trim_to_lookback({"BTC": long}, 10, end_ms)["BTC"]
    # start = 2026-01-20 00:00:00 exactly: the 01-19 bar closed 1ms before it.
    assert trimmed["ts"].iloc[0] == pd.Timestamp("2026-01-20", tz="UTC")
