// The confidence tab's panels.
//
// Different job from the Outcomes tab: that one explores *whether* a factor
// matters, this one reports on a rule that already does, in the smallest number of
// decision-grade figures. Every panel shows the confident cohort against the rest,
// because a 70% win rate only means something next to the ~49% you'd get taking
// everything.
//
// The rule and its thresholds live in src/macd_searcher/signals.py; the measurement
// behind them is in docs/hist_peak_context.md and docs/confidence.md.

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
  usePerfConfidenceSensitivity,
  usePerfConfidenceSummary,
  usePerfConfidenceTimeline,
} from '../api/client'
import type {
  Horizon,
  PerfConfidencePoint,
  PerfConfidenceSensitivity,
  PerfConfidenceSummary,
} from '../api/types'
import { fmtPctPts } from '../lib/format'
import { Badge, Card, StateMsg, tone } from './ui'

const AXIS = '#64748b'
const GRID = '#1e293b'
const tooltipStyle = {
  background: '#0f172a',
  border: '1px solid #1e293b',
  borderRadius: 8,
  fontSize: 12,
}
const HORIZONS: Horizon[] = ['1d', '3d', '7d', '14d']

// Below this many scored confident signals the numbers move too much to act on.
const THIN_COHORT = 30

function pick(rows: PerfConfidenceSummary[] | undefined, cohort: string) {
  return (rows ?? []).find((r) => r.cohort === cohort)
}

/** Paired confident-vs-rest figure with the delta, the tab's core unit. */
function PairedStat({
  label,
  confident,
  rest,
  mid,
  digits = 1,
  suffix = '%',
  hint,
}: {
  label: string
  confident: number | null | undefined
  rest: number | null | undefined
  mid: number
  digits?: number
  suffix?: string
  hint?: string
}) {
  const delta =
    confident != null && rest != null ? confident - rest : null

  return (
    <div className="rounded-lg border border-slate-800 bg-slate-950/40 p-3" title={hint}>
      <div className="text-xs uppercase tracking-wide text-slate-500">{label}</div>
      <div className="mt-1 flex items-baseline gap-2">
        <span className={`text-2xl font-semibold ${tone(confident, mid)}`}>
          {confident == null ? '—' : `${confident.toFixed(digits)}${suffix}`}
        </span>
        {delta != null && (
          <Badge color={delta > 0 ? 'green' : delta < 0 ? 'red' : 'slate'}>
            {delta > 0 ? '+' : ''}
            {delta.toFixed(digits)}
          </Badge>
        )}
      </div>
      <div className="mt-0.5 text-xs text-slate-500">
        rest: {rest == null ? '—' : `${rest.toFixed(digits)}${suffix}`}
      </div>
    </div>
  )
}

export function ConfidenceScorecard({ horizon }: { horizon: Horizon }) {
  const { data, isLoading, isError } = usePerfConfidenceSummary(horizon)
  const conf = pick(data, 'confident')
  const rest = pick(data, 'rest')
  const thin = (conf?.n ?? 0) < THIN_COHORT

  return (
    <Card
      title={`Confident vs rest — ${horizon}`}
      right={
        conf && (
          <span className="text-xs text-slate-500">
            {conf.n} of {conf.n + (rest?.n ?? 0)} scored ({conf.share_pct}%)
          </span>
        )
      }
    >
      <StateMsg loading={isLoading} error={isError} empty={!conf && !rest}>
        {thin && (
          <p className="mb-3 rounded-md border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-300">
            Only {conf?.n ?? 0} scored confident signals so far — under {THIN_COHORT} these
            figures move a lot between runs. Treat them as accumulating, not settled.
          </p>
        )}
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <PairedStat
            label="Win rate"
            confident={conf?.win_pct}
            rest={rest?.win_pct}
            mid={50}
            hint="Share of signals where the predicted move happened. Green above 50%."
          />
          <PairedStat
            label="EV per signal"
            confident={conf?.ev_pct}
            rest={rest?.ev_pct}
            mid={0}
            digits={2}
            hint="Mean direction-normalized return — the number that compounds."
          />
          <PairedStat
            label="Median return"
            confident={conf?.median_pct}
            rest={rest?.median_pct}
            mid={0}
            digits={2}
            hint="The typical outcome, unmoved by a single outlier."
          />
          <PairedStat
            label="Payoff ratio"
            confident={conf?.payoff}
            rest={rest?.payoff}
            mid={1}
            digits={2}
            suffix=""
            hint="Average win ÷ average loss. Near 1.0 means the edge comes from being right more often, not from bigger winners."
          />
        </div>
      </StateMsg>
    </Card>
  )
}

/** Where to put a target and a stop — the most directly tradeable panel here. */
export function ExcursionTiles({ horizon }: { horizon: Horizon }) {
  const { data, isLoading, isError } = usePerfConfidenceSummary(horizon)
  const conf = pick(data, 'confident')
  const rest = pick(data, 'rest')

  return (
    <Card title="Excursion — target and stop guidance">
      <StateMsg loading={isLoading} error={isError} empty={!conf}>
        <div className="grid grid-cols-2 gap-3">
          <PairedStat
            label="Avg best move (MFE)"
            confident={conf?.mfe_pct}
            rest={rest?.mfe_pct}
            mid={0}
            digits={2}
            hint="How far the trade went in your favour at its best point — an upper bound on a realistic target."
          />
          <PairedStat
            label="Avg worst move (MAE)"
            confident={conf?.mae_pct}
            rest={rest?.mae_pct}
            mid={0}
            digits={2}
            hint="How far it went against you at its worst — a stop tighter than this gets hit on trades that would have won."
          />
        </div>
        <p className="mt-3 text-xs text-slate-600">
          Measured over the {horizon} window from the fire price. The confident cohort's
          edge shows up more in a <em>shallower</em> adverse excursion than in a bigger
          favourable one — it loses less rather than winning bigger, which is also what
          the ~1.0 payoff ratio is saying.
        </p>
      </StateMsg>
    </Card>
  )
}

export function HorizonBreakdown({ horizon }: { horizon: Horizon }) {
  // One query per horizon so the table shows all four at once; they're cached and
  // shared with the panels above, so the horizon in view costs nothing extra.
  const queries = HORIZONS.map((h) => usePerfConfidenceSummary(h))
  const loading = queries.some((q) => q.isLoading)
  const error = queries.some((q) => q.isError)

  return (
    <Card title="Edge by holding period">
      <StateMsg loading={loading} error={error} empty={false}>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-800 text-left text-xs uppercase tracking-wide text-slate-500">
                <th className="py-2 pr-3 font-medium">Horizon</th>
                <th className="py-2 pr-3 font-medium">n</th>
                <th className="py-2 pr-3 font-medium">Win — confident</th>
                <th className="py-2 pr-3 font-medium">Win — rest</th>
                <th className="py-2 pr-3 font-medium">EV — confident</th>
                <th className="py-2 pr-3 font-medium">EV — rest</th>
              </tr>
            </thead>
            <tbody>
              {HORIZONS.map((h, i) => {
                const conf = pick(queries[i].data, 'confident')
                const rest = pick(queries[i].data, 'rest')
                const active = h === horizon
                return (
                  <tr
                    key={h}
                    className={`border-b border-slate-800/50 ${active ? 'bg-slate-800/30' : ''}`}
                  >
                    <td className="py-1.5 pr-3 font-medium text-slate-200">
                      {h}
                      {active && <span className="ml-1 text-xs text-slate-500">(shown)</span>}
                    </td>
                    <td className="py-1.5 pr-3 tabular-nums text-slate-400">{conf?.n ?? '—'}</td>
                    <td className={`py-1.5 pr-3 tabular-nums ${tone(conf?.win_pct, 50)}`}>
                      {fmtPctPts(conf?.win_pct, 1)}
                    </td>
                    <td className="py-1.5 pr-3 tabular-nums text-slate-500">
                      {fmtPctPts(rest?.win_pct, 1)}
                    </td>
                    <td className={`py-1.5 pr-3 tabular-nums ${tone(conf?.ev_pct, 0)}`}>
                      {fmtPctPts(conf?.ev_pct, 2, true)}
                    </td>
                    <td className="py-1.5 pr-3 tabular-nums text-slate-500">
                      {fmtPctPts(rest?.ev_pct, 2, true)}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
        <p className="mt-2 text-xs text-slate-600">
          Where the edge peaks tells you how long to hold. A confident row that beats
          'rest' at every horizon is the rule working; one that only wins at 14d is a
          slower trade than the alert implies.
        </p>
      </StateMsg>
    </Card>
  )
}

/** The honesty panel: rule decay shows up here first. */
export function StabilityChart({ horizon, metric }: { horizon: Horizon; metric: 'win' | 'ev' }) {
  const { data, isLoading, isError } = usePerfConfidenceTimeline(horizon)
  const rows = data ?? []

  const months = Array.from(new Set(rows.map((r) => r.month))).sort()
  const get = (cohort: string, month: string): PerfConfidencePoint | undefined =>
    rows.find((r) => r.cohort === cohort && r.month === month)

  const key = metric === 'win' ? 'win_pct' : 'ev_pct'
  const chartRows = months.map((m) => ({
    month: m,
    confident: get('confident', m)?.[key] ?? null,
    rest: get('rest', m)?.[key] ?? null,
    confidentN: get('confident', m)?.n ?? 0,
  }))
  const midline = metric === 'win' ? 50 : 0

  return (
    <Card
      title={metric === 'win' ? 'Win rate by month' : 'EV by month'}
      right={<span className="text-xs text-slate-500">{horizon}</span>}
    >
      <StateMsg loading={isLoading} error={isError} empty={rows.length === 0}>
        <div style={{ height: 240 }}>
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartRows}>
              <CartesianGrid stroke={GRID} vertical={false} />
              <XAxis dataKey="month" stroke={AXIS} fontSize={11} />
              <YAxis
                stroke={AXIS}
                fontSize={12}
                unit="%"
                domain={metric === 'win' ? [0, 100] : ['auto', 'auto']}
              />
              <ReferenceLine y={midline} stroke={AXIS} strokeDasharray="3 3" />
              <Tooltip
                contentStyle={tooltipStyle}
                formatter={(v: number, name: string) => [`${v}%`, name]}
              />
              <Legend wrapperStyle={{ fontSize: 11 }} />
              <Line
                name="confident"
                type="monotone"
                dataKey="confident"
                stroke="#34d399"
                strokeWidth={2.5}
                dot={{ r: 3 }}
                connectNulls
              />
              <Line
                name="rest"
                type="monotone"
                dataKey="rest"
                stroke={AXIS}
                strokeWidth={1.5}
                strokeDasharray="4 3"
                dot={{ r: 2 }}
                connectNulls
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
        <div className="mt-2 flex flex-wrap gap-x-3 text-[10px] text-slate-600">
          {chartRows.map((r) => (
            <span key={r.month} className={r.confidentN < 15 ? 'text-amber-500/70' : undefined}>
              {r.month}: n={r.confidentN}
            </span>
          ))}
        </div>
        <p className="mt-2 text-xs text-slate-600">
          The thresholds were fitted on this sample, so early months flatter themselves —
          the value is in whether <em>new</em> months hold the gap over 'rest'. Amber month
          labels have too few confident signals to read.
        </p>
      </StateMsg>
    </Card>
  )
}

function sensColor(v: number | null, mid: number, span: number): string {
  if (v == null) return '#0f172a'
  const t = Math.max(-1, Math.min(1, (v - mid) / span))
  // Single-hue teal ramp: this grid is about finding a smooth plateau, and a
  // diverging scale would imply a good/bad split that isn't the question here.
  const alpha = 0.12 + 0.55 * Math.abs(t)
  return t >= 0 ? `rgba(45, 212, 191, ${alpha})` : `rgba(100, 116, 139, ${alpha})`
}

/** Threshold sensitivity — a plateau check, explicitly NOT a tuner. */
export function SensitivityGrid({ horizon, metric }: { horizon: Horizon; metric: 'win' | 'ev' }) {
  const { data, isLoading, isError } = usePerfConfidenceSensitivity(horizon)
  const rows = data ?? []

  const reductions = Array.from(new Set(rows.map((r) => r.max_reduction))).sort((a, b) => a - b)
  const peaks = Array.from(new Set(rows.map((r) => r.max_peak_pct))).sort((a, b) => a - b)
  const cell = (red: number, pk: number): PerfConfidenceSensitivity | undefined =>
    rows.find((r) => r.max_reduction === red && r.max_peak_pct === pk)

  const mid = metric === 'win' ? 55 : 1
  const span = metric === 'win' ? 15 : 1.5

  return (
    <Card
      title={metric === 'win' ? 'Threshold sensitivity — win rate' : 'Threshold sensitivity — EV'}
      right={<span className="text-xs text-slate-500">{horizon}</span>}
    >
      <StateMsg loading={isLoading} error={isError} empty={rows.length === 0}>
        <div className="overflow-x-auto">
          <table className="w-full border-separate text-sm" style={{ borderSpacing: 2 }}>
            <thead>
              <tr className="text-xs uppercase tracking-wide text-slate-500">
                <th className="py-1 pr-2 text-left font-medium">Max red ↓ / peak pct →</th>
                {peaks.map((p) => (
                  <th key={p} className="px-2 py-1 text-center font-medium">
                    &lt;{p}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {reductions.map((red) => (
                <tr key={red}>
                  <td className="py-1 pr-2 text-slate-300">&lt;{red}</td>
                  {peaks.map((pk) => {
                    const c = cell(red, pk)
                    const value = c ? (metric === 'win' ? c.win_pct : c.ev_pct) : null
                    return (
                      <td
                        key={pk}
                        className={`rounded px-2 py-1.5 text-center tabular-nums ${
                          c?.is_current ? 'ring-2 ring-emerald-400' : ''
                        }`}
                        style={{
                          background: sensColor(value, mid, span),
                          color: value == null ? '#475569' : '#e2e8f0',
                        }}
                        title={
                          c
                            ? `reduction <${red}, peak pct <${pk} · n=${c.n} (${c.share_pct}% of signals)` +
                              (c.is_current ? ' · CURRENT SETTING' : '')
                            : 'no data'
                        }
                      >
                        {value == null ? (
                          '—'
                        ) : (
                          <>
                            <div>{fmtPctPts(value, metric === 'win' ? 1 : 2, metric === 'ev')}</div>
                            <div className="text-[10px] text-slate-300/70">n={c?.n}</div>
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
          The ringed cell is the setting in force. Read this for <strong>shape, not for a
          winner</strong>: a smooth region around the ring means the rule is robust to where
          exactly the lines are drawn, while an isolated bright square would mean it is
          fitted to noise. Retuning to the best-looking cell on the same data the rule was
          derived from is how it gets overfit — that needs fresh data, not a brighter square.
        </p>
      </StateMsg>
    </Card>
  )
}
