import { useRuns } from '../api/client'
import { fmtNum, relativeTime } from '../lib/format'
import { Badge, Card, StateMsg } from './ui'

const STATUS_COLOR: Record<string, string> = {
  sent: 'green',
  dry_run: 'blue',
  quiet_hours: 'slate',
  empty_suppressed: 'slate',
  no_creds: 'amber',
  failed: 'red',
}

export function RunsTable() {
  const { data, isLoading, isError } = useRuns(10)

  return (
    <Card title="Recent runs">
      <StateMsg loading={isLoading} error={isError} empty={!data || data.length === 0}>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-800 text-left text-xs uppercase tracking-wide text-slate-500">
                <th className="py-2 pr-3 font-medium">When</th>
                <th className="py-2 pr-3 font-medium">Status</th>
                <th className="py-2 pr-3 font-medium">Kept</th>
                <th className="py-2 pr-3 font-medium">Signals</th>
                <th className="py-2 pr-3 font-medium">Secs</th>
              </tr>
            </thead>
            <tbody>
              {(data ?? []).map((r, i) => (
                <tr key={i} className="border-b border-slate-800/50 hover:bg-slate-800/30">
                  <td className="whitespace-nowrap py-2 pr-3 text-slate-400">{relativeTime(r.started_at)}</td>
                  <td className="py-2 pr-3">
                    {r.notify_status && (
                      <Badge color={STATUS_COLOR[r.notify_status] ?? 'slate'}>{r.notify_status}</Badge>
                    )}
                  </td>
                  <td className="py-2 pr-3 tabular-nums text-slate-300">{r.universe_kept ?? '—'}</td>
                  <td className="py-2 pr-3 tabular-nums text-slate-300">{r.signals_count ?? '—'}</td>
                  <td className="py-2 pr-3 tabular-nums text-slate-500">{fmtNum(r.duration_s, 1)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </StateMsg>
    </Card>
  )
}
