import { useState } from 'react'
import {
  Area,
  CartesianGrid,
  ComposedChart,
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
  usePerfHorizonCurve,
  usePerfMacdSignalBuckets,
  usePerfMacdSignalPctBuckets,
  usePerfPeakContextBuckets,
  usePerfRsiBuckets,
  usePerfThresholds,
} from '../api/client'
import type {
  PerfBucket,
  PerfMacdSignalBucket,
  PerfMacdSignalPctBucket,
  PerfPeakBucket,
  PerfRsiBucket,
} from '../api/types'
import { fmtPctPts } from '../lib/format'
import { Card, Segmented, StateMsg } from './ui'

// Recessive axes/grid + a dark tooltip — matches HorizonChart on the tables view.
const AXIS = '#64748b'
const GRID = '#1e293b'
const ACCENT = '#38bdf8' // sky-400 — win-rate line
const RETURN_HUE = '#a78bfa' // violet-400 — return line + spread bands
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
              <Area name="worst–best" dataKey="range" stroke={RETURN_HUE} strokeOpacity={0.25} strokeWidth={1} fill={RETURN_HUE} fillOpacity={0.10} connectNulls />
              <Area name="p25–p75" dataKey="iqr" stroke={RETURN_HUE} strokeOpacity={0.55} strokeWidth={1} fill={RETURN_HUE} fillOpacity={0.24} connectNulls />
              <Line name="avg" type="monotone" dataKey="avg" stroke={RETURN_HUE} strokeWidth={2.5} dot={{ r: 3 }} connectNulls />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
        <p className="mt-2 text-xs text-slate-600">
          <span className="text-violet-300">Violet line</span> = average return · shaded inner band = p25–p75 (typical spread) · faint outer band = worst–best. Above the dashed 0% line is net positive.
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
                            <div className="text-[10px] text-slate-300/70">n={n}</div>
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
          {metric === 'win'
            ? 'Colour: green ≥ 50% win-rate, red < 50%, slate at the 50% midpoint.'
            : 'Colour: green = positive EV, red = negative, slate at the 0% midpoint.'}{' '}
          <span className="text-slate-400">n=</span> under each cell is the sample size — how many signals fell in that reduction bucket at that horizon. Small n is noisy; trust the big-n cells.
        </p>
      </StateMsg>
    </Card>
  )
}

// ---------- RSI-at-fire signal-quality analysis ----------
//
// Tests whether RSI(14) at fire sharpens the flat 30% reduction gate (e.g. a
// bearish flatten at RSI 70 reads stronger than at 40). RSI buckets are
// *ordered*, so their series colour is a sequential ramp (light->dark), not
// arbitrary categorical hues — same for horizon, which is also ordered.

const RSI_BUCKETS = ['a <30', 'b 30-40', 'c 40-50', 'd 50-60', 'e 60-70', 'f >=70'] as const
type RsiDirection = 'bullish' | 'bearish'
const DIRECTIONS: { value: RsiDirection; label: string }[] = [
  { value: 'bullish', label: 'Bullish' },
  { value: 'bearish', label: 'Bearish' },
]
// Sequential ramps: violet identifies an RSI bucket (light=low RSI, dark=high);
// sky identifies a horizon (light=1d, dark=14d) — kept distinct from the win-rate
// ACCENT sky so the two charts' colour keys don't collide with each other's axis.
const RSI_RAMP = ['#ddd6fe', '#c4b5fd', '#a78bfa', '#8b5cf6', '#7c3aed', '#6d28d9'] // violet-200..700
const HORIZON_RAMP = ['#7dd3fc', '#38bdf8', '#0ea5e9', '#0369a1'] // sky-300..800

function bucketLabel(b: string): string {
  return b.slice(2)
}

function RsiHeatmap({ rows, metric }: { rows: PerfRsiBucket[]; metric: 'win' | 'ev' }) {
  const mid = metric === 'win' ? 50 : 0
  const span = metric === 'win' ? 25 : 10
  const title = metric === 'win' ? 'Win rate by RSI × horizon' : 'EV by RSI × horizon'

  const cell = (bucket: string, horizon: string) => {
    const row = rows.find((r) => r.rsi_bucket === bucket && r.horizon === horizon)
    const value = row ? (metric === 'win' ? row.win_pct : row.avg_ret_pct) : null
    return { value, n: row?.n ?? 0 }
  }

  return (
    <Card title={title}>
      <div className="overflow-x-auto">
        <table className="w-full border-separate text-sm" style={{ borderSpacing: 2 }}>
          <thead>
            <tr className="text-xs uppercase tracking-wide text-slate-500">
              <th className="py-1 pr-2 text-left font-medium">RSI</th>
              {HORIZONS.map((h) => (
                <th key={h} className="px-2 py-1 text-center font-medium">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {RSI_BUCKETS.map((bucket) => (
              <tr key={bucket}>
                <td className="py-1 pr-2 text-slate-300">{bucketLabel(bucket)}</td>
                {HORIZONS.map((h) => {
                  const { value, n } = cell(bucket, h)
                  return (
                    <td
                      key={h}
                      className="rounded px-2 py-1.5 text-center tabular-nums"
                      style={{ background: heatColor(value, mid, span), color: value == null ? '#475569' : '#f1f5f9' }}
                      title={value == null ? 'no data' : `RSI ${bucketLabel(bucket)} · ${h} · n=${n}`}
                    >
                      {value == null ? '—' : (
                        <>
                          <div>{fmtPctPts(value, metric === 'win' ? 1 : 2, metric === 'ev')}</div>
                          <div className="text-[10px] text-slate-300/70">n={n}</div>
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
        {metric === 'win'
          ? 'Colour: green ≥ 50% win-rate, red < 50%, slate at the 50% midpoint.'
          : 'Colour: green = positive EV, red = negative, slate at the 0% midpoint.'}{' '}
        <span className="text-slate-400">n=</span> is the sample size per cell — small n is noisy; trust the big-n cells.
      </p>
    </Card>
  )
}

function RsiWinCurve({ rows }: { rows: PerfRsiBucket[] }) {
  const byHB = new Map(rows.map((r) => [`${r.rsi_bucket}|${r.horizon}`, r]))
  const chartRows = HORIZONS.map((h) => {
    const row: Record<string, number | string | null> = { h }
    let wSum = 0
    let nSum = 0
    for (const b of RSI_BUCKETS) {
      const r = byHB.get(`${b}|${h}`)
      row[b] = r?.win_pct ?? null
      if (r && r.win_pct != null) {
        wSum += r.win_pct * r.n
        nSum += r.n
      }
    }
    row.baseline = nSum > 0 ? Math.round((wSum / nSum) * 10) / 10 : null
    return row
  })

  return (
    <Card title="Win rate by horizon, per RSI bucket">
      <div style={{ height: 240 }}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={chartRows}>
            <CartesianGrid stroke={GRID} vertical={false} />
            <XAxis dataKey="h" stroke={AXIS} fontSize={12} />
            <YAxis stroke={AXIS} fontSize={12} unit="%" domain={[0, 100]} />
            <ReferenceLine y={50} stroke={AXIS} strokeDasharray="3 3" />
            <Tooltip contentStyle={tooltipStyle} formatter={(v: number) => `${v}%`} />
            <Legend wrapperStyle={{ fontSize: 11 }} />
            {RSI_BUCKETS.map((b, i) => (
              <Line key={b} name={bucketLabel(b)} type="monotone" dataKey={b} stroke={RSI_RAMP[i]} strokeWidth={2} dot={{ r: 2 }} connectNulls />
            ))}
            <Line name="baseline (all RSI)" type="monotone" dataKey="baseline" stroke={AXIS} strokeWidth={1.5} strokeDasharray="4 3" dot={false} connectNulls />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <p className="mt-2 text-xs text-slate-600">
        One line per RSI(14)-at-fire bucket (light→dark = low→high RSI); dashed grey = the baseline win-rate across all RSI-tagged signals for this direction. A bucket above the baseline beats trading everything.
      </p>
    </Card>
  )
}

function RsiTrendByBucket({ rows }: { rows: PerfRsiBucket[] }) {
  const byHB = new Map(rows.map((r) => [`${r.rsi_bucket}|${r.horizon}`, r]))
  const chartRows = RSI_BUCKETS.map((b) => {
    const row: Record<string, number | string | null> = { bucket: bucketLabel(b) }
    for (const h of HORIZONS) {
      row[h] = byHB.get(`${b}|${h}`)?.win_pct ?? null
    }
    return row
  })

  return (
    <Card title="Win rate vs RSI bucket, per horizon">
      <div style={{ height: 240 }}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={chartRows}>
            <CartesianGrid stroke={GRID} vertical={false} />
            <XAxis dataKey="bucket" stroke={AXIS} fontSize={12} />
            <YAxis stroke={AXIS} fontSize={12} unit="%" domain={[0, 100]} />
            <ReferenceLine y={50} stroke={AXIS} strokeDasharray="3 3" />
            <Tooltip contentStyle={tooltipStyle} formatter={(v: number) => `${v}%`} />
            <Legend wrapperStyle={{ fontSize: 11 }} />
            {HORIZONS.map((h, i) => (
              <Line key={h} name={h} type="monotone" dataKey={h} stroke={HORIZON_RAMP[i]} strokeWidth={2} dot={{ r: 3 }} connectNulls />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
      <p className="mt-2 text-xs text-slate-600">
        The direct read on the thesis: a rising line means a higher RSI at fire correlates with a stronger result for this direction, per horizon.
      </p>
    </Card>
  )
}

export function RsiAnalysis() {
  const { data, isLoading, isError } = usePerfRsiBuckets()
  const [direction, setDirection] = useState<RsiDirection>('bullish')
  const all = data ?? []
  const rows = all.filter((r) => r.direction === direction)

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-medium text-slate-300">RSI(14) at fire — signal quality</h2>
        <Segmented options={DIRECTIONS} value={direction} onChange={setDirection} />
      </div>
      <StateMsg loading={isLoading} error={isError} empty={all.length === 0}>
        <div className="space-y-4">
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <RsiHeatmap rows={rows} metric="win" />
            <RsiHeatmap rows={rows} metric="ev" />
          </div>
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <RsiWinCurve rows={rows} />
            <RsiTrendByBucket rows={rows} />
          </div>
          <p className="text-xs text-slate-600">
            RSI is captured at fire time as context, not a firing condition — this measures whether it sharpens the histogram-reduction signal. Data accumulates since the RSI change shipped; small-n cells are noisy.
          </p>
        </div>
      </StateMsg>
    </div>
  )
}

// ---------- histogram peak vs the token's own tops ----------
//
// Axis = the percentile of this excursion's histogram peak among the token's OWN
// prior same-sign tops. The relationship runs the opposite way to what we assumed:
// a LOW percentile (a modest peak by this token's standards) outperforms. Fading a
// monster move fails — the momentum resumes; fading a tired one works.
//
// Bearish only, so far: it held in both regime halves at +1.6-2.1% EV, while bullish
// was significant in one half and reversed in the other. See docs/hist_peak_context.md.

const PEAK_BUCKETS = ['a <20', 'b 20-40', 'c 40-60', 'd 60-80', 'e 80-100'] as const
// Teal ramp — distinct from RSI violet and signal-line amber. Light = low
// percentile, which here is the FAVOURABLE end.
const PEAK_RAMP = ['#99f6e4', '#5eead4', '#2dd4bf', '#14b8a6', '#0d9488']

function PeakHeatmap({ rows, metric }: { rows: PerfPeakBucket[]; metric: 'win' | 'ev' }) {
  const mid = metric === 'win' ? 50 : 0
  const span = metric === 'win' ? 25 : 10
  const title = metric === 'win' ? 'Win rate by peak percentile × horizon' : 'EV by peak percentile × horizon'

  const cell = (bucket: string, horizon: string) => {
    const row = rows.find((r) => r.bucket === bucket && r.horizon === horizon)
    const value = row ? (metric === 'win' ? row.win_pct : row.avg_ret_pct) : null
    return { value, n: row?.n ?? 0 }
  }

  return (
    <Card title={title}>
      <div className="overflow-x-auto">
        <table className="w-full border-separate text-sm" style={{ borderSpacing: 2 }}>
          <thead>
            <tr className="text-xs uppercase tracking-wide text-slate-500">
              <th className="py-1 pr-2 text-left font-medium">Peak pct</th>
              {HORIZONS.map((h) => (
                <th key={h} className="px-2 py-1 text-center font-medium">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {PEAK_BUCKETS.map((bucket) => (
              <tr key={bucket}>
                <td className="py-1 pr-2 text-slate-300">{bucketLabel(bucket)}</td>
                {HORIZONS.map((h) => {
                  const { value, n } = cell(bucket, h)
                  return (
                    <td
                      key={h}
                      className="rounded px-2 py-1.5 text-center tabular-nums"
                      style={{ background: heatColor(value, mid, span), color: value == null ? '#475569' : '#f1f5f9' }}
                      title={value == null ? 'no data' : `peak pct ${bucketLabel(bucket)} · ${h} · n=${n}`}
                    >
                      {value == null ? '—' : (
                        <>
                          <div>{fmtPctPts(value, metric === 'win' ? 1 : 2, metric === 'ev')}</div>
                          <div className="text-[10px] text-slate-300/70">n={n}</div>
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
        Percentile of this excursion's histogram peak among the token's own prior same-sign tops.{' '}
        <span className="text-slate-400">Low = a modest peak for this token</span> — and that has been the favourable end for bearish fires.
      </p>
    </Card>
  )
}

function PeakTrendByBucket({ rows }: { rows: PerfPeakBucket[] }) {
  const byHB = new Map(rows.map((r) => [`${r.bucket}|${r.horizon}`, r]))
  const chartRows = PEAK_BUCKETS.map((b) => {
    const row: Record<string, number | string | null> = { bucket: bucketLabel(b) }
    for (const h of HORIZONS) {
      row[h] = byHB.get(`${b}|${h}`)?.win_pct ?? null
    }
    return row
  })

  return (
    <Card title="Win rate vs peak percentile, per horizon">
      <div style={{ height: 240 }}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={chartRows}>
            <CartesianGrid stroke={GRID} vertical={false} />
            <XAxis dataKey="bucket" stroke={AXIS} fontSize={11} />
            <YAxis stroke={AXIS} fontSize={12} unit="%" domain={[0, 100]} />
            <ReferenceLine y={50} stroke={AXIS} strokeDasharray="3 3" />
            <Tooltip contentStyle={tooltipStyle} formatter={(v: number) => `${v}%`} />
            <Legend wrapperStyle={{ fontSize: 11 }} />
            {HORIZONS.map((h, i) => (
              <Line key={h} name={h} type="monotone" dataKey={h} stroke={HORIZON_RAMP[i]} strokeWidth={2} dot={{ r: 3 }} connectNulls />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
      <p className="mt-2 text-xs text-slate-600">
        A <em>falling</em> line confirms the finding — smaller peaks (left) beating larger ones (right). This runs opposite to the intuition the metric was built on.
      </p>
    </Card>
  )
}

function PeakWinCurve({ rows }: { rows: PerfPeakBucket[] }) {
  const byHB = new Map(rows.map((r) => [`${r.bucket}|${r.horizon}`, r]))
  const chartRows = HORIZONS.map((h) => {
    const row: Record<string, number | string | null> = { h }
    let wSum = 0
    let nSum = 0
    for (const b of PEAK_BUCKETS) {
      const r = byHB.get(`${b}|${h}`)
      row[b] = r?.win_pct ?? null
      if (r && r.win_pct != null) {
        wSum += r.win_pct * r.n
        nSum += r.n
      }
    }
    row.baseline = nSum > 0 ? Math.round((wSum / nSum) * 10) / 10 : null
    return row
  })

  return (
    <Card title="Win rate by horizon, per peak-percentile band">
      <div style={{ height: 240 }}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={chartRows}>
            <CartesianGrid stroke={GRID} vertical={false} />
            <XAxis dataKey="h" stroke={AXIS} fontSize={12} />
            <YAxis stroke={AXIS} fontSize={12} unit="%" domain={[0, 100]} />
            <ReferenceLine y={50} stroke={AXIS} strokeDasharray="3 3" />
            <Tooltip contentStyle={tooltipStyle} formatter={(v: number) => `${v}%`} />
            <Legend wrapperStyle={{ fontSize: 11 }} />
            {PEAK_BUCKETS.map((b, i) => (
              <Line key={b} name={bucketLabel(b)} type="monotone" dataKey={b} stroke={PEAK_RAMP[i]} strokeWidth={2} dot={{ r: 2 }} connectNulls />
            ))}
            <Line name="baseline (all bands)" type="monotone" dataKey="baseline" stroke={AXIS} strokeWidth={1.5} strokeDasharray="4 3" dot={false} connectNulls />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <p className="mt-2 text-xs text-slate-600">
        Bands above the dashed baseline beat trading every signal in this direction. The two lowest bands are the ones that did.
      </p>
    </Card>
  )
}

export function PeakContextAnalysis() {
  const { data, isLoading, isError } = usePerfPeakContextBuckets()
  const [direction, setDirection] = useState<RsiDirection>('bearish')
  const all = data ?? []
  const rows = all.filter((r) => r.direction === direction)

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-medium text-slate-300">Histogram peak vs this token's own tops</h2>
        <Segmented options={DIRECTIONS} value={direction} onChange={setDirection} />
      </div>
      <StateMsg loading={isLoading} error={isError} empty={all.length === 0}>
        <div className="space-y-4">
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <PeakHeatmap rows={rows} metric="win" />
            <PeakHeatmap rows={rows} metric="ev" />
          </div>
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <PeakWinCurve rows={rows} />
            <PeakTrendByBucket rows={rows} />
          </div>
          <p className="text-xs text-slate-600">
            Each signal's histogram peak is ranked against the same token's own prior same-sign excursions, so a big move on a quiet token isn't confused with a normal move on a volatile one. Measured over ~3,000 scored signals, the <em>low</em> bands outperform — fading a move that is huge by a token's own standards has been the losing side, fading a tired one the winning side. This held in both halves of the sample for <strong>bearish</strong> fires; <strong>bullish</strong> did not hold up and carries no reliable read yet. Signals whose baseline rests on fewer than 3 prior tops are excluded.
          </p>
        </div>
      </StateMsg>
    </div>
  )
}

// ---------- MACD signal-line-at-fire signal-quality analysis ----------
//
// Axis = (fire_macd - fire_hist) / ATR: roughly 7 bars of trend drift over one bar
// of typical range, i.e. a trend signal-to-noise ratio. ATR-normalized rather than
// price-normalized because MACD scales with volatility too, and %-of-price buckets
// collapse into an asset-class proxy. Signed, because the sign is the regime: for a
// bearish fire, +1.2 is a mature uptrend rolling over, -0.4 a downtrend continuing.
//
// The signal line rather than the MACD line so the axis stays independent of `hist`,
// the detector's own firing variable — which ReductionHeatmap already covers.
// See docs/macd_signal_analysis.md.

const MACD_SIGNAL_BUCKETS = [
  'a <-1', 'b -1..-0.5', 'c -0.5..0', 'd 0..0.5', 'e 0.5..1', 'f >=1',
] as const
// Amber sequential ramp (low->high), kept distinct from the RSI section's violet so
// the two ordered-bucket analyses don't read as one chart.
const MACD_SIGNAL_RAMP = ['#fde68a', '#fcd34d', '#fbbf24', '#f59e0b', '#d97706', '#b45309']

function MacdSignalHeatmap({ rows, metric }: { rows: PerfMacdSignalBucket[]; metric: 'win' | 'ev' }) {
  const mid = metric === 'win' ? 50 : 0
  const span = metric === 'win' ? 25 : 10
  const title =
    metric === 'win' ? 'Win rate by signal line × horizon' : 'EV by signal line × horizon'

  const cell = (bucket: string, horizon: string) => {
    const row = rows.find((r) => r.bucket === bucket && r.horizon === horizon)
    const value = row ? (metric === 'win' ? row.win_pct : row.avg_ret_pct) : null
    return { value, n: row?.n ?? 0 }
  }

  return (
    <Card title={title}>
      <div className="overflow-x-auto">
        <table className="w-full border-separate text-sm" style={{ borderSpacing: 2 }}>
          <thead>
            <tr className="text-xs uppercase tracking-wide text-slate-500">
              <th className="py-1 pr-2 text-left font-medium">Signal ÷ ATR</th>
              {HORIZONS.map((h) => (
                <th key={h} className="px-2 py-1 text-center font-medium">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {MACD_SIGNAL_BUCKETS.map((bucket) => (
              <tr key={bucket}>
                <td className="py-1 pr-2 text-slate-300">{bucketLabel(bucket)}</td>
                {HORIZONS.map((h) => {
                  const { value, n } = cell(bucket, h)
                  return (
                    <td
                      key={h}
                      className="rounded px-2 py-1.5 text-center tabular-nums"
                      style={{ background: heatColor(value, mid, span), color: value == null ? '#475569' : '#f1f5f9' }}
                      title={value == null ? 'no data' : `signal÷ATR ${bucketLabel(bucket)} · ${h} · n=${n}`}
                    >
                      {value == null ? '—' : (
                        <>
                          <div>{fmtPctPts(value, metric === 'win' ? 1 : 2, metric === 'ev')}</div>
                          <div className="text-[10px] text-slate-300/70">n={n}</div>
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
        {metric === 'win'
          ? 'Colour: green ≥ 50% win-rate, red < 50%, slate at the 50% midpoint.'
          : 'Colour: green = positive EV, red = negative, slate at the 0% midpoint.'}{' '}
        <span className="text-slate-400">n=</span> is the sample size per cell — small n is noisy; trust the big-n cells.
      </p>
    </Card>
  )
}

function MacdSignalWinCurve({ rows }: { rows: PerfMacdSignalBucket[] }) {
  const byHB = new Map(rows.map((r) => [`${r.bucket}|${r.horizon}`, r]))
  const chartRows = HORIZONS.map((h) => {
    const row: Record<string, number | string | null> = { h }
    let wSum = 0
    let nSum = 0
    for (const b of MACD_SIGNAL_BUCKETS) {
      const r = byHB.get(`${b}|${h}`)
      row[b] = r?.win_pct ?? null
      if (r && r.win_pct != null) {
        wSum += r.win_pct * r.n
        nSum += r.n
      }
    }
    row.baseline = nSum > 0 ? Math.round((wSum / nSum) * 10) / 10 : null
    return row
  })

  return (
    <Card title="Win rate by horizon, per signal-line bucket">
      <div style={{ height: 240 }}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={chartRows}>
            <CartesianGrid stroke={GRID} vertical={false} />
            <XAxis dataKey="h" stroke={AXIS} fontSize={12} />
            <YAxis stroke={AXIS} fontSize={12} unit="%" domain={[0, 100]} />
            <ReferenceLine y={50} stroke={AXIS} strokeDasharray="3 3" />
            <Tooltip contentStyle={tooltipStyle} formatter={(v: number) => `${v}%`} />
            <Legend wrapperStyle={{ fontSize: 11 }} />
            {MACD_SIGNAL_BUCKETS.map((b, i) => (
              <Line key={b} name={bucketLabel(b)} type="monotone" dataKey={b} stroke={MACD_SIGNAL_RAMP[i]} strokeWidth={2} dot={{ r: 2 }} connectNulls />
            ))}
            <Line name="baseline (all buckets)" type="monotone" dataKey="baseline" stroke={AXIS} strokeWidth={1.5} strokeDasharray="4 3" dot={false} connectNulls />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <p className="mt-2 text-xs text-slate-600">
        Read the dashed baseline first. A driftless random walk still produces |signal÷ATR| above 1.0 about 30% of the time, so the question isn't whether the buckets differ from each other — it's whether any of them beats trading every signal.
      </p>
    </Card>
  )
}

function MacdSignalTrendByBucket({ rows }: { rows: PerfMacdSignalBucket[] }) {
  const byHB = new Map(rows.map((r) => [`${r.bucket}|${r.horizon}`, r]))
  const chartRows = MACD_SIGNAL_BUCKETS.map((b) => {
    const row: Record<string, number | string | null> = { bucket: bucketLabel(b) }
    for (const h of HORIZONS) {
      row[h] = byHB.get(`${b}|${h}`)?.win_pct ?? null
    }
    return row
  })

  return (
    <Card title="Win rate vs signal-line bucket, per horizon">
      <div style={{ height: 240 }}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={chartRows}>
            <CartesianGrid stroke={GRID} vertical={false} />
            <XAxis dataKey="bucket" stroke={AXIS} fontSize={11} />
            <YAxis stroke={AXIS} fontSize={12} unit="%" domain={[0, 100]} />
            <ReferenceLine y={50} stroke={AXIS} strokeDasharray="3 3" />
            <Tooltip contentStyle={tooltipStyle} formatter={(v: number) => `${v}%`} />
            <Legend wrapperStyle={{ fontSize: 11 }} />
            {HORIZONS.map((h, i) => (
              <Line key={h} name={h} type="monotone" dataKey={h} stroke={HORIZON_RAMP[i]} strokeWidth={2} dot={{ r: 3 }} connectNulls />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
      <p className="mt-2 text-xs text-slate-600">
        The direct read: a sloped line means where the trend sat at fire time correlates with the result. Flat means the signal line adds nothing over the reduction gate.
      </p>
    </Card>
  )
}

// ---------- the same signal line, normalized by price instead of ATR ----------
//
// A second lens, not a replacement. %-of-price is the more legible unit at a glance
// ("3% of price above equilibrium") but is partly an asset-class proxy, because MACD
// scales with volatility as well as price; the ATR view above is the one that
// survives cross-class comparison. They sit together so a finding in one can be
// checked against the other. See docs/macd_signal_pct_analysis.md.
//
// Even 2%-wide steps: 76% of signals sit within ±5% of zero, so wider buckets dumped
// three-quarters of the data into a handful of cells and hid whatever structure is
// in the band that matters most.

const MACD_SIGNAL_PCT_BUCKETS = [
  'a <-10', 'b -10..-8', 'c -8..-6', 'd -6..-4', 'e -4..-2', 'f -2..0',
  'g 0..2', 'h 2..4', 'i 4..6', 'j 6..8', 'k 8..10', 'l >=10',
] as const
// Rose→fuchsia ramp, distinct from RSI violet, peak-context teal and the ATR view's
// amber. Ordered buckets, so it stays a single sweep rather than categorical hues.
const MACD_SIGNAL_PCT_RAMP = [
  '#fecdd3', '#fda4af', '#fb7185', '#f43f5e', '#e11d48', '#be123c',
  '#9f1239', '#a21caf', '#c026d3', '#d946ef', '#e879f9', '#f5d0fe',
]

function MacdSignalPctHeatmap({
  rows,
  metric,
}: {
  rows: PerfMacdSignalPctBucket[]
  metric: 'win' | 'ev'
}) {
  const mid = metric === 'win' ? 50 : 0
  const span = metric === 'win' ? 25 : 10
  const title =
    metric === 'win' ? 'Win rate by signal ÷ price' : 'EV by signal ÷ price'

  const cell = (bucket: string, horizon: string) => {
    const row = rows.find((r) => r.bucket === bucket && r.horizon === horizon)
    const value = row ? (metric === 'win' ? row.win_pct : row.avg_ret_pct) : null
    return { value, n: row?.n ?? 0 }
  }

  return (
    <Card title={title}>
      <div className="overflow-x-auto">
        <table className="w-full border-separate text-sm" style={{ borderSpacing: 2 }}>
          <thead>
            <tr className="text-xs uppercase tracking-wide text-slate-500">
              <th className="py-1 pr-2 text-left font-medium">Signal ÷ price %</th>
              {HORIZONS.map((h) => (
                <th key={h} className="px-2 py-1 text-center font-medium">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {MACD_SIGNAL_PCT_BUCKETS.map((bucket) => (
              <tr key={bucket}>
                <td className="py-1 pr-2 text-slate-300">{bucketLabel(bucket)}</td>
                {HORIZONS.map((h) => {
                  const { value, n } = cell(bucket, h)
                  return (
                    <td
                      key={h}
                      className="rounded px-2 py-1 text-center tabular-nums"
                      style={{ background: heatColor(value, mid, span), color: value == null ? '#475569' : '#f1f5f9' }}
                      title={value == null ? 'no data' : `signal÷price ${bucketLabel(bucket)}% · ${h} · n=${n}`}
                    >
                      {value == null ? '—' : (
                        <>
                          <div>{fmtPctPts(value, metric === 'win' ? 1 : 2, metric === 'ev')}</div>
                          <div className="text-[10px] text-slate-300/70">n={n}</div>
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
        Empty cells in the bullish positive tail are real, not missing data: bullish
        fires on a flattening downtrend, so a strongly positive (mature-uptrend) signal
        line essentially cannot co-occur with it.
      </p>
    </Card>
  )
}

function MacdSignalPctWinCurve({ rows }: { rows: PerfMacdSignalPctBucket[] }) {
  // Only plot bands this direction actually populates — bullish leaves the top two
  // empty, and dropping them keeps a 12-band chart from carrying dead legend entries.
  const present = MACD_SIGNAL_PCT_BUCKETS.filter((b) =>
    rows.some((r) => r.bucket === b && r.n > 0),
  )
  const byHB = new Map(rows.map((r) => [`${r.bucket}|${r.horizon}`, r]))
  const chartRows = HORIZONS.map((h) => {
    const row: Record<string, number | string | null> = { h }
    let wSum = 0
    let nSum = 0
    for (const b of present) {
      const r = byHB.get(`${b}|${h}`)
      row[b] = r?.win_pct ?? null
      if (r && r.win_pct != null) {
        wSum += r.win_pct * r.n
        nSum += r.n
      }
    }
    row.baseline = nSum > 0 ? Math.round((wSum / nSum) * 10) / 10 : null
    return row
  })

  return (
    <Card title="Win rate by horizon, per price band">
      <div style={{ height: 260 }}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={chartRows}>
            <CartesianGrid stroke={GRID} vertical={false} />
            <XAxis dataKey="h" stroke={AXIS} fontSize={12} />
            <YAxis stroke={AXIS} fontSize={12} unit="%" domain={[0, 100]} />
            <ReferenceLine y={50} stroke={AXIS} strokeDasharray="3 3" />
            <Tooltip contentStyle={tooltipStyle} formatter={(v: number) => `${v}%`} />
            <Legend wrapperStyle={{ fontSize: 10 }} />
            {present.map((b) => (
              <Line
                key={b}
                name={bucketLabel(b)}
                type="monotone"
                dataKey={b}
                stroke={MACD_SIGNAL_PCT_RAMP[MACD_SIGNAL_PCT_BUCKETS.indexOf(b)]}
                strokeWidth={1.5}
                dot={{ r: 1.5 }}
                connectNulls
              />
            ))}
            <Line name="baseline (all bands)" type="monotone" dataKey="baseline" stroke={AXIS} strokeWidth={2} strokeDasharray="4 3" dot={false} connectNulls />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <p className="mt-2 text-xs text-slate-600">
        Twelve bands makes this deliberately crowded — <strong>read the shape, not
        individual lines</strong>: whether the bundle fans out with horizon, and which
        side of the dashed baseline it sits on. The chart beside it is the tool for a
        precise per-band read.
      </p>
    </Card>
  )
}

function MacdSignalPctTrendByBucket({ rows }: { rows: PerfMacdSignalPctBucket[] }) {
  const byHB = new Map(rows.map((r) => [`${r.bucket}|${r.horizon}`, r]))
  const chartRows = MACD_SIGNAL_PCT_BUCKETS.map((b) => {
    const row: Record<string, number | string | null> = { bucket: bucketLabel(b) }
    for (const h of HORIZONS) {
      row[h] = byHB.get(`${b}|${h}`)?.win_pct ?? null
    }
    return row
  })

  return (
    <Card title="Win rate vs price band, per horizon">
      <div style={{ height: 260 }}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={chartRows} margin={{ bottom: 16 }}>
            <CartesianGrid stroke={GRID} vertical={false} />
            <XAxis
              dataKey="bucket"
              stroke={AXIS}
              fontSize={9}
              angle={-40}
              textAnchor="end"
              height={52}
              interval={0}
            />
            <YAxis stroke={AXIS} fontSize={12} unit="%" domain={[0, 100]} />
            <ReferenceLine y={50} stroke={AXIS} strokeDasharray="3 3" />
            <Tooltip contentStyle={tooltipStyle} formatter={(v: number) => `${v}%`} />
            <Legend wrapperStyle={{ fontSize: 11 }} />
            {HORIZONS.map((h, i) => (
              <Line key={h} name={h} type="monotone" dataKey={h} stroke={HORIZON_RAMP[i]} strokeWidth={2} dot={{ r: 2.5 }} connectNulls />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
      <p className="mt-2 text-xs text-slate-600">
        The precise view, and what the finer bands were added for — twelve x-axis points
        instead of six. A monotone slope means where the trend sat relative to price
        correlates with the result; check it against the ATR chart above before
        believing it (see the note at the foot of this panel).
      </p>
    </Card>
  )
}

export function MacdSignalAnalysis() {
  const atrQ = usePerfMacdSignalBuckets()
  const pctQ = usePerfMacdSignalPctBuckets()
  const [direction, setDirection] = useState<RsiDirection>('bullish')

  const atrAll = atrQ.data ?? []
  const pctAll = pctQ.data ?? []
  const atrRows = atrAll.filter((r) => r.direction === direction)
  const pctRows = pctAll.filter((r) => r.direction === direction)

  // One toggle governs both groups — they are two normalizations of the same
  // metric, so splitting the control would invite reading them at odds.
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-medium text-slate-300">MACD signal line at fire — trend context</h2>
        <Segmented options={DIRECTIONS} value={direction} onChange={setDirection} />
      </div>
      <StateMsg
        loading={atrQ.isLoading || pctQ.isLoading}
        error={atrQ.isError || pctQ.isError}
        empty={atrAll.length === 0 && pctAll.length === 0}
      >
        <div className="space-y-4">
          <h3 className="text-xs font-medium uppercase tracking-wide text-slate-500">
            ATR-normalized <span className="normal-case text-slate-600">— comparable across asset classes</span>
          </h3>
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <MacdSignalHeatmap rows={atrRows} metric="win" />
            <MacdSignalHeatmap rows={atrRows} metric="ev" />
          </div>
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <MacdSignalWinCurve rows={atrRows} />
            <MacdSignalTrendByBucket rows={atrRows} />
          </div>

          <h3 className="pt-2 text-xs font-medium uppercase tracking-wide text-slate-500">
            Price-normalized <span className="normal-case text-slate-600">— more legible, but class-confounded</span>
          </h3>
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <MacdSignalPctHeatmap rows={pctRows} metric="win" />
            <MacdSignalPctHeatmap rows={pctRows} metric="ev" />
          </div>
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <MacdSignalPctWinCurve rows={pctRows} />
            <MacdSignalPctTrendByBucket rows={pctRows} />
          </div>

          <p className="text-xs text-slate-600">
            Both groups plot the same value — the MACD signal line at fire — under two
            normalizations. <strong>÷ ATR</strong> is roughly 7 bars of trend drift per bar
            of typical range, so it reads as <em>how cleanly the trend was moving</em>
            rather than how far, and it stays comparable across asset classes.{' '}
            <strong>÷ price</strong> is the more legible unit ("3% of price above
            equilibrium") but is partly an asset-class proxy, since MACD scales with
            volatility as well as price — median |signal ÷ price| runs about 3.2% for
            crypto against 2.3% for equity, so a gradient down the price bands may be
            re-reading class mix rather than a real within-class effect.{' '}
            <strong>Cross-check any finding in the lower group against the upper one
            before trusting it.</strong> Signed in both: for a bearish fire, positive = a
            mature uptrend rolling over, negative = a downtrend continuing. Both are
            derived from existing columns, so they cover the full signal history.
          </p>
        </div>
      </StateMsg>
    </div>
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
      <PeakContextAnalysis />
      <RsiAnalysis />
      <MacdSignalAnalysis />
    </div>
  )
}
