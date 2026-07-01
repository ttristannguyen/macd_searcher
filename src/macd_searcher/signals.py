"""Signal detection.

Two stages, each per-asset:

  Stage 1 — histogram_flattening (earliest)
    MACD histogram (macd - signal_line) peaked above the noise floor and is
    now shrinking strictly toward zero. Fires before MACD itself crosses zero.

  Stage 3 — zero_line_proximity (latest)
    MACD is near zero AND |MACD| has been strictly shrinking. Three modes
    decide what "near" means: price_pct, atr, rank.

When an asset triggers both stages on the same bar, the highest-priority
(latest-stage) signal is returned, since later stages imply the earlier
one already fired.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Literal

import pandas as pd

from .config import AppConfig
from .indicators import atr, macd


log = logging.getLogger(__name__)

Stage = Literal["histogram_flattening", "zero_line_proximity"]
Direction = Literal["bullish", "bearish"]

_STAGE_PRIORITY: dict[Stage, int] = {
    "histogram_flattening": 1,
    "zero_line_proximity": 3,
}


@dataclass(frozen=True)
class Signal:
    name: str
    stage: Stage
    direction: Direction
    close: float
    macd: float
    hist: float
    # Stage 1 fields
    hist_peak: float | None = None
    reduction_from_peak: float | None = None
    # Stage 3 fields
    macd_pct_of_price: float | None = None
    atr_multiple: float | None = None


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


def _strictly_increasing(series: pd.Series) -> bool:
    if len(series) < 2:
        return False
    diffs = series.diff().iloc[1:]
    return bool((diffs > 0).all())


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


def _check_zero_line_proximity(
    name: str,
    close: float,
    macd_df: pd.DataFrame,
    atr_series: pd.Series | None,
    cfg: AppConfig,
) -> Signal | None:
    """Stage 3: MACD near zero AND |MACD| strictly shrinking.

    In rank mode, returns a candidate without applying a magnitude threshold
    — the cross-asset filter in `evaluate_all` keeps only the top-N.
    """
    macd_line = macd_df["macd"]
    lookback = cfg.signal.shrink_lookback
    if len(macd_line) < lookback + 1:
        return None

    last_macd = float(macd_line.iloc[-1])
    if last_macd == 0:
        return None

    recent = macd_line.iloc[-lookback:]

    # Direction: |MACD| must strictly shrink AND sign must imply approach to zero.
    if last_macd < 0 and _strictly_increasing(recent):
        direction: Direction = "bullish"
    elif last_macd > 0 and _strictly_decreasing(recent):
        direction = "bearish"
    else:
        return None

    abs_macd = abs(last_macd)
    pct = abs_macd / close if close > 0 else float("inf")
    atr_mult: float | None = None

    if cfg.signal.mode == "price_pct":
        if pct >= cfg.signal.price_pct_threshold:
            return None
    elif cfg.signal.mode == "atr":
        if atr_series is None or len(atr_series) == 0:
            return None
        last_atr = float(atr_series.iloc[-1])
        if last_atr <= 0:
            return None
        atr_mult = abs_macd / last_atr
        if atr_mult >= cfg.signal.atr_multiple:
            return None
    elif cfg.signal.mode == "rank":
        # No per-asset threshold; cross-asset filter selects top-N later.
        pass
    else:
        raise ValueError(f"Unknown signal.mode: {cfg.signal.mode!r}")

    return Signal(
        name=name,
        stage="zero_line_proximity",
        direction=direction,
        close=close,
        macd=last_macd,
        hist=float(macd_df["hist"].iloc[-1]),
        macd_pct_of_price=pct,
        atr_multiple=atr_mult,
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


def _detect_stages_for_asset(
    name: str,
    df: pd.DataFrame,
    cfg: AppConfig,
) -> list[Signal]:
    """Return all stages that fire for this asset on the latest bar (0–2 entries).

    Stage 1 and Stage 3 each choose whether to include today's forming bar
    (Stage 1 via `histogram_flattening.use_forming_candle`, Stage 3 via the
    global `candles.use_forming_candle`), so they may evaluate on different
    "latest" bars.
    """
    min_bars = cfg.macd.slow + max(
        cfg.signal.shrink_lookback,
        cfg.signal.histogram_flattening.peak_lookback,
    ) + 5
    if len(df) < min_bars:
        return []

    macd_df = macd(df["close"], cfg.macd.fast, cfg.macd.slow, cfg.macd.signal)
    atr_series = (
        atr(df["high"], df["low"], df["close"])
        if cfg.signal.zero_line_enabled and cfg.signal.mode == "atr"
        else None
    )
    last_is_forming = _last_bar_is_forming(df, cfg)

    sigs: list[Signal] = []
    if cfg.signal.histogram_flattening.enabled:
        m, c, _ = _view(
            df, macd_df, None, last_is_forming,
            cfg.signal.histogram_flattening.use_forming_candle,
        )
        s = _check_histogram_flattening(name, c, m, cfg)
        if s is not None:
            sigs.append(s)
    if cfg.signal.zero_line_enabled:
        m, c, a = _view(
            df, macd_df, atr_series, last_is_forming,
            cfg.candles.use_forming_candle,
        )
        s = _check_zero_line_proximity(name, c, m, a, cfg)
        if s is not None:
            sigs.append(s)
    return sigs


def evaluate_all(
    candles: dict[str, pd.DataFrame],
    cfg: AppConfig,
) -> list[Signal]:
    """Evaluate every asset; return one Signal per asset (its highest-priority stage).

    In rank mode for Stage 3, applies a global top-N filter on `macd_pct_of_price`
    BEFORE picking the highest-priority stage. Assets dropped from Stage 3 by
    the rank filter can still surface via Stage 1.
    """
    per_asset: dict[str, list[Signal]] = {}
    for name, df in candles.items():
        if df is None or df.empty:
            continue
        sigs = _detect_stages_for_asset(name, df, cfg)
        if sigs:
            per_asset[name] = sigs

    # Rank-mode global filter for Stage 3 only.
    if cfg.signal.zero_line_enabled and cfg.signal.mode == "rank":
        s3_with_pct: list[tuple[str, float]] = []
        for name, sigs in per_asset.items():
            for s in sigs:
                if s.stage == "zero_line_proximity" and s.macd_pct_of_price is not None:
                    s3_with_pct.append((name, s.macd_pct_of_price))
        s3_with_pct.sort(key=lambda x: x[1])
        keep = {n for n, _ in s3_with_pct[: cfg.signal.rank_top_n]}
        for name in list(per_asset.keys()):
            if name in keep:
                continue
            per_asset[name] = [s for s in per_asset[name] if s.stage != "zero_line_proximity"]
            if not per_asset[name]:
                del per_asset[name]

    out: list[Signal] = []
    for name, sigs in per_asset.items():
        out.append(max(sigs, key=lambda s: _STAGE_PRIORITY[s.stage]))
    log.info(
        "Signals: %d total (%d stage3, %d stage1)",
        len(out),
        sum(1 for s in out if s.stage == "zero_line_proximity"),
        sum(1 for s in out if s.stage == "histogram_flattening"),
    )
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
