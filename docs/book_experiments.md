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
- Baseline: every leg held 14 days. Sharpe 1.42, CAGR +36.9%, max drawdown −18%.

Each variant has a paired 30-day block bootstrap against the baseline. It also has the
Sharpe change in 2023–24 and in 2025–26. A variant counts only if it helps in both
halves. The legs come from this same history, so all results are in-sample.

## Headline

1. **Listing age is the one tangible result.** Give 1.5× weight to longs in coins
   that Hyperliquid listed 2 or more years ago. Give 1.5× weight to shorts in coins
   that it listed less than 1 year ago. Keep all other names at 1×. Sharpe goes from
   1.42 to 1.65 (**+0.23 [+0.03, +0.42]**), positive in both halves (+0.29 / +0.15).
   Max drawdown does not change. The probable mechanism is token supply (§3).
2. **A filter on listing age does not work, but a tilt does.** The filter removes 45%
   of the longs. The book then loses the breadth that its Sharpe needs, and 2025–26
   becomes worse.
3. **Book-level risk controls do not help.** Volatility targets, an equity-curve
   filter, inverse-volatility weights, and beta-neutral sides do not improve both
   halves. B3 earns most when cross-sectional dispersion is high, and its risk also
   increases then. A volatility target cuts exposure exactly when the book earns most.
4. **Two execution variants give small or uncertain gains.**
   - A universe basket on the thin side: +0.05 Sharpe, positive in both halves.
   - A 25% drift band: 17% less turnover, but the Sharpe change is noise.
5. **These entry filters do not help:** same-day fire clusters and re-fires after
   entry. Weekend fires show a pattern, but it has no consistent mechanism.

## 1. Position size and risk control

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

All weights use only data from the close before the trade day. The volatility target
uses the trailing volatility of the book without the target, and an expanding median
as its level. A resize of the book also pays costs.

**Why volatility does not help here.** Split the days into terciles by trailing
30-day cross-sectional dispersion:

| trailing dispersion | B3 mean a day | B3 volatility a day | Sharpe |
|---|---|---|---|
| low | +5.5 bp | 104 bp | 1.01 |
| middle | +10.3 bp | 125 bp | 1.58 |
| high | +13.4 bp | 150 bp | 1.70 |

The return increases as fast as the variance, so mean ÷ variance is almost constant
(5.1, 6.6 and 6.0 × 10⁻⁴). The best weight in a mean-variance sense is mean ÷
variance. B3 is therefore already near its best exposure over time. A volatility target
decreases exposure when dispersion is high, and that is when B3 earns most. The
`peak_pct` legs sort coins against each other, and that sort has more to work with
when coins move apart.

**Why inverse-volatility weights fail.** High-volatility coins do badly as longs and
well as shorts. Fires and non-fires show the same pattern, so this is the generic
low-volatility effect. Inverse-volatility weights decrease both: they help the longs
and hurt the shorts. Beta-neutral sides have no beta to remove. The mean beta is 0.99
on the long side and 0.98 on the short side. A beta match only adds the noise of the
60-day beta estimates.

**No strategy momentum.** B3's monthly returns have autocorrelation −0.21, and its
weekly returns about 0. Thus the equity-curve filter only removes good months.

**The universe basket on the thin side** uses capital that is otherwise in cash. It
adds the thick side's alpha at full size. The gain is small because both sides often
have 10 or more names, and then nothing changes. The backtest does not charge for the
daily rebalance of the basket, the same as profit_strategies.md B2.

## 2. Entry filters

These checks are per trade: first fires, alpha to day 14, and the same-state non-fires
as the counterfactual.

- **Same-day clusters.** Split each leg by the share of the universe that fires the
  same leg on that day. No leg has less alpha on cluster days. L2 has its most stable
  alpha on cluster days (+1.01 [+0.42, +1.61], 2,599 episodes).
- **Re-fire after entry.** H9 says that bearish re-fires are signs of strength. Then a
  re-fire in days 1–2 should be bad for an S1 short and good for an L2 long. The S1
  result shows no effect (+0.92 vs +0.83). L2 shows the expected sign (+0.72 vs +0.16
  from bar 2 to day 14), but only 20% of the trades have no re-fire. S2 changes sign
  between the halves.
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
  Sharpe 0.06. It lost 21% in 2023 and 19% in 2024. A short basket of young coins
  sometimes holds a coin that goes up 5x.

**As a portfolio:**

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

- **The tilt keeps all names, and the filter does not.** The filter cuts the long
  side from 32 to 18 names, and the thin-side rule then makes the whole book smaller.
  The tilt moves weight inside each side, so the book keeps its breadth.
- **Each half of the tilt helps alone, in both halves of the history.**
- **It is not only "majors beat alts".** If the pre-2021 listings get no extra weight,
  the gain decreases to +0.13, and it stays positive in both halves.
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
- The 2025–26 gain is about half the 2023–24 gain.

## 4. What to do

- **Register the age tilt on the watchlist before you use it.** The live research
  frame has no listing age yet. Its candle cache starts on 2025-08-01. Get the first
  candle date from `state/research_cache/history/` and add it as a fire-time feature.
  Then register these checks:
  1. L2 first fires on coins listed ≥ 2 years minus L2 first fires on younger coins:
     alpha > 0.
  2. S1 and S2 first fires on coins listed < 1 year minus older coins: short-side
     alpha > 0.
- **Add the tilt to the backtester as an execution variant** (trading_strategy.md
  §8.2), with the weights 1× and 1.5×. Do not use 2×. Its interval is wider and it
  increases concentration.
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
