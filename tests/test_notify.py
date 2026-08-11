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


def test_format_message_groups_by_direction():
    signals = [
        _mk_signal("ETH", "histogram_flattening", "bullish",
                   macd=-50, hist=-10, close=2000, hist_peak=-25, reduction_from_peak=0.6),
        _mk_signal("SOL", "histogram_flattening", "bearish",
                   macd=2, hist=0.1, close=85, hist_peak=0.5, reduction_from_peak=0.8),
    ]
    text = format_message(signals, scanned_count=50, cfg=AppConfig())
    assert "histogram flattening" in text
    # No Stage-3 vestiges.
    assert "zero-line" not in text and "Stage 3" not in text
    # Each signal name should appear exactly once.
    for name in ("ETH", "SOL"):
        assert text.count(name) == 1
    # Direction headers should be present.
    assert "BEARISH" in text
    assert "BULLISH" in text


def test_format_message_includes_rsi_when_present():
    signals = [
        _mk_signal("BTC", "histogram_flattening", "bearish",
                   hist=0.2, close=100, hist_peak=0.5, reduction_from_peak=0.6, rsi_14=68.0),
    ]
    text = format_message(signals, scanned_count=1, cfg=AppConfig())
    assert "RSI 68" in text


def test_format_message_sorts_shallowest_reduction_first():
    """Ascending reduction: 0.3-0.4 fires measured +1.78% EV vs -0.99% at 0.8-1.0,
    so the shallow end leads (this is the reverse of the original ordering)."""
    signals = [
        _mk_signal("DEEP", "histogram_flattening", "bullish",
                   close=100, hist=-1, hist_peak=-2, reduction_from_peak=0.9),
        _mk_signal("MID", "histogram_flattening", "bullish",
                   close=100, hist=-1, hist_peak=-2, reduction_from_peak=0.6),
        _mk_signal("SHALLOW", "histogram_flattening", "bullish",
                   close=100, hist=-1, hist_peak=-2, reduction_from_peak=0.3),
    ]
    text = format_message(signals, scanned_count=3, cfg=AppConfig())
    assert text.index("SHALLOW") < text.index("MID") < text.index("DEEP")


def test_format_message_floats_high_confidence_to_top():
    """A bolded row buried under 30 others is useless, so confidence outranks
    reduction — even when the confident row has a deeper reduction."""
    signals = [
        _mk_signal("PLAIN", "histogram_flattening", "bearish",
                   close=100, hist=1, hist_peak=2, reduction_from_peak=0.31),
        _mk_signal("CONFIDENT", "histogram_flattening", "bearish",
                   close=100, hist=1, hist_peak=2, reduction_from_peak=0.55,
                   hist_peak_ratio=0.3, hist_peak_pct=12.0, hist_top_n=8),
    ]
    text = format_message(signals, scanned_count=2, cfg=AppConfig())
    assert text.index("CONFIDENT") < text.index("PLAIN")


def test_format_message_omits_hist_peak_and_price():
    """The row was trimmed to reduction + RSI; the raw hist value, the peak it fell
    from, and the price all moved to the dashboard."""
    signals = [
        _mk_signal("BTC", "histogram_flattening", "bearish",
                   hist=0.1234, close=54321.0, hist_peak=0.2345,
                   reduction_from_peak=0.47, rsi_14=68.0),
    ]
    text = format_message(signals, scanned_count=1, cfg=AppConfig())
    row = next(ln for ln in text.split("\n") if "BTC" in ln)
    assert "↓47%" in row and "RSI 68" in row
    # The three things asked to go. ("hist" still appears in the section header.)
    assert "hist " not in row and "0.1234" not in row
    assert "from" not in row and "0.2345" not in row
    assert "$" not in row and "54,321" not in row


def test_format_message_bolds_high_confidence_row():
    """Bearish + shallow reduction + modest peak = the measured high-EV slice."""
    signals = [
        _mk_signal("SOL", "histogram_flattening", "bearish",
                   hist=0.1, close=85.0, hist_peak=0.5, reduction_from_peak=0.45,
                   hist_peak_ratio=0.3, hist_peak_pct=12.0, hist_top_n=8),
    ]
    text = format_message(signals, scanned_count=1, cfg=AppConfig())
    assert "<b>" in text and "</b>" in text
    assert "SOL" in text


def test_format_message_does_not_bold_ordinary_rows():
    """Each miss on its own is enough to withhold the marker."""
    cases = [
        # deep reduction
        dict(direction="bearish", reduction_from_peak=0.85, hist_peak_pct=12.0, hist_top_n=8),
        # large peak for this token
        dict(direction="bearish", reduction_from_peak=0.45, hist_peak_pct=75.0, hist_top_n=8),
        # baseline too thin to trust
        dict(direction="bearish", reduction_from_peak=0.45, hist_peak_pct=12.0, hist_top_n=1),
        # no peak context at all
        dict(direction="bearish", reduction_from_peak=0.45, hist_peak_pct=None, hist_top_n=0),
        # bullish never qualifies — it reversed sign between regime halves
        dict(direction="bullish", reduction_from_peak=0.45, hist_peak_pct=12.0, hist_top_n=8),
    ]
    for kw in cases:
        direction = kw.pop("direction")
        s = _mk_signal("XYZ", "histogram_flattening", direction,
                       hist=0.1, close=100.0, hist_peak=0.5, **kw)
        assert "<b>" not in format_message([s], scanned_count=1, cfg=AppConfig()), kw


def test_format_message_escapes_symbol_names():
    """HTML parse_mode is on, so an interpolated symbol must not inject markup."""
    s = _mk_signal("A<B&C", "histogram_flattening", "bearish",
                   hist=0.1, close=100.0, hist_peak=0.5, reduction_from_peak=0.5)
    text = format_message([s], scanned_count=1, cfg=AppConfig())
    assert "A&lt;B&amp;C" in text
    assert "A<B&C" not in text


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
            [_mk_signal("BTC", "histogram_flattening", "bearish",
                        macd=120, hist=5, close=60000, hist_peak=10, reduction_from_peak=0.6)],
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
            [_mk_signal("TEST", "histogram_flattening", "bullish",
                        macd=-0.1, hist=-0.01, close=100, hist_peak=-0.05, reduction_from_peak=0.5)],
            scanned_count=1,
            cfg=cfg,
        )
    assert "TEST" in buf.getvalue()
