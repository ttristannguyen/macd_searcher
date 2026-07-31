// Multi-select asset-class toggle for the Outcomes tab. `selected` is empty when
// "all" is showing; toggling builds an explicit subset. The parent turns this into
// the `classes` query param (empty = all) and provides it via ClassesContext.
export function ClassFilter({
  present,
  selected,
  onChange,
}: {
  present: string[]
  selected: Set<string>
  onChange: (next: Set<string>) => void
}) {
  if (present.length <= 1) return null // nothing meaningful to filter on

  const allOn = selected.size === 0
  const toggle = (cls: string) => {
    // Empty means "all", so start from the full set — the first click removes one.
    const base = allOn ? new Set(present) : new Set(selected)
    if (base.has(cls)) base.delete(cls)
    else base.add(cls)
    // Collapse "everything selected" back to the empty (= all) representation.
    onChange(present.every((c) => base.has(c)) ? new Set() : base)
  }

  return (
    <div className="flex flex-wrap items-center gap-1.5">
      <span className="text-xs text-slate-500">class</span>
      {present.map((cls) => {
        const on = allOn || selected.has(cls)
        return (
          <button
            key={cls}
            type="button"
            onClick={() => toggle(cls)}
            className={`rounded-md px-2 py-1 text-xs font-medium capitalize transition ${
              on ? 'bg-slate-700 text-slate-100' : 'text-slate-500 hover:text-slate-300'
            }`}
          >
            {cls}
          </button>
        )
      })}
      {!allOn && (
        <button
          type="button"
          onClick={() => onChange(new Set())}
          className="text-xs text-slate-500 underline hover:text-slate-300"
        >
          all
        </button>
      )}
    </div>
  )
}
