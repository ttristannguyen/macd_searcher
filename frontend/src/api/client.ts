import { createContext, useContext } from 'react'
import { useQuery } from '@tanstack/react-query'
import type {
  ClassCountRow,
  DayCount,
  Health,
  Horizon,
  NotifyStatusRow,
  PerfBucket,
  PerfClassStage,
  PerfDistribution,
  PerfHorizon,
  PerfHorizonPoint,
  PerfLeadTime,
  PerfMetric,
  PerfReadiness,
  PerfReductionCounterfactual,
  PerfConfidencePoint,
  PerfConfidenceSensitivity,
  PerfConfidenceSummary,
  PerfMacdSignalBucket,
  PerfMacdSignalPctBucket,
  PerfPeakBucket,
  PerfRsiBucket,
  PerfStageDirection,
  PerfSymbolScore,
  RunRow,
  SignalRow,
  StageDirectionRow,
  SymbolCountRow,
} from './types'

async function fetchJson<T>(path: string): Promise<T> {
  const res = await fetch(path)
  if (!res.ok) {
    throw new Error(`${res.status} ${res.statusText}`)
  }
  return (await res.json()) as T
}

const HEALTH_REFRESH = 30_000
const STATS_REFRESH = 60_000

export const useHealth = () =>
  useQuery({
    queryKey: ['health'],
    queryFn: () => fetchJson<Health>('/api/health'),
    refetchInterval: HEALTH_REFRESH,
  })

export const useRuns = (limit = 10) =>
  useQuery({
    queryKey: ['runs', limit],
    queryFn: () => fetchJson<RunRow[]>(`/api/runs?limit=${limit}`),
    refetchInterval: STATS_REFRESH,
  })

export const useRunsPerDay = (days = 14) =>
  useQuery({
    queryKey: ['runs-per-day', days],
    queryFn: () => fetchJson<DayCount[]>(`/api/stats/runs-per-day?days=${days}`),
    refetchInterval: STATS_REFRESH,
  })

export const useNotifyStatus = () =>
  useQuery({
    queryKey: ['notify-status'],
    queryFn: () => fetchJson<NotifyStatusRow[]>('/api/stats/notify-status'),
    refetchInterval: STATS_REFRESH,
  })

export const useRecentSignals = (limit = 50) =>
  useQuery({
    queryKey: ['recent-signals', limit],
    queryFn: () => fetchJson<SignalRow[]>(`/api/signals/recent?limit=${limit}`),
    refetchInterval: STATS_REFRESH,
  })

export const useByStageDirection = () =>
  useQuery({
    queryKey: ['by-stage-direction'],
    queryFn: () => fetchJson<StageDirectionRow[]>('/api/stats/by-stage-direction'),
    refetchInterval: STATS_REFRESH,
  })

export const useByClass = () =>
  useQuery({
    queryKey: ['by-class'],
    queryFn: () => fetchJson<ClassCountRow[]>('/api/stats/by-class'),
    refetchInterval: STATS_REFRESH,
  })

export const useTopSymbols = (limit = 15) =>
  useQuery({
    queryKey: ['top-symbols', limit],
    queryFn: () => fetchJson<SymbolCountRow[]>(`/api/stats/top-symbols?limit=${limit}`),
    refetchInterval: STATS_REFRESH,
  })

export const useSignalsPerDay = (days = 14) =>
  useQuery({
    queryKey: ['signals-per-day', days],
    queryFn: () => fetchJson<DayCount[]>(`/api/stats/signals-per-day?days=${days}`),
    refetchInterval: STATS_REFRESH,
  })

// ---------- performance / outcomes ----------
//
// Outcomes mature ~14 days after a signal fires, so these refresh slowly.
const PERF_REFRESH = 5 * 60_000

// The Outcomes tab wraps its subtree in ClassesContext with the selected
// asset-class filter (comma-separated; '' = all). The perf hooks read it, so
// every panel refilters together and re-queries on change — no prop-drilling.

export const ClassesContext = createContext<string>('')
const useSelectedClasses = () => useContext(ClassesContext)
const withClasses = (path: string, classes: string) =>
  classes ? `${path}${path.includes('?') ? '&' : '?'}classes=${classes}` : path

export const usePerfReadiness = () => {
  const classes = useSelectedClasses()
  return useQuery({
    queryKey: ['perf-readiness', classes],
    queryFn: () => fetchJson<PerfReadiness>(withClasses('/api/perf/readiness', classes)),
    refetchInterval: PERF_REFRESH,
  })
}

export const usePerfSummary = (horizon: Horizon = '7d') => {
  const classes = useSelectedClasses()
  return useQuery({
    queryKey: ['perf-summary', horizon, classes],
    queryFn: () => fetchJson<PerfStageDirection[]>(withClasses(`/api/perf/summary?horizon=${horizon}`, classes)),
    refetchInterval: PERF_REFRESH,
  })
}

export const usePerfByHorizon = () => {
  const classes = useSelectedClasses()
  return useQuery({
    queryKey: ['perf-by-horizon', classes],
    queryFn: () => fetchJson<PerfHorizon[]>(withClasses('/api/perf/by-horizon', classes)),
    refetchInterval: PERF_REFRESH,
  })
}

export const usePerfHorizonCurve = () => {
  const classes = useSelectedClasses()
  return useQuery({
    queryKey: ['perf-horizon-curve', classes],
    queryFn: () => fetchJson<PerfHorizonPoint[]>(withClasses('/api/perf/horizon-curve', classes)),
    refetchInterval: PERF_REFRESH,
  })
}

export const usePerfLeadTime = () => {
  const classes = useSelectedClasses()
  return useQuery({
    queryKey: ['perf-lead-time', classes],
    queryFn: () => fetchJson<PerfLeadTime[]>(withClasses('/api/perf/lead-time', classes)),
    refetchInterval: PERF_REFRESH,
  })
}

export const usePerfDistribution = (metric: PerfMetric, minN = 1) => {
  const classes = useSelectedClasses()
  return useQuery({
    queryKey: ['perf-distribution', metric, minN, classes],
    queryFn: () =>
      fetchJson<PerfDistribution[]>(withClasses(`/api/perf/distribution?metric=${metric}&min_n=${minN}`, classes)),
    refetchInterval: PERF_REFRESH,
  })
}

// Scorecard lives on its own tab (out of the class-filter scope) — no context.
export const usePerfScorecard = (horizon: Horizon = '7d', minN = 3) =>
  useQuery({
    queryKey: ['perf-scorecard', horizon, minN],
    queryFn: () => fetchJson<PerfSymbolScore[]>(`/api/perf/scorecard?horizon=${horizon}&min_n=${minN}`),
    refetchInterval: PERF_REFRESH,
  })

export const usePerfByClass = (horizon: Horizon = '7d', minN = 1) => {
  const classes = useSelectedClasses()
  return useQuery({
    queryKey: ['perf-by-class', horizon, minN, classes],
    queryFn: () => fetchJson<PerfClassStage[]>(withClasses(`/api/perf/by-class?horizon=${horizon}&min_n=${minN}`, classes)),
    refetchInterval: PERF_REFRESH,
  })
}

export const usePerfThresholds = (horizon: Horizon = '7d') => {
  const classes = useSelectedClasses()
  return useQuery({
    queryKey: ['perf-thresholds', horizon, classes],
    queryFn: () => fetchJson<PerfBucket[]>(withClasses(`/api/perf/thresholds?horizon=${horizon}`, classes)),
    refetchInterval: PERF_REFRESH,
  })
}

export const usePerfReductionCounterfactual = (horizon: Horizon = '7d') => {
  const classes = useSelectedClasses()
  return useQuery({
    queryKey: ['perf-reduction-counterfactual', horizon, classes],
    queryFn: () =>
      fetchJson<PerfReductionCounterfactual[]>(
        withClasses(`/api/perf/reduction-counterfactual?horizon=${horizon}`, classes),
      ),
    refetchInterval: PERF_REFRESH,
  })
}

export const usePerfRsiBuckets = () => {
  const classes = useSelectedClasses()
  return useQuery({
    queryKey: ['perf-rsi-buckets', classes],
    queryFn: () => fetchJson<PerfRsiBucket[]>(withClasses('/api/perf/rsi-buckets', classes)),
    refetchInterval: PERF_REFRESH,
  })
}

export const usePerfConfidenceSummary = (horizon: Horizon = '7d') => {
  const classes = useSelectedClasses()
  return useQuery({
    queryKey: ['perf-confidence-summary', horizon, classes],
    queryFn: () =>
      fetchJson<PerfConfidenceSummary[]>(
        withClasses(`/api/perf/confidence-summary?horizon=${horizon}`, classes),
      ),
    refetchInterval: PERF_REFRESH,
  })
}

export const usePerfConfidenceTimeline = (horizon: Horizon = '7d') => {
  const classes = useSelectedClasses()
  return useQuery({
    queryKey: ['perf-confidence-timeline', horizon, classes],
    queryFn: () =>
      fetchJson<PerfConfidencePoint[]>(
        withClasses(`/api/perf/confidence-timeline?horizon=${horizon}`, classes),
      ),
    refetchInterval: PERF_REFRESH,
  })
}

export const usePerfConfidenceSensitivity = (horizon: Horizon = '7d') => {
  const classes = useSelectedClasses()
  return useQuery({
    queryKey: ['perf-confidence-sensitivity', horizon, classes],
    queryFn: () =>
      fetchJson<PerfConfidenceSensitivity[]>(
        withClasses(`/api/perf/confidence-sensitivity?horizon=${horizon}`, classes),
      ),
    refetchInterval: PERF_REFRESH,
  })
}

export const usePerfMacdSignalPctBuckets = () => {
  const classes = useSelectedClasses()
  return useQuery({
    queryKey: ['perf-macd-signal-pct-buckets', classes],
    queryFn: () =>
      fetchJson<PerfMacdSignalPctBucket[]>(
        withClasses('/api/perf/macd-signal-pct-buckets', classes),
      ),
    refetchInterval: PERF_REFRESH,
  })
}

export const usePerfPeakContextBuckets = () => {
  const classes = useSelectedClasses()
  return useQuery({
    queryKey: ['perf-peak-context-buckets', classes],
    queryFn: () =>
      fetchJson<PerfPeakBucket[]>(withClasses('/api/perf/peak-context-buckets', classes)),
    refetchInterval: PERF_REFRESH,
  })
}

export const usePerfMacdSignalBuckets = () => {
  const classes = useSelectedClasses()
  return useQuery({
    queryKey: ['perf-macd-signal-buckets', classes],
    queryFn: () =>
      fetchJson<PerfMacdSignalBucket[]>(withClasses('/api/perf/macd-signal-buckets', classes)),
    refetchInterval: PERF_REFRESH,
  })
}
