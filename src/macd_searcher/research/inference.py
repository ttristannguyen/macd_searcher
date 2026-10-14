"""Statistics for the research pipeline — numbers in, numbers out, no I/O.

Every interval here is a BLOCK bootstrap. Signals are not independent: forward
windows overlap, many symbols fire on the same day, and the same symbol re-fires
on consecutive days. Resampling individual rows reports significance that is not
there. Resample whole weeks for row-level stats, or collapse to one number per
episode first (``per_episode``) — preferably both.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

LEVEL = 0.95


def block_ci(values, blocks, n_boot: int = 2000, seed: int = 0) -> tuple[float, float, float]:
    """(mean, lo, hi), resampling whole blocks with replacement.

    Vectorised over per-block sums and counts, so it is cheap enough to run on
    every cell of a report. Intervals are NaN with fewer than 3 blocks.
    """
    v = np.asarray(values, dtype=float)
    b = np.asarray(blocks)
    keep = ~np.isnan(v)
    v, b = v[keep], b[keep]
    if len(v) == 0:
        return np.nan, np.nan, np.nan
    keys, inv = np.unique(b, return_inverse=True)
    if len(keys) < 3:
        return float(v.mean()), np.nan, np.nan
    sums = np.bincount(inv, weights=v)
    counts = np.bincount(inv)
    idx = np.random.default_rng(seed).integers(0, len(keys), size=(n_boot, len(keys)))
    boot = sums[idx].sum(axis=1) / counts[idx].sum(axis=1)
    tail = (1 - LEVEL) / 2 * 100
    lo, hi = np.percentile(boot, [tail, 100 - tail])
    return float(v.mean()), float(lo), float(hi)


def spearman_ic(x, y, blocks, n_boot: int = 1000, seed: int = 0) -> tuple[float, float, float, int]:
    """(rho, lo, hi, n): rank correlation of a feature with an outcome, with a
    block-bootstrap interval."""
    x, y, b = (np.asarray(a) for a in (x, y, blocks))
    keep = ~(pd.isna(x) | pd.isna(y))
    x, y, b = x[keep].astype(float), y[keep].astype(float), b[keep]
    if len(x) < 30:
        return np.nan, np.nan, np.nan, len(x)
    rho = spearmanr(x, y).statistic
    keys = np.unique(b)
    members = [np.flatnonzero(b == k) for k in keys]
    rng = np.random.default_rng(seed)
    boot = []
    for _ in range(n_boot):
        k = np.concatenate([members[i] for i in rng.integers(0, len(keys), len(keys))])
        boot.append(spearmanr(x[k], y[k]).statistic)
    tail = (1 - LEVEL) / 2 * 100
    lo, hi = np.nanpercentile(boot, [tail, 100 - tail])
    return float(rho), float(lo), float(hi), len(x)


def per_episode(df: pd.DataFrame, value: str, keep_first: tuple[str, ...] = ()) -> pd.DataFrame:
    """One row per episode: the mean of ``value`` across its fires, plus the week
    and in/out-of-sample flag of its FIRST fire (and any ``keep_first`` columns,
    e.g. the feature as it stood at the first alert)."""
    first = ["week", "month", "oos", *keep_first]
    agg = {value: (value, "mean"), **{c: (c, "first") for c in first}}
    return df.sort_values("fired_at").groupby("episode").agg(**agg)


def bh_qvalues(p) -> np.ndarray:
    """Benjamini–Hochberg q-values, for scanning many features at once."""
    p = np.asarray(p, dtype=float)
    order = np.argsort(p)
    ranked = p[order] * len(p) / (np.arange(len(p)) + 1)
    q = np.minimum.accumulate(ranked[::-1])[::-1].clip(max=1)
    out = np.empty_like(q)
    out[order] = q
    return out
