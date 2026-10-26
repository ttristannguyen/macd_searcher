"""Tests for the B3 book: leg bands, the closed-bar fire history, and positions."""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from macd_searcher import book as book_mod
from macd_searcher.book import (
    HOLD_DAYS,
    Fire,
    build_book,
    closed_bar_fires,
    history_days,
    leg_of,
    open_positions,
)
from macd_searcher.config import AppConfig

TODAY = date(2026, 10, 26)


def _d(k: int) -> date:
    """`k` days before TODAY."""
    return TODAY - timedelta(days=k)


def _candles(closes: list[float], end: date = TODAY, volume: float = 1e6) -> pd.DataFrame:
    """Daily OHLCV whose last bar opens on `end` (the forming bar on a run that day)."""
    s = pd.Series(closes, dtype=float)
    return pd.DataFrame({
        "ts": pd.date_range(end=pd.Timestamp(end, tz="UTC"), periods=len(closes), freq="1D"),
        "open": s, "high": s, "low": s, "close": s,
        "volume": pd.Series([volume] * len(closes)),
    })


def _random_walk(n: int, seed: int = 0) -> list[float]:
    rng = np.random.default_rng(seed)
    return list(100 * np.exp(np.cumsum(rng.normal(0, 0.04, n))))


def _selloff_then_fade_ending_yesterday() -> list[float]:
    """A long flat stretch, a steady selloff, and a fade whose last bar is yesterday's
    close, then today's forming bar. Bullish on closed bars today."""
    closes = [100.0] * 230 + [100.0 - 2.0 * i for i in range(30)]
    last = closes[-1]
    for k in range(4):
        last -= 2.0 * (1.0 - (k + 1) / 5)
        closes.append(last)
    return closes + [last]


# ---------- legs ----------


@pytest.mark.parametrize("direction,peak_pct,leg", [
    ("bullish", 0.0, "L1"), ("bullish", 25.0, "L1"), ("bullish", 25.1, None),
    ("bullish", 50.0, None), ("bullish", 50.1, "S2"), ("bullish", 99.9, "S2"),
    ("bullish", 100.0, None),                       # record trough: ~0 across history
    ("bearish", 25.0, "S1"), ("bearish", 30.0, None), ("bearish", 50.0, "L2"),
    ("bearish", 100.0, "L2"),
    ("bullish", None, None), ("bearish", None, None),
])
def test_leg_bands(direction, peak_pct, leg):
    assert leg_of(direction, peak_pct) == leg


# ---------- closed-bar fires ----------


def test_closed_bar_fire_is_dated_the_day_after_the_close_it_reads():
    df = _candles(_selloff_then_fade_ending_yesterday())
    fires = closed_bar_fires("SOL", df, AppConfig(), [TODAY])
    assert [(f.day, f.direction) for f in fires] == [(TODAY, "bullish")]


def test_forming_bar_cannot_change_a_fire():
    closes = _selloff_then_fade_ending_yesterday()
    calm = closed_bar_fires("SOL", _candles(closes), AppConfig(), [TODAY])
    spiked = closed_bar_fires("SOL", _candles(closes[:-1] + [closes[-1] * 3]), AppConfig(), [TODAY])
    assert calm == spiked


def test_a_day_s_fires_do_not_depend_on_later_bars():
    """The book re-reads the last 16 days every run; a fire must read the same each time."""
    cfg = AppConfig()
    closes = _random_walk(330)
    full = _candles(closes)
    days = [_d(k) for k in range(30, 0, -1)]
    fires = closed_bar_fires("X", full, cfg, days)
    assert any(f.peak_pct is not None for f in fires), "the walk should fire somewhere in 30 days"
    for f in fires:
        k = (TODAY - f.day).days
        cut = _candles(closes[: len(closes) - k], end=f.day)    # that day's run: its bar forming
        assert closed_bar_fires("X", cut, cfg, [f.day]) == [f]


def test_volume_floor_and_short_history_skip_the_day():
    cfg = AppConfig()
    closes = _selloff_then_fade_ending_yesterday()
    assert closed_bar_fires("SOL", _candles(closes, volume=1.0), cfg, [TODAY]) == []
    short = closes[-cfg.candles.lookback_days:]      # 199 closed bars + the forming one
    assert closed_bar_fires("SOL", _candles(short), cfg, [TODAY]) == []


def test_history_days_covers_every_window_the_book_reads():
    cfg = AppConfig()
    # 16 fire days, each a window of `lookback` closed bars ending the day before.
    assert history_days(cfg) > cfg.candles.lookback_days + HOLD_DAYS + 1


# ---------- positions ----------


def _fire(symbol: str, k: int, direction: str = "bullish", peak_pct: float | None = 10.0) -> Fire:
    return Fire(symbol, _d(k), direction, peak_pct)  # type: ignore[arg-type]


def test_a_first_fire_opens_a_position_in_its_leg():
    book = open_positions([_fire("A", 3, "bearish", 80.0)], TODAY)
    assert book["A"].leg == "L2" and book["A"].entry == _d(3)


def test_a_re_fire_neither_opens_nor_extends_a_position():
    # The episode starts 14 days ago in an untraded band; its re-fires in L1 don't count.
    fires = [_fire("A", 14, peak_pct=40.0), _fire("A", 13), _fire("A", 12)]
    assert open_positions(fires, TODAY) == {}
    # A traded first fire 14 days ago has expired, however long the episode ran.
    fires = [_fire("A", 14), _fire("A", 13), _fire("A", 12)]
    assert open_positions(fires, TODAY) == {}


def test_position_expires_after_the_hold():
    fires = [_fire("A", HOLD_DAYS - 1)]
    assert "A" in open_positions(fires, TODAY)
    assert "A" not in open_positions(fires, TODAY + timedelta(days=1))


def test_a_new_episode_restarts_the_clock():
    fires = [_fire("A", 10), _fire("A", 2)]           # a gap of more than a day
    assert open_positions(fires, TODAY)["A"].entry == _d(2)


def test_a_traded_first_fire_flips_the_side():
    fires = [_fire("A", 6, "bullish", 10.0), _fire("A", 2, "bearish", 10.0)]
    assert open_positions(fires, TODAY)["A"].leg == "S1"


def test_an_untraded_fire_leaves_the_position_alone():
    fires = [_fire("A", 6, "bullish", 10.0), _fire("A", 2, "bearish", 40.0)]
    assert open_positions(fires, TODAY)["A"].leg == "L1"


def test_future_fires_are_ignored():
    assert open_positions([_fire("A", -1)], TODAY) == {}


# ---------- the whole book ----------


def test_build_book_reads_crypto_only_back_far_enough_for_yesterday(monkeypatch):
    """Yesterday's oldest position entered HOLD_DAYS - 1 days before it, and telling
    that fire from a re-fire needs the day before: HOLD_DAYS + 1 days back."""
    seen: dict[str, list[date]] = {}

    def fake(symbol, df, cfg, days):
        seen[symbol] = days
        return []

    monkeypatch.setattr(book_mod, "closed_bar_fires", fake)
    flat = _candles([100.0] * 5)
    build_book({"SOL": flat, "xyz:TSLA": flat}, AppConfig(), TODAY)
    assert list(seen) == ["SOL"]
    assert seen["SOL"] == [_d(k) for k in range(HOLD_DAYS + 1, -1, -1)]


def test_build_book_exits_are_today_s_expiries_not_flips(monkeypatch):
    canned = {
        "OLD": [_fire("OLD", HOLD_DAYS)],                                     # expires today
        "NEW": [_fire("NEW", 0)],
        "FLIP": [_fire("FLIP", 5, "bullish", 10.0), _fire("FLIP", 0, "bearish", 10.0)],
    }
    monkeypatch.setattr(book_mod, "closed_bar_fires", lambda s, df, cfg, days: canned[s])
    flat = _candles([100.0] * 5)
    book = build_book({s: flat for s in canned}, AppConfig(), TODAY)
    assert [p.symbol for p in book.exits] == ["OLD"]
    assert {p.symbol: p.leg for p in book.positions} == {"NEW": "L1", "FLIP": "S1"}
    assert book.days_held(next(p for p in book.positions if p.symbol == "NEW")) == 0
