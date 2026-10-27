"""Tests for the run orchestration in __main__ (no network)."""

from __future__ import annotations

import sqlite3

import pytest

from macd_searcher import __main__ as main_mod
from macd_searcher import db
from macd_searcher.config import AppConfig
from macd_searcher.signals import Signal


@pytest.mark.asyncio
async def test_a_failed_send_keeps_the_run_s_signals(monkeypatch):
    """Logging must never depend on Telegram: the signals are written before the send."""
    conn = sqlite3.connect(":memory:")
    db.init_schema(conn)
    db.start_run(conn, "run1", "2026-10-27T04:00:00+00:00", None, None, None)
    fired = Signal(name="SOL", stage="histogram_flattening", direction="bullish",
                   close=100.0, macd=-1.0, hist=-0.2, hist_peak=-0.5, reduction_from_peak=0.6)

    async def fetch(cfg, lookback_days=None, end_ms=None):
        return [], {}, 0

    async def send(*args, **kwargs):
        raise RuntimeError("Telegram HTTP 400")

    monkeypatch.setattr(main_mod, "fetch_universe_and_candles", fetch)
    monkeypatch.setattr(main_mod, "evaluate_all", lambda candles, cfg: [fired])
    monkeypatch.setattr(main_mod, "send_signals", send)

    with pytest.raises(RuntimeError):
        await main_mod._run_once(AppConfig(), conn, "run1", "2026-10-27T04:00:00+00:00")
    assert conn.execute("SELECT symbol FROM signals").fetchall() == [("SOL",)]
