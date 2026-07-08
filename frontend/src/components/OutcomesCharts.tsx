import {
  Area,
  CartesianGrid,
  ComposedChart,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { usePerfHorizonCurve, usePerfThresholds } from '../api/client'
import type { PerfBucket } from '../api/types'
import { fmtPctPts } from '../lib/format'
import { Card, StateMsg } from './ui'

// Recessive axes/grid + a dark tooltip — matches HorizonChart on the tables view.
const AXIS = '#64748b'
const GRID = '#1e293b'
const ACCENT = '#38bdf8' // sky-400 — single-series hue
const tooltipStyle = {
  background: '#0f172a',
  border: '1px solid #1e293b',
  borderRadius: 8,
  color: '#e2e8f0',
  fontSize: 12,
}

const HORIZONS = ['1d', '3d', '7d', '14d'] as const
// Reduction buckets as returned by /api/perf/thresholds (sort-prefixed).
const RED_BUCKETS = ['a 0.3-0.4', 'b 0.4-0.6', 'c 0.6-0.8', 'd 0.8-1.0'] as const

// ---------- win-rate across horizons ----------

export function WinRateCurve() {
  const { data, isLoading, isError } = usePerfHorizonCurve()
  const by = new Map((data ?? []).map((r) => [r.horizon, r]))
  const rows = HORIZONS.map((h) => ({ h, win_pct: by.get(h)?.win_pct ?? null, n: by.get(h)?.n ?? 0 }))

  return (
    <Card title="Win rate across horizons">
      <StateMsg loading={isLoading} error={isError} empty={(data ?? []).length === 0}>
        <div style={{ height: 220 }}>
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={rows}>
              <CartesianGrid stroke={GRID} vertical={false} />
              <XAxis dataKey="h" stroke={AXIS} fontSize={12} />
              <YAxis stroke={AXIS} fontSize={12} unit="%" domain={[0, 100]} />
              <ReferenceLine y={50} stroke={AXIS} strokeDasharray="3 3" label={{ value: 'coin-flip', fill: AXIS, fontSize: 10, position: 'right' }} />
              <Tooltip contentStyle={tooltipStyle} formatter={(v: number) => `${v}%`} />
              <Line type="monotone" dataKey="win_pct" stroke={ACCENT} strokeWidth={2} dot={{ r: 3 }} connectNulls />
            </LineChart>
          </ResponsiveContainer>
        </div>
        <p className="mt-2 text-xs text-slate-600">
          Share of signals where the predicted move happened, by holding window. Above the dashed 50% line beats a coin flip.
        </p>
      </StateMsg>
    </Card>
  )
}

// ---------- return across horizons (avg + spread band) ----------

export function ReturnCurve() {
  const { data, isLoading, isError } = usePerfHorizonCurve()
  const by = new Map((data ?? []).map((r) => [r.horizon, r]))
  const rows = HORIZONS.map((h) => {
    const p = by.get(h)
    return {
      h,
      avg: p?.avg_ret_pct ?? null,
      // Recharts renders a band when the value is a [low, high] tuple.
      range: p ? [p.worst_pct, p.best_pct] : null,
      iqr: p ? [p.p25_pct, p.p75_pct] : null,
    }
  })

  const fmt = (v: number | number[]) =>
    Array.isArray(v) ? `${fmtPctPts(v[0], 1, true)} … ${fmtPctPts(v[1], 1, true)}` : fmtPctPts(v, 2, true)

  return (
    <Card title="Return across horizons">
      <StateMsg loading={isLoading} error={isError} empty={(data ?? []).length === 0}>
        <div style={{ height: 220 }}>
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={rows}>
              <CartesianGrid stroke={GRID} vertical={false} />
              <XAxis dataKey="h" stroke={AXIS} fontSize={12} />
              <YAxis stroke={AXIS} fontSize={12} unit="%" />
              <ReferenceLine y={0} stroke={AXIS} strokeDasharray="3 3" />
              <Tooltip contentStyle={tooltipStyle} formatter={fmt} />
              <Area name="best–worst" dataKey="range" stroke="none" fill={ACCENT} fillOpacity={0.08} connectNulls />
              <Area name="p25–p75" dataKey="iqr" stroke="none" fill={ACCENT} fillOpacity={0.18} connectNulls />
              <Line name="avg" type="monotone" dataKey="avg" stroke={ACCENT} strokeWidth={2} dot={{ r: 3 }} connectNulls />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
        <p className="mt-2 text-xs text-slate-600">
          Line = average return · inner band = p25–p75 (typical spread) · outer band = worst–best. Above the dashed 0% line is net positive.
        </p>
      </StateMsg>
    </Card>
  )
}

// ---------- reduction-bucket heatmaps (win-rate & EV across horizons) ----------

const NEUTRAL: [number, number, number] = [51, 65, 85] // slate-700 — diverging midpoint
const ROSE: [number, number, number] = [190, 18, 60] // rose-700 — loss pole
const EMERALD: [number, number, number] = [4, 120, 87] // emerald-700 — win pole

function mix(a: [number, number, number], b: [number, number, number], t: number): string {
  const c = (i: number) => Math.round(a[i] + (b[i] - a[i]) * t)
  return `rgb(${c(0)}, ${c(1)}, ${c(2)})`
}

/** Diverging colour: neutral slate at `mid`, → emerald above, → rose below. */
function heatColor(value: number | null, mid: number, span: number): string {
  if (value == null) return 'transparent'
  const t = Math.max(-1, Math.min(1, (value - mid) / span))
  return t >= 0 ? mix(NEUTRAL, EMERALD, t) : mix(NEUTRAL, ROSE, -t)
}

function ReductionHeatmap({ metric }: { metric: 'win' | 'ev' }) {
  // Fixed set of horizons → hooks-rules-safe; React Query dedupes the shared keys.
  const q1 = usePerfThresholds('1d')
  const q3 = usePerfThresholds('3d')
  const q7 = usePerfThresholds('7d')
  const q14 = usePerfThresholds('14d')
  const queries = [q1, q3, q7, q14]
  const byHorizon: Record<string, PerfBucket[] | undefined> = {
    '1d': q1.data, '3d': q3.data, '7d': q7.data, '14d': q14.data,
  }

  const loading = queries.some((q) => q.isLoading)
  const error = queries.some((q) => q.isError)
  const empty = queries.every((q) => (q.data ?? []).length === 0)

  const mid = metric === 'win' ? 50 : 0
  const span = metric === 'win' ? 25 : 10
  const title = metric === 'win' ? 'Win rate by reduction × horizon' : 'EV by reduction × horizon'

  const cell = (bucket: string, horizon: string) => {
    const row = (byHorizon[horizon] ?? []).find((r) => r.bucket === bucket)
    const value = row ? (metric === 'win' ? row.win_pct : row.avg_ret_pct) : null
    return { value, n: row?.n ?? 0 }
  }

  return (
    <Card title={title}>
      <StateMsg loading={loading} error={error} empty={empty}>
        <div className="overflow-x-auto">
          <table className="w-full border-separate text-sm" style={{ borderSpacing: 2 }}>
            <thead>
              <tr className="text-xs uppercase tracking-wide text-slate-500">
                <th className="py-1 pr-2 text-left font-medium">Reduction</th>
                {HORIZONS.map((h) => (
                  <th key={h} className="px-2 py-1 text-center font-medium">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {RED_BUCKETS.map((bucket) => (
                <tr key={bucket}>
                  <td className="py-1 pr-2 text-slate-300">{bucket.slice(2)}</td>
                  {HORIZONS.map((h) => {
                    const { value, n } = cell(bucket, h)
                    return (
                      <td
                        key={h}
                        className="rounded px-2 py-1.5 text-center tabular-nums"
                        style={{ background: heatColor(value, mid, span), color: value == null ? '#475569' : '#f1f5f9' }}
                        title={value == null ? 'no data' : `${bucket.slice(2)} · ${h} · n=${n}`}
                      >
                        {value == null ? '—' : (
                          <>
                            <div>{fmtPctPts(value, metric === 'win' ? 1 : 2, metric === 'ev')}</div>
                            <div className="text-[10px] text-slate-300/70">n{n}</div>
                          </>
                        )}
                      </td>
                    )
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="mt-2 text-xs text-slate-600">
          {metric === 'win' ? 'Green ≥ 50% wins, red < 50%.' : 'Green = positive EV, red = negative.'} Cell = value / n · neutral slate at the midpoint.
        </p>
      </StateMsg>
    </Card>
  )
}

// ---------- composition ----------

export function OutcomesCharts() {
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <WinRateCurve />
        <ReturnCurve />
      </div>
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <ReductionHeatmap metric="win" />
        <ReductionHeatmap metric="ev" />
      </div>
    </div>
  )
}
