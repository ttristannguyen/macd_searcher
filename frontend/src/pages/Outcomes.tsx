import { useMemo, useState } from 'react'
import { ClassesContext, useByClass } from '../api/client'
import type { Horizon } from '../api/types'
import { ClassFilter } from '../components/ClassFilter'
import {
  ByClass,
  Excursions,
  HorizonChart,
  LeadTime,
  PerfSummary,
  ReadinessBanner,
  ReductionCounterfactual,
  Thresholds,
} from '../components/Outcomes'
import { OutcomesCharts } from '../components/OutcomesCharts'
import { Segmented } from '../components/ui'

const HORIZONS: { value: Horizon; label: string }[] = [
  { value: '1d', label: '1d' },
  { value: '3d', label: '3d' },
  { value: '7d', label: '7d' },
  { value: '14d', label: '14d' },
]

type ViewMode = 'tables' | 'charts'
const VIEWS: { value: ViewMode; label: string }[] = [
  { value: 'tables', label: 'Tables' },
  { value: 'charts', label: 'Charts' },
]

export function Outcomes() {
  const [horizon, setHorizon] = useState<Horizon>('7d')
  const [view, setView] = useState<ViewMode>('tables')

  // Data-driven class toggles: only classes that actually have signals appear.
  const { data: classRows } = useByClass()
  const present = useMemo(
    () =>
      (classRows ?? [])
        .map((r) => r.asset_class)
        .filter((c): c is string => !!c)
        .sort(),
    [classRows],
  )
  const [selected, setSelected] = useState<Set<string>>(new Set()) // empty = all
  const isAll = selected.size === 0 || (present.length > 0 && present.every((c) => selected.has(c)))
  const classesParam = isAll ? '' : [...selected].sort().join(',')

  return (
    <ClassesContext.Provider value={classesParam}>
      <div className="space-y-4">
        <ReadinessBanner />

        <div className="flex flex-wrap items-center justify-between gap-3">
          <p className="text-xs text-slate-500">
            A loose sanity gauge — a discretionary signalling aid, not a quantified edge.
          </p>
          <div className="flex flex-wrap items-center gap-3">
            <ClassFilter present={present} selected={selected} onChange={setSelected} />
            {view === 'tables' && (
              <div className="flex items-center gap-2">
                <span className="text-xs text-slate-500">horizon</span>
                <Segmented options={HORIZONS} value={horizon} onChange={setHorizon} />
              </div>
            )}
            <Segmented options={VIEWS} value={view} onChange={setView} />
          </div>
        </div>

        {view === 'charts' ? (
          <OutcomesCharts />
        ) : (
          <>
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

            <ReductionCounterfactual horizon={horizon} />
          </>
        )}
      </div>
    </ClassesContext.Provider>
  )
}
