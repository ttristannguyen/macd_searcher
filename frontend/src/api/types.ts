// Mirrors the pydantic response models in src/macd_searcher/web/models.py

export type HealthStatus = 'ok' | 'stale' | 'down'

export interface TableCounts {
  runs: number
  asset_snapshots: number
  signals: number
}

export interface LatestRun {
  run_id: string
  started_at: string
  completed_at: string | null
  duration_s: number | null
  code_version: string | null
  universe_total: number | null
  universe_kept: number | null
  signals_count: number | null
  notify_status: string | null
  error: string | null
}

export interface Health {
  status: HealthStatus
  counts: TableCounts
  latest_run: LatestRun | null
  last_run_age_seconds: number | null
  expected_interval_seconds: number
}

export interface RunRow {
  started_at: string
  universe_total: number | null
  universe_kept: number | null
  signals_count: number | null
  notify_status: string | null
  duration_s: number | null
}

export interface DayCount {
  day: string
  runs?: number | null
  signals?: number | null
}

export interface NotifyStatusRow {
  notify_status: string | null
  n: number
}

export interface SignalRow {
  fired_at: string
  symbol: string
  asset_class: string | null
  stage: string
  direction: string
  fire_close: number | null
  fire_macd: number | null
  fire_macd_pct_of_price: number | null
  fire_reduction_from_peak: number | null
}

export interface StageDirectionRow {
  stage: string
  direction: string
  n: number
}

export interface ClassCountRow {
  asset_class: string | null
  n: number
}

export interface SymbolCountRow {
  symbol: string
  fires: number
}

export interface ProximityHeadroom {
  avg_assets_under_0_2pct: number | null
  avg_assets_under_0_5pct: number | null
  avg_assets_under_1pct: number | null
}

// ---------- performance / outcomes (/api/perf/*) ----------

export type Horizon = '1d' | '3d' | '7d' | '14d'

export interface PerfReadiness {
  total: number
  finalized: number
  have_1d: number
  have_3d: number
  have_7d: number
  have_14d: number
  oldest_pending: string | null
  pending: number
}

export interface PerfStageDirection {
  stage: string
  direction: string
  n: number
  win_pct: number | null
  avg_ret_pct: number | null
  worst_pct: number | null
  best_pct: number | null
}

export interface PerfHorizon {
  stage: string
  ret_1d: number | null
  n_1d: number
  ret_3d: number | null
  n_3d: number
  ret_7d: number | null
  n_7d: number
  ret_14d: number | null
  n_14d: number
}

export interface PerfLeadTime {
  stage: string
  finalized_n: number
  crossed_n: number
  cross_rate_pct: number | null
  avg_bars_to_cross: number | null
  min_bars: number | null
  max_bars: number | null
}

export interface PerfExcursion {
  stage: string
  direction: string
  n: number
  avg_mfe_pct: number | null
  avg_mae_pct: number | null
}

export interface PerfSymbol {
  symbol: string
  asset_class: string | null
  n: number
  win_pct: number | null
  avg_ret_pct: number | null
}

export interface PerfClassStage {
  asset_class: string | null
  stage: string
  n: number
  win_pct: number | null
  avg_ret_pct: number | null
}
