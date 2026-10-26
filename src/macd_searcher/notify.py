"""Telegram notification + dispatch gates.

Responsibilities:
  - Format the message body (with sane truncation if it would exceed Telegram's
    4096-char limit). Two messages, both grouped by B3 leg
    (docs/trading_strategy.md): the daily book from the 00:00 UTC run, and each
    other run's forming-candle fires.
  - Decide whether to actually send: skipped during quiet hours, skipped in
    dry-run mode, skipped if Telegram secrets are missing. In all of those
    cases the body is still printed to stdout so the cron log captures it.
  - Send via raw HTTP to api.telegram.org with simple retry on transient
    failures.

Sent with HTML parse_mode so the day's new positions can be bolded; HTML was chosen
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

from .book import LEGS, LONG_LEGS, Book, Leg, Position, leg_of
from .classify import classify_asset
from .config import AppConfig
from .signals import Signal, signal_line_atr_multiple


log = logging.getLogger(__name__)

# Telegram's hard cap is 4096 chars; chunk well below for safety.
_CHUNK_SOFT_CAP = 3800

# Green for the legs held long, red for the legs held short. L2 is a bearish fire
# held long, so colour follows the trade, not the fire's direction.
_LEG_HEADER: dict[Leg, str] = {
    "L1": "🟢 L1 LONG · bullish pk ≤ 25",
    "L2": "🟢 L2 LONG · bearish pk ≥ 50",
    "S1": "🔴 S1 SHORT · bearish pk ≤ 25",
    "S2": "🔴 S2 SHORT · bullish 50 < pk < 100",
}


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
    What's left is what drives the read: how far it has flattened, where the trend
    sits (`sig`), how big this swing is for the token (`pk`), and RSI as context.

    * `sig` — the MACD signal line in ATR units (negative = trend below equilibrium).
      ATR, not % of price, because it means the same thing on BTC and on gold; it is
      also the axis the dashboard buckets into octiles. The %-of-price reading was
      dropped from the row (2026-10-16); it is still on the dashboard.
    * `pk` — where this excursion's peak ranks among the token's own completed swings
      of the same sign in the lookback (0 = smallest, 100 = deepest). It is what puts
      the fire in its B3 leg. There is deliberately no record-trough warning: it was
      shipped on 2026 live data and did not replicate in history.
    """
    assert s.reduction_from_peak is not None
    pct = s.reduction_from_peak * 100
    sig_atr = signal_line_atr_multiple(s)
    sig = f"  sig {sig_atr:+.2f}×ATR" if sig_atr is not None else ""
    peak = f"  pk {s.hist_peak_pct:.0f}" if s.hist_peak_pct is not None else ""
    rsi = f"  RSI {s.rsi_14:.0f}" if s.rsi_14 is not None else ""
    return f"  {escape(s.name):<10} ↓{pct:.0f}%{sig}{peak}{rsi}"


def _reduction_key(s: Signal) -> float:
    """SHALLOWEST reduction first within a leg.

    This used to rank deepest-reduction first, on the assumption that a bigger
    flatten was a stronger read. Measurement says the opposite — bearish fires at
    0.3-0.4 reduction returned +1.78% EV against -0.99% for 0.8-1.0, because a
    deeply-flattened histogram means the move is already over.
    """
    return s.reduction_from_peak or 0.0


def _by_leg(signals: list[Signal]) -> dict[Leg, list[Signal]]:
    """Crypto fires in a B3 leg, grouped in leg order. Everything else is dropped:
    B3 was backtested on crypto perps only, and trades no other `pk` band."""
    out: dict[Leg, list[Signal]] = {leg: [] for leg in LEGS}
    for s in signals:
        leg = leg_of(s.direction, s.hist_peak_pct)
        if leg is not None and classify_asset(s.name) == "crypto":
            out[leg].append(s)
    return {leg: rows for leg, rows in out.items() if rows}


def format_message(
    signals: list[Signal],
    scanned_count: int,
    cfg: AppConfig,
    now_utc: datetime | None = None,
) -> str:
    """Render an intraday run's forming-candle fires, grouped by B3 leg. May exceed
    Telegram's per-message limit; callers should pass the result through
    `chunk_for_telegram` before sending."""
    when = (now_utc or datetime.now(tz=timezone.utc)).strftime("%Y-%m-%d %H:%M UTC")
    legs = _by_leg(signals)
    lines = [
        f"📊 MACD scan — {when}",
        f"{scanned_count} assets scanned, {sum(len(r) for r in legs.values())} in B3 legs",
        "",
    ]
    if not legs:
        lines.append("No B3 fires this cycle.")
        return "\n".join(lines)

    for leg, rows in legs.items():
        lines.append(f"{_LEG_HEADER[leg]} ({len(rows)})")
        lines.extend(_fmt_stage1_row(s) for s in sorted(rows, key=_reduction_key))
    return "\n".join(lines)


def _fmt_position_row(book: Book, p: Position) -> str:
    """Name, the `pk` that put it in its leg, and days held. A position opened today
    is bolded: it is the one to act on."""
    days = book.days_held(p)
    row = f"{escape(p.symbol):<10} pk {p.peak_pct:.0f}  {'new' if days == 0 else f'd{days}'}"
    return f"  <b>{row}</b>" if days == 0 else f"  {row}"


def format_book_message(book: Book) -> str:
    """Render the daily B3 book: every open position by leg, newest first, then the
    positions that expired today."""
    longs = sum(1 for p in book.positions if p.leg in LONG_LEGS)
    new = sum(1 for p in book.positions if p.entry == book.day)
    lines = [
        f"📒 B3 book — {book.day.isoformat()}",
        f"Long {longs} · Short {len(book.positions) - longs} · {new} new · {len(book.exits)} exits",
        "",
    ]
    if not book.positions and not book.exits:
        lines.append("No open B3 positions.")
        return "\n".join(lines)

    for leg in LEGS:
        rows = sorted((p for p in book.positions if p.leg == leg),
                      key=lambda p: (book.days_held(p), p.symbol))
        if rows:
            lines.append(f"{_LEG_HEADER[leg]} ({len(rows)})")
            lines.extend(_fmt_position_row(book, p) for p in rows)
    if book.exits:
        lines.append(f"⏹ EXITS ({len(book.exits)})")
        lines.extend(f"  {escape(p.symbol):<10} {p.leg}"
                     for p in sorted(book.exits, key=lambda p: (p.leg, p.symbol)))
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
    """Format + dispatch an intraday run's fires. Returns the dispatch status."""
    text = format_message(signals, scanned_count, cfg, now_utc=now_utc)
    return await _dispatch(text, not _by_leg(signals), cfg, now_utc)


async def send_book(book: Book, cfg: AppConfig, now_utc: datetime | None = None) -> str:
    """Format + dispatch the daily B3 book. Returns the dispatch status."""
    empty = not book.positions and not book.exits
    return await _dispatch(format_book_message(book), empty, cfg, now_utc)


async def _dispatch(text: str, empty: bool, cfg: AppConfig, now_utc: datetime | None) -> str:
    """Honors send_when_empty, dry_run, quiet hours, and missing credentials. In
    any non-send path the message body is still printed so cron logs capture the
    scan output.

    Returns a dispatch status for the run log:
    'sent' | 'empty_suppressed' | 'dry_run' | 'quiet_hours' | 'no_creds'.
    """
    if empty and not cfg.notify.send_when_empty:
        log.info("Nothing in the B3 legs; send_when_empty=false. Skipping send.")
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
