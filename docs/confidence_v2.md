# Confidence rule v2 — replace the bearish peak rule with a bullish sig/ATR rule

Working doc + plan + progress tracker. **Retires** the current
`is_high_confidence` (bearish + shallow reduction + modest peak) and replaces it
with a bullish rule built on the MACD signal line's distance from zero. **Built** — all phases done;
one visual check outstanding.

## Why retire v1

v1 was derived on data through 2026-08-06 and measured 70.1% win / +2.65% EV at 7d,
positive in both regime halves. Re-measured on the full set through 2026-09-18 it
has decayed to nothing:

| v1 rule (bearish + red<0.6 + peak pct<40 + n≥3) | n | win | EV |
|---|---|---|---|
| **all** | 496 | 60.9% | **+0.07%** |
| 1st half | 327 | 72.2% | +2.93% |
| 2nd half | 169 | 39.1% | **−5.46%** |
| 2026-08 | 98 | 25.5% | **−10.41%** |

Note the shape: the win rate is still 60.9%, but EV is zero. That's the bearish
payoff problem — bearish signals across the whole dataset run an MFE/MAE ratio near
**0.6**, so being right 6 times in 10 still loses money when the 4 losses are twice
the size. v1 was selecting for win rate on the wrong side of the book.

This is exactly what the Confidence tab's stability chart was built to catch, and
it caught it. The rule did its job by failing visibly.

## The replacement

**`bullish` AND `sig/ATR < −0.5` AND `reduction_from_peak < 0.6`**

where `sig/ATR = (fire_macd − fire_hist) / atr` — the MACD signal line's distance
below zero in units of daily range.

| | n | win | EV | MFE | MAE | ratio |
|---|---|---|---|---|---|---|
| **selected** | 504 | **62.7%** | **+3.86%** | +15.8% | −7.7% | **2.05** |
| everything else | 5314 | 47.8% | −1.17% | +10.6% | −13.2% | 0.80 |

8.7% of all signals. Mann-Whitney **p = 7.2e-15**.

### Why it works — the mechanism is measured, not assumed

A bullish fire is the detector anticipating the histogram crossing back above zero.
Whether that cross *completes* is the single largest split in the dataset:

| bullish signals | n | win | EV | ratio |
|---|---|---|---|---|
| cross completed within 5 bars | 1601 | **65.6%** | **+4.93%** | 2.66 |
| cross failed | 869 | **16.0%** | **−6.11%** | 0.43 |

Completion can't be known at fire time — but `sig/ATR` predicts it, monotonically:

| sig/ATR at fire | n | completes |
|---|---|---|
| < −1 | 323 | **88.2%** |
| −1 to −0.5 | 671 | **83.3%** |
| −0.5 to 0 | 828 | 51.8% |
| ≥ +0.5 | 149 | 47.0% |

A signal line far below zero means a deep downtrend, so MACD crosses back above it
on any bounce — mechanically easier, and with room left to run.

### Why a reduction *ceiling*, not a higher floor

`reduction_from_peak` also predicts completion (0.8+ → 79.6% vs 0.3–0.4 → 53.7%),
but that is nearly tautological: an 80%-shrunk histogram is already next to zero, so
of course it crosses. What it buys in completion it gives back in entry price. Within
the selected cohort:

| reduction | n | win | EV |
|---|---|---|---|
| 0.3–0.4 | 213 | 65.3% | +3.83% |
| 0.4–0.5 | 177 | 55.9% | +3.64% |
| 0.5–0.6 | 114 | 68.4% | +4.25% |
| 0.6–0.8 | 242 | 54.1% | +2.26% |
| 0.8+ | 251 | 48.2% | **+0.56%** |

So the detector's existing **30% minimum is correct** and stays untouched; v2 adds a
**60% cap** on top of it. Capping lifts the rule from +2.64% to +3.86% EV while
keeping 504 of 997 signals.

### Sensitivity — a plateau, not a spike

7d EV across the two thresholds (cell = EV / n):

| | 0.3–0.5 | 0.3–0.6 | 0.3–0.7 | 0.3–0.8 | 0.3–1.0 |
|---|---|---|---|---|---|
| **sig < −1.0** | +4.09 / 121 | +4.10 / 151 | +3.45 / 197 | +3.09 / 232 | +2.43 / 323 |
| **sig < −0.75** | +4.20 / 235 | +4.37 / 313 | +3.88 / 401 | +3.60 / 465 | +2.89 / 622 |
| **sig < −0.5** | +3.74 / 390 | **+3.86 / 504** | +3.57 / 634 | +3.34 / 746 | +2.64 / 997 |
| sig < −0.25 | +2.91 / 555 | +2.85 / 729 | +2.66 / 918 | +2.46 / 1083 | +1.73 / 1446 |
| sig < 0 | +2.78 / 747 | +2.49 / 972 | +2.34 / 1201 | +2.14 / 1401 | +1.47 / 1829 |

Every cell is positive and the surface is smooth — no isolated bright square. The
chosen corner isn't the maximum (that's −0.75 / 0.6 at +4.37%); **−0.5 was picked
for sample size, not for EV**, which is the right way round.

### Reading the grid

Cells are **disjoint bands** on both axes — each bullish signal sits in exactly one
cell, so a cell's win/EV describes that slice alone. Reduction bands run 0.3–0.4 …
0.8–1.0 (0.3 is the detector's own floor; nothing reaches 1.0). The rule is a
rectangle of whole cells, outlined as one box, and those 9 cells add up to exactly
the confident cohort (n=514, +3.82% EV at 7d — a test pins this).

7d EV / n, bullish only, box marked with `[ ]`:

```
   sig/ATR        0.3-0.4    0.4-0.5    0.5-0.6    0.6-0.7    0.7-0.8    0.8-1.0
   < -1.0       [ +4.18/59   +3.71/64   +4.15/30 ]  +1.31/46   +1.08/35   +0.76/92
   -1.0..-0.75  [ +3.82/61   +4.82/55   +5.30/49 ]  +3.24/47   +2.81/31   +1.01/70
   -0.75..-0.5  [ +3.60/98   +2.21/62   +2.94/36 ]  +2.86/44   +2.31/49   +0.15/94
   -0.5..-0.25    +1.65/98   +0.64/74   -0.05/65    +1.38/61   -0.08/53   -2.40/115
   -0.25..0       +6.07/130  +0.76/89   +0.19/59    +1.77/43   -0.89/35   -1.28/71
   >= 0           +3.35/269  +4.54/167  +6.38/92    -0.31/106  +0.85/75   +3.24/121
```

Every boxed cell is positive; the rows just below the box turn flat to negative.
The bottom row (sig/ATR ≥ 0) is worth watching: several of its cells are strong on
decent n. It sits outside the rule and would need its own regime check before it
earned a place in it.

An earlier version showed **cumulative** caps (each cell = everything below a
threshold) with a `<1.1` "no cap" column. That was a threshold-sensitivity sweep,
not a map of where the edge lives, and it was replaced at the user's request.

## Decisions (locked in)

### No new column after all — `atr` is already on both sides

The plan originally called for a `fire_atr` column plus a backfill. On inspection
that is unnecessary, and recording why so it isn't re-proposed:

- **`Signal.atr` already exists.** A later commit ("Add Signal/ATR to telegram msg")
  added it, computed in `_detect_for_asset` only for assets that actually fire.
- **It is deliberately closed-bar aligned.** That commit's comment is explicit: it
  takes the CLOSED bar even under `use_forming_candle`, specifically so the alert's
  number matches `asset_snapshots.atr`. So the Python value and the SQL join value
  are the same quantity by construction — the disagreement the column was meant to
  prevent cannot arise.
- **The join is complete.** 25,059 of 25,059 post-fix signals have a usable joined
  `atr` — 100.00%. There is no NULL tail to design around.

So v2 stays fully derived, exactly like v1: no migration, no backfill, and the rule
applies retroactively to all history the moment the endpoint ships.

The one real consequence: ATR is the closed-bar value while the signal line is the
fire-bar value. That seam is already documented in `_detect_for_asset` and is the
same one the dashboard's existing sig/ATR buckets live with. ATR is a 14-period
Wilder average, so a day of staleness is small against a 0.5-wide threshold.

### Ship class-agnostic, but say plainly that crypto carries it

| class | n | win | EV | ratio |
|---|---|---|---|---|
| **crypto** | 312 | 69.9% | **+6.08%** | 2.86 |
| equity | 160 | 49.4% | +0.21% | 1.09 |

Crypto-only is stronger *and* more stable (1st half +6.17%, 2nd +5.90%). But equity
is flat, not negative, and excluding a class is one more threshold fitted to this
sample. Ship both, surface class on the tab, and revisit if equity stays flat with
another two months. Recorded so it isn't mistaken for an oversight.

### Keep v1's architecture wholesale

Derived-in-SQL, thresholds imported from `signals.py` into `perf.py`, Python↔SQL
agreement test. All of that was right and none of it caused the decay — only the
predicate changes. The one exception is `fire_atr` (above), which is a stored input
to a still-derived rule.

## Progress checklist

### Phases 1 & 2 — Capture + backfill ✅ NOT NEEDED
- [x] Dropped. `Signal.atr` already exists and is closed-bar aligned to
      `asset_snapshots.atr`; the join covers 25,059/25,059 post-fix signals (100%).
      See Decisions. No column, no migration, no backfill.

### Phase 3 — The rule ✅
- [x] `signals.py`: replace `CONFIDENCE_MAX_REDUCTION` / `CONFIDENCE_MAX_PEAK_PCT` /
      `CONFIDENCE_MIN_TOP_N` with `CONFIDENCE_MAX_SIG_ATR = -0.5` and
      `CONFIDENCE_MAX_REDUCTION = 0.6`; rewrite `is_high_confidence` for the bullish
      predicate. Keep the measurement provenance comment, updated.
- [x] `perf.py`: rewrite `_CONFIDENCE_SQL` over `(fire_macd - fire_hist) / atr`
      (`atr` already rides in on `_base()`'s join) and `fire_reduction_from_peak`,
      importing the new constants.
- [x] Update the Python↔SQL agreement test's boundary cases for the new predicate.
- [x] `confidence_sensitivity`: sweep `sig/ATR ∈ {−1, −0.75, −0.5, −0.25, 0}` ×
      `reduction cap ∈ {0.5, 0.6, 0.7, 0.8, 1.1}` instead of the old grid. The
      "current setting" cell and its equality-with-summary test carry over.

### Phase 4 — Surfaces ✅
- [x] `notify.py`: no change needed to `_fmt_stage1_row` itself — the bold follows
      `is_high_confidence` — but confirm `_strength_key` still sorts sensibly now
      that confident rows are bullish (they'll float to the top of the BULLISH
      block rather than the BEARISH one).
- [x] Confidence tab copy: it describes a bearish rule throughout. Update the page
      subtitle, the sensitivity caption (axes changed), and the MFE/MAE caption
      (v2's edge is a 2.05 ratio, not v1's ~1.0).
- [x] `SignalsFeed`: the Peak column painted bearish `pct<40` **green**. Re-measured
      on fresh data that slice is −0.37% EV overall and −4.88% in the recent half —
      better than `pct>=40` (−3.34%) but still losing. Colour removed, number and
      tooltip kept as context, with the reasoning recorded in the component.
- [x] `AssetSignalsTable`: `★` needs no change (it follows `confident`). Added
      `sig_atr` to the row model/endpoint — it is the rule's own axis now, so the
      drill-down should show it.

### Phase 5 — Docs ✅
- [x] `docs/schema.md`: update the derived-confidence note to v2 (still derived —
      note that `atr` comes from the snapshot join, not a `signals` column).
- [x] `docs/confidence.md`: mark v1 superseded with the decay table, linking here.
      Do not delete it — the failure is the most useful thing in it.

### Verification
- [x] `uv run pytest -q` green — 173 passed.
- [x] `npm --prefix frontend run build` clean.
- [x] Against `state/prod_snapshot.sqlite3`: the endpoint returns **n=506, 62.8%
      win, +3.86% EV** at 7d against this doc's 504 / 62.7% / +3.86%. The two extra
      rows are ones the offline script dropped for a NULL `atr` that the endpoint
      correctly puts in `rest`; EV matches to the cent.
- [x] Sensitivity grid's flagged cell equals the summary row exactly (n, win, EV),
      and the whole grid reproduces the table above.
- [x] Dry-run message renders: confident bullish rows bold and floated to the top of
      the BULLISH block; a row failing only the reduction cap (red 0.88) and one
      failing only the sig/ATR cut (-0.20) both correctly stay plain.
- [x] Confidence tab audited end to end against `prod_snapshot`: all five panels
      200 across horizons and with `classes=`, every tile/caption re-read for stale
      v1 wording, and each panel's numbers checked against the source data. Found
      and fixed one real bug — see below. **Still not looked at as rendered pixels**;
      layout and colour are verified by construction, not by eye.

**Bug caught by the audit.** `SensitivityGrid`'s colour scale was still tuned to v1
(`mid=1, span=1.5` for EV). v2's grid runs +1.47 to +4.37, so **18 of 25 cells
saturated** — every cell above 2.5 rendered identically and the plateau-vs-spike
read, which is the panel's whole purpose, was flattened. Recentred on the grid's own
range (EV mid 2.9 / span 1.5, win mid 60 / span 10): 0/25 saturated, and the plateau
around the ringed cell is now visible with the falloff toward the loose corner.

## Caveats to keep honest

- **July was negative** (−1.08%, n=130) while June was +5.52% and August +6.06%.
  Both regime halves are positive (+3.04%, +5.64%) and the second is *stronger*,
  which is the opposite of v1's failure mode — but one losing month in four is the
  realistic expectation, not an anomaly to explain away.
- **The thresholds are fitted to this sample**, same as v1 was. v1 looked just as
  good at this stage and decayed within six weeks. The honest read is that v2 has a
  better mechanism (completion, measured) and a better payoff shape (ratio 2.05 vs
  ~0.9), not that it's proven. **September is the first out-of-sample month** — watch
  it on the stability chart before trusting the headline.
- **3d is the peak horizon** (70.6% win, +3.58%), not 7d. If this becomes a trading
  rule rather than a marker, the holding period should follow the data.
- Bearish signals lose their marker entirely. Given bearish EV is −1.17% across the
  rest of the book, that is the intended outcome, not collateral damage.

## Out of scope / future

- Making confidence a firing *gate* rather than a marker — still a separate decision.
- A stored `fire_confidence_rule` version tag. v1→v2 is exactly the retune that
  [confidence.md](confidence.md) said would justify one: after this ships, "how did
  the signals I was *told* were confident perform?" is no longer answerable for the
  v1 era. Worth adding **before** a v3.
- Crypto-only variant (see Decisions).
- Tracking cross completion as a logged outcome column — it is the strongest
  explanatory variable found so far and is currently recomputed from candles ad hoc.

## Reference — reused code

- `is_high_confidence`, `CONFIDENCE_*`, `_detect_for_asset`, `signal_line_pct_of_price`
  — `signals.py`; `atr` — `indicators.py`.
- `_CONFIDENCE_SQL`, `confidence_summary/timeline/sensitivity` — `web/perf.py`.
- `_backfill_rsi_symbol`, `_run_rsi_backfill`, `--backfill-rsi` — `update_outcomes.py`.
- `_add_missing_columns`, `insert_signals` — `db.py`.
- Confidence tab — `pages/Confidence.tsx`, `components/Confidence.tsx`.
