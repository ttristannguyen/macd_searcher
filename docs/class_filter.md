# Outcomes tab — asset-class filter

Working doc + plan + progress tracker. Adds a **multi-select asset-class filter**
to the top of the Outcomes tab. Independent toggles (any combination); every
signal/outcome panel on the tab re-filters to the selected classes.

## Context / scope (decided)

- **Outcomes tab only** (Tables + Charts). Not the Dashboard or Scorecard tabs.
- **Data-driven toggles**: the class chips are built from the classes *actually
  present* in the data (via the existing `/api/stats/by-class`), so `fx` shows up
  only if there's fx data — directly honouring "if we don't use it, don't include
  it," and future-proof for any class. (`classify_asset` →
  crypto/equity/commodity/fx/index; `fx` = xyz DEX FX pairs like `xyz:EUR`.)
- **Default = all present classes selected** (current behaviour). Deselecting all
  = treat as "all" (never show an empty page).
- Per-*run* panels (health/runs/notify) have no asset class and are on other tabs
  anyway — out of scope.

## Design

**Filter transport:** an optional `classes` query param (comma-separated, e.g.
`?classes=crypto,equity`) on every Outcomes perf endpoint. Absent/empty = no filter
(all classes). Routes split + whitelist against the known set; pass a `list[str]`
(or `None`) into the perf functions.

**Backend chokepoint:** `_base()` already LEFT JOINs `asset_snapshots` for
`asset_class`, so almost everything funnels through one place.

## Backend changes (`web/perf.py`, `web/app.py`)
- `_base(classes=None)` — when `classes` is given, add `AND a.asset_class IN (?,…)`
  to the `perf` CTE and prepend the class params (so order stays
  `[cutoff, *classes, …caller params]`). Returns the extended params as today.
- Thread a `classes` arg through every `_base`-backed function and its route:
  `summary`, `by_horizon`, `horizon_curve`, `lead_time`, `by_class`, `thresholds`,
  `distribution`, `rsi_buckets` (and `by_symbol_scorecard` for free — Scorecard tab
  just won't pass it).
- Two that don't use `_base`:
  - `readiness()` — add the class filter (join `asset_snapshots` for `asset_class`),
    so the readiness banner matches the filtered tab.
  - `reduction_counterfactual()` — already selects from `asset_snapshots` (has
    `asset_class`); add `AND asset_class IN (…)`.
- Route param pattern: `classes: str | None = None` → `_split_classes(classes)`
  helper (comma-split, strip, keep only known classes, `None` if empty).

## Frontend changes (`frontend/src/**`)
- **`ClassFilter` control** (new, in `components/ui.tsx` or `Outcomes` page): fetches
  the present classes via `useByClass()` (`/api/stats/by-class`), renders a toggle
  chip per class (reuse `ASSET_CLASS_COLOR` for the chip colour + a count), and
  emits the selected `Set<string>`. "All / None" affordance optional.
- **Page state** in `pages/Outcomes.tsx`: `selectedClasses` state next to `horizon`;
  render `<ClassFilter>` beside the horizon selector; pass a stable
  `classesParam = [...selected].sort().join(',')` (or `''` = all) down.
- **Thread `classes` through the Outcomes hooks** (`api/client.ts`): add a `classes`
  arg to each, append `&classes=…` to the URL when non-empty, and include it in the
  `queryKey`. Hooks touched: `usePerfReadiness`, `usePerfSummary`, `usePerfByHorizon`,
  `usePerfHorizonCurve`, `usePerfLeadTime`, `usePerfDistribution`, `usePerfByClass`,
  `usePerfThresholds`, `usePerfReductionCounterfactual`, `usePerfRsiBuckets`.
- Each Outcomes component takes the `classes` prop (or reads a small context) and
  passes it to its hook. (A tiny React context for `classes` would avoid prop-drilling
  through ~12 components — decide during build; prop is fine too.)

## Progress checklist

### Phase 1 — Backend
- [x] `_base(classes)` + `_split_classes` helper + validated `classes` param.
- [x] Thread through all `_base`-backed perf fns + routes.
- [x] `readiness` + `reduction_counterfactual` class filters.
- [x] `tests/test_web_perf.py`: seed mixed-class signals; assert each endpoint
      honours `?classes=…` (single, combo, all, unknown-ignored).

### Phase 2 — Frontend
- [x] `ClassFilter` component (data-driven from `useByClass`).
- [x] `classes` threaded through the ~10 Outcomes hooks (queryKey + URL).
- [x] `pages/Outcomes.tsx`: state + control + pass-down (context or props).

### Phase 3 — Docs
- [~] Skipped a schema/README note — the filter is a UI/query concern, no schema
      change; this tracker doc is the record.

### Verification
- [x] `uv run pytest -q` green — 115 passed (+3 class-filter tests).
- [x] `npm --prefix frontend run build` clean.
- [ ] Live eyeball (do in the running dashboard): toggle classes on Outcomes →
      every panel (summary, by-class, thresholds, counterfactual, lead-time,
      excursions, all charts + RSI/reduction heatmaps) re-queries and reflects the
      selection; deselect-all shows all. Not screenshot-verified here.

## Out of scope
- Dashboard tab + Scorecard tab filtering (this pass is Outcomes only).
- Run-level panels (no asset class).

## Reference — reused code
- `_base()` (the class-join chokepoint), all perf fns — `web/perf.py`.
- `by_asset_class` / `/api/stats/by-class`, `useByClass` — `web/queries.py` / `api/client.ts`.
- `ASSET_CLASS_COLOR`, `Segmented`/`Badge` — `lib/format.ts` / `components/ui.tsx`.
