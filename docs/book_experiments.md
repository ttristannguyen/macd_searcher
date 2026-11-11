# B3 experiments: position size, risk control, and filters

Research doc, 2026-10-30. This doc follows [exit_research.md](exit_research.md). It
tests how to size, filter, and control the B3 book
([trading_strategy.md](trading_strategy.md)) to increase gains or decrease losses. It
does not change the four legs.

**Data and method.** The data, the backtest, and the baseline are the same as in
exit_research.md:
- Fires: 2023-03-02 → 2026-10-08, first fire per episode.
- Candles: to 2026-10-24.
- Book: both sides sized to the thinner side, 0.10% a side, flat funding.
- Baseline: every leg held 14 days. Sharpe ~~1.42~~ 1.50, CAGR ~~+36.9%~~ +38.5%, max
  drawdown −18%.

Each variant has a paired 30-day block bootstrap against the baseline. It also has the
Sharpe change in 2023–24 and in 2025–26. A variant counts only if it helps in both
halves. The legs come from this same history, so all results are in-sample.

**Re-anchored 2026-11-03.** The portfolio numbers in the headline, §1 and §3 now come
from the committed backtester, `research/backtest.py` at commit `9238751`.
`scripts/backtest_tables.py` prints each table. The backtester ends a hold at the close
of fire day + 14, and runs fires and returns from 2023-02-28 to 2026-10-15
(exit_research.md, "Backtest"). Superseded values are struck through, or kept in a
"Superseded" block below their table. ⚠ marks a comparison whose sign changed. The
per-trade results in §2 and §3 did not change.

**Fixed 2026-11-04.** A tilt can push a name above the 10% cap. The backtester cut that
name to 10%, and the excess went to cash. Thus the tilted side was smaller than the
other side, and the book was not dollar-neutral:
- The 1.5× age tilt was net long or net short on 27% of days, by up to 10%.
- The 1/volatility weights were net long or net short on 64% of days, by up to 30%.

Now the excess moves to the other names of the same side (`_capped` in
`research/backtest.py`). On a thinner side of 10 names or fewer, each name is at the
cap, so a tilt cannot act there. Only the 8 rows with a tilt change. Their superseded
values are in a block below each table.

## Headline

1. **Listing age is the one tangible result.** Give 1.5× weight to longs in coins
   that Hyperliquid listed 2 or more years ago. Give 1.5× weight to shorts in coins
   that it listed less than 1 year ago. Keep all other names at 1×. Sharpe goes from
   ~~1.42 to 1.65 (+0.23 [+0.03, +0.42])~~ ~~1.50 to 1.69 (+0.19 [−0.01, +0.40])~~
   1.50 to 1.66 (**+0.17 [−0.01, +0.35]**), positive in both halves (~~+0.29~~
   ~~+0.23~~ +0.16 / ~~+0.15~~ +0.18). The interval now includes zero. Max drawdown
   ~~does not change~~ goes from −18% to −20%. The probable mechanism is token supply
   (§3). After the cap fix, the long half alone gives +0.13 [+0.01, +0.26], and the
   short half alone is −0.01 in 2023–24.
2. **A filter on listing age does not work, but a tilt does.** The filter removes
   ~~45%~~ 42% of the longs. The book then loses the breadth that its Sharpe needs, and
   2025–26 becomes worse.
3. **Book-level risk controls do not help.** Volatility targets, an equity-curve
   filter, inverse-volatility weights, and beta-neutral sides do not improve both
   halves. The one exception is the 1/√(volatility) weights (+0.01 / +0.06, after the
   cap fix), and they add +0.00 overall. B3 earns most when cross-sectional dispersion
   is high, and its risk also increases then. A volatility target cuts exposure
   exactly when the book earns most.
4. **Two execution variants give small or uncertain gains.**
   - A universe basket on the thin side: ~~+0.05~~ +0.01 Sharpe, positive in both
     halves. The committed backtester charges the daily rebalance of the basket.
   - A 25% drift band: ~~17%~~ 18% less turnover, but the Sharpe change is noise.
5. **These entry filters do not help:** same-day fire clusters and re-fires after
   entry. Weekend fires show a pattern, but it has no consistent mechanism.

## 1. Position size and risk control

*Backtester `9238751`, 2026-11-03. The two tilt rows: the cap fix, 2026-11-04.*
Turnover is the change against the baseline's 129x a year.

| variant | Sharpe | Δ vs baseline [95%] | Δ 2023–24 | Δ 2025–26 | CAGR | max DD | turnover |
|---|---|---|---|---|---|---|---|
| **baseline** | 1.50 | — | — | — | +38.5% | −18% | — |
| weights ∝ 1 / 20-day volatility ⚠ | 1.43 | −0.07 [−0.39, +0.31] | −0.06 | +0.00 | +32.5% | −17% | +5% |
| weights ∝ 1 / √(20-day volatility) ⚠ | 1.50 | +0.00 [−0.17, +0.21] | +0.01 | +0.06 | +35.6% | −17% | +2% |
| beta-neutral sides (60-day beta to the universe) | 1.36 | −0.13 [−0.51, +0.22] | −0.02 | −0.19 | +33.9% | −27% | +3% |
| volatility target, 30 days, leverage cap 2 | 1.54 | +0.04 [−0.34, +0.40] | −0.08 | −0.15 | +34.5% | −21% | −8% |
| volatility target, 30 days, leverage cap 1 | 1.57 | +0.08 [−0.20, +0.36] | −0.06 | −0.07 | +31.8% | −18% | −18% |
| volatility target, 60 days, leverage cap 2 | 1.50 | +0.00 [−0.24, +0.21] | −0.07 | −0.18 | +33.4% | −17% | −12% |
| equity-curve filter (on only if the last 60 days > 0) | 1.04 | −0.46 [−0.96, +0.04] | −1.03 | −0.21 | +21.0% | −28% | −13% |
| thin side filled with the universe basket | 1.50 | +0.01 [−0.10, +0.11] | +0.06 | +0.01 | +39.9% | −19% | +10% |
| drift band 25% ⚠ | 1.53 | +0.03 [−0.28, +0.35] | +0.04 | +0.03 | +41.6% | −20% | −18% |
| drift band 50% | 1.27 | −0.22 [−0.83, +0.39] | +0.40 | −0.88 | +37.1% | −25% | −29% |

⚠ Two half-year signs changed, and no full-period sign changed. The 1/√(volatility)
weights were +0.02 in 2023–24 and are now −0.02. The 25% band was −0.01 in 2023–24 and
is now +0.04, so it is now positive in both halves. Its interval is still wide, so it
stays noise.

*2026-11-04, the cap fix:* three signs changed. The 1/volatility weights went from
−0.14 to +0.00 in 2025–26. The 1/√(volatility) weights went from −0.04 to +0.00
overall, and from −0.02 to +0.01 in 2023–24. Neither row is a gain.

<details><summary>Superseded: backtester `9238751` before the cap fix</summary>

| variant | Sharpe | Δ vs baseline [95%] | Δ 2023–24 | Δ 2025–26 | CAGR | max DD | turnover |
|---|---|---|---|---|---|---|---|
| weights ∝ 1 / 20-day volatility | 1.33 | −0.17 [−0.58, +0.28] | −0.14 | −0.14 | +29.7% | −22% | +1% |
| weights ∝ 1 / √(20-day volatility) | 1.46 | −0.04 [−0.24, +0.20] | −0.02 | +0.01 | +34.2% | −18% | +0% |

</details>

<details><summary>Superseded: the scratch build of 2026-10-30</summary>

| variant | Sharpe | Δ vs baseline [95%] | Δ 2023–24 | Δ 2025–26 | CAGR | max DD |
|---|---|---|---|---|---|---|
| **baseline** | 1.42 | — | — | — | +36.9% | −18% |
| weights ∝ 1 / 20-day volatility | 1.32 | −0.11 [−0.48, +0.36] | −0.06 | −0.10 | +29.9% | −21% |
| weights ∝ 1 / √(20-day volatility) | 1.41 | −0.01 [−0.19, +0.23] | +0.02 | +0.01 | +33.4% | −17% |
| beta-neutral sides (60-day beta to the universe) | 1.28 | −0.14 [−0.51, +0.20] | −0.01 | −0.21 | +32.1% | −25% |
| volatility target, 30 days, leverage cap 2 | 1.49 | +0.07 [−0.30, +0.44] | −0.04 | −0.14 | +33.8% | −19% |
| volatility target, 30 days, leverage cap 1 | 1.52 | +0.10 [−0.19, +0.39] | −0.02 | −0.06 | +31.1% | −17% |
| volatility target, 60 days, leverage cap 2 | 1.43 | +0.00 [−0.25, +0.21] | −0.06 | −0.18 | +31.7% | −16% |
| equity-curve filter (on only if the last 60 days > 0) | 1.04 | | −0.70 | −0.34 | | |
| thin side filled with the universe basket | 1.47 | +0.05 [−0.08, +0.18] | +0.12 | +0.03 | +39.7% | −18% |
| drift band 25% | 1.51 | +0.09 [−0.23, +0.38] | −0.01 | +0.19 | +41.5% | −22% |
| drift band 50% | 1.25 | −0.17 [−0.81, +0.50] | +0.25 | −0.64 | +36.7% | −26% |

</details>

All weights use only data from the close before the trade day. The volatility target
uses the trailing volatility of the book without the target, and an expanding median
as its level. A resize of the book also pays costs.

**Why volatility does not help here.** Split the days into terciles by trailing
30-day cross-sectional dispersion (*backtester `9238751`*):

| trailing dispersion | B3 mean a day | B3 volatility a day | Sharpe | mean ÷ variance |
|---|---|---|---|---|
| low | +5.9 bp | 103 bp | 1.10 | 5.6 |
| middle | +8.8 bp | 124 bp | 1.35 | 5.7 |
| high | +15.4 bp | 144 bp | 2.04 | 7.4 |

<details><summary>Superseded: the scratch build of 2026-10-30</summary>

| trailing dispersion | B3 mean a day | B3 volatility a day | Sharpe |
|---|---|---|---|
| low | +5.5 bp | 104 bp | 1.01 |
| middle | +10.3 bp | 125 bp | 1.58 |
| high | +13.4 bp | 150 bp | 1.70 |

</details>

The return increases as fast as the variance, so mean ÷ variance is almost constant
(~~5.1, 6.6 and 6.0 × 10⁻⁴~~). The best weight in a mean-variance sense is mean ÷
variance. ~~B3 is therefore already near its best exposure over time.~~ A volatility
target decreases exposure when dispersion is high, and that is when B3 earns most. The
`peak_pct` legs sort coins against each other, and that sort has more to work with
when coins move apart.

*2026-11-03:* mean ÷ variance (daily returns) is now 5.6, 5.7 and 7.4. It is constant
in the low and middle terciles, and 30% higher in the high tercile. Thus the best
exposure is the same or higher when dispersion is high. A volatility target does the
opposite, so the conclusion does not change.

**Why inverse-volatility weights fail.** High-volatility coins do badly as longs and
well as shorts. Fires and non-fires show the same pattern, so this is the generic
low-volatility effect. Inverse-volatility weights decrease both: they help the longs
and hurt the shorts. Beta-neutral sides have no beta to remove. The mean beta is 0.99
on the long side and 0.98 on the short side. A beta match only adds the noise of the
60-day beta estimates.

*2026-11-04:* most of the old −0.17 of the 1/volatility weights came from the cap
error, not from this effect. With the fix, the change is −0.07 [−0.39, +0.31].

**No strategy momentum.** B3's monthly returns have autocorrelation ~~−0.21~~ −0.15,
and its weekly returns ~~about 0~~ −0.05. Thus the equity-curve filter only removes good
months.

**The universe basket on the thin side** uses capital that is otherwise in cash. It
adds the thick side's alpha at full size. The gain is small because both sides often
have 10 or more names, and then nothing changes. ~~The backtest does not charge for the
daily rebalance of the basket, the same as profit_strategies.md B2.~~ The committed
backtester charges the daily rebalance of the basket, at 0.10% a side. The basket adds
10% to turnover, and the gain decreases from +0.05 to +0.01.

## 2. Entry filters

These checks are per trade: first fires, alpha to day 14, and the same-state non-fires
as the counterfactual.

- **Same-day clusters.** Split each leg by the share of the universe that fires the
  same leg on that day. No leg has less alpha on cluster days. L2 has its most stable
  alpha on cluster days (+1.01 [+0.42, +1.61], 2,599 episodes).
- **Re-fire after entry.** H9 says that bearish re-fires are signs of strength. Then a
  re-fire in days 1–2 should be bad for an S1 short and good for an L2 long. The
  values are alpha in the trade direction, from bar 2 to day 14, with re-fire vs no
  re-fire:
  - *S1:* no effect (+0.92 vs +0.83).
  - *L2:* the result agrees. L2 trades with a re-fire earn more alpha than L2 trades
    without one (+0.72 vs +0.16). But only 20% of L2 trades have no re-fire, and they
    still earn +0.16. Thus an exit on them gives nothing.
  - *S2:* the sign changes between the halves.
- **Weekend fires.** L1 and L2 fires on a Saturday or Sunday decision day have about 0
  alpha (L1 −0.05, L2 −0.25), and weekday fires +2.20 and +1.24. Both halves show
  this. But S1 weekend fires are better shorts (+1.81 vs +1.08), and non-fired L2 coins
  show the opposite. No single mechanism explains all four legs. Thus this is an
  observation, not a hypothesis.

## 3. Listing age

**Listing age** is the number of days since the coin's first daily candle on
Hyperliquid. It is known at entry. The history starts on 2021-01-01. Thus all coins
listed before that date (25% of trades, with the majors) show an age from 2021-01-01.

**Per trade (fires), alpha to day 14, 2023–24 / 2025–26 in brackets:**

| leg | listed < 1 year | 1–2 years | > 2 years |
|---|---|---|---|
| L1 long | −0.27 (−0.81 / −0.04) | +2.44 (−2.47 / +3.54) | **+1.62** (+1.43 / +1.68) |
| L2 long | −0.67 (−0.06 / −1.30) | −0.27 (−0.99 / +0.14) | **+1.83** (+1.90 / +1.78) |
| S1 short | **+3.31** (+1.48 / +4.29) | +0.69 | +0.74 (+0.78 / +0.73) |
| S2 short | **+2.14** (+0.31 / +3.28) | +0.36 | +0.24 (−0.24 / +0.47) |

Bold: the 95% interval does not include zero. The longs pay only on old coins, and
the shorts pay most on young coins, in both halves.

**Counterfactuals.**
- *Same-state non-fires* show the same direction, with a larger gap in the L2 state:
  −1.05 (< 1 year), −2.13 (1–2 years), +2.08 (> 2 years). Thus the detector does not
  find this effect. The effect is a property of the coin, and the state makes it
  larger.
- *All eligible coins* (one sample a week) show a smaller effect at 14 days: −0.81
  [−1.69, +0.10] (< 1 year), −0.66 (1–2 years), +0.54 [+0.17, +0.91] (> 2 years).
  In 2023, young coins did better (+0.35 vs −0.13).
- *A book on age alone* (long coins > 2 years, short coins < 1 year, no signals) has
  Sharpe ~~0.06~~ 0.16. It lost ~~21%~~ 17% in 2023 and 19% in 2024. A short basket of
  young coins sometimes holds a coin that goes up 5x. *2026-11-03:* the committed
  backtester holds each day every eligible coin in the two age groups, with the B3
  sizing rules.

**As a portfolio** (*backtester `9238751`, 2026-11-03; tilt rows: cap fix, 2026-11-04*):

| variant | Sharpe | Δ vs baseline [95%] | Δ 2023–24 | Δ 2025–26 | CAGR | max DD | names L / S |
|---|---|---|---|---|---|---|---|
| longs only if listed ≥ 2 years (filter) | 1.79 | +0.30 [−0.30, +0.91] | +0.89 | −0.31 | +51.2% | −21% | 19 / 29 |
| longs only if listed ≥ 1 year (filter) | 1.75 | +0.25 [−0.08, +0.59] | +0.58 | −0.12 | +47.3% | −20% | 28 / 28 |
| **tilt 1.5×: old longs, young shorts** | **1.66** | **+0.17 [−0.01, +0.35]** | **+0.16** | **+0.18** | +45.2% | −20% | 33 / 28 |
| tilt 2×: old longs, young shorts | 1.76 | +0.27 [−0.02, +0.56] | +0.28 | +0.26 | +50.6% | −22% | 33 / 28 |
| tilt 1.5×, pre-2021 listings not given more weight | 1.57 | +0.07 [−0.08, +0.23] | +0.01 | +0.15 | +42.1% | −21% | 33 / 28 |
| tilt 1.5×, longs only | 1.63 | +0.13 [+0.01, +0.26] | +0.17 | +0.09 | +42.9% | −18% | 33 / 28 |
| tilt 1.5×, shorts only ⚠ | 1.54 | +0.04 [−0.07, +0.16] | −0.01 | +0.10 | +40.7% | −20% | 33 / 28 |
| shorts 21 days (exit_research.md) | 1.66 | +0.17 [−0.09, +0.40] | +0.09 | +0.25 | +42.8% | −21% | 33 / 33 |
| shorts 21 days + tilt 1.5× | 1.82 | +0.16 [−0.02, +0.35] vs shorts 21 | +0.16 | +0.17 | +49.5% | −20% | 33 / 33 |

No sign changed. The 1.5× tilt lost its clear interval: its lower end moved from +0.03
to −0.01. It is still positive in both halves. The baseline holds 33 / 28 names.

*2026-11-04, the cap fix:* one sign changed. The shorts-only tilt went from +0.06 to
−0.01 in 2023–24 (⚠). The 1.5× tilt is still positive in both halves.

<details><summary>Superseded: backtester `9238751` before the cap fix</summary>

| variant | Sharpe | Δ vs baseline [95%] | Δ 2023–24 | Δ 2025–26 | CAGR | max DD | names L / S |
|---|---|---|---|---|---|---|---|
| **tilt 1.5×: old longs, young shorts** | **1.69** | **+0.19 [−0.01, +0.40]** | **+0.23** | **+0.15** | +45.7% | −20% | 33 / 28 |
| tilt 2×: old longs, young shorts | 1.79 | +0.30 [−0.04, +0.65] | +0.44 | +0.16 | +51.4% | −20% | 33 / 28 |
| tilt 1.5×, pre-2021 listings not given more weight | 1.61 | +0.11 [−0.06, +0.29] | +0.10 | +0.13 | +43.2% | −21% | 33 / 28 |
| tilt 1.5×, longs only | 1.62 | +0.12 [−0.01, +0.26] | +0.18 | +0.07 | +42.5% | −19% | 33 / 28 |
| tilt 1.5×, shorts only | 1.57 | +0.07 [−0.05, +0.20] | +0.06 | +0.09 | +41.6% | −19% | 33 / 28 |
| shorts 21 days + tilt 1.5× | 1.81 | +0.15 [−0.06, +0.36] vs shorts 21 | +0.17 | +0.13 | +49.0% | −21% | 33 / 33 |

</details>

<details><summary>Superseded: the scratch build of 2026-10-30</summary>

| variant | Sharpe | Δ vs baseline [95%] | Δ 2023–24 | Δ 2025–26 | CAGR | names L / S |
|---|---|---|---|---|---|---|
| longs only if listed ≥ 2 years (filter) | 1.73 | +0.31 [−0.35, +0.93] | +0.92 | −0.33 | +49.5% | 18 / 28 |
| longs only if listed ≥ 1 year (filter) | 1.65 | +0.23 [−0.08, +0.54] | +0.51 | −0.10 | +44.5% | 27 / 27 |
| **tilt 1.5×: old longs, young shorts** | **1.65** | **+0.23 [+0.03, +0.42]** | **+0.29** | **+0.15** | +45.1% | 32 / 27 |
| tilt 2×: old longs, young shorts | 1.75 | +0.33 [−0.00, +0.66] | +0.50 | +0.15 | +50.5% | 32 / 27 |
| tilt 1.5×, pre-2021 listings not given more weight | 1.55 | +0.13 [−0.03, +0.30] | +0.15 | +0.12 | +42.2% | 32 / 27 |
| tilt 1.5×, longs only | 1.55 | +0.12 [−0.02, +0.26] | +0.21 | +0.04 | +40.9% | 32 / 27 |
| tilt 1.5×, shorts only | 1.53 | +0.11 [−0.01, +0.23] | +0.09 | +0.12 | +41.0% | 32 / 27 |
| shorts 21 days (exit_research.md) | 1.70 | | | | +44.6% | 32 / 32 |
| shorts 21 days + tilt 1.5× | 1.86 | +0.17 [−0.06, +0.37] vs shorts 21 | +0.22 | +0.10 | +51.4% | 32 / 32 |

</details>

- **The tilt keeps all names, and the filter does not.** The filter cuts the long
  side from ~~32 to 18~~ 33 to 19 names, and the thin-side rule then makes the whole
  book smaller. The tilt moves weight inside each side, so the book keeps its breadth.
- **The tilt cannot act on a thin side of 10 names or fewer.** Each name on that side
  is at the 10% cap. In 2023–24, the short side is at the cap on 30% of days, and the
  long side on 25%. In 2025–26, each side is at the cap on 6% of days.
- ~~**Each half of the tilt helps alone, in both halves of the history.**~~
  *2026-11-04:* only the long half helps alone in both halves (+0.17 / +0.09). The
  short half is −0.01 in 2023–24 and +0.10 in 2025–26.
- **It is not only "majors beat alts".** If the pre-2021 listings get no extra weight,
  the gain decreases to ~~+0.13~~ ~~+0.11~~ +0.07, and it stays positive in both
  halves. *2026-11-04:* but in 2023–24, almost none of the gain stays (+0.01 of
  +0.16). Pre-2021 listings are 62% of the old long first fires in 2023–24, and 31% in
  2025–26. Thus, in 2023–24, this check cannot separate listing age from the pre-2021
  coins. In 2025–26, +0.15 of the +0.18 stays.
- *Mechanism (hypothesis):* young tokens have a low float and scheduled unlocks.
  Holders sell into strength. Thus a strong trend in a young coin fails (L2), and a
  pullback does not recover (L1). Weakness in a young coin has no buyer support. Thus
  it continues (S1, S2). Old coins have most of their supply in circulation, and their
  trends continue. This explains why the effect is largest in the L2 state, where
  strength meets supply. It also explains why age alone does not make a book. Outside
  these states, young coins sometimes go up a lot.

**Limits.**
- The Hyperliquid listing date is not the token's launch date. An old token that
  Hyperliquid listed late shows as young. A better measure is the share of supply in
  circulation, but this repo has no data for it.
- The cuts (1 year and 2 years) are round numbers. But we selected the preferred
  bucket for each side after we saw the per-trade table.
- The 2025–26 gain is about ~~half~~ ~~two-thirds of~~ the same as the 2023–24 gain
  (+0.18 / +0.16, 2026-11-04).

## 4. What to do

- **Register the age tilt on the watchlist before you use it.** The live research
  frame has no listing age yet. Its candle cache starts on 2025-08-01. Get the first
  candle date from `state/research_cache/history/` and add it as a fire-time feature.
  Then register these checks:
  1. L2 first fires on coins listed ≥ 2 years minus L2 first fires on younger coins:
     alpha > 0.
  2. S1 and S2 first fires on coins listed < 1 year minus older coins: short-side
     alpha > 0.

  *Done 2026-11-09:* `dataset.attach_listing_age` adds `listed_days`. The watchlist has
  three checks, one each for L2, S1 and S2 (strategy_search.md).
- **Add the tilt to the backtester as an execution variant** (trading_strategy.md
  §8.2), with the weights 1× and 1.5×. Do not use 2×. Its interval is wider and it
  increases concentration. *Done 2026-11-03:* the `tilt` argument of
  `research/backtest.py`. `scripts/backtest_tables.py` has the age tilt. *Fixed
  2026-11-04:* the weight above the cap stays in its side.
- **Do not add** volatility targets, equity-curve filters, inverse-volatility weights,
  beta-neutral sides, or cluster filters.
- **Keep the universe basket on the thin side as a §8.2 variant.** Its gain is small,
  but it does not decrease the Sharpe in either half.

## Reproduction

The scripts are scratch and are not in git, the same as for the earlier passes.
Inputs:
- `state/research_cache/history/*.csv`, with `state/research_cache/candles/` for the
  bars from 2026-10-16 to 10-24.
- The coin-day panel from exit_research.md.

The listing age comes from the first row of each history CSV.

*2026-11-03:* the portfolio numbers (headline, §1 and §3) come from the committed
backtester. Run `uv run python scripts/backtest_tables.py` at commit `9238751`. The
per-trade numbers in §2 and §3 still come from the scratch scripts. *2026-11-04:* the
tilt rows need the cap fix (`_capped` in `research/backtest.py`).
