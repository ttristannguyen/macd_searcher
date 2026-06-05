"""Quick live-network smoke test for hyperliquid.py.

Run: uv run python scripts/smoke_hyperliquid.py
"""

from __future__ import annotations

import asyncio
import logging

from macd_searcher.config import load_config
from macd_searcher.hyperliquid import fetch_universe_and_candles


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    cfg = load_config()
    assets, candles, _ = await fetch_universe_and_candles(cfg)

    print(f"\n=== Kept {len(assets)} assets ===")
    for a in sorted(assets, key=lambda x: -x.day_ntl_vlm_usd)[:10]:
        print(
            f"  {a.name:<8}  vol24h=${a.day_ntl_vlm_usd:>14,.0f}  "
            f"OI=${a.open_interest_usd:>14,.0f}  px=${a.mark_px:,.4f}"
        )

    print(f"\n=== Candle samples ===")
    for name in [a.name for a in assets[:3]]:
        df = candles.get(name)
        if df is None or df.empty:
            print(f"  {name}: no candles")
            continue
        print(f"  {name}: {len(df)} bars, last close = {df['close'].iloc[-1]:.4f} @ {df['ts'].iloc[-1]}")


if __name__ == "__main__":
    asyncio.run(main())
