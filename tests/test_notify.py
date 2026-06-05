"""Tests for notify: quiet-hours logic, formatter, dispatch gates.

Live HTTP is never exercised here — `send_signals` is steered into its
non-send branches via config.
"""

from __future__ import annotations

import io
from contextlib import redirect_stdout
from datetime import datetime, time, timezone
from zoneinfo import ZoneInfo

import pytest

from macd_searcher.config import AppConfig
from macd_searcher.notify import (
    chunk_for_telegram,
    format_message,
    in_quiet_hours,
    send_signals,
)
from macd_searcher.signals import Signal


# ---------- quiet hours ----------


def _at_local(hour: int, minute: int = 0, tz: str = "Australia/Melbourne") -> datetime:
    """Construct a UTC datetime that corresponds to the given local clock time."""
    local = datetime.now(tz=ZoneInfo(tz)).replace(hour=hour, minute=minute, second=0, microsecond=0)
    return local.astimezone(timezone.utc)


def test_quiet_hours_active_inside_window():
    cfg = AppConfig()  # default 00:00 → 08:00 Australia/Melbourne
    assert in_quiet_hours(cfg, now_utc=_at_local(3)) is True
    assert in_quiet_hours(cfg, now_utc=_at_local(0)) is True


def test_quiet_hours_inactive_outside_window():
    cfg = AppConfig()
    assert in_quiet_hours(cfg, now_utc=_at_local(8)) is False
    assert in_quiet_hours(cfg, now_utc=_at_local(12)) is False
    assert in_quiet_hours(cfg, now_utc=_at_local(23, 59)) is False


def test_quiet_hours_disabled_flag_short_circuits():
    base = AppConfig()
    cfg = base.model_copy(update={
        "notify": base.notify.model_copy(update={
            "quiet_hours": base.notify.quiet_hours.model_copy(update={"enabled": False})
        })
    })
    # Even at 3 AM, disabled should report not-quiet.
    assert in_quiet_hours(cfg, now_utc=_at_local(3)) is False


def test_quiet_hours_wraparound_window():
    """22:00 → 06:00 wraps midnight — both 23:00 and 05:00 are 'in' quiet hours."""
    base = AppConfig()
    cfg = base.model_copy(update={
        "notify": base.notify.model_copy(update={
            "quiet_hours": base.notify.quiet_hours.model_copy(
                update={"start": time(22, 0), "end": time(6, 0)}
            )
        })
    })
    assert in_quiet_hours(cfg, now_utc=_at_local(23)) is True
    assert in_quiet_hours(cfg, now_utc=_at_local(5)) is True
    assert in_quiet_hours(cfg, now_utc=_at_local(12)) is False


# ---------- formatter ----------


def _mk_signal(
    name: str,
    stage: str,
    direction: str,
    **kw,
) -> Signal:
    defaults = dict(close=100.0, macd=0.1, hist=0.05)
    defaults.update(kw)
    return Signal(name=name, stage=stage, direction=direction, **defaults)  # type: ignore[arg-type]


def test_format_message_empty_signals():
    text = format_message([], scanned_count=99, cfg=AppConfig())
    assert "0 signal" in text
    assert "No assets" in text


def test_format_message_groups_by_stage_and_direction():
    signals = [
        _mk_signal("BTC", "zero_line_proximity", "bearish",
                   macd=120, hist=-5, close=60000, macd_pct_of_price=0.002),
        _mk_signal("ETH", "histogram_flattening", "bullish",
                   macd=-50, hist=-10, close=2000, hist_peak=-25, reduction_from_peak=0.6),
        _mk_signal("SOL", "histogram_flattening", "bearish",
                   macd=2, hist=0.1, close=85, hist_peak=0.5, reduction_from_peak=0.8),
    ]
    text = format_message(signals, scanned_count=50, cfg=AppConfig())
    # Stage 3 must appear before Stage 1 in the output.
    s3_idx = text.index("Stage 3")
    s1_idx = text.index("Stage 1")
    assert s3_idx < s1_idx
    # Each signal name should appear exactly once.
    for name in ("BTC", "ETH", "SOL"):
        assert text.count(name) == 1
    # Direction headers should be present.
    assert "BEARISH" in text
    assert "BULLISH" in text


def test_format_message_sorts_within_bucket_by_strength():
    """Stage 1 bucket should be sorted by descending reduction_from_peak."""
    signals = [
        _mk_signal("LOW", "histogram_flattening", "bullish",
                   close=100, hist=-1, hist_peak=-2, reduction_from_peak=0.3),
        _mk_signal("MID", "histogram_flattening", "bullish",
                   close=100, hist=-1, hist_peak=-2, reduction_from_peak=0.6),
        _mk_signal("HIGH", "histogram_flattening", "bullish",
                   close=100, hist=-1, hist_peak=-2, reduction_from_peak=0.9),
    ]
    text = format_message(signals, scanned_count=3, cfg=AppConfig())
    assert text.index("HIGH") < text.index("MID") < text.index("LOW")


# ---------- chunking ----------


def test_chunk_for_telegram_short_text_one_chunk():
    text = "line1\nline2"
    assert chunk_for_telegram(text) == [text]


def test_chunk_for_telegram_splits_at_line_boundaries():
    # 200 lines × 50 chars = 10_000 chars, well over the 3800 soft cap.
    lines = [f"line-{i:03d}-" + "x" * 40 for i in range(200)]
    text = "\n".join(lines)
    chunks = chunk_for_telegram(text)
    assert len(chunks) > 1
    for c in chunks:
        assert len(c) <= 3800
    # Every line should appear in exactly one chunk.
    rejoined = "\n".join(chunks)
    for ln in lines:
        assert ln in rejoined


# ---------- dispatch gates ----------


@pytest.mark.asyncio
async def test_send_signals_dry_run_prints_to_stdout():
    base = AppConfig()
    cfg = base.model_copy(update={
        "notify": base.notify.model_copy(update={"dry_run": True}),
    })
    buf = io.StringIO()
    with redirect_stdout(buf):
        await send_signals(
            [_mk_signal("BTC", "zero_line_proximity", "bearish",
                        macd=120, hist=-1, close=60000, macd_pct_of_price=0.002)],
            scanned_count=99,
            cfg=cfg,
        )
    assert "BTC" in buf.getvalue()


@pytest.mark.asyncio
async def test_send_signals_empty_with_send_when_empty_false_prints_nothing():
    base = AppConfig()
    cfg = base.model_copy(update={
        "notify": base.notify.model_copy(update={
            "send_when_empty": False, "dry_run": True,
        })
    })
    buf = io.StringIO()
    with redirect_stdout(buf):
        await send_signals([], scanned_count=99, cfg=cfg)
    assert buf.getvalue() == ""


@pytest.mark.asyncio
async def test_send_signals_quiet_hours_prints_but_does_not_send():
    """In quiet hours, the body should still hit stdout for cron logs."""
    cfg = AppConfig()  # quiet hours 00:00-08:00 Melbourne, no Telegram creds
    buf = io.StringIO()
    with redirect_stdout(buf):
        await send_signals([], scanned_count=10, cfg=cfg, now_utc=_at_local(3))
    assert "MACD scan" in buf.getvalue()
    # No HTTP call attempted — would have raised since creds are empty.


@pytest.mark.asyncio
async def test_send_signals_missing_credentials_prints_warning_and_text():
    """No bot token / chat ID configured → fall back to stdout, don't raise."""
    base = AppConfig()
    # Force outside quiet hours by disabling them entirely.
    cfg = base.model_copy(update={
        "notify": base.notify.model_copy(update={
            "quiet_hours": base.notify.quiet_hours.model_copy(update={"enabled": False})
        })
    })
    buf = io.StringIO()
    with redirect_stdout(buf):
        await send_signals(
            [_mk_signal("TEST", "zero_line_proximity", "bullish",
                        macd=-0.1, hist=0.01, close=100, macd_pct_of_price=0.001)],
            scanned_count=1,
            cfg=cfg,
        )
    assert "TEST" in buf.getvalue()
