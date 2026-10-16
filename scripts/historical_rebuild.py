"""Historical rebuild of the closed-candle detector — see docs/historical_rebuild.md.

Runs the production detector (signals._check_histogram_flattening + _peak_vs_history,
current config.yaml) once per symbol per day on 200 closed daily bars, for every core
crypto perp in state/research_cache/history/ (fetched incl. delisted coins), and scores
the frozen hypotheses H1-H9. Read-only; writes nothing outside state/ and stdout.

    uv run python scripts/historical_rebuild.py
"""

from __future__ import annotations

import pickle
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from macd_searcher.config import load_config
from macd_searcher.indicators import macd
from macd_searcher.research.inference import contrast_ci, per_episode
from macd_searcher.signals import _check_histogram_flattening, _peak_vs_history
from macd_searcher.stats import block_ci, episodes

HIST = Path("state/research_cache/history")
OUT = Path("state/research_cache/history_rebuild.pkl")
CONFIRM = ("2022-01-01", "2026-06-08")       # confirmatory window (pre-registered)
CALIB = ("2026-06-09", "2026-10-08")         # live period: calibration only
MIN_NOTIONAL = 300_000                       # scanner's min_24h_volume_usd
MIN_BENCH = 10
HORIZONS = (1, 3, 7, 14)

cfg = load_config("config.yaml")
LB = cfg.candles.lookback_days


def load() -> dict[str, dict]:
    out = {}
    for p in sorted(HIST.glob("*.csv")):
        d = pd.read_csv(p)
        d["ts"] = pd.to_datetime(d["ts"], utc=True, format="ISO8601")
        d = d.sort_values("ts").drop_duplicates("ts").reset_index(drop=True)
        if len(d) < LB + 20:
            continue
        pc = d["close"].shift(1)
        tr = pd.concat([d.high - d.low, (d.high - pc).abs(), (d.low - pc).abs()], axis=1).max(axis=1)
        atr = tr.ewm(alpha=1 / 14, adjust=False).mean()
        days = d["ts"].dt.strftime("%Y-%m-%d").to_numpy()
        out[p.stem.replace("__", ":")] = dict(
            days=days, at={x: i for i, x in enumerate(days)}, close=d["close"].to_numpy(),
            notional=(d["volume"] * d["close"]).to_numpy(), atr=atr.to_numpy(),
            atr30=(atr / atr.shift(30)).to_numpy(),
            m=macd(d["close"], cfg.macd.fast, cfg.macd.slow, cfg.macd.signal))
    return out


def rebuild(assets: dict[str, dict]) -> pd.DataFrame:
    btc = assets["BTC"]
    btc_sig = dict(zip(btc["days"], btc["m"]["signal"].to_numpy()))
    rows, bench_rows = [], []
    for D in pd.date_range("2022-01-01", CALIB[1], freq="D").strftime("%Y-%m-%d"):
        prev = (pd.Timestamp(D) - pd.Timedelta(days=1)).strftime("%Y-%m-%d")
        exits = {h: (pd.Timestamp(D) + pd.Timedelta(days=h)).strftime("%Y-%m-%d") for h in HORIZONS}
        eligible = []
        for s, a in assets.items():
            i_prev = a["at"].get(prev)
            if i_prev is None or i_prev + 1 < LB or a["notional"][i_prev] < MIN_NOTIONAL:
                continue
            eligible.append((s, a, i_prev))
        # benchmark: equal-weight mean forward return of every eligible symbol, same bars
        rets = {h: [] for h in HORIZONS}
        for s, a, i_prev in eligible:
            for h in HORIZONS:
                j = a["at"].get(exits[h])
                if j is not None:
                    rets[h].append(a["close"][j] / a["close"][i_prev] - 1)
        bench = {h: (float(np.mean(v)) if len(v) >= MIN_BENCH else np.nan) for h, v in rets.items()}
        bench_rows.append(dict(day=D, eligible=len(eligible), **{f"bench_{h}d": bench[h] for h in HORIZONS}))
        for s, a, i_prev in eligible:
            mw = a["m"].iloc[i_prev + 1 - LB:i_prev + 1]            # 200 closed bars ending D-1
            sig = _check_histogram_flattening(s, float(a["close"][i_prev]), mw, cfg)
            if sig is None:
                continue
            _, pct, top_n = _peak_vs_history(mw["hist"], sig.direction)
            sign = 1.0 if sig.direction == "bullish" else -1.0
            row = dict(symbol=s, day=D, direction=sig.direction, red=sig.reduction_from_peak,
                       sig_atr=(sig.macd - sig.hist) / a["atr"][i_prev], peak_pct=pct, top_n=top_n,
                       atr_change_30=a["atr30"][i_prev], btc_signal_line=btc_sig.get(prev, np.nan),
                       eligible=len(eligible))
            for h in HORIZONS:
                j = a["at"].get(exits[h])
                raw = a["close"][j] / a["close"][i_prev] - 1 if j is not None else np.nan
                row[f"r_{h}d"] = sign * raw * 100
                row[f"market_{h}d"] = sign * bench[h] * 100
                row[f"alpha_{h}d"] = sign * (raw - bench[h]) * 100
            rows.append(row)
    df = pd.DataFrame(rows)
    df["fired_at"] = pd.to_datetime(df["day"], utc=True)
    df["week"] = df.fired_at.dt.strftime("%G-W%V")
    df["month"] = df.fired_at.dt.strftime("%Y-%m")
    df["year"] = df.fired_at.dt.year
    df["oos"] = False
    ids, starts = episodes(df.symbol.tolist(), df.direction.tolist(), df.day.tolist())
    df["episode"], df["episode_start"] = ids, starts
    return df, pd.DataFrame(bench_rows)


# ---------------------------------------------------------------- the frozen rules
BULL = lambda d: d.direction == "bullish"  # noqa: E731
BEAR = lambda d: d.direction == "bearish"  # noqa: E731
RULE = {
    "v3 bullish": lambda d: BULL(d) & (d.peak_pct <= 50) & (d.red < 0.6),
    "record trough": lambda d: BULL(d) & (d.peak_pct >= 100),
    "v2": lambda d: BULL(d) & (d.sig_atr < -0.5) & (d.red < 0.6),
    "BTC downtrend": lambda d: BULL(d) & (d.btc_signal_line < 0),
    "ATR expanding": lambda d: BULL(d) & (d.atr_change_30 > 1.10),
    "bearish low peak": lambda d: BEAR(d) & (d.peak_pct <= 25),
    "all bullish": BULL,
    "all bearish": BEAR,
}


def ep_alpha(g, col="alpha_7d"):
    g = g[g[col].notna()]
    if g.empty:
        return np.nan, np.nan, np.nan, 0
    e = per_episode(g, col)
    return (*block_ci(e[col], e["week"]), len(e))


def contrast(d, rule, versus, col):
    a, b = d[rule(d) & d[col].notna()], d[versus(d) & ~rule(d) & d[col].notna()]
    if a.empty or b.empty:
        return np.nan, np.nan, np.nan, 0
    ea, eb = per_episode(a, col), per_episode(b, col)
    return (*contrast_ci(ea[col], ea["week"], eb[col], eb["week"]), min(len(ea), len(eb)))


def ic(d):
    g = d[BULL(d) & d.alpha_7d.notna() & d.peak_pct.notna()].sort_values("fired_at")
    e = g.groupby("episode").agg(pk=("peak_pct", "first"), a=("alpha_7d", "mean"), week=("week", "first"))
    if len(e) < 30:
        return np.nan, np.nan, np.nan, len(e)
    rho = spearmanr(e.pk, e.a).statistic
    weeks = e.week.unique()
    members = [np.flatnonzero(e.week.to_numpy() == w) for w in weeks]
    rng = np.random.default_rng(0)
    boot = []
    for _ in range(1000):
        k = np.concatenate([members[i] for i in rng.integers(0, len(weeks), len(weeks))])
        boot.append(spearmanr(e.pk.to_numpy()[k], e.a.to_numpy()[k]).statistic)
    lo, hi = np.nanpercentile(boot, [2.5, 97.5])
    return rho, lo, hi, len(e)


def repeat_minus_first(d):
    g = d[BEAR(d) & d.alpha_7d.notna()].sort_values("fired_at")
    g = g.assign(pos=g.groupby("episode").cumcount())
    first = g[g.pos == 0].set_index("episode")
    later = g[g.pos >= 1].groupby("episode").alpha_7d.mean()
    j = pd.DataFrame({"diff": later - first.alpha_7d, "week": first.week}).dropna()
    if j.empty:
        return np.nan, np.nan, np.nan, 0
    return (*block_ci(j["diff"], j["week"]), len(j))


HYPOTHESES = [   # (id, label, expected sign, statistic)
    ("H1", "v3 bullish alpha", +1, lambda d: ep_alpha(d[RULE["v3 bullish"](d)])),
    ("H2", "record trough alpha", -1, lambda d: ep_alpha(d[RULE["record trough"](d)])),
    ("H3", "IC(peak_pct, alpha), bullish", -1, ic),
    ("H4", "v2 alpha", +1, lambda d: ep_alpha(d[RULE["v2"](d)])),
    ("H5", "v2 timing: market, v2 − rest of bullish", +1,
     lambda d: contrast(d, RULE["v2"], RULE["all bullish"], "market_7d")),
    ("H6", "BTC downtrend: raw, in-regime − rest", +1,
     lambda d: contrast(d, RULE["BTC downtrend"], RULE["all bullish"], "r_7d")),
    ("H7", "ATR expanding alpha", +1, lambda d: ep_alpha(d[RULE["ATR expanding"](d)])),
    ("H8", "bearish low peak, short alpha", +1, lambda d: ep_alpha(d[RULE["bearish low peak"](d)])),
    ("H9", "bearish repeat − first fire", -1, repeat_minus_first),
]


def fmt(m, lo, hi, n):
    if np.isnan(m):
        return f"—  (n={n})"
    return f"{m:+.2f} [{lo:+.2f}, {hi:+.2f}] (n={n})" if not np.isnan(lo) else f"{m:+.2f} (n={n})"


def verdict(sign, m, lo, hi, years_ok):
    if np.isnan(lo):
        return "undecided"
    if min(sign * lo, sign * hi) > 0:
        return "CONFIRMED" if years_ok >= 3 else "undecided (CI ok, years fail)"
    if max(sign * lo, sign * hi) < 0:
        return "CONTRADICTED"
    return "undecided"


def btc_stretches(d):
    days = sorted(d[d.btc_signal_line < 0].day.unique())
    if not days:
        return []
    s = pd.to_datetime(pd.Series(days))
    grp = (s.diff().dt.days > 3).cumsum()
    return [(g.min().date(), g.max().date(), len(g)) for _, g in s.groupby(grp)]


def main():
    if OUT.exists():
        df, bench = pickle.load(open(OUT, "rb"))
    else:
        df, bench = rebuild(load())
        pickle.dump((df, bench), open(OUT, "wb"))
    w = lambda lo, hi: df[df.day.between(lo, hi)]  # noqa: E731
    conf, cal = w(*CONFIRM), w(*CALIB)

    print("=== coverage ===")
    b = bench.assign(year=bench.day.str[:4])
    for y, g in b.groupby("year"):
        dd = conf[conf.year == int(y)] if y < "2026" else conf[conf.year == 2026]
        print(f"  {y}: median eligible {g.eligible.median():5.0f}/day, days with a benchmark "
              f"{g.bench_7d.notna().mean()*100:5.1f}%, confirmatory fires {len(dd):6d}, episodes {dd.episode.nunique():5d}")

    print("\n=== calibration (live period, rebuilt) vs closed-candle reconstruction on snapshots ===")
    for lbl, rule, ref in (("v3 bullish", RULE["v3 bullish"], "+0.44"), ("record trough", RULE["record trough"], "-3.07"),
                           ("all bullish", RULE["all bullish"], "-0.69"), ("all bearish", RULE["all bearish"], "-1.04")):
        print(f"  {lbl:<14s} rebuilt {fmt(*ep_alpha(cal[rule(cal)]))}   snapshot reference {ref}")

    print("\n=== confirmatory: 2022-01-01 → 2026-06-08 (7d, episode-level, week-block CI) ===")
    years = [2022, 2023, 2024, 2025, 2026]
    for hid, label, sign, stat in HYPOTHESES:
        m, lo, hi, n = stat(conf)
        per_year = {y: stat(conf[conf.year == y]) for y in years}
        ok = sum(1 for y in years if not np.isnan(per_year[y][0]) and sign * per_year[y][0] > 0)
        yr = "  ".join(f"{y}:{per_year[y][0]:+.2f}" if not np.isnan(per_year[y][0]) else f"{y}:—" for y in years)
        print(f"  {hid} {label:<40s} {fmt(m, lo, hi, n):<34s} years on expected side {ok}/5 → {verdict(sign, m, lo, hi, ok)}")
        print(f"       by year: {yr}")
    st = btc_stretches(conf[BULL(conf)])
    print(f"\n  H6 admissibility — BTC-downtrend stretches with bullish fires: {len(st)}")
    for a, z, n in st:
        print(f"     {a} → {z}  ({n} fire-days)")


if __name__ == "__main__":
    main()
