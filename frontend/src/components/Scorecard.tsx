import type { ReactNode } from 'react'
import { usePerfScorecard } from '../api/client'
import type { Horizon } from '../api/types'
import { ASSET_CLASS_COLOR, fmtPctPts } from '../lib/format'
import { Badge, Card, StateMsg, tone } from './ui'

// ---------- the ranked table ----------

export function ScorecardTable({ horizon, minN = 3 }: { horizon: Horizon; minN?: number }) {
  const { data, isLoading, isError } = usePerfScorecard(horizon, minN)
  const rows = data ?? []

  return (
    <Card
      title={`Per-symbol expectancy · ${horizon}`}
      right={<span className="text-xs text-slate-600">min {minN} signals · ranked by EV lower bound</span>}
    >
      <StateMsg loading={isLoading} error={isError} empty={rows.length === 0}>
        <div className="max-h-[34rem] overflow-y-auto">
          <table className="w-full text-sm">
            <thead className="sticky top-0 bg-slate-900/95">
              <tr className="border-b border-slate-800 text-left text-xs uppercase tracking-wide text-slate-500">
                <th className="py-1.5 pr-2 font-medium">Symbol</th>
                <th className="py-1.5 pr-2 font-medium">Class</th>
                <th className="py-1.5 pr-2 text-right font-medium">n</th>
                <th className="py-1.5 pr-2 text-right font-medium">Win % (95% CI)</th>
                <th className="py-1.5 text-right font-medium">EV % (95% CI)</th>
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
                  <td className="py-1.5 pr-2 text-right tabular-nums whitespace-nowrap">
                    <span className={tone(r.win_pct, 50)}>{fmtPctPts(r.win_pct)}</span>
                    <span className="ml-1 text-xs text-slate-600">
                      [{r.win_lo.toFixed(0)}–{r.win_hi.toFixed(0)}]
                    </span>
                  </td>
                  <td className="py-1.5 text-right tabular-nums whitespace-nowrap">
                    <span className={tone(r.ev_pct)}>{fmtPctPts(r.ev_pct, 1, true)}</span>
                    <span className="ml-1 text-xs text-slate-600">
                      [{r.ev_lo.toFixed(1)}, {r.ev_hi.toFixed(1)}]
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </StateMsg>
    </Card>
  )
}

// ---------- "how to read this" legend ----------

function Def({ term, children }: { term: string; children: ReactNode }) {
  return (
    <div>
      <dt className="text-sm font-medium text-slate-200">{term}</dt>
      <dd className="text-xs text-slate-400">{children}</dd>
    </div>
  )
}

export function ScorecardLegend() {
  return (
    <Card title="How to read this">
      <dl className="grid gap-3 sm:grid-cols-2">
        <Def term="n">
          Signals scored for this symbol — deduped to one per asset-day, and only
          since the Stage-1 detector fix.
        </Def>
        <Def term="Win % (95% CI)">
          Share of signals that resolved in the predicted direction (bullish up /
          bearish down), with the Wilson confidence interval. A <em>wide</em>
          bracket means too few signals to trust yet.
        </Def>
        <Def term="EV % (95% CI)">
          Expected value per signal — the mean direction-normalized return (a
          bullish +2% and a bearish −2% drop both count as +2%). The number you'd
          average over many trades, with its bootstrap interval.
        </Def>
        <Def term="Ranked by EV lower bound">
          Sorted by the <em>bottom</em> of the EV interval, not the headline — so a
          lucky 3-signal symbol can't outrank a proven one. Trust the lower bound.
        </Def>
      </dl>
      <p className="mt-3 text-xs text-amber-400/80">
        ⚠ Win-rate alone ≠ EV: 40% winners can beat 70% if the winners are bigger.
        Samples are small and from one market regime — a loose gauge, not a
        guarantee. Intervals tighten as more outcomes mature (~2 weeks per signal).
      </p>
    </Card>
  )
}