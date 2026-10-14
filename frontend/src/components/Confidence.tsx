// The confidence tab's panels.
//
// Different job from the Outcomes tab: that one explores *whether* a factor
// matters, this one reports on a rule that already does, in the smallest number of
// decision-grade figures. Every panel shows the confident cohort against the rest,
// because a 63% win rate only means something next to the ~48% you'd get taking
// everything.
//
// The rule and its thresholds live in src/macd_searcher/signals.py; the measurement
// behind them is in docs/confidence_v2.md. (v1 was a bearish peak-context rule; it
// decayed to +0.07% EV and was retired — docs/confidence.md keeps that record.)

import { Fragment } from 'react'
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
  usePerfConfidenceCompare,
  usePerfConfidenceSensitivity,
  usePerfConfidenceSummary,
  usePerfConfidenceTimeline,
} from '../api/client'
import type {
  Horizon,
  PerfConfidencePoint,
  PerfConfidenceSensitivity,
  PerfConfidenceSummary,
  PerfRuleCompare,
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

// ---------- v2 (live) vs v3 (shadow) — raw EV split into market + alpha ----------
//
// The other panels judge a rule on raw EV, which is market move + alpha. Nothing
// here predicts the market move — v1 was retired and v2 adopted on market direction
// (docs/confidence_v3_research.md) — so this panel puts alpha, the part a rule's
// choice of asset controls, next to the raw number. v3 is shadow-only until the
// research watchlist confirms it (docs/confidence_v3.md).

const RULE_LABELS: Record<string, { name: string; note: string }> = {
  v2: { name: 'v2 · live', note: 'bullish, sig/ATR < −0.5, reduction < 0.6 — bolded in Telegram' },
  v3: { name: 'v3 · shadow', note: 'bullish, peak ≤ 50th pct of own swings, reduction < 0.6' },
  v3_bear: { name: 'v3 bearish · shadow', note: 'bearish, peak ≤ 25th pct — tracked only' },
  record: { name: 'record trough', note: 'bullish on the deepest swing in the window — the warning' },
  all: { name: 'everything', note: 'every scored signal' },
}

function alphaCell(r: PerfRuleCompare) {
  if (r.alpha_pct == null) return <span className="text-slate-500">—</span>
  const sure = r.alpha_lo != null && r.alpha_hi != null && (r.alpha_lo > 0 || r.alpha_hi < 0)
  return (
    <span className={sure ? tone(r.alpha_pct) : 'text-slate-300'}>
      {fmtPctPts(r.alpha_pct, 2, true)}
      {r.alpha_lo != null && r.alpha_hi != null && (
        <span className="ml-1 text-xs text-slate-500">
          [{r.alpha_lo.toFixed(2)}, {r.alpha_hi.toFixed(2)}]
        </span>
      )}
    </span>
  )
}

export function RuleComparison({ horizon }: { horizon: Horizon }) {
  const { data, isLoading, isError } = usePerfConfidenceCompare(horizon)
  const rules = data?.rules ?? []
  const months = [...new Set((data?.months ?? []).map((m) => m.month))].sort()
  const monthly = (rule: string, month: string) =>
    data?.months.find((m) => m.rule === rule && m.month === month)

  return (
    <Card title={`Rules compared — raw EV = market + alpha (${horizon})`}>
      <StateMsg loading={isLoading} error={isError} empty={rules.length === 0}>
        <div className="overflow-x-auto">
          <table className="w-full text-sm tabular-nums">
            <thead>
              <tr className="text-left text-xs uppercase tracking-wide text-slate-500">
                <th className="py-1 pr-3 font-medium">rule</th>
                {/* n and win hide on phones so alpha — the column that matters — stays on screen */}
                <th className="hidden py-1 pr-3 text-right font-medium sm:table-cell" title="Scored signals">n</th>
                <th
                  className="py-1 pr-3 text-right font-medium"
                  title="Repeat fires on consecutive days grouped — the effective sample size"
                >
                  episodes
                </th>
                <th className="hidden py-1 pr-3 text-right font-medium sm:table-cell">win</th>
                <th className="py-1 pr-3 text-right font-medium" title="Mean direction-normalized return">
                  raw EV
                </th>
                <th
                  className="py-1 pr-3 text-right font-medium"
                  title="What a random same-class asset, bought at the same instant, gave this side of the trade"
                >
                  = market
                </th>
                <th
                  className="py-1 text-right font-medium"
                  title="What the rule's choice of asset added. 95% interval: one number per episode, whole weeks resampled. Coloured only when the interval excludes zero."
                >
                  + alpha [95%]
                </th>
              </tr>
            </thead>
            <tbody>
              {rules.map((r) => (
                <tr key={r.rule} className="border-t border-slate-800/60" title={RULE_LABELS[r.rule]?.note}>
                  <td className="py-1.5 pr-3 text-slate-300">{RULE_LABELS[r.rule]?.name ?? r.rule}</td>
                  <td className="hidden py-1.5 pr-3 text-right text-slate-400 sm:table-cell">{r.n}</td>
                  <td className="py-1.5 pr-3 text-right text-slate-400">{r.episodes}</td>
                  <td className={`hidden py-1.5 pr-3 text-right sm:table-cell ${tone(r.win_pct, 50)}`}>{fmtPctPts(r.win_pct)}</td>
                  <td className={`py-1.5 pr-3 text-right ${tone(r.ev_pct)}`}>{fmtPctPts(r.ev_pct, 2, true)}</td>
                  <td className="py-1.5 pr-3 text-right text-slate-400">{fmtPctPts(r.market_pct, 2, true)}</td>
                  <td className="py-1.5 text-right">{alphaCell(r)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {months.length > 0 && (
          <div className="mt-4 overflow-x-auto">
            <div className="mb-1 text-xs uppercase tracking-wide text-slate-500">Alpha by month</div>
            <table className="text-sm tabular-nums">
              <thead>
                <tr className="text-xs text-slate-500">
                  <th className="py-1 pr-4 text-left font-medium" />
                  {months.map((m) => (
                    <th key={m} className="px-2 py-1 text-right font-medium">{m}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {['v2', 'v3', 'record'].map((rule) => (
                  <tr key={rule}>
                    <td className="py-1 pr-4 text-slate-400">{RULE_LABELS[rule].name}</td>
                    {months.map((m) => {
                      const cell = monthly(rule, m)
                      return (
                        <td
                          key={m}
                          className={`px-2 py-1 text-right ${cell && cell.n >= THIN_COHORT ? tone(cell.alpha_pct) : 'text-slate-600'}`}
                          title={cell ? `n=${cell.n}` : 'no signals'}
                        >
                          {cell ? fmtPctPts(cell.alpha_pct, 1, true) : '—'}
                        </td>
                      )
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <p className="mt-3 text-xs text-slate-500">
          Raw EV mixes two things: how the market moved, which no rule here predicts, and
          alpha — how the chosen assets did against a random same-class asset bought at the
          same instant. Judge a rule on alpha. v3 is a shadow: it is measured here but does
          not bold Telegram rows until it holds up out of sample. Benchmark exits come from
          the scan snapshots, which miss assets that later fall out of the liquidity filter;
          that understates bullish alpha by roughly 0.2pp. The research report
          (<code className="text-slate-400">python -m macd_searcher.research</code>) is the
          authoritative number. Months with fewer than {THIN_COHORT} signals are greyed.
        </p>
      </StateMsg>
    </Card>
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
            hint="Average win ÷ average loss. Above 1.0 means winners are bigger than losers — the v1 rule sat near 1.0 and won on frequency alone, which is how it decayed to zero EV."
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
          Measured over the {horizon} window from the fire price. The confident cohort
          both runs further in your favour and draws down less — an MFE/MAE ratio near{' '}
          <strong>2.0</strong> against roughly 0.8 for everything else. That asymmetry,
          not the win rate, is what the v2 rule selects for.
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
  // Diverging around a real line (0% EV / 50% win): with disjoint bands some cells
  // genuinely lose money, and that should read as red, not as a paler green.
  const t = Math.max(-1, Math.min(1, (v - mid) / span))
  const alpha = 0.12 + 0.55 * Math.abs(t)
  return t >= 0 ? `rgba(16, 185, 129, ${alpha})` : `rgba(244, 63, 94, ${alpha})`
}

// Below this a cell's win/EV is too noisy to read; it is shown dimmed, not hidden.
const THIN_CELL = 20

/** Signed edge with a true minus sign, fixed width so the row labels align. */
function fmtEdge(v: number): string {
  return `${v < 0 ? '−' : ''}${Math.abs(v).toFixed(2)}`
}

function sigBandLabel(lo: number | null, hi: number | null): string {
  if (lo == null && hi != null) return `< ${fmtEdge(hi)}`
  if (hi == null && lo != null) return `≥ ${fmtEdge(lo)}`
  return `${fmtEdge(lo ?? 0)} to ${fmtEdge(hi ?? 0)}`
}

/** Bullish signals by sig/ATR band x reduction band, with the rule boxed. */
export function SensitivityGrid({ horizon, metric }: { horizon: Horizon; metric: 'win' | 'ev' }) {
  const { data, isLoading, isError } = usePerfConfidenceSensitivity(horizon)
  const rows = data ?? []

  // Row order: deepest sig/ATR first (the open lower end sorts first). Columns:
  // lowest reduction first. Both are read off the data rather than hardcoded.
  const sigBands = Array.from(
    new Map(rows.map((r) => [r.sig_atr_lo ?? -Infinity, { lo: r.sig_atr_lo, hi: r.sig_atr_hi }])).entries(),
  )
    .sort(([a], [b]) => a - b)
    .map(([, band]) => band)
  const redBands = Array.from(
    new Map(rows.map((r) => [r.red_lo, { lo: r.red_lo, hi: r.red_hi }])).values(),
  ).sort((a, b) => a.lo - b.lo)
  const cell = (sigLo: number | null, redLo: number): PerfConfidenceSensitivity | undefined =>
    rows.find((r) => r.sig_atr_lo === sigLo && r.red_lo === redLo)

  // EVERY item below is placed explicitly, and that is load-bearing. CSS grid lays
  // out explicitly-positioned items first and then auto-flows the rest AROUND them,
  // so an explicitly placed outline among auto-placed cells shoves the cells out of
  // position (that was the original bug: a 3x3 hole with the data wrapped past it).
  // With everything explicit, grid items may overlap, and the outline sits on top.
  const HEADER_ROWS = 2 // axis title, then band labels
  const LABEL_COLS = 1
  const place = (row: number, col: number, rowSpan = 1, colSpan = 1) => ({
    gridRow: `${row + 1} / span ${rowSpan}`,
    gridColumn: `${col + 1} / span ${colSpan}`,
  })

  // The confident region as a rectangle of whole cells. The rule is
  // "sig/ATR below X and reduction below Y" over ascending bands, so its cells are
  // always a contiguous block anchored at the top-left — one box, never a scatter.
  const ruleRowCount = sigBands.filter((b) => rows.some((r) => r.in_rule && r.sig_atr_lo === b.lo)).length
  const ruleColCount = redBands.filter((b) => rows.some((r) => r.in_rule && r.red_lo === b.lo)).length

  const mid = metric === 'win' ? 50 : 0
  const span = metric === 'win' ? 20 : 5

  return (
    <Card
      title={metric === 'win' ? 'Win rate — signal line × reduction' : 'EV — signal line × reduction'}
      right={<span className="text-xs text-slate-500">bullish · {horizon}</span>}
    >
      <StateMsg loading={isLoading} error={isError} empty={rows.length === 0}>
        <div className="overflow-x-auto">
          <div
            className="grid gap-0.5"
            style={{
              gridTemplateColumns: `max-content repeat(${redBands.length}, minmax(3.25rem, 1fr))`,
              minWidth: '28rem',
            }}
          >
            {/* column-axis title */}
            <div
              className="pb-0.5 text-center text-[10px] font-medium uppercase tracking-wide text-slate-500"
              style={place(0, LABEL_COLS, 1, redBands.length)}
            >
              reduction from peak →
            </div>

            {/* row-axis title + band labels */}
            <div
              className="self-end pb-1 pr-3 text-[10px] font-medium uppercase tracking-wide text-slate-500"
              style={place(1, 0)}
            >
              signal ÷ ATR ↓
            </div>
            {redBands.map((b, j) => (
              <div
                key={b.lo}
                className="self-end pb-1 text-center text-xs tabular-nums text-slate-400"
                style={place(1, LABEL_COLS + j)}
              >
                {b.lo.toFixed(1)}–{b.hi.toFixed(1)}
              </div>
            ))}

            {sigBands.map((sb, i) => (
              <Fragment key={String(sb.lo)}>
                <div
                  className="flex items-center whitespace-nowrap pr-3 text-xs tabular-nums text-slate-300"
                  style={place(HEADER_ROWS + i, 0)}
                >
                  {sigBandLabel(sb.lo, sb.hi)}
                </div>
                {redBands.map((rb, j) => {
                  const c = cell(sb.lo, rb.lo)
                  const value = c ? (metric === 'win' ? c.win_pct : c.ev_pct) : null
                  const thin = (c?.n ?? 0) < THIN_CELL
                  return (
                    <div
                      key={rb.lo}
                      className={`flex h-12 flex-col items-center justify-center rounded tabular-nums ${
                        thin ? 'opacity-50' : ''
                      }`}
                      style={{
                        ...place(HEADER_ROWS + i, LABEL_COLS + j),
                        background: sensColor(value, mid, span),
                      }}
                      title={
                        c
                          ? `signal ÷ ATR ${sigBandLabel(sb.lo, sb.hi)}, reduction ${rb.lo}–${rb.hi} · n=${c.n}` +
                            (c.in_rule ? ' · inside the confidence rule' : '') +
                            (thin ? ' · thin, read with care' : '')
                          : 'no data'
                      }
                    >
                      {value == null ? (
                        <span className="text-slate-600">—</span>
                      ) : (
                        <>
                          <span className="text-[13px] font-medium leading-tight text-slate-50">
                            {fmtPctPts(value, metric === 'win' ? 1 : 2, metric === 'ev')}
                          </span>
                          <span className="text-[10px] leading-tight text-slate-300/70">n={c?.n}</span>
                        </>
                      )}
                    </div>
                  )
                })}
              </Fragment>
            ))}

            {/* One outline around the whole confident region. Neutral ink rather than
                a data colour: it annotates, it doesn't encode a value, so it must stay
                legible over both the green and the red cells. */}
            {ruleRowCount > 0 && ruleColCount > 0 && (
              <div
                aria-hidden
                className="pointer-events-none relative z-10 rounded-md border-2 border-slate-100"
                style={{
                  ...place(HEADER_ROWS, LABEL_COLS, ruleRowCount, ruleColCount),
                  margin: '-3px',
                }}
              />
            )}
          </div>
        </div>
        <p className="mt-3 text-xs text-slate-600">
          Bullish signals only, split into <strong>disjoint bands</strong> — each signal
          sits in exactly one cell, so a cell describes that slice alone. The{' '}
          <span className="font-medium text-slate-300">outlined box</span> is the confidence
          rule (signal ÷ ATR below −0.50, reduction 0.3–0.6); its cells add up to exactly the
          confident cohort. Read it for whether the edge concentrates inside the box and
          fades outside it. Faded cells have fewer than {THIN_CELL} signals. Picking the
          brightest cell on the same data the rule came from is how it gets overfit — that
          needs fresh data.
        </p>
      </StateMsg>
    </Card>
  )
}
