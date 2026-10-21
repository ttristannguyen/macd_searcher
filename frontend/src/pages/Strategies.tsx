import { useState, type ReactNode } from 'react'
import { useStrategySignals } from '../api/client'
import type { StrategyRule } from '../api/types'
import { StrategyTable, type Side } from '../components/StrategySignals'
import { Segmented } from '../components/ui'

type Lookback = '1' | '7' | '14'

const LOOKBACKS: { value: Lookback; label: string }[] = [
  { value: '1', label: '24h' },
  { value: '7', label: '7d' },
  { value: '14', label: '14d' },
]

// Per-trade alpha figures are the 2023-26 history rebuild as reported in
// docs/profit_strategies.md (2026-10-19). Thresholds are applied server-side
// (web/queries.STRATEGY_RULES); the numbers here are description only.
const LEGS: Record<StrategyRule, { title: string; side: Side; blurb: string }> = {
  v2_bullish: {
    title: 'v2 bullish',
    side: 'long',
    blurb:
      'Bullish, signal line ≥ 0.5 ATR below zero and reduction < 60% — the live marker bolded in Telegram. ' +
      'Its edge was market move, not selection: −0.56% alpha (2026-10-14).',
  },
  v3_bullish: {
    title: 'v3 bullish',
    side: 'long',
    blurb:
      'Bullish, peak_pct ≤ 50 and reduction < 60%. The one pre-registered rule: +0.58% 7d alpha per trade, ' +
      'every year 2023–26 — but as a 7-day book, costs take all of it.',
  },
  bull_low_peak: {
    title: 'Bullish peak_pct ≤ 25',
    side: 'long',
    blurb:
      "v3's strongest quarter (most also appear under v3). +1.92% 14d alpha per trade on history, exploratory.",
  },
  bear_pullback: {
    title: 'Bearish pullback (peak_pct ≥ 50)',
    side: 'long',
    blurb:
      'A bearish fire after a strong move — a pullback in a leader — taken LONG, not short. ' +
      '+1.16 / +1.43 / +2.34% alpha across three periods.',
  },
  bear_low_peak: {
    title: 'Bearish peak_pct ≤ 25',
    side: 'short',
    blurb: 'A feeble rally in a weak coin. +1.04% 14d alpha per trade as a short, exploratory.',
  },
}

/** Recent fires split by the strategy legs in docs/profit_strategies.md. */
export function Strategies() {
  const [lookback, setLookback] = useState<Lookback>('7')
  const { data, isLoading, isError } = useStrategySignals(Number(lookback))

  const table = (rule: StrategyRule) => (
    <StrategyTable
      {...LEGS[rule]}
      rows={data?.find((s) => s.rule === rule)?.rows ?? []}
      loading={isLoading}
      error={isError}
    />
  )

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-sm font-medium text-slate-300">Recent fires by strategy</h2>
          <p className="mt-0.5 text-xs text-slate-500">
            One row per symbol: its latest qualifying fire in the window, with how often it fired.
            Good/bad fire cuts were found on the history they're measured on — read them as upper bounds.
          </p>
        </div>
        <Segmented options={LOOKBACKS} value={lookback} onChange={setLookback} />
      </div>

      <Group title="v2 bullish">{table('v2_bullish')}</Group>

      <Group title="v3 bullish">{table('v3_bullish')}</Group>

      <Group title="Good fires" note="B3's long leg · 14-day hold in the backtest · crypto only">
        {table('bull_low_peak')}
        {table('bear_pullback')}
      </Group>

      <Group title="Bad fires" note="B3's short leg · 14-day hold in the backtest · crypto only">
        {table('bear_low_peak')}
      </Group>
    </div>
  )
}

function Group({ title, note, children }: { title: string; note?: string; children: ReactNode }) {
  return (
    <section className="space-y-3">
      <div className="flex items-baseline gap-3 border-b border-slate-800 pb-1">
        <h3 className="text-sm font-semibold text-slate-200">{title}</h3>
        {note && <span className="text-xs text-slate-500">{note}</span>}
      </div>
      {children}
    </section>
  )
}
