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


RULES: dict[str, Callable[[pd.DataFrame], pd.Series]] = {
    "v1 (retired)": lambda d: _bear(d) & (d.red < V1_MAX_REDUCTION)
        & (d.peak_pct < V1_MAX_PEAK_PCT) & (d.top_n >= V1_MIN_TOP_N),
    "v2 (live)": lambda d: _bull(d) & (d.atr > 0) & (d.sig_atr < CONFIDENCE_MAX_SIG_ATR)
        & (d.red < CONFIDENCE_MAX_REDUCTION),
    "v3 bullish": lambda d: _bull(d) & (d.peak_pct <= V3_BULL_MAX_PEAK_PCT)
        & (d.red < V3_BULL_MAX_REDUCTION),
    "v3 bearish (shadow)": lambda d: _bear(d) & (d.peak_pct <= V3_BEAR_MAX_PEAK_PCT),
    "record-peak warning": lambda d: _bull(d) & (d.peak_pct >= RECORD_PEAK_PCT),
    # Historical rebuild: the peak_pct effect sits in the lowest quarter (+1.51% 2023-26).
    "bullish peak_pct <= 25": lambda d: _bull(d) & (d.peak_pct <= 25),
    "all bullish": _bull,
    "bullish crypto": _bull_crypto,
    # trading_strategy.md 3G and 3H, tracked so the watchlist can test them.
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
    "all bearish": _bear,
    "everything": lambda d: d["direction"].notna(),
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
)
