"""Tests for signal detection.

Fixtures are crafted to drive MACD/histogram into known states. The
amplitudes were chosen so the histogram peak clears the default noise floor
of 0.2% of price.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from macd_searcher.config import AppConfig
from macd_searcher.signals import (
    _check_histogram_flattening,
    _check_zero_line_proximity,
    _last_bar_is_forming,
    _view,
    evaluate_all,
)
from macd_searcher.indicators import macd as compute_macd


# ---------- Helpers ----------


def _df_from_close(prices: list[float]) -> pd.DataFrame:
    s = pd.Series(prices, dtype=float)
    return pd.DataFrame(
        {
            "ts": pd.date_range("2025-01-01", periods=len(prices), freq="1D", tz="UTC"),
            "open": s,
            "high": s,
            "low": s,
            "close": s,
            "volume": pd.Series([1.0] * len(prices)),
        }
    )


def _df_ending_today(prices: list[float]) -> pd.DataFrame:
    """OHLCV df whose final bar opens at today's 00:00 UTC (still forming)."""
    s = pd.Series(prices, dtype=float)
    end = pd.Timestamp.now(tz="UTC").normalize()  # today's midnight UTC
    return pd.DataFrame(
        {
            "ts": pd.date_range(end=end, periods=len(prices), freq="1D", tz="UTC"),
            "open": s,
            "high": s,
            "low": s,
            "close": s,
            "volume": pd.Series([1.0] * len(prices)),
        }
    )


def _rally_then_fade(rally_n: int = 30, step: float = 2.0, fade_n: int = 4) -> list[float]:
    """Flat prefix → strong linear rally → short decelerating fade.

    The flat prefix gives MACD time to warm up before the rally begins, so the
    end-of-series state is unaffected. Tuned so the histogram peaks during the
    rally and is still positive but well below the peak at the final bar
    (Stage 1 bearish setup).
    """
    prefix = [100.0] * 15
    rally = [100.0 + step * i for i in range(rally_n)]
    out = prefix + rally
    last = out[-1]
    for k in range(fade_n):
        s = step * (1.0 - (k + 1) / (fade_n + 1))
        last += s
        out.append(last)
    return out


def _selloff_then_fade(drop_n: int = 30, step: float = 2.0, fade_n: int = 4) -> list[float]:
    """Mirror of the rally case — Stage 1 bullish setup."""
    prefix = [100.0] * 15
    drop = [100.0 - step * i for i in range(drop_n)]
    out = prefix + drop
    last = out[-1]
    for k in range(fade_n):
        s = step * (1.0 - (k + 1) / (fade_n + 1))
        last -= s
        out.append(last)
    return out


def _rally_then_flat(rally_n: int = 30, top: float = 130.0, flat_n: int = 60) -> list[float]:
    """Rally, then long flat — MACD decays back toward zero from above (Stage 3 bearish)."""
    rally = list(np.linspace(100.0, top, rally_n))
    return rally + [top] * flat_n


def _selloff_then_flat(drop_n: int = 30, bottom: float = 70.0, flat_n: int = 60) -> list[float]:
    """Mirror — MACD decays back toward zero from below (Stage 3 bullish)."""
    drop = list(np.linspace(100.0, bottom, drop_n))
    return drop + [bottom] * flat_n


# ---------- Stage 1: histogram flattening ----------


def test_stage1_fires_bearish_on_decelerating_rally():
    cfg = AppConfig()
    prices = _rally_then_fade()
    df = _df_from_close(prices)
    macd_df = compute_macd(df["close"], cfg.macd.fast, cfg.macd.slow, cfg.macd.signal)
    sig = _check_histogram_flattening("TEST", float(df["close"].iloc[-1]), macd_df, cfg)
    assert sig is not None
    assert sig.stage == "histogram_flattening"
    assert sig.direction == "bearish"
    assert sig.hist > 0
    assert sig.hist_peak is not None and sig.hist_peak > sig.hist
    assert sig.reduction_from_peak is not None and sig.reduction_from_peak >= 0.3


def test_stage1_fires_bullish_on_decelerating_selloff():
    cfg = AppConfig()
    df = _df_from_close(_selloff_then_fade())
    macd_df = compute_macd(df["close"], cfg.macd.fast, cfg.macd.slow, cfg.macd.signal)
    sig = _check_histogram_flattening("TEST", float(df["close"].iloc[-1]), macd_df, cfg)
    assert sig is not None
    assert sig.direction == "bullish"
    assert sig.hist < 0
    assert sig.hist_peak is not None and sig.hist_peak < sig.hist  # peak more negative


def test_stage1_silent_when_peak_below_noise_floor():
    """Tiny histogram swings must not trigger Stage 1."""
    base = AppConfig()
    cfg = base.model_copy(update={
        "signal": base.signal.model_copy(update={
            "histogram_flattening": base.signal.histogram_flattening.model_copy(
                update={"min_peak_pct_of_price": 0.5}  # 50% of price — impossible to clear
            )
        })
    })
    df = _df_from_close(_rally_then_fade())
    macd_df = compute_macd(df["close"], cfg.macd.fast, cfg.macd.slow, cfg.macd.signal)
    assert _check_histogram_flattening("TEST", float(df["close"].iloc[-1]), macd_df, cfg) is None


def test_stage1_silent_during_pure_rally():
    """Linear rally without a fade: hist is still expanding in absolute terms early
    on, or already decaying smoothly — but reduction-from-peak alone shouldn't fire
    without the strict-shrink condition over the configured window."""
    cfg = AppConfig()
    # 25 bars of a slow linear rally — short enough that the histogram hasn't
    # had time to peak and then strictly shrink 3 bars in a row.
    df = _df_from_close([100.0 + 0.5 * i for i in range(25)])
    macd_df = compute_macd(df["close"], cfg.macd.fast, cfg.macd.slow, cfg.macd.signal)
    assert _check_histogram_flattening("TEST", float(df["close"].iloc[-1]), macd_df, cfg) is None


# ---------- Stage 3: zero-line proximity ----------


def test_stage3_silent_during_strong_uptrend():
    cfg = AppConfig()
    df = _df_from_close([100.0 + i for i in range(60)])
    macd_df = compute_macd(df["close"], cfg.macd.fast, cfg.macd.slow, cfg.macd.signal)
    assert _check_zero_line_proximity("TEST", float(df["close"].iloc[-1]), macd_df, None, cfg) is None


def test_stage3_fires_bearish_on_rally_then_flat():
    """After a rally, a long flat lets MACD decay back to near zero from above."""
    cfg = AppConfig()
    df = _df_from_close(_rally_then_flat())
    macd_df = compute_macd(df["close"], cfg.macd.fast, cfg.macd.slow, cfg.macd.signal)
    sig = _check_zero_line_proximity("TEST", float(df["close"].iloc[-1]), macd_df, None, cfg)
    assert sig is not None
    assert sig.stage == "zero_line_proximity"
    assert sig.direction == "bearish"
    assert 0 < sig.macd < 1.0
    assert sig.macd_pct_of_price is not None and sig.macd_pct_of_price < cfg.signal.price_pct_threshold


def test_stage3_fires_bullish_on_selloff_then_flat():
    cfg = AppConfig()
    df = _df_from_close(_selloff_then_flat())
    macd_df = compute_macd(df["close"], cfg.macd.fast, cfg.macd.slow, cfg.macd.signal)
    sig = _check_zero_line_proximity("TEST", float(df["close"].iloc[-1]), macd_df, None, cfg)
    assert sig is not None
    assert sig.direction == "bullish"
    assert -1.0 < sig.macd < 0


def test_stage3_rank_mode_emits_without_threshold():
    """In rank mode, Stage 3 passes the per-asset threshold gate unconditionally."""
    base = AppConfig()
    cfg = base.model_copy(update={
        "signal": base.signal.model_copy(update={"mode": "rank"})
    })
    df = _df_from_close(_rally_then_flat())
    macd_df = compute_macd(df["close"], cfg.macd.fast, cfg.macd.slow, cfg.macd.signal)
    sig = _check_zero_line_proximity("TEST", float(df["close"].iloc[-1]), macd_df, None, cfg)
    assert sig is not None
    assert sig.macd_pct_of_price is not None  # carried for the cross-asset ranking step


# ---------- evaluate_all integration ----------


def test_evaluate_all_one_signal_per_asset():
    """Each asset appears at most once in the output, regardless of which stage(s) fire."""
    cfg = AppConfig()
    candles = {
        "S1B": _df_from_close(_rally_then_fade()),       # Stage 1 bearish
        "S1L": _df_from_close(_selloff_then_fade()),     # Stage 1 bullish
        "S3B": _df_from_close(_rally_then_flat()),       # Stage 3 bearish
        "S3L": _df_from_close(_selloff_then_flat()),     # Stage 3 bullish
        "NONE": _df_from_close([100.0 + i for i in range(60)]),  # strong trend, no signal
    }
    out = evaluate_all(candles, cfg)
    names = [s.name for s in out]
    assert len(names) == len(set(names)), "Same asset appeared twice in output"
    assert "NONE" not in names, "Strong-trend series should not emit a signal"


def test_evaluate_all_returns_correct_stages():
    cfg = AppConfig()
    candles = {
        "RALLY_FADE": _df_from_close(_rally_then_fade()),
        "RALLY_FLAT": _df_from_close(_rally_then_flat()),
    }
    out = {s.name: s for s in evaluate_all(candles, cfg)}
    assert out["RALLY_FADE"].stage == "histogram_flattening"
    assert out["RALLY_FLAT"].stage == "zero_line_proximity"


def test_evaluate_all_skips_short_series():
    assert evaluate_all({"X": _df_from_close([100.0] * 10)}, AppConfig()) == []


def test_evaluate_all_handles_empty_dict():
    assert evaluate_all({}, AppConfig()) == []


def test_evaluate_all_rank_mode_limits_to_top_n():
    """rank_top_n=1 ⇒ at most one Stage 3 signal across qualifying assets."""
    base = AppConfig()
    cfg = base.model_copy(update={
        "signal": base.signal.model_copy(update={"mode": "rank", "rank_top_n": 1}),
    })
    candles = {
        "A": _df_from_close(_rally_then_flat(top=110, flat_n=60)),
        "B": _df_from_close(_rally_then_flat(top=130, flat_n=60)),
        "C": _df_from_close(_rally_then_flat(top=150, flat_n=60)),
    }
    out = evaluate_all(candles, cfg)
    s3 = [s for s in out if s.stage == "zero_line_proximity"]
    assert len(s3) <= 1


def test_evaluate_all_disabled_stages_emit_nothing():
    base = AppConfig()
    cfg = base.model_copy(update={
        "signal": base.signal.model_copy(update={
            "zero_line_enabled": False,
            "histogram_flattening": base.signal.histogram_flattening.model_copy(
                update={"enabled": False}
            ),
        }),
    })
    candles = {
        "X": _df_from_close(_rally_then_fade()),
        "Y": _df_from_close(_rally_then_flat()),
    }
    assert evaluate_all(candles, cfg) == []


# ---------- forming-candle handling ----------


def test_last_bar_is_forming_detection():
    cfg = AppConfig()
    assert _last_bar_is_forming(_df_ending_today([100.0] * 60), cfg) is True
    # 2025-dated fixture: the final bar's day elapsed long ago.
    assert _last_bar_is_forming(_df_from_close([100.0] * 60), cfg) is False


def test_view_keeps_forming_for_stage1_drops_for_stage3():
    cfg = AppConfig()
    prices = [float(p) for p in range(100, 160)]  # last close 159, prev 158
    df = _df_ending_today(prices)
    macd_df = compute_macd(df["close"], cfg.macd.fast, cfg.macd.slow, cfg.macd.signal)

    # Stage 1 (use_forming=True): keep today's bar.
    m1, c1, _ = _view(df, macd_df, None, last_is_forming=True, use_forming=True)
    assert c1 == 159.0
    assert len(m1) == len(macd_df)

    # Stage 3 (use_forming=False) with a forming bar present: drop it.
    m3, c3, _ = _view(df, macd_df, None, last_is_forming=True, use_forming=False)
    assert c3 == 158.0
    assert len(m3) == len(macd_df) - 1
    # Causal EWM: the trimmed frame equals the untrimmed frame minus its last row.
    assert m3["macd"].iloc[-1] == macd_df["macd"].iloc[-2]


def test_view_no_drop_when_last_bar_not_forming():
    cfg = AppConfig()
    df = _df_from_close([float(p) for p in range(100, 160)])
    macd_df = compute_macd(df["close"], cfg.macd.fast, cfg.macd.slow, cfg.macd.signal)
    # Not forming → both detectors see the full series regardless of the flag.
    for use_forming in (True, False):
        m, c, _ = _view(df, macd_df, None, last_is_forming=False, use_forming=use_forming)
        assert c == 159.0
        assert len(m) == len(macd_df)


def test_shorter_shrink_lookback_is_a_superset():
    """A 2-bar shrink is a strict relaxation of 3-bar: any asset that fires
    Stage 1 at lookback 3 must also fire at lookback 2 (other guards equal)."""
    base = AppConfig().model_copy(update={
        "signal": AppConfig().signal.model_copy(update={"zero_line_enabled": False}),
    })
    cfg3 = base  # default shrink_lookback is 3
    cfg2 = base.model_copy(update={
        "signal": base.signal.model_copy(update={
            "histogram_flattening": base.signal.histogram_flattening.model_copy(
                update={"shrink_lookback": 2}
            )
        })
    })
    candles = {
        "A": _df_from_close(_rally_then_fade()),
        "B": _df_from_close(_selloff_then_fade()),
        "C": _df_from_close(_rally_then_flat()),
        "D": _df_from_close([100.0 + 0.5 * i for i in range(60)]),
    }
    fired3 = {s.name for s in evaluate_all(candles, cfg3) if s.stage == "histogram_flattening"}
    fired2 = {s.name for s in evaluate_all(candles, cfg2) if s.stage == "histogram_flattening"}
    assert fired3 <= fired2
