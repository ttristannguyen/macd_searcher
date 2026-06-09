import { useQuery } from '@tanstack/react-query'
import type {
  ClassCountRow,
  DayCount,
  Health,
  NotifyStatusRow,
  ProximityHeadroom,
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

export const useProximityHeadroom = () =>
  useQuery({
    queryKey: ['headroom'],
    queryFn: () => fetchJson<ProximityHeadroom>('/api/stats/proximity-headroom'),
    refetchInterval: STATS_REFRESH,
  })
