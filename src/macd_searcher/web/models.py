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
    fire_reduction_from_peak: Optional[float] = None
    fire_rsi_14: Optional[float] = None
    # This excursion's peak vs the token's own prior same-sign tops. NULL on rows
    # that predate the columns and were never backfilled; top_n is the trust gauge.
    fire_hist_peak_ratio: Optional[float] = None
    fire_hist_peak_pct: Optional[float] = None
    fire_hist_top_n: Optional[int] = None


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


class PerfHorizonPoint(BaseModel):
    horizon: str
    n: int
    # all percent points; avg=mean, best=max, worst=min over the deduped returns.
    win_pct: float
    avg_ret_pct: float
    median_pct: float
    p25_pct: float
    p75_pct: float
    best_pct: float
    worst_pct: float
    std_pct: Optional[float] = None


class PerfLeadTime(BaseModel):
    stage: str
    finalized_n: int
    crossed_n: int
    cross_rate_pct: Optional[float] = None
    avg_bars_to_cross: Optional[float] = None
    min_bars: Optional[int] = None
    max_bars: Optional[int] = None


class PerfSymbolScore(BaseModel):
    symbol: str
    asset_class: Optional[str] = None
    n: int
    # all percent points; win_lo/hi = Wilson CI, ev_lo/hi = BCa bootstrap CI.
    win_pct: float
    win_lo: float
    win_hi: float
    ev_pct: float
    ev_lo: float
    ev_hi: float
    payoff: Optional[float] = None  # avg win / avg |loss|; None if no losses
    sqn: Optional[float] = None     # Van Tharp System Quality Number; None if std=0


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


class PerfRsiBucket(BaseModel):
    horizon: str
    direction: str
    rsi_bucket: str
    n: int
    win_pct: Optional[float] = None
    avg_ret_pct: Optional[float] = None


class PerfPeakBucket(BaseModel):
    horizon: str
    direction: str
    # Percentile band of this excursion's peak among the token's own prior
    # same-sign tops (e.g. 'a <20'). Low = a modest peak by this token's standards.
    bucket: str
    n: int
    win_pct: Optional[float] = None
    avg_ret_pct: Optional[float] = None


class PerfMacdSignalBucket(BaseModel):
    horizon: str
    direction: str
    # ATR-normalized MACD signal line at fire, signed (e.g. 'e 0.5..1').
    bucket: str
    n: int
    win_pct: Optional[float] = None
    avg_ret_pct: Optional[float] = None


class PerfReductionCounterfactual(BaseModel):
    bucket: str
    n: int
    # EV/win reconstructed from snapshot closes (faithful); drawdown is a
    # close-based proxy that understates true intraday MAE. All percent points.
    win_pct: float
    ev_pct: float
    drawdown_proxy_pct: float


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
