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
