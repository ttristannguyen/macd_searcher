import type { StrategySignalRow } from '../api/types'
import { ASSET_CLASS_COLOR, fmtPct, fmtPrice, relativeTime } from '../lib/format'
import { Badge, Card, StateMsg } from './ui'

// The side you'd TAKE, which is not always the fire's direction: the bearish
// pullback is a bearish fire held long (docs/profit_strategies.md).
export type Side = 'long' | 'short'

/** One strategy leg's recent fires, one row per symbol (its latest fire). */
export function StrategyTable({
  title,
  side,
  blurb,
  rows,
  loading,
  error,
}: {
  title: string
  side: Side
  blurb: string
  rows: StrategySignalRow[]
  loading: boolean
  error: boolean
}) {
  const right = (
    <div className="flex items-center gap-2">
      <Badge color={side === 'long' ? 'green' : 'red'}>{side}</Badge>
      <span className="text-xs tabular-nums text-slate-600">{rows.length} symbols</span>
    </div>
  )

  return (
    <Card title={title} right={right}>
      <p className="-mt-1 mb-3 text-xs text-slate-500">{blurb}</p>
      <StateMsg loading={loading} error={error}>
        {rows.length === 0 ? (
          <div className="py-6 text-center text-sm text-slate-500">No fires in this window.</div>
        ) : (
          <div className="max-h-[22rem] overflow-y-auto">
            <table className="w-full text-sm">
              <thead className="sticky top-0 bg-slate-900/95 backdrop-blur">
                <tr className="border-b border-slate-800 text-left text-xs uppercase tracking-wide text-slate-500">
                  <th className="py-2 pr-3 font-medium">Last fire</th>
                  <th className="py-2 pr-3 font-medium">Symbol</th>
                  <th className="py-2 pr-3 font-medium">Class</th>
                  <th className="py-2 pr-3 font-medium">Peak</th>
                  <th className="py-2 pr-3 font-medium">Reduction</th>
                  <th className="py-2 pr-3 font-medium">RSI</th>
                  <th className="py-2 pr-3 font-medium">Fires</th>
                  <th className="py-2 pr-3 font-medium">First seen</th>
                  <th className="py-2 pr-3 font-medium">Price</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((s) => (
                  <tr key={s.symbol} className="border-b border-slate-800/50 hover:bg-slate-800/30">
                    <td className="whitespace-nowrap py-1.5 pr-3 text-slate-400">{relativeTime(s.fired_at)}</td>
                    <td className="py-1.5 pr-3 font-medium text-slate-100">{s.symbol}</td>
                    <td className="py-1.5 pr-3">
                      {s.asset_class && <Badge color={ASSET_CLASS_COLOR[s.asset_class] ?? 'slate'}>{s.asset_class}</Badge>}
                    </td>
                    <PeakCell signal={s} />
                    <td className="py-1.5 pr-3 tabular-nums text-slate-300">↓{fmtPct(s.fire_reduction_from_peak, 0)}</td>
                    <td className="py-1.5 pr-3 tabular-nums text-slate-300">{s.fire_rsi_14 != null ? Math.round(s.fire_rsi_14) : '—'}</td>
                    <td className="py-1.5 pr-3 tabular-nums text-slate-300">{s.fires}</td>
                    <td className="whitespace-nowrap py-1.5 pr-3 text-slate-400">{relativeTime(s.first_fired_at)}</td>
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

// peak_pct is the axis every one of these rules cuts on, so it leads; the ratio to
// the token's typical top is context. Every row here has a pct (the rule needs it).
function PeakCell({ signal: s }: { signal: StrategySignalRow }) {
  const { fire_hist_peak_ratio: ratio, fire_hist_peak_pct: pct, fire_hist_top_n: n } = s
  return (
    <td
      className="py-1.5 pr-3 tabular-nums text-slate-300"
      title={`${pct != null ? Math.round(pct) : '—'}th pct of this token's own ${
        s.direction === 'bearish' ? 'bear' : 'bull'
      } tops · ${ratio != null ? ratio.toFixed(1) : '—'}× typical · n=${n ?? 0}`}
    >
      p{pct != null ? Math.round(pct) : '—'}
      {ratio != null && <span className="ml-1 text-[10px] text-slate-500">{ratio.toFixed(1)}×</span>}
    </td>
  )
}
