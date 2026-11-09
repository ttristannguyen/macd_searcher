"""The B3 target book of a day, for the trading bot (docs/trading_strategy.md §8.1).

This module is the boundary between the strategy and the bot. The bot reads the book
through ``target_from_candles`` and imports the other names that it needs from here.
The backtester's ``target_book`` makes each decision, so the bot trades the rules
that the backtest tested. Pure: candles go in, and the book comes out.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Collection, Iterable
from dataclasses import dataclass
from datetime import date, timedelta

import pandas as pd

from .book import LONG_LEGS, Fire as BarFire, closed_bar_fires, history_days, leg_of
from .config import AppConfig
from .research import backtest as bt
from .research.backtest import COST_PER_SIDE, FUNDING_LONG_APR, FUNDING_SHORT_APR, Position
from .stats import episodes

__all__ = ["COST_PER_SIDE", "FUNDING_LONG_APR", "FUNDING_SHORT_APR", "FIRE_DAYS", "Position", "TRADED_LEGS", "Target",
           "book_fires", "history_days", "listed_on", "target_from_candles", "target_on"]

# Only these legs open positions. To drop a leg after its watchlist check is
# contradicted (docs/trading_strategy.md §5, "leg kill"), remove it here. A fire in a
# dropped leg then leaves its coin alone, as a fire in an untraded band does.
TRADED_LEGS = frozenset({"L1", "L2", "S1", "S2"})

# Fire days that the book reads, back from today. A position on day D comes from a
# first fire on D - HOLD_DAYS or later. The book of D - 1 needs one more day, and the
# first-fire flag of the oldest of those fires needs the day before it.
FIRE_DAYS = bt.HOLD_DAYS + 3


def book_fires(fires: Iterable[BarFire]) -> dict[date, list[bt.Fire]]:
    """The fires of each day as ``target_book`` reads them: with a leg, a side and
    the first-fire flag. A fire outside TRADED_LEGS has no leg."""
    fires = list(fires)
    _, first = episodes([f.symbol for f in fires], [f.direction for f in fires],
                        [f.day.isoformat() for f in fires], bt.EPISODE_GAP_DAYS)
    out: dict[date, list[bt.Fire]] = defaultdict(list)
    for f, is_first in zip(fires, first):
        leg = leg_of(f.direction, f.peak_pct)
        leg = leg if leg in TRADED_LEGS else None
        side = 0 if leg is None else (1 if leg in LONG_LEGS else -1)
        out[f.day].append(bt.Fire(f.symbol, leg, side, is_first))
    return dict(out)


def target_on(day: date, fires: dict[date, list[bt.Fire]], listed: Callable[[date], Collection[str]],
              stopped: Collection[tuple[str, date]] = (),
              start: date = date.min) -> tuple[dict[str, Position], dict[str, float]]:
    """The positions and the target weights of ``day``.

    Replay ``target_book`` from an empty book over the HOLD_DAYS + 1 days that can
    still hold a position on ``day``. A position that an earlier fire opened has
    expired by then. ``stopped`` holds the (symbol, entry day) of each short that its
    tail stop closed. Thus the result is a function of closed bars and of the stops
    only, and a second run on the same day gives the same book (§8.4).

    A fire before ``start`` opens no position. Thus the bot builds its book from zero
    on its first day, and does not buy the positions in the middle of their hold.
    """
    positions: dict[str, Position] = {}
    weights: dict[str, float] = {}
    for k in range(bt.HOLD_DAYS, -1, -1):
        d = day - timedelta(days=k)
        exits = {s for s, p in positions.items() if (s, p.entry) in stopped}
        today = fires.get(d, ()) if d >= start else ()
        positions, weights = bt.target_book(d, today, positions, listed(d), exits)
    return positions, weights


def listed_on(bars: dict[str, pd.DataFrame]) -> Callable[[date], set[str]]:
    """The coins listed on each decision day: a bar on that day (it can still be
    forming) and a bar on the day before. That is the backtest's rule: a coin with no
    return for the day is not listed."""
    days = {s: set(df["ts"].dt.date) for s, df in bars.items()}
    return lambda d: {s for s, have in days.items() if d in have and d - timedelta(days=1) in have}


@dataclass(frozen=True)
class Target:
    positions: dict[str, Position]      # today's book
    weights: dict[str, float]           # a fraction of equity: + long, - short
    yesterday: dict[str, Position]      # a short that exits today keeps its stop until it closes


def target_from_candles(day: date, candles: dict[str, pd.DataFrame], cfg: AppConfig,
                        stopped: Collection[tuple[str, date]] = (), start: date = date.min) -> Target:
    """The book of ``day``, from the daily candles of each coin.

    ``candles`` needs ``history_days(cfg)`` days. A coin with no candles counts as not
    listed, so its position closes: the caller must stop if a fetch failed. ``stopped``
    and ``start`` are inputs because only the bot knows them, and they change the
    weights of the other names.
    """
    fire_days = [day - timedelta(days=k) for k in range(FIRE_DAYS - 1, -1, -1)]
    fires = book_fires(f for s, df in candles.items() for f in closed_bar_fires(s, df, cfg, fire_days))
    listed = listed_on(candles)
    positions, weights = target_on(day, fires, listed, stopped, start)
    yesterday, _ = target_on(day - timedelta(days=1), fires, listed, stopped, start)
    return Target(positions, weights, yesterday)
