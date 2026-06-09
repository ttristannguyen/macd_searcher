export function relativeTime(iso: string | null): string {
  if (!iso) return '—'
  const diffMs = Date.now() - new Date(iso).getTime()
  const s = Math.round(diffMs / 1000)
  if (s < 60) return `${s}s ago`
  const m = Math.round(s / 60)
  if (m < 60) return `${m}m ago`
  const h = Math.round(m / 60)
  if (h < 48) return `${h}h ago`
  return `${Math.round(h / 24)}d ago`
}

export function fmtPrice(n: number | null | undefined): string {
  if (n == null) return '—'
  if (n >= 1000) return '$' + n.toLocaleString(undefined, { maximumFractionDigits: 2 })
  if (n >= 1) return '$' + n.toFixed(4)
  return '$' + n.toFixed(6)
}

export function fmtPct(n: number | null | undefined, digits = 2): string {
  if (n == null) return '—'
  return (n * 100).toFixed(digits) + '%'
}

export function fmtNum(n: number | null | undefined, digits = 4): string {
  if (n == null) return '—'
  if (Math.abs(n) >= 1000) return n.toLocaleString(undefined, { maximumFractionDigits: 2 })
  return Number(n.toFixed(digits)).toString()
}

export function stageLabel(stage: string): string {
  if (stage === 'histogram_flattening') return 'Stage 1 · histogram'
  if (stage === 'zero_line_proximity') return 'Stage 3 · zero-line'
  return stage
}

export function stageShort(stage: string): string {
  if (stage === 'histogram_flattening') return 'S1 hist'
  if (stage === 'zero_line_proximity') return 'S3 zero'
  return stage
}

export const ASSET_CLASS_COLOR: Record<string, string> = {
  crypto: 'blue',
  equity: 'purple',
  commodity: 'amber',
  fx: 'green',
  index: 'slate',
}
