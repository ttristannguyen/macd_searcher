"""The portfolio tables of the docs, from the committed backtester.

    uv run python scripts/backtest_tables.py > tables.md

Each section prints the tables of one doc: profit_strategies.md, trading_strategy.md,
exit_research.md and book_experiments.md. The rules of the book come from
``research/backtest.py``. This script only makes the variants: other fires, other
baskets, exit rules, and weights that a rejected idea changes. Each paired interval
uses the same 30-day blocks for both books.
"""

from __future__ import annotations

import pickle
import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from macd_searcher.book import LEGS
from macd_searcher.config import load_config
from macd_searcher.research import backtest as bt
from macd_searcher.research.dataset import DEEP_DIP_PCT
from macd_searcher.signals import CONFIDENCE_V3_MAX_PEAK_PCT, CONFIDENCE_V3_MAX_REDUCTION
from macd_searcher.stats import episodes

PANEL = bt.load_panel(Path("state/research_cache") / bt.PANEL_FILE)
FIRES = bt.book_fires(PANEL)
DAYS = PANEL.days
COL = {s: j for j, s in enumerate(PANEL.symbols)}
SPLIT = DAYS.index(date(2025, 1, 1))          # 2023-24 against 2025-26
UNIVERSE = PANEL.universe
SHORTS_21 = {"S1": 21, "S2": 21}


def run(fires: pd.DataFrame = FIRES, **kw) -> bt.Run:
    return bt.simulate(PANEL, fires, **kw)


BASE = run()


# ---------------------------------------------------------------- format

def num(x: float, fmt: str) -> str:
    return format(x, fmt).replace("-", "−")


def pct(x: float, digits: int = 1) -> str:
    return num(x * 100, f"+.{digits}f") + "%"


def years(r: np.ndarray) -> str:
    return " / ".join(num(v * 100, "+.0f") for v in bt.period_returns(r, DAYS, "year"))


def sharpe_with_ci(r: np.ndarray) -> str:
    lo, hi = bt.sharpe_ci(r)
    return f"{num(bt.sharpe(r), '.2f')} [{num(lo, '.2f')}, {num(hi, '.2f')}]"


def half_sharpes(r: np.ndarray) -> tuple[float, float]:
    return bt.sharpe(r[:SPLIT]), bt.sharpe(r[SPLIT:])


def paired(base: np.ndarray, variant: np.ndarray) -> str:
    """Δ Sharpe [95%] | Δ 2023-24 | Δ 2025-26."""
    d, lo, hi = bt.sharpe_diff_ci(base, variant)
    (b1, b2), (v1, v2) = half_sharpes(base), half_sharpes(variant)
    return f"{num(d, '+.2f')} [{num(lo, '+.2f')}, {num(hi, '+.2f')}] | {num(v1 - b1, '+.2f')} | {num(v2 - b2, '+.2f')}"


def book_row(name: str, r: np.ndarray) -> str:
    """| name | CAGR | Sharpe [95%] | max DD | by year |"""
    return f"| {name} | {pct(bt.cagr(r))} | {sharpe_with_ci(r)} | {pct(bt.max_drawdown(r), 0)} | {years(r)} |"


def variant_row(name: str, base: bt.Run, v: bt.Run, extra: str = "") -> str:
    """| name | Sharpe | Δ [95%] | Δ 2023-24 | Δ 2025-26 | CAGR | max DD | (extra) |"""
    return (f"| {name} | {num(bt.sharpe(v.net), '.2f')} | {paired(base.net, v.net)} | {pct(bt.cagr(v.net))} "
            f"| {pct(bt.max_drawdown(v.net), 0)} |" + (f" {extra} |" if extra else ""))


def turnover_change(base: bt.Run, v: bt.Run) -> str:
    return num(v.turnover.mean() / base.turnover.mean() * 100 - 100, "+.0f") + "%"


def names(v: bt.Run) -> str:
    return f"{v.longs.mean():.0f} / {v.shorts.mean():.0f}"


def header(title: str, *cols: str) -> None:
    print(f"\n### {title}\n")
    print("| " + " | ".join(cols) + " |")
    print("|" + "---|" * len(cols))


# ---------------------------------------------------------------- fires and baskets

def legs(*names: str) -> pd.DataFrame:
    return FIRES[FIRES["leg"].isin(names)]


def relabel(f: pd.DataFrame, leg: str, side: int) -> pd.DataFrame:
    return f.assign(leg=leg, side=side)


BULL = FIRES["fire"] == "bullish"
V3 = relabel(FIRES[BULL & (FIRES["peak_pct"] <= CONFIDENCE_V3_MAX_PEAK_PCT)
                   & (FIRES["red"] < CONFIDENCE_V3_MAX_REDUCTION)], "v3", 1)
DEEP = relabel(FIRES[BULL & (FIRES["peak_pct"] > 50)], "deep", -1)     # every bullish peak_pct > 50, records too
ALL_BULL = relabel(FIRES[BULL], "bull", 1)
PULLBACK_SIG = legs("L2")[legs("L2")["sig_atr"] >= 0.5]
LONGS = legs("L1", "L2")


def coin_matrix(column: str) -> np.ndarray:
    cd = PANEL.coin_days
    wide = cd.pivot(index="day", columns="symbol", values=column)
    return wide.reindex(index=[d.isoformat() for d in DAYS], columns=PANEL.symbols).to_numpy(dtype=float)


NOTIONAL = coin_matrix("notional")      # prior-day notional of each coin on each decision day
RANK = pd.DataFrame(np.where(UNIVERSE, NOTIONAL, np.nan)).rank(axis=1, ascending=False).to_numpy()


def random_weekly(n: int = 20, seed: int = 0) -> np.ndarray:
    """``n`` universe coins drawn on the first day of each ISO week and kept for that week."""
    rng = np.random.default_rng(seed)
    mask = np.zeros_like(UNIVERSE)
    week, chosen = None, np.array([], dtype=int)
    for t, d in enumerate(DAYS):
        if d.isocalendar()[:2] != week:
            week, pool = d.isocalendar()[:2], np.flatnonzero(UNIVERSE[t])
            chosen = rng.choice(pool, size=min(n, len(pool)), replace=False)
        mask[t, chosen] = UNIVERSE[t, chosen]
    return mask


BTC_ONLY = np.zeros_like(UNIVERSE)
BTC_ONLY[:, COL["BTC"]] = True


# ---------------------------------------------------------------- market series

RET = np.where(UNIVERSE, PANEL.ret, np.nan)
ALT_INDEX = np.nanmean(RET, axis=1)             # the universe is never empty in the window
BTC_RET = PANEL.ret[:, COL["BTC"]]


def btc_weights(on: np.ndarray) -> np.ndarray:
    w = np.zeros_like(PANEL.ret)
    w[:, COL["BTC"]] = on
    return w


def btc_trend(n: int) -> np.ndarray:
    """1 on a decision day when BTC's prior close is above its n-day SMA, else 0."""
    close = PANEL.close["BTC"]
    above = (close > close.rolling(n).mean()).astype(float)
    return above.shift(1).reindex([d.isoformat() for d in DAYS]).to_numpy()


def reweighted(weights: np.ndarray, base: bt.Run = BASE) -> bt.Run:
    """A book that holds other daily weights. The coin returns, costs and funding stay
    those of ``base``."""
    acc = bt.account(weights, base.ret)
    return bt.Run(DAYS, acc["weights"], base.ret, acc["net"], acc["gross"], acc["cost"], acc["funding"],
                  acc["turnover"], base.longs, base.shorts)


def with_weights(weights: np.ndarray, base: bt.Run = BASE) -> np.ndarray:
    return reweighted(weights, base).net


# ---------------------------------------------------------------- profit_strategies.md

def profit_strategies() -> None:
    print("\n## profit_strategies.md")
    b2 = run(LONGS, basket=UNIVERSE)
    b1 = run(V3, basket=UNIVERSE, holds={"v3": 7})
    sleeve = {n: btc_trend(n) for n in (20, 50, 100, 200)}
    btc_perp = with_weights(btc_weights(np.ones(len(DAYS))))

    header("Menu", "#", "strategy", "CAGR", "Sharpe [95%]", "max DD", "by year")
    rows = [("—", "BTC buy & hold, price only *(reference)*", BTC_RET),
            ("—", "equal-weight alt universe, price only *(reference)*", ALT_INDEX),
            ("A2", "B2 at 2x leverage", with_weights(2 * b2.weights, b2)),
            ("A3", "BTC perp 1x + B3", with_weights(BASE.weights + btc_weights(np.ones(len(DAYS))))),
            ("B1", "v3 bullish 7d, universe-hedged", b1.net),
            ("B2", "good fires 14d, universe-hedged", b2.net),
            ("B3", "good fires long / bad fires short, 14d", BASE.net),
            ("B4", "BTC > SMA50 + B3", with_weights(BASE.weights + btc_weights(sleeve[50]))),
            ("C1", "BTC > SMA50 trend, alone", with_weights(btc_weights(sleeve[50])))]
    for k, name, r in rows:
        print(book_row(f"{k} | {name}", r))

    header("A2: B2 with leverage", "leverage", "CAGR", "max DD", "worst year")
    for lev in (1, 2, 3, 4):
        r = with_weights(lev * b2.weights, b2)
        y = bt.period_returns(r, DAYS, "year")
        print(f"| {lev}x | {pct(bt.cagr(r))} | {pct(bt.max_drawdown(r), 0)} | {y.idxmin()} {pct(y.min(), 0)} |")
    kelly = b2.net.mean() / b2.net.var()
    print(f"\nKelly from B2: full {kelly:.1f}x; half-Kelly at half the Sharpe {kelly / 4:.1f}x")

    header("A3: BTC plus a neutral overlay", "", "CAGR", "Sharpe [95%]", "max DD", "by year")
    print(book_row("BTC perp 1x", btc_perp))
    for name, book in (("B2", b2), ("B3", BASE), ("B1", b1)):
        print(book_row(f"BTC perp 1x + {name}", with_weights(book.weights + btc_weights(np.ones(len(DAYS))), book)))
    print(f"\ncorrelation with BTC: B2 {np.corrcoef(b2.net, BTC_RET)[0, 1]:+.2f}, "
          f"B3 {np.corrcoef(BASE.net, BTC_RET)[0, 1]:+.2f}, B1 {np.corrcoef(b1.net, BTC_RET)[0, 1]:+.2f}")

    header("B1/B2: universe-hedged books", "book", "CAGR", "vol", "Sharpe [95%]",
           "Sharpe before costs and funding", "max DD", "turnover a year")
    hedged = [("all bullish, 7d", ALL_BULL, {"bull": 7}), ("v3 bullish, 7d", V3, {"v3": 7}),
              ("v3 bullish, 14d", V3, None), ("bullish `peak_pct ≤ 25` (L1), 14d", legs("L1"), None),
              ("bearish pullback (L2, long), 14d", legs("L2"), None),
              ("bearish pullback + sig ≥ 0.5, 7d", PULLBACK_SIG, {"L2": 7}),
              ("good fires combined, 14d (B2)", LONGS, None)]
    betas = []
    for name, f, holds in hedged:
        v = run(f, basket=UNIVERSE, holds=holds)
        r = v.net
        print(f"| {name} | {pct(bt.cagr(r))} | {r.std() * np.sqrt(365) * 100:.0f}% | {sharpe_with_ci(r)} "
              f"| {num(bt.sharpe(v.gross), '.2f')} | {pct(bt.max_drawdown(r), 0)} | {v.turnover.mean() * 365:.0f}x |")
        for y in (2023, 2024, 2025, 2026):
            m = np.array([d.year == y for d in DAYS])
            betas.append(np.polyfit(ALT_INDEX[m], r[m], 1)[0])
    print(f"\ndaily beta to the alt index, every book and year: {min(betas):+.2f} to {max(betas):+.2f}")

    header("B2: the hedge decides", "short leg", "CAGR", "Sharpe", "2024")
    hedges = [("equal-weight eligible universe", UNIVERSE),
              ("coins ranked 21+ by prior-day volume", UNIVERSE & (RANK > 20)),
              ("20 random eligible coins, redrawn weekly", random_weekly()),
              ("top 20 by prior-day volume", UNIVERSE & (RANK <= 20)),
              ("BTC", BTC_ONLY)]
    for name, mask in hedges:
        r = run(LONGS, basket=mask).net
        print(f"| {name} | {pct(bt.cagr(r))} | {num(bt.sharpe(r), '.2f')} "
              f"| {pct(bt.period_returns(r, DAYS, 'year')['2024'], 0)} |")
    top20 = np.nanmean(np.where(UNIVERSE & (RANK <= 20), PANEL.ret, np.nan), axis=1)
    print(f"\nprice only, a year: top 20 {pct(bt.cagr(top20))}, BTC {pct(bt.cagr(BTC_RET))}, "
          f"alt universe {pct(bt.cagr(ALT_INDEX))}")

    header("B3: the short leg", "short leg", "CAGR", "Sharpe [95%]", "max DD", "by year")
    print(book_row("bearish `peak_pct ≤ 25` (S1 only)", run(legs("L1", "L2", "S1")).net))
    print(book_row("bullish `50 < peak_pct < 100` (S2 only)", run(legs("L1", "L2", "S2")).net))
    print(book_row("both (B3)", BASE.net))
    print(f"\nB3 correlation: BTC {np.corrcoef(BASE.net, BTC_RET)[0, 1]:+.2f}, alt index "
          f"{np.corrcoef(BASE.net, ALT_INDEX)[0, 1]:+.2f}, B2 {np.corrcoef(BASE.net, b2.net)[0, 1]:+.2f}")

    header("B3 robustness", "variant", "Sharpe")
    hold = {h: bt.sharpe(run(holds={leg: h for leg in LEGS}).net) for h in (7, 14, 21)}
    print(f"| hold 7 / 14 / 21 days | {' / '.join(num(v, '.2f') for v in hold.values())} |")
    print(f"| all fires (every traded fire restarts the clock) | {num(bt.sharpe(run(first_only=False).net), '.2f')} |")
    floors = [bt.sharpe(run(FIRES[FIRES["notional"] >= x]).net) for x in (2e6, 10e6, 50e6)]
    print(f"| only coins with ≥ $2M / $10M / $50M prior-day volume | {' / '.join(num(v, '.2f') for v in floors)} |")
    costs = [bt.sharpe(run(cost=c).net) for c in (0, 0.0005, 0.001, 0.002)]
    print(f"| cost 0 / 0.05 / 0.10 / 0.20% per side | {' / '.join(num(v, '.2f') for v in costs)} |")
    halves = bt.period_returns(BASE.net, DAYS, "half")
    print(f"| half-years {halves.index[0]} → {halves.index[-1]} (return) | "
          f"{' / '.join(num(v * 100, '+.0f') for v in halves)}% |")
    oos = run(pd.concat([V3, DEEP]), holds={"v3": 7, "deep": 7})
    print(f"| the out-of-sample version: v3 bullish long / bullish `peak_pct > 50` short, 7d "
          f"| {sharpe_with_ci(oos.net)} |")

    header("When B3 works: months by the alt index's prior 90-day move", "regime at month start", "months",
           "B2 mean / % positive", "B3 mean / % positive")
    level = np.cumprod(1 + ALT_INDEX)
    month = pd.Series([f"{d.year}-{d.month:02d}" for d in DAYS])
    starts = month.drop_duplicates()
    move = {m: level[t - 1] / level[t - 91] - 1 for t, m in starts.items() if t >= 91}
    gross = {k: bt.period_returns(v.gross, DAYS, "month") for k, v in (("B2", b2), ("B3", BASE))}
    regime = pd.Series({m: "down" if x < -0.2 else "up" if x > 0.2 else "between" for m, x in move.items()})
    for label, key in (("alt index down > 20%", "down"), ("in between", "between"), ("alt index up > 20%", "up")):
        ms = regime.index[regime == key]
        cells = [f"{pct(gross[k][ms].mean())} / {(gross[k][ms] > 0).mean() * 100:.0f}%" for k in ("B2", "B3")]
        print(f"| {label} | {len(ms)} | {cells[0]} | {cells[1]} |")
    disp = pd.Series(np.nanstd(RET, axis=1)).groupby(month).mean()
    high = disp > disp.median()
    print(f"\nB3 gross a month, high / low cross-sectional dispersion: {pct(gross['B3'][high].mean())} / "
          f"{pct(gross['B3'][~high].mean())}")
    h = bt.period_returns(ALT_INDEX, DAYS, "half")
    print(f"2023H2: alt index {pct(h['2023H2'], 0)}, B3 {pct(halves['2023H2'], 0)}")

    header("B4: BTC trend + B3", "", "CAGR", "Sharpe [95%]", "max DD", "by year")
    for n in (50, 100, 200):
        print(book_row(f"BTC > SMA{n} + B3", with_weights(BASE.weights + btc_weights(sleeve[n]))))
    print(book_row("BTC > SMA50 + B1 (out-of-sample rule)", with_weights(b1.weights + btc_weights(sleeve[50]), b1)))
    print(f"\ncorrelation of the SMA50 sleeve with B3: "
          f"{np.corrcoef(with_weights(btc_weights(sleeve[50])), BASE.net)[0, 1]:+.2f}")

    header("C1: BTC trend-following alone", "N", "CAGR", "Sharpe", "max DD", "time in market", "switches a year")
    for n, on in sleeve.items():
        r = with_weights(btc_weights(on))
        print(f"| {n} | {pct(bt.cagr(r))} | {num(bt.sharpe(r), '.2f')} | {pct(bt.max_drawdown(r), 0)} "
              f"| {on.mean() * 100:.0f}% | {np.abs(np.diff(on)).sum() / len(on) * 365:.0f} |")

    print("\nC5: B2 Sharpe by hold 7 / 10 / 14 / 21 / 30: " + " / ".join(
        num(bt.sharpe(run(LONGS, basket=UNIVERSE, holds={"L1": h, "L2": h}).net), ".2f") for h in (7, 10, 14, 21, 30)))

    bear = FIRES["fire"] == "bearish"
    c2 = [("bearish `peak_pct ≤ 25` (S1), 7d", legs("S1"), {"S1": 7}),
          ("bullish `peak_pct ≥ 75`, 7d", relabel(FIRES[BULL & (FIRES["peak_pct"] >= 75)], "deep", -1), {"deep": 7}),
          ("all bearish fires, 7d", relabel(FIRES[bear], "bear", -1), {"bear": 7})]
    print("\nC2: short books, universe-hedged long: " + "; ".join(
        f"{name} {num(bt.sharpe(run(f, basket=UNIVERSE, holds=holds).net), '.2f')}" for name, f, holds in c2))

    header("C6a: failed-cross exit, universe-hedged", "book", "no exit", "k = 2", "k = 3", "k = 4", "k = 5", "k = 7")
    for name, f, leg, hold in (("v3 bullish, 7d", V3, "v3", 7), ("v3 bullish, 14d", V3, "v3", 14),
                               ("`peak_pct ≤ 25`, 7d", legs("L1"), "L1", 7),
                               ("`peak_pct ≤ 25`, 14d", legs("L1"), "L1", 14)):
        cells = []
        for k in (None, 2, 3, 4, 5, 7):
            if k is not None and k >= hold:
                cells.append("—")
                continue
            v = run(f, basket=UNIVERSE, holds={leg: hold}, exit_rule=failed_cross(k) if k else None)
            cells.append(f"{num(bt.sharpe(v.net), '.2f')} ({pct(bt.cagr(v.net))}, {v.longs.mean():.1f} names)")
        print(f"| {name} | " + " | ".join(cells) + " |")


# ---------------------------------------------------------------- trading_strategy.md

def state_triggers(leg: str, side: int, in_state: pd.Series) -> pd.DataFrame:
    """A trigger on each eligible coin-day that enters the state (a new run of state days)."""
    cd = PANEL.coin_days
    s = cd[cd["eligible"] & in_state].copy()
    _, s["first"] = episodes(s["symbol"].tolist(), [leg] * len(s), s["day"].tolist())
    return s[s["first"]].assign(leg=leg, side=side)


def trading_strategy() -> None:
    print("\n## trading_strategy.md")
    s = bt.summary(BASE)
    gross_year = BASE.gross.mean() * 365
    print(f"\nB3: Sharpe {sharpe_with_ci(BASE.net)}, CAGR {pct(s['cagr'])}, max DD {pct(s['max_dd'], 0)}, "
          f"vol {BASE.net.std() * np.sqrt(365) * 100:.1f}%")
    print(f"costs {pct(s['cost'])} and funding {pct(s['funding'])} a year, against a gross return of "
          f"{pct(gross_year)} a year (costs = {s['cost'] / gross_year * 100:.0f}% of gross)")
    print(f"turnover {s['turnover']:.0f}x a year, names {s['longs']:.1f} long / {s['shorts']:.1f} short")
    print(f"first fires {bt.sharpe(BASE.net):.2f} against all fires {bt.sharpe(run(first_only=False).net):.2f}")
    cd = PANEL.coin_days
    s2_state = (cd["hist"] < 0) & (cd["state_pct"] > 50) & (cd["state_pct"] < 100)
    as_state = run(pd.concat([legs("L1", "L2", "S1"), state_triggers("S2", -1, s2_state)]))
    print(f"S2: B3 without S2 {bt.sharpe(run(legs('L1', 'L2', 'S1')).net):.2f}, without S1 "
          f"{bt.sharpe(run(legs('L1', 'L2', 'S2')).net):.2f}")
    print(f"S2 traded as the MACD state on any eligible coin: Sharpe {bt.sharpe(as_state.net):.2f}, "
          f"Δ [95%] | Δ 2023–24 | Δ 2025–26 = {paired(BASE.net, as_state.net)}, names {names(as_state)} "
          f"against {names(BASE)}")
    kelly = BASE.net.mean() / BASE.net.var()
    print(f"Kelly from B3: full {kelly:.1f}x; half-Kelly at half the Sharpe {kelly / 4:.1f}x")


# ---------------------------------------------------------------- exit_research.md

STATE = {(r.symbol, r.day): (r.hist, r.state_pct) for r in PANEL.coin_days.itertuples()}


def adverse_state(exit_legs: tuple[str, ...]):
    """Exit when the coin's closed-bar state keeps going against the trade: a long whose
    coin is in a deep dip, or a short whose coin is in a strong rally (state peak_pct >= 75)."""
    def rule(day: date, p: bt.Position) -> bool:
        hist, pct_ = STATE.get((p.symbol, day.isoformat()), (0.0, None))
        return (p.leg in exit_legs and pct_ is not None and pct_ >= DEEP_DIP_PCT
                and (hist < 0 if p.side > 0 else hist > 0))
    return rule


def side_gross(v: bt.Run) -> float:
    return np.abs(v.weights).sum(axis=1).mean() / 2


def failed_cross(k: int):
    """Close a long at the close of bar k when the histogram has not crossed zero on any
    of the first k closes (profit_strategies.md C6a). Bar i is the close of fire day +
    i - 1, and the panel row of the next day holds it."""
    def rule(day: date, p: bt.Position) -> bool:
        if (day - p.entry).days != k:
            return False
        bars = [STATE.get((p.symbol, (p.entry + timedelta(days=i)).isoformat()), (np.nan, None))[0]
                for i in range(1, k + 1)]
        return not any(h >= 0 for h in bars)
    return rule


def exit_research() -> None:
    print("\n## exit_research.md")
    header("§4: as portfolios", "book", "Sharpe", "Δ vs baseline [95%]", "Δ 2023–24", "Δ 2025–26", "CAGR", "max DD",
           "turnover")
    print(f"| baseline: every leg 14 days | {num(bt.sharpe(BASE.net), '.2f')} | — | — | — | {pct(bt.cagr(BASE.net))} "
          f"| {pct(bt.max_drawdown(BASE.net), 0)} | — |")
    variants = [("every leg 7 days", dict(holds={leg: 7 for leg in LEGS})),
                ("every leg 21 days", dict(holds={leg: 21 for leg in LEGS})),
                ("L2 7 days, rest 14", dict(holds={"L2": 7})),
                ("shorts 21 days, longs 14", dict(holds=SHORTS_21)),
                ("L2 7, L1 14, shorts 21", dict(holds={"L2": 7, **SHORTS_21})),
                ("+ adverse-state exit (L2, S2)", dict(exit_rule=adverse_state(("L2", "S2")))),
                ("+ adverse-state exit (all legs)", dict(exit_rule=adverse_state(LEGS))),
                ("shorts 21 + adverse-state exit (all legs)", dict(holds=SHORTS_21, exit_rule=adverse_state(LEGS))),
                ("+ short tail stop at +30%", dict(short_stop=0.3)),
                ("+ short tail stop at +50%", dict(short_stop=0.5)),
                ("+ short tail stop at +100%", dict(short_stop=1.0))]
    for name, kw in variants:
        v = run(**kw)
        print(variant_row(name, BASE, v, turnover_change(BASE, v)))

    header("§5: holding the shorts 21 days", "check", "baseline", "shorts 21", "Δ [95% paired]")
    grid = {h: run(holds={"S1": h, "S2": h}) for h in (10, 14, 17, 21, 25, 30)}
    print("| short hold 10 / 14 / 17 / 21 / 25 / 30 days | | "
          + " / ".join(num(bt.sharpe(v.net), ".2f") for v in grid.values()) + " | "
          + " / ".join(num(bt.sharpe(v.net) - bt.sharpe(BASE.net), "+.2f") for v in grid.values()) + " |")
    for name, kw in (("cost 0.05% a side", dict(cost=0.0005)), ("cost 0.20% a side", dict(cost=0.002)),
                     ("all fires (re-fires restart the clock)", dict(first_only=False))):
        b, v = run(**kw), run(holds=SHORTS_21, **kw)
        d, lo, hi = bt.sharpe_diff_ci(b.net, v.net)
        print(f"| {name} | {num(bt.sharpe(b.net), '.2f')} | {num(bt.sharpe(v.net), '.2f')} "
              f"| {num(d, '+.2f')} [{num(lo, '+.2f')}, {num(hi, '+.2f')}] |")
    for name, holds in (("S1 alone to 21 days", {"S1": 21}), ("S2 alone to 21 days", {"S2": 21})):
        v = run(holds=holds)
        d, lo, hi = bt.sharpe_diff_ci(BASE.net, v.net)
        print(f"| {name} | {num(bt.sharpe(BASE.net), '.2f')} | {num(bt.sharpe(v.net), '.2f')} "
              f"| {num(d, '+.2f')} [{num(lo, '+.2f')}, {num(hi, '+.2f')}] |")
    s21 = grid[21]
    hb, hv = bt.period_returns(BASE.net, DAYS, "half"), bt.period_returns(s21.net, DAYS, "half")
    print(f"| half-years {hb.index[0]} → {hb.index[-1]} (return, pts) | | | "
          + " / ".join(num((hv[k] - hb[k]) * 100, "+.1f") for k in hb.index) + " |")
    base1, base2 = half_sharpes(BASE.net)
    print("\nshort-hold grid, Δ by half (2023–24 / 2025–26): " + ", ".join(
        f"{h}d {num(half_sharpes(v.net)[0] - base1, '+.2f')} / {num(half_sharpes(v.net)[1] - base2, '+.2f')}"
        for h, v in grid.items()))
    print(f"side gross {side_gross(BASE):.2f} -> {side_gross(s21):.2f}; vol {BASE.net.std() * np.sqrt(365) * 100:.1f}% -> "
          f"{s21.net.std() * np.sqrt(365) * 100:.1f}%; names {names(BASE)} -> {names(s21)}; "
          f"CAGR {pct(bt.cagr(BASE.net))} -> {pct(bt.cagr(s21.net))}; max DD {pct(bt.max_drawdown(BASE.net), 0)} -> "
          f"{pct(bt.max_drawdown(s21.net), 0)}; half-years better {(hv > hb).sum()} of {len(hb)}")


# ---------------------------------------------------------------- book_experiments.md

def lagged(frame: pd.DataFrame) -> np.ndarray:
    """A value per coin known at the close before each decision day."""
    return frame.shift(1).reindex([d.isoformat() for d in DAYS]).reindex(columns=PANEL.symbols).to_numpy()


BAR_RET = PANEL.close / PANEL.close.shift(1) - 1
VOL20 = lagged(BAR_RET.rolling(20, min_periods=15).std())
ROW = {d: t for t, d in enumerate(DAYS)}


def inverse_vol(power: float):
    def tilt(day: date, p: bt.Position) -> float:
        row = VOL20[ROW[day]]
        v = row[COL[p.symbol]]
        return 1 / (v if v > 0 else np.nanmedian(row)) ** power
    return tilt


def beta_neutral(weights: np.ndarray) -> np.ndarray:
    universe_mean = pd.Series(ALT_INDEX, index=[d.isoformat() for d in DAYS]).reindex(BAR_RET.index)
    beta = lagged(BAR_RET.rolling(60, min_periods=40).cov(universe_mean).div(
        universe_mean.rolling(60, min_periods=40).var(), axis=0))
    beta = np.nan_to_num(beta, nan=1.0)
    out = weights.copy()
    for t in range(len(out)):
        w, b = out[t], beta[t]
        long_beta, short_beta = (w[w > 0] * b[w > 0]).sum(), (-w[w < 0] * b[w < 0]).sum()
        if short_beta > 0:
            w[w < 0] *= long_beta / short_beta
    return out


def vol_target(lookback: int, cap: float) -> np.ndarray:
    """A daily scale for the whole book: the expanding median of the book's trailing
    volatility over its current trailing volatility, known at the close before."""
    vol = pd.Series(BASE.net).rolling(lookback, min_periods=lookback // 2).std().shift(1)
    k = (vol.expanding().median() / vol).clip(0, cap)
    return k.fillna(1.0).to_numpy()


def equity_filter(lookback: int = 60) -> np.ndarray:
    trailing = pd.Series(BASE.net).rolling(lookback).sum().shift(1)
    return np.where(trailing.isna() | (trailing > 0), 1.0, 0.0)


AGE_START = date(2021, 1, 1)        # the first day of history/: older listings show this date


def age_tilt(k: float, longs: bool = True, shorts: bool = True, pre_2021: bool = True):
    """k x weight on longs listed 2+ years and on shorts listed under 1 year at entry."""
    def tilt(day: date, p: bt.Position) -> float:
        first = PANEL.first_bar[p.symbol]
        age = (p.entry - first).days
        old = age >= 730 and (pre_2021 or first > AGE_START)
        return k if (p.side > 0 and longs and old) or (p.side < 0 and shorts and age < 365) else 1.0
    return tilt


def book_experiments() -> None:
    print("\n## book_experiments.md")
    header("§1: position size and risk control", "variant", "Sharpe", "Δ vs baseline [95%]", "Δ 2023–24",
           "Δ 2025–26", "CAGR", "max DD", "turnover")
    print(f"| **baseline** | {num(bt.sharpe(BASE.net), '.2f')} | — | — | — | {pct(bt.cagr(BASE.net))} "
          f"| {pct(bt.max_drawdown(BASE.net), 0)} | — |")
    scaled = lambda k: reweighted(BASE.weights * k[:, None])  # noqa: E731
    rows = [("weights ∝ 1 / 20-day volatility", run(tilt=inverse_vol(1.0))),
            ("weights ∝ 1 / √(20-day volatility)", run(tilt=inverse_vol(0.5))),
            ("beta-neutral sides (60-day beta to the universe)", reweighted(beta_neutral(BASE.weights))),
            ("volatility target, 30 days, leverage cap 2", scaled(vol_target(30, 2.0))),
            ("volatility target, 30 days, leverage cap 1", scaled(vol_target(30, 1.0))),
            ("volatility target, 60 days, leverage cap 2", scaled(vol_target(60, 2.0))),
            ("equity-curve filter (on only if the last 60 days > 0)", scaled(equity_filter())),
            ("thin side filled with the universe basket", run(basket=UNIVERSE)),
            ("drift band 25%", run(band=0.25)),
            ("drift band 50%", run(band=0.5))]
    for name, v in rows:
        print(variant_row(name, BASE, v, turnover_change(BASE, v)))

    header("§1: B3 by trailing 30-day cross-sectional dispersion", "trailing dispersion", "B3 mean a day",
           "B3 volatility a day", "Sharpe", "mean ÷ variance")
    disp = pd.Series(np.nanstd(RET, axis=1)).rolling(30).mean().shift(1)
    tercile = pd.qcut(disp, 3, labels=["low", "middle", "high"])
    for label in ("low", "middle", "high"):
        r = BASE.net[(tercile == label).to_numpy()]
        print(f"| {label} | {num(r.mean() * 1e4, '+.1f')} bp | {r.std() * 1e4:.0f} bp | {num(bt.sharpe(r), '.2f')} "
              f"| {r.mean() / r.var():.3f} |")
    weeks = pd.Series(BASE.net, index=pd.DatetimeIndex(DAYS)).resample("W").apply(lambda x: np.prod(1 + x) - 1)
    print(f"\nautocorrelation: monthly {bt.period_returns(BASE.net, DAYS, 'month').autocorr():+.2f}, "
          f"weekly {weeks.autocorr():+.2f}")

    header("§3: listing age as a portfolio", "variant", "Sharpe", "Δ vs baseline [95%]", "Δ 2023–24", "Δ 2025–26",
           "CAGR", "max DD", "names L / S")
    age = (pd.to_datetime(FIRES["day"]) - pd.to_datetime(FIRES["symbol"].map(PANEL.first_bar))).dt.days
    is_long = FIRES["side"] > 0
    s21 = run(holds=SHORTS_21)
    rows = [("longs only if listed ≥ 2 years (filter)", BASE, run(FIRES[~is_long | (age >= 730)])),
            ("longs only if listed ≥ 1 year (filter)", BASE, run(FIRES[~is_long | (age >= 365)])),
            ("**tilt 1.5×: old longs, young shorts**", BASE, run(tilt=age_tilt(1.5))),
            ("tilt 2×: old longs, young shorts", BASE, run(tilt=age_tilt(2.0))),
            ("tilt 1.5×, pre-2021 listings not given more weight", BASE, run(tilt=age_tilt(1.5, pre_2021=False))),
            ("tilt 1.5×, longs only", BASE, run(tilt=age_tilt(1.5, shorts=False))),
            ("tilt 1.5×, shorts only", BASE, run(tilt=age_tilt(1.5, longs=False))),
            ("shorts 21 days (exit_research.md)", BASE, s21),
            ("shorts 21 days + tilt 1.5× (Δ vs shorts 21)", s21, run(holds=SHORTS_21, tilt=age_tilt(1.5)))]
    for name, base, v in rows:
        print(variant_row(name, base, v, names(v)))
    print(f"\nbaseline names L / S: {names(BASE)}")
    # The age book: each day, every eligible coin listed 2+ years is long and every coin
    # listed under 1 year is short. A hold of 0 days keeps a coin only on its own day.
    cd = PANEL.coin_days
    cd_age = (pd.to_datetime(cd["day"]) - pd.to_datetime(cd["symbol"].map(PANEL.first_bar))).dt.days
    old, young = cd_age >= 730, cd_age < 365
    pick = cd[cd["eligible"] & (old | young)]
    daily = pick.assign(first=True, leg=np.where(old[pick.index], "old", "young"),
                        side=np.where(old[pick.index], 1, -1))
    age_only = run(daily, holds={"old": 0, "young": 0})
    y = bt.period_returns(age_only.net, DAYS, "year")
    print(f"age alone (long listed 2+ years, short listed < 1 year, every eligible coin, daily): Sharpe "
          f"{bt.sharpe(age_only.net):.2f}, 2023 {pct(y['2023'], 0)}, 2024 {pct(y['2024'], 0)}")


# ---------------------------------------------------------------- the live bot's execution (research_log.md 2026-11-07)

LIVE = bt.with_low(PANEL, Path("state/research_cache"))       # a resting buy needs the bar lows
BOT = dict(fill="limit", short_stop=1.0, stop_delay=1)       # the execution of docs/trading_bot.md


def live(fires: pd.DataFrame = FIRES, **kw) -> bt.Run:
    return bt.simulate(LIVE, fires, **kw)


def entry_fills(v: bt.Run) -> tuple[float, float]:
    """(share of first-fire entries whose order filled on the fire day, mean days to fill).
    An entry that never fills in its hold counts as the hold's length."""
    first = FIRES[FIRES["first"] & FIRES["leg"].notna()]
    days = []
    for r in first.itertuples():
        t0, j = ROW[date.fromisoformat(r.day)], COL[r.symbol]
        held = np.sign(v.weights[t0:t0 + bt.HOLD_DAYS + 1, j]) == r.side
        if BASE.weights[t0, j] * r.side > 0:            # the backtest opened it on its fire day
            days.append(held.argmax() if held.any() else bt.HOLD_DAYS + 1)
    days = np.array(days)
    return float((days == 0).mean()), float(days.mean())


def live_execution() -> None:
    print("\n## research_log.md 2026-11-07: the live bot's execution")
    header("fills", "book", "Sharpe", "Δ vs baseline [95%]", "Δ 2023–24", "Δ 2025–26", "CAGR", "max DD",
           "costs a year", "orders filled")
    print(f"| **baseline: every order fills at the close, 0.10% a side** | {num(bt.sharpe(BASE.net), '.2f')} | — | — | — "
          f"| {pct(bt.cagr(BASE.net))} | {pct(bt.max_drawdown(BASE.net), 0)} | {pct(BASE.cost.mean() * 365)} | 100% |")
    rows = [("0.015% a side at the close (the maker fee, every order fills)", dict(cost=bt.MAKER_COST)),
            ("resting limit order for one day, then a new one (the bot)", dict(fill="limit")),
            ("resting limit order for one day, then cross the spread", dict(fill="limit_then_cross")),
            ("drift band 25%, fills at the close (the bot's band)", dict(band=0.25)),
            ("resting limit order + drift band 25%", dict(fill="limit", band=0.25))]
    runs = {}
    for name, kw in rows:
        v = runs[name] = live(**kw)
        fill = v.filled.sum() / v.sent.sum()
        print(variant_row(name, BASE, v, f"{pct(v.cost.mean() * 365)} | {fill * 100:.1f}%"))
    limit = runs["resting limit order for one day, then a new one (the bot)"]
    fee = runs["0.015% a side at the close (the maker fee, every order fills)"]
    share, days = entry_fills(limit)
    print(f"\nlimit orders: gross a year {pct(limit.gross.mean() * 365)} against {pct(fee.gross.mean() * 365)} with "
          f"every order filled; costs a year {pct(limit.cost.mean() * 365)} against {pct(BASE.cost.mean() * 365)}")
    print(f"first-fire entries filled on the fire day: {share * 100:.1f}%; mean days to fill {days:.2f}")

    header("the short tail stop at +100%", "book", "Sharpe", "Δ vs baseline [95%]", "Δ 2023–24", "Δ 2025–26",
           "CAGR", "max DD")
    day1 = live(short_stop=1.0)
    for name, v in (("stop from the fire day (the backtest)", day1),
                    ("stop from the next day (the bot)", live(short_stop=1.0, stop_delay=1)),
                    ("the bot: limit orders + stop from the next day", live(**BOT))):
        print(variant_row(name, BASE, v))

    header("the $10 minimum order, with the bot's execution (limit orders, stop from the next day)", "book",
           "Sharpe", "Δ vs baseline [95%]", "Δ 2023–24", "Δ 2025–26", "CAGR", "max DD",
           "days with only the closes", "max \\|net\\|", "correlation with the baseline")
    for band in (0.25, 0.0):
        for equity in (500, 1000, 2000, 3000, 5000, 10000, None):
            v = live(**BOT, band=band, equity=equity)
            size = f"${equity:,}" if equity else "no minimum"
            print(variant_row(f"band {band:.0%}, {size}", BASE, v,
                              f"{v.closes_only.mean() * 100:.0f}% | {np.abs(v.weights.sum(axis=1)).max() * 100:.0f}% "
                              f"| {np.corrcoef(BASE.net, v.net)[0, 1]:.2f}"))


# ---------------------------------------------------------------- new exits (exit_research.md §8)

HIST = coin_matrix("hist")
PCT_STATE = coin_matrix("state_pct")
S2_BAND = (HIST < 0) & (PCT_STATE > 50) & (PCT_STATE < 100)
TRUE_RANGE = np.fmax(LIVE.high - LIVE.low, np.fmax(np.abs(LIVE.high - LIVE.prev_close),
                                                    np.abs(LIVE.low - LIVE.prev_close)))
ATR = pd.DataFrame(TRUE_RANGE).ewm(alpha=1 / 14, adjust=False, ignore_na=True).mean().to_numpy()


def long_in_s2_band(day: date, p: bt.Position) -> bool:
    """Close a long when its coin is in S2's band: a dip that continues to go down."""
    return p.side > 0 and bool(S2_BAND[ROW[day], COL[p.symbol]])


def edge_paid(day: date, p: bt.Position) -> bool:
    """Close when the histogram, signed in the trade's direction, has risen since the
    entry, is above zero, and now shrinks: the move that the leg traded is over."""
    t, t0, j = ROW[day], ROW[p.entry], COL[p.symbol]
    x = p.side * HIST[t0:t + 1, j]
    if len(x) < 3 or not (x[-1] > 0 and x[-1] < x[-2]):
        return False
    return bool((np.diff(x[:-1]) > 0).any())


def _move(day: date, p: bt.Position) -> tuple[float, float]:
    """(the trade's return since entry, the coin's ATR at entry as a fraction of price)."""
    t, t0, j = ROW[day], ROW[p.entry], COL[p.symbol]
    entry = PANEL.prev_close[t0, j]
    return p.side * (PANEL.prev_close[t, j] / entry - 1), ATR[max(t0 - 1, 0), j] / entry


def take_profit(k: float):
    def rule(day: date, p: bt.Position) -> bool:
        move, atr = _move(day, p)
        return move >= k * atr
    return rule


def give_back(k: float):
    """Close when the trade has been k ATR in profit and has since lost k ATR."""
    def rule(day: date, p: bt.Position) -> bool:
        t0, t, j = ROW[p.entry], ROW[day], COL[p.symbol]
        entry = PANEL.prev_close[t0, j]
        path = p.side * (PANEL.prev_close[t0 + 1:t + 1, j] / entry - 1)
        atr = ATR[max(t0 - 1, 0), j] / entry
        return bool(len(path) and path.max() >= k * atr and path[-1] <= path.max() - k * atr)
    return rule


def rank_exit(day: date, p: bt.Position) -> bool:
    """Close when the trade's move since entry is in the best decile of the entry day's
    universe over the same days (top for a long, bottom for a short)."""
    t, t0, j = ROW[day], ROW[p.entry], COL[p.symbol]
    moves = np.where(UNIVERSE[t0], PANEL.prev_close[t] / PANEL.prev_close[t0] - 1, np.nan)
    mine = moves[j] if UNIVERSE[t0, j] else PANEL.prev_close[t, j] / PANEL.prev_close[t0, j] - 1
    return bool(mine >= np.nanpercentile(moves, 90) if p.side > 0 else mine <= np.nanpercentile(moves, 10))


def without_flips(triggers: pd.DataFrame) -> pd.DataFrame:
    """The triggers on coins with no long first fire in the last HOLD_DAYS days: a trigger
    that would flip a long is dropped."""
    longs = FIRES[FIRES["first"] & FIRES["leg"].isin(("L1", "L2"))]
    last_long = {}
    for r in longs.itertuples():
        last_long.setdefault(r.symbol, []).append(date.fromisoformat(r.day))
    keep = [not any(0 <= (date.fromisoformat(r.day) - d).days <= bt.HOLD_DAYS for d in last_long.get(r.symbol, ()))
            for r in triggers.itertuples()]
    return triggers[keep]


def new_exits() -> None:
    print("\n## exit_research.md §8: new exits")
    header("as portfolios", "book", "Sharpe", "Δ vs baseline [95%]", "Δ 2023–24", "Δ 2025–26", "CAGR", "max DD",
           "turnover")
    holds_7 = run(holds={leg: 7 for leg in LEGS})
    rows = [("longs close in S2's band (hist < 0, 50 < `peak_pct` < 100)", run(exit_rule=long_in_s2_band)),
            ("edge paid: the trade-side histogram rose above 0 and now shrinks", run(exit_rule=edge_paid)),
            ("take profit at 3 ATR", run(exit_rule=take_profit(3))),
            ("take profit at 5 ATR", run(exit_rule=take_profit(5))),
            ("give back 2 ATR after 2 ATR of profit", run(exit_rule=give_back(2))),
            ("rank: best decile of the universe since entry", run(exit_rule=rank_exit)),
            ("scale out: half at day 7, the rest at day 14", reweighted(0.5 * (holds_7.weights + BASE.weights))),
            ("a same-leg re-fire restarts the clock", run(restart_same_leg=True))]
    for name, v in rows:
        print(variant_row(name, BASE, v, turnover_change(BASE, v)))

    header("why S2 as the MACD state scores higher", "book", "Sharpe", "Δ vs baseline [95%]", "Δ 2023–24",
           "Δ 2025–26", "CAGR", "max DD", "names L / S")
    cd = PANEL.coin_days
    triggers = state_triggers("S2", -1, (cd["hist"] < 0) & (cd["state_pct"] > 50) & (cd["state_pct"] < 100))
    no_s2 = legs("L1", "L2", "S1")
    for name, v in (("S2 as the MACD state (trading_strategy.md)", run(pd.concat([no_s2, triggers]))),
                    ("S2 as the MACD state, no trigger on a coin held long", run(pd.concat([no_s2, without_flips(triggers)]))),
                    ("S2 fires, longs close in S2's band", run(exit_rule=long_in_s2_band))):
        print(variant_row(name, BASE, v, names(v)))


# ---------------------------------------------------------------- strategy search (docs/strategy_search.md)

# (fast, slow, signal, min_reduction). The grid was fixed before the first look.
NEIGHBOURS = ((8, 17, 9, 0.3), (10, 22, 9, 0.3), (15, 30, 9, 0.3), (19, 39, 9, 0.3),
              (12, 26, 9, 0.2), (12, 26, 9, 0.4), (12, 26, 6, 0.3), (12, 26, 12, 0.3))


def neighbour_panel(fast: int, slow: int, signal: int, reduction: float) -> bt.Panel:
    """The frozen panel of a detector with other parameters. A build takes about one
    minute, so the panel stays in the cache."""
    path = Path("state/research_cache/neighbours") / f"p_{fast}_{slow}_{signal}_{int(reduction * 100)}.pkl"
    if not path.exists():
        cfg = load_config("config.yaml")
        cfg.macd.fast, cfg.macd.slow, cfg.macd.signal = fast, slow, signal
        cfg.signal.histogram_flattening.min_reduction_from_peak = reduction
        path.parent.mkdir(exist_ok=True)
        raw = bt.build_panel(bt.load_bars(Path("state/research_cache")), cfg)
        path.write_bytes(pickle.dumps(raw | dict(source="neighbour panel", built=path.name)))
    return bt.load_panel(path)


def band_exit(panel: bt.Panel):
    """``long_in_s2_band`` on the MACD state of another panel."""
    def matrix(column: str) -> np.ndarray:
        wide = panel.coin_days.pivot(index="day", columns="symbol", values=column)
        return wide.reindex(index=[d.isoformat() for d in DAYS], columns=PANEL.symbols).to_numpy(dtype=float)
    hist, state = matrix("hist"), matrix("state_pct")
    band = (hist < 0) & (state > 50) & (state < 100)

    def rule(day: date, p: bt.Position) -> bool:
        return p.side > 0 and bool(band[ROW[day], COL[p.symbol]])
    return rule


STACK = dict(exit_rule=long_in_s2_band, holds=SHORTS_21, tilt=age_tilt(1.5))


def strategy_search() -> None:
    print("\n## strategy_search.md")
    header("B3 and the stack", "book", "Sharpe", "Δ vs baseline [95%]", "Δ 2023–24", "Δ 2025–26", "CAGR", "max DD",
           "turnover")
    print(f"| **baseline** | {num(bt.sharpe(BASE.net), '.2f')} | — | — | — | {pct(bt.cagr(BASE.net))} "
          f"| {pct(bt.max_drawdown(BASE.net), 0)} | — |")
    for name, kw in (("longs close in S2's band", dict(exit_rule=long_in_s2_band)), ("shorts 21 days", dict(holds=SHORTS_21)),
                     ("age tilt 1.5×", dict(tilt=age_tilt(1.5))), ("**the stack: all three**", STACK)):
        v = run(**kw)
        print(variant_row(name, BASE, v, turnover_change(BASE, v)))

    bot_base = live(**BOT)
    header("the stack with the bot's execution (limit orders, stop from the next day)", "book", "Sharpe",
           "Δ vs the bot's B3 [95%]", "Δ 2023–24", "Δ 2025–26", "CAGR", "max DD")
    print(f"| the bot's B3 | {num(bt.sharpe(bot_base.net), '.2f')} | — | — | — | {pct(bt.cagr(bot_base.net))} "
          f"| {pct(bt.max_drawdown(bot_base.net), 0)} |")
    for name, kw in (("the stack", {}), ("the stack, $5,000", dict(equity=5000)), ("the stack, $10,000", dict(equity=10000))):
        print(variant_row(name, bot_base, live(**BOT, **STACK, **kw)))

    header("each change on the 9 detector settings: Δ Sharpe (Δ 2023–24 / Δ 2025–26) against the same settings",
           "fast / slow / signal / reduction", "Sharpe of B3", "longs close in S2's band", "shorts 21 days",
           "age tilt 1.5×", "the stack")
    settings = [("12 / 26 / 9 / 0.3", PANEL)] + [(" / ".join(map(str, n)), neighbour_panel(*n)) for n in NEIGHBOURS]
    wins = {k: [0, 0] for k in ("band", "shorts", "tilt", "stack")}
    for name, panel in settings:
        fires = bt.book_fires(panel)
        base = bt.simulate(panel, fires)
        exit_ = band_exit(panel)
        cells = []
        for k, kw in (("band", dict(exit_rule=exit_)), ("shorts", dict(holds=SHORTS_21)),
                      ("tilt", dict(tilt=age_tilt(1.5))),
                      ("stack", dict(exit_rule=exit_, holds=SHORTS_21, tilt=age_tilt(1.5)))):
            v = bt.simulate(panel, fires, **kw)
            d = bt.sharpe(v.net) - bt.sharpe(base.net)
            d1, d2 = (x - y for x, y in zip(half_sharpes(v.net), half_sharpes(base.net)))
            wins[k][0] += d > 0
            wins[k][1] += d1 > 0 and d2 > 0
            cells.append(f"{num(d, '+.2f')} ({num(d1, '+.2f')} / {num(d2, '+.2f')})")
        print(f"| {name} | {num(bt.sharpe(base.net), '.2f')} | " + " | ".join(cells) + " |")
    print("\nsettings with Δ > 0, and with Δ > 0 in both halves, of 9: "
          + ", ".join(f"{k} {a} and {b}" for k, (a, b) in wins.items()))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")         # the tables use −, → and Δ
    print(f"# Portfolio tables — panel built {PANEL.meta['built']}, window {DAYS[0]} → {DAYS[-1]}")
    profit_strategies()
    trading_strategy()
    exit_research()
    book_experiments()
    live_execution()
    new_exits()
    strategy_search()
