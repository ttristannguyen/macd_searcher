import { ByClassChart, NotifyStatusChart, RunsPerDayChart, SignalsPerDayChart, StageDirectionChart } from '../components/Charts'
import { HealthBanner } from '../components/HealthBanner'
import { Headroom } from '../components/Headroom'
import { RunsTable } from '../components/RunsTable'
import { SignalsFeed } from '../components/SignalsFeed'
import { TopSymbols } from '../components/TopSymbols'

export function Dashboard() {
  return (
    <div className="space-y-4">
      <HealthBanner />

      {/* Composition: three charts across */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <StageDirectionChart />
        <ByClassChart />
        <NotifyStatusChart />
      </div>

      {/* Cadence + latest signals */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <div className="space-y-4 lg:col-span-2">
          <SignalsPerDayChart />
          <RunsPerDayChart />
        </div>
        <RunsTable />
      </div>

      <SignalsFeed />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <Headroom />
        </div>
        <TopSymbols />
      </div>
    </div>
  )
}
