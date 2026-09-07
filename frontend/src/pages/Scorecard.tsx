import { useState } from 'react'
import { usePerfScorecard } from '../api/client'
import type { Horizon } from '../api/types'
import { AssetSignalsTable } from '../components/AssetSignalsTable'
import { ScorecardLegend, ScorecardTable } from '../components/Scorecard'
import { fmtPctPts } from '../lib/format'
import { Segmented, tone } from '../components/ui'

const HORIZONS: { value: Horizon; label: string }[] = [
  { value: '1d', label: '1d' },
  { value: '3d', label: '3d' },
  { value: '7d', label: '7d' },
  { value: '14d', label: '14d' },
]

/** The selected symbol's Scorecard figures, repeated above the detail table so the
 *  records stay anchored to the number they explain. Reads from the same cached
 *  query the table used, so selecting a row costs no extra request. */
function SelectedSummary({ symbol, horizon }: { symbol: string; horizon: Horizon }) {
  const { data } = usePerfScorecard(horizon, 3)
  const r = (data ?? []).find((x) => x.symbol === symbol)
  if (!r) return null
  return (
    <div className="flex flex-wrap items-center gap-4 rounded-lg border border-slate-800 bg-slate-950/40 px-3 py-2 text-xs">
      <span className="text-slate-500">Scorecard · {horizon}</span>
      <span className="text-slate-400">n={r.n}</span>
      <span className={tone(r.win_pct, 50)}>
        win {fmtPctPts(r.win_pct)}{' '}
        <span className="text-slate-600">
          [{r.win_lo.toFixed(0)}–{r.win_hi.toFixed(0)}]
        </span>
      </span>
      <span className={tone(r.ev_pct)}>
        EV {fmtPctPts(r.ev_pct, 2, true)}{' '}
        <span className="text-slate-600">
          [{r.ev_lo.toFixed(1)}, {r.ev_hi.toFixed(1)}]
        </span>
      </span>
      {r.sqn != null && <span className="text-slate-400">SQN {r.sqn.toFixed(2)}</span>}
    </div>
  )
}

export function Scorecard() {
  const [horizon, setHorizon] = useState<Horizon>('7d')
  // No router in this app (tabs are useState in App.tsx), so the drill-down is
  // page state. Cost: no deep-link. Noted in docs/scorecard_asset_detail.md.
  const [selected, setSelected] = useState<string | null>(null)

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        {selected ? (
          <button
            type="button"
            onClick={() => setSelected(null)}
            className="text-xs text-slate-400 underline-offset-2 hover:text-slate-200 hover:underline"
          >
            ← all assets
          </button>
        ) : (
          <p className="text-xs text-slate-500">
            Which tokens have a reliably positive expected value per signal — ranked, with
            confidence. Click a row to see the signals behind the number.
          </p>
        )}
        <div className="flex items-center gap-2">
          <span className="text-xs text-slate-500">horizon</span>
          <Segmented options={HORIZONS} value={horizon} onChange={setHorizon} />
        </div>
      </div>

      {selected ? (
        <>
          <SelectedSummary symbol={selected} horizon={horizon} />
          <AssetSignalsTable symbol={selected} horizon={horizon} />
        </>
      ) : (
        <>
          <ScorecardLegend />
          <ScorecardTable horizon={horizon} onSelect={setSelected} />
        </>
      )}
    </div>
  )
}
