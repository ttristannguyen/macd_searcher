import type { ReactNode } from 'react'

export function Card({
  title,
  right,
  children,
  className = '',
}: {
  title?: string
  right?: ReactNode
  children: ReactNode
  className?: string
}) {
  return (
    <div className={`rounded-xl border border-slate-800 bg-slate-900/60 p-4 ${className}`}>
      {(title || right) && (
        <div className="mb-3 flex items-center justify-between">
          {title && <h2 className="text-sm font-medium capitalize text-slate-400">{title}</h2>}
          {right}
        </div>
      )}
      {children}
    </div>
  )
}

const BADGE_COLORS: Record<string, string> = {
  slate: 'bg-slate-700/40 text-slate-300',
  green: 'bg-emerald-500/15 text-emerald-400',
  red: 'bg-rose-500/15 text-rose-400',
  blue: 'bg-sky-500/15 text-sky-400',
  amber: 'bg-amber-500/15 text-amber-400',
  purple: 'bg-violet-500/15 text-violet-400',
}

export function Badge({ children, color = 'slate' }: { children: ReactNode; color?: string }) {
  return (
    <span className={`inline-block rounded px-1.5 py-0.5 text-xs font-medium capitalize ${BADGE_COLORS[color] ?? BADGE_COLORS.slate}`}>
      {children}
    </span>
  )
}

/** Small segmented button group for filters. */
export function Segmented<T extends string>({
  options,
  value,
  onChange,
}: {
  options: { value: T; label: string }[]
  value: T
  onChange: (v: T) => void
}) {
  return (
    <div className="inline-flex rounded-lg border border-slate-800 bg-slate-950/40 p-0.5">
      {options.map((o) => (
        <button
          key={o.value}
          onClick={() => onChange(o.value)}
          className={`rounded-md px-2.5 py-1 text-xs font-medium transition ${
            value === o.value ? 'bg-slate-700 text-slate-100' : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          {o.label}
        </button>
      ))}
    </div>
  )
}

export function Metric({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="min-w-0">
      <div className="text-xs uppercase tracking-wide text-slate-500">{label}</div>
      <div className="truncate text-lg font-semibold text-slate-100">{value}</div>
    </div>
  )
}

/** Tailwind text colour by sign of `n` relative to `mid` (e.g. returns vs 0,
 *  win% vs 50): emerald above, rose below, slate at the line. */
export function tone(n: number | null | undefined, mid = 0): string {
  if (n == null) return 'text-slate-500'
  if (n > mid) return 'text-emerald-400'
  if (n < mid) return 'text-rose-400'
  return 'text-slate-300'
}

/** Loading / empty / error placeholder for chart and table bodies. */
export function StateMsg({
  loading,
  error,
  empty,
  children,
}: {
  loading?: boolean
  error?: boolean
  empty?: boolean
  children: ReactNode
}) {
  if (loading) return <div className="py-8 text-center text-sm text-slate-500">Loading…</div>
  if (error) return <div className="py-8 text-center text-sm text-rose-400">Failed to load</div>
  if (empty) return <div className="py-8 text-center text-sm text-slate-500">No data yet</div>
  return <>{children}</>
}
