# Confidence signals — logging + a decision view

Working doc + plan + progress tracker. Takes `is_high_confidence` — today a
presentation detail that bolds a Telegram row — and makes it a first-class,
queryable dimension with a dashboard tab built to answer one question:

> **Should I take this trade, and what should I expect from it?**

The existing Outcomes tab is for *exploring* whether a factor matters. This is for
*acting* on the ones that already do.

## Context / why

The rule (`bearish` + `reduction < 0.6` + `peak percentile < 40` + `top_n >= 3`)
marks 11.4% of signals and measured 70.1% win / +2.65% EV at 7d, versus a 51.6% /
+0.02% baseline — clearing both bars in each regime half independently. See
[hist_peak_context.md](hist_peak_context.md) for the derivation.

Right now that fact lives only in a bolded line in Telegram. It can't be counted,
tracked, or checked for decay. If the rule quietly stops working we'd find out from
losing trades rather than from the dashboard.

## Decisions (locked in)

### Derive the flag in SQL — no column, no migration

Every input already sits on `signals`: `direction`, `fire_reduction_from_peak`,
`fire_hist_peak_pct`, `fire_hist_top_n`. So confidence is a `CASE` expression over
the existing `perf` CTE, exactly like the MACD signal line was
([macd_signal_analysis.md](macd_signal_analysis.md)). No `ALTER TABLE`, no capture
change, and it applies **retroactively to all backfilled history** — the dashboard
is populated the moment the endpoint ships.

The real payoff is retuning: when a threshold moves, derived history re-labels
itself, so "how would this rule have done?" is answerable immediately. A stored
column would need a re-backfill on every tweak.

### One source of truth for the thresholds

The risk of deriving is two definitions of one rule — `is_high_confidence` in
Python (Telegram) and a `CASE` in SQL (dashboard) — drifting apart. Mitigated two ways:

1. `web/perf.py` **imports the constants** from `signals.py`
   (`CONFIDENCE_MAX_REDUCTION`, `CONFIDENCE_MAX_PEAK_PCT`, `CONFIDENCE_MIN_TOP_N`)
   and interpolates them into the SQL. The *numbers* are defined once.
2. A test builds `Signal` objects across the boundaries, inserts them, and asserts
   the SQL cohort matches `is_high_confidence` row for row.

### Not stored — until the first retune

YAGNI. The Telegram message is already the record of what was actually sent. The
moment we change a threshold we lose the ability to ask "how did the signals I *was
told* were confident perform?", and **that** is when a stored
`fire_confidence_rule` (a version tag, not a bool) earns its place. Noted, not built.

### Its own tab, not more Outcomes

Outcomes already carries four analysis sections. Confidence is a different job —
a small number of decision-grade numbers, not exploration — so it gets a fourth tab
between Outcomes and Scorecard.

### Cohorts are `confident` / `rest`, always shown together

A win rate with nothing to compare against is a vanity metric. Every panel shows
both cohorts plus the delta; the question is never "is 70% good" but "is 70% better
than the 51% I'd get taking everything".

## Progress checklist

### Phase 1 — Backend: the cohort + summary ✅
- [x] `web/perf.py`: `_CONFIDENCE_SQL` built from the imported `signals.py`
      constants; exposed as a `cohort` column (`'confident'` / `'rest'`) on `perf`.
- [x] `confidence_summary(conn, horizon, classes)` → one row per cohort with
      `n`, `share_pct`, `win_pct`, `ev_pct`, `median_pct`, `mfe_pct`, `mae_pct`,
      `payoff`. Reuse `stats.summarize`; MFE/MAE come straight off the columns.
- [x] `web/models.py` `PerfConfidenceSummary`; `GET /api/perf/confidence-summary`.
- [x] Tests: cohort assignment at every boundary (reduction, peak pct, top_n,
      direction); **Python↔SQL agreement test** (see Decisions); NULL peak context
      falls to `rest`, never silently drops.

### Phase 2 — Backend: stability over time ✅
- [x] `confidence_timeline(conn, horizon, classes)` → one row per
      (cohort, UTC month) with `n`, `win_pct`, `ev_pct`. Month, not week — 11% of
      signals split two ways gets thin fast.
- [x] `GET /api/perf/confidence-timeline`.
- [x] Tests: bucketing lands signals in the right month; a month below a small-`n`
      floor is returned with its `n` rather than hidden, so the UI can grey it.

### Phase 3 — Backend: threshold sensitivity ✅
- [x] `confidence_sensitivity(conn, horizon, classes)` → grid over
      `max_reduction ∈ {0.4, 0.5, 0.6, 0.7}` × `max_peak_pct ∈ {20, 30, 40, 50, 60}`,
      each cell `{n, share_pct, win_pct, ev_pct}`.
- [x] `GET /api/perf/confidence-sensitivity`.
- [x] Tests: the cell matching the live constants equals `confidence_summary`'s
      `confident` row — the grid and the headline can't disagree.

### Phase 4 — Frontend: the Confidence tab ✅
- [x] `api/types.ts` + `api/client.ts`: three types, three hooks, class-filtered
      via `withClasses` like the rest.
- [x] `pages/Confidence.tsx` + a 4th entry in `App.tsx`'s `TABS`/`PAGES`.
- [x] **Scorecard header** *(core)* — big paired stat tiles, confident vs rest, for
      the selected horizon: win rate, EV, n, share of signals. Delta badge on each.
- [x] **Horizon table** *(core)* — the same metrics across 1d/3d/7d/14d, so you can
      see where the edge peaks and pick a holding period.
- [x] **Stability chart** *(core)* — monthly win-rate and EV, both cohorts, with a
      baseline line. This is the honesty panel: it's how rule decay shows up.
- [x] **MFE / MAE tiles** *(recommended)* — average best and worst excursion for
      confident signals. Directly informs target and stop placement, which is the
      most trade-actionable number on the page.
- [x] **Sensitivity heatmap** *(recommended)* — win or EV over the threshold grid,
      current setting marked. A smooth plateau around the marker means the rule is
      robust; an isolated bright cell means it's overfit and should be distrusted.
- [x] Empty/thin states: below ~30 scored confident signals the tab shows an
      "accumulating" banner instead of numbers that will move a lot.

### Phase 5 — Run-level count ✅ (built, not skipped)
- [x] `runs.confident_count` (nullable INTEGER, `_add_missing_columns` migration) +
      set it in the orchestrator. Answers "am I getting enough confident signals
      per week to bother?" without scanning `signals`. Cheap; skip if unwanted.

### Phase 6 — Docs ✅
- [x] `docs/schema.md`: note that confidence is derived, not stored, and where the
      thresholds live, so nobody hunts for a `fire_confident` column.

### Verification
- [x] `uv run pytest -q` green — 146 passed.
- [x] `npm --prefix frontend run build` clean.
- [x] Smoke-tested all three endpoints against `state/peakctx_work.sqlite3`.
      **The summary reproduces the headline exactly** — confident n=348, 70.1% win,
      +2.65% EV at 7d — so the SQL cohort and the offline analysis agree.
- [x] Served live and exercised the API end-to-end: `MACD_SEARCHER_DB_PATH=state/peakctx_work.sqlite3
      uvicorn macd_searcher.web.app:app --port 8399`. All three endpoints 200 across
      horizons and with `classes=`, the SPA bundle serves at `/`, and the JSON matches
      the offline numbers. **Not** visually screenshot-verified — the panels render from
      this data but nobody has looked at the pixels.

## Caveats to keep honest

- **Hard dependency on the peak-context backfill.** `fire_hist_peak_pct` is NULL on
  any signal that predates it, and those fall into `rest`. Run
  `--backfill-peak-context` on a DB *before* reading this tab, or `confident` will
  look artificially tiny and `rest` artificially bad.
- **The thresholds were fitted on the same two months the tab will display.** Until
  genuinely new data accrues, the headline numbers are in-sample and will look
  better than reality. The stability chart is the antidote — watch whether new
  months hold up, and treat the first out-of-sample month as the real test.
- **11.4% of signals, split by month, gets thin.** A month with n=12 will swing
  wildly. Show `n` everywhere; grey out thin periods rather than hiding them.
- **The sensitivity grid is a multiple-comparisons machine.** It exists to check
  for a plateau, *not* to pick the best cell. Retuning to the brightest square is
  exactly how this gets overfit — if we ever do retune, it should be on data the
  current thresholds were not fitted to.

## Out of scope / future

- Turning confidence into a **firing gate** (suppressing non-confident alerts). The
  measurement says it would help; it's deliberately a separate decision from
  measuring it, and shouldn't ride along with a dashboard change.
- Position sizing / a continuous confidence *score* rather than a boolean. Sensible
  eventually; needs more data than we have.
- Per-symbol confident performance — the Scorecard tab's job, and thin at 11%.
- A stored rule version (see Decisions) — add at the first retune.

## Reference — reused code

- `is_high_confidence`, `CONFIDENCE_*` constants — `src/macd_searcher/signals.py`.
- `_base()`, `parse_classes`, `peak_context_buckets` (endpoint shape),
  `by_symbol_scorecard` (per-cohort stats + payoff) — `web/perf.py`.
- `summarize` — `stats.py`. `heatColor`, `Card`, `Segmented`, `StateMsg`,
  `HORIZONS` — `components/ui.tsx` / `components/OutcomesCharts.tsx`.
- `Scorecard.tsx` — closest existing page to the stat-tile layout.
- Tab wiring — `App.tsx` `TABS` / `PAGES`.


## Measured results (first run, `prod_snapshot` after the peak-context backfill)

Confident vs rest, by horizon — the edge widens with holding period:

| horizon | confident n | win | EV | rest win | rest EV |
|---|---|---|---|---|---|
| 1d | 381 | 57.0% | +0.47% | 52.9% | +0.35% |
| 3d | 371 | 63.6% | +1.64% | 55.1% | +0.62% |
| **7d** | **348** | **70.1%** | **+2.65%** | 49.3% | −0.32% |
| 14d | 135 | 70.4% | +3.31% | 40.2% | −1.85% |

At 1d the two cohorts are nearly indistinguishable — the edge needs days to express,
which argues against treating a bolded alert as a same-day trade.

**Payoff ≈ 1.0** for both cohorts (0.99 vs 0.94), so the edge is entirely in *being
right more often*, not in bigger winners. MFE is similar between cohorts (10.98 vs
10.02) while MAE is meaningfully shallower (−8.13 vs −10.71): confident signals mostly
lose less, rather than win more.

**Stability** (7d): confident beat rest in both months, including the bad one —
2026-06 76.2% / +4.34% vs 57.1% / +1.41%; 2026-07 66.5% / +1.64% vs 43.5% / −1.59%.

**Sensitivity: a plateau, not a spike.** All 20 grid cells are positive EV (+1.62% to
+3.03%), win rates 63.5–74.0%. The live setting (0.6 / 40) sits in a broad flat
region, which is the strongest evidence yet that the rule isn't fitted to noise. The
nominal best cell (0.5 / 30 → 74.0% / +2.93%) is not meaningfully better and is *not*
a reason to retune on this data.
