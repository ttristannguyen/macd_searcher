# Removing Stage 3 (zero-line proximity)

Working doc + progress tracker for making **histogram_flattening the sole
detector**. Check items off as they land. Companion to the approved plan.

## Context

Stage 3 (zero-line proximity) isn't performing, so we're dropping it. After this,
Stage 1 (histogram_flattening) is the only detector — the scanner detects/alerts
S1 only, config loses all S3 knobs, and the dashboard reads as an S1-only tool.

## Decisions (locked in)

- **Non-destructive to the DB.** `CREATE TABLE IF NOT EXISTS` never migrates an
  existing table, so dropping columns would only change *fresh* DBs and throw away
  history. Keep every column. `stage` stays (new rows always `histogram_flattening`);
  S3-only signal columns (`fire_macd_pct_of_price`, `fire_atr_multiple`) written NULL.
  `asset_snapshots` unchanged.
- **Dashboard is S1-only** (user choice): read queries filter to
  `stage = 'histogram_flattening'`; historical S3 stays in the DB but isn't shown.
- `_strictly_increasing` is used **only** by S3 (verified) → delete it.
  `_strictly_decreasing` is shared with S1 → keep.
- `update_outcomes.py` and `__main__.py` need **no change** (stage-agnostic;
  `bars_to_zero_cross` is a general outcome metric, not S3).

## Progress checklist

### Phase 1 — Detector (`src/macd_searcher/signals.py`)
- [x] Delete `_check_zero_line_proximity` and `_strictly_increasing`
- [x] `Signal`: drop `macd_pct_of_price`, `atr_multiple` fields (keep `stage`, S1 fields)
- [x] Remove `_STAGE_PRIORITY`; narrow `Stage` type to the single value
- [x] `_detect_stages_for_asset`: run only the histogram_flattening check
- [x] `evaluate_all`: strip the rank-mode global filter; simplify to S1-only; fix log line
- [x] Leave `compute_asset_metrics` / `AssetMetrics` / `compute_all_metrics` unchanged

### Phase 2 — Config (`config.py` + `config.yaml`)
- [x] `config.py`: remove S3 fields from `SignalConfig` + the `SignalMode` Literal; update docstring
- [x] `config.yaml`: delete the Stage-3 block + comments; fix the `candles.use_forming_candle` comment

### Phase 3 — DB writes (`src/macd_searcher/db.py`)
- [x] `insert_signals`: write `None` for `fire_macd_pct_of_price` / `fire_atr_multiple`
- [x] Leave `SCHEMA_SQL` untouched

### Phase 4 — Alerts (`src/macd_searcher/notify.py`)
- [x] Remove `_fmt_stage3_row`, the `zero_line_proximity` label, S3 branch of `_strength_key`
- [x] Simplify `format_message` to single-stage (no stage loop, no `cfg.signal.mode`)

### Phase 5 — Read API (`web/perf.py`, `web/queries.py`, `web/models.py`, `web/app.py`)
- [x] perf.py `_base()`: add `AND stage = 'histogram_flattening'`
- [x] perf.py `thresholds()`: drop the proximity branch + `ThresholdKind` (reduction-only)
- [x] queries.py: filter `recent_signals` + `by_stage_direction` to S1; drop
      `fire_macd_pct_of_price` from `recent_signals` SELECT; delete `proximity_headroom`
- [x] models.py: delete `ProximityHeadroom`; drop `fire_macd_pct_of_price` from `SignalRow`
- [x] app.py: remove `/api/stats/proximity-headroom`; drop `kind` from `/api/perf/thresholds`

### Phase 6 — Frontend (`frontend/src/**`)
- [x] Delete `components/Headroom.tsx`; remove `useProximityHeadroom` + `ProximityHeadroom` type;
      remove its slot in `pages/Dashboard.tsx`
- [x] `SignalsFeed.tsx`: remove stage-filter Segmented + S3 branch/`fire_macd_pct_of_price` in `keyMetric`
- [x] `Outcomes.tsx` `Thresholds`: remove proximity/reduction toggle; `usePerfThresholds` drops `kind`
- [x] `lib/format.ts`: drop `zero_line_proximity` branches in `stageLabel`/`stageShort`
- [x] `types.ts`: remove `ProximityHeadroom`, `ThresholdKind`, `SignalRow.fire_macd_pct_of_price`

### Phase 7 — Tests (delete S3 cases, reseed S1)
- [x] `test_signals.py`: delete `test_stage3_*`, rank-mode, disabled-S3 cases + dead imports; fix `evaluate_all` tests
- [x] `test_web_perf.py`: reseed `_seed` to `histogram_flattening`; fix stage keys; drop proximity assertion
- [x] `test_notify.py`: drop S3-formatting cases
- [x] `test_db.py`: `insert_signals` writes NULL S3 fields
- [x] `test_web.py`: remove proximity-headroom + S3 by-stage-direction expectations
- [x] `test_outcomes.py`: verify no `zero_line` seed; `scripts/smoke_signals.py`: drop `mode`/S3 refs

### Phase 8 — Docs
- [x] `docs/schema.md` (S3 columns legacy/NULL for new rows), `README.md`, `docs/queries.sql`
      (mark proximity SQL legacy), brief notes in `PLAN.md` / `FRONTEND_PLAN.md` /
      `NEXT_STEPS.md` / `docs/research.md`

### Verification
- [x] `uv run pytest -q` green
- [x] `npm --prefix frontend run build` clean
- [x] `python -m macd_searcher --dry-run --no-db` → S1-only message, no `cfg.signal.mode` error
- [x] API: `/api/perf/summary` + `/api/perf/thresholds` S1-only; `/api/stats/proximity-headroom` → 404
