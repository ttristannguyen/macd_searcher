# Outcomes "Charts" view — win-rate/return curves + reduction heatmaps

Working doc + progress tracker. Adds a **Charts** mode to the Outcomes tab that
visualizes data we already collect — **no schema change, no backfill, no scoring
change**. Check items off as they land.

## Context

Goal is *visibility into strategy performance* (benchmark column shelved). The
Outcomes tables are good; this adds a chart view of the same data:

- **Win Rate & Return** — win-rate across horizons (chart) + return across horizons
  with avg / best / worst spread band (chart).
- **Reduction Buckets** — win-rate heatmap + EV heatmap, across horizons, diverging
  color (dark-red heavy loss → red → green → dark-green heavy win).

## Decisions (locked in)

- **Data reuse:** reduction heatmaps reuse the existing `thresholds(horizon)`
  endpoint, called once per horizon on the frontend (no backend change). Only the
  per-horizon win-rate / best-worst curve needs a new endpoint.
- **One new endpoint** `horizon_curve` reuses `_base()` + `stats.summarize`
  (Python aggregation, like `by_symbol_scorecard` / `distribution`). Overall
  strategy — not split by direction (easy to add later).
- **UI:** a `[Tables | Charts]` toggle on the Outcomes page (not a new top-level
  tab). Charts span all horizons, so the horizon selector is hidden in Charts mode.
- **Heatmap:** pure CSS grid (Tailwind + inline diverging color) — no new lib.

## Progress checklist

### Phase 1 — Backend endpoint ✅
- [x] `web/perf.py`: `horizon_curve(conn)` → per-horizon tidy rows
      `{horizon, n, win_pct, avg_ret_pct, median_pct, p25_pct, p75_pct, best_pct,
      worst_pct, std_pct}` over `_base()` `perf` where `ret_Nd IS NOT NULL`, via
      `summarize` + a win count.
- [x] `web/models.py`: `PerfHorizonPoint` model.
- [x] `web/app.py`: `GET /api/perf/horizon-curve` route (+ import).

### Phase 2 — Frontend data layer
- [x] `api/types.ts`: `PerfHorizonPoint`.
- [x] `api/client.ts`: `usePerfHorizonCurve()`. (Heatmaps reuse `usePerfThresholds(horizon)` ×4.)

### Phase 3 — Frontend components (`components/OutcomesCharts.tsx`, new file)
- [x] `WinRateCurve` — Recharts line of `win_pct` vs horizon + 50% `ReferenceLine`
      (reuse `HorizonChart`'s AXIS/GRID/tooltipStyle from `components/Outcomes.tsx`).
- [x] `ReturnCurve` — Recharts `ComposedChart`: `avg_ret_pct` line + best/worst
      `Area` band (+ optional p25/p75 band), 0% `ReferenceLine`.
- [x] `heatColor(value, mid)` helper — diverging rose→slate→emerald.
- [x] `ReductionWinHeatmap` + `ReductionEVHeatmap` — CSS grid, rows = reduction
      buckets, cols = horizons; merge the 4 `thresholds` results into a
      bucket×horizon matrix; blank cells where `n=0`.

### Phase 4 — Wire into the page
- [x] `pages/Outcomes.tsx`: `[Tables | Charts]` `Segmented`; Charts renders
      `<OutcomesCharts />` and hides the horizon selector; Tables unchanged.

### Phase 5 — Tests
- [x] `tests/test_web_perf.py`: `/api/perf/horizon-curve` — seed has
      `px_1d=px_3d=px_7d=px_14d`, so every horizon: `n=3`, `win_pct=66.7`,
      `avg_ret_pct=3.33`, `best_pct=10.0`, `worst_pct=-5.0`.

### Verification
- [x] `uv run pytest -q` green.
- [x] `npm --prefix frontend run build` clean.
- [ ] **Visual eyeball (do in the running dashboard):** Outcomes → toggle Charts —
      confirm the win-rate curve (50% line), return curve with the avg line + spread
      band, and the two reduction heatmaps render without label/geometry issues; then
      toggle back to Tables and confirm the existing panels are unchanged. (Build +
      tests pass; the live render hasn't been screenshot-verified here.)

## Reference — reused code
- `_base()`, `summary()` (aggregate style), `thresholds()` — `web/perf.py`.
- `stats.summarize` — `src/macd_searcher/stats.py`.
- `HorizonChart` (Recharts constants), `Segmented`, `tone` — `components/Outcomes.tsx` / `components/ui.tsx`.
- `usePerfThresholds`, `usePerfByHorizon` — `api/client.ts`.
