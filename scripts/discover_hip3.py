"""Probe HIP-3 endpoints to decide how to integrate dex='xyz' into our fetch."""

from __future__ import annotations

import asyncio
import json
import time

import httpx

BASE = "https://api.hyperliquid.xyz/info"


async def post(client: httpx.AsyncClient, body: dict) -> object:
    r = await client.post(BASE, json=body, timeout=15.0)
    r.raise_for_status()
    return r.json()


async def main() -> None:
    async with httpx.AsyncClient() as client:
        print("=== metaAndAssetCtxs with dex='xyz' ===")
        try:
            payload = await post(client, {"type": "metaAndAssetCtxs", "dex": "xyz"})
            if isinstance(payload, list) and len(payload) == 2:
                meta, ctxs = payload
                univ = meta.get("universe", [])
                print(f"universe entries: {len(univ)}")
                print(f"first universe entry: {json.dumps(univ[0], indent=2) if univ else 'empty'}")
                print(f"first asset ctx: {json.dumps(ctxs[0], indent=2) if ctxs else 'empty'}")
                # Sum 24h vol to sanity-check liquidity
                total_vol = sum(float(c.get("dayNtlVlm", 0)) for c in ctxs)
                print(f"total dayNtlVlm across xyz: ${total_vol:,.0f}")
            else:
                print(f"unexpected: {payload!r}")
        except Exception as exc:
            print(f"error: {exc}")

        end_ms = int(time.time() * 1000)
        start_ms = end_ms - 5 * 86_400_000

        print("\n=== candleSnapshot for 'xyz:TSLA' (prefixed) ===")
        try:
            candles = await post(client, {
                "type": "candleSnapshot",
                "req": {"coin": "xyz:TSLA", "interval": "1d", "startTime": start_ms, "endTime": end_ms},
            })
            print(f"got {len(candles) if isinstance(candles, list) else 'n/a'} candles")
            if isinstance(candles, list) and candles:
                print(f"sample: {candles[-1]}")
        except Exception as exc:
            print(f"error: {exc}")

        print("\n=== candleSnapshot for 'TSLA' (bare) ===")
        try:
            candles = await post(client, {
                "type": "candleSnapshot",
                "req": {"coin": "TSLA", "interval": "1d", "startTime": start_ms, "endTime": end_ms},
            })
            print(f"got {len(candles) if isinstance(candles, list) else 'n/a'} candles")
            if isinstance(candles, list) and candles:
                print(f"sample: {candles[-1]}")
        except Exception as exc:
            print(f"error: {exc}")


if __name__ == "__main__":
    asyncio.run(main())
