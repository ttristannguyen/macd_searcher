"""Hyperliquid Info API client.

Two endpoints used:
  - `metaAndAssetCtxs`: returns the perp universe + live volume / OI / mark price.
    Used once per run to build the filtered asset list.
  - `candleSnapshot`: returns OHLCV for one coin over a time range.
    Called concurrently for every surviving asset.

All requests are POST against `<base_url>/info` with a JSON body. No auth.
"""

from __future__ import annotations

import asyncio
import logging
import random
import time
from dataclasses import dataclass

import httpx
import pandas as pd

from .config import AppConfig


log = logging.getLogger(__name__)


@dataclass(frozen=True)
class AssetMeta:
    """A perp that passed the liquidity filter."""

    name: str
    mark_px: float
    day_ntl_vlm_usd: float
    open_interest_coin: float
    open_interest_usd: float


class HyperliquidError(RuntimeError):
    """Raised when the Info API returns an unexpected response."""


async def _post_info(
    client: httpx.AsyncClient,
    body: dict,
    cfg: AppConfig,
) -> object:
    """POST /info with retry on 429 / 5xx / network errors."""
    url = f"{cfg.hyperliquid.base_url.rstrip('/')}/info"
    last_exc: Exception | None = None
    for attempt in range(1, cfg.hyperliquid.retry_attempts + 1):
        try:
            resp = await client.post(url, json=body, timeout=cfg.hyperliquid.request_timeout_s)
            if resp.status_code == 200:
                return resp.json()
            if resp.status_code in (429, 500, 502, 503, 504):
                last_exc = HyperliquidError(
                    f"HTTP {resp.status_code} on {body.get('type')}: {resp.text[:200]}"
                )
            else:
                raise HyperliquidError(
                    f"HTTP {resp.status_code} on {body.get('type')}: {resp.text[:200]}"
                )
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            last_exc = exc

        if attempt < cfg.hyperliquid.retry_attempts:
            delay = cfg.hyperliquid.retry_backoff_s * (2 ** (attempt - 1))
            delay += random.uniform(0, delay * 0.25)
            log.warning(
                "Hyperliquid %s attempt %d failed (%s); retrying in %.2fs",
                body.get("type"),
                attempt,
                last_exc,
                delay,
            )
            await asyncio.sleep(delay)

    assert last_exc is not None
    raise last_exc


async def _fetch_meta_and_ctxs(
    client: httpx.AsyncClient,
    cfg: AppConfig,
    dex: str | None,
) -> tuple[list[dict], list[dict]]:
    """Call metaAndAssetCtxs for one DEX. dex=None means the core perp universe."""
    body: dict = {"type": "metaAndAssetCtxs"}
    if dex is not None:
        body["dex"] = dex
    payload = await _post_info(client, body, cfg)
    if not (isinstance(payload, list) and len(payload) == 2):
        raise HyperliquidError(
            f"Unexpected metaAndAssetCtxs shape for dex={dex!r}: {type(payload).__name__}"
        )
    meta, asset_ctxs = payload
    universe = meta.get("universe", [])
    if len(universe) != len(asset_ctxs):
        raise HyperliquidError(
            f"dex={dex!r}: universe length {len(universe)} != asset_ctxs length {len(asset_ctxs)}"
        )
    return universe, asset_ctxs


async def fetch_universe(client: httpx.AsyncClient, cfg: AppConfig) -> tuple[list[AssetMeta], int]:
    """Fetch core perp universe + any configured HIP-3 DEXes; apply liquidity filter.

    Returns ``(kept_assets, total_seen)`` where ``total_seen`` is the count
    across all DEXes before filtering (useful for the run log).

    Universe entries from HIP-3 DEXes come pre-prefixed (e.g. ``xyz:TSLA``),
    and Hyperliquid's ``candleSnapshot`` accepts those prefixed symbols
    directly, so no symbol munging is needed downstream.
    """
    sources: list[str | None] = [None] + list(cfg.hyperliquid.extra_dexes)
    min_vol = cfg.universe_filter.min_24h_volume_usd
    min_oi = cfg.universe_filter.min_open_interest_usd

    out: list[AssetMeta] = []
    total_seen = 0
    skipped_delisted = 0
    skipped_disabled = 0
    skipped_illiquid = 0

    for dex in sources:
        universe, asset_ctxs = await _fetch_meta_and_ctxs(client, cfg, dex)
        total_seen += len(universe)
        per_dex_kept = 0

        for u, ctx in zip(universe, asset_ctxs):
            if u.get("isDelisted"):
                skipped_delisted += 1
                continue
            # HIP-3 entries carry a growthMode field; treat anything other than
            # "enabled" as off-limits to avoid trading on paused/withdrawn markets.
            gm = u.get("growthMode")
            if gm is not None and gm != "enabled":
                skipped_disabled += 1
                continue
            try:
                mark_px = float(ctx["markPx"])
                day_ntl_vlm = float(ctx["dayNtlVlm"])
                oi_coin = float(ctx["openInterest"])
            except (KeyError, TypeError, ValueError) as exc:
                log.warning("Skipping %s: bad asset_ctx fields (%s)", u.get("name"), exc)
                continue

            oi_usd = oi_coin * mark_px
            if day_ntl_vlm < min_vol or oi_usd < min_oi:
                skipped_illiquid += 1
                continue

            out.append(
                AssetMeta(
                    name=u["name"],
                    mark_px=mark_px,
                    day_ntl_vlm_usd=day_ntl_vlm,
                    open_interest_coin=oi_coin,
                    open_interest_usd=oi_usd,
                )
            )
            per_dex_kept += 1

        log.info(
            "  dex=%s: %d entries, %d kept after filters",
            dex if dex is not None else "core",
            len(universe),
            per_dex_kept,
        )

    log.info(
        "Universe: %d total across %d DEX(es) → %d kept "
        "(skipped %d delisted, %d disabled, %d illiquid; vol>=$%.0fM and OI>=$%.0fM)",
        total_seen,
        len(sources),
        len(out),
        skipped_delisted,
        skipped_disabled,
        skipped_illiquid,
        min_vol / 1e6,
        min_oi / 1e6,
    )
    return out, total_seen


async def _fetch_one_candles(
    client: httpx.AsyncClient,
    coin: str,
    cfg: AppConfig,
    start_ms: int,
    end_ms: int,
) -> pd.DataFrame:
    body = {
        "type": "candleSnapshot",
        "req": {
            "coin": coin,
            "interval": cfg.candles.interval,
            "startTime": start_ms,
            "endTime": end_ms,
        },
    }
    raw = await _post_info(client, body, cfg)
    if not isinstance(raw, list):
        raise HyperliquidError(f"candleSnapshot for {coin} returned {type(raw).__name__}")

    if not raw:
        return pd.DataFrame(columns=["ts", "open", "high", "low", "close", "volume"])

    df = pd.DataFrame(raw)
    df = df.rename(columns={"t": "ts", "o": "open", "h": "high", "l": "low", "c": "close", "v": "volume"})
    df["ts"] = pd.to_datetime(df["ts"], unit="ms", utc=True)
    for col in ("open", "high", "low", "close", "volume"):
        df[col] = df[col].astype(float)
    df = df[["ts", "open", "high", "low", "close", "volume"]].sort_values("ts").reset_index(drop=True)

    # The forming (current, incomplete) bar is intentionally kept here. Whether
    # to use it is a per-detector decision made in signals.py, so the data layer
    # always returns the full series including today.
    return df


async def fetch_all_candles(
    client: httpx.AsyncClient,
    assets: list[AssetMeta],
    cfg: AppConfig,
) -> dict[str, pd.DataFrame]:
    """Fetch 1D candles for every asset concurrently.

    Assets whose fetch fails are logged and dropped from the result.
    """
    end_ms = int(time.time() * 1000)
    start_ms = end_ms - cfg.candles.lookback_days * 86_400_000

    sem = asyncio.Semaphore(cfg.hyperliquid.concurrency)

    async def _bounded(coin: str) -> tuple[str, pd.DataFrame | None]:
        async with sem:
            try:
                df = await _fetch_one_candles(client, coin, cfg, start_ms, end_ms)
                return coin, df
            except Exception as exc:  # noqa: BLE001 — log and continue
                log.warning("Candle fetch failed for %s: %s", coin, exc)
                return coin, None

    results = await asyncio.gather(*(_bounded(a.name) for a in assets))
    out = {coin: df for coin, df in results if df is not None}
    log.info("Fetched candles for %d / %d assets", len(out), len(assets))
    return out


async def fetch_universe_and_candles(
    cfg: AppConfig,
) -> tuple[list[AssetMeta], dict[str, pd.DataFrame], int]:
    """One-shot helper: open a client, filter universe, fetch all candles.

    Returns ``(assets, candles, universe_total)``.
    """
    async with httpx.AsyncClient() as client:
        assets, universe_total = await fetch_universe(client, cfg)
        candles = await fetch_all_candles(client, assets, cfg)
    return assets, candles, universe_total
