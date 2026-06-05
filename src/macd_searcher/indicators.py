"""Technical indicators: MACD and ATR.

Both use pandas EWM directly — no TA-Lib dependency. MACD uses standard
exponential smoothing (`adjust=False`); ATR uses Wilder's smoothing (alpha = 1/N).
"""

from __future__ import annotations

import pandas as pd


def macd(
    close: pd.Series,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> pd.DataFrame:
    """Compute MACD, signal line, and histogram for a close-price series.

    Returns a DataFrame indexed like `close` with columns ``macd``, ``signal``, ``hist``.
    """
    if slow <= fast:
        raise ValueError(f"slow ({slow}) must be greater than fast ({fast})")
    if signal <= 0:
        raise ValueError(f"signal ({signal}) must be positive")

    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    hist = macd_line - signal_line

    return pd.DataFrame(
        {"macd": macd_line, "signal": signal_line, "hist": hist},
        index=close.index,
    )


def atr(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    period: int = 14,
) -> pd.Series:
    """Wilder's Average True Range.

    True Range = max(high-low, |high - prev_close|, |low - prev_close|).
    Wilder's smoothing is equivalent to EWM with alpha = 1/period, adjust=False,
    seeded with the simple mean of the first `period` TR values. We use the
    pandas EWM approximation (no explicit SMA seed) — converges within a few
    periods and is standard practice for live scanning.
    """
    if period <= 0:
        raise ValueError(f"period ({period}) must be positive")

    prev_close = close.shift(1)
    tr = pd.concat(
        [
            high - low,
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)

    return tr.ewm(alpha=1.0 / period, adjust=False).mean()
