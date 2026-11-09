"""Tests for the pure helpers and the parsers in hyperliquid (no network)."""

from __future__ import annotations

import httpx
import pandas as pd

from macd_searcher.config import AppConfig
from macd_searcher.hyperliquid import PerpSpec, fetch_core_perps, fetch_l2_book, trim_to_lookback

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


def _client(payload) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(lambda req: httpx.Response(200, json=payload)))


async def test_core_perps_drop_the_delisted_and_keep_the_illiquid():
    payload = [{"universe": [{"name": "BTC", "szDecimals": 5, "maxLeverage": 40},
                             {"name": "OLD", "szDecimals": 0, "maxLeverage": 3, "isDelisted": True},
                             {"name": "TINY", "szDecimals": 0, "maxLeverage": 3}]},
               [{"midPx": "60000.5", "dayNtlVlm": "1e9"}, {"midPx": "1"}, {"midPx": None, "markPx": "0.01"}]]
    async with _client(payload) as client:
        perps = await fetch_core_perps(client, AppConfig())
    assert perps == [PerpSpec("BTC", 5, 40, 60000.5), PerpSpec("TINY", 0, 3, 0.01)]


async def test_l2_book_parses_both_sides():
    payload = {"coin": "BTC", "levels": [[{"px": "99", "sz": "2", "n": 1}], [{"px": "101", "sz": "3", "n": 2}]]}
    async with _client(payload) as client:
        assert await fetch_l2_book(client, "BTC", AppConfig()) == ([(99.0, 2.0)], [(101.0, 3.0)])
