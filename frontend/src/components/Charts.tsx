import type { ReactNode } from 'react'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import {
  useByClass,
  useByStageDirection,
  useNotifyStatus,
  useRunsPerDay,
  useSignalsPerDay,
} from '../api/client'
import { ASSET_CLASS_COLOR, stageShort } from '../lib/format'
import { Card, StateMsg } from './ui'

const AXIS = '#64748b'
const GRID = '#1e293b'
const BULL = '#34d399'
const BEAR = '#fb7185'
const BAR = '#38bdf8'

const HEX: Record<string, string> = {
  blue: '#38bdf8',
  purple: '#a78bfa',
  amber: '#fbbf24',
  green: '#34d399',
  slate: '#94a3b8',
  red: '#fb7185',
}

const tooltipStyle = {
  background: '#0f172a',
  border: '1px solid #1e293b',
  borderRadius: 8,
  color: '#e2e8f0',
  fontSize: 12,
}

const NOTIFY_HEX: Record<string, string> = {
  sent: '#34d399',
  dry_run: '#38bdf8',
  quiet_hours: '#94a3b8',
  empty_suppressed: '#64748b',
  no_creds: '#fbbf24',
  failed: '#fb7185',
}

function ChartBox({ children }: { children: ReactNode }) {
  return <div style={{ height: 220 }}>{children}</div>
}

export function StageDirectionChart() {
  const { data, isLoading, isError } = useByStageDirection()
  const byStage: Record<string, { stage: string; bullish: number; bearish: number }> = {}
  for (const r of data ?? []) {
    const key = r.stage
    byStage[key] ??= { stage: stageShort(r.stage), bullish: 0, bearish: 0 }
    if (r.direction === 'bullish') byStage[key].bullish = r.n
    else byStage[key].bearish = r.n
  }
  const rows = Object.values(byStage)

  return (
    <Card title="Signals by stage & direction">
      <StateMsg loading={isLoading} error={isError} empty={rows.length === 0}>
        <ChartBox>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={rows}>
              <CartesianGrid stroke={GRID} vertical={false} />
              <XAxis dataKey="stage" stroke={AXIS} fontSize={12} />
              <YAxis stroke={AXIS} fontSize={12} allowDecimals={false} />
              <Tooltip contentStyle={tooltipStyle} cursor={{ fill: '#1e293b55' }} />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Bar dataKey="bullish" name="bullish" fill={BULL} radius={[3, 3, 0, 0]} />
              <Bar dataKey="bearish" name="bearish" fill={BEAR} radius={[3, 3, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </ChartBox>
      </StateMsg>
    </Card>
  )
}

export function ByClassChart() {
  const { data, isLoading, isError } = useByClass()
  const rows = (data ?? []).map((r) => ({
    label: r.asset_class ?? 'unknown',
    n: r.n,
    color: HEX[ASSET_CLASS_COLOR[r.asset_class ?? ''] ?? 'slate'],
  }))

  return (
    <Card title="Signals by asset class">
      <StateMsg loading={isLoading} error={isError} empty={rows.length === 0}>
        <ChartBox>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={rows} layout="vertical" margin={{ left: 16 }}>
              <CartesianGrid stroke={GRID} horizontal={false} />
              <XAxis type="number" stroke={AXIS} fontSize={12} allowDecimals={false} />
              <YAxis type="category" dataKey="label" stroke={AXIS} fontSize={12} width={80} />
              <Tooltip contentStyle={tooltipStyle} cursor={{ fill: '#1e293b55' }} />
              <Bar dataKey="n" name="signals" radius={[0, 3, 3, 0]}>
                {rows.map((r, i) => (
                  <Cell key={i} fill={r.color} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </ChartBox>
      </StateMsg>
    </Card>
  )
}

export function NotifyStatusChart() {
  const { data, isLoading, isError } = useNotifyStatus()
  const rows = (data ?? []).map((r) => ({
    name: r.notify_status ?? 'unknown',
    value: r.n,
  }))

  return (
    <Card title="Dispatch status">
      <StateMsg loading={isLoading} error={isError} empty={rows.length === 0}>
        <ChartBox>
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie data={rows} dataKey="value" nameKey="name" innerRadius={45} outerRadius={75} paddingAngle={2}>
                {rows.map((r, i) => (
                  <Cell key={i} fill={NOTIFY_HEX[r.name] ?? '#64748b'} />
                ))}
              </Pie>
              <Tooltip contentStyle={tooltipStyle} />
              <Legend wrapperStyle={{ fontSize: 12 }} />
            </PieChart>
          </ResponsiveContainer>
        </ChartBox>
      </StateMsg>
    </Card>
  )
}

export function SignalsPerDayChart() {
  const { data, isLoading, isError } = useSignalsPerDay(14)
  const rows = [...(data ?? [])]
    .reverse()
    .map((r) => ({ day: r.day.slice(5), signals: r.signals ?? 0 }))

  return (
    <Card title="Signals per day">
      <StateMsg loading={isLoading} error={isError} empty={rows.length === 0}>
        <ChartBox>
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={rows}>
              <CartesianGrid stroke={GRID} vertical={false} />
              <XAxis dataKey="day" stroke={AXIS} fontSize={12} />
              <YAxis stroke={AXIS} fontSize={12} allowDecimals={false} />
              <Tooltip contentStyle={tooltipStyle} />
              <Line type="monotone" dataKey="signals" stroke={BAR} strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </ChartBox>
      </StateMsg>
    </Card>
  )
}

export function RunsPerDayChart() {
  const { data, isLoading, isError } = useRunsPerDay(14)
  const rows = [...(data ?? [])]
    .reverse()
    .map((r) => ({ day: r.day.slice(5), runs: r.runs ?? 0 }))

  return (
    <Card title="Runs per day" right={<span className="text-xs text-slate-600">target: 6/day</span>}>
      <StateMsg loading={isLoading} error={isError} empty={rows.length === 0}>
        <ChartBox>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={rows}>
              <CartesianGrid stroke={GRID} vertical={false} />
              <XAxis dataKey="day" stroke={AXIS} fontSize={12} />
              <YAxis stroke={AXIS} fontSize={12} allowDecimals={false} />
              <Tooltip contentStyle={tooltipStyle} cursor={{ fill: '#1e293b55' }} />
              <Bar dataKey="runs" fill={BAR} radius={[3, 3, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </ChartBox>
      </StateMsg>
    </Card>
  )
}
