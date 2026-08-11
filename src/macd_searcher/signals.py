"""Signal detection.

One stage, per-asset:

  Stage 1 — histogram_flattening
    MACD histogram (macd - signal_line) peaked above the noise floor and is
    now shrinking strictly toward zero. Fires before MACD itself crosses zero.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, replace
from statistics import median
from typing import Literal

import pandas as pd

from .config import AppConfig
from .indicators import atr, macd, rsi


log = logging.getLogger(__name__)

Stage = Literal["histogram_flattening"]
Direction = Literal["bullish", "bearish"]


@dataclass(frozen=True)
class Signal:
    name: str
    stage: Stage
    direction: Direction
    close: float
    macd: float
    hist: float
    hist_peak: float | None = None
    reduction_from_peak: float | None = None
    # 14-day Wilder RSI at fire time (0–100). Context for later signal-quality
    # analysis — not a firing condition. None if the value is NaN.
    rsi_14: float | None = None
    # This excursion's peak measured against the token's OWN prior same-sign tops
    # (see _peak_vs_history). Context, not a firing condition. ratio/pct are None
    # and top_n is 0 when the window holds no prior same-sign excursion.
    hist_peak_ratio: float | None = None
    hist_peak_pct: float | None = None
    hist_top_n: int = 0


# ---------- confidence marker ----------
#
# Thresholds measured on 3,050 scored signals (2026-06-06 → 08-06, prod_snapshot,
# after the peak-context backfill). Kept as constants rather than config knobs
# because they're empirical findings, not preferences — changing one should follow a
# re-measurement, not a whim. See docs/hist_peak_context.md.
#
# The rule marks 11.4% of signals: 70.1% win / +2.65% EV at 7d, against a 51.6% /
# +0.02% baseline. What earns the "confident" label is that it clears both bars in
# EACH regime half independently (1st: 73.6% / +3.88%, 2nd: 67.8% / +1.82%) — a rule
# that only works in a good tape isn't confidence, it's a bull market.
#
# Deliberately NOT included:
#   * RSI — every RSI-carrying signal falls in the second half (logging started
#     mid-sample), so it cannot be regime-tested at all, and within that one regime
#     it shows no monotonic relationship. Revisit after --backfill-rsi.
#   * bullish — the same filter reads 77.8% / +5.05% in the first half and
#     19.4% / -4.34% in the second. Marking those bold would mislead exactly when
#     it matters most.
CONFIDENCE_MAX_REDUCTION = 0.6   # shallower = caught earlier; deep fires are late
CONFIDENCE_MAX_PEAK_PCT = 40.0   # a modest peak by this token's own standards
CONFIDENCE_MIN_TOP_N = 3         # below this the peak baseline is not trustworthy


def is_high_confidence(s: Signal) -> bool:
    """True if this signal falls in the measured high-expectancy slice.

    Bearish only, shallow reduction, and a peak that's unremarkable for this token.
    Presentation-only today — it bolds the Telegram row; it does not gate firing.
    """
    return (
        s.direction == "bearish"
        and s.reduction_from_peak is not None
        and s.reduction_from_peak < CONFIDENCE_MAX_REDUCTION
        and s.hist_peak_pct is not None
        and s.hist_top_n >= CONFIDENCE_MIN_TOP_N
        and s.hist_peak_pct < CONFIDENCE_MAX_PEAK_PCT
    )


def _strictly_decreasing(series: pd.Series) -> bool:
    """True if every value is strictly less than the previous."""
    if len(series) < 2:
        return False
    diffs = series.diff().iloc[1:]
    return bool((diffs < 0).all())


def _consecutive_shrink_count(series: pd.Series) -> int:
    """Consecutive tail bars where ``|value|`` strictly decreases AND the sign
    does not flip (a zero-crossing resets the count). Pass the SIGNED series.

    e.g. [.., 0.5, 0.3, -0.1] → 0 (the last bar crossed zero), but
    [.., -0.5, -0.3, -0.2] → 2. Used for analytics logging.
    """
    vals = series.to_numpy()
    n = 0
    for i in range(len(vals) - 1, 0, -1):
        cur, prev = vals[i], vals[i - 1]
        same_sign = (cur > 0 and prev > 0) or (cur < 0 and prev < 0)
        if same_sign and abs(cur) < abs(prev):
            n += 1
        else:
            break
    return n


def _trailing_same_sign_len(hist_vals, last_hist: float) -> int:
    """Length of the trailing run of bars sharing ``last_hist``'s sign — i.e. the
    current same-sign histogram excursion. A zero value or sign flip ends it."""
    positive = last_hist > 0
    n = 0
    for v in reversed(hist_vals):
        if (v > 0) if positive else (v < 0):
            n += 1
        else:
            break
    return n


def _excursion_peak(hist: pd.Series, peak_lookback: int) -> float | None:
    """Signed peak of the current same-sign histogram excursion, capped at
    ``peak_lookback`` bars. None if the last bar is exactly zero.

    Confining the peak to the trailing same-sign run (since the last zero-cross)
    is what stops a stale peak from a prior excursion — or a green↔red flip —
    from inflating the reduction-from-peak. Shared by the Stage-1 detector and
    the per-asset snapshot metrics so the two never drift out of agreement.
    """
    last = float(hist.iloc[-1])
    if last == 0:
        return None
    seg = _trailing_same_sign_len(hist.to_numpy(), last)
    seg_window = hist.iloc[-min(seg, peak_lookback):]
    return float(seg_window.max()) if last > 0 else float(seg_window.min())


def _excursion_peaks(hist: pd.Series) -> tuple[list[float], list[float]]:
    """Magnitude of the extreme of every **completed** same-sign histogram
    excursion in the series, split by sign.

    Returns ``(bull_troughs, bear_peaks)`` — the |extremes| of the negative runs
    (where bullish signals fire) and of the positive runs (bearish). These are the
    token's own historical tops, the baseline a current excursion is judged against.

    The **trailing run is deliberately excluded**: it's the in-progress excursion
    the caller is measuring, so including it would compare it against itself. A
    zero value terminates a run and belongs to neither sign.
    """
    bull: list[float] = []
    bear: list[float] = []
    run_positive: bool | None = None   # None = not currently inside a run
    extreme = 0.0

    for raw in hist.to_numpy():
        v = float(raw)
        sign = None if v == 0 else v > 0
        if sign != run_positive:
            if run_positive is not None:            # close the run we just left
                (bear if run_positive else bull).append(abs(extreme))
            run_positive, extreme = sign, v
        elif sign is not None:                      # extend the current run
            extreme = max(extreme, v) if run_positive else min(extreme, v)

    # The trailing run is intentionally left unclosed — see docstring.
    return bull, bear


def _peak_vs_history(
    hist: pd.Series, direction: Direction
) -> tuple[float | None, float | None, int]:
    """How big is the current excursion's peak against this token's own tops?

    Returns ``(ratio, percentile, n)``:
      * ``ratio``      — current |peak| ÷ **median** prior same-sign |top|. Median,
        not mean, so one blow-off spike doesn't set the bar.
      * ``percentile`` — mid-rank percentile (0-100, tie-aware) of the current
        |peak| among those priors.
      * ``n``          — how many priors the baseline rests on; the trust gauge.

    Per-sign on purpose: a bearish signal is judged against prior *bear* tops,
    a bullish one against prior *bull* troughs — momentum is often asymmetric.
    ``(None, None, 0)`` when the window holds no prior same-sign excursion.
    """
    current = _excursion_peak(hist, len(hist))   # uncapped: the full excursion
    if current is None:
        return None, None, 0

    cur = abs(current)
    bull, bear = _excursion_peaks(hist)
    priors = bear if direction == "bearish" else bull
    n = len(priors)
    if n == 0:
        return None, None, 0

    med = median(priors)
    ratio = cur / med if med > 0 else None
    below = sum(1 for p in priors if p < cur)
    ties = sum(1 for p in priors if p == cur)
    return ratio, (below + 0.5 * ties) / n * 100.0, n


def _check_histogram_flattening(
    name: str,
    close: float,
    macd_df: pd.DataFrame,
    cfg: AppConfig,
) -> Signal | None:
    """Stage 1: histogram peaked above noise floor, now shrinking back toward zero.

    Peak-finding and the shrink check are confined to the **current same-sign
    excursion** (since the last zero-crossing), so a stale peak from a prior
    excursion can't inflate the reduction, and a green↔red flip can't be
    mistaken for shrinking toward zero.
    """
    s = cfg.signal.histogram_flattening
    hist = macd_df["hist"]
    if len(hist) < s.shrink_lookback + 1:
        return None

    last_hist = float(hist.iloc[-1])
    if last_hist == 0:
        return None  # exactly at zero is technically a cross, not "approaching"

    # Current same-sign run. Need enough same-sign bars to confirm a sustained
    # approach without a zero-crossing inside the shrink window.
    seg = _trailing_same_sign_len(hist.to_numpy(), last_hist)
    if seg < s.shrink_lookback:
        return None

    direction: Direction = "bearish" if last_hist > 0 else "bullish"

    # Peak = extreme of THIS excursion only, capped at peak_lookback bars.
    # last_hist != 0 was checked above, so the peak is never None here.
    peak = _excursion_peak(hist, s.peak_lookback)
    assert peak is not None

    abs_peak = abs(peak)
    abs_last = abs(last_hist)

    # Noise floor: peak must be meaningful relative to price.
    if close <= 0 or abs_peak / close < s.min_peak_pct_of_price:
        return None

    # Reduction from peak.
    if abs_last > (1.0 - s.min_reduction_from_peak) * abs_peak:
        return None

    # Strict shrink over last N bars — all same-sign now (guaranteed by seg check).
    recent_abs = hist.iloc[-s.shrink_lookback:].abs()
    if not _strictly_decreasing(recent_abs):
        return None

    reduction = 1.0 - (abs_last / abs_peak)

    return Signal(
        name=name,
        stage="histogram_flattening",
        direction=direction,
        close=close,
        macd=float(macd_df["macd"].iloc[-1]),
        hist=last_hist,
        hist_peak=peak,
        reduction_from_peak=reduction,
    )


_INTERVAL_MS: dict[str, int] = {
    "1m": 60_000,
    "5m": 300_000,
    "15m": 900_000,
    "1h": 3_600_000,
    "4h": 14_400_000,
    "1d": 86_400_000,
}


def _last_bar_is_forming(df: pd.DataFrame, cfg: AppConfig) -> bool:
    """True if the final bar's interval has not yet elapsed (still forming)."""
    if df.empty:
        return False
    bar_ms = _INTERVAL_MS.get(cfg.candles.interval, 86_400_000)
    last_open_ms = int(df["ts"].iloc[-1].timestamp() * 1000)
    now_ms = int(time.time() * 1000)
    return now_ms < last_open_ms + bar_ms


def _view(
    df: pd.DataFrame,
    macd_df: pd.DataFrame,
    atr_series: pd.Series | None,
    last_is_forming: bool,
    use_forming: bool,
) -> tuple[pd.DataFrame, float, pd.Series | None]:
    """Return (macd_df, close, atr) trimmed to the bars a detector should see.

    Because MACD/ATR use causal EWM (adjust=False), dropping the last row of the
    pre-computed frames yields exactly the closed-bar result — no recompute.
    """
    if last_is_forming and not use_forming:
        a = atr_series.iloc[:-1] if atr_series is not None else None
        return macd_df.iloc[:-1], float(df["close"].iloc[-2]), a
    return macd_df, float(df["close"].iloc[-1]), atr_series


def _detect_for_asset(
    name: str,
    df: pd.DataFrame,
    cfg: AppConfig,
) -> Signal | None:
    """Run the histogram_flattening detector on this asset's latest bar.

    Stage 1 reads today's still-forming daily bar when
    `histogram_flattening.use_forming_candle` is set, so it can join momentum
    intraday.
    """
    hf = cfg.signal.histogram_flattening
    if not hf.enabled:
        return None
    min_bars = cfg.macd.slow + max(hf.shrink_lookback, hf.peak_lookback) + 5
    if len(df) < min_bars:
        return None

    macd_df = macd(df["close"], cfg.macd.fast, cfg.macd.slow, cfg.macd.signal)
    last_is_forming = _last_bar_is_forming(df, cfg)
    m, c, _ = _view(df, macd_df, None, last_is_forming, hf.use_forming_candle)
    sig = _check_histogram_flattening(name, c, m, cfg)
    if sig is None:
        return None

    # 14-day RSI at the same fire bar. RSI uses causal Wilder smoothing, so the
    # closed-bar value is iloc[-2] when the forming bar was dropped, else iloc[-1].
    drop_forming = last_is_forming and not hf.use_forming_candle
    rsi_val = float(rsi(df["close"]).iloc[-2 if drop_forming else -1])

    # Peak-vs-history on `m["hist"]` — the exact series the detector just fired on,
    # so the current excursion is the one that triggered the signal.
    ratio, pct, top_n = _peak_vs_history(m["hist"], sig.direction)
    return replace(
        sig,
        rsi_14=None if pd.isna(rsi_val) else rsi_val,
        hist_peak_ratio=ratio,
        hist_peak_pct=pct,
        hist_top_n=top_n,
    )


def evaluate_all(
    candles: dict[str, pd.DataFrame],
    cfg: AppConfig,
) -> list[Signal]:
    """Evaluate every asset; return at most one histogram_flattening Signal each."""
    out: list[Signal] = []
    for name, df in candles.items():
        if df is None or df.empty:
            continue
        s = _detect_for_asset(name, df, cfg)
        if s is not None:
            out.append(s)
    log.info("Signals: %d stage1", len(out))
    return out


# ---------- per-asset metrics for analytics logging ----------


@dataclass(frozen=True)
class AssetMetrics:
    """Detector intermediates for one asset, computed every run for every asset
    (fired or not). Persisted to `asset_snapshots` so thresholds can be swept
    offline without re-fetching candles.

    Two perspectives are captured because the two detectors see different bars:
      - "confirmed" fields use closed bars only (Stage 3's view)
      - "live" fields include today's forming bar (Stage 1's view)
    """

    name: str
    # Confirmed (closed-bar) view — matches Stage 3
    close: float
    macd: float
    macd_signal: float
    hist: float
    atr: float | None
    macd_pct_of_price: float | None
    macd_shrinking_n_bars: int
    # Live (forming-bar) view — matches Stage 1
    live_close: float
    live_hist: float
    live_hist_pct_of_price: float | None
    hist_recent_peak: float | None
    hist_reduction_from_peak: float | None
    hist_shrinking_n_bars: int


def compute_asset_metrics(name: str, df: pd.DataFrame, cfg: AppConfig) -> AssetMetrics | None:
    """Compute detector intermediates for one asset, or None if too few bars."""
    min_bars = cfg.macd.slow + cfg.signal.histogram_flattening.peak_lookback + 5
    if len(df) < min_bars:
        return None

    macd_df = macd(df["close"], cfg.macd.fast, cfg.macd.slow, cfg.macd.signal)
    atr_series = atr(df["high"], df["low"], df["close"])
    last_is_forming = _last_bar_is_forming(df, cfg)

    # Confirmed (closed-bar) view.
    cm, c_close, c_atr = _view(df, macd_df, atr_series, last_is_forming, use_forming=False)
    c_macd = float(cm["macd"].iloc[-1])
    c_hist = float(cm["hist"].iloc[-1])
    c_signal = float(cm["signal"].iloc[-1])
    c_atr_val = float(c_atr.iloc[-1]) if c_atr is not None else None
    macd_pct = abs(c_macd) / c_close if c_close > 0 else None
    macd_shrink = _consecutive_shrink_count(cm["macd"])

    # Live (forming-bar) view.
    lm, l_close, _ = _view(df, macd_df, None, last_is_forming, use_forming=True)
    l_hist = float(lm["hist"].iloc[-1])
    l_hist_pct = abs(l_hist) / l_close if l_close > 0 else None

    # Same-sign-excursion peak — identical logic to the Stage-1 detector (via the
    # shared _excursion_peak), so a snapshot's reduction matches what would have
    # fired. NULL when the last bar is at/through zero (no valid current peak).
    peak = _excursion_peak(lm["hist"], cfg.signal.histogram_flattening.peak_lookback)
    reduction = 1.0 - abs(l_hist) / abs(peak) if peak not in (None, 0) else None
    hist_shrink = _consecutive_shrink_count(lm["hist"])

    return AssetMetrics(
        name=name,
        close=c_close,
        macd=c_macd,
        macd_signal=c_signal,
        hist=c_hist,
        atr=c_atr_val,
        macd_pct_of_price=macd_pct,
        macd_shrinking_n_bars=macd_shrink,
        live_close=l_close,
        live_hist=l_hist,
        live_hist_pct_of_price=l_hist_pct,
        hist_recent_peak=peak,
        hist_reduction_from_peak=reduction,
        hist_shrinking_n_bars=hist_shrink,
    )


def compute_all_metrics(candles: dict[str, pd.DataFrame], cfg: AppConfig) -> list[AssetMetrics]:
    """Compute metrics for every asset with enough history."""
    out: list[AssetMetrics] = []
    for name, df in candles.items():
        if df is None or df.empty:
            continue
        m = compute_asset_metrics(name, df, cfg)
        if m is not None:
            out.append(m)
    return out
