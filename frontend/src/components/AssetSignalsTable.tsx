import { useMemo, useState } from 'react'
import { useAssetSignals } from '../api/client'
import type { AssetSignalRow, Horizon } from '../api/types'
import { ASSET_CLASS_COLOR, fmtNum, fmtPct, fmtPctPts, fmtPrice } from '../lib/format'
import { Badge, Card, StateMsg, tone } from './ui'

// Finalization waits horizon_days + 1 so the horizon bar has closed — see the
// comment in update_outcomes.score_signal. 15 is that number for the 14d horizon.
const FINALIZE_DAYS = 15

type SortKey = keyof AssetSignalRow
type Dir = 'asc' | 'desc'

/** Returns are fractions on the wire (0.10 = +10%); show them signed as percent. */
const ret = (v: number | null) => fmtPctPts(v == null ? null : v * 100, 1, true)

function daysSince(iso: string): number {
  return Math.floor((Date.now() - new Date(iso).getTime()) / 86_400_000)
}

/** Clickable column header. Nulls always sort last, in either direction — a
 *  column of em-dashes at the top is never what you wanted. */
function Th({
  label,
  col,
  sort,
  onSort,
  align = 'right',
  title,
}: {
  label: string
  col: SortKey
  sort: { key: SortKey; dir: Dir }
  onSort: (k: SortKey) => void
  align?: 'left' | 'right'
  title?: string
}) {
  const active = sort.key === col
  return (
    <th
      className={`whitespace-nowrap py-1.5 pr-2 font-medium ${align === 'left' ? 'text-left' : 'text-right'}`}
      title={title}
    >
      <button
        type="button"
        onClick={() => onSort(col)}
        className={`transition hover:text-slate-300 ${active ? 'text-slate-300' : ''}`}
      >
        {label}
        {active && <span className="ml-0.5 text-[9px]">{sort.dir === 'asc' ? '▲' : '▼'}</span>}
      </button>
    </th>
  )
}

export function AssetSignalsTable({ symbol, horizon }: { symbol: string; horizon: Horizon }) {
  const { data, isLoading, isError } = useAssetSignals(symbol, horizon)
  const [sort, setSort] = useState<{ key: SortKey; dir: Dir }>({ key: 'fired_at', dir: 'desc' })

  const onSort = (key: SortKey) =>
    setSort((s) => (s.key === key ? { key, dir: s.dir === 'asc' ? 'desc' : 'asc' } : { key, dir: 'desc' }))

  const rows = useMemo(() => {
    const arr = [...(data?.rows ?? [])]
    arr.sort((a, b) => {
      const x = a[sort.key]
      const y = b[sort.key]
      if (x == null && y == null) return 0
      if (x == null) return 1 // nulls last regardless of direction
      if (y == null) return -1
      const cmp =
        typeof x === 'string'
          ? x.localeCompare(y as string)
          : Number(x) - Number(y) // covers numbers and the two booleans
      return sort.dir === 'asc' ? cmp : -cmp
    })
    return arr
  }, [data, sort])

  const counts = data
    ? [
        `${data.measured} measured`,
        data.pending ? `${data.pending} pending` : null,
        data.same_day_excluded ? `${data.same_day_excluded} same-day repeats excluded` : null,
      ]
        .filter(Boolean)
        .join(' · ')
    : ''

  return (
    <Card
      title={`${symbol} · every measured signal`}
      right={
        <div className="flex items-center gap-2">
          {data?.asset_class && (
            <Badge color={ASSET_CLASS_COLOR[data.asset_class] ?? 'slate'}>{data.asset_class}</Badge>
          )}
          <span className="text-xs text-slate-600">{counts}</span>
        </div>
      }
    >
      <StateMsg loading={isLoading} error={isError} empty={rows.length === 0}>
        <div className="max-h-[36rem] overflow-auto">
          <table className="w-full text-sm">
            <thead className="sticky top-0 bg-slate-900/95 backdrop-blur">
              <tr className="border-b border-slate-800 text-xs uppercase tracking-wide text-slate-500">
                <Th label="Fired" col="fired_at" sort={sort} onSort={onSort} align="left" />
                <Th label="Dir" col="direction" sort={sort} onSort={onSort} align="left" />
                <Th label="Px" col="fire_close" sort={sort} onSort={onSort} />
                <Th label="↓Peak" col="fire_reduction_from_peak" sort={sort} onSort={onSort}
                    title="Reduction from the histogram peak — the firing metric" />
                <Th label="Ratio" col="fire_hist_peak_ratio" sort={sort} onSort={onSort}
                    title="This excursion's peak ÷ median of the token's own prior same-sign tops" />
                <Th label="Pct" col="fire_hist_peak_pct" sort={sort} onSort={onSort}
                    title="Percentile of that peak among the token's own prior tops (low = modest)" />
                <Th label="n" col="fire_hist_top_n" sort={sort} onSort={onSort}
                    title="How many prior tops the ratio/percentile rest on" />
                <Th label="RSI" col="fire_rsi_14" sort={sort} onSort={onSort} />
                <Th label="Sig%" col="sig_pct_of_price" sort={sort} onSort={onSort}
                    title="MACD signal line at fire, as % of price" />
                <Th label="MACD" col="fire_macd" sort={sort} onSort={onSort} />
                <Th label="1d" col="ret_1d" sort={sort} onSort={onSort} />
                <Th label="3d" col="ret_3d" sort={sort} onSort={onSort} />
                <Th label="7d" col="ret_7d" sort={sort} onSort={onSort} />
                <Th label="14d" col="ret_14d" sort={sort} onSort={onSort} />
                <Th label="MFE" col="mfe" sort={sort} onSort={onSort}
                    title="Best excursion in the predicted direction within 14d" />
                <Th label="MAE" col="mae" sort={sort} onSort={onSort}
                    title="Worst excursion against the predicted direction within 14d" />
                <Th label="Cross" col="bars_to_zero_cross" sort={sort} onSort={onSort}
                    title="Bars until MACD crossed zero in the predicted direction" />
                <Th label="Status" col="finalized" sort={sort} onSort={onSort} align="left" />
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr
                  key={r.fired_at + r.direction}
                  className={`border-b border-slate-800/50 last:border-0 hover:bg-slate-800/30 ${
                    r.finalized ? '' : 'opacity-60'
                  }`}
                >
                  <td className="whitespace-nowrap py-1.5 pr-2 text-slate-400">{r.fired_at.slice(0, 10)}</td>
                  <td className="py-1.5 pr-2">
                    <Badge color={r.direction === 'bullish' ? 'green' : 'red'}>{r.direction}</Badge>
                    {r.confident && <span className="ml-1 text-[10px] text-emerald-400" title="high-confidence rule">★</span>}
                  </td>
                  <td className="py-1.5 pr-2 text-right tabular-nums text-slate-300">{fmtPrice(r.fire_close)}</td>
                  <td className="py-1.5 pr-2 text-right tabular-nums text-slate-400">
                    {r.fire_reduction_from_peak == null ? '—' : fmtPct(r.fire_reduction_from_peak, 0)}
                  </td>
                  <td className="py-1.5 pr-2 text-right tabular-nums text-slate-400">
                    {r.fire_hist_peak_ratio == null ? '—' : `${r.fire_hist_peak_ratio.toFixed(1)}×`}
                  </td>
                  <td className="py-1.5 pr-2 text-right tabular-nums text-slate-400">
                    {r.fire_hist_peak_pct == null ? '—' : `p${Math.round(r.fire_hist_peak_pct)}`}
                  </td>
                  <td className="py-1.5 pr-2 text-right tabular-nums text-slate-600">{r.fire_hist_top_n ?? '—'}</td>
                  <td className="py-1.5 pr-2 text-right tabular-nums text-slate-300">
                    {r.fire_rsi_14 == null ? '—' : Math.round(r.fire_rsi_14)}
                  </td>
                  <td className="py-1.5 pr-2 text-right tabular-nums text-slate-400">
                    {fmtPctPts(r.sig_pct_of_price, 1, true)}
                  </td>
                  <td className="py-1.5 pr-2 text-right tabular-nums text-slate-500">{fmtNum(r.fire_macd)}</td>
                  <td className={`py-1.5 pr-2 text-right tabular-nums ${tone(r.ret_1d)}`}>{ret(r.ret_1d)}</td>
                  <td className={`py-1.5 pr-2 text-right tabular-nums ${tone(r.ret_3d)}`}>{ret(r.ret_3d)}</td>
                  <td className={`py-1.5 pr-2 text-right tabular-nums ${tone(r.ret_7d)}`}>{ret(r.ret_7d)}</td>
                  <td className={`py-1.5 pr-2 text-right tabular-nums ${tone(r.ret_14d)}`}>{ret(r.ret_14d)}</td>
                  <td className="py-1.5 pr-2 text-right tabular-nums text-emerald-400/70">{ret(r.mfe)}</td>
                  <td className="py-1.5 pr-2 text-right tabular-nums text-rose-400/70">{ret(r.mae)}</td>
                  <td className="py-1.5 pr-2 text-right tabular-nums text-sky-400/70">
                    {r.bars_to_zero_cross ?? '—'}
                  </td>
                  <td className="whitespace-nowrap py-1.5 pr-2 text-xs text-slate-500">
                    {r.finalized ? 'final' : `pending ${Math.min(daysSince(r.fired_at), FINALIZE_DAYS)}/${FINALIZE_DAYS}d`}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="mt-2 text-xs text-slate-600">
          Same cohort the Scorecard counts: post-detector-fix, one signal per symbol-day (earliest
          kept). <span className="text-slate-400">Pending</span> rows are dimmed — their horizon bar
          hasn't closed, so a blank return is an unanswered question, not a flat result.
          Per-symbol edge does not persist across periods, so read this as <em>what happened</em>,
          not as what this token does.
        </p>
      </StateMsg>
    </Card>
  )
}
