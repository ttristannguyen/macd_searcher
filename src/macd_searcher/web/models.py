"""Pydantic response models — typed API + free Swagger docs at /docs."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel


HealthStatus = Literal["ok", "stale", "down"]


class TableCounts(BaseModel):
    runs: int
    asset_snapshots: int
    signals: int


class LatestRun(BaseModel):
    run_id: str
    started_at: str
    completed_at: Optional[str] = None
    duration_s: Optional[float] = None
    code_version: Optional[str] = None
    universe_total: Optional[int] = None
    universe_kept: Optional[int] = None
    signals_count: Optional[int] = None
    notify_status: Optional[str] = None
    error: Optional[str] = None


class Health(BaseModel):
    status: HealthStatus
    counts: TableCounts
    latest_run: Optional[LatestRun] = None
    last_run_age_seconds: Optional[float] = None
    expected_interval_seconds: int


class RunRow(BaseModel):
    started_at: str
    universe_total: Optional[int] = None
    universe_kept: Optional[int] = None
    signals_count: Optional[int] = None
    notify_status: Optional[str] = None
    duration_s: Optional[float] = None


class DayCount(BaseModel):
    day: str
    runs: Optional[int] = None
    signals: Optional[int] = None


class NotifyStatusRow(BaseModel):
    notify_status: Optional[str] = None
    n: int


class SignalRow(BaseModel):
    fired_at: str
    symbol: str
    asset_class: Optional[str] = None
    stage: str
    direction: str
    fire_close: Optional[float] = None
    fire_macd: Optional[float] = None
    fire_macd_pct_of_price: Optional[float] = None
    fire_reduction_from_peak: Optional[float] = None


class StageDirectionRow(BaseModel):
    stage: str
    direction: str
    n: int


class ClassCountRow(BaseModel):
    asset_class: Optional[str] = None
    n: int


class SymbolCountRow(BaseModel):
    symbol: str
    fires: int


class ProximityHeadroom(BaseModel):
    avg_assets_under_0_2pct: Optional[float] = None
    avg_assets_under_0_5pct: Optional[float] = None
    avg_assets_under_1pct: Optional[float] = None
