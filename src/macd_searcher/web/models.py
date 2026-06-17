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


# ---------- performance / outcomes (/api/perf/*) ----------


class PerfReadiness(BaseModel):
    total: int
    finalized: int
    have_1d: int
    have_3d: int
    have_7d: int
    have_14d: int
    oldest_pending: Optional[str] = None
    pending: int


class PerfStageDirection(BaseModel):
    stage: str
    direction: str
    n: int
    win_pct: Optional[float] = None
    avg_ret_pct: Optional[float] = None
    worst_pct: Optional[float] = None
    best_pct: Optional[float] = None


class PerfHorizon(BaseModel):
    stage: str
    ret_1d: Optional[float] = None
    n_1d: int
    ret_3d: Optional[float] = None
    n_3d: int
    ret_7d: Optional[float] = None
    n_7d: int
    ret_14d: Optional[float] = None
    n_14d: int


class PerfLeadTime(BaseModel):
    stage: str
    finalized_n: int
    crossed_n: int
    cross_rate_pct: Optional[float] = None
    avg_bars_to_cross: Optional[float] = None
    min_bars: Optional[int] = None
    max_bars: Optional[int] = None


class PerfExcursion(BaseModel):
    stage: str
    direction: str
    n: int
    avg_mfe_pct: Optional[float] = None
    avg_mae_pct: Optional[float] = None


class PerfSymbol(BaseModel):
    symbol: str
    asset_class: Optional[str] = None
    n: int
    win_pct: Optional[float] = None
    avg_ret_pct: Optional[float] = None


class PerfClassStage(BaseModel):
    asset_class: Optional[str] = None
    stage: str
    n: int
    win_pct: Optional[float] = None
    avg_ret_pct: Optional[float] = None


class PerfBucket(BaseModel):
    bucket: str
    n: int
    win_pct: Optional[float] = None
    avg_ret_pct: Optional[float] = None


class PerfDistribution(BaseModel):
    stage: str
    direction: str
    metric: str
    n: int
    # All in percent points. `min`/`max` shadow builtins only as field names.
    min: Optional[float] = None
    p10: Optional[float] = None
    p25: Optional[float] = None
    median: Optional[float] = None
    p75: Optional[float] = None
    p90: Optional[float] = None
    max: Optional[float] = None
    mean: Optional[float] = None
    winsorized_mean: Optional[float] = None
    std: Optional[float] = None
