# Why bullish and bearish diverge — and what to do about it

Findings doc. Measured 2026-09-11 against `state/prod_snapshot.sqlite3` as synced
2026-09-10 13:00 (23,599 signals; runs through 2026-09-10). Started from a simple
question — *why is bullish EV better than bearish?* — and ended somewhere more
useful: **the bearish signal is not weak, it is inverted.**

**Cohort:** `_base()` — post-`DETECTOR_FIX_CUTOFF`, `stage='histogram_flattening'`,
deduped to the earliest fire per (symbol, direction, UTC-day) — further restricted
to rows with a scored 7d outcome and a usable ATR. That is **5,244 signals over 86
UTC days, 2026-06-09 → 2026-09-02** (2,218 bullish / 3,026 bearish). Signals fired
after 2026-09-02 have no 7d outcome yet and are excluded throughout.

Companion to [regime_consistency_analysis.md](regime_consistency_analysis.md)
(which has known errors listed at the bottom of this file) and
[macd_signal_analysis.md](macd_signal_analysis.md).

> ## ⚠ Revised 2026-09-12 — the original conclusion was wrong
>
> Two errors were found by asking a question this document could not answer:
> *why* do 20% of bearish signals end in a big up-move? Chasing the mechanism
> broke two of the three headline results.
>
> 1. **The benchmark was biased.** Alpha was `raw − class MEDIAN`. Asset returns
>    are right-skewed (pool mean exceeds pool median by ~0.97pp at 7d), so
>    `E[X − median] > 0` for *any* selection. A **random** pick scored **+1.10%**
>    against that benchmark. Every alpha in the first version was inflated by
>    roughly that much. Corrected to the class **mean**, against which a random
>    pick scores 0.00% by construction.
> 2. **The 20% tail is the base rate.** 21.4% of bearish signals rose >10% in
>    14d. So did **21.5%** of random same-class same-day assets. Excess: −0.1pp.
>
> **Net effect: §6's flip does NOT survive split-half** (H1 +0.24%
> [−0.50, +0.98], includes zero) and **§3's "real breakout" claim is dead**.
> Sections below are corrected; the superseded numbers are kept struck through
> where they are instructive.

## Headline

| | bullish | bearish |
|---|---|---|
| n | 2,218 | 3,026 |
| win rate @7d | 50.2% | 48.5% |
| EV @7d | +1.41% | −2.44% |
| avg win / avg loss | +9.40% / −6.64% (**1.42**) | +6.23% / −10.61% (**0.59**) |
| skew | +1.33 | −2.32 |
| alpha vs class mean @7d | **−1.057%** [−1.67, −0.42] | **−0.861%** [−1.60, −0.14] |

The win rates differ by 1.7pp. The EVs differ by **3.85pp**. A 1.7pp hit-rate gap
cannot produce that — the payoff ratio does: bullish winners pay 1.42x what its
losers cost, bearish winners pay 0.59x. Bearish is not much worse at *being right*;
it is far worse at *getting paid for it*.

**The corrected alpha row is the real headline, and it is brutally simple: both
directions lose to their own asset class, by about the same amount.** Bullish −1.06%,
bearish −0.86%, both CIs excluding zero. The apparent asymmetry in raw EV is the
right skew of crypto returns acting on a long vs a short, not a difference in what
the detector knows.

*(Superseded: the first version reported bullish +0.081% "neutral" and bearish
−2.106%, both measured against a median benchmark that flatters any selection by
~1.10%.)*

## 1. Bearish EV is an identity, not a result

`ret_bearish = 1 − px/fire_close = −raw_move`, so mean bearish EV *is* the negated
average move of whatever it fired on. "Bearish EV is −2.3%" and "those assets rose
2.3%" are the same sentence. The class split makes the identity visible:

```
crypto      n=2015   undirected +3.27%   bearish EV -3.27%
equity      n= 837   undirected +0.72%   bearish EV -0.72%
commodity   n= 150   undirected +1.43%   bearish EV -1.43%
```

So the real question was never "why is bearish EV bad" — it was **"why did the
things it fired on go up?"**

## 2. It is selection, not market drift

The obvious answer — *it was a bull market, shorts lose* — is wrong, and the
benchmark kills it. On bearish-fire days the **class median moved +0.42%**. Nearly
flat. The assets it fired on moved **+2.52%**, six times as far.

```
            n      raw   mean bench   median bench   ALPHA(own dir)   95% CI        excl.0
bullish  2154  +1.464%      +2.521%        +1.418%         -1.057%   [-1.67,-0.42]   yes
bearish  2911  +2.465%      +1.604%        +0.414%         -0.861%   [-1.60,-0.14]   yes
```

The two benchmark columns are the whole story of the original error. Against the
**median** the bearish pool looks nearly flat (+0.414%) and the signal's +2.465%
looks like huge outperformance. Against the **mean** — the benchmark a random pick
actually has to beat — the pool returned +1.604%, and the signal *underperformed* it.

So §2's original claim ("the detector was picking the ones that went up") is
**wrong**. It was picking assets that went up about as much as everything else in
their class, and slightly less.

~~The tape was not carrying them up. The detector was picking the ones that went
up.~~ **Corrected: the tape was carrying them up, and the detector added nothing.**
The bearish call still fails — raw +2.465% means shorts lost — but the cause is
that the class itself returned +1.604% on those days, not that these particular
assets were selected for strength. A bearish fire does structurally require a
positive histogram peak, and it does fire at RSI 50.9 against bullish's 42.7; that
simply does not translate into picking outperformers.

This is the same verdict already recorded in `_PEAK_PCT_BUCKET_SQL`'s comment in
`web/perf.py`, reached from a completely different direction: *"Fading a monster
move fails — the momentum resumes; fading a tired one works. Bearish only so far."*

**And bullish is worse, not neutral.** Alpha −1.057%, CI excluding zero. Its +1.41%
EV is not just "entirely its class's move" — it is *less* than its class's move.
Buying the class at random on those days would have paid **+2.521%**. Both
directions are value-destroying relative to the simplest possible alternative.

## 3. One trade in five blows up, and that tail is the whole story

Bearish, raw 14d price move (positive = the call failed):

```
p5 -18.24%   p25 -5.78%   p50 +0.10%   p75 +7.82%   p95 +28.38%   mean +2.49%
rose >10%: 20.5%    >20%: 9.7%
```

The **median bearish signal works** — price drifts down. The 521 signals that rose
>10% contribute +5.17pp of the +2.49% mean; exclude them and the mean is −3.36%.

That arithmetic is correct but the inference drawn from it was not. "The negative EV
*is* this tail" implies the tail is a signal failure mode. It is not — it is the
right tail of the asset return distribution, which the counterfactual below shows
the signal does not alter.

~~And it is a real breakout, not crypto beta: 17.7% beat their own class by >10pp.~~
**Wrong — that was measured without a counterfactual.** Compared against every
same-class same-day asset:

```
                                    bearish signals   random same-day   excess
rose >10% in 14d                             21.4%            21.5%     -0.1pp
beat class median by >10pp                   18.1%            17.6%     +0.4pp
fell more than 10%                           15.5%            16.0%     -0.5pp
```

The full 14d distribution is indistinguishable from a random pick at *every*
percentile (n=2,544 signals vs 179,353 counterfactual observations):

```
  pct      signals    random     shift
  p5       -18.39%   -17.81%   -0.58pp
  p50       -0.18%    -0.20%   +0.02pp
  p90      +20.65%   +22.07%   -1.42pp
  p95      +29.95%   +32.15%   -2.19pp
  mean      +2.42%    +2.69%   -0.27pp
```

**So the answer to "why do 20% of bearish signals end in a big up-move" is: because
20% of everything does.** Median daily ATR on these assets is 6.14% of price, so a
>10% move over 14 days is **1.6 daily ATRs** — 45.5% of the so-called blow-ups are
under 3 ATR. The threshold was absolute on assets whose ordinary two-week range is
far wider than it. There is no blow-up phenomenon to explain.

The tail is also not concentrated in a way that would suggest a mechanism: 556
blow-ups spread over 78 of 81 fire-days and 119 symbols; the top 10 days hold 34.5%
and the top 10 symbols 25.7%.

The MACD confirming does not protect you — **73% of bearish signals do cross zero
downward** (against 37% for bullish) and price still rises.

## 4. You cannot see it coming at fire time

Every fire-time feature we store, tested against "does this blow up >10% by 14d"
(base rate 20.5%):

```
signal/ATR       lift 0.85x – 1.09x
RSI at fire      lift 0.79x – 1.18x
reduction        lift 0.73x – 1.11x
asset class      crypto 1.17x · equity 0.78x · commodity 0.38x
```

Nothing but asset class, and that is mostly volatility. **There is no fire-time
fingerprint for these.**

After three days there is one — a signal that rose >3% in the first 3 days has a
**39.3%** blow-up rate against **11.6%** if it fell >3% (3.4x). But it is too late
to profit: from day 3 that strong group's median forward return is **−2.33%** and
its class-relative alpha is +0.33%, indistinguishable from zero. The breakout is
already in the price.

### Correction: a look-ahead trap in the first cut

The first pass showed "never crossed zero" as a powerful predictor (+6.66% forward).
That was wrong. `bars_to_zero_cross` spans the whole 14d window, so the status is
not knowable on day 3. Restricted to *crossed by day 3*, **the effect reverses**
(+0.10% not-yet-crossed vs +4.81% crossed). Recorded because the same trap is
waiting in any forward-window column: `bars_to_zero_cross`,
`max_favorable_move_pct`, `max_adverse_move_pct` and `outcome_updated_at` are all
horizon-scoped and none of them may be used as a day-N feature.

## 5. Two things that fell out

**A take-profit point.** When a bearish signal works early (price fell >3%) *and*
the MACD has crossed zero by day 3, the next 11 days return **+4.81%** (median
+3.26%, **+2.18% above class**). Knowable on day 3. The signal completing is a
take-profit trigger, not a reason to hold — the move is spent and price
mean-reverts.

### Can the take-profit setup be diagnosed at fire time? Mostly no

Asked of the cohort above (n=489, forward +4.94%): what were `hist % of price`,
`signal ÷ ATR` and `signal % of price` when these fired? Medians, against every
other bearish signal:

| fire-time metric | take-profit cohort | all other bearish | shift |
|---|---|---|---|
| histogram % of price | +0.553% | +0.529% | +0.024 |
| peak % of price | +1.266% | +1.447% | −0.181 |
| **signal ÷ ATR** | **−0.405** | **+0.024** | **−0.429** |
| **signal % of price** | **−2.955%** | **+0.131%** | **−3.086** |
| reduction from peak | 0.545 | 0.547 | −0.002 |
| RSI at fire | 43.8 | 51.4 | −7.6 |

The two signal-line metrics look like a powerful diagnostic — in-cohort rate runs
from **34.4%** in the lowest signal/ATR quintile to **0.0%** in the highest, a lift
of 1.91x down to zero.

**It is very close to a tautology, and must not be used as a finding.** The cohort
*requires* a zero cross by day 3. And:

```
corr(signal/ATR, macd/ATR) = 0.9897        median |hist|/ATR = 0.102

P(MACD crosses zero by day 3):
  macd/ATR -1.75..-0.48  100.0%      sig/ATR -1.80..-0.57  100.0%
  macd/ATR -0.17..+0.20   65.6%      sig/ATR -0.27..+0.08   63.0%
  macd/ATR +0.61..+2.21    0.0%      sig/ATR +0.45..+2.01    0.0%
```

Because `hist` is tiny at fire (median 0.102 ATR), `signal ≈ macd`, and the two
curves are the same curve. "Low signal/ATR predicts the cohort" restates "a MACD
already below zero crosses zero quickly." No information is added.

**Histogram % of price carries nothing** — quintile lift 0.76x–1.21x, non-monotone,
and the medians are 0.553% vs 0.529%. It is not a discriminator.

**And nothing sharpens the cohort from the inside.** Splitting the 489 into terciles:

```
by signal/ATR   -1.80..-0.61  n=163  fwd +6.84%  CI [+4.41, +8.92]
                -0.61..-0.28  n=163  fwd +2.85%  CI [+0.61, +4.93]
                -0.28..+0.41  n=163  fwd +5.13%  CI [+2.41, +8.12]
```

Non-monotone with overlapping intervals — the middle tercile is the *worst*. That
is noise, not a gradient. `macd/ATR` reproduces it almost exactly (corr 0.99), as
it must.

**A hypothesis that failed, recorded so it isn't retried.** A bearish fire with
`macd < 0` and `hist > 0` is structurally distinct — MACD below zero but above its
signal line, i.e. a *failed bounce inside a downtrend* rather than a topping rally.
Plausible that the two behave differently. They do not:

```
                              n    share   short EV 7d   blow-up   LONG alpha 7d
macd < 0 (failed bounce)   1347    43.6%        -1.73%     21.9%   +1.96% [+1.10, +2.89]
macd > 0 (topping rally)   1739    56.4%        -2.90%     19.2%   +2.12% [+1.07, +3.17]
```

Long alphas are indistinguishable and the intervals nest. Worse, on split-half the
`macd < 0` half *fails* (H1 +0.76% [−0.18, +1.64], includes zero) while `macd > 0`
survives both. So the MACD sign is not a useful filter, and if anything the classic
topping-rally setup is the more robust of the two.

**What this leaves.** The fire-time half of the recipe is free rather than
predictive: select bearish fires with `macd/ATR` below roughly −0.2 and the
zero-cross condition is all but guaranteed. The binding constraint is the >3% price
fall by day 3, which §4 already established has no fire-time fingerprint. **The
setup is reproducible as a rule you wait for, not one you select at fire time.**

*Multiple-comparisons warning:* between §4 and here, roughly a dozen fire-time
features have now been tested against this cohort. At that count something crosses
a 95% threshold by chance alone. Only the tautological separations were large, and
they are excluded by construction — treat any future "one more feature" result from
this cohort as a hypothesis needing fresh data, not a finding.

**Stops help less than expected.**

```
hold to 14d (current)      mean -2.49%   median -0.10%   worst-5% -28.4%
exit if up >0% at day 3    mean -1.71%   median -1.41%   worst-5% -21.1%   cuts 45.7%
```

The mean improves and the **median gets worse** — you cut trades that would have
recovered. Simulated on daily closes only, so a real intraday stop fills worse; no
fees or funding.

## 6. The flip: long the bearish signals

Corrected against the class **mean**. The original version of this section used the
median benchmark and reported +2.11% surviving both halves; that is withdrawn.

```
cohort                half      n    alpha   median   day-block 95% CI   excl.0
LONG bearish (flip)   all    2911   +0.86%   -0.51%   [+0.12, +1.62]     yes
                      H1     1292   +0.24%   -0.47%   [-0.50, +0.98]     NO
                      H2     1619   +1.36%   -0.54%   [+0.23, +2.48]     yes
LONG bullish          all    2154   -1.06%   -2.04%   [-1.67, -0.42]     yes
                      H1     1163   -2.08%   -3.00%   [-2.79, -1.39]     yes
                      H2      991   +0.15%   -0.95%   [-0.77, +1.08]     NO
```

**The flip does not survive split-half.** H1 includes zero. The full-sample +0.86%
rests on H2 alone, which is exactly the pattern a regime artifact produces.

Worse for any trading use: the **median** flip trade has alpha of **−0.51%**. More
than half of them underperform simply buying the class. The positive mean is carried
by a right tail that §3 now shows is not signal-driven — it is the asset
distribution's own tail, available to a random pick.

~~The inverted bearish signal is a better long than the actual bullish signal.~~ It
is better than bullish (−1.06%), but "better than a significantly negative number"
is not an edge.

### What the payoff actually looks like

```
p5 -12.9%   p25 -4.7%   p50 +0.3%   p75 +6.5%   p95 +26.8%
mean +2.44%   share profitable 51.5%
```

This is **not a steady edge**. Win rate is barely a coin flip, half of all trades
land between −4.7% and +6.5%, and the mean sits +2.16pp above the median. It is a
positive-skew, right-tail-carried profile: most trades go nowhere, and the return
comes from occasionally catching a runner. Position sizing and survivorship of the
drawdowns matter more than entry precision.

### What this does and does not license

**Does:** stop treating a bearish fire as a short setup — shorts lost in this
window, and the short-side alpha is significantly negative.

**Does NOT:** support flipping to a long. That was the original conclusion and it is
withdrawn. The long side fails split-half, its median trade is negative, and the
`>10%` tail that carries its mean is available from a random pick on the same
class-day. Four holes, the first two fatal:

0. **It fails split-half** (H1 +0.24%, CI includes zero) once the benchmark is
   unbiased.
0. **The median trade loses to the class** (−0.51%). The mean is a tail artifact.

3. **Both halves are the same regime.** Split-half tests *time stability*, not
   *regime robustness*. June–September 2026 was one crypto uptrend. "Fading
   strength fails" is precisely what a trending market produces, and precisely what
   would reverse in a chop or a downtrend. This is the single biggest risk to the
   finding.
4. **Effect size is unstable even inside that regime** — H1 +0.24% vs H2 +1.36%.
5. **Funding is not measured.** These are perps; a sustained long in a bull market
   pays funding continuously, and we store no funding data (`runs`,
   `asset_snapshots`, `signals` have no funding column). At typical perp funding a
   7-day hold would eat most or all of a +0.86% alpha on its own. **There is very
   likely nothing left net of carry.**

Also unmeasured: fees, slippage, borrow, and the fact that every number here is a
close-to-close paper return on a signal that fired intraday on a forming bar.

## Suggested next step

The analysis says *what happened*. Turning it into something testable needs a rule
specification — entry, exit, sizing, and which subset of bearish fires to take —
and that is a trading decision rather than an analytical one.

<!-- TODO(human): specify the candidate rule to measure next. -->

**Candidate rule to backtest (to be filled in):**

```
cohort   :
entry    :
exit     :
sizing   :
skip if  :
```

Once that is specified it can be measured against the same benchmark and split-half
machinery used above, and the answer will be directly comparable to the numbers in
§6.

## Method notes

- **Benchmark** = per `(asset_class, UTC day)` **mean** forward move of every symbol
  in that class, built from `asset_snapshots` daily closes (earliest run per symbol
  per day), requiring ≥20 symbols in a cell. `alpha = sign × (raw_move − benchmark)`.
  **Use the mean, never the median.** Returns are right-skewed (pool mean exceeds
  pool median by an average of +0.97pp at 7d across 184 class-day pools), so a
  median benchmark hands any selection — including a random one — about +1.10% of
  free "alpha". This was the central error in the first version of this document.
- **Always compute the counterfactual.** For any rate-based claim ("X% of signals
  do Y"), measure the same rate over every same-class same-day asset before calling
  it a finding. The 20% blow-up rate looked alarming and turned out to be exactly
  the base rate.
- **Check thresholds against volatility.** A `>10%` cut sounds decisive but is 1.6
  daily ATRs on assets with a 6.14% median ATR. Absolute thresholds on
  high-volatility assets select noise.
- **Day-block bootstrap** everywhere, 2000–3000 resamples. Forward windows overlap,
  so observations cluster within a day; resampling whole UTC days keeps the cluster
  intact. A plain per-signal bootstrap is materially too narrow here and would have
  reported significance that is not there.
- **Split-half** on calendar days, H1/H2 either side of 2026-07-22.
- **Snapshot state matters.** An earlier pass at §Headline and §2 was run against
  the *previous* daily sync and reported slightly different magnitudes (bullish
  alpha +0.001%, bearish −2.178%). Every number in this document is from the
  2026-09-10 13:00 snapshot; if you re-run after a later sync, expect the
  magnitudes to move again while the signs and orderings hold. Cite the snapshot
  date with any figure taken from here.
- MFE/MAE are stored as **fractions**, not percent (avg bearish MFE +0.09 = 9%).
- Cohort is `_base()`: post-`DETECTOR_FIX_CUTOFF`, `stage='histogram_flattening'`,
  deduped to the earliest fire per (symbol, direction, UTC-day).

## Known errors in `regime_consistency_analysis.md`

Flagged repeatedly, still uncorrected there — do not read that file's §1 without
these:

1. The 14d alphas were computed against a **7d benchmark**. Corrected values:
   crypto-confident +0.87% / +1.23%, equity +0.50% / −0.45%.
2. Consequently the claim that *"alpha is negative in all four cells"* for equity is
   **false**.
3. Neither of that document's two headline findings survives beta adjustment, which
   it does not mention.
