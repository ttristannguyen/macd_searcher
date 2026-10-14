# Confidence research — v2 audit, outside indicators, and a v3 proposal

Findings doc. Measured 2026-10-14 against `state/prod_snapshot.sqlite3` (synced
2026-10-14 14:00; 31,435 signals, latest run 2026-10-14 00:00). Goal: find patterns
in the database that improve the confidence marker ([confidence_v2.md](confidence_v2.md)),
with a deliberate lean toward indicators the detector does not already use.

## Headline

1. **v2 has no selection edge.** Its in-sample +3.82% 7d EV decomposes as **+4.60%
   market move − 0.56% alpha**. A random same-class asset bought at the same instant
   did as well. Out of sample (fired ≥ 2026-09-19) its raw EV is −2.64% (n=28).
2. **v1 was retired for the wrong reason.** Its August "collapse" (raw EV −10.41%)
   was the market rallying 10.45% against a short; its alpha that month was −0.19%.
   Over the whole sample v1 has alpha **+0.80%** (week-block [+0.09, +1.44]) — modest
   skill, though not significant at episode level (§6) — and v2 replaced it with none.
   Both rules were judged on raw EV, which is dominated by market direction.
3. **The signal is `peak_pct`:** *fading a tired move works, fading a record move
   fails.* For bullish fires, low `fire_hist_peak_pct` is good and a **record**
   downswing (`peak_pct = 100`) is the worst slice in the book (alpha −2.41%
   in-sample, **−7.95% out-of-sample**). This survives every robustness check below,
   including one-number-per-episode inference. The bearish mirror looks as strong at
   row level but **does not survive episode-level inference** (§6).
4. **Proposed v3** — bullish `peak_pct ≤ 50 & red < 0.6` (primary), plus a record-peak
   veto; the bearish leg `peak_pct ≤ 25` only as a shadow. The combined rule has 7d
   alpha +0.92% [+0.45, +1.41] in-sample and +2.04% [+0.53, +3.33] out of sample at
   row level, and **+0.93% [+0.09, +1.80] at episode level** — real, but closer to
   the edge of significance than the row-level numbers suggest. Stored columns only.
5. **~60 outside indicators tested** (trend, momentum, volatility, volume, candle
   shape, relative strength, open interest, market regime, funding, signal crowding).
   None beats `peak_pct`. A few replicate (volatility, ADX, OI/volume, distance from
   the 200-day) but are **generic factors** — they predict alpha for random assets
   too. Market-timing indicators (BTC trend, breadth) look strong in-sample and
   **flip sign out of sample**. Funding predicted nothing in-sample and costs ~0.16%
   a week on longs; out of sample, high funding started marking bad bullish signals —
   a hypothesis to watch, not yet a finding (§8).
6. **The effective sample is ~26% of `n`.** Repeat fires on consecutive days overlap;
   only 2,054 of 7,832 rows are independent episodes. Every headline claim was
   re-checked at episode level (§6), which is why the bearish leg is demoted.

The single most important change is not a threshold: **judge confidence rules on
alpha, not raw EV.** That one process fix would have prevented both v1's retirement
and v2's adoption.

## Data and method

Read this before reusing any number — the method is what makes them trustworthy.

- **Cohort:** `perf._base()` — post-`DETECTOR_FIX_CUTOFF`, `stage='histogram_flattening'`,
  earliest fire per (symbol, direction, UTC day). 7,832 signals, 2026-06-09 → 2026-10-14.
  7d outcomes exist for fires through 2026-10-06.
- **In-sample / out-of-sample split at 2026-09-19.** v2 was fitted on data through
  2026-09-18, so everything after is genuinely unseen by v2. All new thresholds below
  were set on in-sample data only (medians or round numbers, not optimised) and then
  checked out of sample.
- **Alpha = return minus a same-instant counterfactual.** For each signal's run, the
  benchmark is the **mean** forward return of every same-class symbol in that run's
  `asset_snapshots`, entered at that run's `live_close` and exited at the same daily
  close as `px_Nd`. Same entry instant, same exit bar. A random universe pick scores
  exactly 0 by construction. (The **median** benchmark used in
  [direction_asymmetry_analysis.md](direction_asymmetry_analysis.md)'s first draft
  hands any selection ~+1% of free alpha on right-skewed returns — do not use it.)
- **Alignment verified:** DB `px_7d` equals the fetched candle close at fire-day + 7
  on 7,459 / 7,459 rows.
- **Outside indicators** come from daily OHLCV fetched from the Hyperliquid public API
  for all 240 universe symbols (2025-08-01 → today), computed on **closed bars up to
  the day before the fire** — no look-ahead. 66% of deduped fires are at 00:00 UTC,
  where that is exactly the information available. OI and volume come from
  `asset_snapshots` at the fire run (OI change uses the same symbol 24/72/168h earlier).
- **Statistics:** day-block bootstrap for the scans (forward windows overlap, so whole
  UTC days are resampled together); Benjamini–Hochberg FDR across the indicator scan;
  every rate-based claim checked against the universe counterfactual. **Day-block is
  not enough on its own** — see §6: consecutive-day repeat fires make only ~26% of
  rows independent, so headline claims are re-checked with first-fire-per-episode,
  week-block, and one-number-per-episode inference.

## 1. v2's edge was the market, not the selection

```
                      n     raw EV   = market move   + alpha    alpha 95% CI
v2 in-sample        480    +4.04%       +4.60%        -0.56%    [-1.30, +0.30]
v2 out-of-sample     22    -3.14%       -3.75%        +0.61%    [-1.18, +2.06]
bullish rest (IS)  2068    +2.13%       +2.61%        -0.48%
bearish (IS)       3308    -2.76%       -2.07%        -0.69%
```

v2 fires after deep sell-offs, which in June–September were followed by sharp
class-wide bounces (crypto runs with a v2 fire saw the class rise +5.97% over 7d vs
+3.42% on an average run). So v2 had some *market-timing* content in-sample — but the
assets it picked did no better than their peers, and that timing has not survived:
out of sample v2 fired almost only on equities (20 of 28 signals, 2 crypto) into a
falling tape.

v2's own axis carries no selection information at all on the full sample:

```
               alpha IC (7d)              raw IC (7d)
sig_atr      -0.017 [-0.063, +0.033]    -0.048 [-0.151, +0.067]
macd_atr     -0.014 [-0.059, +0.035]    -0.053 [-0.159, +0.065]
red          -0.049 [-0.087, -0.018]    -0.067 [-0.137, +0.004]
```

The cross-completion mechanism in confidence_v2.md is real but **mechanical**: a
signal line far below zero makes the cross easy, which says nothing about whether the
asset beats the market afterwards.

## 2. v1 was retired on market direction

```
v1 = bearish & red<0.6 & peak_pct<40 & top_n>=3      (n=586, 7.6% of signals)

month      n    raw EV    market move (short-signed)    alpha
2026-06  130    +4.34%           +2.12%                +1.89% [+0.88, +2.99]
2026-07  230    +1.50%           +1.28%                +0.42% [-0.35, +1.17]
2026-08   98   -10.41%          -10.45%                -0.19% [-1.96, +1.52]
2026-09  114    -1.06%           -1.93%                +0.74% [-0.71, +2.12]
2026-10   14    +8.42%           +4.88%                +3.46% [+2.16, +5.92]
all      586    -0.19%                                 +0.80% [+0.17, +1.36]
```

August's −10.41% is the market move to two decimal places. The rule's selection was
flat that month and positive overall. The Confidence tab's stability chart "caught"
a bull rally, not a broken rule.

## 3. The outside-indicator scan

61 features × bullish signals, IC against 7d alpha, discovery in-sample with FDR,
validation out-of-sample. Families: trend (SMA20/50/100/200 distance, SMA slope, ADX,
DI spread), momentum (ROC 3–60d, stochastic, CCI, RSI), volatility (ATR %, ATR
14/50, realised vol, vol-of-vol, Bollinger %B and width), volume (1d/5d vs 20d,
down-volume share), candle shape (body, wicks, close location, streak), position
(drawdown from 30/90d high, range position), relative strength vs BTC, derivatives
(OI change 1/3/7d, OI ÷ volume, log volume), market regime (BTC/ETH ROC, BTC vs
SMA50/200, BTC ADX, breadth above SMA50, crypto median ROC), funding (§8).

**Replicated — same sign out of sample, FDR q < 0.05 in-sample:**

```
feature            IS IC                     OOS IC
peak_pct          -0.110 [-0.147,-0.063]    -0.233 [-0.292,-0.134]   detector column
peak_ratio        -0.109 [-0.144,-0.066]    -0.246 [-0.334,-0.143]   detector column
atr_ratio_14_50   -0.146 [-0.191,-0.105]    -0.096 [-0.201,+0.048]   vol expanding = worse
oi_to_vol         +0.102 [+0.059,+0.146]    +0.115 [+0.014,+0.199]   high OI per unit volume = better
adx14             -0.101 [-0.148,-0.045]    -0.146 [-0.259,+0.018]   strong trend = worse
dist_sma200_atr   -0.082 [-0.128,-0.037]    -0.168 [-0.247,-0.056]   far above 200d = worse
atr_pct / rv20    -0.075 / -0.089           -0.366 / -0.348          volatile assets = worse
dd_from_high_30   +0.076 [+0.035,+0.121]    +0.279 [+0.169,+0.416]   (mostly volatility again)
```

These CIs are day-block (too narrow, §6). Re-run at one number per episode (843
bullish episodes, week-block), every feature in the table still excludes zero over
the full sample — `peak_pct` −0.134 [−0.200, −0.056], `oi_to_vol` +0.123
[+0.070, +0.189], `dist_sma200_atr` −0.137 [−0.228, −0.066], `atr_ratio_14_50`
−0.118 [−0.194, −0.047] — while `sig_atr` stays at −0.025 [−0.120, +0.060]. The
OOS-only episode subset (n=90) is too small to confirm any of them on its own.

**Generic factors, not signal skill.** Run on every universe asset at every 00:00 run
(15,464 asset-days with a 7d alpha), the same features predict alpha with the same
sign. Among bullish signals they are 1.5–3x stronger — and significantly so for
`atr_ratio_14_50` (−0.144 vs −0.067) and `oi_to_vol` (+0.101 vs +0.029), whose CIs
do not overlap — so the signal amplifies them. But a low-volatility tilt would help a
random portfolio too; it is not something the MACD detector knows.

**Market-timing features do not replicate.** For *raw* return, BTC stochastic
(IS −0.369), BTC 7d ROC (−0.328), ETH 7d ROC and crypto median ROC are the strongest
in-sample predictors in the whole scan — "buy bullish signals after the market has
fallen". All four **flip to positive out of sample** (+0.13 to +0.25). Timing the
market from these is fitting one regime.

**Inside the v2 cohort alone, nothing passes FDR** (n=480). No outside indicator
rescues v2.

**Indicators built from the signal stream itself carry nothing either.** Crowding
(how many same-direction fires in the run, as a count or a share of the universe) and
repeat behaviour (days since the symbol last fired the same way; first fire in 14
days) all have alpha ICs within ±0.03 in-sample. Crowded bullish runs do show far
higher *raw* EV (+5.06% vs +1.44% for lone fires, win 65% vs 46%) at identical alpha
— a market-wide capitulation-then-bounce, the same timing effect as v2, not selection.

## 4. `peak_pct` — the finding

For a bullish fire, `fire_hist_peak_pct` is the percentile of the current negative
histogram trough among every completed negative trough in the ~200-bar window
(`signals._peak_vs_history`); 100 = the deepest bearish momentum swing in that window.
For a bearish fire it is the same against prior positive peaks.

**Bullish, 7d alpha by band — monotone:**

```
peak_pct     IS alpha                  n     OOS alpha                 n
0–25        +0.91% [+0.09, +1.77]     537    +3.90% [-3.00,+11.27]    22
25–50       +0.08% [-0.70, +0.85]     570    -1.54% [-3.88, +0.46]    88
50–75       -0.04% [-1.06, +1.02]     568    +0.53% [-1.32, +2.65]   128
75–<100     -1.60% [-2.36, -0.91]     438    -1.89% [-3.27, +1.20]    70
100         -2.41% [-3.73, -1.06]     414    -7.95% [-9.81, -5.79]    64
```

**It is not a proxy for volatility or drawdown.** Record peaks underperform inside
every ATR% tercile (−0.69 / −2.55 / −4.15% vs −0.16 / −0.06 / −0.24% non-record) and
inside every 90-day-drawdown tercile. It holds in both classes (crypto record −4.65%
[−6.35, −2.93] vs non-record +0.31%; equity −1.57% vs −0.87%) and across `top_n`
buckets. In crypto the raw-EV gap is large too: record **+0.05%** vs non-record
**+4.76%**.

**And it mirrors on the bearish side** (short-side alpha):

```
peak_pct     IS alpha                  n     OOS alpha                 n
0–25        +1.00% [+0.48, +1.59]     778    +2.36% [+0.79, +3.74]    85
25–50       -0.48% [-1.07, +0.03]     720    -0.17% [-1.43, +1.57]   151
50–75       -2.08% [-2.95, -1.19]     578    -0.98% [-1.84, +0.01]   191
75–<100     -2.21% [-3.42, -0.98]     544    -0.34% [-1.64, +0.90]   174
100         -0.56% [-1.53, +0.46]     661    -0.93% [-1.99, +0.33]   207
```

The mechanism is the one `_PEAK_PCT_BUCKET_SQL`'s comment already records for
bearish: a modest excursion that is fading is exhaustion; a record excursion that is
pausing is momentum that resumes. **But read the bearish table with §6 in hand:** at
one number per episode its gradient is no longer significant (IC −0.035
[−0.126, +0.064]). The bullish side holds up at episode level; the bearish side is a
hypothesis.

## 5. A composite score is mostly a veto

Equal-weight rank composite of the five least-collinear replicating features
(`peak_pct`, `adx14`, `oi_to_vol`, `atr_pct`, `atr_ratio_14_50`; ranks against the
in-sample distribution so out-of-sample has no leakage):

```
bullish   IC vs 7d alpha    IS +0.164 [+0.118,+0.207]    OOS +0.269 [+0.160,+0.342]
          Q1 (worst)        IS -3.30% [-4.55,-2.07]      OOS -4.90% [-6.96,-1.51]
          Q5 (best)         IS +1.01% [+0.27,+1.81]      OOS +1.76% [-0.65,+5.03]
bearish   IC                IS -0.012                    OOS -0.052   (does not transfer)
```

Q1 is worse than Q2–5 in every complete month (gap −1.2, −4.6, −7.2, −5.2pp). But
taken one at a time, `peak_pct`'s worst quintile alone gives −2.45% / **−7.86%**, as
strong as the whole composite out of sample. **The composite adds complexity, not
information** — `peak_pct` does the work.

Simple median-split rules on the other features (ADX, OI/volume, ATR ratio) gave
in-sample alpha of +0.05 to +0.63% with out-of-sample CIs spanning zero. A
significant IC does not make a tradeable cut.

## 6. Robustness — repeat fires overlap, so the real sample is a quarter of n

`_base()` dedups to one fire per symbol-direction-day, but the same setup re-fires on
consecutive days: **71% of bullish rows are a repeat of the same symbol within 3
days**, and their 7d forward windows overlap almost completely. Grouping fires with
gaps ≤ 3 days into episodes leaves **2,054 independent episodes out of 7,832 rows
(26%)**. The day-block bootstrap used above handles same-day clustering but treats a
symbol's consecutive days as independent, so its CIs are too narrow. Three stricter
treatments, 7d alpha:

```
                   (A) first fire per episode         (B) all rows,              (C) one number per episode,
                   IS                 OOS             week-block CI              week-block CI
v1 (retired)      +0.12 [-0.86,+1.13] +1.45 [+0.17,+2.82]  +0.80 [+0.09,+1.44]   +0.63 [-0.40,+1.43]
v2 (current)      -0.47 [-1.71,+0.73] -0.95 (n=7)          -0.51 [-1.59,+0.54]   -0.19 [-1.63,+1.26]
v3 bullish leg    +0.94 [-0.08,+2.15] +2.66 [-0.37,+5.49]  +0.88 [-0.31,+2.05]   +1.11 [+0.01,+2.20]
v3 bearish leg    +0.55 [-0.59,+1.70] +2.26 [-0.71,+4.14]  +1.13 [+0.34,+2.06]   +0.77 [-0.45,+1.78]
v3 combined       +0.76 [-0.03,+1.62] +2.47 [+0.40,+4.31]  +1.03 [+0.22,+2.00]   +0.93 [+0.09,+1.80]
VETO bull record  -3.88 [-6.54,-1.23] -7.46 [-12.8,-0.56]  -3.15 [-5.72,-0.76]   -2.12 [-5.07,+0.69]
everything        -0.45 [-0.91,+0.03] +0.49 [-0.79,+1.94]  -0.63 [-1.02,-0.20]   -0.25 [-0.68,+0.19]
```

And the feature itself, one number per episode (first fire's `peak_pct`, mean alpha
across the episode), week-block CI:

```
bullish peak_pct   0-25 +1.76   25-50 +0.87   50-75 +0.52   75-<100 -1.75   100 -2.33
                   episode IC -0.134 [-0.200, -0.055]                       <- robust
bearish peak_pct   0-25 +0.61   25-50 -0.52   50-75 -1.30   75-<100 -2.31   100 -0.63
                   episode IC -0.035 [-0.126, +0.064]                       <- not robust
```

**What survives:** the bullish `peak_pct` gradient (monotone, IC excludes zero at
episode level); v3 combined (point estimate stable at +0.76 to +1.03% across every
treatment, lower bound just above zero in two of three, first-fire OOS
+2.47% [+0.40, +4.31]); the record-peak veto in (A) and (B). **What weakens:** the
bearish leg, whose row-level strength came largely from repeats; and v1, whose
selection edge is real at row level but not at episode level. **What doesn't
change:** v2 has no selection edge under any treatment.

The same overlap applies to every number in
[direction_asymmetry_analysis.md](direction_asymmetry_analysis.md) and
[confidence_v2.md](confidence_v2.md), which used day-block or no resampling.

## 7. Proposed v3

```
confident  =  bullish AND peak_pct <= 50 AND reduction_from_peak < 0.6     (primary)
warning    =  bullish AND peak_pct = 100                                   (record-peak veto)
shadow     =  bearish AND peak_pct <= 25            (track on the tab; do not bold yet)
```

All inputs are stored columns (`fire_hist_peak_pct`, `fire_reduction_from_peak`,
`direction`), so — like v1 and v2 — it is derivable in SQL and applies retroactively.

```
rule                          share   IS alpha 7d             OOS alpha 7d            winsorised   months>0
v1 (retired)                  7.6%   +0.78 [+0.13,+1.39]     +0.91 [-0.43,+2.35]       +0.81%        4/5
v2 (current)                  7.1%   -0.56 [-1.30,+0.30]     +0.61 [-1.18,+2.06]       -0.51%        2/5
v3 bullish leg                9.0%   +0.81 [+0.08,+1.55]     +1.58 [-0.96,+4.35]       +0.66%        4/5
v3 bearish leg               11.3%   +1.00 [+0.48,+1.59]     +2.36 [+0.79,+3.74]       +1.14%        5/5
v3 combined                  20.3%   +0.92 [+0.45,+1.41]     +2.04 [+0.53,+3.33]       +0.94%        4/5
VETO: bullish record peak     6.8%   -2.41 [-3.73,-1.06]     -7.95 [-9.81,-5.79]       -3.25%        1/5
everything                  100.0%   -0.61 [-0.88,-0.33]     -0.75 [-1.38,-0.19]       -0.56%        1/5
```

(winsorised = 7d alpha clipped at the 1st/99th percentile, full sample.)

**Sensitivity is a plateau.** Bullish 7d alpha / n over the two thresholds:

```
peak<=     red<0.5     red<0.6     red<0.7     red<0.8     no cap
25       +1.63/204   +1.42/262   +1.47/325   +1.34/374   +1.03/559
37.5     +1.37/307   +1.44/389   +1.46/480   +1.31/554   +0.97/789
50       +0.90/496   +0.88/628   +0.88/772   +0.67/894   +0.40/1217
62.5     +0.88/621   +0.89/786   +0.90/959   +0.68/1104  +0.52/1458
75       +0.66/828   +0.65/1047  +0.57/1276  +0.31/1472  +0.28/1913
uncapped +0.30/1069  +0.29/1350  +0.20/1634  -0.04/1873  -0.12/2421
```

Alpha rises smoothly as the peak cap tightens; the reduction axis barely matters.
All nine cells around `peak ≤ 50 / red < 0.6` have positive out-of-sample point
estimates (+1.01 to +2.35%). 50 was chosen for sample size, not because it is the
best cell — tighter caps score higher on fewer signals. The bearish grid has the same
shape (`peak ≤ 12.5`: +1.62 to +2.61%; `peak ≤ 25`: +1.13 to +1.57%; `peak ≤ 50`:
+0.09 to +0.42%).

**Horizon:** unlike v2 (peak at 3d), the v3 bullish edge accumulates — alpha +0.08 /
+0.51 / +0.88 / +1.19% at 1 / 3 / 7 / 14d. The bearish leg likewise (+0.99 / +1.00 /
+1.46% at 3 / 7 / 14d in-sample).

### What v3 is and is not

- **It is a selection edge of roughly +1% per week against the asset's own class.**
  That is what alpha measures and what survived out of sample.
- **It is not a promise of positive raw P&L.** A naked bullish v3 position still rides
  the market: in October every rule, v3 included, had negative raw EV. The bearish
  leg's raw EV in-sample is −0.10% at 7d — profitable only when the short is paired
  against the class.
- **Hedging against BTC is not the same as hedging against the class.** Long crypto
  v3 / short BTC returned +1.23% [−0.13, +2.81] in-sample — no better than long *every*
  crypto bullish signal / short BTC (+1.61%), because alt-vs-BTC drift dominates a
  ~1% edge. An executable hedge needs a basket closer to the class mean.

## 8. Funding

Hourly funding history fetched per symbol (`fundingHistory`, from 2026-05-15).
Coverage: **239 of 240 symbols, 99% of signal rows.**

**(a) Funding did not predict anything in-sample — and only started to in the
falling market.** Last-hour rate, 24h and 7d means, a 30-day z-score and the 24h
premium all have in-sample alpha ICs within ±0.04 for both directions, every CI
spanning zero (n=2,533 bullish, 3,283 bearish). The level explains why: median
funding at fire is **9.8% APR for bullish and 10.7% for bearish** — essentially
Hyperliquid's default 0.01%/8h (10.95% APR). Most of the time funding sits at its
baseline and carries no positioning information.

Out of sample, though, the bullish ICs are consistently negative and exclude zero:

```
bullish     IS IC                     OOS IC (n=372 rows, ~90 episodes)
fund_last   +0.017 [-0.025,+0.054]    -0.187 [-0.263,-0.120]
fund_24h    -0.013 [-0.058,+0.028]    -0.177 [-0.284,-0.084]
fund_7d     -0.031 [-0.078,+0.012]    -0.198 [-0.281,-0.135]
prem_24h    -0.015 [-0.052,+0.022]    -0.150 [-0.293,-0.005]
bearish     all within ±0.05 in both periods
```

Plausible mechanism: in a falling market, bullish signals on assets where longs are
paying up (crowded positioning) unwind harder than their peers. But it is absent in
three months of in-sample data, rests on ~90 independent episodes in one regime, and
was not pre-registered. **Treat it as the leading hypothesis to watch, not a rule
input.** If it persists into a rising market it would justify storing funding at fire.

**(b) Carry is a small cost, not a deal-breaker.** Realised funding over the 7-day
hold, as % of notional (a long pays it, a short receives it), full sample:

```
              n     long pays    raw -> net of funding     alpha -> net of funding
v2           542     +0.160%     +3.48% -> +3.32%          -0.51% -> -0.67% [-1.38,+0.07]
v3 bullish   677     +0.160%     +2.71% -> +2.55%          +0.86% -> +0.69% [+0.01,+1.39]
v3 bearish   879     +0.127%     +0.09% -> +0.22%          +1.14% -> +1.26% [+0.73,+1.83]
all bullish 3147     +0.176%     +1.93% -> +1.75%          -0.67% -> -0.85% [-1.22,-0.48]
all bearish 4312     +0.124%     -2.03% -> -1.91%          -0.59% -> -0.47% [-0.75,-0.17]
```

About 0.12–0.18% a week, ≈6–9% APR. It takes about a fifth off the v3 bullish leg's
weekly alpha (+0.86% → +0.69%, CI still just clear of zero at day-block) and slightly
*helps* shorts. This also corrects
[direction_asymmetry_analysis.md](direction_asymmetry_analysis.md), which had assumed
funding would eat most of a +0.86% alpha.

**Recommendation:** no funding gate now. Net out ~0.16%/week on longs in any trading
rule built on v3, and re-test the out-of-sample funding effect once the market turns.

## Recommendations

1. **Change how rules are judged before changing the rule.** Add the decomposition
   `raw EV = market move + alpha` to the Confidence tab's summary and stability chart,
   with alpha against the same-run, same-class **mean**. Every retune decision so far
   has been made on raw EV; both mistakes in this doc follow from that.
2. **Shadow-run v3 next to v2** rather than replacing v2 outright. Compute it on the
   tab for 4–6 weeks without changing Telegram bolding. v3 was chosen after looking at
   6 candidate rules and ~60 features, and its episode-level CI only just clears
   zero, so the out-of-sample number is the one to watch. Track the bullish leg and
   the bearish shadow separately — they have very different evidence behind them.
3. **Ship the record-peak warning.** It is the clearest single result here
   (monotone gradient, −7.95% OOS at row level, −7.46% first-fire OOS, both classes,
   not a volatility or drawdown proxy) and needs no new rule: render `peak_pct = 100`
   on bullish rows as a warning rather than a neutral number. Its episode-level CI
   does include zero (only 100 episodes), so this is a warning, not a gate.
4. **Report effective sample size.** Show episodes alongside `n` on the Confidence
   tab and use week- or episode-level resampling for its intervals; at ~26%
   independence, `n` overstates the evidence about fourfold.
5. **Add the `fire_confidence_rule` version tag before v3** — confidence_v2.md already
   asked for it. Without it, a v2→v3 switch erases the ability to ask how the signals
   people were *told* were confident performed.
6. Do not add sig/ATR or market-regime gates to v3. Neither carries selection
   information, and the regime gates reverse out of sample.

## Caveats

- **Short out-of-sample window.** 2026-09-19 → 2026-10-06 fires, one market regime
  (falling). OOS n is 61–87 per leg. The OOS CIs that exclude zero are encouraging,
  not conclusive.
- **Multiple comparisons.** ~60 features and 6 rule shapes were examined. `peak_pct`
  is the only feature whose result is monotone, signal-specific, OOS-stronger and
  confound-free — but the v3 thresholds were still chosen with the in-sample data in
  view.
- **Alpha is relative.** Positive alpha in a falling market can still mean losing
  money, just less than the class.
- **Fees and slippage are not modelled; funding is measured but not netted** in the
  headline tables (§8 shows it is ~0.12–0.18% a week). All returns are close-to-close
  on a signal that fires on a forming bar.
- **`peak_pct` depends on the 200-bar window.** A config change to `lookback_days`
  changes what "record" means and would need re-measurement.

## Reproduction

Ad hoc scripts (session scratchpad, not committed): candle + funding fetch via
`hyperliquid.fetch_candles` / `fundingHistory`; dataset build joining `_base()` to
indicators at fire-day − 1 and the same-run class benchmark; IC scan with BH-FDR;
universe counterfactual panel over 00:00 runs. Everything above is reproducible from
the method section against a 2026-10-14 snapshot.
