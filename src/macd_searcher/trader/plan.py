"""The pure core of the trading bot: what to hold, and the orders to get there.

Closed-bar fires, prices and the ledger state go in. Positions, weights and orders
come out. No network, DB or Telegram here. The backtester's ``target_book`` makes
each decision, so the bot trades the rules that the backtest tested
(docs/trading_strategy.md §8.1).
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Collection, Iterable
from dataclasses import dataclass
from datetime import date, timedelta

import pandas as pd

from ..book import LONG_LEGS, Fire as BarFire, leg_of
from ..research import backtest as bt
from ..stats import episodes

# Only these legs open positions. To drop a leg after its watchlist check is
# contradicted (docs/trading_strategy.md §5, "leg kill"), remove it here. A fire in a
# dropped leg then leaves its coin alone, as a fire in an untraded band does.
TRADED_LEGS = frozenset({"L1", "L2", "S1", "S2"})

# Fire days that the bot reads, back from today. A position on day D comes from a
# first fire on D - HOLD_DAYS or later. The book of D - 1 needs one more day, and the
# first-fire flag of the oldest of those fires needs the day before it.
FIRE_DAYS = bt.HOLD_DAYS + 3

# No position is more than 1% of its coin's prior-day notional volume (§3.3). At
# $10k of equity this limit does not apply. It applies only at a larger size.
MAX_VOLUME_SHARE = 0.01

# Hyperliquid does not accept an order below $10 of notional. A full close is always
# sent, so that the bot does not keep a small residual position.
MIN_ORDER_USD = 10.0

# The short tail stop (§5): a short closes when the price reaches the close before
# its entry x (1 + SHORT_STOP). It is insurance against a 5x day or a liquidation
# only. Of the shorts that touch +50%, 63% end the hold better than −50%, so a
# tighter stop sells squeezes that revert. In the backtest, +100% costs 0.08 Sharpe,
# and +50% costs 0.16 (exit_research.md §6). Decided 2026-11-06.
SHORT_STOP = 1.00

# Hyperliquid's base fees (docs/trading_strategy.md §3.1). The bot sends one
# post-only limit order a coin, so a rebalance pays the maker fee. A stop and a halt
# close at the market, so they pay the taker fee.
MAKER_FEE = 0.00015
TAKER_FEE = 0.00045


# ---------------------------------------------------------------- the target book

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
              start: date = date.min) -> tuple[dict[str, bt.Position], dict[str, float]]:
    """The positions and the target weights of ``day``.

    Replay ``target_book`` from an empty book over the HOLD_DAYS + 1 days that can
    still hold a position on ``day``. A position that an earlier fire opened has
    expired by then. ``stopped`` holds the (symbol, entry day) of each short that its
    tail stop closed. Thus the result is a function of closed bars and of the stops
    only, and a second run on the same day gives the same book (§8.4).

    A fire before ``start`` opens no position. Thus the bot builds its book from zero
    on its first day, and does not buy the positions in the middle of their hold.
    """
    positions: dict[str, bt.Position] = {}
    weights: dict[str, float] = {}
    for k in range(bt.HOLD_DAYS, -1, -1):
        d = day - timedelta(days=k)
        exits = {s for s, p in positions.items() if (s, p.entry) in stopped}
        today = fires.get(d, ()) if d >= start else ()
        positions, weights = bt.target_book(d, today, positions, listed(d), exits)
    return positions, weights


def volume_capped(weights: dict[str, float], volume: dict[str, float], equity: float) -> dict[str, float]:
    """Each weight cut to MAX_VOLUME_SHARE of its coin's prior-day notional. A cut
    makes the book less neutral, and the net-exposure alert then shows it."""
    out = {}
    for s, w in weights.items():
        cap = MAX_VOLUME_SHARE * volume.get(s, 0.0) / equity
        out[s] = max(-cap, min(cap, w))
    return out


# ---------------------------------------------------------------- orders

@dataclass(frozen=True)
class Order:
    symbol: str
    size: float       # coins: + buy, - sell
    target: float     # the target weight after the order


def rebalance_orders(target: dict[str, float], held: dict[str, float], equity: float,
                     mids: dict[str, float], sz_decimals: dict[str, int]) -> list[Order]:
    """One net order for each coin that takes the held book to the target book (§3.2).

    ``held`` is the signed size of each position, in coins. A coin that is not in the
    target, or that has a target of 0, closes in full. An order below MIN_ORDER_USD is
    not sent.

    There is no drift band. A band lets the held book go net, and then the planned-net
    rule blocks the opening orders on about a third of days, at each account size. At
    the maker fee, a band saves only 0.3% a year (research log, 2026-11-07).
    """
    orders = []
    for s in sorted(set(target) | set(held)):
        size, w = held.get(s, 0.0), target.get(s, 0.0)
        if w == 0:
            if size:
                orders.append(Order(s, -size, 0.0))
            continue
        px = mids[s]
        n = sz_decimals[s]
        delta = round(round(w * equity / px, n) - size, n)
        if abs(delta * px) >= MIN_ORDER_USD:
            orders.append(Order(s, delta, w))
    return orders


def touch(size: float, bids: list[tuple[float, float]], asks: list[tuple[float, float]]) -> float:
    """The price of a post-only limit order at the touch: the best bid for a buy, and
    the best ask for a sell. The order joins the queue and pays the maker fee."""
    return bids[0][0] if size > 0 else asks[0][0]


def taker_fill(size: float, bids: list[tuple[float, float]], asks: list[tuple[float, float]]) -> float | None:
    """The average price of a market order of ``size`` coins (+ buy, - sell) that
    takes the levels of the book in sequence. None if the book is too thin."""
    left, paid = abs(size), 0.0
    for px, sz in asks if size > 0 else bids:
        take = min(left, sz)
        paid += take * px
        left -= take
        if left <= 1e-12:
            return paid / abs(size)
    return None


def resting_fill(kind: str, size: float, px: float, bars: pd.DataFrame, since: date,
                 day: date) -> tuple[date, float] | None:
    """The bar day and the price at which a resting order fills on paper, or None.

    The order rests from the bar of ``since`` to the bar of ``day`` - 1. A limit order
    fills at its price only when the price trades through it: an order at the touch
    waits behind the queue. A stop is a buy that closes a short. It fills at its
    trigger, or at the open if the bar opens above the trigger, as in the backtest.
    """
    rest = bars[(bars["ts"].dt.date >= since) & (bars["ts"].dt.date < day)]
    for bar in rest.itertuples():
        if kind == "stop" and bar.high >= px:
            return bar.ts.date(), max(px, bar.open)
        if kind == "limit" and (bar.low < px if size > 0 else bar.high > px):
            return bar.ts.date(), px
    return None


# ---------------------------------------------------------------- the short tail stop

@dataclass(frozen=True)
class StopOrder:
    symbol: str
    size: float       # coins to buy: the held short
    trigger: float
    entry: date       # the entry day of the short


def stop_orders(held: dict[str, float], weights: dict[str, float], positions: Iterable[bt.Position],
                bars: dict[str, pd.DataFrame]) -> list[StopOrder]:
    """A tail stop for each held short that the target keeps short or closes.

    The trigger is the close before the entry x (1 + SHORT_STOP), as in the backtest.
    ``positions`` has the book of yesterday, then the book of today. Today's position
    wins when both have the coin. Thus a short that exits today keeps its stop until
    its close fills. A short that flips to a long gets no stop: its buy order is
    already at the touch.
    """
    by_symbol = {p.symbol: p for p in positions if p.side < 0}
    out = []
    for s, size in sorted(held.items()):
        p, df = by_symbol.get(s), bars.get(s)
        if size >= 0 or weights.get(s, 0.0) > 0 or p is None or df is None:
            continue
        ref = df.loc[df["ts"].dt.date == p.entry - timedelta(days=1), "close"]
        if not ref.empty:
            out.append(StopOrder(s, -size, float(ref.iloc[0]) * (1 + SHORT_STOP), p.entry))
    return out


def listed_on(bars: dict[str, pd.DataFrame]) -> Callable[[date], set[str]]:
    """The coins listed on each decision day: a bar on that day (it can still be
    forming) and a bar on the day before. That is the backtest's rule: a coin with no
    return for the day is not listed."""
    days = {s: set(df["ts"].dt.date) for s, df in bars.items()}
    return lambda d: {s for s, have in days.items() if d in have and d - timedelta(days=1) in have}
