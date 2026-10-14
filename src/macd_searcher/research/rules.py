"""Named cohorts the report tracks, and the pre-registered watchlist.

Each rule is a mask over the research frame. v2's and v3's thresholds are imported
from ``signals.py`` so the report can never disagree with the dashboard or the live
marker. v1's are written out here because it is retired.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

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


RULES: dict[str, Callable[[pd.DataFrame], pd.Series]] = {
    "v1 (retired)": lambda d: _bear(d) & (d.red < V1_MAX_REDUCTION)
        & (d.peak_pct < V1_MAX_PEAK_PCT) & (d.top_n >= V1_MIN_TOP_N),
    "v2 (live)": lambda d: _bull(d) & (d.atr > 0) & (d.sig_atr < CONFIDENCE_MAX_SIG_ATR)
        & (d.red < CONFIDENCE_MAX_REDUCTION),
    "v3 bullish": lambda d: _bull(d) & (d.peak_pct <= V3_BULL_MAX_PEAK_PCT)
        & (d.red < V3_BULL_MAX_REDUCTION),
    "v3 bearish (shadow)": lambda d: _bear(d) & (d.peak_pct <= V3_BEAR_MAX_PEAK_PCT),
    "record-peak warning": lambda d: _bull(d) & (d.peak_pct >= RECORD_PEAK_PCT),
    "all bullish": _bull,
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
    expect_sign: int          # +1: alpha should be positive; -1: negative
    on_confirm: str


WATCHLIST: tuple[Check, ...] = (
    Check("v3 bullish", "Does the v3 bullish leg keep positive alpha out of sample?",
          +1, "promote v3 bullish from shadow to the live marker"),
    Check("v3 bearish (shadow)", "Does the bearish low-peak leg hold at episode level?",
          +1, "add the bearish leg to v3"),
    Check("record-peak warning", "Do record-peak bullish signals keep underperforming?",
          -1, "keep the warning; consider making it a gate"),
    Check("v2 (live)", "Has v2 developed any selection edge?",
          +1, "re-examine before retiring v2"),
)
