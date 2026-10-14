"""Local cache of daily candles and hourly funding for the research pipeline.

Lives in a ``research_cache/`` folder next to the database it serves (normally
``state/``, gitignored), one CSV per symbol per kind. Anchored to the database
rather than the working directory: a relative path silently found nothing when run
from elsewhere, and the report fell back to a survivorship-biased benchmark. Every run tops it up incrementally, so only the first run
pays for a full history — about 45 minutes for funding, because the API
rate-limits history requests far below the scanner's concurrency.

A symbol that fails is logged and skipped rather than retried hard: the cache is
incremental, so the next run picks it up. A research report should never fail
because one HIP-3 market returned a 429.
"""

from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path

import httpx
import pandas as pd

from ..config import AppConfig
from ..hyperliquid import fetch_candles, fetch_funding_history

log = logging.getLogger(__name__)

# Candles start well before the first post-fix signal (2026-06-09) so that
# 200-bar indicators are warmed up by then. Funding is only needed around fires.
CANDLES_START = pd.Timestamp("2025-08-01", tz="UTC")
FUNDING_START = pd.Timestamp("2026-05-15", tz="UTC")
KINDS = ("candles", "funding")


def root_for(db_path: str | Path) -> Path:
    return Path(db_path).resolve().parent / "research_cache"


def _path(root: Path, kind: str, symbol: str) -> Path:
    # ':' is illegal in Windows filenames and HIP-3 symbols carry one (xyz:TSLA).
    return root / kind / f"{symbol.replace(':', '__')}.csv"


def read(root: Path, kind: str, symbol: str) -> pd.DataFrame | None:
    path = _path(root, kind, symbol)
    if not path.exists():
        return None
    df = pd.read_csv(path)
    df["ts"] = pd.to_datetime(df["ts"], utc=True, format="ISO8601")
    return df


def _write(root: Path, kind: str, symbol: str, df: pd.DataFrame) -> None:
    path = _path(root, kind, symbol)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)


def load(root: Path, kind: str, symbols: list[str]) -> dict[str, pd.DataFrame]:
    """Everything cached for ``symbols``; symbols with no cache file are absent."""
    out = {}
    for s in symbols:
        df = read(root, kind, s)
        if df is not None and len(df):
            out[s] = df
    return out


def _ms(ts: pd.Timestamp) -> int:
    return int(ts.timestamp() * 1000)


async def _top_up(client: httpx.AsyncClient, cfg: AppConfig, root: Path, kind: str, symbol: str) -> int:
    """Fetch what is missing for one symbol and merge it in. Returns new rows."""
    old = read(root, kind, symbol)
    now = pd.Timestamp.now(tz="UTC")
    if kind == "candles":
        # Re-fetch the last two bars: the newest was still forming when cached.
        start = CANDLES_START if old is None else old["ts"].max() - pd.Timedelta(days=2)
        new = await fetch_candles(client, symbol, cfg, _ms(start), _ms(now))
    else:
        start = FUNDING_START if old is None else old["ts"].max() + pd.Timedelta(milliseconds=1)
        new = await fetch_funding_history(client, symbol, cfg, _ms(start))
    if new.empty:
        return 0
    merged = new if old is None else pd.concat([old, new])
    merged = merged.drop_duplicates("ts", keep="last").sort_values("ts").reset_index(drop=True)
    _write(root, kind, symbol, merged)
    return len(merged) - (0 if old is None else len(old))


async def refresh(root: Path, symbols: list[str], cfg: AppConfig, kinds: tuple[str, ...] = KINDS,
                  pause_s: float = 1.0) -> list[str]:
    """Top up the cache for every symbol, one request at a time. Returns the
    ``kind:symbol`` entries that failed this run (they retry next run)."""
    failed = []
    async with httpx.AsyncClient() as client:
        for kind in kinds:
            t0 = time.time()
            for i, symbol in enumerate(symbols, 1):
                try:
                    await _top_up(client, cfg, root, kind, symbol)
                except Exception as exc:  # noqa: BLE001 — skip; incremental cache retries next run
                    log.warning("%s refresh failed for %s: %s", kind, symbol, exc)
                    failed.append(f"{kind}:{symbol}")
                if i % 40 == 0:
                    log.info("%s: %d/%d symbols (%.0fs)", kind, i, len(symbols), time.time() - t0)
                await asyncio.sleep(pause_s if kind == "funding" else pause_s / 4)
    return failed
