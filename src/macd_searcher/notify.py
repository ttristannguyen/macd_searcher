"""Telegram notification + dispatch gates.

Responsibilities:
  - Format the per-run signal list into a single text body (with sane
    truncation if the body would exceed Telegram's 4096-char limit).
  - Decide whether to actually send: skipped during quiet hours, skipped in
    dry-run mode, skipped if Telegram secrets are missing. In all of those
    cases the body is still printed to stdout so the cron log captures it.
  - Send via raw HTTP to api.telegram.org with simple retry on transient
    failures.

Sent with HTML parse_mode so high-confidence rows can be bolded; HTML was chosen
over MarkdownV2 because it only requires escaping `& < >` (symbol names are the
only interpolated free text), whereas MarkdownV2 would need every `+ - . |` in the
numbers escaped. Everything else is emojis and indentation, which render the same
everywhere.
"""

from __future__ import annotations

import asyncio
import logging
import random
from datetime import datetime, timezone
from html import escape
from zoneinfo import ZoneInfo

import httpx

from .config import AppConfig
from .signals import Signal, is_high_confidence


log = logging.getLogger(__name__)

# Telegram's hard cap is 4096 chars; chunk well below for safety.
_CHUNK_SOFT_CAP = 3800

_STAGE_HEADER = "📉 histogram flattening"
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


def _fmt_stage1_row(s: Signal) -> str:
    """One signal line. Deliberately sparse — the raw hist value, the peak it fell
    from, and the price were all dropped as noise you can look up in the dashboard.
    What's left is the two things that drive the read: how far it has flattened,
    and RSI as context.

    High-confidence rows (see `is_high_confidence`) are bolded, which is why the
    sender uses HTML parse_mode.
    """
    assert s.reduction_from_peak is not None
    pct = s.reduction_from_peak * 100
    rsi = f"  RSI {s.rsi_14:.0f}" if s.rsi_14 is not None else ""
    row = f"{escape(s.name):<10} ↓{pct:.0f}%{rsi}"
    return f"  <b>{row}</b>" if is_high_confidence(s) else f"  {row}"


def _strength_key(s: Signal) -> tuple[bool, float]:
    """Sort order within a direction bucket: high-confidence rows first, then
    SHALLOWEST reduction first.

    This used to rank deepest-reduction first, on the assumption that a bigger
    flatten was a stronger read. Measurement says the opposite — bearish fires at
    0.3-0.4 reduction returned +1.78% EV against -0.99% for 0.8-1.0, because a
    deeply-flattened histogram means the move is already over. Sorting ascending
    puts the best rows at the top, where the bolding is actually useful.
    """
    return (not is_high_confidence(s), s.reduction_from_peak or 0.0)


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

    lines.append("")
    lines.append(f"{_STAGE_HEADER} ({len(signals)})")
    for direction in ("bearish", "bullish"):
        rows = sorted(
            [s for s in signals if s.direction == direction],
            key=_strength_key,
        )
        if not rows:
            continue
        lines.append(f"{_DIRECTION_EMOJI[direction]} {direction.upper()} ({len(rows)})")
        for s in rows:
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
    parse_mode: str | None = None,
) -> None:
    """Post one chunk. `parse_mode` is opt-in per call site: the signal body asks for
    HTML so it can bold rows, but error alerts must stay plain — a Python traceback
    contains `<module>`, which Telegram would reject as malformed HTML.
    """
    url = f"https://api.telegram.org/bot{cfg.telegram.bot_token}/sendMessage"
    payload: dict = {
        "chat_id": cfg.telegram.chat_id,
        "text": text,
        "disable_web_page_preview": True,
    }
    if parse_mode:
        payload["parse_mode"] = parse_mode
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
            await _send_one(client, chunk, cfg, parse_mode="HTML")
    return "sent"
