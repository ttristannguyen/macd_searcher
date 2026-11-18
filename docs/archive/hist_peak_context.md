# Histogram peak vs. the token's historical tops — capture + tooltip

Working doc + plan + progress tracker. Adds a per-signal metric: **how big is this
excursion's histogram peak relative to the token's own historical tops** — a ratio
("1.8× typical") and a **percentile** ("82nd pct of this token's bull tops"), with
the sample size `n`. Computed at fire time and logged on the signal, plus a
**backfill** so it could be measured immediately rather than after a two-week wait.
Measurement came back positive — see [Findings](#findings-backfilled-measurement).

## Context / why

The metric is normalized per-token, so a `|hist|` of 0.5 that's "1.8× typical" for
one token isn't confused with 0.5 that's "0.6× typical" for another. RSI and
reduction already give two signal-quality dimensions; this adds a third.

> **⚠️ The original thesis was wrong — and the inverse is tradeable.**
> This doc opened with: *"a flatten from a peak that's huge relative to the token's
> own norm is a more meaningful momentum-exhaustion read than a flatten from a tiny
> one."* Backfilled onto 3,004 scored signals, **the opposite holds**. See
> [Findings](#findings-backfilled-measurement) — the result is a *filter*, not a
> tooltip, so the plan below was re-ordered to measure before surfacing.

## Decisions (locked in)

- **Compute fresh from the hist series** — *not* from logged `hist_recent_peak`
  (that's 10-bar-capped, recorded ~6×/day so it over-weights long moves, and only
  goes back to when logging started). The scanner already has the full 200-bar
  `hist` in memory at fire time, so this is nearly free.
- **Fixes the 10-day-window inaccuracy** by detecting **full same-sign excursions**
  (bounded by zero-crossings), not a fixed 10-bar window — for *both* the baseline
  tops **and** the current top. (The detector keeps its 10-bar cap for the *firing*
  gate — deliberate; this metric uses a separate, uncapped full-excursion peak via
  `_excursion_peak(hist, len(hist))`.)
- **Median, not mean**, for "typical top" (one blow-off spike skews the mean).
- **Percentile too** (mid-rank, tie-aware) — more robust/interpretable than a ratio.
- **Per-sign**: a bearish signal is compared to prior *bear* tops (positive peaks),
  bullish to prior *bull* troughs — momentum is often asymmetric.
- **Exclude the current (in-progress) excursion** from the baseline.
- Scope = fired signals (`signals` table), like RSI. Non-destructive DB migration.

## Metric stored (3 columns, display-ready)
- `fire_hist_peak_ratio` — current |peak| ÷ **median** of prior same-sign |tops|.
- `fire_hist_peak_pct` — mid-rank **percentile** (0–100) of the current |peak| among
  prior same-sign tops.
- `fire_hist_top_n` — count of prior same-sign tops the baseline is built from (the
  trust gauge; `n=3` → treat "2.5×" as noise).
All NULL/0 when there's no prior same-sign excursion in the 200-bar window.

## Findings (backfilled measurement)

Measured on `state/prod_snapshot.sqlite3` (2026-06-06 → 08-06) after the Phase-2b
backfill: 14,332 signals recomputed, 14,133 with a real baseline, **3,004 of them
scored at 7d**. Baseline across those: 51.8% win, +0.06% EV.

### 1. The relationship is inverted, and it's bearish-only

Bearish signals, by ratio decile — a smooth gradient, not a threshold artifact:

| decile | ratio | n | win% | EV% |
|---|---|---|---|---|
| 1 | 0.00–0.18 | 161 | 62.7 | +1.60 |
| 2 | 0.18–0.36 | 157 | **71.3** | **+2.75** |
| 3 | 0.36–0.51 | 159 | 58.5 | +1.07 |
| 4–5 | 0.51–0.86 | 323 | ~59 | +0.6 |
| 6–9 | 0.86–2.81 | 641 | ~51 | ~−0.2 |
| 10 | >2.81 | 166 | 59.0 | +0.81 |

*(bearish baseline: 57.4% win, +0.65% EV)*

**Fading a monster move doesn't work; fading a tired one does.** A histogram peak
far above the token's own norm means momentum too strong to reverse — it pauses and
resumes. A modest peak is a move that genuinely rolls over.

The **percentile** form cuts even more cleanly than the ratio (it's rank-based, so
the heavy right tail — max ratio 27× — can't distort it):

| `fire_hist_peak_pct` | n | win% | EV% |
|---|---|---|---|
| 0–20 | 422 | 63.5 | +1.54 |
| 20–40 | 301 | 62.5 | +1.39 |
| 40–60 | 401 | 50.6 | −0.15 |
| 60–80 | 240 | 54.2 | +0.37 |
| 80–100 | 243 | 55.1 | −0.20 |

### 2. It is a filter, and it survives the regime split

Bearish, dropping `ratio >= 0.6` — **positive EV in both halves**, unlike the
signal-line elevation filter which only ever made a bad regime less bad:

| | before | after | p |
|---|---|---|---|
| all | n=1607, 57.4%, +0.65% | n=566, **64.3%, +1.77%** | — |
| first half | 57.6%, +0.91% | 63.7%, **+2.05%** | 0.022 |
| second half | 57.3%, +0.51% | 64.6%, **+1.61%** | 0.00017 |

It also **strengthens as the baseline becomes more trustworthy** — a coherence check
the metric passes: `top_n>=6` → 68.2% / +2.56%; `top_n>=8` → 74.4% / +3.84%.

### 3. It's a genuinely new axis

`corr(log ratio, reduction_from_peak) = −0.23` — weak, so this is not re-reading the
reduction gate we already trade.

### Caveats
- **Bullish does not hold.** First half favours low ratio (p=0.033); second half is
  flat and slightly reversed (p=0.33). Bearish-only until more data says otherwise.
- Two months, one regime pair. The bearish result repeating in both halves at
  p=0.0002 in the larger one is the strongest evidence we have, but it's still 2 months.
- **Many looks at one dataset.** Ratio buckets, percentile buckets, deciles, `top_n`
  gating, two directions, two halves. The headline bearish result is robust to that;
  the `top_n>=8` cell (n=133) is a second cut on the same data — suggestive, not proven.
- Baselines are thin: median `top_n` is 6. That's what `top_n` is for.

## Progress checklist

### Phase 1 — Detector helpers + capture (`src/macd_searcher/signals.py`) ✅
- [x] `_excursion_peaks(hist) -> (bull_troughs, bear_peaks)` — |peak| of every
      **completed** same-sign excursion, split by sign; trailing run excluded.
- [x] `_peak_vs_history(hist, direction) -> (ratio, pct, n)` — cur =
      `abs(_excursion_peak(hist, len(hist)))`; priors = same-sign completed tops;
      `ratio = cur/median(priors)`, `pct = mid-rank percentile`, `n = len(priors)`;
      `(None, None, 0)` when no priors / median 0.
- [x] `Signal`: add `hist_peak_ratio`, `hist_peak_pct` (`float | None`), `hist_top_n` (`int = 0`).
- [x] `_detect_for_asset`: after the signal fires, compute on `m["hist"]` (the exact
      fire-view series) and `replace(sig, …)` alongside the existing RSI attach.
- [x] Tests (`tests/test_signals.py` / `tests/test_indicators.py`): crafted hist with
      a few completed excursions + a trailing one → assert the excursion peaks,
      ratio, percentile, and n; a no-prior case → None/0.

### Phase 2 — Database (`src/macd_searcher/db.py`) ✅
- [x] `SCHEMA_SQL`: `fire_hist_peak_ratio REAL, fire_hist_peak_pct REAL, fire_hist_top_n INTEGER` on `signals`.
- [x] `init_schema`: extend the existing `_add_missing_columns` call with the 3 columns.
- [x] `insert_signals`: write the 3 new values.
- [x] `tests/test_db.py`: migration adds them; roundtrip.

### Phase 2b — Backfill ✅ (added; the doc originally deferred measurement)
- [x] `db.fetch_signals_missing_peak_context` / `db.update_signal_peak_context` —
      NULL `fire_hist_top_n` marks un-backfilled rows, so 0 ("computed, no baseline")
      is never redone.
- [x] `update_outcomes.py --backfill-peak-context`: one candle fetch per symbol over
      all its signals, slice to the `lookback_days` window ending at each fire bar,
      recompute. 178 symbols / 14,332 signals in ~90s.
- [ ] Run it against the live VM DB (done only against `prod_snapshot` so far).

### Runbook — backfilling the live VM DB

The backfill is **idempotent and non-destructive**: it only writes rows where
`fire_hist_top_n IS NULL`, so a second run is a no-op and no existing column is ever
overwritten. The schema migration runs automatically (`update_outcomes.main` calls
`init_schema`). Still, take the backup — it costs 20 seconds.

```bash
ssh <your-vm>
cd ~/macd_searcher

# 1. Back up first. .backup is WAL-safe; a plain `cp` can miss the -wal file.
.venv/bin/python -c "import sqlite3,sys; s=sqlite3.connect('state/macd_searcher.sqlite3'); d=sqlite3.connect('state/macd_searcher.backup.sqlite3'); s.backup(d); d.close(); s.close(); print('backup ok')"

# 2. Deploy the code carrying the new columns + the backfill flag.
git pull && uv sync --extra web

# 3. Run it. ~90s for ~180 symbols; expect a few HTTP 429s — the client retries.
#    Pick a window away from the crons (scan at 0 */4, outcomes at 01:30 UTC).
.venv/bin/python -m macd_searcher.update_outcomes --backfill-peak-context

# 4. Verify: most signals should now carry a baseline.
.venv/bin/python -c "import sqlite3; c=sqlite3.connect('file:state/macd_searcher.sqlite3?mode=ro',uri=True); print('total', c.execute('SELECT COUNT(*) FROM signals').fetchone()[0]); print('with baseline', c.execute('SELECT COUNT(*) FROM signals WHERE fire_hist_top_n>0').fetchone()[0]); print('still NULL', c.execute('SELECT COUNT(*) FROM signals WHERE fire_hist_top_n IS NULL').fetchone()[0])"

# 5. Restart the dashboard so the API serves the new columns.
sudo systemctl restart macd-searcher-web
```

Expect roughly the shape seen on `prod_snapshot`: ~99% of signals get a baseline, the
rest legitimately have no prior same-sign excursion in their window. If step 4 shows
a large "still NULL" count, some symbols' candle fetches failed — the log names them,
and simply re-running picks up only those.

Rollback: `mv state/macd_searcher.backup.sqlite3 state/macd_searcher.sqlite3`. The new
columns are additive, so older code also keeps working against the migrated DB.

### Phase 3 — Dashboard surfaces ✅
- [x] `recent_signals` SELECT + `SignalRow` model + `SignalRow` TS type: the 3 fields.
- [x] `SignalsFeed.tsx`: a **Peak** column (`1.8× p82`) with a tooltip naming the
      verdict. Green when it's the favourable (low-percentile) side of a *bearish*
      fire; muted when `top_n < 3` or absent. Bullish shows the number, no verdict —
      it didn't hold up.
- [x] **Analysis panel** (`PeakContextAnalysis` in `OutcomesCharts.tsx`) — win/EV
      heatmaps + curves by peak percentile x horizon, direction toggle defaulting to
      **bearish** (the side with a result). Added beyond the original plan: the
      measurement turned this into a filter, which deserves more than a tooltip.
- [x] `perf.peak_context_buckets` + `/api/perf/peak-context-buckets`, class-filtered
      like the rest of the tab; excludes `top_n < 3` as untrustworthy.

### Phase 4 — Docs
- [ ] `docs/schema.md`: rows for the 3 new columns. README: one line in the S1
      description that we also log peak-vs-history context.

### (Optional) Telegram
- [ ] Deferred — the alert row is already busy (hist, reduction, RSI, price). Could
      append `pk 1.8×`; leaving out for now to avoid clutter. Decide later.

### Verification
- [x] `uv run pytest -q` green — 134 passed.
- [x] `npm --prefix frontend run build` clean.
- [ ] `python -m macd_searcher --dry-run --no-db` runs; spot-check the values are
      sane (ratio ~0.3–3, pct 0–100, n small).

## Caveats to keep honest
- 200 daily bars ≈ only ~10–30 same-sign excursions (fewer for strong-trending
  tokens) → a noisy baseline for thin histories; that's what `n` is for.
- This is a *new* computed metric — not derivable from existing columns.

## Out of scope / future
- **Peak-context bucket analysis** (win/EV by peak-ratio or percentile bucket,
  like the RSI/reduction heatmaps) — the natural payoff once data accrues. The
  bucket-analysis pattern is being built first for the signal line
  ([macd_signal_analysis.md](macd_signal_analysis.md)); copy it when the ratio
  columns have matured.
- Snapshot-level version (every asset, for counterfactual) — later.

## Sibling work

[macd_signal_analysis.md](macd_signal_analysis.md) — MACD signal-line at fire, the
third signal-quality dimension. Independent of this doc and much cheaper: the
signal line is already derivable from existing columns (`fire_macd − fire_hist`),
so it needs no capture, no migration, and no waiting for data. Worth landing first.

## Reference — reused code
- `_excursion_peak`, `_trailing_same_sign_len`, `_detect_for_asset`, `Signal`,
  `replace` pattern — `src/macd_searcher/signals.py` (same spot RSI is attached).
- `_add_missing_columns` migration, `insert_signals`, `SCHEMA_SQL` — `db.py`.
- `recent_signals` — `web/queries.py`; `SignalRow` — `web/models.py`;
  RSI column pattern — `components/SignalsFeed.tsx`.
