import { useTopSymbols } from '../api/client'
import { Card, StateMsg } from './ui'

export function TopSymbols() {
  const { data, isLoading, isError } = useTopSymbols(15)
  const max = Math.max(1, ...(data ?? []).map((r) => r.fires))

  return (
    <Card title="Most active symbols">
      <StateMsg loading={isLoading} error={isError} empty={!data || data.length === 0}>
        <ul className="space-y-1.5">
          {(data ?? []).map((r) => (
            <li key={r.symbol} className="flex items-center gap-2 text-sm">
              <span className="w-24 shrink-0 truncate text-slate-300">{r.symbol}</span>
              <div className="h-2 flex-1 overflow-hidden rounded bg-slate-800">
                <div className="h-full rounded bg-sky-500/70" style={{ width: `${(r.fires / max) * 100}%` }} />
              </div>
              <span className="w-6 shrink-0 text-right tabular-nums text-slate-400">{r.fires}</span>
            </li>
          ))}
        </ul>
      </StateMsg>
    </Card>
  )
}
