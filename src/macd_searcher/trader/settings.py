"""The settings of the trading bot: its own YAML file and its own ``.env``.

The detector settings come from the installed ``macd_searcher`` (``load_packaged``), so
that they are the settings of the commit that the bot trades. The YAML file and
``.env`` are in the working directory, because the cron line starts the bot there.
"""

from __future__ import annotations

import os
from pathlib import Path

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field

from macd_searcher.config import AppConfig, TelegramSecrets, load_packaged


class TraderConfig(BaseModel):
    db_path: str = "state/trader.sqlite3"
    # The equity of the paper account on its first day.
    paper_equity_usd: float = Field(10_000, gt=0)
    # The live bot has its own ledger, and it sends orders to this exchange. The
    # default is the testnet, so a live run with real money needs a deliberate edit.
    live_db_path: str = "state/trader_live.sqlite3"
    live_url: str = "https://api.hyperliquid-testnet.xyz"


def load(path: str | None = None) -> tuple[AppConfig, TraderConfig]:
    """The detector settings with the bot's Telegram secrets, and the bot's settings.

    The messages go to ``TRADER_TELEGRAM_CHAT_ID`` when it is set, so that a halt is not
    lost among the scanner's alerts.
    """
    load_dotenv(Path.cwd() / ".env", override=False)
    raw = yaml.safe_load(Path(path or "trader.yaml").read_text(encoding="utf-8")) or {}
    secrets = TelegramSecrets(bot_token=os.environ.get("TELEGRAM_BOT_TOKEN", ""),
                              chat_id=os.environ.get("TRADER_TELEGRAM_CHAT_ID")
                              or os.environ.get("TELEGRAM_CHAT_ID", ""))
    return load_packaged().model_copy(update={"telegram": secrets}), TraderConfig.model_validate(raw)
