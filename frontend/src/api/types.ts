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
  fire_reduction_from_peak: number | null
  fire_rsi_14: number | null
  // Peak vs this token's own prior same-sign tops. null on signals that predate
  // the columns and were never backfilled; top_n is how many priors back it.
  fire_hist_peak_ratio: number | null
  fire_hist_peak_pct: number | null
  fire_hist_top_n: number | null
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

// One row per horizon for the Charts view (overall strategy). All percent points.
export interface PerfHorizonPoint {
  horizon: string
  n: number
  win_pct: number
  avg_ret_pct: number
  median_pct: number
  p25_pct: number
  p75_pct: number
  best_pct: number
  worst_pct: number
  std_pct: number | null
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

export type PerfMetric = 'ret_1d' | 'ret_3d' | 'ret_7d' | 'ret_14d' | 'mfe' | 'mae'

export interface PerfDistribution {
  stage: string
  direction: string
  metric: string
  n: number
  min: number | null
  p10: number | null
  p25: number | null
  median: number | null
  p75: number | null
  p90: number | null
  max: number | null
  mean: number | null
  winsorized_mean: number | null
  std: number | null
}

export interface PerfSymbolScore {
  symbol: string
  asset_class: string | null
  n: number
  win_pct: number
  win_lo: number
  win_hi: number
  ev_pct: number
  ev_lo: number
  ev_hi: number
  payoff: number | null
  sqn: number | null
}

export interface PerfClassStage {
  asset_class: string | null
  stage: string
  n: number
  win_pct: number | null
  avg_ret_pct: number | null
}

export interface PerfBucket {
  bucket: string
  n: number
  win_pct: number | null
  avg_ret_pct: number | null
}

// One row per (horizon, direction, RSI-at-fire bucket). The frontend pivots this
// into heatmaps/lines — see components/OutcomesCharts.tsx.
export interface PerfRsiBucket {
  horizon: string
  direction: string
  rsi_bucket: string
  n: number
  win_pct: number | null
  avg_ret_pct: number | null
}

// The confidence cohort: 'confident' = the measured high-expectancy slice,
// 'rest' = every other scored signal. Derived from existing columns (no stored
// flag), so it applies retroactively to backfilled history.
export interface PerfConfidenceSummary {
  cohort: string
  horizon: string
  n: number
  share_pct: number
  win_pct: number
  ev_pct: number
  median_pct: number
  mfe_pct: number | null
  mae_pct: number | null
  payoff: number | null
}

export interface PerfConfidencePoint {
  cohort: string
  month: string
  n: number
  win_pct: number | null
  ev_pct: number | null
}

export interface PerfConfidenceSensitivity {
  max_reduction: number
  max_peak_pct: number
  n: number
  share_pct: number
  win_pct: number | null
  ev_pct: number | null
  is_current: boolean
}

// One row per (horizon, direction, peak-vs-own-history percentile band). Low
// percentile = a modest peak by this token's standards — which is the side that
// performs, opposite to the original assumption. See docs/hist_peak_context.md.
export interface PerfPeakBucket {
  horizon: string
  direction: string
  bucket: string
  n: number
  win_pct: number | null
  avg_ret_pct: number | null
}

// Same metric as PerfMacdSignalBucket, normalized by price instead of ATR — a
// second, more legible lens on the same signal line. Carries a known asset-class
// confound; see docs/macd_signal_pct_analysis.md.
export interface PerfMacdSignalPctBucket {
  horizon: string
  direction: string
  bucket: string
  n: number
  win_pct: number | null
  avg_ret_pct: number | null
}

// One row per (horizon, direction, ATR-normalized MACD-signal-line bucket). The
// axis is (fire_macd - fire_hist) / atr — signed, so the sign carries the regime.
export interface PerfMacdSignalBucket {
  horizon: string
  direction: string
  bucket: string
  n: number
  win_pct: number | null
  avg_ret_pct: number | null
}

// Counterfactual reduction buckets from asset_snapshots (extends below the 0.3
// fire threshold). EV/win are faithful; drawdown_proxy is a close-based floor.
export interface PerfReductionCounterfactual {
  bucket: string
  n: number
  win_pct: number
  ev_pct: number
  drawdown_proxy_pct: number
}
