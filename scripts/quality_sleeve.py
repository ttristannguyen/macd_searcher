"""The quality sleeve of docs/strategy_search.md: a walk-forward model, as a market-neutral book.

    uv run --with scikit-learn python scripts/quality_sleeve.py
    uv run --with scikit-learn python scripts/quality_sleeve.py --placebo 30

The model is a research tool, so scikit-learn is not a project dependency. The book
goes through ``backtest.account``. The script uses the helpers of ``backtest_tables.py``.

* The features are known at the close before the decision day.
* The label is the rank of the 14-day excess over the same-day universe mean.
* Each month from 2024-01, the model trains on the rows whose label ended before that
  month. Thus each score is out of sample for the model.
* The settings are fixed. We did not tune them.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor

import backtest_tables as T
from macd_searcher.research import backtest as bt

HORIZON = 14
START = date(2024, 1, 1)
MIN_NOTIONAL = 2e6
# The book is the mean of six books, so that we do not select one after the first look.
GRID = ((0.10, 7), (0.10, 14), (0.15, 7), (0.15, 14), (0.20, 7), (0.20, 14))
BETA_DAYS = 60

P, DAYS, UNIVERSE = T.PANEL, T.DAYS, T.UNIVERSE
LISTED = P.listed
N_DAYS, N_COINS = P.ret.shape
FIRST_TEST = next(t for t, d in enumerate(DAYS) if d >= START)
FLOOR = T.NOTIONAL >= MIN_NOTIONAL


def lagged(frame: pd.DataFrame) -> np.ndarray:
    return T.lagged(frame).astype(float)


def rank_in_day(m: np.ndarray) -> np.ndarray:
    return pd.DataFrame(np.where(UNIVERSE, m, np.nan)).rank(axis=1, pct=True).to_numpy()


def features() -> np.ndarray:
    """The eight quality features: volatility, residual volatility, MAX, nearness to the
    high, size, listing age, illiquidity and beta. The ablation of the 2026-11-09 pass
    showed that the fires and the momentum add nothing to these."""
    ret, close = T.BAR_RET, P.close
    day_index = [d.isoformat() for d in DAYS]
    # T.NOTIONAL[t] is the notional of bar t - 1, so these two windows are already known at
    # the close before day t. Do not lag them again.
    notional = pd.DataFrame(T.NOTIONAL, index=day_index, columns=P.symbols)
    prior_move = ret.abs().shift(1).reindex(index=day_index, columns=P.symbols)
    size = np.log(notional.where(notional > 0)).rolling(30, min_periods=20).mean().to_numpy()
    amihud = (prior_move / notional).rolling(20, min_periods=15).mean().to_numpy()
    market = pd.Series(T.ALT_INDEX, index=day_index).reindex(ret.index).fillna(ret.mean(axis=1))
    beta = ret.rolling(60, min_periods=40).cov(market).div(market.rolling(60, min_periods=40).var(), axis=0)
    residual = ret.sub(beta.shift(1).mul(market, axis=0))
    age = np.array([[(d - P.first_bar[s]).days for s in P.symbols] for d in DAYS], dtype=float)
    mats = [lagged(ret.rolling(30, min_periods=20).std()), lagged(residual.rolling(30, min_periods=20).std()),
            lagged(ret.rolling(30, min_periods=20).max()), lagged(close / close.rolling(180, min_periods=120).max()),
            size, age, amihud, lagged(beta)]
    return np.stack([rank_in_day(m) for m in mats], axis=2)


def forward_excess() -> np.ndarray:
    fwd = np.full((N_DAYS, N_COINS), np.nan)
    for t in range(N_DAYS - HORIZON):
        fwd[t] = np.prod(1 + np.nan_to_num(P.ret[t:t + HORIZON + 1]), axis=0) - 1
    fwd = np.where(UNIVERSE, fwd, np.nan)
    return fwd - np.nanmean(fwd, axis=1, keepdims=True)


def walk_forward(x: np.ndarray, labels: np.ndarray) -> np.ndarray:
    row, col = np.where(UNIVERSE)
    xs, ys = x[row, col], labels[row, col]
    score = np.full((N_DAYS, N_COINS), np.nan)
    for month in sorted({(d.year, d.month) for d in DAYS if d >= START}):
        test_days = [t for t, d in enumerate(DAYS) if (d.year, d.month) == month]
        train = (row + HORIZON < test_days[0]) & ~np.isnan(ys)
        model = HistGradientBoostingRegressor(max_depth=3, learning_rate=0.05, max_iter=200, min_samples_leaf=300,
                                              l2_regularization=1.0, random_state=0).fit(xs[train], ys[train])
        test = np.isin(row, test_days)
        score[row[test], col[test]] = model.predict(xs[test])
    return score


def side_weights(score: np.ndarray, q: float) -> np.ndarray:
    """B3's sizing on the top and the bottom ``q`` of the coins above the floor."""
    rank = pd.DataFrame(np.where(UNIVERSE & FLOOR, score, np.nan)).rank(axis=1, pct=True).to_numpy()
    long_, short = rank >= 1 - q, rank <= q
    n_long, n_short = long_.sum(1).astype(float), short.sum(1).astype(float)
    gross = np.minimum(1.0, bt.MAX_WEIGHT * np.minimum(n_long, n_short))
    w_long = np.divide(gross, n_long, out=np.zeros(N_DAYS), where=n_long > 0)
    w_short = np.divide(gross, n_short, out=np.zeros(N_DAYS), where=n_short > 0)
    return long_ * w_long[:, None] - short * w_short[:, None]


def book(score: np.ndarray) -> np.ndarray:
    """The mean of the grid books. A book of hold H is the mean of its last H daily books."""
    grid = [pd.DataFrame(side_weights(score, q)).rolling(h, min_periods=1).mean().to_numpy() for q, h in GRID]
    return _beta_hedged(np.where(LISTED, np.mean(grid, axis=0), 0.0))


def _beta_hedged(w: np.ndarray) -> np.ndarray:
    """Remove the book's trailing beta to the coins above the floor with a basket of them.
    Low-volatility longs against high-volatility shorts are net short the market."""
    member = FLOOR & UNIVERSE
    market = pd.Series(np.nanmean(np.where(member, P.ret, np.nan), axis=1))
    gross = pd.Series(bt.account(w, P.ret)["gross"])
    beta = (gross.rolling(BETA_DAYS, min_periods=30).cov(market) / market.rolling(BETA_DAYS, min_periods=30).var())
    beta = beta.shift(1).fillna(0).clip(-1, 1).to_numpy()
    return w - beta[:, None] * member / np.maximum(member.sum(1)[:, None], 1)


def net(w: np.ndarray) -> np.ndarray:
    return bt.account(np.where(LISTED, w, 0.0), P.ret)["net"]


def report(name: str, r: np.ndarray, base: np.ndarray) -> str:
    s, b = r[FIRST_TEST:], base[FIRST_TEST:]
    d, lo, hi = bt.sharpe_diff_ci(b, s)
    return (f"| {name} | {bt.sharpe(s):.2f} | {d:+.2f} [{lo:+.2f}, {hi:+.2f}] | {bt.sharpe(r[FIRST_TEST:T.SPLIT]):.2f} "
            f"| {bt.sharpe(r[T.SPLIT:]):.2f} | {bt.cagr(s) * 100:+.1f}% | {bt.max_drawdown(s) * 100:.0f}% |")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--placebo", type=int, default=0, help="the number of runs with permuted labels")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")         # the tables use → and –
    x, excess = features(), forward_excess()
    labels = pd.DataFrame(excess).rank(axis=1, pct=True).to_numpy().copy()
    sleeve = book(walk_forward(x, labels))
    stack = T.run(**T.STACK).weights

    print(f"window {DAYS[FIRST_TEST]} → {DAYS[-1]}")
    print("| book | Sharpe | Δ vs B3 [95%] | 2024 | 2025–26 | CAGR | max DD |")
    print("|---|---|---|---|---|---|---|")
    b3 = T.BASE.net
    for name, r in (("B3", b3), ("the quality sleeve alone", net(sleeve)), ("the stack", net(stack)),
                    ("75% B3 + 25% sleeve", net(0.75 * T.BASE.weights + 0.25 * sleeve)),
                    ("75% stack + 25% sleeve", net(0.75 * stack + 0.25 * sleeve))):
        print(report(name, r, b3))

    results = []
    for seed in range(args.placebo):
        rng, shuffled = np.random.default_rng(seed), labels.copy()
        for t in range(N_DAYS):
            ok = ~np.isnan(shuffled[t])
            shuffled[t, ok] = rng.permutation(shuffled[t, ok])
        results.append(bt.sharpe(net(book(walk_forward(x, shuffled)))[FIRST_TEST:]))
    if results:
        a = np.array(results)
        real = bt.sharpe(net(sleeve)[FIRST_TEST:])
        print(f"\nplacebo, {len(a)} runs: mean {a.mean():+.2f}, sd {a.std():.2f}, max {a.max():+.2f}; "
              f"share at or above the real {real:.2f}: {(a >= real).mean():.3f}")


if __name__ == "__main__":
    main()
