"""Named cohorts the report tracks, and the pre-registered watchlist.

Each rule is a mask over the research frame. v2's and v3's thresholds are imported
from ``signals.py`` so the report can never disagree with the dashboard or the live
marker. v1's are written out here because it is retired.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np
import pandas as pd

from ..signals import (
    CONFIDENCE_MAX_REDUCTION,
    CONFIDENCE_MAX_SIG_ATR,
    CONFIDENCE_V3_BEAR_MAX_PEAK_PCT as V3_BEAR_MAX_PEAK_PCT,
    CONFIDENCE_V3_MAX_PEAK_PCT as V3_BULL_MAX_PEAK_PCT,
    CONFIDENCE_V3_MAX_REDUCTION as V3_BULL_MAX_REDUCTION,
    RECORD_PEAK_PCT,
)

# v1, retired 2026-09 (see docs/confidence_v2.md for its thresholds' provenance).
V1_MAX_REDUCTION, V1_MAX_PEAK_PCT, V1_MIN_TOP_N = 0.6, 40, 3


def _bull(d: pd.DataFrame) -> pd.Series:
    return d["direction"] == "bullish"


def _bear(d: pd.DataFrame) -> pd.Series:
    return d["direction"] == "bearish"


def _col(d: pd.DataFrame, name: str) -> pd.Series:
    """A candle-derived column, or all-NaN when the report ran without candles -
    so those rules come out empty instead of crashing the report."""
    return d[name] if name in d else pd.Series(np.nan, index=d.index)


def _bull_crypto(d: pd.DataFrame) -> pd.Series:
    return _bull(d) & (d["asset_class"] == "crypto")


# S&P 500 / Nasdaq-100 members among the xyz equity perps (clear cases only, as of
# 2026-10; ARM, SNDK, TSM and DKNG left out as uncertain). Hand-kept: extend it as
# the DEX lists more index names.
US_INDEX_EQUITIES = frozenset({
    "AAPL", "AMAT", "AMD", "AMZN", "ASML", "AVGO", "BX", "COIN", "COST", "CRWD", "DELL", "GOOGL",
    "HOOD", "IBM", "INTC", "LLY", "META", "MRNA", "MRVL", "MSFT", "MSTR", "MU", "NFLX", "NOW",
    "NVDA", "ORCL", "PLTR", "QCOM", "TSLA", "WDC",
})


def _us_index_equity(d: pd.DataFrame) -> pd.Series:
    return (d["asset_class"] == "equity") & d["symbol"].str.split(":").str[-1].isin(US_INDEX_EQUITIES)


def _crypto_pullback(d: pd.DataFrame) -> pd.Series:
    return _bear(d) & (d["asset_class"] == "crypto") & (d.peak_pct >= 50)


def _bull_deep(d: pd.DataFrame) -> pd.Series:
    return _bull(d) & (d.peak_pct > 50) & (d.peak_pct < 100)


def _first(d: pd.DataFrame) -> pd.Series:
    return d["episode_start"].astype(bool)


def _v2(d: pd.DataFrame) -> pd.Series:
    return _bull(d) & (d.atr > 0) & (d.sig_atr < CONFIDENCE_MAX_SIG_ATR) & (d.red < CONFIDENCE_MAX_REDUCTION)


def _v2_odd_day(d: pd.DataFrame) -> pd.Series:
    """v2 fires on a day v2 fired on at most 5 symbols: no market-wide cluster, so the
    pick is a selection, not the whole market. Counted over the rows given (the frame is
    one row per symbol per day; the watchlist passes only rows that have an alpha)."""
    v2 = _v2(d)
    return v2 & (v2.groupby(d["day"]).transform("sum") <= 5)


RULES: dict[str, Callable[[pd.DataFrame], pd.Series]] = {
    "v1 (retired)": lambda d: _bear(d) & (d.red < V1_MAX_REDUCTION)
        & (d.peak_pct < V1_MAX_PEAK_PCT) & (d.top_n >= V1_MIN_TOP_N),
    "v2 (live)": _v2,
    # 2026-10-18 pass: v2 on days without a cluster of v2 fires (market bottoms).
    "v2 on an odd day (<= 5 v2 fires)": _v2_odd_day,
    "v3 bullish": lambda d: _bull(d) & (d.peak_pct <= V3_BULL_MAX_PEAK_PCT)
        & (d.red < V3_BULL_MAX_REDUCTION),
    "v3 bearish (shadow)": lambda d: _bear(d) & (d.peak_pct <= V3_BEAR_MAX_PEAK_PCT),
    "record-peak warning": lambda d: _bull(d) & (d.peak_pct >= RECORD_PEAK_PCT),
    # Historical rebuild: the peak_pct effect sits in the lowest quarter (+1.51% 2023-26).
    "bullish peak_pct <= 25": lambda d: _bull(d) & (d.peak_pct <= 25),
    "all bullish": _bull,
    "bullish crypto": _bull_crypto,
    # The v2 plan's 3G and 3H (trading_strategy.md appendix), tracked so the watchlist can test them.
    "BTC downtrend (bullish crypto)": lambda d: _bull_crypto(d) & (_col(d, "btc_signal_line") < 0),
    "ATR expanding (bullish crypto)": lambda d: _bull_crypto(d) & (_col(d, "atr_change_30") > 1.10),
    # Episode structure (2026-10-15 dataset pass, docs/research_log.md).
    "bearish repeat fires": lambda d: _bear(d) & ~d["episode_start"].astype(bool),
    "bullish first fires": lambda d: _bull(d) & d["episode_start"].astype(bool),
    "bullish first fire at 00:00": lambda d: _bull(d) & d["episode_start"].astype(bool)
        & (d["fired_at"].dt.hour == 0),
    # A strong uptrend (positive excursion in the top half of the asset's own) whose
    # momentum has cooled: a pullback in a leader, tested as a LONG (2026-10-16 pass).
    "bearish pullback (peak_pct >= 50)": lambda d: _bear(d) & (d.peak_pct >= 50),
    # 2026-10-18 pass: the signal line (the Telegram row's `sig`) as the trend-strength
    # gauge instead of, and on top of, peak_pct. Cut 0.5 fixed on 2023-25 history.
    "bearish high sig (sig_atr >= 0.5)": lambda d: _bear(d) & (d.atr > 0) & (d.sig_atr >= 0.5),
    "bearish pullback + high sig": lambda d: _bear(d) & (d.peak_pct >= 50) & (d.atr > 0) & (d.sig_atr >= 0.5),
    # 2026-10-19 pass: the same trades on strong assets instead of alts.
    "crypto pullback": _crypto_pullback,
    "crypto pullback above SMA200": lambda d: _crypto_pullback(d) & (_col(d, "dist_sma200_atr") > 0),
    "v3 bullish, S&P 500 / Nasdaq-100": lambda d: _bull(d) & _us_index_equity(d)
        & (d.peak_pct <= V3_BULL_MAX_PEAK_PCT) & (d.red < V3_BULL_MAX_REDUCTION),
    # B3's short leg in docs/profit_strategies.md: deep, often coin-specific selling.
    "bullish 50 < peak_pct < 100": _bull_deep,
    # 2026-10-24 pass: early recovery (above SMA50, still below SMA200), where that short failed.
    "bullish 50 < peak_pct < 100, early recovery": lambda d: _bull_deep(d)
        & (_col(d, "dist_sma50_atr") > 0) & (_col(d, "dist_sma200_atr") <= 0),
    # 2026-10-25 pass: crowded longs going into the dip (baseline funding is ~11% APR).
    "bullish, 7d funding >= 15% APR": lambda d: _bull(d) & (_col(d, "fund_7d_apr") >= 15),
    # B3's short legs as traded: crypto, first fire per episode (docs/exit_research.md).
    "crypto bearish peak_pct <= 25, first fires": lambda d: _bear(d) & (d["asset_class"] == "crypto")
        & (d.peak_pct <= 25) & _first(d),
    "crypto bullish 50 < peak_pct < 100, first fires": lambda d: _bull_deep(d) & (d["asset_class"] == "crypto")
        & _first(d),
    # 2026-10-28 pass: B3's long leg L2 by peak_pct band. At 14d, only the 75-<100 band
    # earned alpha. Record peaks gave alpha in week 1 and lost it in week 2.
    "crypto pullback, first fires": lambda d: _crypto_pullback(d) & _first(d),
    "crypto pullback peak_pct >= 75, first fires": lambda d: _crypto_pullback(d) & (d.peak_pct >= 75) & _first(d),
    "crypto pullback 75 <= peak_pct < 100, first fires": lambda d: _crypto_pullback(d) & (d.peak_pct >= 75)
        & (d.peak_pct < RECORD_PEAK_PCT) & _first(d),
    "all bearish": _bear,
    "everything": lambda d: d["direction"].notna(),
}

# Rules that also use what happened AFTER the fire. Scored from the fire, they would
# condition on their own first bars (an uncrossed fire has by construction fallen), so
# they are kept out of RULES and the cohort table. A check may use one only with the
# late-entry metric that starts where its condition is known (AFTER_FIRE_METRIC).
AFTER_FIRE_RULES: dict[str, Callable[[pd.DataFrame], pd.Series]] = {
    # 2026-10-23 (profit_strategies.md C6a): the uncrossed deep fires carry the drift.
    "bullish 50 < peak_pct < 100, uncrossed at bar 3": lambda d: _bull_deep(d) & (_col(d, "crossed_by_bar3") == 0),
    # 2026-10-27 (exit_research.md): a pullback long whose coin then falls into a deep dip.
    "crypto pullback, first fires, deep dip by day 13": lambda d: _crypto_pullback(d) & _first(d)
        & _col(d, "deep_dip_day").notna(),
}
AFTER_FIRE_METRIC = {
    "bullish 50 < peak_pct < 100, uncrossed at bar 3": "alpha_from_bar3",
    "crypto pullback, first fires, deep dip by day 13": "alpha_from_dip",
}


@dataclass(frozen=True)
class Check:
    """A hypothesis written down BEFORE the next look at the data, with the result
    that would confirm it. Testing these first, before any new search, is what keeps
    repeated passes over the same database from fitting noise."""

    rule: str
    question: str
    expect_sign: int          # +1: the measure should be positive; -1: negative
    on_confirm: str
    # The day the hypothesis was written down. A check is scored ONLY on fires from
    # this date on: anything earlier was seen when the hypothesis was formed, and
    # re-confirming on it is circular.
    registered: str
    # Which outcome column ("alpha", "r" for raw, "market"). With `versus`, the
    # measure is the DIFFERENCE between this rule and the versus rule's other rows -
    # how timing questions are asked, since timing is invisible to alpha.
    metric: str = "alpha"
    versus: str | None = None
    # "discovery": the live data must confirm it (whole interval on the expected side).
    # "monitor": already confirmed elsewhere (docs/historical_rebuild.md), so live data
    # only has to not contradict it — it acts once it has enough episodes.
    role: str = "discovery"
    # Days held. None = the report's --horizon (7 by default). Set it when the
    # hypothesis itself is about a holding period. Live outcomes stop at 14d; 21d
    # comes from closed candles (dataset.CANDLE_HORIZONS).
    horizon: int | None = None


WATCHLIST: tuple[Check, ...] = (
    Check("v3 bullish", "Does the v3 bullish leg keep positive alpha out of sample? "
          "(history 2023-26: +0.58, confirmed)",
          +1, "promote v3 bullish from shadow to the live marker", registered="2026-10-14", role="monitor"),
    Check("v3 bearish (shadow)", "Does the bearish low-peak leg hold at episode level?",
          +1, "add the bearish leg to v3", registered="2026-10-14"),
    Check("record-peak warning", "Do record-peak bullish signals keep underperforming? "
          "(history 2023-26: +0.01, NOT reproduced)",
          -1, "keep the warning; consider making it a gate", registered="2026-10-14"),
    Check("v2 (live)", "Has v2 developed any selection edge?",
          +1, "re-examine before retiring v2", registered="2026-10-14"),
    # Added 2026-10-15 from the trading_strategy.md audit.
    Check("v2 (live)", "Is v2's TIMING real - do its fires catch bigger class moves than other bullish signals?",
          +1, "keep v2's conditions as a market-level entry trigger", metric="market", versus="all bullish", registered="2026-10-15"),
    Check("BTC downtrend (bullish crypto)", "Do bullish crypto fires in a BTC downtrend beat the rest, raw? "
          "(only 2 such stretches as of 2026-10-15)", +1, "admit the 3G regime filter",
          metric="r", versus="bullish crypto", registered="2026-10-15"),
    Check("ATR expanding (bullish crypto)", "Does 3H's ATR-expansion filter add selection beyond its timing?",
          +1, "keep 3H as a selection filter, not just a timing one", registered="2026-10-15"),
    # Added 2026-10-15 from the dataset pass (docs/research_log.md).
    Check("bearish repeat fires", "Are bearish re-fires worse shorts than first fires? "
          "(history 2023-26, paired: -1.01, confirmed)",
          -1, "act only on the first fire of a bearish episode", metric="alpha", versus="all bearish",
          registered="2026-10-15", role="monitor"),
    Check("bullish first fire at 00:00", "Do bullish first fires at 00:00 UTC keep underperforming intraday "
          "first fires? (in-sample -1.64 vs +0.29; no mechanism yet)", -1,
          "find the mechanism before acting on it", metric="alpha", versus="bullish first fires", registered="2026-10-15"),
    # Added 2026-10-16 from the historical rebuild: a threshold history suggested, which
    # history itself may not confirm — so it is a live discovery test.
    Check("bullish peak_pct <= 25", "Do bullish fires in the lowest peak_pct quarter beat their class? "
          "(history 2023-26: +1.51%; v3's <= 50 includes a ~0 band)", +1,
          "tighten v3's peak cut to 25", registered="2026-10-16"),
    # Alpha on bearish rows is short-side, so a good LONG shows up as a negative value.
    Check("bearish pullback (peak_pct >= 50)", "Are bearish fires after a strong uptrend good LONGS? "
          "(history 2023-26: long-side +1.39%, every year; seen on all periods at once, so not yet out of sample)",
          -1, "add a long-side 'pullback in a leader' marker", registered="2026-10-16"),
    # Added 2026-10-18 (docs/research_log.md). Bearish alpha is short-side: good LONGS read negative.
    Check("bearish high sig (sig_atr >= 0.5)", "Do bearish fires with the signal line >= 0.5 ATR keep "
          "trending up - good LONGS? (history: long-side +1.45 2023-25, +2.25 on the 2026H1 holdout; "
          "about half is generic momentum)", -1, "flag high-sig bearish fires as long candidates",
          registered="2026-10-18"),
    Check("bearish pullback + high sig", "Does sig >= 0.5 ATR add to the bearish pullback, as a long? "
          "(history, sig >= 0.5 minus < 0.5 within peak_pct >= 50: +0.80 / +2.59 / +0.26, every CI spans 0)",
          -1, "require both peak_pct and sig for the long-side marker", versus="bearish pullback (peak_pct >= 50)",
          registered="2026-10-18"),
    Check("v2 on an odd day (<= 5 v2 fires)", "Does v2 pick better assets when it is not part of a "
          "market-wide cluster? (history crypto: +0.67 [-0.35, +1.78]; live in-sample: -0.77, both span 0)",
          +1, "use v2 as a selection signal outside cluster days", registered="2026-10-18"),
    # Added 2026-10-18: holding periods from the peak_pct band pass (exploratory).
    Check("bullish peak_pct <= 25", "Does the low-peak bullish edge hold at 14d? "
          "(history 2023-26: +1.92% at 14d, +2.04% at 30d, vs +1.51% at 7d)", +1,
          "hold low-peak bullish longs ~14d rather than 7d", registered="2026-10-18", horizon=14),
    Check("v3 bearish (shadow)", "Is the bearish low-peak short good at 14d? "
          "(history 2023-26: +1.04% at 14d, every year; 7d was undecided)", +1,
          "consider a 14d hold for bearish low-peak shorts", registered="2026-10-18", horizon=14),
    # Added 2026-10-19: the same trades on strong assets instead of alts (docs/research_log.md).
    Check("crypto pullback above SMA200", "Is the crypto pullback a better LONG when the coin is above its "
          "200-day average? (history 2023-26: long alpha +1.66 vs +0.38 below; fire beats holding the "
          "same coin by +2.70)", -1, "require price above SMA200 for the long-side marker",
          versus="crypto pullback", registered="2026-10-19"),
    Check("v3 bullish, S&P 500 / Nasdaq-100", "Does v3 bullish pick winners among index equities? "
          "(live in-sample: +3.41 alpha, +4.28 over holding the same stock, 44 ep, one window; "
          "other equities -1.98)", +1, "trade v3 on index equities", registered="2026-10-19"),
    # Added 2026-10-23 (docs/profit_strategies.md C6a). Long-side alpha, so a good SHORT
    # reads negative. Entered at the bar-3 close, never scored from the fire.
    Check("bullish 50 < peak_pct < 100, uncrossed at bar 3", "Are deep bullish fires still uncrossed at "
          "bar 3 good SHORTS from there? (history 2023-26, first fires, bar 3 -> 14d: -1.08 [-1.72, -0.43]; "
          "crossed ones -0.15)", -1, "short B3's deep-bullish leg only once uncrossed at bar 3",
          registered="2026-10-23", metric="alpha_from_bar3", horizon=14),
    # Added 2026-10-24 (docs/research_log.md). Long-side alpha: a worse SHORT reads positive.
    Check("bullish 50 < peak_pct < 100, early recovery", "Is the deep-bullish short worse on coins above "
          "SMA50 but below SMA200? (history 2023-26, 14d long-side vs rest of the leg: +2.83 [-0.76, +6.03], "
          "220 ep; post hoc from a 2x2 cut, no mechanism)", +1,
          "find the mechanism, then drop early-recovery coins from B3's short leg",
          versus="bullish 50 < peak_pct < 100", registered="2026-10-24", horizon=14),
    # Added 2026-10-25 (docs/research_log.md): confidence_v3_research.md section 8's
    # out-of-sample funding effect, now with a fixed cut. Non-firing coins show no such effect.
    Check("bullish, 7d funding >= 15% APR", "Do bullish fires on coins whose longs paid >= 15% APR over the "
          "prior week underperform the rest of bullish fires? (live, rule - rest: Jun-Sep -1.60 [-3.89, +0.27], "
          "156 ep; Sep 19 - Oct 7 -6.37 [-9.82, -2.69], 49 ep; Oct 8-17 -4.96, 14 ep; all one falling market "
          "from September)", -1, "skip or short bullish fires with crowded funding",
          versus="all bullish", registered="2026-10-25"),
    # Added 2026-10-27 (docs/exit_research.md): exits for B3. Each is measured from the
    # 14d exit or the deep-dip close, never from the fire. Bearish alpha is short-side
    # and bullish long-side, so a good S2 short reads negative and a bad L2 long positive.
    Check("crypto bearish peak_pct <= 25, first fires", "Does B3's S1 short keep earning in the week after its "
          "14d exit? (history 2023-26, 14d -> 21d: +0.40 [-0.13, +0.91], every year)", +1,
          "hold S1 shorts 21 days", registered="2026-10-27", metric="alpha_from_14d", horizon=21),
    Check("crypto bullish 50 < peak_pct < 100, first fires", "Does B3's S2 short keep earning in the week after "
          "its 14d exit? (history 2023-26, 14d -> 21d, long-side: -0.38 [-0.92, +0.18], 3 of 4 years)", -1,
          "hold S2 shorts 21 days", registered="2026-10-27", metric="alpha_from_14d", horizon=21),
    Check("crypto pullback, first fires, deep dip by day 13", "Do pullback LONGS whose coin "
          "falls into a deep dip (hist < 0, state peak_pct >= 75) lose from there to the 14d exit? (history "
          "2023-26, long-side -1.19 [-2.02, -0.42], 31% of trades; -1.81 in 2023-24, -0.58 in 2025-26)", +1,
          "exit L2 longs on a deep dip", registered="2026-10-27", metric="alpha_from_dip", horizon=14),
    # Added 2026-10-28 (docs/research_log.md): B3's L2 long by peak_pct band, first fires.
    # Bearish alpha is short-side, so a better LONG reads negative.
    Check("crypto pullback 75 <= peak_pct < 100, first fires", "Is L2 a better 14d LONG in the 75-<100 band "
          "than in the rest of the leg? (closed-bar history to 2026-10, long-side: 75-<100 +2.24 [+0.73, +3.76], "
          "every year; 50-75 +0.19; records -0.12; band - rest +2.15 [+0.46, +3.90])", -1,
          "restrict L2 to 75 <= peak_pct < 100", versus="crypto pullback, first fires",
          registered="2026-10-28", horizon=14),
    Check("crypto pullback 75 <= peak_pct < 100, first fires", "Is the 75-<100 band a better 14d LONG than "
          "record peaks? (closed-bar history to 2026-10, long-side: records +1.48 at 7d, -0.12 at 14d; "
          "band - records at 14d +2.36 [-0.33, +5.07])", -1,
          "drop record peaks from L2", versus="crypto pullback peak_pct >= 75, first fires",
          registered="2026-10-28", horizon=14),
)
