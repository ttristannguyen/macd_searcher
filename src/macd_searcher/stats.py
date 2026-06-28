"""Robust summary statistics for outcome distributions.

SQLite has no median, percentile, or standard-deviation functions, and trading
returns are fat-tailed and right-skewed — so a plain mean is misleading. These
helpers describe the whole distribution with quantiles (median + spread) and a
*winsorized* mean (extremes capped at the p5/p95 fence, not deleted) so a few
moonshots can't dominate without throwing the tail away.

This is the project-specific aggregation; the standard stats (Wilson CI,
bootstrap, Spearman) come from `scipy.stats` directly — see docs/research.md §0.

Pure functions over plain sequences of floats: no DB or web import, so the
dashboard API and any offline analysis script can share them.
"""

from __future__ import annotations

from typing import Iterable, Optional

import numpy as np

# Quantiles reported for every distribution: tails (10/90) + the IQR (25/75)
# + the median (50).
QUANTILES = (10, 25, 50, 75, 90)


def summarize(values: Iterable[Optional[float]], winsor: float = 0.05) -> Optional[dict]:
    """Quantile + robust-mean summary of `values` (None/NaN dropped).

    Returns None if there is nothing to summarize. `winsor` is the fraction
    clipped from *each* tail before the winsorized mean (0.05 -> clip to the
    5th/95th percentile). All values are in the input's natural units; callers
    scale to percent points if they want.
    """
    arr = np.asarray([v for v in values if v is not None], dtype=float)
    arr = arr[~np.isnan(arr)]
    n = int(arr.size)
    if n == 0:
        return None

    p10, p25, p50, p75, p90 = (float(x) for x in np.percentile(arr, QUANTILES))
    lo, hi = np.percentile(arr, [winsor * 100, (1 - winsor) * 100])
    return {
        "n": n,
        "min": float(arr.min()),
        "p10": p10,
        "p25": p25,
        "median": p50,
        "p75": p75,
        "p90": p90,
        "max": float(arr.max()),
        "mean": float(arr.mean()),
        "winsorized_mean": float(np.clip(arr, lo, hi).mean()),
        # Sample std (ddof=1); undefined for a single point.
        "std": float(arr.std(ddof=1)) if n > 1 else None,
    }
