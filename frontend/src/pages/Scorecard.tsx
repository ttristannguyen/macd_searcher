import { useState } from 'react'
import type { Horizon } from '../api/types'
import { ScorecardLegend, ScorecardTable } from '../components/Scorecard'
import { Segmented } from '../components/ui'

const HORIZONS: { value: Horizon; label: string }[] = [
  { value: '1d', label: '1d' },
  { value: '3d', label: '3d' },
  { value: '7d', label: '7d' },
  { value: '14d', label: '14d' },
]

export function Scorecard() {
  const [horizon, setHorizon] = useState<Horizon>('7d')

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-xs text-slate-500">
          Which tokens have a reliably positive expected value per signal — ranked, with confidence.
        </p>
        <div className="flex items-center gap-2">
          <span className="text-xs text-slate-500">horizon</span>
          <Segmented options={HORIZONS} value={horizon} onChange={setHorizon} />
        </div>
      </div>

      <ScorecardLegend />
      <ScorecardTable horizon={horizon} />
    </div>
  )
}