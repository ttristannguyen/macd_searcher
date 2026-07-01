import { useState } from 'react'
import type { Horizon } from '../api/types'
import {
  ByClass,
  Excursions,
  HorizonChart,
  LeadTime,
  PerfSummary,
  ReadinessBanner,
  Thresholds,
} from '../components/Outcomes'
import { Segmented } from '../components/ui'

const HORIZONS: { value: Horizon; label: string }[] = [
  { value: '1d', label: '1d' },
  { value: '3d', label: '3d' },
  { value: '7d', label: '7d' },
  { value: '14d', label: '14d' },
]

export function Outcomes() {
  const [horizon, setHorizon] = useState<Horizon>('7d')

  return (
    <div className="space-y-4">
      <ReadinessBanner />

      <div className="flex items-center justify-between">
        <p className="text-xs text-slate-500">
          A loose sanity gauge — a discretionary signalling aid, not a quantified edge.
        </p>
        <div className="flex items-center gap-2">
          <span className="text-xs text-slate-500">horizon</span>
          <Segmented options={HORIZONS} value={horizon} onChange={setHorizon} />
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <PerfSummary horizon={horizon} />
        <HorizonChart />
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <LeadTime />
        <Excursions />
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <ByClass horizon={horizon} />
        <Thresholds horizon={horizon} />
      </div>
    </div>
  )
}
