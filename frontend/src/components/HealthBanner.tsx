import { useHealth } from '../api/client'
import type { HealthStatus } from '../api/types'
import { relativeTime } from '../lib/format'
import { Card, Metric } from './ui'

const STATUS: Record<HealthStatus, { label: string; dot: string; pill: string }> = {
  ok: { label: 'OK', dot: 'bg-emerald-400', pill: 'bg-emerald-500/15 text-emerald-400 ring-1 ring-emerald-500/30' },
  stale: { label: 'STALE', dot: 'bg-amber-400', pill: 'bg-amber-500/15 text-amber-400 ring-1 ring-amber-500/30' },
  down: { label: 'DOWN', dot: 'bg-rose-400', pill: 'bg-rose-500/15 text-rose-400 ring-1 ring-rose-500/30' },
}

export function HealthBanner() {
  const { data, isLoading, isError } = useHealth()

  if (isLoading) {
    return <Card>Loading health…</Card>
  }
  if (isError || !data) {
    return (
      <Card>
        <span className="text-rose-400">API unreachable</span>
        <span className="ml-2 text-sm text-slate-500">
          is the backend running? (`uv run macd-searcher-web`)
        </span>
      </Card>
    )
  }

  const s = STATUS[data.status]
  const lr = data.latest_run

  return (
    <Card>
      <div className="flex flex-wrap items-center gap-x-8 gap-y-4">
        <div className="flex items-center gap-3">
          <span className={`inline-flex items-center gap-2 rounded-full px-3 py-1 text-sm font-semibold ${s.pill}`}>
            <span className={`h-2 w-2 rounded-full ${s.dot}`} />
            {s.label}
          </span>
          <span className="text-xs text-slate-500">scanner</span>
        </div>
        <Metric label="Last run" value={lr ? relativeTime(lr.started_at) : '—'} />
        <Metric label="Dispatch" value={lr?.notify_status ?? '—'} />
        <Metric label="Universe kept" value={lr?.universe_kept ?? '—'} />
        <Metric label="Signals last run" value={lr?.signals_count ?? '—'} />
        <Metric label="Total signals" value={data.counts.signals.toLocaleString()} />
        <Metric label="Snapshots" value={data.counts.asset_snapshots.toLocaleString()} />
      </div>
    </Card>
  )
}
