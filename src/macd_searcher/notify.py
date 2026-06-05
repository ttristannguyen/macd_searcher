"""Telegram notification + dispatch gates.

Responsibilities:
  - Format the per-run signal list into a single text body (with sane
    truncation if the body would exceed Telegram's 4096-char limit).
  - Decide whether to actually send: skipped during quiet hours, skipped in
    dry-run mode, skipped if Telegram secrets are missing. In all of those
    cases the body is still printed to stdout so the cron log captures it.
  - Send via raw HTTP to api.telegram.org with simple retry on transient
    failures.

Plain text is used (no Markdown / HTML parse_mode) — the structure comes
from emojis and indentation, which renders identically everywhere.
"""

from __future__ import annotations

import asyncio
import logging
import random
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import httpx

from .config import AppConfig
from .signals import Signal


log = logging.getLogger(__name__)

# Telegram's hard cap is 4096 chars; chunk well below for safety.
_CHUNK_SOFT_CAP = 3800

_STAGE_LABELS = {
    "zero_line_proximity": "🎯 Stage 3 — zero-line proximity",
    "histogram_flattening": "📉 Stage 1 — histogram flattening",
}
_DIRECTION_EMOJI = {"bullish": "🟢", "bearish": "🔴"}


# ---------- quiet hours ----------


def in_quiet_hours(cfg: AppConfig, now_utc: datetime | None = None) -> bool:
    """True if the current local time falls in the configured quiet window.

    Handles wrap-around (e.g. 22:00 → 06:00) as well as same-day windows.
    """
    qh = cfg.notify.quiet_hours
    if not qh.enabled:
        return False
    tz = ZoneInfo(qh.timezone)
    now = (now_utc or datetime.now(tz=timezone.utc)).astimezone(tz)
    t = now.time()
    if qh.start <= qh.end:
        return qh.start <= t < qh.end
    return t >= qh.start or t < qh.end


# ---------- formatting ----------


def _fmt_price(px: float) -> str:
    if px >= 1000:
        return f"${px:,.2f}"
    if px >= 1:
        return f"${px:,.4f}"
    return f"${px:.6f}"


def _fmt_stage1_row(s: Signal) -> str:
    assert s.hist_peak is not None and s.reduction_from_peak is not None
    pct = s.reduction_from_peak * 100
    return (
        f"  {s.name:<10} hist {s.hist:+.4g} "
        f"(↓{pct:.0f}% from {s.hist_peak:+.4g})  px {_fmt_price(s.close)}"
    )


def _fmt_stage3_row(s: Signal, mode: str) -> str:
    metric = ""
    if mode == "atr" and s.atr_multiple is not None:
        metric = f"|M|/ATR {s.atr_multiple:.2f}"
    elif s.macd_pct_of_price is not None:
        metric = f"|M|/px {s.macd_pct_of_price:.2%}"
    return f"  {s.name:<10} MACD {s.macd:+.4g}   {metric}   px {_fmt_price(s.close)}"


def _strength_key(s: Signal) -> float:
    """Sort order within a bucket — strongest first."""
    if s.stage == "zero_line_proximity":
        return s.macd_pct_of_price if s.macd_pct_of_price is not None else float("inf")
    if s.stage == "histogram_flattening":
        return -(s.reduction_from_peak or 0.0)
    return 0.0


def format_message(
    signals: list[Signal],
    scanned_count: int,
    cfg: AppConfig,
    now_utc: datetime | None = None,
) -> str:
    """Render the full message body. May exceed Telegram's per-message limit;
    callers should pass the result through `chunk_for_telegram` before sending."""
    when = (now_utc or datetime.now(tz=timezone.utc)).strftime("%Y-%m-%d %H:%M UTC")
    lines: list[str] = []
    lines.append(f"📊 MACD scan — {when}")
    lines.append(f"{scanned_count} assets scanned, {len(signals)} signal(s)")

    if not signals:
        lines.append("")
        lines.append("No assets met the configured criteria this cycle.")
        return "\n".join(lines)

    # Group: stage 3 first (closer to actual cross), then stage 1.
    for stage in ("zero_line_proximity", "histogram_flattening"):
        bucket = [s for s in signals if s.stage == stage]
        if not bucket:
            continue
        lines.append("")
        lines.append(f"{_STAGE_LABELS[stage]} ({len(bucket)})")
        for direction in ("bearish", "bullish"):
            rows = sorted(
                [s for s in bucket if s.direction == direction],
                key=_strength_key,
            )
            if not rows:
                continue
            lines.append(f"{_DIRECTION_EMOJI[direction]} {direction.upper()} ({len(rows)})")
            for s in rows:
                if stage == "zero_line_proximity":
                    lines.append(_fmt_stage3_row(s, cfg.signal.mode))
                else:
                    lines.append(_fmt_stage1_row(s))

    return "\n".join(lines)


def chunk_for_telegram(text: str, soft_cap: int = _CHUNK_SOFT_CAP) -> list[str]:
    """Split on line boundaries so each piece fits in a single Telegram message."""
    if len(text) <= soft_cap:
        return [text]
    chunks: list[str] = []
    cur: list[str] = []
    cur_len = 0
    for line in text.split("\n"):
        line_len = len(line) + 1  # account for the newline
        if cur and cur_len + line_len > soft_cap:
            chunks.append("\n".join(cur))
            cur = [line]
            cur_len = line_len
        else:
            cur.append(line)
            cur_len += line_len
    if cur:
        chunks.append("\n".join(cur))
    return chunks


# ---------- Telegram HTTP ----------


async def _send_one(
    client: httpx.AsyncClient,
    text: str,
    cfg: AppConfig,
) -> None:
    url = f"https://api.telegram.org/bot{cfg.telegram.bot_token}/sendMessage"
    payload = {
        "chat_id": cfg.telegram.chat_id,
        "text": text,
        "disable_web_page_preview": True,
    }
    last_exc: Exception | None = None
    for attempt in range(1, 4):
        try:
            resp = await client.post(url, json=payload, timeout=15.0)
            if resp.status_code == 200:
                return
            if resp.status_code in (429, 500, 502, 503, 504):
                last_exc = RuntimeError(f"Telegram HTTP {resp.status_code}: {resp.text[:200]}")
            else:
                raise RuntimeError(f"Telegram HTTP {resp.status_code}: {resp.text[:200]}")
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            last_exc = exc

        if attempt < 3:
            delay = (1.0 * 2 ** (attempt - 1)) + random.uniform(0, 0.5)
            log.warning("Telegram send attempt %d failed (%s); retrying in %.2fs", attempt, last_exc, delay)
            await asyncio.sleep(delay)

    assert last_exc is not None
    raise last_exc


# ---------- public entrypoint ----------


async def send_raw_text(text: str, cfg: AppConfig) -> None:
    """One-shot helper to push an arbitrary text message to Telegram.

    Bypasses quiet hours and dry-run gates — caller decides. Used for
    error alerts from the orchestrator. No-op if creds are missing.
    """
    if not cfg.telegram.configured:
        log.warning("send_raw_text: Telegram not configured; dropping message.")
        return
    async with httpx.AsyncClient() as client:
        for chunk in chunk_for_telegram(text):
            await _send_one(client, chunk, cfg)


async def send_signals(
    signals: list[Signal],
    scanned_count: int,
    cfg: AppConfig,
    now_utc: datetime | None = None,
) -> str:
    """Format + dispatch. Honors send_when_empty, dry_run, quiet hours, and
    missing credentials. In any non-send path the message body is still
    printed so cron logs capture the scan output.

    Returns a dispatch status for the run log:
    'sent' | 'empty_suppressed' | 'dry_run' | 'quiet_hours' | 'no_creds'.
    """

    text = format_message(signals, scanned_count, cfg, now_utc=now_utc)

    if not signals and not cfg.notify.send_when_empty:
        log.info("No signals; send_when_empty=false. Skipping send.")
        return "empty_suppressed"

    if cfg.notify.dry_run:
        log.info("Dry-run mode; printing message to stdout instead of Telegram.")
        print(text)
        return "dry_run"

    if in_quiet_hours(cfg, now_utc=now_utc):
        log.info("In quiet hours (%s %s–%s); printing instead of sending.",
                 cfg.notify.quiet_hours.timezone,
                 cfg.notify.quiet_hours.start,
                 cfg.notify.quiet_hours.end)
        print(text)
        return "quiet_hours"

    if not cfg.telegram.configured:
        log.warning("Telegram credentials missing; printing instead. "
                    "Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID to enable sends.")
        print(text)
        return "no_creds"

    chunks = chunk_for_telegram(text)
    async with httpx.AsyncClient() as client:
        for i, chunk in enumerate(chunks, start=1):
            log.info("Sending Telegram chunk %d/%d (%d chars)", i, len(chunks), len(chunk))
            await _send_one(client, chunk, cfg)
    return "sent"
