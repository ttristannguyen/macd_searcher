# RSI-bucket signal-quality analysis — heatmaps + curves

Working doc + progress tracker. Adds an **RSI analysis** to the Outcomes → Charts
view: win-rate (and EV) by **RSI bucket × horizon**, split by **direction**, as a
heatmap and line graphs. Tests whether RSI sharpens signal quality beyond the flat
30% reduction gate. Check items off as they land.

## Context / why

RSI(14) is now logged per signal (`fire_rsi_14`). We want to see whether a bearish
flatten at RSI 70 really is a stronger read than at 40 — and, honestly, whether
conditioning on RSI **beats trading every signal** (the baseline).

> **⚠️ Data dependency — read first.** Only signals fired *after* the RSI change
> carry `fire_rsi_14`, and outcomes mature ~14 days later — so this view is empty
> for ~2 weeks and thin longer, **unless** we run the historical-RSI **backfill**
> (Phase 0) to compute `fire_rsi_14` on existing *finalized* signals → instant
> analyzable data. Strongly recommended to pair the two.

## Decisions (locked in)

- One tidy endpoint `rsi_buckets` reusing `_base()` — carries every dimension
  (`horizon × direction × rsi_bucket`); the frontend pivots. No per-call fan-out.
- Buckets = requested `30-40/40-50/50-60/60-70` **plus tails `<30` and `≥70`** (the
  tails are where the thesis lives).
- Reuse the existing `heatColor` helper + `ReductionHeatmap` grid + charts patterns
  in `components/OutcomesCharts.tsx`.
- RSI buckets are **ordered** → line graphs use a **sequential** colour ramp
  (light→dark), not categorical hues (per the dataviz skill).
- A **Bullish | Bearish** toggle scopes the whole RSI section.

## Progress checklist

### Phase 0 — (Prerequisite) Historical RSI backfill — SKIPPED FOR NOW
- [ ] Deferred by user decision (2026-07-04): enough time has passed since the RSI
      change shipped to have ~7d-horizon data organically. Revisit if the 7d/14d
      buckets stay too thin. `update_outcomes.py --backfill-rsi` (+ `db` helper):
      per symbol with any NULL `fire_rsi_14`, re-fetch candles (reuse
      `_score_symbol` path), compute `rsi(close)` at each fire bar,
      `UPDATE signals SET fire_rsi_14=…`.

### Phase 1 — Backend endpoint ✅
- [x] `web/perf.py` `rsi_buckets(conn)` → rows `{horizon, direction, rsi_bucket, n,
      win_pct, avg_ret_pct}` over `_base()` where `fire_rsi_14 IS NOT NULL AND
      ret_Nd IS NOT NULL`; buckets `<30 / 30-40 / 40-50 / 50-60 / 60-70 / ≥70`.
- [x] `web/models.py` `PerfRsiBucket`; `web/app.py` `GET /api/perf/rsi-buckets`.
- [x] Tests: `tests/test_web_perf.py` `test_rsi_buckets_win_and_ev`,
      `test_rsi_buckets_excludes_signals_without_rsi` — 112 passed overall.

### Phase 2 — Frontend data layer ✅
- [x] `api/types.ts` `PerfRsiBucket`; `api/client.ts` `usePerfRsiBuckets()`.

### Phase 3 — Frontend charts (`components/OutcomesCharts.tsx`) ✅
- [x] **Bullish | Bearish** `Segmented` scoping the RSI section (`RsiAnalysis`).
- [x] **Win-rate heatmap** — RSI bucket × horizon, diverging @ 50%, `n` per cell. *(core)*
- [x] **Win-rate line graph** — x=horizon, line per RSI bucket (violet sequential
      ramp) + dashed **baseline** (n-weighted overall win-rate for that direction,
      derived client-side from the bucket rows — no extra endpoint). *(core + baseline)*
- [x] **EV heatmap** — same grid, diverging @ 0%. *(recommended)*
- [x] **RSI→win-rate trend** — x=RSI bucket, line per horizon (sky sequential ramp,
      the direct monotonic-thesis view). *(recommended)*
- [x] Low-`n` "accumulating" note (shared caption; heatmap cells show `n=` per cell).

### Phase 4 — Wire into page ✅
- [x] `pages/Outcomes.tsx`: already satisfied — `RsiAnalysis` is composed directly
      inside `OutcomesCharts()`, which the Charts toggle renders.

### Phase 5 — Docs
- [x] `NEXT_STEPS.md` no longer exists in this repo (removed in an earlier commit,
      already on `origin/main`) — nothing to append there. This tracker doc is the
      record; note the deferred backfill (Phase 0) here.

### Verification
- [x] `uv run pytest -q` green — 112 passed.
- [x] `npm --prefix frontend run build` clean.
- [ ] Live eyeball in the running dashboard (Outcomes → Charts → RSI section):
      heatmaps + lines populate, direction toggle + baseline work, small-n cells
      read as noisy. Not yet screenshot-verified in this session — data is thin
      until more post-RSI-change signals finalize (backfill was skipped).

## Out of scope
- 2D RSI × reduction cross-analysis (too sparse yet).
- Acting on the finding (RSI as a firing/ranking condition, detector tuning) —
  measurement only for now.

## Reference — reused code
- `_base()`, `summary()`/`thresholds()` (aggregate style) — `web/perf.py`.
- `heatColor`, `ReductionHeatmap`, `WinRateCurve`/`ReturnCurve` patterns,
  `HORIZONS` — `components/OutcomesCharts.tsx`.
- `usePerfThresholds`/`usePerfHorizonCurve` — `api/client.ts`.
- `_score_symbol` (candle fetch), `rsi` — `update_outcomes.py` / `indicators.py`.
