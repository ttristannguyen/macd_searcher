import { useState } from 'react'
import { useRecentSignals } from '../api/client'
import type { SignalRow } from '../api/types'
import { ASSET_CLASS_COLOR, fmtNum, fmtPct, fmtPrice, relativeTime, stageShort } from '../lib/format'
import { Badge, Card, Segmented, StateMsg } from './ui'

type DirFilter = 'all' | 'bullish' | 'bearish'

function keyMetric(s: SignalRow): string {
  if (s.fire_reduction_from_peak != null) {
    return `↓${fmtPct(s.fire_reduction_from_peak, 0)} from peak`
  }
  return '—'
}

// Peak size vs this token's OWN prior same-sign tops. Measurement found the low
// end is the good end for bearish fires — fading a monster move fails, fading a
// tired one works — so a modest peak is highlighted, not dimmed. Bearish only;
// bullish shows the number without a verdict. See docs/hist_peak_context.md.
const PEAK_TRUST_FLOOR = 3

function PeakCell({ signal: s }: { signal: SignalRow }) {
  const { fire_hist_peak_ratio: ratio, fire_hist_peak_pct: pct, fire_hist_top_n: n } = s
  if (ratio == null || pct == null || !n) {
    return <td className="py-1.5 pr-3 text-slate-600">—</td>
  }

  const thin = n < PEAK_TRUST_FLOOR
  // Only bearish has held up across both regime halves, so only bearish is coloured.
  const favourable = s.direction === 'bearish' && pct < 40
  const colour = thin ? 'text-slate-500' : favourable ? 'text-emerald-400' : 'text-slate-300'
  const verdict = thin
    ? 'baseline too thin to read'
    : s.direction === 'bearish'
      ? favourable
        ? 'modest peak for this token — the side that has performed'
        : 'large peak for this token — historically the weaker side'
      : 'bullish: no reliable read yet'

  return (
    <td
      className={`py-1.5 pr-3 tabular-nums ${colour}`}
      title={`${ratio.toFixed(1)}× typical · ${Math.round(pct)}th pct of this token's own ${
        s.direction === 'bearish' ? 'bear' : 'bull'
      } tops · n=${n} · ${verdict}`}
    >
      {ratio.toFixed(1)}×
      <span className="ml-1 text-[10px] text-slate-500">p{Math.round(pct)}</span>
    </td>
  )
}

export function SignalsFeed() {
  const { data, isLoading, isError } = useRecentSignals(100)
  const [dir, setDir] = useState<DirFilter>('all')

  const all = data ?? []
  const rows = all.filter((s) => dir === 'all' || s.direction === dir)

  const filters = (
    <div className="flex flex-wrap items-center gap-2">
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
                  <th className="py-2 pr-3 font-medium">RSI</th>
                  <th className="py-2 pr-3 font-medium">Peak</th>
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
                    <td className="py-1.5 pr-3 tabular-nums text-slate-300">{s.fire_rsi_14 != null ? Math.round(s.fire_rsi_14) : '—'}</td>
                    <PeakCell signal={s} />
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
