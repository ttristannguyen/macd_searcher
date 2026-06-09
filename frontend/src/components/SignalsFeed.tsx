import { useState } from 'react'
import { useRecentSignals } from '../api/client'
import type { SignalRow } from '../api/types'
import { ASSET_CLASS_COLOR, fmtNum, fmtPct, fmtPrice, relativeTime, stageShort } from '../lib/format'
import { Badge, Card, Segmented, StateMsg } from './ui'

type StageFilter = 'all' | 'zero_line_proximity' | 'histogram_flattening'
type DirFilter = 'all' | 'bullish' | 'bearish'

function keyMetric(s: SignalRow): string {
  if (s.stage === 'zero_line_proximity' && s.fire_macd_pct_of_price != null) {
    return `${fmtPct(s.fire_macd_pct_of_price)} to zero`
  }
  if (s.stage === 'histogram_flattening' && s.fire_reduction_from_peak != null) {
    return `↓${fmtPct(s.fire_reduction_from_peak, 0)} from peak`
  }
  return '—'
}

export function SignalsFeed() {
  const { data, isLoading, isError } = useRecentSignals(100)
  const [stage, setStage] = useState<StageFilter>('all')
  const [dir, setDir] = useState<DirFilter>('all')

  const all = data ?? []
  const rows = all.filter(
    (s) => (stage === 'all' || s.stage === stage) && (dir === 'all' || s.direction === dir),
  )

  const filters = (
    <div className="flex flex-wrap items-center gap-2">
      <Segmented<StageFilter>
        value={stage}
        onChange={setStage}
        options={[
          { value: 'all', label: 'All' },
          { value: 'zero_line_proximity', label: 'S3' },
          { value: 'histogram_flattening', label: 'S1' },
        ]}
      />
      <Segmented<DirFilter>
        value={dir}
        onChange={setDir}
        options={[
          { value: 'all', label: 'All' },
          { value: 'bullish', label: 'Bull' },
          { value: 'bearish', label: 'Bear' },
        ]}
      />
      <span className="text-xs tabular-nums text-slate-600">
        {rows.length} of {all.length}
      </span>
    </div>
  )

  return (
    <Card title="Latest Signals" right={filters}>
      <StateMsg loading={isLoading} error={isError} empty={all.length === 0}>
        {rows.length === 0 ? (
          <div className="py-8 text-center text-sm text-slate-500">No signals match these filters.</div>
        ) : (
          <div className="max-h-[26rem] overflow-y-auto">
            <table className="w-full text-sm">
              <thead className="sticky top-0 bg-slate-900/95 backdrop-blur">
                <tr className="border-b border-slate-800 text-left text-xs uppercase tracking-wide text-slate-500">
                  <th className="py-2 pr-3 font-medium">When</th>
                  <th className="py-2 pr-3 font-medium">Symbol</th>
                  <th className="py-2 pr-3 font-medium">Class</th>
                  <th className="py-2 pr-3 font-medium">Stage</th>
                  <th className="py-2 pr-3 font-medium">Direction</th>
                  <th className="py-2 pr-3 font-medium">MACD</th>
                  <th className="py-2 pr-3 font-medium">Signal Detail</th>
                  <th className="py-2 pr-3 font-medium">Price</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((s, i) => (
                  <tr key={i} className="border-b border-slate-800/50 hover:bg-slate-800/30">
                    <td className="whitespace-nowrap py-1.5 pr-3 text-slate-400">{relativeTime(s.fired_at)}</td>
                    <td className="py-1.5 pr-3 font-medium text-slate-100">{s.symbol}</td>
                    <td className="py-1.5 pr-3">
                      {s.asset_class && <Badge color={ASSET_CLASS_COLOR[s.asset_class] ?? 'slate'}>{s.asset_class}</Badge>}
                    </td>
                    <td className="py-1.5 pr-3 text-slate-400">{stageShort(s.stage)}</td>
                    <td className="py-1.5 pr-3">
                      <Badge color={s.direction === 'bullish' ? 'green' : 'red'}>{s.direction}</Badge>
                    </td>
                    <td className="py-1.5 pr-3 tabular-nums text-slate-300">{fmtNum(s.fire_macd)}</td>
                    <td className="whitespace-nowrap py-1.5 pr-3 text-slate-400">{keyMetric(s)}</td>
                    <td className="py-1.5 pr-3 tabular-nums text-slate-300">{fmtPrice(s.fire_close)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </StateMsg>
    </Card>
  )
}
