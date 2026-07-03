"""Configuration loader.

YAML file holds tunable behaviour; .env holds secrets. Both are merged into
a single immutable AppConfig that the rest of the app reads.
"""

from __future__ import annotations

import os
from datetime import time
from pathlib import Path

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field, field_validator, model_validator


class HistogramFlatteningConfig(BaseModel):
    """The histogram_flattening detector — our sole signal.

    Fires when the MACD histogram (macd - signal) has peaked above the noise
    floor and is now shrinking back toward zero. Direction is set by which
    side of zero the histogram peaked on.
    """

    enabled: bool = True
    shrink_lookback: int = Field(3, ge=2)
    min_peak_pct_of_price: float = Field(0.002, ge=0)
    min_reduction_from_peak: float = Field(0.3, ge=0, le=1)
    peak_lookback: int = Field(10, ge=2)
    # Reads today's still-forming daily bar so it can join momentum intraday.
    use_forming_candle: bool = True


class SignalConfig(BaseModel):
    """Detector configuration — histogram_flattening only."""

    histogram_flattening: HistogramFlatteningConfig = HistogramFlatteningConfig()


class MACDConfig(BaseModel):
    fast: int = Field(12, gt=0)
    slow: int = Field(26, gt=0)
    signal: int = Field(9, gt=0)

    @model_validator(mode="after")
    def _slow_gt_fast(self) -> "MACDConfig":
        if self.slow <= self.fast:
            raise ValueError("macd.slow must be greater than macd.fast")
        return self


class CandlesConfig(BaseModel):
    interval: str = "1d"
    lookback_days: int = Field(200, ge=35)


class HyperliquidConfig(BaseModel):
    base_url: str = "https://api.hyperliquid.xyz"
    concurrency: int = Field(10, gt=0)
    request_timeout_s: float = Field(15.0, gt=0)
    retry_attempts: int = Field(3, ge=1)
    retry_backoff_s: float = Field(1.0, ge=0)
    # HIP-3 builder-deployed perp DEXes to include alongside the core perp
    # universe. "xyz" exposes equities (TSLA, NVDA, ...), commodities (GOLD,
    # BRENTOIL, ...), and FX (EUR, GBP, ...). Empty list disables HIP-3.
    extra_dexes: list[str] = ["xyz"]


class UniverseFilterConfig(BaseModel):
    min_24h_volume_usd: float = Field(1_000_000, ge=0)
    min_open_interest_usd: float = Field(1_000_000, ge=0)


class QuietHoursConfig(BaseModel):
    enabled: bool = True
    timezone: str = "Australia/Melbourne"
    start: time = time(0, 0)
    end: time = time(8, 0)

    @field_validator("start", "end", mode="before")
    @classmethod
    def _parse_hhmm(cls, v: object) -> object:
        if isinstance(v, str):
            hh, mm = v.split(":")
            return time(int(hh), int(mm))
        return v


class NotifyConfig(BaseModel):
    send_when_empty: bool = True
    quiet_hours: QuietHoursConfig = QuietHoursConfig()
    dry_run: bool = False


class DatabaseConfig(BaseModel):
    enabled: bool = True
    path: str = "state/macd_searcher.sqlite3"


class OutcomesConfig(BaseModel):
    # How many days forward the update_outcomes job scores each signal:
    # the MFE/MAE window and the zero-cross search horizon. The px_1d/3d/7d/14d
    # columns are fixed regardless. A signal is finalized once this many days
    # have elapsed since it fired.
    horizon_days: int = Field(14, ge=1)


class TelegramSecrets(BaseModel):
    bot_token: str = ""
    chat_id: str = ""

    @property
    def configured(self) -> bool:
        return bool(self.bot_token and self.chat_id)


class AppConfig(BaseModel):
    signal: SignalConfig = SignalConfig()
    macd: MACDConfig = MACDConfig()
    candles: CandlesConfig = CandlesConfig()
    hyperliquid: HyperliquidConfig = HyperliquidConfig()
    universe_filter: UniverseFilterConfig = UniverseFilterConfig()
    notify: NotifyConfig = NotifyConfig()
    database: DatabaseConfig = DatabaseConfig()
    outcomes: OutcomesConfig = OutcomesConfig()
    telegram: TelegramSecrets = TelegramSecrets()
    log_level: str = "INFO"


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def load_config(config_path: str | os.PathLike[str] | None = None) -> AppConfig:
    """Load YAML + .env into an AppConfig.

    Resolution order:
      1. `config_path` argument
      2. `MACD_SEARCHER_CONFIG` env var
      3. `<project_root>/config.yaml`
    """
    load_dotenv(_project_root() / ".env", override=False)

    path = (
        Path(config_path)
        if config_path is not None
        else Path(os.environ.get("MACD_SEARCHER_CONFIG", _project_root() / "config.yaml"))
    )

    if not path.is_file():
        raise FileNotFoundError(f"Config file not found: {path}")

    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    raw["telegram"] = {
        "bot_token": os.environ.get("TELEGRAM_BOT_TOKEN", ""),
        "chat_id": os.environ.get("TELEGRAM_CHAT_ID", ""),
    }
    if lvl := os.environ.get("MACD_SEARCHER_LOG_LEVEL"):
        raw["log_level"] = lvl

    return AppConfig.model_validate(raw)
