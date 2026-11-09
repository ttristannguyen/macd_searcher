"""Tests for the target book: the boundary between the strategy and the trading bot."""

from __future__ import annotations

import random
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import yaml

from macd_searcher import target
from macd_searcher.book import Fire as BarFire
from macd_searcher.config import AppConfig, load_packaged
from macd_searcher.research import backtest as bt

D0 = date(2026, 11, 1)


def _d(k: int) -> date:
    return D0 + timedelta(days=k)


def _fire(symbol: str, k: int, direction: str = "bullish", peak_pct: float | None = 10.0) -> BarFire:
    return BarFire(symbol, _d(k), direction, peak_pct)  # type: ignore[arg-type]


def _everyone(symbols):
    return lambda d: set(symbols)


def _bars(n: int, first: date) -> pd.DataFrame:
    return pd.DataFrame({"ts": pd.date_range(pd.Timestamp(first, tz="UTC"), periods=n, freq="1D"),
                         "close": [1.0] * n})


def test_book_fires_gives_the_leg_the_side_and_the_first_flag():
    fires = target.book_fires([_fire("A", 0), _fire("A", 1), _fire("B", 1, "bearish", 80.0),
                               _fire("C", 1, "bullish", 40.0)])
    assert fires[_d(0)] == [bt.Fire("A", "L1", 1, True)]
    assert set(fires[_d(1)]) == {bt.Fire("A", "L1", 1, False), bt.Fire("B", "L2", 1, True),
                                 bt.Fire("C", None, 0, True)}


def test_a_dropped_leg_has_no_leg(monkeypatch):
    monkeypatch.setattr(target, "TRADED_LEGS", frozenset({"L1", "L2", "S1"}))
    assert target.book_fires([_fire("A", 0, "bullish", 60.0)])[_d(0)] == [bt.Fire("A", None, 0, True)]


def test_the_replay_gives_the_backtest_book_on_each_day():
    """Live trades what was tested (docs/trading_strategy.md §8.1). The bot replays
    15 days from an empty book. The backtest keeps its book from the first day."""
    rng = random.Random(0)
    symbols = [f"C{i}" for i in range(8)]
    raw = [_fire(s, k, rng.choice(["bullish", "bearish"]), rng.choice([5.0, 20.0, 40.0, 60.0, 80.0, 100.0]))
           for k in range(60) for s in symbols if rng.random() < 0.3]
    fires = target.book_fires(raw)
    book: dict = {}
    sizes = []
    for k in range(60):
        book, weights = bt.target_book(_d(k), fires.get(_d(k), ()), book, set(symbols))
        assert target.target_on(_d(k), fires, _everyone(symbols)) == (book, weights)
        sizes.append(sum(w != 0 for w in weights.values()))
    assert max(sizes) >= 5, "the random fires should build a book on both sides"


def test_the_book_starts_from_zero_on_the_start_day():
    fires = target.book_fires([_fire("OLD", 0), _fire("REFIRE", 1), _fire("REFIRE", 2),
                               _fire("NEW", 2), _fire("S", 2, "bearish", 10.0)])
    positions, _ = target.target_on(_d(3), fires, _everyone({"OLD", "REFIRE", "NEW", "S"}), start=_d(2))
    # OLD fired before the start. REFIRE's fire on the start day is a re-fire of an
    # episode that began before it, so it is not a first fire.
    assert set(positions) == {"NEW", "S"}


def test_a_stopped_short_leaves_the_book_and_a_new_first_fire_opens_it_again():
    fires = target.book_fires([_fire("S", 0, "bearish", 10.0), _fire("L", 0), _fire("L2", 0),
                               _fire("S", 9, "bearish", 10.0)])
    symbols = {"S", "L", "L2"}
    positions, _ = target.target_on(_d(5), fires, _everyone(symbols), stopped={("S", _d(0))})
    assert set(positions) == {"L", "L2"}
    positions, weights = target.target_on(_d(9), fires, _everyone(symbols), stopped={("S", _d(0))})
    assert positions["S"].entry == _d(9) and weights["S"] < 0


def test_a_coin_that_is_not_listed_today_closes():
    fires = target.book_fires([_fire("A", 0), _fire("B", 0, "bearish", 10.0)])
    positions, weights = target.target_on(_d(3), fires, lambda d: {"A", "B"} if d < _d(3) else {"A"})
    assert set(positions) == {"A"} and weights == {"A": 0.0}


def test_listed_on_needs_the_bar_of_the_day_and_the_bar_before():
    listed = target.listed_on({"A": _bars(3, _d(0)), "B": _bars(1, _d(2))})
    assert listed(_d(1)) == {"A"} and listed(_d(2)) == {"A"} and listed(_d(3)) == set()


def test_target_from_candles_gives_the_book_of_today_and_of_yesterday(monkeypatch):
    canned = {"L": [_fire("L", 0)], "S": [_fire("S", 0, "bearish", 10.0)], "NEW": [_fire("NEW", 5)]}
    seen = {}

    def fires(symbol, df, cfg, days):
        seen[symbol] = days
        return canned[symbol]

    monkeypatch.setattr(target, "closed_bar_fires", fires)
    bars = {s: _bars(10, _d(-4)) for s in canned}
    book = target.target_from_candles(_d(5), bars, AppConfig())
    assert seen["L"] == [_d(5 - k) for k in range(target.FIRE_DAYS - 1, -1, -1)]
    assert set(book.positions) == {"L", "S", "NEW"} and set(book.yesterday) == {"L", "S"}
    assert book.weights["S"] < 0 and sum(book.weights.values()) == 0


def test_target_from_candles_applies_the_stops_and_the_start_day(monkeypatch):
    canned = {"L": [_fire("L", 0)], "S": [_fire("S", 0, "bearish", 10.0)], "NEW": [_fire("NEW", 5)]}
    monkeypatch.setattr(target, "closed_bar_fires", lambda s, df, cfg, days: canned[s])
    bars = {s: _bars(10, _d(-4)) for s in canned}
    stopped = target.target_from_candles(_d(5), bars, AppConfig(), stopped={("S", _d(0))})
    assert set(stopped.positions) == {"L", "NEW"}
    late = target.target_from_candles(_d(5), bars, AppConfig(), start=_d(5))
    assert set(late.positions) == {"NEW"} and late.yesterday == {}


def test_the_packaged_settings_are_the_values_of_config_yaml():
    raw = yaml.safe_load((Path(__file__).parents[1] / "config.yaml").read_text(encoding="utf-8"))
    assert load_packaged() == AppConfig.model_validate(raw)
    assert load_packaged().signal.histogram_flattening.shrink_lookback == 2     # the code default is 3
    assert load_packaged().telegram.bot_token == ""
