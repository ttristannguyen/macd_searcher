# MACD signal-line at fire — bucket analysis (heatmaps + curves)

Working doc + progress tracker. Adds a **MACD signal-line analysis** to the
Outcomes → Charts view: win-rate and EV by **signal-line bucket × horizon**, split
by **direction**, as heatmaps and line graphs — the same shape as the RSI analysis
([rsi_analysis.md](rsi_analysis.md)). Tests whether *where the trend sits* at fire
time sharpens signal quality beyond the flat 30% reduction gate.

Sibling of [hist_peak_context.md](hist_peak_context.md) (histogram peak vs the
token's own tops) — a third signal-quality dimension, but a much cheaper one: see
"No capture needed" below.

## Context / why

The histogram says momentum is *flattening*. The signal line says **what it's
flattening out of**. A bearish flatten with the signal line far above zero is a
mature uptrend rolling over; the same flatten with the signal line below zero is a
bear-market bounce fading. Those are different trades, and today we can't tell them
apart in the outcome data.

## Headline finding: no capture, no migration

The RSI analysis needed a scanner change, a DB column, and a two-week wait for data.
**This needs none of that.** The signal line at fire time is already implied by
columns on every `signals` row, past and present:

```
hist = macd − signal_line          (indicators.macd, by construction)
⇒  fire_signal_line = fire_macd − fire_hist
```

Both come from the same fire-view bar in `_check_histogram_flattening`
([signals.py:154-163](../src/macd_searcher/signals.py#L154-L163)), so the identity is
exact — including under `use_forming_candle: true`. Verified against the local DB:
101/101 signals reconcile, and the derived (live) value sits a median 2.3% from the
snapshot's closed-bar `macd_signal`, i.e. the same quantity one bar apart.

The normalizer is free too: `_base()` **already** LEFT JOINs `asset_snapshots`
([perf.py:119](../src/macd_searcher/web/perf.py#L119)), which carries `atr` — present
on 101/101 signals locally.

**So this is a `web/perf.py` query + a frontend section. No scanner change, no
`ALTER TABLE`, no backfill job, and the full signal history is analyzable on day one.**

## Decisions (locked in)

### Normalize by ATR, not % of price

The user's opening question was "% of price to normalise?". The data says no —
%-of-price is an asset-class proxy in disguise. Median |signal line| across 666
snapshots in the local DB:

| class | % of price | ÷ ATR |
|---|---|---|
| fx | 0.17% | 0.38 |
| commodity | 1.60% | 0.48 |
| index | 1.43% | 1.16 |
| equity | 2.24% | 0.52 |
| crypto | 4.08% | 0.43 |

%-of-price spans **24×** fx→crypto; ATR-normalized spans **~1.4×** (index aside, n=10).
MACD scales with volatility as well as price, so dividing by price leaves the
volatility term in — bucket by it and the low buckets are "fx and commodities", the
high buckets are "crypto". Dividing by ATR removes both. `signal ÷ ATR` also reads
naturally: *how many daily ranges the trend is displaced from equilibrium*.

(The new class filter mitigates but doesn't fix this — the default view is
all-classes, and we want the buckets to mean the same thing in every view.)

### What `signal ÷ ATR` actually measures: trend signal-to-noise

Not trend *size*. An EMA of span N lags price by `(N−1)/2` bars, so the MACD line is
the gap between a 5.5-bar lag and a 12.5-bar lag — i.e. **exactly 7 bars' worth of
the current drift rate**. Verified on a clean ramp: MACD comes out at 7.00 × the
per-bar slope at every slope tested. ATR is one bar of typical movement. So:

```
signal ÷ ATR  ≈  7 × (drift per bar) ÷ (range per bar)
```

Holding drift **fixed** at 1.0/bar and varying only the chop:

| series | drift/bar | ATR | signal ÷ ATR |
|---|---|---|---|
| pure trend, no noise | 1.0 | 1.01 | 6.94 |
| strong trend, some chop | 1.0 | 1.50 | 4.67 |
| same drift, heavy chop | 1.0 | 4.08 | 1.35 |
| no drift, pure chop | 0.0 | 2.08 | 0.93 |

Same drift, and the reading collapses 6.94 → 1.35. It measures **how efficiently the
trend converted daily range into net displacement** — a cousin of Kaufman's
efficiency ratio. That reframes the thesis for the better: not *"does a bigger MACD
predict a better flatten"* but **"does fading a clean, persistent trend beat fading a
choppy one?"** — the more interesting question for a momentum-exhaustion detector.

It also explains the one residual class skew: equities/indices over-represent the top
bucket because they trend more smoothly than crypto (less chop per unit drift). Under
this reading that's signal, not confound.

### Bucket the signal line **signed**, split by direction

Not `abs`. The sign carries the regime, and it's the whole point: for a **bearish**
signal, `+1.2` = mature uptrend rolling over vs `−0.4` = downtrend continuation. The
existing **Bullish | Bearish** toggle keeps each half readable, exactly as the RSI
section does.

Edges `−1 / −0.5 / 0 / +0.5 / +1` → six buckets, mirroring the RSI six. Chosen from
the observed spread over fired signals (p5 −0.90, p50 +0.13, p95 +1.17, min −1.51,
max +1.60), so the tails are real but thin. Local occupancy over 101 pre-fix signals:

```
             <-1  -1..-0.5  -0.5..0  0..0.5  0.5..1  >=1
bullish       1       9        11      12       0      0
bearish       4       5         7      13      32      7
```

Bullish fires cluster negative (median −0.44), bearish positive (+0.58) — the regime
story showing up before we've measured a single outcome.

### Analyze the signal line, **not** the MACD line

The ask mentioned both. They're near-collinear (`corr(macd÷ATR, signal÷ATR) = 0.99`),
so two heatmaps would largely say the same thing twice — but the choice between them
is *not* immaterial: bucketed with the edges below, **20% of signals land in a
different bucket** depending on which axis you use. Worth deciding on principle
rather than on smoothness.

**The reason is orthogonality, not smoothing.** `macd = signal + hist`, and `hist` is
the detector's own firing variable — it fires precisely when `hist` has shrunk ≥30%
off its peak. We *already* analyze the `hist` dimension separately: `thresholds()`
buckets by `fire_reduction_from_peak`, and [hist_peak_context.md](hist_peak_context.md)
will bucket by peak ratio. So bucketing by the **MACD line** blends two things we
want to read apart — where the trend sits *and* how far the flatten has progressed —
and a gradient across those buckets would partly re-read the reduction effect
`thresholds()` already measures, with no way to tell which was driving it.

Taking the signal line subtracts the firing variable back out and leaves three
roughly-independent axes:

| axis | question | lives in |
|---|---|---|
| `signal ÷ ATR` | where does the trend sit / how clean is it | this doc |
| `reduction_from_peak` | how far has the flatten progressed | `thresholds()` |
| `hist_peak_ratio` | how big was the excursion | `hist_peak_context.md` |

**On the smoothing concern** (raised, fairly, in review): the signal line is an EMA9
of the MACD line, so it trades bias for variance — ~4 bars of lag in exchange for
less noise. Both costs were checked rather than assumed:

- *Lag* is the real cost, but it's small here. The gap between the two axes is
  `hist ÷ ATR`, whose median is **8–11% of a bucket width** (bullish −0.041, bearish
  +0.056 against 0.5-wide buckets) — it does not materially displace values, it just
  reshuffles rows already sitting near a boundary.
- *Noise* cuts the other way, and in our favour. Noise in the **bucketing** variable
  causes regression dilution: it smears rows across bucket boundaries and biases the
  measured gradient **toward flat**. The noisier axis would understate a real effect.
  Given the wide null distribution below, we need all the attenuation-resistance we
  can get.

### Rest

- One tidy endpoint `macd_signal_buckets` reusing `_base(classes)` — carries every
  dimension (`horizon × direction × bucket`); the frontend pivots. No per-call fan-out.
- Rows without a joined `atr` are excluded (`a.atr IS NOT NULL AND a.atr > 0`), same
  as RSI excludes NULL `fire_rsi_14`.
- Ordered buckets → **sequential** colour ramp, per the dataviz skill. Use a ramp
  distinct from RSI's violet (amber/orange) so the two sections don't read as one.

## Progress checklist

### Phase 1 — Backend endpoint
- [x] `web/perf.py`: `_MACD_SIGNAL_BUCKET_SQL` over
      `(s.fire_macd - s.fire_hist) / a.atr`, edges as above, `a`-prefixed label sort
      keys (`'a <-1'` … `'f >=1'`) matching the `_RSI_BUCKET_SQL` convention.
- [x] `macd_signal_buckets(conn, classes)` → rows `{horizon, direction, bucket, n,
      win_pct, avg_ret_pct}`; loop the four horizons like `rsi_buckets`.
- [x] `web/models.py`: `PerfMacdSignalBucket`. `web/app.py`:
      `GET /api/perf/macd-signal-buckets`, threading `classes` through `parse_classes`.
- [x] `tests/test_web_perf.py`: win/EV per bucket; a row with NULL `atr` is excluded;
      the `fire_macd − fire_hist` derivation lands in the bucket you'd expect;
      `classes` filter applies.

### Phase 2 — Frontend data layer
- [x] `api/types.ts` `PerfMacdSignalBucket`; `api/client.ts` `usePerfMacdSignalBuckets()`
      (reads `ClassesContext` via `withClasses`, like the other Outcomes hooks).

### Phase 3 — Frontend charts (`components/OutcomesCharts.tsx`)
- [x] `MacdSignalAnalysis()` section — **Bullish | Bearish** `Segmented`, mirroring
      `RsiAnalysis` ([OutcomesCharts.tsx:365](../frontend/src/components/OutcomesCharts.tsx#L365)).
- [x] **Win-rate heatmap** — bucket × horizon, diverging @ 50%, `n` per cell. *(core)*
- [x] **EV heatmap** — same grid, diverging @ 0%. *(recommended)*
- [x] **Win-rate curve** — x=horizon, line per bucket + dashed n-weighted **baseline**
      (derived client-side, no extra endpoint).
- [x] **Trend view** — x=bucket, line per horizon: the direct monotonic read.
- [x] Caption: what `signal ÷ ATR` means in words, and why ATR not price.

### Phase 4 — Wire in + docs
- [x] Compose `<MacdSignalAnalysis />` into `OutcomesCharts()` below `<RsiAnalysis />`.
- [x] `docs/schema.md`: note the derived metric (no new columns) so the next reader
      doesn't go hunting for a `fire_macd_signal` column.

### Verification
- [x] `uv run pytest -q` green.
- [x] `npm --prefix frontend run build` clean.
- [ ] Live eyeball: buckets populate for both directions, baseline renders, class
      filter re-queries the section. **Not verifiable locally** — the local DB has 0
      scored outcomes (0 of 101 signals have `px_7d`), so the endpoint correctly
      returns []. Needs the VM DB.

## Caveats to keep honest

- **ATR comes from the closed-bar snapshot**, the signal line from the live fire bar.
  ATR is a 14-period Wilder average — one bar of staleness is negligible against a
  0.5-ATR bucket width. Worth a one-line comment at the SQL, not a redesign.
- **`atr` arrives via a LEFT JOIN on `asset_snapshots`**, so a signal whose snapshot
  row is missing drops out of this analysis. That's the same rows the class filter
  already drops; it is not silent — `n` per cell shows it.
- Outer buckets (`<−1`, `≥+1`) are thin per direction today and may need merging if
  they stay that way. Read them as noise until `n` says otherwise.
- **The null distribution is wide — expect a modest gradient, if any.** Simulated over
  600 driftless random walks, `|signal ÷ ATR|` has a median of **0.66** and exceeds
  **1.0 about 30%** of the time (stable across realistic ATR calibrations). Our fired
  signals span p5 −0.90 to p95 +1.17, so the whole observed range sits largely inside
  what pure chance produces. Consequences for reading the charts: don't label the top
  bucket "strong trend", and treat the dashed **baseline** on the win-rate curve as
  the thing that matters — the question is whether any bucket beats trading everything,
  not whether the buckets differ from each other.
- This measures **correlation on fired signals only** — it cannot tell you how
  signal-line position performs where the detector never fired. That's what
  `reduction_counterfactual` does for reduction; the equivalent here would need
  `asset_snapshots.macd_signal` (which exists — see Out of scope).

## Out of scope / future

- **Counterfactual version** over `asset_snapshots` (every asset, fired or not) —
  `macd_signal`, `atr`, and `live_close` are all already stored, so the
  `reduction_counterfactual` machinery would port over. The natural follow-on if the
  fired-only view shows something.
- **2D cross-analysis** (signal line × RSI, or × peak-ratio) — too sparse yet, same
  call as the RSI doc made.
- **Trend-aligned variant** (`signal × +1 bearish / −1 bullish`) to collapse both
  directions onto one "how extended is the trend we're fading" axis, doubling n per
  bucket. Cheap to add later; costs the asymmetry the direction toggle exists to show.
- Acting on the finding (signal line as a firing/ranking condition) — measurement only.

## Reference — reused code

- `_base()`, `_RSI_BUCKET_SQL`, `rsi_buckets`, `parse_classes` — `web/perf.py`.
- `PerfRsiBucket` — `web/models.py`; `/api/perf/rsi-buckets` route — `web/app.py`.
- `RsiAnalysis`, `RsiHeatmap`, `RsiWinCurve`, `RsiTrendByBucket`, `heatColor`,
  `HORIZONS`, `Segmented` — `components/OutcomesCharts.tsx`.
- `usePerfRsiBuckets`, `withClasses`, `ClassesContext` — `api/client.ts`.
- `hist = macd − signal` — `indicators.macd`; fire-view `Signal` — `signals.py`.
