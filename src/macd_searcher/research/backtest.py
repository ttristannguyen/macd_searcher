"""The B3 backtester: the reference for every portfolio number in the docs.

    uv run python -m macd_searcher.research.backtest            # the baseline
    uv run python -m macd_searcher.research.backtest --rebuild  # rebuild the frozen panel first

The layers are the same as ``stats.py`` -> ``web/perf.py``:

* ``target_book`` is pure. Fires, the open positions and the listed coins go in.
  Positions and target weights come out. The live bot will call it
  (docs/trading_strategy.md §8.1).
* ``simulate`` calls it once a day over the frozen panel, and ``account`` does the
  accounting: drift, turnover, costs and funding.
* ``build_panel`` and ``load_panel`` do the I/O. Candles go in, and the frozen
  coin-day panel comes out.

The rules of the book are the constants below. A variant (docs/trading_strategy.md
§8.2) must name each rule that it changes, as a keyword argument.
"""

from __future__ import annotations

import argparse
import pickle
import sys
from collections.abc import Callable, Collection, Iterable, Sequence
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd

from ..book import LONG_LEGS, leg_of
from ..config import AppConfig, load_config
from ..indicators import macd
from ..signals import _check_histogram_flattening, _peak_vs_history
from ..stats import CI_LEVEL, episodes
from . import cache, dataset

# ---------------------------------------------------------------- the rules

# A position stays open until the close of fire day + HOLD_DAYS. That is the exit bar of
# alpha_14d in the research pipeline (dataset.attach_candle_exits). A fire on day D
# enters at the close of D - 1, so a hold earns HOLD_DAYS + 1 daily returns.
HOLD_DAYS = 14

# Only the first fire of an episode opens a position. A re-fire on the next day is the
# same setup, and bearish re-fires are worse shorts (H9). An episode is a run of
# same-direction fires with gaps of at most one day (stats.episodes).
FIRST_FIRES_ONLY = True
EPISODE_GAP_DAYS = 1

# No name gets more than 10% of equity. Both sides are sized to the thinner side, so
# the book stays dollar-neutral: side gross = min(100%, 10% x names on the thinner
# side). Weights are equal within a side. The rest of the equity stays in cash.
MAX_WEIGHT = 0.10

# 0.10% of each unit traded: Hyperliquid's 0.045% taker fee plus 0.055% of assumed
# slippage (docs/profit_strategies.md). It applies to all turnover. That includes the
# trades that bring drifted weights back to target, and the universe basket.
COST_PER_SIDE = 0.001

# The live bot (docs/trading_bot.md) sends post-only limit orders at the touch. A
# filled limit order pays Hyperliquid's base maker fee and no slippage. The price that
# a resting order does not get is in the fill rule of ``account``, not in this fee.
MAKER_COST = 0.00015

# Hyperliquid refuses an order below $10 of notional. The bot drops such an order, but
# it always sends a full close. If the dropped orders make the planned book more than
# ±10% net, the bot sends only the closes (docs/trading_bot.md §4, step 8).
MIN_ORDER_USD = 10.0
MAX_PLANNED_NET = 0.10

# Flat funding from the live measurements (docs/confidence_v3_research.md §8): longs
# pay 9% APR and shorts receive 6.5% APR.
FUNDING_LONG_APR = 0.09
FUNDING_SHORT_APR = 0.065

# The last day of the backtest: the last closed bar in history/, which has every coin.
# The candle cache has newer bars only for the coins that the scanner saw after
# 2026-06. After this day, 30 live coins have no bars, and the book would treat them
# as delisted (8 open positions on this day).
WINDOW_END = date(2026, 10, 15)

# Sharpe intervals resample 30-day blocks of daily returns. Holds overlap for 15 days,
# so a block keeps about two holds together.
BOOT_BLOCK_DAYS = 30
BOOT_DRAWS = 2000

PANEL_FILE = "backtest_panel.pkl"

# The other rules have no value to pin, so the code enforces them where they apply:
# * one position per coin (``target_book``);
# * a traded first fire opens, flips or restarts that position, and a fire in a band
#   that the book does not trade leaves it alone (``target_book``);
# * a delisted coin exits at its last close (``simulate``: a coin with no bar today is
#   not listed);
# * we never read a symbol's newest cached bar (``load_bars``).


# ---------------------------------------------------------------- the pure core

@dataclass(frozen=True)
class Fire:
    """One closed-bar fire on its decision day. ``leg`` is None for a band that the
    book does not trade. ``side`` is +1 for a long leg and -1 for a short leg."""

    symbol: str
    leg: str | None
    side: int
    first: bool


@dataclass(frozen=True)
class Position:
    symbol: str
    leg: str
    side: int
    entry: date      # the fire day: the book enters at the close of the day before
    last: date       # the last day held: the book exits at the close of this day


def target_book(day: date, fires: Iterable[Fire], positions: dict[str, Position], listed: Collection[str],
                exits: Collection[str] = (), *, holds: dict[str, int] | None = None,
                tilt: Callable[[date, Position], float] | None = None,
                basket: Sequence[str] | None = None, first_only: bool = FIRST_FIRES_ONLY,
                restart_same_leg: bool = False) -> tuple[dict[str, Position], dict[str, float]]:
    """Today's positions and target weights (a fraction of equity: + long, - short).

    ``positions`` is the book after the last rebalance. A position closes when its hold
    ends, when its coin is not in ``listed``, or when its coin is in ``exits`` (a stop
    or an exit rule that the caller applies). Then each traded first fire opens a
    position, or flips or restarts the open position on that coin.

    The variants are off by default: ``holds`` gives a hold per leg, ``tilt`` gives a
    weight factor per position, and ``basket`` fills the thin side with an equal-weight
    basket of these coins (docs/trading_strategy.md §8.2). With ``restart_same_leg``, a
    re-fire in the leg of the open position restarts that position. Other re-fires
    still do nothing.
    """
    book = {s: p for s, p in positions.items() if p.last >= day and s in listed and s not in exits}
    for f in fires:
        if f.leg is None or f.symbol not in listed:
            continue
        same_leg = f.symbol in book and book[f.symbol].leg == f.leg
        if first_only and not f.first and not (restart_same_leg and same_leg):
            continue
        hold = (holds or {}).get(f.leg, HOLD_DAYS)
        book[f.symbol] = Position(f.symbol, f.leg, f.side, day, day + timedelta(days=hold))
    return book, _weights(day, book, tilt, basket)


def _weights(day: date, book: dict[str, Position], tilt, basket) -> dict[str, float]:
    """Both sides get the gross of the thinner side. With a basket, they get the gross of
    the thicker side, and the basket fills the gap. Inside a side, the weights follow the
    tilt (equal by default) and stop at MAX_WEIGHT."""
    sides = [[p for p in book.values() if p.side > 0], [p for p in book.values() if p.side < 0]]
    n_thin, n_thick = sorted(len(s) for s in sides)
    gross = min(1.0, MAX_WEIGHT * (n_thick if basket is not None else n_thin))
    weights: dict[str, float] = {}
    for sign, side in zip((1, -1), sides):
        if not side:
            continue
        side_gross = min(gross, MAX_WEIGHT * len(side))      # a thin side can hold only 10% a name
        factor = np.array([tilt(day, p) if tilt else 1.0 for p in side])
        weights.update({p.symbol: sign * x for p, x in zip(side, _capped(side_gross, factor))})
    gap = sum(weights.values())          # the net exposure: the basket takes the other side
    if basket and gap:
        for s in basket:
            weights[s] = weights.get(s, 0.0) - gap / len(basket)
    return weights


def _capped(total: float, factor: np.ndarray) -> np.ndarray:
    """Weights in proportion to ``factor``, with a sum of ``total`` and none above
    MAX_WEIGHT. The weight above the cap moves to the names below the cap. Thus the side
    keeps its gross, and the book stays dollar-neutral. On a thinner side of 10 names or
    fewer, each name is at the cap, so a tilt has no effect there."""
    w = np.zeros(len(factor))
    free = np.ones(len(factor), dtype=bool)
    while free.any():
        w[free] = (total - w[~free].sum()) * factor[free] / factor[free].sum()
        over = free & (w > MAX_WEIGHT)
        if not over.any():
            break
        w[over] = MAX_WEIGHT
        free &= ~over
    return w


# ---------------------------------------------------------------- simulation

@dataclass(frozen=True)
class Panel:
    """The frozen inputs. Row t of each matrix is decision day ``days[t]``: the book
    trades at the close of day t - 1 and earns the return of bar t."""

    meta: dict
    coin_days: pd.DataFrame
    close: pd.DataFrame      # all closes, one row per calendar day (indicators need the bars before the window)
    symbols: list[str]
    days: list[date]
    ret: np.ndarray          # the return of bar t; NaN if the coin has no bar t or t - 1
    open: np.ndarray
    high: np.ndarray
    prev_close: np.ndarray   # the close of bar t - 1, the price at the rebalance of day t
    eligible: np.ndarray     # in the universe: 200+ closed bars and prior-day notional >= the floor
    first_bar: dict[str, date]
    low: np.ndarray | None = None    # the frozen panel has no lows: ``with_low`` adds them

    @property
    def listed(self) -> np.ndarray:
        return ~np.isnan(self.ret)

    @property
    def universe(self) -> np.ndarray:
        return self.eligible & self.listed


def book_fires(panel: Panel) -> pd.DataFrame:
    """Every fire in the window, with its B3 leg (``book.leg_of``), side and episode."""
    f = panel.coin_days[panel.coin_days["fire"].notna()].copy()
    _, f["first"] = episodes(f["symbol"].tolist(), f["fire"].tolist(), f["day"].tolist(), EPISODE_GAP_DAYS)
    f["peak_pct"] = f["state_pct"]          # a fire is in the direction of its own state
    f["leg"] = [leg_of(d, None if np.isnan(p) else p) for d, p in zip(f["fire"], f["peak_pct"])]
    f["side"] = np.where(f["leg"].isin(LONG_LEGS), 1, np.where(f["leg"].notna(), -1, 0))
    return f[f["day"] <= panel.days[-1].isoformat()].reset_index(drop=True)


@dataclass(frozen=True)
class Run:
    days: list[date]
    weights: np.ndarray     # what the book holds each day, after a drift band
    ret: np.ndarray         # the coin returns that the book earned, with stop fills
    net: np.ndarray         # the daily return after costs and funding
    gross: np.ndarray       # the daily return before costs and funding
    cost: np.ndarray
    funding: np.ndarray
    turnover: np.ndarray    # the sum of |trade| as a fraction of equity
    longs: np.ndarray       # names per side in the book; the basket is not counted
    shorts: np.ndarray
    sent: np.ndarray | None = None         # day x coin: an order went to the coin
    filled: np.ndarray | None = None       # day x coin: that order filled
    closes_only: np.ndarray | None = None  # a day on which the $10 minimum let only the closes go


def account(weights: np.ndarray, ret: np.ndarray, *, cost: float = COST_PER_SIDE, band: float = 0.0,
            equity: float | None = None, fills: tuple[np.ndarray, np.ndarray, np.ndarray] | None = None,
            cross: bool = False) -> dict[str, np.ndarray]:
    """Daily returns of a book that trades to ``weights`` at each close.

    Weights drift with prices between rebalances. Each trade from the drifted weight to
    the target pays ``cost`` per side. With a ``band`` > 0, the book keeps a drifted
    weight that is within ``band`` x |target| of the target (§8.2 variant 2).

    The live bot's rules are off by default (docs/trading_bot.md):

    * ``equity`` is the account size in USD, the same each day. An order below
      MIN_ORDER_USD does not go, and the held weight stays (``_min_orders``).
    * ``fills`` = (buy, sell, forced), day x coin masks, makes each order a resting
      limit order at the close before the bar. A buy fills on a bar where ``buy`` is
      True, a sell where ``sell`` is True, and a ``forced`` trade does not wait (a stop
      fill or a delisting). An order that does not fill keeps the held weight, and the
      next rebalance sends a new order. A filled limit order pays MAKER_COST.
    * With ``cross``, an order that did not fill on the bar before crosses the spread
      at this rebalance. Forced and crossed trades pay ``cost``.
    """
    n_days, n_coins = weights.shape
    held = np.zeros(n_coins)
    waited = np.zeros(n_coins, dtype=bool)        # the order on the last bar did not fill
    out = {k: np.zeros(n_days) for k in ("net", "gross", "cost", "funding", "turnover")}
    out["closes_only"] = np.zeros(n_days, dtype=bool)
    out["sent"], out["filled"] = np.zeros(weights.shape, dtype=bool), np.zeros(weights.shape, dtype=bool)
    traded = weights.copy()
    for t in range(n_days):
        target = w = weights[t]
        if band:
            keep = (w != 0) & (np.sign(w) == np.sign(held)) & (np.abs(w - held) <= band * np.abs(w))
            w = np.where(keep, held, w)
        if equity is not None:
            w, out["closes_only"][t] = _min_orders(target, w, held, equity)
        sent = w != held
        taker = sent
        if fills is not None:
            buy, sell, forced = (m[t] for m in fills)
            taker = sent & (forced | (waited & cross))
            done = taker | (sent & (w > held) & buy) | (sent & (w < held) & sell)
            waited = sent & ~done
            w = np.where(done, w, held)
        out["sent"][t], out["filled"][t] = sent, w != held
        traded[t] = w
        assert not np.isnan(ret[t][w != 0]).any(), "the book holds a coin with no bar"
        r = np.where(w != 0, ret[t], 0.0)
        gross = float(w @ r)
        delta = np.abs(w - held)
        turnover = float(delta.sum())
        fee = cost * turnover if fills is None else cost * delta[taker].sum() + MAKER_COST * delta[~taker].sum()
        funding = (w[w > 0].sum() * FUNDING_LONG_APR + w[w < 0].sum() * FUNDING_SHORT_APR) / 365
        out["gross"][t], out["turnover"][t] = gross, turnover
        out["cost"][t], out["funding"][t] = fee, funding
        out["net"][t] = gross - fee - funding
        held = w * (1 + r) / (1 + gross)
    out["weights"] = traded
    return out


def _min_orders(target: np.ndarray, w: np.ndarray, held: np.ndarray, equity: float) -> tuple[np.ndarray, bool]:
    """The bot's $10 rules (docs/trading_bot.md §4, step 8). A full close always goes.
    Another order below MIN_ORDER_USD does not go. If the orders that remain make the
    planned book more than MAX_PLANNED_NET net, only the closes go: the bot does not
    open an unhedged book. Returns the weights after the orders, and True if only the
    closes went."""
    close = (target == 0) & (held != 0)
    w = np.where(~close & (np.abs(w - held) * equity < MIN_ORDER_USD), held, w)
    if abs(w.sum()) > MAX_PLANNED_NET:
        return np.where(close, 0.0, held), True
    return w, False


def simulate(panel: Panel, fires: pd.DataFrame, *, holds: dict[str, int] | None = None,
             tilt: Callable[[date, Position], float] | None = None, basket: np.ndarray | None = None,
             first_only: bool = FIRST_FIRES_ONLY, restart_same_leg: bool = False,
             short_stop: float | None = None, stop_delay: int = 0,
             exit_rule: Callable[[date, Position], bool] | None = None,
             cost: float = COST_PER_SIDE, band: float = 0.0,
             fill: Literal["close", "limit", "limit_then_cross"] = "close", equity: float | None = None) -> Run:
    """Run ``target_book`` once a day over the panel, then ``account`` for the returns.

    ``fires`` is ``book_fires(panel)`` or a subset of it. ``basket`` is a day x coin mask
    of the basket members, for example ``panel.universe``. ``short_stop`` closes a short
    when the bar's high reaches entry x (1 + short_stop). The fill is at that price, or
    at the open if the bar opens above it (§8.2 variant 3). The stop starts
    ``stop_delay`` days after the fire day: the live bot places the stop of a new short
    at the next daily run. ``exit_rule`` closes a position at a rebalance when it
    returns True.

    ``fill`` is how the orders fill. "close" is the backtest's rule: at the close, at
    ``cost``. "limit" is the live bot's rule: a post-only limit order at the close
    before the bar, which rests for one bar. A buy fills if the bar's low is below that
    price, and a sell if the high is above it. "limit_then_cross" crosses the spread
    one day later if the limit order did not fill. Both need ``panel.low``
    (``with_low``). ``equity`` (USD) adds the bot's $10 rules (``account``).
    """
    if fill != "close" and panel.low is None:
        raise ValueError(f"fill={fill!r} needs the bar lows: use with_low(panel, root)")
    col = {s: j for j, s in enumerate(panel.symbols)}
    row = {d: t for t, d in enumerate(panel.days)}
    by_day = {date.fromisoformat(d): [Fire(r.symbol, r.leg if pd.notna(r.leg) else None, r.side, r.first)
                                      for r in g.itertuples()]
              for d, g in fires.groupby("day")}
    weights = np.zeros_like(panel.ret)
    ret = panel.ret.copy()
    longs, shorts = np.zeros(len(panel.days)), np.zeros(len(panel.days))
    listed_mask = panel.listed
    book: dict[str, Position] = {}
    stopped: set[str] = set()
    forced = np.isnan(panel.ret)          # a delisted coin closes at its last close
    for t, day in enumerate(panel.days):
        listed = {panel.symbols[j] for j in np.flatnonzero(listed_mask[t])}
        exits = stopped | {s for s, p in book.items() if exit_rule and exit_rule(day, p)}
        members = [panel.symbols[j] for j in np.flatnonzero(basket[t])] if basket is not None else None
        book, target = target_book(day, by_day.get(day, ()), book, listed, exits, holds=holds, tilt=tilt,
                                   basket=members, first_only=first_only, restart_same_leg=restart_same_leg)
        for s, w in target.items():
            weights[t, col[s]] = w
        longs[t] = sum(p.side > 0 for p in book.values())
        shorts[t] = len(book) - longs[t]
        stopped = set()
        if short_stop is None:
            continue
        for s, p in book.items():
            if p.side > 0 or (day - p.entry).days < stop_delay:
                continue
            j = col[s]
            stop = panel.prev_close[row[p.entry], j] * (1 + short_stop)
            if panel.high[t, j] >= stop:
                ret[t, j] = max(stop, panel.open[t, j]) / panel.prev_close[t, j] - 1
                stopped.add(s)
                forced[min(t + 1, len(panel.days) - 1), j] = True      # the stop fill does not wait
    fills = None
    if fill != "close":
        fills = (panel.low < panel.prev_close, panel.high > panel.prev_close, forced)
    acc = account(weights, ret, cost=cost, band=band, equity=equity, fills=fills, cross=fill == "limit_then_cross")
    return Run(days=panel.days, weights=acc["weights"], ret=ret, net=acc["net"], gross=acc["gross"],
               cost=acc["cost"], funding=acc["funding"], turnover=acc["turnover"], longs=longs, shorts=shorts,
               sent=acc["sent"], filled=acc["filled"], closes_only=acc["closes_only"])


# ---------------------------------------------------------------- statistics (pure)

def sharpe(r: np.ndarray) -> float:
    return float(r.mean() / r.std() * np.sqrt(365))


def cagr(r: np.ndarray) -> float:
    return float(np.prod(1 + r) ** (365 / len(r)) - 1)


def max_drawdown(r: np.ndarray) -> float:
    equity = np.cumprod(1 + r)
    return float((equity / np.maximum.accumulate(equity) - 1).min())


def _block_index(n: int, draws: int = BOOT_DRAWS, block: int = BOOT_BLOCK_DAYS, seed: int = 0) -> np.ndarray:
    """Row indices of ``draws`` series of length ``n``. Each series joins random blocks."""
    starts = np.random.default_rng(seed).integers(0, n - block + 1, size=(draws, -(-n // block)))
    return (starts[:, :, None] + np.arange(block)).reshape(draws, -1)[:, :n]


def _sharpes(x: np.ndarray) -> np.ndarray:
    return x.mean(axis=1) / x.std(axis=1) * np.sqrt(365)


def sharpe_ci(r: np.ndarray) -> tuple[float, float]:
    tail = (1 - CI_LEVEL) / 2 * 100
    lo, hi = np.percentile(_sharpes(r[_block_index(len(r))]), [tail, 100 - tail])
    return float(lo), float(hi)


def sharpe_diff_ci(base: np.ndarray, variant: np.ndarray) -> tuple[float, float, float]:
    """(Sharpe of variant - Sharpe of base, lo, hi). Both books get the same blocks."""
    idx = _block_index(len(base))
    tail = (1 - CI_LEVEL) / 2 * 100
    lo, hi = np.percentile(_sharpes(variant[idx]) - _sharpes(base[idx]), [tail, 100 - tail])
    return sharpe(variant) - sharpe(base), float(lo), float(hi)


def period_returns(r: np.ndarray, days: Sequence[date], period: str) -> pd.Series:
    """The compounded return of each calendar "year", "half" (2023H1) or "month"."""
    label = {"year": lambda d: str(d.year), "half": lambda d: f"{d.year}H{1 if d.month <= 6 else 2}",
             "month": lambda d: f"{d.year}-{d.month:02d}"}[period]
    return pd.Series(r).groupby([label(d) for d in days]).apply(lambda x: float(np.prod(1 + x) - 1))


# ---------------------------------------------------------------- the frozen panel (I/O)

def load_bars(root: Path) -> dict[str, pd.DataFrame]:
    """Closed daily bars for each coin in ``history/``, extended with the newer bars in
    ``candles/``.

    ``history/`` is the one-off fetch of every core crypto perp, with the delisted
    coins (scripts/historical_rebuild.py). ``candles/`` is the research cache, which the
    pipeline tops up each day. We never read a symbol's newest cached bar in either
    source, because it can be a forming bar (``dataset.closed_candles``).
    """
    symbols = [p.stem.replace("__", ":") for p in sorted((root / "history").glob("*.csv"))]
    history = dataset.closed_candles(cache.load(root, "history", symbols))
    candles = dataset.closed_candles(cache.load(root, "candles", symbols))
    out = {}
    for symbol, df in history.items():
        newer = candles.get(symbol)
        if newer is not None:
            df = pd.concat([df, newer[newer["ts"] > df["ts"].max()]])
        out[symbol] = df.reset_index(drop=True)
    return out


def _wilder_atr(df: pd.DataFrame) -> np.ndarray:
    """ATR14 on closed bars, as the historical rebuild calculates it."""
    prev_close = df["close"].shift(1)
    tr = pd.concat([df["high"] - df["low"], (df["high"] - prev_close).abs(),
                    (df["low"] - prev_close).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / 14, adjust=False).mean().to_numpy()


def build_panel(bars: dict[str, pd.DataFrame], cfg: AppConfig) -> dict:
    """The detector's view of each coin on each day, and the prices.

    ``coin_days`` has one row per (symbol, decision day D). The detector reads the 200
    bars that closed through D - 1, as ``book.closed_bar_fires`` does. Each row has the
    coin's MACD state on those bars, and the fire if there is one. The detector runs
    only on eligible coin-days (prior-day notional >= the scanner's volume floor), as
    in the rebuild. The panel starts on the first decision day with an eligible coin:
    before that day, Hyperliquid's candles have no volume.
    """
    lookback = cfg.candles.lookback_days
    floor = cfg.universe_filter.min_24h_volume_usd
    notional = {s: (df["volume"] * df["close"]).to_numpy() for s, df in bars.items()}
    decision = {s: (df["ts"] + pd.Timedelta(days=1)).dt.strftime("%Y-%m-%d").to_numpy()
                for s, df in bars.items()}
    first_day = min(decision[s][i] for s in bars for i in range(lookback - 1, len(bars[s]))
                    if notional[s][i] >= floor)
    rows = []
    for symbol, df in bars.items():
        m = macd(df["close"], cfg.macd.fast, cfg.macd.slow, cfg.macd.signal)
        hist, close, atr = m["hist"].to_numpy(), df["close"].to_numpy(), _wilder_atr(df)
        for i in range(lookback - 1, len(df)):
            if decision[symbol][i] < first_day or hist[i] == 0:
                continue
            window = m.iloc[i + 1 - lookback:i + 1]
            _, state_pct, _ = _peak_vs_history(window["hist"], "bullish" if hist[i] < 0 else "bearish")
            eligible = bool(notional[symbol][i] >= floor)
            sig = _check_histogram_flattening(symbol, float(close[i]), window, cfg) if eligible else None
            rows.append((symbol, decision[symbol][i], eligible, notional[symbol][i], hist[i], state_pct,
                         sig.direction if sig else None, sig.reduction_from_peak if sig else np.nan,
                         (sig.macd - sig.hist) / atr[i] if sig else np.nan))
    coin_days = pd.DataFrame(rows, columns=["symbol", "day", "eligible", "notional", "hist", "state_pct",
                                            "fire", "red", "sig_atr"])
    prices = pd.concat([pd.DataFrame({"symbol": s, "day": df["ts"].dt.strftime("%Y-%m-%d"), "open": df["open"],
                                      "high": df["high"], "close": df["close"]}) for s, df in bars.items()])
    return dict(coin_days=coin_days.sort_values(["day", "symbol"]).reset_index(drop=True),
                prices=prices.reset_index(drop=True), coins=len(bars),
                bars=(prices["day"].min(), prices["day"].max()),
                decision_days=(coin_days["day"].min(), coin_days["day"].max()))


def load_panel(path: Path) -> Panel:
    raw = pickle.loads(path.read_bytes())
    prices, coin_days = raw["prices"], raw["coin_days"]
    calendar = pd.date_range(prices["day"].min(), prices["day"].max(), freq="D").strftime("%Y-%m-%d")
    wide = {k: prices.pivot(index="day", columns="symbol", values=k).reindex(calendar)
            for k in ("open", "high", "close")}
    close = wide["close"]
    window = calendar[(calendar >= coin_days["day"].min()) & (calendar <= WINDOW_END.isoformat())]
    eligible = (coin_days[coin_days["eligible"]].pivot(index="day", columns="symbol", values="eligible")
                .reindex(index=window, columns=close.columns).notna().to_numpy())
    at = lambda df: df.loc[window].to_numpy()  # noqa: E731
    return Panel(meta={k: v for k, v in raw.items() if k not in ("prices", "coin_days")},
                 coin_days=coin_days, close=close, symbols=list(close.columns),
                 days=[date.fromisoformat(d) for d in window], ret=at(close / close.shift(1) - 1),
                 open=at(wide["open"]), high=at(wide["high"]), prev_close=at(close.shift(1)), eligible=eligible,
                 first_bar={s: date.fromisoformat(d) for s, d in prices.groupby("symbol")["day"].min().items()})


def with_low(panel: Panel, root: Path) -> Panel:
    """The panel with the low of each bar, from the CSVs of ``load_bars``. The frozen
    panel has no lows, and a resting buy order needs them.

    Stop if a close in the window is not the panel's close. Then the CSVs are not the
    bars of the panel, and the lows would come from other bars."""
    bars = load_bars(root)
    wide = {k: pd.DataFrame({s: df.set_index(df["ts"].dt.strftime("%Y-%m-%d"))[k] for s, df in bars.items()})
            for k in ("low", "close")}
    window = [d.isoformat() for d in panel.days]
    close = wide["close"].reindex(index=window, columns=panel.symbols).to_numpy()
    frozen = panel.close.loc[window].to_numpy()
    known = ~np.isnan(frozen)
    if not np.allclose(close[known], frozen[known], rtol=1e-9):
        raise ValueError(f"the bars in {root} are not the bars of the frozen panel")
    return replace(panel, low=wide["low"].reindex(index=window, columns=panel.symbols).to_numpy())


# ---------------------------------------------------------------- report

def summary(run: Run) -> dict:
    r = run.net
    lo, hi = sharpe_ci(r)
    return dict(sharpe=sharpe(r), lo=lo, hi=hi, cagr=cagr(r), max_dd=max_drawdown(r),
                years=period_returns(r, run.days, "year"), halves=period_returns(r, run.days, "half"),
                turnover=run.turnover.mean() * 365, longs=run.longs.mean(), shorts=run.shorts.mean(),
                cost=run.cost.mean() * 365, funding=run.funding.mean() * 365)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m macd_searcher.research.backtest", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cache", default="state/research_cache", help="the research cache (default %(default)s)")
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--rebuild", action="store_true", help="build the frozen panel again from the candle CSVs")
    args = ap.parse_args(argv)
    root = Path(args.cache)
    path = root / PANEL_FILE
    if args.rebuild:
        raw = build_panel(load_bars(root), load_config(args.config))
        raw["source"] = f"{(root / 'history').as_posix()}/*.csv + {(root / 'candles').as_posix()}/*.csv"
        raw["built"] = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        path.write_bytes(pickle.dumps(raw))
    elif not path.exists():
        print(f"No panel at {path}. Run with --rebuild to build it.", file=sys.stderr)
        return 1
    panel = load_panel(path)
    fires = book_fires(panel)
    s = summary(simulate(panel, fires))
    meta = panel.meta
    print(f"panel {path.as_posix()}, built {meta['built']} from {meta['source']}")
    print(f"panel bars {meta['bars'][0]} -> {meta['bars'][1]}, decision days {meta['decision_days'][0]} -> "
          f"{meta['decision_days'][1]}, {meta['coins']} coins")
    print(f"backtest window {panel.days[0]} -> {panel.days[-1]} ({len(panel.days)} days), {len(fires)} fires "
          f"({int(fires['first'].sum())} first fires)")
    print(f"B3: Sharpe {s['sharpe']:.3f} [{s['lo']:.2f}, {s['hi']:.2f}], CAGR {s['cagr'] * 100:+.2f}%, "
          f"max drawdown {s['max_dd'] * 100:.2f}%")
    print("years: " + " / ".join(f"{y} {v * 100:+.1f}%" for y, v in s["years"].items()))
    print("halves: " + " / ".join(f"{h} {v * 100:+.1f}%" for h, v in s["halves"].items()))
    print(f"turnover {s['turnover']:.0f}x a year; names {s['longs']:.1f} long / {s['shorts']:.1f} short; "
          f"costs {s['cost'] * 100:.1f}% and funding {s['funding'] * 100:.1f}% a year")
    return 0


if __name__ == "__main__":
    sys.exit(main())
