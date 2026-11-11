# Strategy search: books that can do better than B3

Research doc, 2026-11-09. This doc tests new methods against B3
([profit_strategies.md](profit_strategies.md)). It follows
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
  leader. Same-state coins go down too (exit_research.md §8).
- **Shorts 21 days.** S1's and S2's alpha continues in days 14–21 (exit_research.md §1).
- **Age tilt.** Young coins have a low float and scheduled unlocks (book_experiments.md
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
   for each coin.
4. Fetch the funding history from 2023. This takes hours. Then §5 can cover more than
   one regime, and a funding factor can have a proper test.

## Reproduction

```
uv run python scripts/backtest_tables.py > tables.md
uv run --with scikit-learn python scripts/quality_sleeve.py --placebo 30
```

`backtest_tables.py` prints §3 and the settings table of §3. It builds the eight panels
of the other settings into `state/research_cache/neighbours/` on the first run (about
one minute each). The factors, the trend sleeves, the ablations, the funding gap and the
Reality Check are scratch.
