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

from dataclasses import replace

from datetime import date

from macd_searcher.book import Book, Position
from macd_searcher.config import AppConfig
from macd_searcher.notify import (
    chunk_for_telegram,
    format_book_message,
    format_message,
    in_quiet_hours,
    send_book,
    send_signals,
)
from macd_searcher.signals import (
    Signal,
    signal_line_atr_multiple,
)


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
    # pk 10 by default puts a crypto fire in a B3 leg (L1 bullish, S1 bearish), so
    # it shows up in the message.
    defaults = dict(close=100.0, macd=0.1, hist=0.05, hist_peak_pct=10.0)
    defaults.update(kw)
    return Signal(name=name, stage=stage, direction=direction, **defaults)  # type: ignore[arg-type]


def test_format_message_empty_signals():
    text = format_message([], scanned_count=99, cfg=AppConfig())
    assert "0 in B3 legs" in text
    assert "No B3 fires" in text


def _leg_signal(name: str, direction: str, peak_pct: float | None) -> Signal:
    return _mk_signal(name, "histogram_flattening", direction, hist_peak=0.5,
                      reduction_from_peak=0.5, hist_peak_pct=peak_pct)


def test_format_message_groups_by_leg_in_leg_order():
    signals = [
        _leg_signal("DEEP", "bullish", 80.0),       # S2
        _leg_signal("WEAK", "bearish", 10.0),       # S1
        _leg_signal("LEADER", "bearish", 90.0),     # L2
        _leg_signal("MILD", "bullish", 20.0),       # L1
    ]
    text = format_message(signals, scanned_count=50, cfg=AppConfig())
    headers = [ln for ln in text.split("\n") if ln.startswith(("🟢", "🔴"))]
    assert [h.split()[1] for h in headers] == ["L1", "L2", "S1", "S2"]
    assert text.index("MILD") < text.index("LEADER") < text.index("WEAK") < text.index("DEEP")
    assert "4 in B3 legs" in text


def test_format_message_colours_by_trade_not_by_fire():
    """L2 is a bearish fire held long, so its header is green."""
    text = format_message([_leg_signal("LEADER", "bearish", 90.0)], 1, AppConfig())
    assert "🟢 L2 LONG" in text and "🔴" not in text


def test_format_message_drops_untraded_bands_and_non_crypto():
    signals = [
        _leg_signal("MIDBAND", "bullish", 40.0),
        _leg_signal("RECORD", "bullish", 100.0),
        _leg_signal("NOPK", "bearish", None),
        _leg_signal("xyz:TSLA", "bullish", 10.0),
        _leg_signal("SOL", "bullish", 10.0),
    ]
    text = format_message(signals, scanned_count=5, cfg=AppConfig())
    for gone in ("MIDBAND", "RECORD", "NOPK", "TSLA"):
        assert gone not in text
    assert "SOL" in text and "1 in B3 legs" in text


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


def test_format_message_never_bolds_intraday_rows():
    """v2's bold marker is gone (no selection edge); bold now means a new B3 position,
    which only the daily book knows about. This row was v2-confident."""
    s = _mk_signal("SOL", "histogram_flattening", "bullish",
                   macd=-2.2, hist=-0.2, close=85.0, hist_peak=-0.5,
                   reduction_from_peak=0.45, atr=2.0)   # sig/ATR -1.00
    assert "<b>" not in format_message([s], scanned_count=1, cfg=AppConfig())


def test_format_message_escapes_symbol_names():
    """HTML parse_mode is on, so an interpolated symbol must not inject markup."""
    s = _mk_signal("A<B&C", "histogram_flattening", "bearish",
                   hist=0.1, close=100.0, hist_peak=0.5, reduction_from_peak=0.5)
    text = format_message([s], scanned_count=1, cfg=AppConfig())
    assert "A&lt;B&amp;C" in text
    assert "A<B&C" not in text


def test_signal_line_atr_multiple_derivation():
    """Same `macd - hist` signal line, divided by ATR instead of price."""
    s = _mk_signal("BTC", "histogram_flattening", "bullish",
                   close=100.0, macd=-7.2, hist=-0.2, atr=4.0,
                   hist_peak=-2.0, reduction_from_peak=0.4)
    assert signal_line_atr_multiple(s) == pytest.approx(-1.75)
    # Price is irrelevant to this axis — that is the whole point of it. The same
    # trend on a token priced 20x lower reads identically.
    s2 = replace(s, close=5.0)
    assert signal_line_atr_multiple(s2) == pytest.approx(-1.75)


def test_signal_line_atr_multiple_none_when_atr_unusable():
    """No ATR, or a flat series with zero range, leaves nothing to normalize by."""
    base = dict(close=100.0, macd=-7.2, hist=-0.2, reduction_from_peak=0.4)
    assert signal_line_atr_multiple(
        _mk_signal("BTC", "histogram_flattening", "bullish", atr=None, **base)) is None
    assert signal_line_atr_multiple(
        _mk_signal("BTC", "histogram_flattening", "bullish", atr=0.0, **base)) is None


def test_format_message_shows_signal_line_in_atr_only():
    """`sig` is the ATR multiple alone; the %-of-price reading left the row."""
    s = _mk_signal("ETH", "histogram_flattening", "bullish",
                   close=100.0, macd=-7.2, hist=-0.2, atr=4.0, hist_peak=-2.0,
                   reduction_from_peak=0.4, rsi_14=38.0)
    row = next(ln for ln in format_message([s], 1, AppConfig()).split("\n") if "ETH" in ln)
    assert "sig -1.75\u00d7ATR" in row
    assert "↓40%" in row and "RSI 38" in row
    assert "%" not in row.split("sig")[1]      # no % of price after `sig`


def test_format_message_signal_line_signed_both_ways():
    """A bearish fire above equilibrium reads positive, so the sign carries the regime."""
    s = _mk_signal("SOL", "histogram_flattening", "bearish",
                   close=100.0, macd=3.2, hist=0.2, atr=2.0, hist_peak=1.0,
                   reduction_from_peak=0.5)
    row = next(ln for ln in format_message([s], 1, AppConfig()).split("\n") if "SOL" in ln)
    assert "sig +1.50\u00d7ATR" in row


def test_format_message_omits_sig_without_atr():
    """No ATR to normalize by: the field is dropped, not shown as nan."""
    s = _mk_signal("BAD", "histogram_flattening", "bullish",
                   close=100.0, macd=-1.0, hist=-0.2, hist_peak=-2.0,
                   reduction_from_peak=0.4)
    row = next(ln for ln in format_message([s], 1, AppConfig()).split("\n") if "BAD" in ln)
    assert "sig" not in row
    assert "↓40%" in row


@pytest.mark.parametrize("peak_pct,shown", [(18.4, "pk 18"), (99.6, "pk 100")])
def test_format_message_shows_peak_percentile_as_a_plain_number(peak_pct, shown):
    """`pk` is a number on every row, rounded; 99.6 is S2, not a record trough."""
    s = _mk_signal("PK", "histogram_flattening", "bullish", close=100.0, macd=-1.0, hist=-0.2,
                   atr=2.0, reduction_from_peak=0.4, hist_peak_pct=peak_pct, hist_top_n=6)
    row = next(ln for ln in format_message([s], 1, AppConfig()).split("\n") if "PK" in ln)
    assert shown in row


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


def test_format_message_has_no_record_trough_warning():
    """The record-trough warning was removed after it failed to replicate in history
    (docs/historical_rebuild.md, H2). A record trough is in no B3 leg, so it isn't shown."""
    s = _mk_signal("REC", "histogram_flattening", "bullish", close=100.0, macd=-1.0, hist=-0.2,
                   atr=2.0, reduction_from_peak=0.4, hist_peak_pct=100.0, hist_top_n=6)
    text = format_message([s], 1, AppConfig())
    assert "REC" not in text and "\u26a0" not in text and "record" not in text


# ---------- the daily book ----------

_DAY = date(2026, 10, 26)


def _pos(symbol: str, leg: str, days_ago: int, peak_pct: float = 12.0) -> Position:
    return Position(symbol, leg, date.fromordinal(_DAY.toordinal() - days_ago), peak_pct)  # type: ignore[arg-type]


def _book() -> Book:
    return Book(
        day=_DAY,
        positions=[_pos("OLDER", "L1", 9), _pos("FRESH", "L1", 0), _pos("LEADER", "L2", 3, 88.0),
                   _pos("DEEP", "S2", 1, 70.0)],
        exits=[_pos("GONE", "S1", 14)],
    )


def test_book_message_counts_sides_new_and_exits():
    lines = format_book_message(_book()).split("\n")
    assert lines[0].endswith("B3 book — 2026-10-26")
    assert lines[1] == "Long 3 \u00b7 Short 1 \u00b7 1 new \u00b7 1 exits"


def test_book_message_bolds_only_today_s_entries_newest_first():
    text = format_book_message(_book())
    fresh = next(ln for ln in text.split("\n") if "FRESH" in ln)
    older = next(ln for ln in text.split("\n") if "OLDER" in ln)
    assert fresh.strip().startswith("<b>") and "new" in fresh
    assert "<b>" not in older and "d9" in older
    assert text.index("FRESH") < text.index("OLDER")


def test_book_message_lists_legs_then_exits():
    text = format_book_message(_book())
    assert text.index("L1 LONG") < text.index("L2 LONG") < text.index("S2 SHORT") < text.index("EXITS")
    assert "S1 SHORT" not in text                   # an empty leg gets no header
    assert "GONE" in text.split("EXITS")[1]
    assert "pk 88" in next(ln for ln in text.split("\n") if "LEADER" in ln)


def test_book_message_when_flat():
    text = format_book_message(Book(day=_DAY, positions=[], exits=[]))
    assert "Long 0 \u00b7 Short 0" in text and "No open B3 positions." in text


@pytest.mark.asyncio
async def test_send_book_empty_with_send_when_empty_false_prints_nothing():
    base = AppConfig()
    cfg = base.model_copy(update={
        "notify": base.notify.model_copy(update={"send_when_empty": False, "dry_run": True})
    })
    buf = io.StringIO()
    with redirect_stdout(buf):
        status = await send_book(Book(day=_DAY, positions=[], exits=[]), cfg)
    assert status == "empty_suppressed" and buf.getvalue() == ""


@pytest.mark.asyncio
async def test_send_book_dry_run_prints_the_book():
    base = AppConfig()
    cfg = base.model_copy(update={"notify": base.notify.model_copy(update={"dry_run": True})})
    buf = io.StringIO()
    with redirect_stdout(buf):
        assert await send_book(_book(), cfg) == "dry_run"
    assert "B3 book" in buf.getvalue() and "FRESH" in buf.getvalue()
