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

from datetime import date
from typing import Iterable, Optional, Sequence

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


# ---------- dependence-aware inference ----------
#
# Signals are not independent: forward windows overlap, many symbols fire on the
# same day, and ~69% of deduped signals re-fire the next day. Resampling single rows
# reports significance that is not there. Group repeat fires into episodes, and
# resample whole blocks (weeks) — see docs/research_method.md.

CI_LEVEL = 0.95


def block_ci(values, blocks, n_boot: int = 2000, seed: int = 0) -> tuple[float, float, float]:
    """(mean, lo, hi), resampling whole blocks with replacement.

    Vectorised over per-block sums and counts, so it is cheap enough to run on every
    cell of a report or a dashboard panel. NaN values are dropped; the interval is
    NaN with fewer than 3 blocks.
    """
    v = np.asarray(values, dtype=float)
    b = np.asarray(blocks)
    keep = ~np.isnan(v)
    v, b = v[keep], b[keep]
    if len(v) == 0:
        return float("nan"), float("nan"), float("nan")
    keys, inv = np.unique(b, return_inverse=True)
    if len(keys) < 3:
        return float(v.mean()), float("nan"), float("nan")
    sums = np.bincount(inv, weights=v)
    counts = np.bincount(inv)
    idx = np.random.default_rng(seed).integers(0, len(keys), size=(n_boot, len(keys)))
    boot = sums[idx].sum(axis=1) / counts[idx].sum(axis=1)
    tail = (1 - CI_LEVEL) / 2 * 100
    lo, hi = np.percentile(boot, [tail, 100 - tail])
    return float(v.mean()), float(lo), float(hi)


def episodes(symbols: Sequence[str], directions: Sequence[str], days: Sequence[str],
             gap_days: int = 1) -> tuple[list[str], list[bool]]:
    """Group repeat fires into episodes; returns ``(episode_id, is_first_fire)`` per
    input row, in input order.

    A fire whose same-symbol, same-direction predecessor fired within ``gap_days``
    calendar days (``days`` are 'YYYY-MM-DD') continues that episode.
    """
    n = len(symbols)
    order = sorted(range(n), key=lambda i: (symbols[i], directions[i], days[i]))
    last: dict[tuple[str, str], date] = {}
    count: dict[tuple[str, str], int] = {}
    ids, starts = [""] * n, [False] * n
    for i in order:
        key = (symbols[i], directions[i])
        d = date.fromisoformat(days[i])
        prev = last.get(key)
        start = prev is None or (d - prev).days > gap_days
        if start:
            count[key] = count.get(key, 0) + 1
        ids[i] = f"{symbols[i]}|{directions[i]}|{count[key]}"
        starts[i] = start
        last[key] = d
    return ids, starts
