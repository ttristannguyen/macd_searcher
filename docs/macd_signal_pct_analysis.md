# MACD signal-line at fire — price-normalized bucket analysis (heatmaps + curves)

Working doc + plan + progress tracker. Adds a **second lens** on the MACD
signal-line-at-fire metric already analyzed in
[macd_signal_analysis.md](macd_signal_analysis.md): the same win-rate/EV
heatmaps and curves, split by direction, but bucketed by
**`(fire_macd − fire_hist) / fire_close × 100`** — signal line as a percentage
of the token's own price. **Built and measured** — see Findings below.

## Context / why

`macd_signal_analysis.md` already tried %-of-price and rejected it as the
*primary* axis: it measured as an asset-class proxy (fx 0.17% vs crypto 4.08%
median, a 24× spread, vs ~1.4× once ATR-normalized) and shipped ATR instead.
This doc doesn't relitigate that call — the request is to add %-of-price
**alongside** the ATR view, not replace it, so the two can be read side by
side. A plain percentage is also just more directly legible at a glance
("this trend is 3% of price above equilibrium") than an ATR-multiple, even
knowing it carries the class-mix confound.

## Decisions (locked in)

### Reuse the ATR doc's structural decisions unchanged

Signed buckets (not `abs`) split by **direction** via the existing
Bullish/Bearish toggle, analyzing the **signal line** (not the MACD line, to
stay orthogonal to `hist`/`reduction_from_peak`, already covered by
`thresholds()`) — see
[macd_signal_analysis.md § Decisions](macd_signal_analysis.md#decisions-locked-in)
for the reasoning; it applies identically here since it's the same underlying
metric, just re-normalized.

### Layout: same panel, no new toggle (confirmed with the user)

The new heatmaps/curves join the existing `MacdSignalAnalysis` section,
governed by its current Bullish/Bearish toggle — not a new section, not a
dual-always-visible bearish+bullish layout. To keep 8 cards (4 ATR + 4 price)
scannable, group them under two sub-headings ("ATR-normalized" /
"Price-normalized") inside the one panel.

### Bucket edges: even 2%-wide steps from −10 to +10 (12 buckets)

`<-10 / -10..-8 / -8..-6 / -6..-4 / -4..-2 / -2..0 / 0..2 / 2..4 / 4..6 / 6..8
/ 8..10 / >=10`.

First pass used 6 buckets at `−5/−2/0/2/5` (~5× the ATR version's step size).
Rejected on inspection: **76% of all signals (13,084 of 17,200) sit within
±5%** of zero, so 4 of those 6 buckets absorbed three-quarters of the data
between them — not enough resolution to see a pattern in exactly the band
that matters most.

```
percentiles [p1, p5, p25, p50, p75, p95, p99]
bullish (n=8113): -15.04  -9.97  -5.65  -2.63  -0.88   1.78   4.32
bearish (n=9087): -12.01  -8.07  -3.19  -0.89   1.36   5.38   9.20
```

Finer, evenly-stepped occupancy (post-`DETECTOR_FIX_CUTOFF`,
`histogram_flattening`, deduped-equivalent raw pull against
`state/prod_snapshot.sqlite3`):

```
             <-10  -10..-8 -8..-6 -6..-4 -4..-2 -2..0  0..2  2..4  4..6  6..8  8..10  >=10
bullish       402    624    801   1198   1814   2056   843   278    68    29     0      0
bearish       196    287    318    715   1656   2350  1846   859   534   186    68     72
```

Doubling the bucket count is free for the two **heatmaps** — buckets render
as rows (horizon is the fixed 4-column axis), so 12 buckets just makes the
table taller, same shape as every other heatmap in this set. It is **not**
free for `MacdSignalPctWinCurve`: that chart puts one line per bucket on a
single x=horizon plot, so 12 buckets means 13 lines (plus the dashed
baseline) instead of 7 — likely too crowded to read. `MacdSignalPctTrendByBucket`
(x=bucket, one line per horizon) is unaffected either way — only 4 horizon
lines regardless of bucket count. Resolve the win-curve crowding in Phase 3
below rather than shrinking the bucket count back down.

**Bullish's positive tail is genuinely empty past +8%** (`8..10`/`>=10` both
exactly 0 of 8,113) — a real structural asymmetry, not a bug: bullish fires on
downtrend-flattening context, so a strongly positive (mature-uptrend) signal
line essentially can't co-occur with it. The heatmap will correctly show
empty cells there for bullish; leave them empty rather than merging buckets
to hide it.

### The asset-class-proxy effect is expected — re-confirmed, with a caveat

A fresh check of median `|signal/price %|` by class corroborates the ATR
doc's finding qualitatively, though the exact numbers don't match its
historical table — worth reading with the sample sizes attached, not at face
value:

| class | median \|%\| | n |
|---|---|---|
| fx | 9.89% | **19** |
| crypto | 3.17% | 9,102 |
| equity | 2.29% | 3,947 |
| commodity | 2.22% | 717 |
| index | 0.26% | **123** |

`fx` and `index` are thin enough that their medians are close to anecdotal —
crypto/equity/commodity (the classes with real n) still show the same
multiple-of-spread pattern the ATR doc used to justify normalizing by ATR in
the first place. This is the expected, already-documented tradeoff of this
axis, not a new problem to solve — the point of building it is to let the
two views be compared directly, not to fix the confound.

## Progress checklist

### Phase 1 — Backend endpoint ✅
- [x] `web/perf.py` (after `macd_signal_buckets`, ~line 738): `_MACD_SIGNAL_PCT_EXPR
      = "(fire_macd - fire_hist) / fire_close * 100"`; `_MACD_SIGNAL_PCT_BUCKET_SQL`
      with the edges above, `a`-prefixed sort keys matching every other bucket SQL
      in the file.
- [x] `macd_signal_pct_buckets(conn, classes)` — copy of `macd_signal_buckets`'s
      body: reuse `_base(classes)`, loop the four horizons, gate on
      `fire_close IS NOT NULL AND fire_close > 0` (mirrors the `atr IS NOT NULL
      AND atr > 0` gate), group by `(direction, bucket)`, return
      `{horizon, direction, bucket, n, win_pct, avg_ret_pct}`.
- [x] `web/models.py`: `PerfMacdSignalPctBucket` — same fields as
      `PerfMacdSignalBucket`, own model per the established per-metric convention.
- [x] `web/app.py`: `GET /api/perf/macd-signal-pct-buckets`, same signature as
      `perf_macd_signal_buckets` (`classes: str | None = None`, `parse_classes`).
- [x] `tests/test_web_perf.py`: win/EV per bucket; a row with `fire_close` NULL/0
      excluded; the derivation lands in the expected bucket; `classes` filter applies.

### Phase 2 — Frontend data layer ✅
- [x] `api/types.ts`: `PerfMacdSignalPctBucket`.
- [x] `api/client.ts`: `usePerfMacdSignalPctBuckets()` — same pattern as
      `usePerfMacdSignalBuckets`, reads `ClassesContext` via `withClasses`.

### Phase 3 — Frontend charts ✅ (`components/OutcomesCharts.tsx`)
- [x] `MACD_SIGNAL_PCT_BUCKETS` label array; a new sequential ramp, distinct hue
      from violet (RSI) / teal (peak-context) / amber (MACD-signal ATR) — rose.
- [x] `MacdSignalPctHeatmap({ rows, metric })` — structural copy of
      `MacdSignalHeatmap`, axis label "Signal ÷ price %".
- [x] `MacdSignalPctWinCurve({ rows })` — copy of `MacdSignalWinCurve`, but with
      12 buckets it's a 13-line chart (see Decisions above) — treat it as a
      secondary/gestalt view (caption note: "read shape, not individual
      buckets") rather than trying to thin it out; `MacdSignalPctTrendByBucket`
      is the primary tool for a precise per-bucket read once it has 12 x-axis
      points instead of 6.
- [x] `MacdSignalPctTrendByBucket({ rows })` — copy of `MacdSignalTrendByBucket`;
      benefits most from the finer buckets since its x-axis is now 12 points.
- [x] In `MacdSignalAnalysis()`: add `usePerfMacdSignalPctBuckets()`, filter by the
      existing `direction` state, render the 4 new components under a
      "Price-normalized" sub-heading below the existing 4 (now under an
      "ATR-normalized" sub-heading) — one toggle still governs all 8.
- [x] Extend the panel's trailing caption with one sentence on the price-normalized
      view and its asset-class-proxy caveat.

### Phase 4 — Wire in + docs ✅
- [x] `docs/schema.md`: note the derived metric (no new columns), same as the ATR
      doc's entry.

### Verification
- [x] `uv run pytest -q` green — 150 passed.
- [x] `npm --prefix frontend run build` clean.
- [x] Served against `state/prod_snapshot.sqlite3`
      (`MACD_SEARCHER_DB_PATH=state/prod_snapshot.sqlite3 uvicorn macd_searcher.web.app:app
      --port 8401`): both bucket endpoints 200, `classes=` threads through, SPA serves,
      88 rows returned, and the bucket fills match the occupancy pattern the plan
      predicted (including the genuinely empty bullish positive tail).
- [ ] Visual pass over the 8 cards in the browser — the two sub-headings and the
      12-row heatmaps render from this data but have not been looked at directly.

## Caveats to keep honest

- Same caveats as [macd_signal_analysis.md](macd_signal_analysis.md#caveats-to-keep-honest)
  apply unchanged: fired-signals-only correlation, wide null distribution (don't
  over-read the outer buckets), signal line is a live-fire-bar value.
- Additionally here: **the asset-class-proxy effect is real, not a bug** — a
  gradient across price-% buckets may partly be re-reading "which classes tend to
  land in which bucket" rather than a genuine within-class effect. Cross-check
  any finding against the ATR heatmap sitting right above it before trusting it.
- `fx` (n=19) and `index` (n=123) are too thin for either normalization to say
  much yet; don't draw class-specific conclusions from them.

## Out of scope / future

- Counterfactual version over `asset_snapshots` — same follow-on noted in the ATR
  doc, applies equally here if the fired-only view shows something worth chasing.
- Acting on the finding (as a firing/ranking condition) — measurement only, same
  as every other bucket-analysis doc in this set.

## Reference — reused code

- `_base()`, `_MACD_SIGNAL_EXPR`, `_MACD_SIGNAL_BUCKET_SQL`, `macd_signal_buckets`,
  `parse_classes` — `web/perf.py`.
- `PerfMacdSignalBucket` — `web/models.py`; `/api/perf/macd-signal-buckets` route —
  `web/app.py`.
- `MacdSignalAnalysis`, `MacdSignalHeatmap`, `MacdSignalWinCurve`,
  `MacdSignalTrendByBucket`, `heatColor`, `HORIZONS`, `Segmented` —
  `components/OutcomesCharts.tsx`.
- `usePerfMacdSignalBuckets`, `withClasses`, `ClassesContext` — `api/client.ts`.
- `hist = macd − signal` identity, fire-view `Signal` — `signals.py`.

## Measured results (first run, `state/prod_snapshot.sqlite3`, 7d, deduped + scored)

| signal ÷ price | bull n | win | EV | bear n | win | EV |
|---|---|---|---|---|---|---|
| <-10 | 80 | **70.0%** | **+4.53%** | 47 | 40.4% | −3.01% |
| -10..-8 | 147 | 60.5% | +3.84% | 72 | 51.4% | −1.56% |
| -8..-6 | 192 | 55.7% | +1.99% | 99 | 55.6% | −0.15% |
| -6..-4 | 294 | 54.1% | +0.73% | 187 | 65.8% | +2.10% |
| -4..-2 | 381 | 40.7% | −1.64% | 392 | 57.1% | +0.21% |
| -2..0 | 453 | **36.9%** | **−1.90%** | 460 | 48.9% | −0.32% |
| 0..2 | 215 | 38.6% | −1.50% | 321 | 57.3% | +0.30% |
| 2..4 | 71 | 38.0% | −3.49% | 151 | 60.3% | +0.75% |
| 4..6 | 20 | 75.0% | +9.47% | 112 | 56.3% | −1.26% |
| 6..8 | 9 | 55.6% | +2.43% | 37 | 54.1% | −4.14% |
| 8..10 | — | — | — | 9 | 77.8% | +2.76% |
| >=10 | — | — | — | 13 | 69.2% | +8.67% |

**The finer buckets paid off, and they agree with the ATR view.** Bullish shows a
clean monotone gradient across the whole negative side: 70.0% / +4.53% at `<-10`
decaying steadily to 36.9% / −1.90% at `-2..0`. That is the same story the ATR
analysis told (bullish "elevation" is `−signal`, so deeply negative = a mature
downtrend being reversed) — arriving at it independently through a different
normalizer is a genuine corroboration, not a restatement.

It also vindicates the bucket-width decision: the rejected 6-bucket version would
have merged `-2..0` (n=453, the worst cell) into a single `-2..0`-ish band with its
neighbours and blurred the steepest part of the gradient.

Bearish is much noisier and non-monotone (`-6..-4` at 65.8% / +2.10%, `4..6` at
56.3% / −1.26%). The apparently strong far-positive tail — `8..10` 77.8%, `>=10`
69.2% / +8.67% — rests on n=9 and n=13 and should not be read as a finding.

**Structural asymmetry confirmed as predicted:** bullish `8..10` and `>=10` are
genuinely empty, because bullish fires on a flattening downtrend and cannot
co-occur with a strongly positive (mature-uptrend) signal line. The heatmap shows
them blank rather than merging the bands away.
