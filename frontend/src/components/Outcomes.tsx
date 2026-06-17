import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import {
  usePerfByHorizon,
  usePerfBySymbol,
  usePerfLeadTime,
  usePerfMfeMae,
  usePerfReadiness,
  usePerfSummary,
} from '../api/client'
import type { Horizon } from '../api/types'
import { ASSET_CLASS_COLOR, fmtPctPts, relativeTime, stageShort } from '../lib/format'
import { Badge, Card, Metric, StateMsg } from './ui'

const AXIS = '#64748b'
const GRID = '#1e293b'
const STAGE_HEX: Record<string, string> = {
  'S1 hist': '#a78bfa',
  'S3 zero': '#38bdf8',
}
const tooltipStyle = {
  background: '#0f172a',
  border: '1px solid #1e293b',
  borderRadius: 8,
  color: '#e2e8f0',
  fontSize: 12,
}

/** Green for positive / winning, rose for negative / losing, slate at the line. */
function tone(n: number | null | undefined, mid = 0): string {
  if (n == null) return 'text-slate-500'
  if (n > mid) return 'text-emerald-400'
  if (n < mid) return 'text-rose-400'
  return 'text-slate-300'
}

function dirColor(direction: string): string {
  return direction === 'bullish' ? 'green' : 'red'
}

// ---------- readiness banner ----------

export function ReadinessBanner() {
  const { data, isLoading, isError } = usePerfReadiness()
  const r = data
  const maturing = !!r && r.finalized === 0
  const note = !r
    ? ''
    : r.total === 0
      ? 'No signals logged yet.'
      : maturing
        ? 'Accumulating data — outcomes mature ~14 days after a signal fires.'
        : 'Outcomes are direction-normalized and deduped to one signal per asset-day.'

  return (
    <Card
      title="Outcome readiness"
      right={
        r && r.pending > 0 ? (
          <span className="text-xs text-slate-500">
            oldest pending {relativeTime(r.oldest_pending)}
          </span>
        ) : null
      }
    >
      <StateMsg loading={isLoading} error={isError} empty={!r}>
        {r && (
          <div className="space-y-3">
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <Metric label="Signals" value={r.total} />
              <Metric label="Finalized" value={r.finalized} />
              <Metric label="7d scored" value={r.have_7d} />
              <Metric label="Pending" value={r.pending} />
            </div>
            <p className={`text-xs ${maturing ? 'text-amber-400' : 'text-slate-500'}`}>{note}</p>
          </div>
        )}
      </StateMsg>
    </Card>
  )
}

// ---------- headline: win-rate & return by stage × direction ----------

export function PerfSummary({ horizon }: { horizon: Horizon }) {
  const { data, isLoading, isError } = usePerfSummary(horizon)
  const rows = data ?? []

  return (
    <Card title={`Win rate & return · ${horizon}`}>
      <StateMsg loading={isLoading} error={isError} empty={rows.length === 0}>
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-800 text-left text-xs uppercase tracking-wide text-slate-500">
              <th className="py-1.5 pr-2 font-medium">Stage</th>
              <th className="py-1.5 pr-2 font-medium">Dir</th>
              <th className="py-1.5 pr-2 text-right font-medium">n</th>
              <th className="py-1.5 pr-2 text-right font-medium">Win</th>
              <th className="py-1.5 pr-2 text-right font-medium">Avg</th>
              <th className="py-1.5 pr-2 text-right font-medium">Best</th>
              <th className="py-1.5 text-right font-medium">Worst</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={`${r.stage}-${r.direction}`} className="border-b border-slate-800/50 last:border-0">
                <td className="py-1.5 pr-2 text-slate-300">{stageShort(r.stage)}</td>
                <td className="py-1.5 pr-2"><Badge color={dirColor(r.direction)}>{r.direction}</Badge></td>
                <td className="py-1.5 pr-2 text-right tabular-nums text-slate-400">{r.n}</td>
                <td className={`py-1.5 pr-2 text-right tabular-nums ${tone(r.win_pct, 50)}`}>{fmtPctPts(r.win_pct)}</td>
                <td className={`py-1.5 pr-2 text-right tabular-nums ${tone(r.avg_ret_pct)}`}>{fmtPctPts(r.avg_ret_pct, 2, true)}</td>
                <td className="py-1.5 pr-2 text-right tabular-nums text-emerald-400/70">{fmtPctPts(r.best_pct, 1, true)}</td>
                <td className="py-1.5 text-right tabular-nums text-rose-400/70">{fmtPctPts(r.worst_pct, 1, true)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </StateMsg>
    </Card>
  )
}

// ---------- return across horizons (edge grow or decay?) ----------

export function HorizonChart() {
  const { data, isLoading, isError } = usePerfByHorizon()
  const stages = data ?? []
  const stageKeys = stages.map((s) => stageShort(s.stage))
  const HS: Horizon[] = ['1d', '3d', '7d', '14d']
  const rows = HS.map((h) => {
    const row: Record<string, number | string | null> = { h }
    for (const s of stages) row[stageShort(s.stage)] = s[`ret_${h}`] as number | null
    return row
  })

  return (
    <Card title="Avg return across horizons">
      <StateMsg loading={isLoading} error={isError} empty={stages.length === 0}>
        <div style={{ height: 220 }}>
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={rows}>
              <CartesianGrid stroke={GRID} vertical={false} />
              <XAxis dataKey="h" stroke={AXIS} fontSize={12} />
              <YAxis stroke={AXIS} fontSize={12} unit="%" />
              <ReferenceLine y={0} stroke={AXIS} strokeDasharray="3 3" />
              <Tooltip contentStyle={tooltipStyle} formatter={(v: number) => `${v}%`} />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              {stageKeys.map((k) => (
                <Line key={k} type="monotone" dataKey={k} stroke={STAGE_HEX[k] ?? '#94a3b8'} strokeWidth={2} dot={{ r: 3 }} connectNulls />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>
      </StateMsg>
    </Card>
  )
}

// ---------- lead time: does Stage 1 warn earlier? ----------

export function LeadTime() {
  const { data, isLoading, isError } = usePerfLeadTime()
  const rows = data ?? []

  return (
    <Card title="Zero-cross lead time">
      <StateMsg loading={isLoading} error={isError} empty={rows.length === 0}>
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-800 text-left text-xs uppercase tracking-wide text-slate-500">
              <th className="py-1.5 pr-2 font-medium">Stage</th>
              <th className="py-1.5 pr-2 text-right font-medium">Final</th>
              <th className="py-1.5 pr-2 text-right font-medium">Crossed</th>
              <th className="py-1.5 text-right font-medium">Avg bars</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.stage} className="border-b border-slate-800/50 last:border-0">
                <td className="py-1.5 pr-2 text-slate-300">{stageShort(r.stage)}</td>
                <td className="py-1.5 pr-2 text-right tabular-nums text-slate-400">{r.finalized_n}</td>
                <td className="py-1.5 pr-2 text-right tabular-nums text-slate-300">
                  {r.crossed_n} <span className="text-slate-500">({fmtPctPts(r.cross_rate_pct)})</span>
                </td>
                <td className="py-1.5 text-right tabular-nums text-sky-400">{r.avg_bars_to_cross ?? '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </StateMsg>
    </Card>
  )
}

// ---------- tradeability: MFE / MAE ----------

export function Excursions() {
  const { data, isLoading, isError } = usePerfMfeMae()
  const rows = data ?? []

  return (
    <Card title="Favorable / adverse excursion">
      <StateMsg loading={isLoading} error={isError} empty={rows.length === 0}>
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-800 text-left text-xs uppercase tracking-wide text-slate-500">
              <th className="py-1.5 pr-2 font-medium">Stage</th>
              <th className="py-1.5 pr-2 font-medium">Dir</th>
              <th className="py-1.5 pr-2 text-right font-medium">n</th>
              <th className="py-1.5 pr-2 text-right font-medium">MFE</th>
              <th className="py-1.5 text-right font-medium">MAE</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={`${r.stage}-${r.direction}`} className="border-b border-slate-800/50 last:border-0">
                <td className="py-1.5 pr-2 text-slate-300">{stageShort(r.stage)}</td>
                <td className="py-1.5 pr-2"><Badge color={dirColor(r.direction)}>{r.direction}</Badge></td>
                <td className="py-1.5 pr-2 text-right tabular-nums text-slate-400">{r.n}</td>
                <td className="py-1.5 pr-2 text-right tabular-nums text-emerald-400">{fmtPctPts(r.avg_mfe_pct, 2, true)}</td>
                <td className="py-1.5 text-right tabular-nums text-rose-400">{fmtPctPts(r.avg_mae_pct, 2, true)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </StateMsg>
    </Card>
  )
}

// ---------- per-symbol reliability ----------

export function SymbolPerf({ horizon }: { horizon: Horizon }) {
  const { data, isLoading, isError } = usePerfBySymbol(horizon, 3)
  const rows = data ?? []

  return (
    <Card title={`Per-symbol reliability · ${horizon}`} right={<span className="text-xs text-slate-600">min 3 signals</span>}>
      <StateMsg loading={isLoading} error={isError} empty={rows.length === 0}>
        <div className="max-h-[24rem] overflow-y-auto">
          <table className="w-full text-sm">
            <thead className="sticky top-0 bg-slate-900/95">
              <tr className="border-b border-slate-800 text-left text-xs uppercase tracking-wide text-slate-500">
                <th className="py-1.5 pr-2 font-medium">Symbol</th>
                <th className="py-1.5 pr-2 font-medium">Class</th>
                <th className="py-1.5 pr-2 text-right font-medium">n</th>
                <th className="py-1.5 pr-2 text-right font-medium">Win</th>
                <th className="py-1.5 text-right font-medium">Avg</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.symbol} className="border-b border-slate-800/50 last:border-0">
                  <td className="py-1.5 pr-2 text-slate-300">{r.symbol}</td>
                  <td className="py-1.5 pr-2">
                    {r.asset_class ? (
                      <Badge color={ASSET_CLASS_COLOR[r.asset_class] ?? 'slate'}>{r.asset_class}</Badge>
                    ) : (
                      <span className="text-slate-600">—</span>
                    )}
                  </td>
                  <td className="py-1.5 pr-2 text-right tabular-nums text-slate-400">{r.n}</td>
                  <td className={`py-1.5 pr-2 text-right tabular-nums ${tone(r.win_pct, 50)}`}>{fmtPctPts(r.win_pct)}</td>
                  <td className={`py-1.5 text-right tabular-nums ${tone(r.avg_ret_pct)}`}>{fmtPctPts(r.avg_ret_pct, 2, true)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </StateMsg>
    </Card>
  )
}
