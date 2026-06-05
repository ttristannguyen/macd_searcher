"""End-to-end dry-run: fetch live signals, then render the Telegram message.

The notify module is forced into dry-run mode so nothing is actually sent —
the message body just gets printed.
"""

from __future__ import annotations

import asyncio
import logging
import sys

# Windows consoles default to cp1252 which can't encode the emoji glyphs in the
# Telegram body. On Linux/VPS this is the default anyway.
sys.stdout.reconfigure(encoding="utf-8")

from macd_searcher.config import load_config
from macd_searcher.hyperliquid import fetch_universe_and_candles
from macd_searcher.notify import send_signals
from macd_searcher.signals import evaluate_all


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    cfg = load_config()
    # Force dry-run regardless of config so this script never sends anything.
    cfg = cfg.model_copy(update={
        "notify": cfg.notify.model_copy(update={"dry_run": True}),
    })

    _, candles, _ = await fetch_universe_and_candles(cfg)
    signals = evaluate_all(candles, cfg)
    await send_signals(signals, scanned_count=len(candles), cfg=cfg)


if __name__ == "__main__":
    asyncio.run(main())
