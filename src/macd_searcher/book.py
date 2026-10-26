"""The B3 book: long the good fires, short the bad fires (docs/trading_strategy.md).

Pure: candles in, positions out. No network, DB or Telegram here, so the same code
can later drive the backtester and the trading bot (trading_strategy.md §8.1).

The book is built from CLOSED daily bars, the detector the historical rebuild and
the portfolio backtests used (scripts/historical_rebuild.py), not from the
scanner's forming-candle alerts. Every 200-bar window here is cut exactly as the
rebuild cuts it, so a coin's leg on a given day never depends on when you look.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Literal

import pandas as pd

from .classify import classify_asset
from .config import AppConfig
from .indicators import macd
from .signals import Direction, _check_histogram_flattening, _peak_vs_history


Leg = Literal["L1", "L2", "S1", "S2"]
LEGS: tuple[Leg, ...] = ("L1", "L2", "S1", "S2")
LONG_LEGS: tuple[Leg, ...] = ("L1", "L2")

# Daily closes a position is held from entry; its exit is the rebalance after the
# 14th close (trading_strategy.md §1.2).
HOLD_DAYS = 14

# Bars fetched ahead of the oldest 200-bar window so MACD is warm there, as it was in
# the rebuild (which computed it over the full history). The EWM start-up effect is
# ~(25/27)^100 ≈ 0.05% of its initial size by then.
MACD_WARMUP_BARS = 100

_ONE_DAY = timedelta(days=1)


def leg_of(direction: Direction, peak_pct: float | None) -> Leg | None:
    """Which B3 leg a fire belongs to, or None for the bands the book doesn't trade
    (25-50 either way, and bullish record troughs, which are ~0 across history)."""
    if peak_pct is None:
        return None
    if direction == "bullish":
        if peak_pct <= 25:
            return "L1"          # a mild dip, already turning: long
        if 50 < peak_pct < 100:
            return "S2"          # a deep dip keeps drifting: short
        return None
    if peak_pct >= 50:
        return "L2"              # a pullback in a leader: long
    if peak_pct <= 25:
        return "S1"              # a feeble rally in a weak coin: short
    return None


@dataclass(frozen=True)
class Fire:
    """One closed-bar fire, dated the day it would be traded (the bar after the
    close it reads), as in the rebuild."""

    symbol: str
    day: date
    direction: Direction
    peak_pct: float | None


@dataclass(frozen=True)
class Position:
    symbol: str
    leg: Leg
    entry: date
    peak_pct: float


@dataclass(frozen=True)
class Book:
    day: date
    positions: list[Position]
    exits: list[Position]      # held yesterday, expired today

    def days_held(self, p: Position) -> int:
        return (self.day - p.entry).days


def history_days(cfg: AppConfig) -> int:
    """Days of candles `build_book` needs: a full window for every fire day it reads
    (today's book, yesterday's for the exits, and one more day to tell a first fire
    from a re-fire), plus MACD warm-up."""
    return cfg.candles.lookback_days + HOLD_DAYS + 2 + MACD_WARMUP_BARS


def closed_bar_fires(symbol: str, df: pd.DataFrame, cfg: AppConfig, days: list[date]) -> list[Fire]:
    """Run the production detector for each fire day on the 200 closed bars ending
    the day before, skipping days the coin fails the volume floor. A still-forming
    bar in `df` is harmless: no window reaches it."""
    lookback = cfg.candles.lookback_days
    index = {d: i for i, d in enumerate(df["ts"].dt.date)}
    m = macd(df["close"], cfg.macd.fast, cfg.macd.slow, cfg.macd.signal)
    close = df["close"].to_numpy()
    notional = (df["volume"] * df["close"]).to_numpy()

    out: list[Fire] = []
    for day in days:
        i = index.get(day - _ONE_DAY)
        if i is None or i + 1 < lookback or notional[i] < cfg.universe_filter.min_24h_volume_usd:
            continue
        window = m.iloc[i + 1 - lookback:i + 1]
        sig = _check_histogram_flattening(symbol, float(close[i]), window, cfg)
        if sig is None:
            continue
        _, pct, _ = _peak_vs_history(window["hist"], sig.direction)
        out.append(Fire(symbol, day, sig.direction, pct))
    return out


def open_positions(fires: list[Fire], day: date) -> dict[str, Position]:
    """The book as of `day`, one position per coin.

    Only the first fire of an episode opens a position: a re-fire the next day is the
    same setup (and on bearish fires, a worse one, H9). The latest first fire in a
    traded band sets the side and restarts the clock; a fire in an untraded band
    leaves the position alone.
    """
    fired = {(f.symbol, f.direction, f.day) for f in fires}
    held: dict[str, Position] = {}
    for f in sorted(fires, key=lambda f: f.day):
        if f.day > day or (f.symbol, f.direction, f.day - _ONE_DAY) in fired:
            continue
        leg = leg_of(f.direction, f.peak_pct)
        if leg is not None:
            assert f.peak_pct is not None
            held[f.symbol] = Position(f.symbol, leg, f.day, f.peak_pct)
    return {s: p for s, p in held.items() if (day - p.entry).days < HOLD_DAYS}


def build_book(candles: dict[str, pd.DataFrame], cfg: AppConfig, day: date) -> Book:
    """Today's book and today's exits, from candles alone.

    Crypto only: B3 was backtested on crypto perps. Coins outside the candle set (for
    example ones that have dropped out of the scanner's universe) are not in it.
    """
    # Fire days back to the day before yesterday's oldest position, which is
    # enough to tell its first fire from a re-fire.
    days = [day - timedelta(days=k) for k in range(HOLD_DAYS + 1, -1, -1)]
    fires = [
        f
        for symbol, df in candles.items()
        if classify_asset(symbol) == "crypto" and df is not None and not df.empty
        for f in closed_bar_fires(symbol, df, cfg, days)
    ]
    today = open_positions(fires, day)
    yesterday = open_positions(fires, day - _ONE_DAY)
    exits = [p for s, p in yesterday.items() if s not in today]
    return Book(day=day, positions=list(today.values()), exits=exits)
