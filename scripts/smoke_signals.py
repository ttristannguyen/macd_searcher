"""End-to-end smoke test: pull live Hyperliquid candles → run all detectors."""

from __future__ import annotations

import asyncio
import logging

from macd_searcher.config import load_config
from macd_searcher.hyperliquid import fetch_universe_and_candles
from macd_searcher.signals import evaluate_all


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    cfg = load_config()
    _, candles, _ = await fetch_universe_and_candles(cfg)
    signals = evaluate_all(candles, cfg)

    by_stage_dir: dict[tuple[str, str], list] = {}
    for s in signals:
        by_stage_dir.setdefault((s.stage, s.direction), []).append(s)

    print(f"\n=== {len(signals)} signal(s) on {len(candles)} assets ===")
    for (stage, direction), items in sorted(by_stage_dir.items()):
        print(f"\n[{stage} / {direction}] {len(items)}")
        for s in items:
            extras = []
            if s.macd_pct_of_price is not None:
                extras.append(f"|MACD|/px={s.macd_pct_of_price:.4%}")
            if s.atr_multiple is not None:
                extras.append(f"|MACD|/ATR={s.atr_multiple:.2f}")
            if s.reduction_from_peak is not None:
                extras.append(f"hist down {s.reduction_from_peak:.0%} from {s.hist_peak:+.4f}")
            extra_s = " | ".join(extras)
            print(f"  {s.name:<10} px=${s.close:>12,.4f}  MACD={s.macd:+9.4f}  hist={s.hist:+9.4f}  {extra_s}")


if __name__ == "__main__":
    asyncio.run(main())
