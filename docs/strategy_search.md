# Strategy search: books that can do better than B3

Research doc, 2026-11-09. This doc tests new methods against B3
([archive/profit_strategies.md](archive/profit_strategies.md)). It follows
[research_method.md](research_method.md). All portfolio numbers come from the committed
backtester, except where the text says "scratch".

**Data.** The frozen panel, 2023-02-28 → 2026-10-15, 234 coins. Costs are 0.10% a side.
Funding is flat, except in §5. The walk-forward model starts on 2024-01-01, so those
tables start on that day. B3 has Sharpe 1.82 on that window, and 1.50 on the full window.

## Headline

1. **Two candidates did better than B3 in the backtester.** No candidate is confirmed.

   | book | window | Sharpe | Δ vs B3 [95%] | CAGR | max DD |
   |---|---|---|---|---|---|
   | B3 | full | 1.50 | — | +38.5% | −18% |
   | **the stack** | full | **2.04** | **+0.54 [+0.08, +0.97]** | +61.0% | −23% |
   | B3 | 2024-01 → | 1.82 | — | +53.8% | −18% |
   | the stack | 2024-01 → | 2.40 | +0.58 [+0.02, +1.09] | +83.6% | −23% |
   | 75% B3 + 25% quality sleeve | 2024-01 → | 2.35 | +0.53 [+0.22, +0.89] | +53.3% | −16% |
   | **75% stack + 25% quality sleeve** | 2024-01 → | **2.87** | **+1.05 [+0.31, +1.78]** | +75.0% | −19% |

2. **The stack adds three rules to B3.** All three are in earlier docs:
   - A long closes when its coin enters S2's band.
   - The shorts stay open for 21 days.
   - The age tilt of 1.5× applies.

   With the bot's execution, the stack has Sharpe 1.99, and B3 has 1.44.
3. **The quality sleeve is new.** It is a market-neutral book on a walk-forward model.
   Each score is out of sample for the model. It has a correlation of about −0.15 with
   B3.
4. **B3's 1.50 is the best of 9 detector settings.** The other 8 settings score from
   −0.04 to 1.32 (§2). Thus expect less than 1.50 from B3.
5. **The evidence has limits (§6).** A family-wise test over 52 books gives p = 0.12 for
   the best book. Thus no book passes at 5%. Nothing changes in the live book.
6. *2026-11-16 (§8):* **no change improves the blend, but its gain is robust.** With real
   funding, the blend has Sharpe 2.85, +0.37 [+0.06, +0.70] against the stack, in both
   halves. The sleeve adds +0.43 to +0.49 on each of the 9 detector settings. The sleeve
   alone falls from 1.44 to 1.14 with real funding, and its funding cost increases each
   year.

## 1. What was tested

The pass tested about 100 books. The directions and the windows were fixed before the
first look at each group.

| group | books | result |
|---|---|---|
| 19 cross-sectional factors: MAX, skew, volatility, residual volatility, beta, nearness to the high, residual momentum, size, illiquidity, volume surge, wicks, trend quality | 19 | best Sharpe 0.55. None helps a blend with B3 in both halves |
| execution: taker for opens or closes, maker for resizes | 4 | none better than the bot's resting orders |
| structure of B3: legs, bands, liquidity floors, combinations | 14 | §3 |
| other detector parameters, and ensembles of them | 12 | §2 |
| trend sleeves: SMA and Donchian on the top 5, 10, 20 coins | 18 | none better than BTC > SMA50 as an overlay |
| walk-forward model: grid, ablation, placebo | 20 | §4 |
| flips: a long that enters S2's band becomes a short | 9 | +0.57 on B3, but negative in 2025–26 on 4 of the 9 settings |
| walk-forward choice of B3's legs | 1 | §2 |

## 2. B3 is the top of its neighbourhood

The first row is B3. Each other row changes one detector parameter. The grid was fixed
before the first look.

| fast / slow / signal / reduction | Sharpe | 2023–24 | 2025–26 |
|---|---|---|---|
| 12 / 26 / 9 / 0.3 (B3) | 1.50 | 0.21 | 2.79 |
| 10 / 22 / 9 / 0.3 | 1.32 | 0.70 | 1.94 |
| 12 / 26 / 9 / 0.4 | 1.17 | −0.31 | 2.63 |
| 12 / 26 / 9 / 0.2 | 1.11 | 0.16 | 2.01 |
| 12 / 26 / 12 / 0.3 | 0.81 | −0.56 | 2.08 |
| 8 / 17 / 9 / 0.3 | 0.76 | 0.67 | 0.87 |
| 12 / 26 / 6 / 0.3 | 0.75 | 0.35 | 1.17 |
| 15 / 30 / 9 / 0.3 | 0.73 | −0.45 | 1.77 |
| 19 / 39 / 9 / 0.3 | −0.04 | −0.61 | 0.56 |

- **The mean ensemble of the books does not help.** The five MACD speeds score 1.27, and
  all nine score 1.27.
- *Why the neighbours are lower (hypothesis):* we fitted the bands of the legs on the
  12 / 26 / 9 fires. The neighbours use the same bands without a fit.
- **B3's structure is real.** A walk-forward choice of the legs starts with no knowledge.
  Each quarter from 2024-01, it trades each band with a past 14-day alpha of |t| > 1.
  By 2025-07 it selects L1, L2, S1 and S2. Its Sharpe is 1.36 on 2024-01 →, and B3 has
  1.82 on that window. Thus 1.36 is a better estimate of the edge than 1.82.

## 3. The stack

| book | Sharpe | Δ vs B3 [95%] | Δ 2023–24 | Δ 2025–26 | CAGR | max DD |
|---|---|---|---|---|---|---|
| B3 | 1.50 | — | — | — | +38.5% | −18% |
| longs close in S2's band | 1.76 | +0.26 [−0.12, +0.62] | +0.48 | +0.03 | +50.0% | −21% |
| shorts 21 days | 1.66 | +0.17 [−0.09, +0.40] | +0.09 | +0.25 | +42.8% | −21% |
| age tilt 1.5× | 1.66 | +0.17 [−0.01, +0.35] | +0.16 | +0.18 | +45.2% | −20% |
| **the stack** | **2.04** | **+0.54 [+0.08, +0.97]** | **+0.66** | **+0.43** | +61.0% | −23% |

With the bot's execution (limit orders, the stop from the next day):

| book | Sharpe | Δ vs the bot's B3 [95%] | Δ 2023–24 | Δ 2025–26 | CAGR | max DD |
|---|---|---|---|---|---|---|
| the bot's B3 | 1.44 | — | — | — | +36.7% | −19% |
| the stack | 1.99 | +0.55 [+0.08, +0.95] | +0.48 | +0.63 | +59.4% | −24% |
| the stack, $5,000 | 2.05 | +0.60 [+0.12, +1.03] | +0.50 | +0.73 | +61.9% | −23% |
| the stack, $10,000 | 2.01 | +0.57 [+0.11, +0.97] | +0.50 | +0.65 | +60.4% | −24% |

**Test on the other detector settings.** These 8 books have other trades (correlation
0.44 to 0.93 with B3). A rule that only fits the B3 trades must not help them.

| change | Δ > 0, of 9 settings | Δ > 0 in both halves, of 9 |
|---|---|---|
| age tilt 1.5× | 9 | **9** |
| shorts 21 days | 7 | 6 |
| longs close in S2's band | 9 | 5 |
| **the stack** | **9** | **7** |

*Mechanisms.* Each rule has its mechanism and its counterfactual in an earlier doc:
- **Close in S2's band.** L2 is a pullback in a leader. A coin in S2's band is not a
  leader. Same-state coins go down too (archive/exit_research.md §8).
- **Shorts 21 days.** S1's and S2's alpha continues in days 14–21 (archive/exit_research.md §1).
- **Age tilt.** Young coins have a low float and scheduled unlocks (archive/book_experiments.md
  §3). This is a hypothesis.

**The cost is a larger drawdown:** −23% against −18%.

## 4. The quality sleeve

**The book.** `scripts/quality_sleeve.py` trains a gradient-boosted model each month.
The features are eight quality measures: volatility, residual volatility, MAX, nearness
to the 180-day high, size, listing age, illiquidity and beta. The label is the rank of
the 14-day excess over the same-day universe mean. Each month trains only on rows whose
label ended before that month. We did not tune the settings. The book holds the top and
the bottom quantiles of the coins above $2M of notional. It is the mean of six books
(q = 0.10, 0.15, 0.20; hold 7 and 14 days), so we select no grid point. A universe basket
removes its trailing 60-day beta.

| book, 2024-01 → | Sharpe | 2024 | 2025–26 | CAGR | max DD |
|---|---|---|---|---|---|
| the quality sleeve alone | 1.44 | 1.73 | 1.35 | +37.7% | −22% |
| 75% B3 + 25% sleeve | 2.35 | 0.78 | 3.45 | +53.3% | −16% |
| 75% stack + 25% sleeve | 2.87 | 1.55 | 3.81 | +75.0% | −19% |

The script gives the placebo. The other checks are scratch, on a version of the sleeve
with Sharpe 1.29:

- **Placebo.** We permuted each day's labels across the coins. 30 runs give a mean Sharpe
  of −0.40, a standard deviation of 0.63 and a maximum of +0.68. None reaches the real
  1.44. Thus the pipeline does not leak.
- **Delay.** A score that is one day older gives 1.11, and five days older gives 0.90.
  The edge decays slowly, so it is not an artefact of the bar of the trade.
- **Ablation** (no floor). All features score 0.74 and the eight quality features alone
  score 0.74. Without the quality features the score is 0.40. The detector features
  alone score 0.05. The quality features hold the edge, and the fires do not.
- **The model does better than plain sorts.** On coins above $2M, low volatility alone
  scores 0.72 and an IC-weighted mean of the features scores 0.76.
- **Liquidity.** The sleeve scores 0.74 with no floor, 1.18 at $2M, 1.21 at $5M and 0.96
  at $10M. Small coins are the problem. The short leg is expensive to hold there.
- **Legs.** The short leg alone scores 0.79 and the long leg alone scores 0.30.

*Mechanism (hypothesis):* volatile new tokens have lottery demand and dilution from
unlocks. Their expected return is low, but their beta is high. Thus a low-volatility,
old-coin long against a high-volatility, young-coin short has alpha after the beta
hedge. We did not test this directly: the repo has no supply data. A plain age sort
looks good (Sharpe 1.25), but it is not stable. Without the listings from before 2021,
it scores −1.12 in 2024. Its longs carry 2024, and its shorts carry 2025–26.

## 5. Real funding (orientation only)

The backtest uses flat funding. The live funding cache covers 154 days of one regime.
Plus means that the book pays. These rows are scratch.

| book | real funding a year | flat funding a year | Sharpe with the gap, 2024-01 → |
|---|---|---|---|
| B3 | −5.3% | +2.5% | 2.12 |
| the stack | −3.2% | +2.5% | 2.61 |
| the quality sleeve | +14.6% | +3.7% | 0.85 |
| 75% stack + 25% sleeve | | | 2.90 |

- **The flat rule is good for the sleeve and bad for B3.** Young shorts paid funding
  over these 154 days. Young coins have crowded shorts.
- The sleeve still helps the blend after the gap.
- A funding factor has little information on this window: the rank IC of 7-day funding
  against the 14-day excess is +0.029, on 132 days with overlapped windows.
- *2026-11-16:* §8.2 has the real funding of 2024-01 → 2026-10. It replaces this table.

## 6. Limits

- **In-sample.** The three rules of the stack came from this same history. The test on
  the other detector settings reduces this risk, but those books share the calendar and
  many coins.
- **Family-wise test (scratch).** A Reality Check over 52 books gives p = 0.12 for the
  best book and p = 0.17 for 75% stack + 25% sleeve. The test uses 30-day blocks. Thus
  no book is significant at 5% after the search.
- **One market cycle.** The sleeve has 2.8 years of test data. The alt market fell in
  most of it.
- **The sleeve needs a model.** It needs scikit-learn and a job that trains the model
  each month. That is against the KISS rule until live data shows that the sleeve earns
  its cost.
- **Capacity.** The sleeve's shorts are small, young coins. Real slippage can be more
  than 0.10%.
- **Funding.** §5 is one regime. It can change the sleeve's result in both directions.

This doc is backtest research. It does not give investment advice.

## 7. Next steps

1. Score the three listing-age checks (`rules.WATCHLIST`, 2026-11-09). The other rules
   of the stack have checks from 2026-10-27 and 2026-11-07.
2. Do not change the live book before these checks have 30 episodes.
3. Run the stack and the quality sleeve as paper books next to B3. Log the real funding
   for each coin. *2026-11-16:* `target.target_from_candles(variant="stack",
   first_bars=...)` gives the stack's book (trader_repo_plan.md, phase I). On 3 days of
   real candles, its weights are equal to the backtest's stack book.
4. Fetch the funding history from 2023. This takes hours. Then §5 can cover more than
   one regime, and a funding factor can have a proper test. *Done 2026-11-16, from
   2023-12 (`scripts/fetch_funding_history.py`, §8.2).*

## 8. Improvements to the blend (2026-11-16)

Question: can a change to 75% stack + 25% sleeve increase its Sharpe? Before each batch
of tests, we recorded each hypothesis, its direction and its mechanism. A change counts
only if it helps in both halves (2024 / 2025–26) and has a mechanism. The window is
2024-01-01 → 2026-10-15. The baseline blend has Sharpe 2.87 with flat funding.

**Result: no change improves the blend.** 17 variants fail (§8.4). The pass found three
facts that change what to expect from the blend:
1. The gain of the sleeve is robust (§8.1).
2. Real funding takes the sleeve from 1.44 to 1.14, but the blend keeps its gain (§8.2).
3. The blend is not dollar-neutral, and the bot's net rule blocks it on some days (§8.6).

### 8.1 The gain of the sleeve is robust

The first three rows come from `quality_sleeve.py --settings --placebo 20`. The other
rows are scratch.

| check | result |
|---|---|
| the blend against the stack alone | +0.47 [+0.18, +0.82], +0.36 / +0.60 |
| the sleeve on the stack of each of the 9 detector settings | Δ +0.43 to +0.49. Each interval is above 0. Both halves on 9 of 9 |
| 20 placebo sleeves (labels permuted in each day), blended 75/25 | Δ −0.12 mean, +0.15 max. None reaches +0.47 |
| the bot's execution (resting limit orders, short stop from the next day) | blend 2.80, +0.48 [+0.18, +0.82] against the bot's stack |
| the sleeve's beta to the floor basket (daily) | −0.01. Up-market +0.02, down-market +0.02. Alpha +35% a year, t 2.4 |
| the sleeve trades at 0.30% a side | blend 2.72 (−0.15) |

- **The sleeve adds about +0.45 to any stack.** The other settings have weaker stacks
  (0.18 to 2.29). Thus expect the blend to be about 0.4 above the true Sharpe of the
  stack, not 2.87.
- *Mechanism of the diversification.* The two books earn in different conditions. The
  sleeve earns most after the alt index increased by more than 10% in 30 days (Sharpe 3.91).
  It earns little after a fall (0.52) or a flat month (0.21). The stack earns in each of
  the three (1.36 / 2.95 / 2.79). The daily correlation is −0.14 (+0.04 in 2024, −0.23
  in 2025–26).

### 8.2 Real funding

Hourly funding for all 219 coins that the blend holds, 2023-12 → 2026-10
(`scripts/fetch_funding_history.py`, `backtest.load_funding`). Real data covers 99% of
the gross. `quality_sleeve.py --funding` prints the table.

| book | Sharpe, flat funding | Sharpe, real funding | 2024 | 2025–26 | real funding a year, 2024 / 2025 / 2026 |
|---|---|---|---|---|---|
| B3 | 1.82 | 1.94 | 0.34 | 3.00 | +2.8% / −1.2% / −5.3% |
| the quality sleeve | 1.44 | **1.14** | 1.81 | **0.88** | +0.1% / +12.9% / **+19.9%** |
| the stack | 2.40 | 2.48 | 1.14 | 3.37 | +3.6% / +0.1% / −4.3% |
| **75% stack + 25% sleeve** | 2.87 | **2.85** | 1.52 | 3.79 | +2.7% / +3.3% / +1.7% |

Plus means that the book pays. With real funding, the blend against the stack is **+0.37
[+0.06, +0.70]**, +0.38 / +0.41.

- **The flat rate is good for the sleeve, as §5 found.** Over the 154 live days of §5,
  the sleeve paid 14.3% a year. That was not one regime only: its cost increased each
  year.
- *Mechanism.* The sleeve shorts the coins with the lowest score: young, volatile and
  illiquid. In 2024, longs paid about 29% a year on each quintile of the score. In
  2025–26, longs on the lowest quintile received 37.8% a year, and longs on the top
  quintile paid 7.3%. Thus the shorts of the sleeve became crowded, and a short on a
  crowded coin pays.
- **The blend keeps its gain because the stack receives funding.** The stack's shorts
  are not crowded in the same way: it received 4.3% a year in 2026.
- **The sleeve can pay much more before the blend loses its gain.** We added a cost to
  each unit of the sleeve's side gross (scratch). The mean side gross is 0.57.

  | extra funding a year, a unit of side gross | 0 | +10% | +20% | +30% | +40% | +60% |
  |---|---|---|---|---|---|---|
  | sleeve Sharpe | 1.14 | 0.90 | 0.67 | 0.43 | 0.20 | −0.28 |
  | blend − stack | +0.37 | +0.30 | +0.23 | +0.16 | +0.09 | −0.05 |

  The gain is zero at about +53% a unit, that is +30% of the sleeve's equity. Thus the
  sleeve's total funding can be up to about +40% a year. The 2026 rate is +17% a unit
  above the window mean, and at that rate the blend keeps about +0.25.

### 8.3 The quality signs are stable when beta leaves the label

The sleeve's label is the raw 14-day excess return, and the raw excess holds beta. In
2023, before the test window, the raw label gives the opposite sign for each risk
feature: high beta won (IC +0.14, t 3.0). A label with the beta part removed gives the
quality signs in 2023 too:

| feature | 2023 IC, raw label | 2023 IC, beta-adjusted label | 2024 → IC, beta-adjusted label |
|---|---|---|---|
| volatility | +0.120 (t 1.6) | −0.047 (t −1.0) | −0.134 (t −5.9) |
| residual volatility | +0.048 (t 0.7) | −0.071 (t −2.5) | −0.139 (t −7.2) |
| MAX | +0.072 (t 0.9) | −0.053 (t −1.0) | −0.118 (t −5.6) |
| beta | +0.136 (t 3.0) | −0.105 (t −2.0) | −0.054 (t −2.1) |
| listing age | +0.089 (t 0.6) | +0.161 (t 1.4) | +0.128 (t 6.1) |

Thus the 2023 reversal was the alt rally in the label, not a change in the effect. This
supports the mechanism of §4: risky young coins earn less than their beta.

### 8.4 What does not help

All rows are scratch. Δ is against the blend, with flat funding in the first part and
real funding in the second part.

| change | Δ [95%] | Δ 2024 | Δ 2025–26 | why it fails |
|---|---|---|---|---|
| sleeve no-trade band 25% | −0.00 [−0.04, +0.04] | +0.01 | −0.02 | the six-book mean already trades slowly (61× a year) |
| 50% stack + 50% sleeve | +0.16 [−0.37, +0.69] | +0.42 | −0.10 | a fixed ratio has no mechanism |
| weights by inverse 60-day volatility | +0.12 [−0.54, +0.78] | +0.40 | −0.22 | the same |
| capital fill: the sleeve takes the stack's unused gross | +0.02 [−0.10, +0.15] | +0.09 | −0.01 | thin-stack days are few after 2024 |
| sleeve-score tilt 1.5× on the stack, with the age tilt | −0.14 [−0.29, −0.00] | −0.24 | −0.10 | the books become alike: correlation −0.14 → −0.07 |
| sleeve-score tilt in place of the age tilt | −0.19 [−0.40, −0.00] | −0.29 | −0.12 | the same |
| beta-adjusted label (§8.3) | −0.02 [−0.19, +0.10] | −0.07 | +0.02 | the model already found the signs: score correlation 0.91 |
| maker orders for the sleeve (the sleeve alone) | +0.05 [+0.01, +0.08] | −0.03 | +0.08 | one half only |
| a sleeve with no model: low volatility | −0.21 [−0.52, +0.06] | −0.21 | −0.18 | the model holds more than one factor |
| a sleeve with no model: low volatility + old age | −0.25 [−0.55, +0.05] | −0.30 | −0.22 | the same |
| a sleeve with no model: mean of the 8 ranks, 2023 signs | −0.85 [−1.43, −0.38] | −0.41 | −1.27 | the 2023 signs are wrong (§8.3) |
| *real funding:* no sleeve short when 7-day funding < −10% a year | −0.09 [−0.21, +0.07] | −0.04 | −0.15 | the crowded shorts still fall more than they pay |
| no stack short entry when 7-day funding < −10% a year (the stack alone) | −0.07 [−0.33, +0.20] | +0.13 | −0.22 | one half only |
| both filters | −0.16 [−0.46, +0.15] | +0.08 | −0.36 | the same |
| 7-day funding as a ninth sleeve feature | −0.07 [−0.18, +0.02] | −0.11 | −0.05 | the same |
| the label less the funding that a long pays | −0.05 [−0.10, +0.00] | −0.08 | −0.03 | the same |
| + 10% funding-carry sleeve (long low funding, short high funding) | −0.02 [−0.18, +0.15] | +0.03 | −0.07 | the carry earns 22.8% a year of funding and loses more on price |

- **Funding is a fair price.** The carry sleeve alone has Sharpe −0.27 with its
  funding, and −1.20 on price only. A coin with negative funding falls by more than its
  funding pays a short. Thus a funding filter removes shorts that earn their cost.
- **Per trade (first fires, 2024 →), the stack's crowded shorts pay but do not fall
  more.** S2 first fires with 7-day funding below −10% a year earn −0.53 net of funding
  against +1.44 for the rest (−1.97 [−4.34, +0.11]). On price only, the gap is −0.33.
  Same-state non-fires show the same funding gap (−1.63), so the detector adds nothing.
- **Per trade, stack trades against the sleeve earn less.** A long in the lowest
  quintile of the score, or a short in the top quintile, earns +0.53 against +1.37
  (−0.84 [−2.20, +0.42]). Same-state non-fires show the same gap (−1.36 [−2.22,
  −0.45]). Thus it is the sleeve's own factor, and the blend already holds it.

### 8.5 A simpler sleeve does the same

| model | sleeve Sharpe | blend Sharpe | Δ vs the monthly model [95%] | Δ 2024 | Δ 2025–26 |
|---|---|---|---|---|---|
| retrain each month (the baseline) | 1.44 | 2.87 | — | — | — |
| **retrain each year** | 1.53 | 2.87 | −0.01 [−0.20, +0.20] | +0.02 | −0.02 |
| frozen at 2024-01 | 1.23 | 2.68 | −0.19 [−0.50, +0.14] | +0.02 | −0.35 |
| beta-adjusted label, retrain each year | 1.86 | 2.92 | +0.04 [−0.17, +0.23] | +0.03 | +0.08 |
| beta-adjusted label, frozen at 2024-01 | 1.54 | 2.78 | −0.09 [−0.34, +0.16] | +0.03 | −0.17 |

Flat funding, scratch.

- **A yearly retrain is enough.** The live sleeve does not need a job each month.
- **The sleeve's own Sharpe is noisy.** It goes from 1.23 to 1.86 with the retrain
  schedule, and the blend stays between 2.68 and 2.92. Do not read the sleeve's Sharpe
  to two decimals.

### 8.6 The blend is not dollar-neutral

The sleeve's beta basket keeps the sleeve net long: +18% on average, and up to +46%. The
blend is net long by 4.5% on average, and by more than 10% on 3.6% of days. On those days
the bot's planned-net rule (`MAX_PLANNED_NET`, ±10%) sends only the closes. With the $10
minimum order, the blend loses −0.09 at $10,000 and −0.14 [−0.39, +0.00] at $50,000
(−0.24 in 2025–26). Scratch.

A live blend needs the net rule on the stack's part only, or on the beta-adjusted net.

### 8.7 What to do

1. Keep the blend as the candidate. Its gain survives real funding, the bot's execution,
   the 9 settings and the placebo. It is still in-sample for the stack's rules (§6).
2. Make the paper sleeve retrain each year, not each month.
3. Before the blend trades, apply the net rule of the bot to the stack's part only.
4. Log the sleeve's funding each month. Its cost increased from +0% to +20% a year in
   three years. At more than about +40% a year (§8.2), the sleeve does not help the
   blend.
5. Do not add a funding filter, a funding feature or a carry sleeve.

Nothing goes on the watchlist. Each per-trade effect of this pass is also in the
same-state non-fires, so the detector does not know it (research_method.md rule 4).

## Reproduction

```
uv run python scripts/backtest_tables.py > tables.md
uv run --with scikit-learn python scripts/quality_sleeve.py --placebo 30
uv run --with scikit-learn python scripts/quality_sleeve.py --settings --placebo 20   # §8.1
uv run python scripts/fetch_funding_history.py                                         # once, ~2.5 hours
uv run --with scikit-learn python scripts/quality_sleeve.py --funding                 # §8.2
```

`backtest_tables.py` prints §3 and the settings table of §3. It builds the eight panels
of the other settings into `state/research_cache/neighbours/` on the first run (about
one minute each). The factors, the trend sleeves, the ablations, the funding gap and the
Reality Check are scratch.
