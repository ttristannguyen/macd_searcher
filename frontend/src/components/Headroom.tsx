import { useProximityHeadroom } from '../api/client'
import { Card, StateMsg } from './ui'

function Kpi({ label, value }: { label: string; value: number | null }) {
  return (
    <div className="rounded-lg border border-slate-800 bg-slate-950/40 p-4 text-center">
      <div className="text-2xl font-semibold text-sky-400">{value ?? '—'}</div>
      <div className="mt-1 text-xs text-slate-500">{label}</div>
    </div>
  )
}

export function Headroom() {
  const { data, isLoading, isError } = useProximityHeadroom()
  return (
    <Card
      title="Alert headroom — avg assets/run near the zero line"
      right={<span className="text-xs text-slate-600">(upper bound; ignores shrink filter)</span>}
    >
      <StateMsg loading={isLoading} error={isError} empty={!data}>
        {data && (
          <div className="grid grid-cols-3 gap-3">
            <Kpi label="within 0.2%" value={data.avg_assets_under_0_2pct} />
            <Kpi label="within 0.5%" value={data.avg_assets_under_0_5pct} />
            <Kpi label="within 1.0%" value={data.avg_assets_under_1pct} />
          </div>
        )}
      </StateMsg>
    </Card>
  )
}
