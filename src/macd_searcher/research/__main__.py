"""Periodic research report: ``uv run python -m macd_searcher.research --help``.

Prints markdown to stdout (or ``--out``), so a run can be pasted into, or diffed
against, docs/confidence_v3_research.md. Progress goes to stderr.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sqlite3
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

from ..config import load_config
from . import cache, dataset
from .inference import bh_qvalues, block_ci, per_episode, spearman_ic
from .rules import RULES, WATCHLIST

log = logging.getLogger("macd_searcher.research")

# The date v2's thresholds were last fitted through + 1. Move it whenever the
# live rule is retuned, so "out of sample" keeps meaning "unseen by the rule".
DEFAULT_OOS_FROM = "2026-09-19"
MIN_EPISODES = 30   # below this a watchlist verdict is "pending", not a result

# Columns that are outcomes, ids or raw inputs — never features. carry_7d is a
# FORWARD quantity (funding paid during the hold); scanning it would be look-ahead.
_NOT_FEATURES = {"fire_close", "fire_macd", "fire_hist", "fire_hist_peak", "atr", "oos", "episode_start"}
_OUTCOME_PREFIXES = ("r_", "market_", "alpha_", "bench_", "px_", "ret_", "carry_")


def _fmt(m: float, lo: float, hi: float) -> str:
    if np.isnan(m):
        return "—"
    if np.isnan(lo):
        return f"{m:+.2f}"
    return f"{m:+.2f} [{lo:+.2f}, {hi:+.2f}]"


def _episode_ci(g: pd.DataFrame, col: str) -> tuple[float, float, float, int]:
    e = per_episode(g, col)
    return (*block_ci(e[col], e["week"]), len(e))


def rules_section(df: pd.DataFrame, h: int) -> list[str]:
    a, r, m = f"alpha_{h}d", f"r_{h}d", f"market_{h}d"
    scored = df[df[a].notna()]
    lines = [
        f"## Rules — {h}d  (raw = market + alpha; alpha vs the same-run class mean)",
        "",
        "| rule | share | rows | episodes | raw | market | alpha, rows (week CI) "
        "| alpha, episodes (week CI) | in-sample (ep) | out-of-sample (ep) | months α>0 |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for name, rule in RULES.items():
        g = scored[rule(scored)]
        if g.empty:
            continue
        rows = block_ci(g[a], g["week"])
        ep_m, ep_lo, ep_hi, n_ep = _episode_ci(g, a)
        is_ = _episode_ci(g[~g["oos"]], a)
        oos = _episode_ci(g[g["oos"]], a) if g["oos"].any() else (np.nan,) * 3 + (0,)
        months = g.groupby("month")[a].mean()
        lines.append(
            f"| {name} | {rule(df).mean() * 100:.1f}% | {len(g)} | {n_ep} | {g[r].mean():+.2f} "
            f"| {g[m].mean():+.2f} | {_fmt(*rows)} | {_fmt(ep_m, ep_lo, ep_hi)} "
            f"| {_fmt(*is_[:3])} (n={is_[3]}) | {_fmt(*oos[:3])} (n={oos[3]}) "
            f"| {(months > 0).sum()}/{len(months)} |")
    return lines


def watchlist_section(df: pd.DataFrame, h: int) -> list[str]:
    a = f"alpha_{h}d"
    oos = df[df["oos"] & df[a].notna()]
    lines = ["## Watchlist (pre-registered — test these before searching for anything new)", "",
             "| rule | question | out-of-sample episodes | alpha (ep, week CI) | verdict |",
             "|---|---|---|---|---|"]
    for c in WATCHLIST:
        g = oos[RULES[c.rule](oos)]
        m, lo, hi, n = _episode_ci(g, a) if len(g) else (np.nan, np.nan, np.nan, 0)
        if n < MIN_EPISODES:
            verdict = f"pending (needs {MIN_EPISODES} episodes)"
        elif not np.isnan(lo) and c.expect_sign * lo > 0 and c.expect_sign * hi > 0:
            verdict = f"**confirmed** → {c.on_confirm}"
        elif not np.isnan(lo) and c.expect_sign * hi < 0:
            verdict = "**contradicted**"
        else:
            verdict = "undecided (CI spans 0)"
        lines.append(f"| {c.rule} | {c.question} | {n} | {_fmt(m, lo, hi)} | {verdict} |")
    return lines


def funding_section(df: pd.DataFrame, h: int) -> list[str]:
    if "carry_7d" not in df:
        return []
    lines = ["## Funding", "", "| rule | rows with carry | carry a long pays over 7d | alpha → net of carry |",
             "|---|---|---|---|"]
    for name, rule in RULES.items():
        g = df[rule(df) & df["carry_7d"].notna() & df["alpha_7d"].notna()]
        if g.empty:
            continue
        net = g["alpha_7d"] + np.where(g["direction"] == "bullish", -1, 1) * g["carry_7d"]
        lines.append(f"| {name} | {len(g)} | {g['carry_7d'].mean():+.3f}% "
                     f"| {g['alpha_7d'].mean():+.2f} → {_fmt(*block_ci(net, g['week']))} |")
    return lines


def scan_section(df: pd.DataFrame, h: int) -> list[str]:
    a = f"alpha_{h}d"
    feats = [c for c in df.columns
             if c not in _NOT_FEATURES and not c.startswith(_OUTCOME_PREFIXES)
             and pd.api.types.is_numeric_dtype(df[c]) and df[c].notna().mean() > 0.5]
    lines = ["## Feature scan — episode-level IC vs alpha (feature as at the episode's first alert)", ""]
    for direction in ("bullish", "bearish"):
        g = df[(df["direction"] == direction) & df[a].notna()]
        e = per_episode(g, a, keep_first=tuple(feats))
        rows = []
        for f in feats:
            ins, out = e[~e["oos"]], e[e["oos"]]
            rho, lo, hi, n = spearman_ic(ins[f], ins[a], ins["week"], n_boot=300)
            se = (hi - lo) / 3.92 if hi > lo else np.nan
            p = 2 * (1 - norm.cdf(abs(rho) / se)) if se else np.nan
            orho, olo, ohi, on = spearman_ic(out[f], out[a], out["week"], n_boot=300)
            rows.append((f, rho, lo, hi, n, p, orho, olo, ohi, on))
        q = bh_qvalues([r[5] if not np.isnan(r[5]) else 1.0 for r in rows])
        lines += [f"### {direction} ({len(e)} episodes)", "",
                  "| feature | in-sample IC | q | out-of-sample IC | same sign |", "|---|---|---|---|---|"]
        for (f, rho, lo, hi, n, p, orho, olo, ohi, on), qq in sorted(zip(rows, q), key=lambda t: t[1]):
            if qq > 0.25:
                continue
            same = "yes" if np.sign(rho) == np.sign(orho) else "no"
            lines.append(f"| {f} | {_fmt(rho, lo, hi)} (n={n}) | {qq:.3f} | {_fmt(orho, olo, ohi)} (n={on}) | {same} |")
        lines.append("")
    return lines


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m macd_searcher.research", description=__doc__)
    ap.add_argument("--db", default="state/prod_snapshot.sqlite3")
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--oos-from", default=DEFAULT_OOS_FROM,
                    help="first day the live rule has not seen (default %(default)s)")
    ap.add_argument("--horizon", type=int, default=7, choices=dataset.HORIZONS)
    ap.add_argument("--gap-days", type=int, default=1,
                    help="a re-fire within this many days continues an episode (default %(default)s)")
    ap.add_argument("--offline", action="store_true", help="use the cache as-is; no API calls")
    ap.add_argument("--scan", action="store_true", help="also scan every feature (slow)")
    ap.add_argument("--out", help="write the report here instead of stdout")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, stream=sys.stderr, format="%(asctime)s %(message)s")

    conn = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    symbols = [r[0] for r in conn.execute("SELECT DISTINCT symbol FROM asset_snapshots ORDER BY 1")]
    root = cache.root_for(args.db)
    if not args.offline:
        failed = asyncio.run(cache.refresh(root, symbols, load_config(args.config)))
        if failed:
            log.warning("%d cache entries failed this run and will retry next run", len(failed))
    candles, funding = cache.load(root, "candles", symbols), cache.load(root, "funding", symbols)
    log.info("cache %s: candles %d, funding %d of %d symbols", root, len(candles), len(funding), len(symbols))
    if not candles:
        log.warning("NO CANDLES CACHED — alpha will use snapshot exits, which are survivorship-"
                    "biased against bullish signals. Run without --offline to fill the cache.")

    df = dataset.build(conn, candles, funding, gap_days=args.gap_days, oos_from=args.oos_from)
    latest = conn.execute("SELECT MAX(started_at) FROM runs").fetchone()[0]
    h = args.horizon
    scored = df[df[f"alpha_{h}d"].notna()]
    lines = [
        f"# Research report — snapshot through {latest[:16]} UTC", "",
        f"- signals (deduped, post-fix): {len(df)}; with a {h}d alpha: {len(scored)} "
        f"in {scored['episode'].nunique()} episodes (gap ≤ {args.gap_days}d)",
        f"- out of sample from {args.oos_from}: {int(scored['oos'].sum())} rows, "
        f"{scored[scored['oos']]['episode'].nunique()} episodes",
        f"- caches: candles {len(candles)}, funding {len(funding)} of {len(symbols)} symbols — "
        f"benchmark exits from {'candles' if candles else '**snapshots only (survivorship-biased)**'}", "",
    ]
    lines += rules_section(df, h) + [""] + watchlist_section(df, h) + [""] + funding_section(df, h)
    if args.scan:
        lines += [""] + scan_section(df, h)
    text = "\n".join(lines) + "\n"
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        log.info("wrote %s", args.out)
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
