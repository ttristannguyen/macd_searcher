"""Build the research frame: one row per deduped signal (``perf._base()``) with
outcomes, an aligned alpha benchmark, episode ids, and features known at fire time.

Pure functions over DataFrames wherever possible, so the parts that have been gotten
wrong before — the benchmark, the episode grouping, the no-look-ahead join — are
unit-tested without a database (tests/test_research.py).
"""

from __future__ import annotations

import sqlite3

import numpy as np
import pandas as pd

from ..indicators import macd
from ..stats import episodes
from ..web.perf import _base

HORIZONS = (1, 3, 7, 14)
# A class needs this many symbols in a run before its mean is a usable benchmark.
MIN_BENCH_SYMBOLS = 10


def _shift_day(days: pd.Series, n: int) -> pd.Series:
    return (pd.to_datetime(days) + pd.Timedelta(days=n)).dt.strftime("%Y-%m-%d")


def _utc(ts: pd.Series) -> pd.Series:
    # One resolution everywhere: merge_asof and reindexing refuse mixed units.
    return pd.to_datetime(ts, utc=True, format="ISO8601").astype("datetime64[ns, UTC]")


# ---------------------------------------------------------------- loading

def load_signals(conn: sqlite3.Connection) -> pd.DataFrame:
    """The dashboard's own cohort, so research and the Confidence tab agree on n."""
    cte, params = _base(None)
    df = pd.read_sql(cte + """
        SELECT signal_id, run_id, symbol, asset_class, direction, fired_at, fire_close,
               fire_macd, fire_hist, fire_hist_peak, fire_reduction_from_peak AS red,
               fire_rsi_14 AS rsi,
               fire_hist_peak_pct AS peak_pct, fire_hist_peak_ratio AS peak_ratio,
               fire_hist_top_n AS top_n, atr, px_1d, px_3d, px_7d, px_14d,
               ret_1d, ret_3d, ret_7d, ret_14d
        FROM perf""", conn, params=params)
    df["fired_at"] = _utc(df["fired_at"])
    df["day"] = df["fired_at"].dt.strftime("%Y-%m-%d")
    df["week"] = df["fired_at"].dt.strftime("%G-W%V")
    df["month"] = df["fired_at"].dt.strftime("%Y-%m")
    df["sig_atr"] = (df["fire_macd"] - df["fire_hist"]) / df["atr"]
    return df


def load_snapshots(conn: sqlite3.Connection) -> pd.DataFrame:
    df = pd.read_sql("""
        SELECT a.run_id, a.symbol, a.asset_class, a.close, a.live_close, a.mark_px,
               a.open_interest_usd, a.day_ntl_vlm_usd, r.started_at
        FROM asset_snapshots a JOIN runs r ON r.run_id = a.run_id""", conn)
    df["t"] = _utc(df["started_at"])
    df["day"] = df["t"].dt.strftime("%Y-%m-%d")
    return df


# ---------------------------------------------------------------- outcomes

def daily_closes(snaps: pd.DataFrame, candles: dict[str, pd.DataFrame] | None = None) -> pd.Series:
    """The close OF each (symbol, day).

    From candles wherever they are cached. Otherwise from ``asset_snapshots``:
    ``close`` on any run of day D is the closed bar of D−1 (checked exact against
    candles), so the close of day X is the close seen on day X+1 — but only while the
    symbol is still in the liquidity-filtered universe. See ``benchmark`` for why
    that matters.
    """
    seen = snaps.groupby(["symbol", "day"])["close"].first()
    from_snaps = pd.Series(seen.to_numpy(), index=pd.MultiIndex.from_arrays(
        [seen.index.get_level_values("symbol"),
         _shift_day(pd.Series(seen.index.get_level_values("day")), -1)], names=["symbol", "day"]))
    if not candles:
        return from_snaps
    from_candles = pd.concat(
        {s: pd.Series(df["close"].to_numpy(), index=df["ts"].dt.strftime("%Y-%m-%d"))
         for s, df in candles.items()}, names=["symbol", "day"])
    return from_candles.combine_first(from_snaps)


def benchmark(snaps: pd.DataFrame, candles: dict[str, pd.DataFrame] | None = None,
              horizons=HORIZONS) -> pd.DataFrame:
    """What a random comparable asset returned: the MEAN forward return of every
    same-class symbol in the signal's own run.

    Entry is each symbol's ``live_close`` at that run — the same instant the signal
    fired. Exit is the close of day ``fire_day + N``, the same bar ``px_Nd`` uses.

    The mean, never the median: returns are right-skewed, so ``E[x − median] > 0``
    and a median benchmark hands every selection — a random one included — about
    +1% of free alpha at 7d. With the mean, a random pick scores 0 by construction.

    Pass ``candles``. Without them, exits come from snapshots, which only exist for
    symbols still inside the liquidity filter N days later — and the ones that fall
    out are the losers (−2.5% over 7d against +2.1% for those that stay). That
    survivorship inflates the benchmark and biases alpha against bullish signals.
    (The signal's own symbol is part of its run's mean; with 10+ symbols per class
    that only shrinks alpha slightly toward zero.)
    """
    close_of = daily_closes(snaps, candles)
    out = snaps[["run_id", "asset_class"]].copy()
    for n in horizons:
        key = pd.MultiIndex.from_arrays([snaps["symbol"], _shift_day(snaps["day"], n)])
        out[f"bench_{n}d"] = close_of.reindex(key).to_numpy() / snaps["live_close"].to_numpy() - 1
    cols = [f"bench_{n}d" for n in horizons]
    grouped = out.groupby(["run_id", "asset_class"])[cols]
    return grouped.mean().where(grouped.count() >= MIN_BENCH_SYMBOLS).reset_index()


def attach_outcomes(sig: pd.DataFrame, bench: pd.DataFrame, horizons=HORIZONS) -> pd.DataFrame:
    """Per horizon, in percent, with ``r = market + alpha`` exactly where a
    benchmark exists:

    * ``r_Nd``      — direction-normalised return, the dashboard's ``ret_Nd``;
    * ``market_Nd`` — what a random same-class asset gave this side of the trade;
    * ``alpha_Nd``  — the part the signal's choice of asset added.
    """
    df = sig.merge(bench, on=["run_id", "asset_class"], how="left")
    sign = np.where(df["direction"] == "bullish", 1.0, -1.0)
    for n in horizons:
        raw = df[f"px_{n}d"] / df["fire_close"] - 1
        df[f"r_{n}d"] = df[f"ret_{n}d"] * 100
        df[f"market_{n}d"] = sign * df[f"bench_{n}d"] * 100
        df[f"alpha_{n}d"] = sign * (raw - df[f"bench_{n}d"]) * 100
    return df


def assign_episodes(sig: pd.DataFrame, gap_days: int = 1) -> pd.DataFrame:
    """Group repeat fires into episodes. A fire whose same-symbol, same-direction
    predecessor fired within ``gap_days`` calendar days continues that episode.

    ~69% of deduped signals also fired the day before, and their forward windows
    overlap almost completely — counting them separately overstates the evidence
    about fourfold. ``episode_start`` marks the first alert of each episode.
    """
    ids, starts = episodes(sig["symbol"].tolist(), sig["direction"].tolist(), sig["day"].tolist(), gap_days)
    return sig.assign(episode=ids, episode_start=starts)


# ---------------------------------------------------------------- features

def _wilder(x: pd.Series, n: int) -> pd.Series:
    return x.ewm(alpha=1 / n, adjust=False).mean()


def indicators(candles: pd.DataFrame) -> pd.DataFrame:
    """Outside indicators for one symbol, indexed by bar date ('YYYY-MM-DD').
    All causal: the value at bar D uses bars <= D only."""
    df = candles.sort_values("ts").reset_index(drop=True)
    c, h, l, o, v = df["close"], df["high"], df["low"], df["open"], df["volume"]
    pc = c.shift(1)
    tr = pd.concat([h - l, (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)
    atr14 = _wilder(tr, 14)
    out = pd.DataFrame(index=df["ts"].dt.strftime("%Y-%m-%d"))
    out.index.name = "day"

    def put(name, series):
        out[name] = series.to_numpy()

    put("atr_pct", atr14 / c * 100)
    put("atr_ratio_14_50", atr14 / _wilder(tr, 50))
    put("atr_change_30", atr14 / atr14.shift(30))   # trading_strategy.md 3H's "ATR expanded" ratio
    for n in (20, 50, 100, 200):
        put(f"dist_sma{n}_atr", (c - c.rolling(n, min_periods=n).mean()) / atr14)
    sma50 = c.rolling(50).mean()
    put("sma50_slope_atr", (sma50 - sma50.shift(10)) / atr14)
    for n in (3, 7, 14, 30, 60):
        put(f"roc_{n}", (c / c.shift(n) - 1) * 100)
    put("dd_from_high_30", (c / h.rolling(30).max() - 1) * 100)
    put("dd_from_high_90", (c / h.rolling(90).max() - 1) * 100)
    put("range_pos_30", (c - l.rolling(30).min()) / (h.rolling(30).max() - l.rolling(30).min()))
    m20, s20 = c.rolling(20).mean(), c.rolling(20).std()
    put("bb_pctb", (c - (m20 - 2 * s20)) / (4 * s20))
    put("bb_width_atr", 4 * s20 / atr14)
    put("stoch_k14", (c - l.rolling(14).min()) / (h.rolling(14).max() - l.rolling(14).min()) * 100)
    up, dn = h.diff(), -l.diff()
    pdi = 100 * _wilder(pd.Series(np.where((up > dn) & (up > 0), up, 0.0)), 14) / atr14
    ndi = 100 * _wilder(pd.Series(np.where((dn > up) & (dn > 0), dn, 0.0)), 14) / atr14
    put("adx14", _wilder(100 * (pdi - ndi).abs() / (pdi + ndi), 14))
    put("di_spread", pdi - ndi)
    lr = np.log(c / pc)
    put("rv20", lr.rolling(20).std() * np.sqrt(365) * 100)
    put("rv_ratio_5_20", lr.rolling(5).std() / lr.rolling(20).std())
    notional = v * c
    put("vol_ratio_1_20", notional / notional.rolling(20).mean())
    put("vol_ratio_5_20", notional.rolling(5).mean() / notional.rolling(20).mean())
    put("down_vol_share_10", (notional * (c < pc)).rolling(10).sum() / notional.rolling(10).sum())
    rng = (h - l).replace(0, np.nan)
    put("body_atr", (c - o) / atr14)
    put("lower_wick_frac", (np.minimum(o, c) - l) / rng)
    put("close_loc", (c - l) / rng)
    put("close", c)
    return out


def _at_previous_day(sig: pd.DataFrame, frame: pd.DataFrame) -> pd.DataFrame:
    """Rows of a day-indexed ``frame`` for the day BEFORE each fire, aligned to sig."""
    got = frame.reindex(_shift_day(sig["day"], -1).to_numpy())
    got.index = sig.index
    return got


def attach_indicators(sig: pd.DataFrame, candles: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Features from the last bar CLOSED before the fire day — no look-ahead.

    66% of deduped fires are at 00:00 UTC, where that is exactly what was known.
    Later fires also saw part of the forming bar; ignoring it is conservative.
    """
    parts = []
    for symbol, idx in sig.groupby("symbol").groups.items():
        df = candles.get(symbol)
        if df is None or len(df) < 60:
            continue
        parts.append(_at_previous_day(sig.loc[idx], indicators(df)).drop(columns="close"))
    return sig.join(pd.concat(parts)) if parts else sig


def market_context(candles: dict[str, pd.DataFrame], classes: dict[str, str]) -> pd.DataFrame:
    """Day-indexed market regime: BTC trend/momentum and breadth above SMA50."""
    closes = pd.DataFrame({s: indicators(df)["close"] for s, df in candles.items() if len(df) >= 60})
    sma50 = closes.rolling(50, min_periods=50).mean()
    above = (closes > sma50).where(sma50.notna())
    crypto = [s for s in closes.columns if classes.get(s) == "crypto"]
    out = pd.DataFrame(index=closes.index)
    if "BTC" in candles:
        btc = indicators(candles["BTC"])
        bc = candles["BTC"].sort_values("ts")
        # The regime switch in trading_strategy.md 3G: BTC's own signal line vs zero.
        out["btc_signal_line"] = pd.Series(macd(bc["close"])["signal"].to_numpy(),
                                           index=bc["ts"].dt.strftime("%Y-%m-%d"))
        out["btc_roc_7"] = btc["roc_7"]
        out["btc_roc_30"] = btc["roc_30"]
        out["btc_dist_sma50_atr"] = btc["dist_sma50_atr"]
        out["btc_stoch_k14"] = btc["stoch_k14"]
    out["breadth_sma50"] = above.mean(axis=1) * 100
    out["breadth_crypto_sma50"] = above[crypto].mean(axis=1) * 100
    out["crypto_median_roc7"] = (closes[crypto].pct_change(7, fill_method=None) * 100).median(axis=1)
    return out


def attach_open_interest(sig: pd.DataFrame, snaps: pd.DataFrame) -> pd.DataFrame:
    """OI change (in coins, so price moves don't masquerade as OI) over 1/3/7 days,
    OI ÷ daily volume, and log volume — from the snapshots around the fire."""
    s = snaps.assign(oi_coin=snaps["open_interest_usd"] / snaps["mark_px"])
    s = s[["symbol", "t", "oi_coin", "open_interest_usd", "day_ntl_vlm_usd"]].sort_values("t")
    q = sig[["symbol", "fired_at"]].rename(columns={"fired_at": "t"}).reset_index().sort_values("t")
    now = pd.merge_asof(q, s, on="t", by="symbol", direction="backward",
                        tolerance=pd.Timedelta("2h")).set_index("index")
    out = pd.DataFrame(index=sig.index)
    for hours, name in ((24, "1d"), (72, "3d"), (168, "7d")):
        back = q.assign(t=q["t"] - pd.Timedelta(hours=hours)).sort_values("t")
        past = pd.merge_asof(back, s, on="t", by="symbol", direction="nearest",
                             tolerance=pd.Timedelta("3h")).set_index("index")
        out[f"oi_chg_{name}"] = (now["oi_coin"] / past["oi_coin"].reindex(now.index) - 1) * 100
    out["oi_to_vol"] = now["open_interest_usd"] / now["day_ntl_vlm_usd"]
    out["log_vol_usd"] = np.log10(now["day_ntl_vlm_usd"])
    return sig.join(out)


def attach_funding(sig: pd.DataFrame, funding: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Funding before the fire (as APR %) and the carry actually paid over the 7d hold.

    ``carry_7d`` is the % of notional a LONG pays over the next 168 hours (a short
    receives it); NaN until the whole window has been observed.
    """
    cols = {k: np.full(len(sig), np.nan) for k in ("fund_24h_apr", "fund_7d_apr", "carry_7d")}
    pos = {ix: i for i, ix in enumerate(sig.index)}
    for symbol, idx in sig.groupby("symbol").groups.items():
        f = funding.get(symbol)
        if f is None or f.empty:
            continue
        t = f["ts"].to_numpy(dtype="datetime64[ns]")
        cum = np.concatenate([[0.0], np.cumsum(f["funding"].to_numpy())])
        for ix in idx:
            fired = np.datetime64(sig.at[ix, "fired_at"].tz_convert(None), "ns")
            j = np.searchsorted(t, fired, side="left")            # records strictly before fire
            for hours, name in ((24, "fund_24h_apr"), (168, "fund_7d_apr")):
                k = np.searchsorted(t, fired - np.timedelta64(hours, "h"), side="left")
                if j > k:
                    cols[name][pos[ix]] = (cum[j] - cum[k]) / (j - k) * 24 * 365 * 100
            e = np.searchsorted(t, fired + np.timedelta64(168, "h"), side="left")
            if j < e < len(t):
                cols["carry_7d"][pos[ix]] = (cum[e] - cum[j]) * 100
    return sig.assign(**cols)


# ---------------------------------------------------------------- after the fire

# Some hypotheses act a few bars AFTER the fire ("short it if MACD still hasn't crossed
# by bar 3"). Their outcome has to be measured from that later entry: scored from the
# fire, the rule would be conditioning on its own first bars, which is look-ahead.
# Bar 3 is the third daily close at or after the fire, the close of fire day + 2. That
# matches the closed-candle history test (docs/profit_strategies.md C6a).
LATE_BAR = 3


def crossed_by_bar3(sig: pd.DataFrame, hist: dict[str, pd.Series]) -> pd.Series:
    """1.0 if the MACD histogram crossed zero (MACD through its signal line) on any of
    the first ``LATE_BAR`` daily closes at or after the fire, 0.0 if it didn't, and NaN
    until all those bars have closed. ``hist`` maps symbol -> closed-bar histogram
    indexed by 'YYYY-MM-DD'.

    A FORWARD quantity: use it only to choose a late entry, never as a fire-time feature.
    """
    combined = pd.concat(hist, names=["symbol", "day"])
    bars = np.column_stack([
        combined.reindex(pd.MultiIndex.from_arrays([sig["symbol"], _shift_day(sig["day"], i)])).to_numpy()
        for i in range(LATE_BAR)])
    bullish = (sig["direction"] == "bullish").to_numpy()[:, None]
    crossed = np.where(bullish, bars >= 0, bars <= 0).any(axis=1)
    return pd.Series(np.where(np.isnan(bars).any(axis=1), np.nan, crossed), index=sig.index)


def attach_late_entry(sig: pd.DataFrame, snaps: pd.DataFrame, candles: dict[str, pd.DataFrame],
                      horizons=HORIZONS) -> pd.DataFrame:
    """``alpha_from_bar3_Nd``: the alpha of entering at the close of bar 3 instead of at
    the fire, exiting on the same bar as ``px_Nd``. The benchmark is the same-run,
    same-class mean over those same bars, so a random late entry also scores zero."""
    close_of = daily_closes(snaps, candles)

    def forward(symbols: pd.Series, days: pd.Series, n: int) -> np.ndarray:
        at = lambda k: close_of.reindex(pd.MultiIndex.from_arrays([symbols, _shift_day(days, k)])).to_numpy()  # noqa: E731
        return at(n) / at(LATE_BAR - 1) - 1

    sign = np.where(sig["direction"] == "bullish", 1.0, -1.0)
    out = {}
    for n in (h for h in horizons if h > LATE_BAR):
        b = snaps[["run_id", "asset_class"]].assign(bench=forward(snaps["symbol"], snaps["day"], n))
        grouped = b.groupby(["run_id", "asset_class"])["bench"]
        bench = grouped.mean().where(grouped.count() >= MIN_BENCH_SYMBOLS).rename("bench").reset_index()
        aligned = sig[["run_id", "asset_class"]].merge(bench, on=["run_id", "asset_class"], how="left")
        out[f"alpha_from_bar3_{n}d"] = sign * (forward(sig["symbol"], sig["day"], n) - aligned["bench"].to_numpy()) * 100
    return sig.assign(**out)


def _closed_bar_hist(candles: pd.DataFrame) -> pd.Series:
    df = candles.sort_values("ts")
    return pd.Series(macd(df["close"])["hist"].to_numpy(), index=df["ts"].dt.strftime("%Y-%m-%d"))


# ---------------------------------------------------------------- assembly

def build(conn: sqlite3.Connection, candles: dict | None = None, funding: dict | None = None,
          gap_days: int = 1, oos_from: str | None = None) -> pd.DataFrame:
    """The full research frame. Indicator and funding columns are present only when
    those caches are passed in. Alpha works from the database alone, but carries a
    survivorship bias without candles (see ``benchmark``)."""
    sig = load_signals(conn)
    snaps = load_snapshots(conn)
    df = attach_outcomes(sig, benchmark(snaps, candles))
    df = assign_episodes(df, gap_days)
    df = attach_open_interest(df, snaps)
    if candles:
        classes = snaps.groupby("symbol")["asset_class"].first().to_dict()
        df = attach_indicators(df, candles)
        df = df.join(_at_previous_day(df, market_context(candles, classes)))
        df = attach_late_entry(df, snaps, candles)
        df["crossed_by_bar3"] = crossed_by_bar3(df, {s: _closed_bar_hist(c) for s, c in candles.items()})
    if funding:
        df = attach_funding(df, funding)
    df["oos"] = df["fired_at"] >= pd.Timestamp(oos_from, tz="UTC") if oos_from else False
    return df
