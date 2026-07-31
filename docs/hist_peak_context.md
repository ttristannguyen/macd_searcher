# Histogram peak vs. the token's historical tops — capture + tooltip

Working doc + plan + progress tracker. Adds a per-signal metric: **how big is this
excursion's histogram peak relative to the token's own historical tops** — a ratio
("1.8× typical") and a **percentile** ("82nd pct of this token's bull tops"), with
the sample size `n`. Computed at fire time, logged on the signal, shown as a feed
tooltip. **Capture-only** (like RSI); the peak-context *analysis* (win/EV by
peak-ratio bucket) is a future follow-on.

## Context / why

A flatten from a peak that's huge *relative to the token's own norm* is a more
meaningful momentum-exhaustion read than a flatten from a tiny one. RSI and
reduction already give two signal-quality dimensions; this adds a third — and it's
normalized per-token, so a `|hist|` of 0.5 that's "1.8× typical" for one token
isn't confused with 0.5 that's "0.6× typical" for another.

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

## Progress checklist

### Phase 1 — Detector helpers + capture (`src/macd_searcher/signals.py`)
- [ ] `_excursion_peaks(hist) -> (bull_troughs, bear_peaks)` — |peak| of every
      **completed** same-sign excursion, split by sign; trailing run excluded.
- [ ] `_peak_vs_history(hist, direction) -> (ratio, pct, n)` — cur =
      `abs(_excursion_peak(hist, len(hist)))`; priors = same-sign completed tops;
      `ratio = cur/median(priors)`, `pct = mid-rank percentile`, `n = len(priors)`;
      `(None, None, 0)` when no priors / median 0.
- [ ] `Signal`: add `hist_peak_ratio`, `hist_peak_pct` (`float | None`), `hist_top_n` (`int = 0`).
- [ ] `_detect_for_asset`: after the signal fires, compute on `m["hist"]` (the exact
      fire-view series) and `replace(sig, …)` alongside the existing RSI attach.
- [ ] Tests (`tests/test_signals.py` / `tests/test_indicators.py`): crafted hist with
      a few completed excursions + a trailing one → assert the excursion peaks,
      ratio, percentile, and n; a no-prior case → None/0.

### Phase 2 — Database (`src/macd_searcher/db.py`)
- [ ] `SCHEMA_SQL`: `fire_hist_peak_ratio REAL, fire_hist_peak_pct REAL, fire_hist_top_n INTEGER` on `signals`.
- [ ] `init_schema`: extend the existing `_add_missing_columns` call with the 3 columns.
- [ ] `insert_signals`: write the 3 new values.
- [ ] `tests/test_db.py`: migration adds them; roundtrip.

### Phase 3 — Dashboard tooltip (`web/queries.py`, `web/models.py`, `frontend/src/**`)
- [ ] `recent_signals` SELECT + `SignalRow` model + `SignalRow` TS type: add the 3 fields.
- [ ] `SignalsFeed.tsx`: a compact **Peak** column, e.g. `1.8×`, with a `title`
      **tooltip**: `"82nd pct · n=14 · vs this token's typical bear top"`. Muted/`—`
      when `n` is small or null.

### Phase 4 — Docs
- [ ] `docs/schema.md`: rows for the 3 new columns. README: one line in the S1
      description that we also log peak-vs-history context.

### (Optional) Telegram
- [ ] Deferred — the alert row is already busy (hist, reduction, RSI, price). Could
      append `pk 1.8×`; leaving out for now to avoid clutter. Decide later.

### Verification
- [ ] `uv run pytest -q` green.
- [ ] `npm --prefix frontend run build` clean.
- [ ] `python -m macd_searcher --dry-run --no-db` runs; spot-check the values are
      sane (ratio ~0.3–3, pct 0–100, n small).

## Caveats to keep honest
- 200 daily bars ≈ only ~10–30 same-sign excursions (fewer for strong-trending
  tokens) → a noisy baseline for thin histories; that's what `n` is for.
- This is a *new* computed metric — not derivable from existing columns.

## Out of scope / future
- **Peak-context bucket analysis** (win/EV by peak-ratio or percentile bucket,
  like the RSI/reduction heatmaps) — the natural payoff once data accrues.
- Snapshot-level version (every asset, for counterfactual) — later.

## Reference — reused code
- `_excursion_peak`, `_trailing_same_sign_len`, `_detect_for_asset`, `Signal`,
  `replace` pattern — `src/macd_searcher/signals.py` (same spot RSI is attached).
- `_add_missing_columns` migration, `insert_signals`, `SCHEMA_SQL` — `db.py`.
- `recent_signals` — `web/queries.py`; `SignalRow` — `web/models.py`;
  RSI column pattern — `components/SignalsFeed.tsx`.
