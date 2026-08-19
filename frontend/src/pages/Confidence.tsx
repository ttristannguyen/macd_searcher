import { useMemo, useState } from 'react'
import { ClassesContext, useByClass } from '../api/client'
import type { Horizon } from '../api/types'
import { ClassFilter } from '../components/ClassFilter'
import {
  ConfidenceScorecard,
  ExcursionTiles,
  HorizonBreakdown,
  SensitivityGrid,
  StabilityChart,
} from '../components/Confidence'
import { Segmented } from '../components/ui'

const HORIZONS: { value: Horizon; label: string }[] = [
  { value: '1d', label: '1d' },
  { value: '3d', label: '3d' },
  { value: '7d', label: '7d' },
  { value: '14d', label: '14d' },
]

/** The "should I take this trade" view.
 *
 * Distinct from Outcomes, which explores whether a factor matters at all. Here the
 * rule is settled and the page reports on it: how big the edge is, whether it is
 * holding up month to month, and where to place a target and a stop.
 */
export function Confidence() {
  const [horizon, setHorizon] = useState<Horizon>('7d')

  // Data-driven class toggles, matching the Outcomes tab.
  const { data: classRows } = useByClass()
  const present = useMemo(
    () =>
      (classRows ?? [])
        .map((r) => r.asset_class)
        .filter((c): c is string => Boolean(c))
        .sort(),
    [classRows],
  )
  // Empty set = all classes; collapsed to the query-param string the hooks read.
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const isAll = selected.size === 0 || (present.length > 0 && present.every((c) => selected.has(c)))
  const classesParam = isAll ? '' : [...selected].sort().join(',')

  return (
    <ClassesContext.Provider value={classesParam}>
      <div className="space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-sm font-medium text-slate-300">High-confidence signals</h2>
            <p className="mt-0.5 text-xs text-slate-500">
              Bearish fires with a shallow reduction and an unremarkable peak for that
              token — the slice bolded in Telegram.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <ClassFilter present={present} selected={selected} onChange={setSelected} />
            <Segmented options={HORIZONS} value={horizon} onChange={setHorizon} />
          </div>
        </div>

        <ConfidenceScorecard horizon={horizon} />

        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <HorizonBreakdown horizon={horizon} />
          <ExcursionTiles horizon={horizon} />
        </div>

        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <StabilityChart horizon={horizon} metric="win" />
          <StabilityChart horizon={horizon} metric="ev" />
        </div>

        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <SensitivityGrid horizon={horizon} metric="win" />
          <SensitivityGrid horizon={horizon} metric="ev" />
        </div>

        <p className="text-xs text-slate-600">
          The rule is measurement-only: it marks alerts, it does not suppress them. Its
          thresholds live in <code className="text-slate-500">signals.py</code> and are
          derived rather than stored, so changing one re-labels all history here — see
          docs/confidence.md.
        </p>
      </div>
    </ClassesContext.Provider>
  )
}
