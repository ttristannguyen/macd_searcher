# Research log

One dated entry per periodic pass of [research_method.md](research_method.md), newest
first. Each entry records what the pass learned about the dataset, what it changed
in the tooling, and what it registered on the watchlist. Topic deep-dives keep their
own docs ([archive/confidence_v3_research.md](archive/confidence_v3_research.md),
[archive/confidence_v3.md](archive/confidence_v3.md)); this is the running record.

---

## 2026-11-19 — more exit alternatives

Question: does an exit that archive/exit_research.md and strategy_search.md did not test
help B3 or the stack?

**Data.** The frozen panel (built 2026-11-03), crypto only, fires and returns 2023-02-28 →
2026-10-15. First fires only. The per-trade numbers come from scratch scripts in the
backtester's convention (archive/exit_research.md §8). The portfolio numbers come from the
committed backtester (`backtest_tables.exit_alternatives()`). The funding rows use the real
hourly funding from 2023-12, so their window is 2024-01-01 → 2026-10-15. All of this is
in-sample.

**Method.** We wrote each hypothesis, its sign and its mechanism before the first look.
Batch 1 was H1–H4. Batch 2 (H5, H6) came after the per-trade results of batch 1. Each
rule decides on day D' from bars closed through D' − 1, and exits at that close.

| | rule | mechanism | expected |
|---|---|---|---|
| H1 | a long closes when its 7-day funding is ≥ 15% or ≥ 50% APR | crowded longs meet long liquidations | > 0 |
| H1b | a short closes when its 7-day funding is ≤ −15% or ≤ −50% APR | crowded shorts meet a squeeze | ≤ 0 (strategy_search.md §8.4) |
| H2 | close after a bar with 3× the coin's median notional of 20 bars, in the trade's favour | the forced flow ends, and the price reverts | > 0 |
| H3 | close when the coin falls below the $300k liquidity floor | coins that leave the universe are the losers (research_method.md rule 2) | > 0 for longs |
| H4 | hold 7 days more when the coin is in a state that continues: a long in a strong rally, a short in a deep dip | these states continue (2026-10-25) | > 0 |
| H5 | when the long side has more names than max(10, short names), close the L2 longs held more than 7 days, oldest first | L2's edge is paid by day 7 (archive/exit_research.md §1), and the gross does not fall | > 0 |
| H6 | an L2 long above its SMA200 at entry closes when its close falls below the SMA200 | the 200-day trend is part of L2's edge (2026-11-19, the lookback entry) | > 0 |

### Watchlist (snapshot 2026-11-19 00:00 UTC)

- **No B3 leg check has 30 episodes.** The first 21-day outcomes are here. S2 after its
  14d exit: −1.99 long-side, 11 ep, the expected side. S1: 0 ep. The L2 deep-dip exit: −1.10,
  7 ep, the wrong side (the long gained). The S2-band flip: 0 ep.
- **The v3 bearish leg at 7d is not confirmed now.** On 2026-11-16 it was +3.55 [+1.53,
  +5.89], 34 ep. Now it is +2.19 [−2.52, +5.25], 38 ep. At 14d it is +3.34 [−1.75, +7.97],
  26 ep.
- **A new verdict outside B3:** bullish crypto fires in a BTC downtrend are contradicted.
  Rule − rest, raw: −2.61 [−6.54, −0.17], 124 ep.
- The other verdicts do not change: v2 confirmed (+1.41 [+0.58, +2.38], 179 ep), the
  record-peak warning contradicted (+1.05 [+0.32, +2.20], 153 ep), v3 bullish holds.

### Per trade

Exit alpha minus 14-day-hold alpha, 2023–24 / 2025–26 (H1, H1b: 2024 / 2025–26). Bold: the
95% week-block interval excludes zero. The share is the trades that the rule closes before
day 14. For H4, it is the trades that the rule holds longer.

| rule | L1 | L2 | S1 | S2 | share (L1 / L2 / S1 / S2) |
|---|---|---|---|---|---|
| H1, funding ≥ 15% APR | −0.43 / −0.16 | −0.97 / −0.18 | | | 25 / 43% |
| H1, funding ≥ 50% APR | −0.08 / **−0.24** | +0.01 / −0.10 | | | 5 / 17% |
| H1b, funding ≤ −15% APR | | | **−0.51** / −0.12 | **−0.42** / −0.08 | 20 / 21% |
| H1b, funding ≤ −50% APR | | | −0.28 / −0.11 | −0.16 / −0.16 | 8 / 7% |
| H2, volume climax | +1.02 / **−0.94** | −0.46 / +0.21 | −0.32 / −0.28 | −0.18 / −0.31 | 43 / 35 / 28 / 31% |
| H3, below the floor | +0.45 / **−0.71** | −0.08 / **−0.45** | **−0.93** / −0.36 | −0.15 / **−1.00** | 45 / 39 / 45 / 40% |
| H4, 7 days more | +0.23 / −0.06 | +0.30 / +0.15 | **+0.18** / +0.01 | +0.05 / +0.06 | 5 / 7 / 5 / 11% |
| H6, below the SMA200 | +0.06 / +0.04 | +0.10 / −0.02 | | | 6 / 11% |

The same rules on same-state non-fires (archive/exit_research.md §8):

| rule | L1 | L2 | S1 | S2 |
|---|---|---|---|---|
| H1, funding ≥ 15% APR | +0.75 / −0.12 | **−1.40** / **−0.50** | | |
| H1, funding ≥ 50% APR | +0.17 / −0.05 | −0.92 / **−0.19** | | |
| H1b, funding ≤ −15% APR | | | −0.22 / −0.04 | −0.19 / −0.09 |
| H1b, funding ≤ −50% APR | | | −0.18 / **−0.28** | +0.11 / −0.09 |
| H2, volume climax | +0.04 / −0.23 | **−1.40** / −0.05 | −0.28 / +0.26 | +0.31 / −0.14 |
| H3, below the floor | +0.18 / −0.03 | +0.35 / −0.12 | −0.32 / +0.09 | +0.17 / **−0.55** |
| H4, 7 days more | +0.05 / +0.00 | +0.09 / −0.13 | +0.05 / +0.06 | +0.14 / **+0.15** |
| H6, below the SMA200 | +0.36 / **+0.06** | +0.04 / −0.05 | | |

- **Funding exits cost alpha (H1, H1b).** A long with high funding is a coin in a strong
  trend, and the trend continues. Same-state L2 coins lose −1.40 / −0.50 too. Thus funding
  is a fair price for crowded longs, as strategy_search.md §8.4 found for crowded shorts.
- **The volume climax changes sign with the market (H2).** L1 gains +1.02 in 2023–24 and
  loses −0.94 in 2025–26, as the take-profits did (archive/exit_research.md §3). The other
  legs lose. On same-state L2 coins, an up bar on high volume starts more trend (−1.40).
- **The liquidity floor does not predict (H3).** 39–45% of the trades go below $300k on
  one day of the hold or more. Rule 2 of research_method.md is about the same window: the
  fall causes the exit. After the exit, the longs do not lose more, and the shorts
  continue to go down.
- **The trend break is noise (H6).** It closes 11% of L2 trades, for +0.10 / −0.02.
- **A longer hold in a state that continues is positive but small (H4).** It acts on 5–11%
  of the trades. The same-state coins agree, so it is a state effect, not a fire effect.

### As portfolios

| book | Sharpe | Δ [95%] | Δ 2023–24 | Δ 2025–26 | CAGR | max DD | turnover | names long / short |
|---|---|---|---|---|---|---|---|---|
| **B3** | 1.50 | — | — | — | +38.5% | −18% | — | 33 / 28 |
| H4, 7 days more in a state that continues | 1.52 | +0.02 [−0.04, +0.08] | +0.04 | +0.01 | +39.1% | −19% | −2% | 33 / 28 |
| H4, shorts only | 1.52 | +0.03 [−0.00, +0.06] | +0.04 | +0.02 | +39.4% | −18% | −1% | 33 / 28 |
| H5, L2 held more than 7 days | 1.61 | +0.12 [−0.13, +0.38] | +0.25 | +0.04 | +45.4% | −19% | +8% | 27 / 28 |
| H5, L2 held more than 5 days | 1.72 | +0.23 [−0.07, +0.54] | +0.44 | +0.07 | +50.8% | −18% | +11% | 25 / 28 |
| H5 placebo: the youngest L2 longs held 1 day or more | 1.64 | +0.14 [−0.27, +0.57] | +0.34 | −0.01 | +48.4% | −22% | +34% | 19 / 28 |
| **the stack** | 2.04 | — | — | — | +61.0% | −23% | — | 27 / 33 |
| H4, 7 days more in a state that continues | 2.05 | +0.01 [−0.05, +0.07] | +0.01 | +0.01 | +61.1% | −23% | −1% | 27 / 33 |
| H5, L2 held more than 7 days | 2.07 | +0.03 [−0.12, +0.19] | +0.05 | +0.04 | +63.6% | −23% | +6% | 24 / 33 |
| H5, L2 held more than 5 days | 2.10 | +0.06 [−0.13, +0.22] | +0.06 | +0.07 | +65.2% | −22% | +9% | 22 / 33 |
| H5 placebo: the youngest L2 longs held 1 day or more | 1.88 | −0.16 [−0.53, +0.15] | −0.44 | +0.09 | +57.6% | −25% | +27% | 18 / 33 |

Δ is against the same book. A placebo that closes random L2 longs held 1 day or more gives
+0.08 on B3 (10 seeds, −0.12 to +0.28) and −0.11 on the stack (−0.19 to +0.09).
We registered H5 at 7 days. `exit_alternatives()` also prints H5 at 3 and 10 days, and H4
for the longs only.

H1 with real funding, 2024-01-01 → 2026-10-15:

| book | funding | Sharpe | Δ vs the same book [95%] | Δ 2024 | Δ 2025–26 |
|---|---|---|---|---|---|
| B3, funding ≥ 15% APR | flat / real | 1.38 / 1.68 | −0.44 / −0.26 [−0.92, +0.30] | −0.78 / −0.58 | −0.35 / −0.20 |
| B3, funding ≥ 50% APR | flat / real | 1.73 / 1.93 | −0.09 / −0.01 [−0.47, +0.34] | +0.12 / +0.27 | −0.18 / −0.14 |
| the stack, funding ≥ 15% APR | flat / real | 1.83 / 2.07 | −0.57 / −0.41 [−0.99, −0.02] | −1.41 / −1.23 | −0.24 / −0.11 |
| the stack, funding ≥ 50% APR | flat / real | 2.26 / 2.41 | −0.14 / −0.07 [−0.40, +0.13] | −0.20 / −0.08 | −0.11 / −0.07 |

The interval is for real funding.

- **No exit helps the stack.** H4 adds +0.01, and H5 adds +0.03 to +0.06. The funding exit
  costs money with real funding too.
- **On B3, H5's gain does not come from the age.** The placebo that closes the youngest
  L2 longs gives +0.14, and random L2 longs give +0.08 on average. Thus B3 gains from fewer
  L2 names on days with a full long side, not from the close of spent trades.
- **Mechanism: the stack's band exit already closes the spent L2 trades.** Per trade, L2's
  alpha in days 7–14 is +0.06 / −0.14. L2 longs in S2's band by day 7 lose −1.53 [−3.06,
  −0.40] / −0.80 [−1.85, +0.26] in those days. The others earn +0.78 / +0.07. The stack
  closes the first group. Thus an age rule has no spent trades left to close.
- **Observation only: on the stack, skip the new L2 longs on a day with a full long side.**
  It gives +0.30 [−0.04, +0.69], but +0.66 / −0.00 by half (B3: +0.05). It was a placebo,
  it is an entry rule, and it does not help in 2025–26. No mechanism explains it.
- *Answer:* no new exit helps in both halves with a mechanism. Exits on the trade's price,
  volume, liquidity or funding do not help. In three passes, two exit rules helped: the
  close on the coin's MACD state (S2's band) and a hold for each leg (shorts 21 days).

### Tooling

- `backtest_tables.exit_alternatives()` prints the portfolio tables of this entry.
- `backtest_tables.close_when_full()` is `bt.simulate` with fills at the close, no stop,
  and the H5 rule. With no close, it gives the baseline exactly. The rule needs the whole
  book, so it is not an `exit_rule` of `simulate`.

### Registered this pass

Nothing:
- No rule helps in both halves with a mechanism and a counterfactual.
- The per-trade effects of funding and volume are also in the same-state coins, so the
  detector does not know them (research_method.md rule 4).

---

## 2026-11-19 — the `peak_pct` lookback, and a cap of 5% a name

Questions:
1. Does a `peak_pct` window other than 200 bars sort the good and the bad fires better?
   Do the longs and the shorts need different windows?
2. How does a cap of 5% a name, in place of 10%, change the profit of the book?

**Data.** The frozen panel (built 2026-11-03), crypto only, fires and returns
2023-02-28 → 2026-10-15. First fires only. The per-trade numbers come from scratch
scripts in the backtester's convention: entry at the close of D − 1, exit at the close of
D + 14, alpha against the mean of the eligible universe over the same bars, week-block
intervals. The portfolio numbers come from the committed backtester
(`backtest_tables.peak_lookback()` and `name_cap()`). All of this is in-sample.

**The lookback test changes only the window that ranks the excursion.** The fires, the
universe and MACD (warm over the full history) do not change. A coin with fewer bars than
L uses all of its bars. The leg bands stay at 25 / 50 / 100. At L = 200, the new state is
equal to the panel's `state_pct` on all 162,531 coin-days.

### Per trade: 14d alpha in the trade's direction

| L (bars) | priors of the same sign, median | L1 (ep) | L2 (ep) | S1 (ep) | S2 (ep) | all traded fires | Δ all traded vs 200, same fires [95%] |
|---|---|---|---|---|---|---|---|
| 50 | 1 | +0.66 (1,323) | +0.61 (3,820) | +0.66 (1,857) | +1.44 (196) | +0.65 | −0.46 [−0.88, −0.02] |
| 100 | 3 | +1.67 (1,112) | +0.62 (3,998) | +0.47 (1,599) | +0.18 (1,266) | +0.66 | −0.45 [−0.79, −0.11] |
| 150 | 5 | +1.34 (1,069) | +0.84 (3,677) | +1.07 (1,661) | +0.89 (1,981) | +0.96 | −0.15 [−0.36, +0.05] |
| **200** | 7 | +1.73 (1,009) | +0.96 (3,407) | +1.26 (1,554) | +0.96 (2,171) | +1.12 | — |
| 300 | 11 | +1.19 (1,017) | +0.70 (3,000) | +0.70 (1,621) | +0.81 (2,293) | +0.79 | −0.32 [−0.51, −0.14] |
| 400 | 14 | +1.63 (1,049) | +0.75 (2,832) | +0.98 (1,693) | +0.66 (2,305) | +0.89 | −0.23 [−0.46, +0.01] |
| 600 | 20 | +1.14 (1,115) | +0.75 (2,760) | +0.70 (1,796) | +0.77 (2,327) | +0.80 | −0.31 [−0.59, −0.03] |

Same state, and fire − state, in the trade's direction at 14d. The state rows are
universe coin-days in the leg's band with no same-side fire in the last 5 days. The last
column is the rank correlation of the first fires' `peak_pct` with the coin's price change
over the same window.

| L | L1 state / fire − state | L2 state / fire − state | S1 state / fire − state | S2 state / fire − state | correlation with the price change, bullish / bearish |
|---|---|---|---|---|---|
| 50 | −0.02 / +0.68 | +0.01 / +0.60 | +0.10 / +0.56 | +0.30 / +1.15 | +0.31 / +0.11 |
| 100 | +0.31 / +1.35 | +0.42 / +0.20 | +0.02 / +0.45 | +0.38 / −0.20 | +0.40 / +0.23 |
| 150 | +0.10 / +1.24 | +0.56 / +0.28 | +0.33 / +0.75 | +0.65 / +0.24 | +0.39 / +0.32 |
| **200** | +0.09 / **+1.65** [+0.59, +2.74] | +0.65 / +0.31 | +0.10 / **+1.16** [+0.39, +1.92] | +0.55 / +0.41 | +0.42 / +0.40 |
| 300 | +0.06 / +1.12 | +0.62 / +0.08 | +0.22 / +0.47 | +0.44 / +0.37 | +0.46 / +0.50 |
| 400 | +0.12 / +1.51 | +0.82 / −0.07 | +0.37 / +0.61 | +0.51 / +0.15 | +0.52 / +0.49 |
| 600 | +0.03 / +1.11 | +1.03 / −0.28 | +0.56 / +0.14 | +0.65 / +0.12 | +0.55 / +0.56 |

- **No window sorts the fires better than 200 bars.** On the same fires, each other window
  lowers the mean alpha of the traded fires by 0.15 to 0.46 points. Four of the six
  intervals exclude zero. No leg is better at another window, except S2 at 50 bars, which
  keeps only 196 episodes.
- **A short window has too few priors.** At 50 bars, the median fire has 1 prior
  excursion of its sign, so `peak_pct` is 0, 50 or 100. At 100 bars, 22% of the fires have
  2 priors or fewer. The bands then sort noise.
- **A long window ranks the price level.** The histogram is in price units. Over a longer
  window the price moves more, so `peak_pct` follows the price change more (+0.42 at 200
  bars, +0.56 at 600). Then the state earns the leg's alpha, and the fire adds less. L2's
  state goes from +0.65 to +1.03 and its fire − state from +0.31 to −0.28. S1's state goes
  from +0.10 to +0.56 and its fire − state from +1.16 to +0.14. At 600 bars, `peak_pct` is
  a generic price-momentum sort (research_method.md rule 4).
- **L1 does not depend on the window.** Its fire − state is +1.1 to +1.65 at each window
  from 100 to 600 bars. The fire carries L1.
- **Two band results of 2026-10-28 are properties of the 200-bar window.** Bearish 75–<100
  as a long is +2.10 at 200 bars, but −0.15 at 150 and +0.54 to +1.17 at 300–600. Bearish
  records (100) are −0.07 at 200 bars, but +1.09 to +1.31 at 50–150 and at 400–600.
- **Mechanism test: the histogram divided by the close.** This removes most of the link
  to the price change (+0.13 / −0.01 at 200 bars, +0.11 / +0.05 at 600). But B3 falls to
  0.95 at 200 bars, and to 0.27–0.87 at the other windows (scratch, on `simulate`). Thus
  the 200-day trend inside `peak_pct` is part of B3's edge. This agrees with 2026-10-19:
  the pullback long belongs to coins in an uptrend. A window of 600 bars holds too much of
  the price level, and hist / close holds too little.

### As portfolios

| book | Sharpe | Δ vs L = 200 [95%] | Δ 2023–24 | Δ 2025–26 | CAGR | max DD | names long / short |
|---|---|---|---|---|---|---|---|
| B3, L = 50 | 0.19 | −1.30 [−2.40, −0.09] | +0.07 | −2.66 | +1.8% | −35% | 40 / 16 |
| B3, L = 100 | 0.54 | −0.95 [−1.78, −0.06] | −0.35 | −1.60 | +10.6% | −31% | 38 / 22 |
| B3, L = 150 | 1.40 | −0.10 [−0.72, +0.52] | +0.21 | −0.38 | +33.8% | −23% | 36 / 27 |
| **B3, L = 200** | 1.50 | — | — | — | +38.5% | −18% | 33 / 28 |
| B3, L = 300 | 0.87 | −0.63 [−1.22, −0.11] | −0.39 | −0.88 | +19.3% | −23% | 30 / 29 |
| B3, L = 400 | 1.11 | −0.39 [−1.18, +0.28] | −0.24 | −0.62 | +26.2% | −26% | 29 / 29 |
| B3, L = 600 | 1.00 | −0.50 [−1.30, +0.22] | −0.51 | −0.55 | +23.2% | −25% | 29 / 30 |
| B3, longs at 100, shorts at 200 | 1.50 | +0.00 [−0.40, +0.45] | +0.30 | −0.26 | +36.9% | −20% | 36 / 26 |
| B3, longs at 400, shorts at 200 | 1.58 | +0.09 [−0.27, +0.51] | +0.21 | −0.07 | +42.1% | −20% | 29 / 28 |
| B3, longs at 600, shorts at 200 | 1.51 | +0.02 [−0.38, +0.47] | +0.04 | −0.04 | +40.2% | −26% | 28 / 27 |
| B3, longs at 200, shorts at 150 | 1.39 | −0.11 [−0.59, +0.34] | −0.19 | −0.02 | +34.5% | −27% | 33 / 27 |
| B3, longs at 200, shorts at 400 | 1.13 | −0.36 [−0.95, +0.09] | −0.33 | −0.43 | +27.0% | −23% | 33 / 29 |
| the stack, L = 150 | 1.90 | −0.14 [−0.76, +0.41] (vs the stack) | +0.28 | −0.53 | +54.3% | −18% | 29 / 32 |
| **the stack, L = 200** | 2.04 | — | — | — | +61.0% | −23% | 27 / 33 |
| the stack, L = 400 | 1.47 | −0.57 [−1.35, +0.15] (vs the stack) | +0.23 | −1.38 | +39.0% | −22% | 24 / 35 |

`backtest_tables.peak_lookback()` prints every row of the grid.

- **200 bars is the best window for B3 and for the stack.** No other window gives Δ > 0 in
  both halves, for all the legs or for one side alone.
- **The longs do not need another window.** Longs at 100 to 600 bars score 1.30 to 1.58.
  The best, longs at 400 bars, gives +0.09 [−0.27, +0.51], +0.21 / −0.07. This agrees with
  L1's fire − state, which does not depend on the window.
- **The shorts need 200 bars.** Each other short window costs 0.11 to 0.98 Sharpe, and the
  loss is negative in both halves at each window.
- *Answer:* another window does not make it easier to find the coins that go up or down.
  The good and the bad fires do not need different windows.
- *Caveat:* the bands were set at 200 bars on this same history, so 200 bars has an
  advantage. The two mechanisms (too few priors, the price level) explain the loss on each
  side of 200 without that advantage.

### A cap of 5% a name

Each side has equal weights that stop at the cap. Thus the side gross is min(100%, cap ×
names on the thinner side). `max_weight` is the new variant of `backtest.simulate`.

| book | Sharpe | Δ vs 10% [95%] | Δ 2023–24 | Δ 2025–26 | CAGR | max DD | mean side gross | volatility a year | worst name-day |
|---|---|---|---|---|---|---|---|---|---|
| B3, 10% | 1.50 | — | — | — | +38.5% | −18% | 84% | 24% | −7.5% |
| B3, 7.5% | 1.55 | +0.05 [−0.05, +0.16] | +0.06 | −0.03 | +37.6% | −17% | 79% | 22% | −5.6% |
| **B3, 5%** | 1.67 | +0.18 [−0.06, +0.43] | +0.16 | −0.05 | +35.2% | −16% | 69% | 19% | −3.9% |
| the stack, 10% | 2.04 | — | — | — | +61.0% | −23% | 82% | 25% | −7.5% |
| the stack, 7.5% | 2.04 | +0.00 [−0.14, +0.15] | −0.08 | +0.03 | +55.2% | −21% | 76% | 23% | −5.6% |
| **the stack, 5%** | 2.20 | +0.16 [−0.11, +0.43] | −0.08 | +0.17 | +49.7% | −16% | 66% | 19% | −3.7% |
| the bot's B3, $5,000, 5% (vs 10%) | 1.70 | +0.20 [−0.05, +0.49] | +0.05 | +0.10 | +36.2% | −14% | 69% | 19% | −4.0% |
| the bot's stack, $5,000, 5% (vs 10%) | 2.25 | +0.21 [−0.05, +0.46] | −0.05 | +0.20 | +51.9% | −16% | 66% | 19% | −3.6% |

The bot's rows use limit orders and the stop from the next day. Their base is the same
book at 10% (B3 1.49, the stack 2.05).

By names on the thinner side of the 10% book:

| book | thinner side | share of days | side gross 10% / 5% | Sharpe 10% / 5% | Sharpe 10%, 2023–24 / 2025–26 |
|---|---|---|---|---|---|
| B3 | 0–9 | 30% | 46% / 23% | 0.56 / 0.55 | 0.38 / 1.49 |
| B3 | 10–19 | 29% | 100% / 72% | 0.53 / 0.43 | −0.58 / 2.36 |
| B3 | 20 or more | 41% | 100% / 100% | 2.97 / 2.97 | 2.23 / 3.13 |
| the stack | 0–9 | 34% | 48% / 24% | 0.76 / 0.75 | 1.06 / −0.23 |
| the stack | 10–19 | 26% | 100% / 69% | 1.45 / 1.06 | 0.09 / 3.49 |
| the stack | 20 or more | 40% | 100% / 100% | 3.72 / 3.76 | 2.89 / 3.91 |

- **The 5% cap gives less profit.** CAGR falls from +38.5% to +35.2% for B3, and from
  +61.0% to +49.7% for the stack. The mean side gross falls from 84% to 69%, and from 82%
  to 66%.
- **The risk falls more than the return.** Volatility falls from 24–25% to 19%. Max
  drawdown falls from −18% to −16% (B3) and from −23% to −16% (the stack). The worst loss
  from one name on one day falls from 7.5% to 3.9% of equity.
- **The Sharpe gain is not robust.** With fills at the close, B3 gains +0.18 [−0.06,
  +0.43], but −0.05 in 2025–26. The stack gains +0.16 [−0.11, +0.43], but −0.08 in
  2023–24. With the bot's execution, B3 gains in both halves at each account size (+0.19
  to +0.27). The stack still loses in 2023–24 at each size (−0.05 to −0.13). Each interval
  includes zero.
- **Mechanism: the cap is an exposure rule for thin days.** The cap changes the book only
  when the thinner side has fewer than 20 names. The 10% book, with each day's exposure
  cut to the 5% book's side gross, scores 1.68 against 1.67 (B3). Thus the cap does not
  change which coins the book holds. It only holds less on thin days.
- **Broad days are the best days in each half.** With 20 names or more on the thinner
  side, the 10% book has the highest Sharpe in both halves (B3: 2.23 and 3.13; the stack:
  2.89 and 3.91). A broad book is diversified, and many fires come when dispersion is
  high (2026-10-30). But on thin days, the order of 0–9 names and 10–19 names changes
  between the halves and the books. The cap cuts the 0–9 days most, so its gain changes
  sign.
- **The thin days are mostly in 2023–24.** The thinner side has fewer than 20 names on 85%
  of the days in 2023–24, and on 32% in 2025–26. Thus most of the full-period gain comes
  from less exposure in 2023–24, B3's weak half (Sharpe 0.21).
- *For the decision:* the cap is a risk choice, not an edge. At 1x it costs 3 points of
  CAGR (B3) to 11 points (the stack), and it halves the loss from one name. At the 10%
  book's volatility, the 5% book would earn more (B3 +44.4% against +38.5%). But that needs
  a side gross above 100% on full days, and the bot trades 1x neutral.

### Tooling

- `backtest.simulate` and `backtest.target_book` take `max_weight`, the cap a name
  (default MAX_WEIGHT). A test pins it. The baseline does not change (the golden test
  passes).
- `backtest_tables.lookback_panel(L)` gives the frozen panel with the state `peak_pct` on
  the last L bars. The state stays in `state/research_cache/neighbours/`. `peak_lookback()`
  and `name_cap()` print the tables of this entry.

### Registered this pass

Nothing:
- No lookback variant helps in both halves, and the live frame has only the 200-bar
  `peak_pct`.
- The cap is a rule of the book, not a per-trade check.

---

## 2026-11-18 — the B3 research docs move to the archive

Three docs record finished passes. They are now in `archive/`:
[archive/profit_strategies.md](archive/profit_strategies.md),
[archive/exit_research.md](archive/exit_research.md) and
[archive/book_experiments.md](archive/book_experiments.md). This entry keeps their final
results. All values come from the committed backtester (re-anchored 2026-11-03), on fires
and returns from 2023-02-28 to 2026-10-15. All values are in-sample.

**Profit strategies (2026-10-19).**
- Long-only signal books lost money. The equal-weight alt universe fell 71% in 2025.
- The selection edge pays only in a market-neutral book. A hedge with BTC or the top 20
  coins lost 26–27% a year.
- B3 (long the good fires, short the bad fires, 14d) has Sharpe 1.50 [0.55, 2.56] and
  max drawdown −18%. This became the B3 spec in [trading_strategy.md](trading_strategy.md).
- BTC > SMA50 plus B3 (B4) has Sharpe 1.75 [0.71, 2.86] and max drawdown −37%. It stacks
  two in-sample picks.
- Costs decide the 7d books: v3 bullish at 7d has Sharpe −0.12 net.
- These did not work: market timing from fire clusters, plain momentum, long-only with a
  trend switch, and the failed-cross exit (C6a).

**Exits (2026-10-27, 2026-11-07).**
- Hold the shorts (S1, S2) 21 days: +0.17 [−0.09, +0.40] Sharpe, +0.09 / +0.25 by half.
  This is now one of the three rules of the stack.
- No exit rule improves the longs. Stops, take-profits, trailing stops, zero-cross exits
  and opposite-fire exits do not help in both halves.
- The short tail stop at +50% costs 0.16 Sharpe. Use +100% as insurance only.
- The S2-band flip of L2 longs is on the watchlist (2026-11-07). The stack uses the
  close, not the flip.

**Position size, risk control and filters (2026-10-30).**
- The listing-age tilt (1.5× on longs listed ≥2y and shorts listed <1y) gives
  +0.17 [−0.01, +0.35], +0.16 / +0.18 by half. It is now one of the three rules of the
  stack. Three checks are on the watchlist (2026-11-09).
- An age filter does not work, because it removes the breadth of the book.
- Volatility targets, equity-curve filters, inverse-volatility weights, beta-neutral
  sides and cluster filters do not help. B3 earns most when dispersion is high.

---

## 2026-11-16 — can the stack + quality sleeve do better?

Question: can a change to 75% stack + 25% quality sleeve increase its Sharpe? The full
write-up is in [strategy_search.md](strategy_search.md) §8. Before each batch of tests,
we recorded each hypothesis, its direction and its mechanism. The window is 2024-01-01 →
2026-10-15 (the walk-forward sleeve), with the halves 2024 / 2025–26.

**Watchlist (snapshot of 2026-11-16 00:00 UTC).** No B3 leg check has 30 episodes. The
v3 bearish leg (S1) is confirmed at 7d: +3.55 [+1.53, +5.89], 34 ep. The 21-day, band
and listing-age checks have no outcome yet. Their first outcomes come from 11-17 to
11-23.

- **No change improves the blend.** 17 variants fail. These include blend weights, a
  sleeve-score tilt on the stack, a beta-adjusted label, maker orders, sleeves with no
  model, funding filters, a funding feature and a funding-carry sleeve.
- **The gain of the sleeve is robust.** It adds +0.43 to +0.49 to the stack of each of
  the 9 detector settings, in both halves on 9 of 9. 20 placebo sleeves add −0.12 on
  average (max +0.15). With the bot's execution, the gain is +0.48 [+0.18, +0.82]. The
  sleeve's beta is −0.01.
- **Real funding (2023-12 → 2026-10, 99% of the gross):** the blend has Sharpe 2.85, and
  +0.37 [+0.06, +0.70] against the stack (+0.38 / +0.41). The sleeve alone falls from
  1.44 to 1.14, and to 0.88 in 2025–26. Its funding cost was +0.1%, +12.9% and +19.9% a
  year in 2024, 2025 and 2026. *Mechanism:* the sleeve shorts young, volatile coins. In
  2025–26, longs on those coins received 37.8% a year, so the shorts paid.
- **Funding is a fair price.** A carry sleeve receives 22.8% a year of funding and loses
  more on price (Sharpe −1.20 on price only). Thus a funding filter removes shorts that
  earn their cost.
- **The quality signs are stable.** In 2023, the raw label gave the opposite sign for
  each risk feature (high beta won, IC +0.14, t 3.0). With beta out of the label, 2023
  has the quality signs too. The 2023 reversal was the alt rally in the label.
- **A yearly retrain is enough** (blend −0.01 [−0.20, +0.20]). The sleeve alone moves
  from 1.23 to 1.86 with the retrain schedule, and the blend stays at 2.68–2.92.
- **The blend is not dollar-neutral.** The beta basket keeps it net long by 4.5% on
  average. On 3.6% of days the bot's ±10% planned-net rule sends only the closes. That
  costs up to −0.14 at $50,000.

### Tooling

- `backtest.account` takes `funding`, a day × coin matrix of real daily funding. A NaN
  cell uses the flat rate. `backtest.load_funding` reads it from `funding_history/` and
  `funding/`. Two tests pin both.
- `scripts/fetch_funding_history.py` fetches the hourly funding of each coin from
  2023-12-01 to 2026-05-15 (about 2.5 hours, once).
- `scripts/quality_sleeve.py` has `--settings` (the sleeve on the 9 settings) and
  `--funding` (each book with real funding). `--placebo` also gives the blend's gain.

### Registered this pass

Nothing. Each per-trade effect of this pass is also in the same-state non-fires:
- Stack trades against the sleeve's score: −0.84 for fires, −1.36 for non-fires.
- Crowded S2 shorts net of funding: −1.97 for fires, −1.63 for non-fires.

Thus the detector does not know these effects (research_method.md rule 4).

---

## 2026-11-09 — a search for books that do better than B3

Question: does another method or strategy do better than B3? The full write-up is in
[strategy_search.md](strategy_search.md). The pass tested about 100 books on the frozen
panel, 2023-02-28 → 2026-10-15.

**Watchlist (snapshot of 2026-11-09).** No leg check has 30 episodes, so no B3 leg has a
verdict. The verdicts outside B3 do not change: the record-peak warning is contradicted
(+1.68 [+0.78, +4.21], 107 ep), and v2 is confirmed (+1.81 [+0.06, +3.00], 75 ep).

- **Two candidates do better than B3 in the backtester.** No candidate is confirmed.
  - The stack (longs close in S2's band, shorts 21 days, age tilt 1.5×): Sharpe 2.04
    against 1.50, +0.54 [+0.08, +0.97], +0.66 / +0.43 by half. With the bot's execution:
    1.99 against 1.44.
  - 75% stack + 25% quality sleeve, 2024-01 →: 2.87 against 1.82, +1.05 [+0.31, +1.78].
- **B3's 1.50 is the best of 9 detector settings.** The others score from −0.04 to 1.32.
  The ensembles of the settings score 1.27.
- **The stack helps on the other settings:** Δ > 0 on 9 of 9, and in both halves on 7 of
  9. The age tilt alone has both halves on 9 of 9.
- **A walk-forward choice of the legs finds L1, L2, S1 and S2 by 2025-07,** and it scores
  1.36 on 2024-01 →, against 1.82 for B3. This is the better estimate of B3's edge.
- **The quality sleeve holds the edge in its quality features** (volatility, age, size,
  MAX, illiquidity). The detector features alone score 0.05 walk-forward. 30 placebo runs
  do not reach the real Sharpe of 1.44.
- **These do not help:** 19 factor books, 18 trend sleeves, the taker and maker splits,
  and the flips (negative in 2025–26 on 4 of 9 settings).
- **Family-wise, nothing passes at 5%** (52 books, best p = 0.12). The flat funding rule
  is good for the sleeve: its young shorts paid funding over the 154 live days. Its
  Sharpe falls from about 1.3 to 0.85 with the live funding gap.

### Tooling

- `cache.first_bars` and `dataset.attach_listing_age` add `listed_days` to the live
  frame. This closes the open item of archive/book_experiments.md §4.
- `backtest_tables.strategy_search` prints the tables of the stack and of the settings.
- `scripts/quality_sleeve.py` is the walk-forward sleeve.

### Registered this pass

Three per-leg checks of the listing-age tilt, at 14 days:
- L2 first fires on coins listed ≥ 2 years, against the rest of L2. A better long reads
  negative.
- S1 first fires on coins listed < 1 year, against the rest of S1 (> 0, short-side).
- S2 first fires on coins listed < 1 year, against the rest of S2. A better short reads
  negative.

---

## 2026-11-07 — the live bot's execution, and new exits

Questions:
1. Does the execution of the bot (docs/trading_bot.md) keep B3's edge?
2. What is the smallest account that trades the tested book?
3. Does an exit that archive/exit_research.md did not test help?

**Data.** The prod snapshot was synced on 2026-11-07. Its last run is 2026-11-06 20:00
UTC. The portfolio numbers come from the committed backtester on the frozen panel,
2023-02-28 → 2026-10-15 (`scripts/backtest_tables.py`, `live_execution()` and
`new_exits()`). The per-trade numbers come from scratch scripts in the backtester's
convention. The exits are in [archive/exit_research.md](archive/exit_research.md) §8.

### Watchlist (snapshot 2026-11-06 20:00 UTC)

**No leg check has 30 episodes, so no leg is confirmed or contradicted.** No leg is
dropped (trading_strategy.md §5). Bearish alpha is short-side, so a bad L2 long reads
positive.

| check | leg | registered | measure | episodes | value | verdict |
|---|---|---|---|---|---|---|
| `bullish peak_pct <= 25` | L1 | 10-16 | alpha 7d | 4 | +7.45 [+4.07, +11.20] | pending |
| `bullish peak_pct <= 25` | L1 | 10-18 | alpha 14d | 1 | −1.20 | pending |
| `bearish pullback (peak_pct >= 50)` | L2 | 10-16 | alpha 7d | 20 | +4.74 [−3.74, +12.52] | pending |
| `bearish pullback (peak_pct >= 50)` | L2 | 10-16 | alpha 14d (`--horizon 14`) | 11 | +13.39 (no interval) | pending |
| `v3 bearish (shadow)` | S1 | 10-14 | alpha 7d | 15 | +3.94 [+2.88, +5.99] | pending |
| `v3 bearish (shadow)` | S1 | 10-18 | alpha 14d | 5 | +5.29 | pending |
| S1 and S2 21-day holds | S1, S2 | 10-27 | `alpha_from_14d_21d` | 0 | — | pending |
| L2 deep-dip exit | L2 | 10-27 | `alpha_from_dip_14d` | 0 | — | pending |
| uncrossed at bar 3 | S2 | 10-23 | `alpha_from_bar3_14d` | 0 | — | pending |

- **Two checks outside B3 have a verdict.** The record-peak warning is contradicted:
  record-peak bullish fires beat their class (+1.39 [+0.49, +4.20] at 7d, 86 ep). v2
  is confirmed: +2.04 [+0.06, +3.12] at 7d, 54 ep.
- **The L2 long is the leg to watch.** Its 11 episodes at 14d lost 13.4 points of
  alpha. The 21-day checks need fires from 10-27 with a 21-day outcome, so they wait
  until about 11-18.
- *Orientation, not evidence* (out of sample from 2026-09-19, partly seen before
  registration): S1 earns +5.39 [+1.73, +7.08] at 14d (46 ep). L2 loses 0.55 at 14d
  (216 ep). Crypto S2 first fires lose 0.35 as a short (131 ep).

### B1. Resting post-only limit orders

`simulate(fill="limit")`: each order is a post-only limit order at the close before the
bar. A buy fills if the bar's low is below it, and a sell if the high is above it. The
next rebalance sends a new order. A filled order pays 0.015%. A stop and a delisting
cross the spread at 0.10%.

| book | Sharpe | Δ vs baseline [95%] | Δ 2023–24 | Δ 2025–26 | CAGR | max DD | costs a year | orders filled |
|---|---|---|---|---|---|---|---|---|
| **baseline: every order fills at the close, 0.10% a side** | 1.50 | — | — | — | +38.5% | −18% | 12.9% | 100% |
| 0.015% a side, every order fills at the close | 1.96 | +0.47 [+0.42, +0.52] | +0.41 | +0.53 | +54.5% | −16% | 1.9% | 100% |
| resting limit order, a new one each day (the bot) | 1.53 | +0.03 [−0.08, +0.13] | +0.05 | +0.04 | +39.6% | −20% | 1.9% | 98.7% |
| resting limit order for one day, then cross | 1.53 | +0.04 [−0.07, +0.13] | +0.06 | +0.04 | +39.8% | −20% | 2.2% | 98.7% |
| drift band 25%, fills at the close | 1.53 | +0.03 [−0.28, +0.35] | +0.04 | +0.03 | +41.6% | −20% | 10.6% | 100% |
| resting limit order + drift band 25% | 1.54 | +0.04 [−0.27, +0.36] | +0.09 | +0.02 | +42.0% | −20% | 1.6% | 98.7% |

- **The limit orders keep the edge, but they do not add to it.** Costs fall from 12.9%
  to 1.9% a year. The gross return falls from 50.4% to 40.2% a year. Thus the 1.3% of
  orders that do not fill cost about as much as the fee saves.
- *Mechanism:* a buy at the close before the bar does not fill only if the bar never
  trades below its open, so the price goes up all day. A sell does not fill only if the
  price goes down all day. Each order that does not fill misses a large move in the
  trade's direction, or holds a position through a large move against it.
- **Fill rate and days to fill.** 99.4% of the first-fire entries fill on the fire day.
  The mean time to fill is 0.01 days.
- **"Limit for one day, then cross" adds nothing,** because 99% of the orders fill on
  the first day.

Adverse selection of the entry order, first fires, 14-day alpha:

| leg | not filled on day 1: fires / same state | 14d alpha filled → not filled, fires | same state | bot − backtest alpha when not filled, fires | same state |
|---|---|---|---|---|---|
| L1 | 2.0% / 1.3% | +1.58 → +8.94 | +0.23 → +9.74 | −3.55 [−5.59, −2.05] | −8.85 |
| L2 | 0.8% / 0.8% | +0.98 → +2.43 | +0.86 → +8.19 | −1.70 [−3.33, −0.27] | −3.96 |
| S1 | 2.3% / 1.1% | +1.21 → +3.55 | −0.16 → +4.44 | −2.55 [−4.50, −1.37] | −2.23 |
| S2 | 0.6% / 1.1% | +0.94 → +4.51 | +0.62 → +3.53 | −3.10 [−4.80, −1.73] | −1.42 |

- **The orders that do not fill are the best trades.** Same-state coins show the same
  split, so this is how a daily bar works, not a property of the fires.
- L1 and S1 fires do not fill a little more often than their state (2.0% against 1.3%,
  2.3% against 1.1%). Over all the trades of a leg, the cost is −0.07 (L1), −0.01
  (L2), −0.06 (S1) and −0.02 (S2) points a trade.
- *Limit of the model:* the bot sends its orders at 00:10 UTC at the touch, not at the
  close. The touch can be some ticks from the close.

### B2. The stop gap

A short that a resting order opens gets its +100% stop at the next daily run. Of 3,725
S1 and S2 first fires, none traded +100% above its entry within its first bar. One
did within bars 1–2: APE (S1, 2026-04-23), +174% in bar 2, where the bot has its stop.

| leg | group | n | ≥ +100%: bar 1 / bars 1–2 | ≥ +50%: bar 1 / bars 1–2 | 14d return when ≥ +50% in bars 1–2 |
|---|---|---|---|---|---|
| S1 | fires | 1,554 | 0 / 1 | 1 / 3 | +59% |
| S1 | same state | 4,343 | 1 / 4 | 6 / 16 | +21% |
| S2 | fires | 2,171 | 0 / 0 | 2 / 8 | +58% |
| S2 | same state | 4,991 | 0 / 0 | 3 / 12 | +52% |

- **The gap keeps the edge.** The +100% stop from the next day (`stop_delay=1`) scores
  the same as the stop from the fire day: 1.41, −0.08 [−0.19, +0.01] against the
  baseline. The bot's full execution (limit orders and the late stop) scores 1.44,
  −0.05 [−0.19, +0.07].
- A short that trades +50% in its first two bars loses about 58% by day 14. At a weight
  of about 3%, that is about 1.7% of equity. It occurs on 0.3% of the shorts.
- The one same-state coin at +100% in bar 1 was a wick: ZEREBRO on 2025-10-10, high
  +232%, close −37%. A stop on that bar would have closed a short that ended the day in
  profit.

### B3. Small accounts and the $10 minimum order

`simulate(equity=...)`: the equity in USD is the same each day. An order below $10
does not go, and a full close always goes. If the planned book is more than ±10% net,
only the closes go. All rows use the bot's execution (limit orders, stop from the next
day).

| book | Sharpe | Δ vs baseline [95%] | Δ 2023–24 | Δ 2025–26 | CAGR | max DD | days with only the closes | max \|net\| | correlation with the baseline |
|---|---|---|---|---|---|---|---|---|---|
| band 25%, $500 | 0.65 | −0.85 [−2.08, +0.24] | −0.34 | −1.37 | +13.1% | −31% | 69% | 60% | 0.53 |
| band 25%, $1,000 | 0.92 | −0.58 [−1.39, +0.29] | +0.43 | −1.62 | +22.1% | −19% | 51% | 60% | 0.78 |
| band 25%, $2,000 | 1.24 | −0.25 [−0.69, +0.26] | −0.20 | −0.41 | +32.5% | −22% | 38% | 49% | 0.87 |
| band 25%, $5,000 | 1.36 | −0.14 [−0.48, +0.29] | −0.15 | −0.16 | +36.0% | −21% | 32% | 43% | 0.91 |
| band 25%, $10,000 | 1.36 | −0.13 [−0.48, +0.31] | −0.19 | −0.11 | +36.1% | −21% | 33% | 43% | 0.91 |
| band 25%, no minimum | 1.45 | −0.05 [−0.38, +0.27] | +0.13 | −0.21 | +38.7% | −20% | 0% | 29% | 0.94 |
| band 0%, $500 | 0.63 | −0.86 [−2.13, +0.22] | −0.33 | −1.40 | +12.8% | −33% | 68% | 53% | 0.53 |
| band 0%, $1,000 | 0.83 | −0.66 [−1.39, +0.15] | +0.52 | −1.85 | +19.4% | −21% | 47% | 60% | 0.80 |
| band 0%, $2,000 | 1.28 | −0.22 [−0.59, +0.21] | +0.01 | −0.50 | +32.7% | −22% | 19% | 45% | 0.92 |
| band 0%, $3,000 | 1.45 | −0.04 [−0.27, +0.19] | +0.13 | −0.22 | +37.9% | −18% | 7% | 44% | 0.97 |
| **band 0%, $5,000** | 1.49 | −0.00 [−0.16, +0.15] | +0.21 | −0.18 | +38.4% | −17% | 0% | 22% | 0.98 |
| band 0%, $10,000 | 1.46 | −0.03 [−0.17, +0.08] | +0.11 | −0.16 | +37.4% | −18% | 0% | 21% | 0.99 |
| band 0%, no minimum | 1.44 | −0.05 [−0.19, +0.07] | +0.09 | −0.18 | +36.7% | −19% | 0% | 21% | 0.99 |

The table in `backtest_tables.py` also has band 25% at $3,000.

- **With the bot's 25% drift band, no account size trades the tested book.** The band
  lets the held weights drift, and the drift makes the book net. Then the planned-net
  rule sends only the closes on about a third of the days, at every size. The closes
  can all be on one side, so the net goes up to 43%, against 29% with no rule.
- **With no band, $5,000 is the smallest tested account that trades the tested book.**
  No day sends only the closes, and the returns have a correlation of 0.98 with the
  baseline. At $3,000, 7% of the days send only the closes.
- *Mechanism below $5,000:* at $2,000, a name is about $60. When a name opens or
  closes, each other name of that side changes by $2–3, below the minimum. Those
  resizes do not go, the side drifts, and the planned net goes above 10%. Then the
  bot opens nothing until enough positions close.
- **At the maker fee, the band saves little:** 1.9% → 1.6% of costs a year.

### B4. Funding by leg

Live funding (`state/research_cache/funding/`, hourly), first fires 2026-05-15 →
2026-10-15, mean funding over the 15 days of the hold. Plus means that longs pay. One
regime only, so this is orientation.

| leg | fires (n) | same state (n) | the leg pays a year (+) or receives (−), fires | backtest |
|---|---|---|---|---|
| L1 | +5.4% [−0.5, +9.6] (119) | +5.5% [+3.0, +8.4] (462) | +5.4% | +9.0% |
| L2 | −1.1% [−9.0, +4.2] (500) | +3.2% [−2.6, +7.1] (1,557) | −1.1% | +9.0% |
| S1 | +3.6% [−0.4, +6.7] (244) | +5.3% [+1.6, +9.2] (913) | −3.6% | −6.5% |
| S2 | +1.7% [−4.8, +7.7] (357) | +4.7% [−2.3, +10.1] (974) | −1.7% | −6.5% |

The universe pays +3.3% [+0.2, +6.1].

- **The longs are not crowded.** L1 pays what its state pays. L2 pays less than its
  state and less than the universe.
- *Mechanism:* an L2 fire is a pullback. The longs leave, and funding falls. L2's
  funding in the 7 days before the fire is −0.6% APR, against +6.2% for its state.
- **The shorts receive less than the backtest assumes.** Net, the book received about
  2.3% a year of side gross. The backtest charges it about 2.5%.

### Exits (archive/exit_research.md §8)

- **No new exit helps in both halves per trade:** an exit when the edge is paid,
  take-profits and a give-back in ATR units, a rank exit, a scale-out, and same-leg
  restarts. As portfolios, the edge-paid exit costs −0.49 [−1.03, −0.01], and the
  rank exit costs −0.25. The others, except the S2-band exit below, are within ±0.08.
- **Why S2 as the MACD state scores 2.15:** it flips the longs whose coin falls into
  S2's band to shorts. Without those flips it scores 1.27. If the book closes those
  longs and does not short them, it scores 1.76 (+0.26 [−0.12, +0.62], +0.48 / +0.03).
- Per trade, the flip is an L2 effect. 45% of L2 first fires enter S2's band by day
  13. As a short for 14 days from that close, they earn +1.71 [+0.05, +3.62] in
  2023–24 and +0.24 in 2025–26 (same state +1.28 / −1.20).

**Plumbing check** of the new column on the 2026-11-07 snapshot: 53% of the live
crypto pullback first fires enter S2's band by day 13 (history: 45%). Their live
`alpha_from_band_14d` is +3.50 [+1.14, +7.25], 261 ep. Those fires were seen before
registration, so this is orientation.

### Tooling

- `backtest.simulate` has four new variants: `fill` ("close", "limit",
  "limit_then_cross"), `stop_delay`, `equity` and `restart_same_leg`. `account` has
  `equity`, `fills` and `cross`. The constants are `MAKER_COST`, `MIN_ORDER_USD` and
  `MAX_PLANNED_NET`.
- `backtest.with_low` adds the bar lows to the frozen panel from the candle CSVs. It
  stops if a close is not the panel's close. `Run` has `sent`, `filled` and
  `closes_only`. The baseline does not change (the golden test passes).
- `dataset.first_deep_dip` takes `in_state`. `attach_band_flip` adds `s2_band_day` and
  `alpha_from_band_14d`.

### Registered this pass

- `crypto pullback, first fires, S2 band by day 13` (`rules.AFTER_FIRE_RULES`, metric
  `alpha_from_band_14d`): a pullback long whose coin enters S2's band is a good short
  for 14 days from that close (> 0 short-side).

---

## 2026-11-04 — the tilt cap fix

Question: does a tilt keep B3 dollar-neutral? It did not. A tilt pushed some names
above the 10% cap. `_weights` cut them to 10%, and the excess went to cash. Thus the
tilted side was smaller than the other side. Now the excess moves to the other names
of the same side. The baseline does not change, because equal weights never go above
the cap. Only the 8 rows with a tilt change (archive/book_experiments.md §1 and §3).

- **The 1.5× age tilt changes little:** +0.19 [−0.01, +0.40] → +0.17 [−0.01, +0.35],
  positive in both halves (+0.16 / +0.18). Before the fix, it was net long or net
  short on 27% of days, by up to 10%.
- **Most of the 1/volatility penalty was the error.** It goes from −0.17 to −0.07
  [−0.39, +0.31]. Before the fix, that book was net long or net short on 64% of days,
  by up to 30%. The 1/√(volatility) weights go from −0.04 to +0.00.
- **A tilt cannot act on a thin side of 10 names or fewer**, because each name is at
  the cap. The short side is at the cap on 30% of days in 2023–24, and on 6% in
  2025–26.
- **The short half of the age tilt does not help in 2023–24** (+0.06 → −0.01). The
  long half alone has the only interval above zero: +0.13 [+0.01, +0.26].
- **In 2023–24, the gain needs the pre-2021 listings.** Without their extra weight,
  +0.01 of +0.16 stays. They are 62% of the old long first fires in 2023–24, and 31%
  in 2025–26. In 2025–26, +0.15 of +0.18 stays.

Nothing registered: the live frame still has no listing age.

---

## 2026-11-03 — the committed backtester; portfolio numbers re-anchored

Question: why does B3's Sharpe differ across the docs (1.11 to 1.42) when the fires
are the same? The scratch builds used different portfolio rules and did not record
them. `research/backtest.py` (commit `9238751`) now pins each rule. With the bar cut of
the 2026-10-27 build, it gives that build's Sharpe 1.4215 exactly. The pinned baseline
is **Sharpe 1.50 [0.55, 2.56], CAGR +38.5%, max drawdown −18%** (2023-02-28 →
2026-10-15). The portfolio tables of archive/profit_strategies.md, trading_strategy.md,
archive/exit_research.md and archive/book_experiments.md come from it now.

- **The universe basket is expensive.** Its daily rebalance now pays costs. B2 goes
  from 0.92 to 0.47 (0.98 with a free rebalance). Each universe-hedged book is weaker.
- **Signs that changed:** "every leg 7 days" against 14 (+0.13 → −0.05), the B3 hold
  order (7 > 14 > 21 → 7 < 14 < 21), B2 at 30 days, v3 bullish at 14d, and four cells
  of the C6a table. None changes a decision.
- **One comparison changed its conclusion.** S2 traded as the MACD state now scores
  2.15 against 1.50 for S2 fires (+0.65 [−0.06, +1.31], both halves). The 2026-10-25
  table below says "the same book" (1.06). The state book has a broader short side,
  and it flips longs whose coin falls into a deep dip. It is not registered yet.
- **Two intervals now include zero:** the 1.5× age tilt (+0.19 [−0.01, +0.40]) and S1
  alone to 21 days (+0.14 [−0.02, +0.32]). Both stay positive in both halves.

The 2026-10-25 portfolio table below is superseded.

---

## 2026-10-28 — L2 and S2 by `peak_pct` band and histogram reduction

Question: how do B3's L2 and S2 legs change with the `peak_pct` band and with the
histogram reduction (`red`) at the fire?

Data: the closed-bar rebuild, extended with the live candle cache to 2026-10-24. The
data is crypto only. The tables use the first fire of each episode, as B3 trades. Alpha
is in the direction of the trade. Intervals use week blocks. The panel has 95,921
coin-days and 26,972 fires. Before 2026-06-08, 23,122 of the 23,125 cached rebuild fires
match, with the same `peak_pct` and `red`. The scripts are scratch and are not committed.
All of this is in-sample.

| leg | band | 7d | 14d | 21d | episodes |
|---|---|---|---|---|---|
| L2 | 50–75 | +0.35 | +0.19 | | 1,438 |
| L2 | 75–<100 | **+1.80** [+0.71, +2.87] | **+2.24** [+0.73, +3.76] | | 802 |
| L2 | 100 | +1.48 [−0.29, +3.44] | −0.12 [−2.30, +2.17] | | 655 |
| S2 | 50–75 | +0.21 | +0.58 | +0.73 | 1,403 |
| S2 | 75–<100 | +0.54 | **+1.44** [+0.33, +2.49] | **+2.23** [+0.95, +3.48] | 821 |

- **At 14d, the 75–<100 band holds all of L2's alpha.** It is positive every year. It
  beats the rest of the leg by +2.15 [+0.46, +3.90]. The full leg is +0.68 [−0.05, +1.42].
- **Record peaks (100) earn +1.48 in week 1 and lose it by day 14.**
- **S2's deeper band is better**, by +0.86 [−0.56, +2.30] at 14d and +1.51 [−0.07,
  +3.14] at 21d. Both intervals include zero.
- The 2026-10-18 band table used the mean of all fires in each episode. Re-fires are
  better longs (H9), so that table showed bearish 25–50 and 50–75 too high. On first
  fires, bearish 25–50 as a long is +0.18 / +0.38 at 7d / 14d. That is ≈ 0, as
  trading_strategy.md §1.1 says.

**Histogram reduction does not sort either leg.** The `red` bins are round numbers near
the quartiles of `red`. They were fixed before the first look.
- By `red` alone (0.30–0.45 / 0.45–0.60 / 0.60–0.80 / 0.80–1.00) at 14d: L2 is +0.89 /
  +0.52 / −0.21 / +1.18, and S2 is +0.72 / +1.96 / +0.13 / +0.72. There is no gradient.
- In each band, the rank IC of `red` against alpha is between −0.08 and +0.06. Only 1
  of 12 intervals excludes zero: S2 50–75 at 14d, +0.06 [+0.00, +0.11].
- One cell passes the usual robustness tests: S2 50–75 × `red` 0.45–0.60, +2.81 [+1.12,
  +4.43] at 14d (323 ep). Without its top 10 symbols, it is +2.52. Both halves of the
  history are positive. But the best `red` bin changes between bands, and no mechanism
  explains it. It is 1 cell of about 80, so it is not a finding.
- The same cell in L2 (+0.94 at 14d) falls to +0.20 without its top 10 symbols.

**Counterfactual.** Almost no coin retraces 30% without a fire: 37 coin-days in 3.6
years in L2's bands. Thus, a test of `red` against non-firing coins is not possible.
This agrees with 2026-10-25: the detector finds each such setup. The possible comparison
is the same band before the histogram retraces 30%. These coin-days have a retrace below
0.30, a peak above the noise floor, and no same-side fire in the last 5 days.

| 14d | state, retrace < 0.30 | fire |
|---|---|---|
| L2 50–75 | −0.35 | +0.19 |
| L2 75–<100 | +0.94 | +2.24 |
| L2 100 | **+2.15** [+0.06, +4.39] | −0.12 |
| S2 50–75 | +0.35 | +0.58 |
| S2 75–<100 | +0.81 | +1.44 |

- In the 75–<100 band, the L2 fire adds approximately +1.3 to its state.
- **On record peaks, the fire is a worse long than its state.** A record rally that
  continues to extend continues to pay. After its histogram falls by 30%, the rally gives
  back its week-1 gain by day 14. In the record band, a deeper `red` is also worse: IC
  −0.06 [−0.13, +0.01] at 14d.
- *Mechanism (hypothesis):* a record-strength excursion is a blow-off. When its momentum
  falls by 30% or more, the move is complete.
- The S2 fire adds little to its state (+0.2 / +0.6), as on 2026-10-25.

### Registered this pass

- The crypto pullback with 75 ≤ `peak_pct` < 100 against the rest of the pullback,
  first fires, 14d. A better long reads negative.
- The same band against record-peak pullbacks, first fires, 14d.

---

## 2026-10-30 — B3 position size, risk control and filters

Question: can position size, book-level risk control, or a filter increase B3's gains
or decrease its losses? The full results are in
[archive/book_experiments.md](archive/book_experiments.md). The data and the baseline are the same as
on 2026-10-27. Each variant is a paired bootstrap, split 2023–24 / 2025–26.

- **A listing-age tilt is the one tangible result.** It gives 1.5× weight to longs
  listed ≥ 2 years and to shorts listed < 1 year. It adds **+0.23 [+0.03, +0.42]**
  Sharpe, positive in both halves. Same-state non-fires show the same effect, and a
  book on age alone makes nothing (Sharpe 0.06). Thus age is a property of the coin
  that the state makes larger. Mechanism (hypothesis): unlock supply meets strength.
- **A filter on age fails.** It cuts the long side from 32 to 18 names, and 2025–26
  becomes worse.
- **Risk controls fail.** B3 earns most when trailing dispersion is high (Sharpe 1.01
  / 1.58 / 1.70 by tercile). Its risk increases as fast as its return. Thus a
  volatility target cuts exposure when the book earns most. Monthly autocorrelation is
  −0.21, so an equity-curve filter only removes good months.
- **No effect:** inverse-volatility weights, beta-neutral sides (both sides have beta
  ≈ 0.99), cluster-day filters, re-fires after entry.
- **Observation only:** L1 and L2 fires on a weekend decision day have about 0 alpha,
  in both halves. S1 and the non-fires do not agree, so no mechanism explains it.

Not registered: the live research frame has no listing age yet. archive/book_experiments.md §4
gives the two checks to register after the feature exists.

---

## 2026-10-27 — exits for B3

Question: does any exit beat B3's 14-day time exit? Full write-up in
[archive/exit_research.md](archive/exit_research.md). Fires 2023-03-02 → 2026-10-08, first fire per
episode, candles to 2026-10-24. Every rule is reported on 2023–24 and 2025–26
separately.

- **The legs run on different clocks.** The longs' fire edge is spent by day 14, and
  L2's by day 7. S1 and S2 keep earning in days 14–21 (+0.50, +0.71), positive every
  year. Holding the shorts 21 days adds **+0.27 [−0.05, +0.58]** Sharpe to the book.
  The gain is positive in both periods, holds at 0.05–0.20% costs, and short holds of
  21–30 days form a plateau.
- **Path exits don't work.** Stops, take-profits and trailing stops on alpha, and
  zero-cross and opposite-fire exits, are noise, flip with the market, or cost alpha.
  The good longs lean towards reversal after a bad start (C6a).
- **State exit, hypothesis only.** An L2 long whose coin falls into a deep dip loses
  −1.57 more by day 14. Exiting it adds +0.65 per trade in 2023–24 and +0.13 in
  2025–26.
- **The short tail stop at +50% costs 0.11 Sharpe.** 63% of the shorts that touch +50%
  end the 14 days better than the stop.

**Tooling.** The pipeline now has a 21-day horizon (`dataset.CANDLE_HORIZONS`),
measured from closed candles only, because the database scores outcomes to 14d. A
symbol's newest cached bar is never read, since it may have been forming when cached.
Two new late-entry metrics:
- `alpha_from_14d_21d`: entry at the 14d exit, exit at day 21.
- `alpha_from_dip_14d`: from the first close after the fire on which the coin is in a
  deep dip (`deep_dip_day`, bearish fires only) to the 14d exit.

Each after-fire rule now names its metric in `rules.AFTER_FIRE_METRIC`, and a test pins
it. `--horizon 21` also works for the cohort table.

**Plumbing check** on the 2026-10-27 snapshot. Fires through 2026-10-03 have a 21d
outcome, 99.9% of the crypto rows that have a 14d outcome. A deep dip comes before the
exit on 33% of crypto pullback first fires (history: 31%). These live episodes were
all seen before registration, so they are orientation, not evidence:

| leg | measure | live value | episodes |
|---|---|---|---|
| S1 | days 14–21 | +0.25 [−0.85, +1.10] | 208 |
| S2 | days 14–21, long-side | −0.74 [−1.80, +0.86] | 233 |
| L2 | after a deep dip, short-side | +3.03 [+0.99, +6.99] | 159 |

### Registered this pass

- S1 and S2 crypto first fires: alpha from the 14d exit to day 21 (> 0 as a short).
  These are two checks, so each leg's hold can switch on its own.
- Crypto pullback first fires whose coin falls into a deep dip by day 13: alpha from
  that close to the 14d exit, expected negative for the long.

---

## 2026-10-25 — periodic pass: the fire vs the state it fires in

Snapshot synced 2026-10-25 (latest run 04:00 UTC): 8,578 deduped signals, 7,474 with a
7d alpha in 2,304 episodes. The report ran with `--scan`.

**Watchlist: still nothing to score.** All 20 checks are pending. The most fresh
episodes any check has is 25 (ATR expanding). 7d outcomes reach fires through
2026-10-17, and the 14d checks have none yet.

**What moved.** These windows were seen before, so they are for orientation only:
- The live bullish `peak_pct` IC has turned the wrong way since 2026-09-19: +0.10
  [−0.01, +0.24] (220 ep), against −0.05 on 2026-10-15. Over the same window the
  deep-bullish leg is +0.52 long-side (161 ep), so the short lost. That is one falling
  month. History is unaffected (below).
- Bullish 00:00 first fires: −1.48 [−2.50, −0.60] overall. The 7 episodes since
  registration read +3.38.
- Bearish: no feature reaches q ≤ 0.25, as before.

### What the fire adds over the MACD state (history)

Question (archive/profit_strategies.md §6.5): is B3 an own-history momentum sort that the
detector happens to sit on, or does the fire itself add something? To answer it I built a
panel of every eligible coin-day, 95,928 rows from 2023-03 to 2026-10-24. The history
CSVs were extended with the live candle cache. Each row records the MACD state the
detector sees (excursion sign, `peak_pct` against the coin's own history), whether it
fired or not. It reproduces the rebuild exactly: 26,569 fires, identical `peak_pct` and
alpha. The table uses long-side excess vs the eligible-universe mean, first fire per
episode, and week-block intervals. "Not fired" means same side and band, with no
same-side fire in the last 5 days. Everything here is in-sample.

| leg (trade) | fires 7d (ep) | same state, not fired | fire − state, 7d | fire − state, 14d | years right side (7d) |
|---|---|---|---|---|---|
| bullish `peak_pct ≤ 25` (long) | +1.31 (1,012) | +0.21 | **+1.10 [+0.33, +1.89]** | **+1.62 [+0.55, +2.73]** | 4/4 |
| bearish `peak_pct ≥ 50` (long) | +1.03 (3,455) | −0.08 | **+1.12 [+0.44, +1.80]** | +0.33 [−0.57, +1.27] | 4/4 |
| bearish `peak_pct ≤ 25` (short) | −0.95 (1,557) | +0.04 | **−0.99 [−1.65, −0.32]** | **−1.18 [−1.99, −0.33]** | 4/4 |
| bullish `50 < peak_pct < 100` (short) | −0.40 (2,179) | −0.42 | +0.02 [−0.60, +0.68] | −0.35 [−1.20, +0.57] | 2/4 |

- **On three of B3's four legs, the fire adds about ±1.1% at 7d**, on the right side
  every year. Matching the non-fires on own-history 10d and 30d return quintiles as well
  leaves it unchanged: +1.19 / +1.05 / −1.11 at 7d, every interval clear of zero.
- **Own-history price momentum is not B3.** Take the percentile of a coin's 30d return
  among its own last 200 values. Across all coins it has IC −0.045 [−0.062, −0.030]
  with 14d excess. That is short-term *reversal*, the opposite sign to the pullback leg.
  A price sort can't stand in for the detector, which answers §6.5.
- **The deep-bullish short leg is the state, not the fire.** Coins in a deep negative
  excursion underperform whether or not the detector fires (−0.42 vs −0.40).
- **Across the universe, mild excursions revert and extreme ones continue.** All coin-days
  at 14d, each state against the rest (state mean by year 2023 / 24 / 25 / 26):
  - Mild dip (hist < 0, `peak_pct ≤ 25`): +0.46 [+0.02, +0.90] (−0.48 / −0.30 / +0.57 / +0.84).
  - Mild rally (hist > 0, ≤ 25): −0.50 [−0.93, −0.09], negative every year.
  - Strong rally (hist > 0, 75 to < 100): **+1.86 [+0.74, +3.05]**, positive every year.
  - Deep dip (hist < 0, 75 to < 100): **−1.38 [−2.05, −0.71]**, negative in 3 of 4 years.

  Each B3 leg is one of these states, and the fire sharpens three of them. As a single
  linear score, the signed excursion has IC ≈ 0 (−0.01) because the relationship bends.
- **The trigger bar isn't the edge.** Some same-state coins clear the noise floor and
  have retraced ≥ 30% but didn't fire. Almost all of them are the day after a fire. Once
  recent fires are excluded, only 19–133 per leg remain in 3.6 years. The day-after rows
  do as well as the fire (bullish `peak_pct ≤ 25` at 7d: +2.03, 252 rows). So the
  detector catches essentially every "real excursion, ≥ 30% retraced" setup, and the
  exact bar it fires on doesn't matter. That is C6a's conclusion reached from the other
  side.
- *Mechanism (hypothesis):* a move that is modest by the coin's own standards is noise
  around its trend, and it reverts. An extreme one carries information (a trend, or a
  breakdown), and it persists. On the mild legs, the fire finds a real excursion that
  has already turned: a dip that is both small and over. On the deep leg it has nothing
  to add. The state already says "breakdown", and the histogram turning doesn't end it.

**As portfolios.** Built as in archive/profit_strategies.md: 14d hold, 0.10% a side, flat funding.
*Superseded 2026-11-03: the committed backtester gives other values (entry of that
date).*

| book | CAGR | Sharpe [95%] | max DD | 2023 / 24 / 25 / 26 |
|---|---|---|---|---|
| B3, all fires (the doc's 1.11; calibration) | +27.7% | 1.14 [0.19, 2.29] | −23% | +20 / +7 / +81 / +5% |
| B3, first fires only | +34.5% | 1.29 [0.35, 2.47] | −21% | +13 / +17 / +106 / +8% |
| B3, deep leg traded as the state (any coin) | +23.5% | 1.06 [0.11, 2.22] | −29% | −1 / +17 / +53 / +22% |
| B3, deep leg dropped | +18.1% | 0.65 [−0.29, 1.86] | −41% | +50 / +2 / +53 / −22% |
| state only: long strong rally, short deep dip | +12.5% | 0.49 [−0.56, 1.50] | −52% | +13 / +45 / −1 / −5% |

- **The state book is not a strategy** (Sharpe 0.49, −52% drawdown). Trading the deep
  leg as the state instead of as fires changes nothing. B3 stays as it is. The deep leg
  still earns its place: dropping it halves the Sharpe.

**A mechanism test that failed.** If deep dips underperform because they are
coin-specific collapses ([archive/confidence_v3.md](archive/confidence_v3.md)), the effect should fade
on days when many coins are in a deep dip at once. Using history before the live period
at 14d, it doesn't. Deep fires are −0.56 on low-breadth days (87 ep), −0.11 on mid days,
and **−1.12 [−1.82, −0.45]** on high-breadth days (1,387 ep). Breadth explains neither
the leg nor its live October failure.

**Counterfactual for the pending "uncrossed at bar 3" short.** The test measures deep-dip
coins from bar 3 to 14d:
- First fires still uncrossed at bar 3: −1.07 [−1.72, −0.46]. That is 59% of fires and
  reproduces C6a.
- Non-firing coins in the same state, uncrossed: −0.46 [−0.89, −0.05]. That is 94% of
  them.
- Fire − state among the uncrossed: −0.61 [−1.40, +0.19], with the fire worse in 3 of 4
  years.

About 40% of the check's expected effect is the state persisting. The check stays as
registered.

### Funding before the fire (live)

The 2026-10-14 pass saw high funding mark bad bullish fires, but only over 2026-09-19 →
10-07. The table gives the episode IC between 7d funding and 7d alpha for each window.
Fires from 10-08 to 10-17 had not been seen then. The counterfactual is every crypto coin
in the day's first run that did not fire bullish.

| window | bullish fires | non-firing coins |
|---|---|---|
| Jun–Sep | −0.06 (856 ep) | −0.01 |
| 09-19 → 10-07 | −0.21 (119 ep) | +0.01 |
| 10-08 → 10-17 (fresh) | **−0.23** (102 ep) | −0.09 |

- **The effect is specific to bullish fires.** It is not a generic crowding factor.
- **Two limits.** The fresh window covers only two weeks, so its interval means nothing.
  Every window since September is the same falling market.
- *Mechanism (hypothesis):* a bullish fire is a dip whose selling is slowing. If longs
  kept paying up into the dip, the dip hasn't flushed them, and the unwind is still to
  come. Non-firing coins with high funding are mostly trending up, where crowding means
  something else.

### Registered this pass

- Bullish fires with 7d funding ≥ 15% APR vs the rest of bullish (alpha < 0). 15 is a
  round number about 4 points over Hyperliquid's ~11% baseline. Bullish fires: median
  8.2, p80 12.6, p90 18.0. As a cohort since June it reads −2.27 [−4.29, −0.36] (210 ep),
  negative in all five months. Those months are seen data and are not evidence.

The panel, state and backtest scripts were scratch and are not committed. Inputs:
`state/research_cache/history/*.csv` extended with `state/research_cache/candles/`.

---

## 2026-10-24 — SMA50 / SMA100 / SMA200 on the good and bad fires

Question: the 2026-10-19 SMA200 split, run again on the 50- and 100-day averages and
on all four B3 legs. History rebuild, first fire per episode, fires 2023-03-02 →
2026-10-08, candles to 2026-10-16. "Above" means the prior close is above the average
(`dist_smaN_atr > 0`, the same bar the entry uses). Alpha is in the trade's
direction, so a bad fire's positive number is a good short. Week-block 95% intervals.
Everything here was found on this same history; nothing is out of sample. Scratch
script, not committed.

| leg (trade) | average | 7d above (ep) | 7d below (ep) | 7d above − below | 14d above − below |
|---|---|---|---|---|---|
| bearish `peak_pct ≥ 50` (long) | SMA50 | +1.37 (2,214) | +0.43 (1,241) | +0.94 [−0.09, +2.01] | −0.30 |
| | SMA100 | +1.77 (1,884) | +0.15 (1,571) | **+1.62 [+0.64, +2.65]** | +0.22 [−1.17, +1.55] |
| | SMA200 | +1.65 (1,703) | +0.44 (1,752) | **+1.21 [+0.10, +2.38]** | +0.16 |
| bullish `peak_pct ≤ 25` (long) | SMA50 | +1.97 (276) | +1.06 (736) | +0.91 [−0.60, +2.44] | +0.09 |
| | SMA100 | +1.27 (224) | +1.32 (788) | −0.05 | −1.07 [−3.50, +1.14] |
| | SMA200 | +0.92 (135) | +1.37 (877) | −0.45 | −1.08 [−3.40, +1.04] |
| bearish `peak_pct ≤ 25` (short) | SMA50 | +0.61 (478) | +1.10 (1,079) | −0.50 [−1.70, +0.74] | −0.87 |
| | SMA100 | +0.50 (397) | +1.11 (1,160) | −0.61 | +0.09 |
| | SMA200 | +0.81 (268) | +0.98 (1,289) | −0.17 | +0.45 |
| bullish `50 < peak_pct < 100` (short) | SMA50 | +0.05 (727) | +0.57 (1,452) | −0.52 [−1.68, +0.69] | −1.03 |
| | SMA100 | +0.16 (891) | +0.56 (1,288) | −0.40 | −0.48 |
| | SMA200 | +0.88 (835) | +0.10 (1,344) | +0.79 [−0.19, +1.75] | +0.48 |

- **Only the pullback long depends on the trend, and only over the first week.** All
  three averages agree. At 7d the gap is +0.9 to +1.6 and positive every year (SMA100:
  +0.50 / +0.63 / +2.61 / +2.48). By 14d it is gone: pullbacks below the average go
  from +0.15 at 7d to +0.84 at 14d, and those above go from +1.77 to +1.05. The trend
  changes how fast the pullback pays, not how much. That helps a 7d hold. It adds
  nothing to B3's 14d book.
- **Counterfactual: being above the average is not the edge.** Non-firing coins on the
  same days and on the same side of SMA100 score −0.08 above and −0.43 below. Fire minus
  those coins is +1.86 [+0.92, +2.84] above and +0.58 [−0.13, +1.32] below. Dose
  response at 7d, by distance above SMA100 in ATRs (pullback / non-firing coins):
  −2…0: +0.31 / −1.42; 0…2: +1.19 / −0.31; 2…4: +2.26 / −0.46; 4…6: +2.71 / +1.70;
  > 6: −3.55 / −2.35 (48 ep). The fire's edge rises with the trend and the non-firing
  coins' alpha doesn't, until coins are stretched more than 6 ATR.
- **SMA100 isn't "the best average".** Its gap (+1.62) and SMA200's (+1.21) sit
  inside each other's intervals, and picking it after seeing all three would be
  selection. The SMA200 check registered 2026-10-19 stays the single test.
- *Mechanism:* the pullback fire marks momentum cooling after a big move up. Above the
  average, that move belongs to an established trend. Trends persist, so the pause
  resolves upward within days. Below the average the same move is a rally inside a
  downtrend and doesn't extend in week 1. Why those then catch up in week 2 is **not
  explained**.
- **The other three legs don't care about the trend.** Bullish `peak_pct ≤ 25` and the
  bearish `peak_pct ≤ 25` short work above and below every average. Their gaps are
  noise, and in both cases most fires sit below the averages (73–87% for the bullish
  leg).
- **The deep-bullish short fails in one state: early recovery** (above SMA50, below
  SMA200). Short alpha 7d / 14d: −1.94 / −1.61 (220 ep) there, against +0.50 to +1.49
  in the other three combinations. Long-side difference vs the rest of the leg is
  +2.60 [+0.04, +5.11] at 7d and +2.83 [−0.76, +6.03] at 14d. That is why SMA50 and
  SMA200 seemed to point opposite ways. The counterfactual doesn't support a story,
  though. Across all days, coins in early recovery *trail* the universe (−1.30 at 7d,
  negative 2023–25). On the days these fires happen, non-firing early-recovery coins
  beat it (+1.54). So the fire adds little against its own peers (+0.49), and the
  failure looks like *which days* these fires land on (alt rebounds), not a property
  of the state. No mechanism yet. It comes out of a 2×2 cut over five legs and two
  horizons, so selection is likely.
- The all-bullish row repeats 2026-10-19: above SMA200 −0.46 vs +0.23 below (7d).

### Registered this pass

- Deep-bullish short in early recovery vs the rest of the deep-bullish leg, 14d.
  Long-side, so a worse short reads positive. Hypothesis only: no mechanism.

---

## 2026-10-23 — failed-cross exit on the good fires

Question: should v3 bullish and bullish `peak_pct ≤ 25` trades be closed if MACD
hasn't crossed its signal line *k* bars after entry? History rebuild, first fire per
episode, fires 2023-03-02 → 2026-10-08, candles to 2026-10-15. Full write-up in
[archive/profit_strategies.md](archive/profit_strategies.md) §C6a.

- **No.** Per trade the exit costs alpha at every *k* (v3 7d, k = 3: −0.25 [−0.48,
  −0.03]; `peak_pct ≤ 25` 7d: −0.31 [−0.61, −0.06]). As a universe-hedged portfolio
  the Sharpe moves ±0.2 with no trend in *k*, which is noise.
- **Mechanism:** uncrossed good fires are down about 2% vs peers at bar 3 but then
  earn as much or more alpha than crossed ones (`peak_pct ≤ 25`: +0.87 vs +0.31). The
  edge is slow selection, and the cross is short-horizon timing.
- **Counterfactual:** across all eligible coins with a negative histogram, "no cross by
  bar 3" is worth only about −0.2. On the bad bullish fires (`50 < peak_pct < 100`) the
  sign flips: uncrossed fires keep drifting (−1.08 after bar 3, 14d), and the exit
  helps a long by +0.58 [+0.24, +0.91].
- **Registered:** "bullish 50 < peak_pct < 100, uncrossed at bar 3", expected to be a
  good short from the bar-3 close to 14d (−1.08 in history). It is a refinement of
  B3's short leg.

**Tooling.** `dataset.crossed_by_bar3` checks whether the closed-bar MACD histogram
crossed on the first three daily closes from the fire day. `dataset.attach_late_entry`
gives `alpha_from_bar3_Nd`: entry at the close of fire day + 2, against the same-run
class mean over the same bars. Rules that read what happened after the fire live in
`rules.AFTER_FIRE_RULES`, outside the cohort table, and a test pins them to the
late-entry metric. Scored from the fire, an "uncrossed" rule would be measuring its own
first bars. Plumbing check on the live snapshot: 98% of signals have the cross flag,
and 398 episodes match the rule before registration. Those episodes are not
evidence.

## 2026-10-19 — strong assets instead of alts

Question: do the trades work better on assets that trend up (crypto majors, index
equities)? Picking BTC/ETH/BNB/HYPE *because* they did well is hindsight, so the
counterfactual here is **holding the same asset on random days of the same window**
("fire − hold"), next to alpha. The rule version uses only what was known at the time:
price above its 200-day average at the prior close. First fire per episode, 7d long.

**Crypto history (2023 → 2026-10-08, closed candle):**

| | trades | raw | hold same asset | fire − hold | alpha |
|---|---|---|---|---|---|
| BTC/ETH/BNB/HYPE, pullback long | 147 | +0.41 | +1.05 | −0.64 [−2.22, +0.96] | +1.14 |
| BTC/ETH/BNB/HYPE, v3 bullish | 52 | +1.88 | +1.16 | +0.72 [−2.78, +4.28] | +3.31 |
| coin above SMA200, pullback long | 1,733 | +2.49 | −0.22 | **+2.70 [+0.27, +5.47]** | +1.66 |
| coin above SMA200, pullback pk ≥ 75 | 1,176 | +3.65 | −0.03 | **+3.68 [+0.68, +6.64]** | +2.19 |
| coin above SMA200, all bullish | 1,987 | −1.88 | −0.27 | −1.61 [−4.35, +0.93] | −0.44 |
| alts below SMA200, pullback long | 1,769 | −1.47 | −0.91 | −0.56 [−2.76, +1.59] | +0.38 |

- **On the named majors, the signals don't beat holding them.** Their alpha against
  the alt universe is just majors beating alts, which holding them gets too.
- **The pullback long belongs to coins in an uptrend.** Above SMA200 it beats holding
  the same coin by +2.7 to +3.7. Below SMA200 it is ≈ 0. This is the "leader" in
  "pullback in a leader".
- **Bullish fires on uptrend coins don't work** (−1.61 vs hold). A plausible reading,
  not tested: a sell-off deep enough to fire bullish on an uptrend coin means the
  trend is breaking.

**Equities (production log, Jun–Oct 2026, alpha vs the equity class mean):**

| | trades | raw | hold same stock | fire − hold | alpha |
|---|---|---|---|---|---|
| S&P 500 / Nasdaq-100 names, v3 bullish | 44 | +4.81 [+0.20, +9.59] | +0.54 | +4.28 [−0.16, +8.78] | +3.41 (73% win) |
| S&P 500 / Nasdaq-100 names, pullback long | 133 | +0.24 | +0.52 | −0.28 | +1.06 |
| other equities, v3 bullish | 100 | −1.41 | −0.76 | −0.64 | −1.98 |

The index-name v3 result matches the v2 plan's equity split in
[trading_strategy.md](trading_strategy.md#appendix-the-v2-plan-and-its-audit) (tech wins, Korea/China/
IPOs lose), but it is 44 trades in one window. There is no equity history to check it
on (candles start 2025-11). The crypto pullback works on equities only weakly.

### Registered this pass

- Crypto pullback above SMA200 vs the rest of the crypto pullback, as a long.
- v3 bullish on S&P 500 / Nasdaq-100 names: alpha > 0.

---

## 2026-10-18 — periodic pass

Snapshot synced 2026-10-18 00:20 (latest run 2026-10-17 12:00 UTC): 7,979 deduped
signals, 7,150 with a 7d alpha in 2,183 episodes. The report ran with `--scan`.

**Watchlist: nothing to score yet.** All checks show 0 episodes since their
registration (2026-10-14 → 16). The first 7d outcomes close around 2026-10-21/22, so
there are no verdicts this pass.

**What moved.** These windows have all been seen before, so they are for orientation only:
- v3 bullish: alpha +0.81 [−0.25, +1.90] (382 ep). Since 2026-09-19: +0.41 [−2.38,
  +3.04] (48 ep), down from +0.91 at 45 ep on 2026-10-14.
- Record-peak warning since 2026-09-19: −4.84 [−6.66, −3.38] (24 ep). Still strongly
  negative live, while history 2023–26 is +0.01. The Telegram warning was dropped on
  the history result (`e938cc3`). Its pending check decides on fresh data.
- Bearish pullback (`peak_pct` ≥ 50): short-side −1.37 [−2.31, −0.36] (740 ep), i.e.
  long-side +1.37, matching history. Not new evidence, because it was registered on this data.
- Feature scan: nothing new replicates. `vol_ratio_1_20` passes FDR in-sample and flips
  after 2026-09-19. No bearish feature reaches q ≤ 0.25.

### The signal line on bearish fires (the Telegram `sig`)

User observation: bearish fires with a high signal line keep trending up. Tested on
the historical rebuild as a long, 7d alpha, episode-level, week-block intervals. The
cut (`sig_atr` ≥ 0.5, where the effect starts) was fixed on 2023–25 *before* the
other windows were printed.

| | 2023–25 (cut set here) | 2026H1 | live period, rebuilt |
|---|---|---|---|
| bearish, sig ≥ 0.5, long alpha | +1.45 [+0.41, +2.51], 1,041 ep | **+2.25 [+0.86, +4.47]**, 164 ep | +1.74 [−0.03, +4.76], 295 ep |
| bearish, sig < 0.5 | +0.23 | +0.48 | +0.84 |
| non-firing coins, positive hist, sig ≥ 0.5 | +0.79 | +1.53 | −0.31 |
| fire − non-firing | +0.66 [−0.78, +2.04] | +0.72 [−2.72, +3.79] | +2.06 [−0.22, +5.16] |
| within peak ≥ 50: sig ≥ 0.5 − sig < 0.5 | +0.80 [−0.55, +2.33] | +2.59 [−0.44, +5.50] | +0.26 [−2.71, +4.91] |
| peak < 50 but sig ≥ 0.5 | +0.06 | +0.06 | −2.10 |

- **The direction holds out of sample.** High-sig bearish fires make good longs.
- **About half of it is generic momentum.** Coins with a high signal line outperform
  whether or not the detector fires, so the fire adds roughly +0.7, which is not
  significant in any window on its own.
- **`sig` mostly repeats `peak_pct`** (correlation +0.48). Without a big excursion
  (peak < 50) a high `sig` is worth nothing. On top of one it adds +0.3 to +2.6, every
  interval spanning zero. Both together is the strongest cell: +1.70 / +3.51 / +2.51.
- *Mechanism:* the signal line is a slow average of MACD, so a high value means a
  sustained uptrend. Strong trends persist (momentum), and the fire marks momentum
  cooling. It is the same pullback-in-a-leader effect as the 2026-10-16 entry, read
  off a different gauge.
- *Caveat:* 2026H1 had already been seen for the `peak_pct` pullback, and the two
  gauges overlap, so that holdout is only partly clean.

### v2 on odd days (no market-wide cluster)

Crypto history, by the share of the universe firing v2 that day: odd days (< 5%)
alpha +0.67 [−0.35, +1.78] (353 ep), positive every year (+0.97 / +1.14 / +0.78 /
+0.27), against −0.11 on cluster days (≥ 10%). Live, all classes: odd days (≤ 5 fires)
−0.77 [−2.53, +0.56] (87 ep). v2's raw return sits on cluster days (live +5.45, all
of it market). Cluster days can't produce alpha: when v2 fires on 20–30% of the
universe, its picks *are* the benchmark. Big clusters (≥ 20%) bounced, raw +2.98
[+0.68, +5.10], and mid-sized ones (10–20%) kept falling (−2.53).

### `peak_pct` bands at 7 / 14 / 30 days

Exploratory, not pre-registered. Historical rebuild 2023-03-02 → 2026-06-08, alpha
(bearish = short side), episode-level. Intervals use week blocks at 7/14d and month blocks
at 30d, because 30-day windows overlap across about four weeks. Years = years with alpha > 0.

| `peak_pct` | bullish 7d | bullish 14d | bullish 30d | bearish 7d | bearish 14d | bearish 30d |
|---|---|---|---|---|---|---|
| 0–25 | **+1.51** [+0.77, +2.29] 4/4 | **+1.92** [+0.80, +3.00] 3/4 | **+2.04** [+0.66, +3.82] 4/4 | +0.55 [−0.11, +1.20] 4/4 | **+1.04** [+0.29, +1.75] 4/4 | **+1.54** [+0.33, +2.60] 4/4 |
| 25–50 | +0.11 | −0.12 | −0.08 | −0.62 | −0.54 | −0.02 |
| 50–75 | −0.24 | −0.70 | −1.57 [−3.37, +0.04] 0/4 | −0.57 | −0.54 | +0.34 |
| 75–<100 | −0.07 | −0.85 | −1.41 | **−1.96** [−3.07, −0.80] | **−1.99** [−3.84, −0.36] | −2.09 |
| 100 | +0.01 | +0.27 | +1.11 | **−1.94** [−3.92, −0.20] | −1.16 | −0.87 |

Episodes: bullish 913 / 1,250 / 1,219 / 694 / 729; bearish 1,347 / 1,826 / 1,289 / 661 / 520.

- **The low band's edge grows with the hold.** Bullish 0–25 goes +1.51 → +1.92 → +2.04,
  and the bearish short goes +0.55 (spans 0) → +1.04 → +1.54, positive every year at
  each horizon. The bearish leg of v3 is undecided at 7d only because 7d is too short.
- **The bullish bands above 50 drift negative with time** (50–75 is −1.57 at 30d,
  negative in all four years). The v3 cut at 50 keeps them out. The 25–50 band is about 0
  at every horizon, which supports the existing check that tightens v3's cut to 25.
- **Bearish 75–100 is the long-side pullback** from the 2026-10-16 entry, seen again at
  every horizon.
- *Mechanism (hypothesis):* `peak_pct` ranks the excursion against the asset's own
  history, so it works as a relative-strength gauge. A shallow dip (bullish, low band)
  is a pause in an asset that is not weak, and a shallow rally (bearish, low band) is
  a bounce in one that is not strong. Relative strength persists for weeks
  (cross-sectional momentum), so the gap accumulates instead of decaying the way a
  short-term bounce would.
- *Caveats:* the 14d windows overlap, so week-block intervals are somewhat optimistic.
  Per-trade noise also grows with the hold. Live outcomes stop at 14d, so the 30d
  numbers can't be checked live.

### Registered this pass

- Bearish high sig (`sig_atr` ≥ 0.5) as a long: short-side alpha < 0.
- Bearish pullback + high sig vs the rest of the pullback: < 0 (does `sig` add?).
- v2 on an odd day (≤ 5 v2 fires): alpha > 0.
- Bullish `peak_pct` ≤ 25 at **14d**: alpha > 0. Watchlist checks can now set their
  own holding period (`Check.horizon`, `81223f0`).
- v3 bearish (`peak_pct` ≤ 25) at **14d**: short-side alpha > 0.

---

## 2026-10-16 — Bollinger bands, and bearish fires as longs

Discovery on the historical rebuild (2023 → 2026-10-08, closed candle, crypto). All
three periods (2023–25, 2026H1, the rebuilt live period) were looked at together, so
**nothing here is out of sample**. 7d alpha, episode-level, week-block 95% intervals.
Scripts were scratch, not committed.

**Bollinger bands add nothing the signals don't already have.**
- *At entry.* Bullish fires essentially never sit below the lower band (%B at the
  prior close: median 0.32, min 0.01). A close below the band means the histogram is
  still growing, so the detector cannot fire. "Lower band + MACD flattening" doesn't
  happen on the same bar. %B, squeeze (width vs own 120d) and width change have no
  consistent IC. Band width as a % of price predicts alpha (2023–25 IC −0.10), but it
  is the known low-volatility factor: random assets show it too (−0.07), and it fades
  after 2025. "Closed below the band in the last 5 days" was +0.06 in 2023–25 and
  reversed later.
- *As exits* (v3 and all bullish first fires against a 7d hold, paired): a
  middle-band exit lifts the win rate from ~45% to ~65% and the alpha by 0.0. It banks
  small wins and holds losers to the 14d cap, and random entries get the same win-rate
  jump. The upper-band exit and a resting limit at the middle band add nothing. The
  lower-band −2% stop changes alpha by +0.24 / +0.29 / −0.15 across the periods (v3),
  about what it does to random entries (+0.13 / +0.06 / −0.08). It helps in falling
  markets and costs a little in rallies: tail control, as §3C already concluded.

**Found: bearish fires after a strong uptrend are good longs.** A bearish fire with
`peak_pct` ≥ 50 (the positive excursion is in the top half of the asset's own),
held long:

| | long 7d alpha | episodes | non-firing assets, same MACD state | fire − non-fire |
|---|---|---|---|---|
| 2023–25 | +1.16 [+0.54, +1.74] | 2,442 | +0.25 | +0.90 [+0.16, +1.67] |
| 2026H1 | +1.43 [+0.18, +2.61] | 490 | −0.34 | +1.77 [+0.18, +3.34] |
| live period, rebuilt | +2.34 [+1.26, +3.67] | 552 | −0.48 | +2.82 [+1.52, +4.23] |
| production log, crypto | +1.78 [+0.80, +3.09] | 495 | — | — |
| v3 bullish, same 2023–26 | +0.53 [+0.02, +1.06] | 1,591 | | |

Positive every year (+0.87 / +1.41 / +0.98 / +1.94). It survives dropping the top 10
symbols (+0.85) and 1% winsorising (+1.17). It is right-skewed: only 46% of
episodes beat their universe. Low-peak bearish fires are the opposite (long alpha
≈ −0.7), which is H8's direction.

*Mechanism.* Peak percentile measures how strong a trend is against the asset's own
history. Strong trends persist across assets: momentum. Among non-firing assets in a
strong uptrend, the edge rises as momentum cools. Histogram still rising: −0.04%.
Falling but under the detector's thresholds: +0.27%. Fired: +0.80% (row-level). So the
detector's job here is spotting a *pullback in a leader*, as opposed to chasing one
still extending. That is something the detector knows, not a generic factor. It is the
same effect as H3 and H9 seen from the long side: bearish setups that don't fall are
showing strength.

*For trading:* alpha needs hedging to be kept. Over these trades' 2025 windows the alt
universe fell ~4% and BTC ~1%, so both a long-only and a BTC-hedged version lost money
(−3.2%, −2.1%) despite +0.98% alpha. v3 behaves the same (2025: raw −2.7%, BTC-hedged
−2.4%, alpha +0.44%). Only a hedge against the alt basket itself keeps the alpha.

### Registered this pass

- Bearish pullback (`peak_pct` ≥ 50) as a long: short-side alpha < 0.

---

## 2026-10-16 — historical rebuild

The closed-candle detector rebuilt over 2023 → 2026-06-08 crypto history (2022 had no
coin above the volume floor), against hypotheses frozen beforehand in
[archive/historical_rebuild.md](archive/historical_rebuild.md), which has the full results.
Calibration on the live period passed. 10,372 episodes, about 4× the live dataset.

- **Confirmed in every year with data:** v3 bullish alpha +0.58% [+0.04, +1.15];
  `peak_pct` IC −0.06; bearish repeat fires worse than first fires, −1.01%.
- **Not reproduced:** the record-trough penalty (+0.01% across history, against −3% to
  −4% live). It was this cycle's effect, not a general one.
- **No timing hypothesis confirmed:** v2 timing, and the BTC-downtrend filter (21 regime
  stretches, inconsistent by year).
- Watchlist roles updated per the frozen mapping. v3 bullish and bearish repeat fires
  are now **monitors** (act at ≥ 30 live episodes unless contradicted); the rest stay
  discovery tests.

Also measured (2026-10-15, not pre-registered): forming candle vs closed candle on live
data. The forming candle enters a median 20h earlier and captures +0.92% (bullish) /
+0.65% (bearish) before the close-based detector would fire. Keep it.

---

## 2026-10-15 — dataset pass

Snapshot synced 2026-10-15 14:00 (latest run 00:00). 7d outcomes for fires through
2026-10-08. Alpha against the same-run, same-class mean with candle exits; repeat
fires collapsed to episodes (re-fire within a day); week-block 95% intervals.

### What the dataset is

| | |
|---|---|
| post-fix runs | 765, every 4h from 2026-06-09 to 2026-10-15, no gaps, 1 errored |
| universe | median 155 symbols per run (108–198): 147 crypto, 79 equity, 8 commodity, 4 fx, 2 index ever seen |
| alerts | 30,619 raw → 7,877 after per-day dedup (26%) → **2,411 episodes** (31% of deduped rows) |
| episodes | median 3 fires, p90 6, max 17; 24% fire only once |
| firing rate | **39% of the day's universe fires at least once** (p10 23%, p90 56%) |
| breadth of firing | 226 symbols fired; the top 10 hold only 8% of rows |
| direction mix | 61% bullish in June, 35–37% Jul–Aug, 42% Sep, 51% Oct |

**The detector is not a rare event.** Four in ten assets fire on a typical day, and
the 30,619 alerts are about 2,400 distinct setups. That breadth is consistent with
everything measured so far: a signal that fires on 40% of the universe can hardly
pick out a special 40%, and across the book alpha is ≈ 0.

**One market cycle.** Mean 7d forward move of a random crypto asset, by fire month:
Jun +2.3%, Jul −1.3%, Aug +7.7%, Sep +5.7%, Oct −6.4%. BTC month-end: May 73.7k →
Jun 58.6k → Jul 62.9k → Aug 78.6k → Sep 83.6k → Oct (so far) 81.3k. A June crash, a
two-month rally, a falling October. Any result that depends on market direction has
been tested on roughly one turn.

**Completeness.** r_1d 99%, r_7d 96%, r_14d 90%, RSI and ATR 100%, `peak_pct` 99%,
funding carry 97%, 200-day distance 78% (newer listings lack 200 bars).
**Commodity, fx and index never get a benchmark.** Each class has fewer than the 10
same-run symbols the benchmark needs, so 475 scored rows (6%) carry no alpha. If those
classes matter, pool them into one "macro" benchmark class (14 symbols).

### Detector quirk: the 00:00 run sees a flat candle

At 00:00 UTC the scanner's "forming" daily candle is seconds old, sitting at the last
close. With `use_forming_candle`, the detector feeds MACD that near-flat bar, and a
flat bar mechanically shrinks the histogram (`hist_new ≈ (1 − 2/(9+1)) · hist_prev`
plus a small MACD term), which is exactly what the detector looks for. Re-running the
real detector on closed bars only:

| first fire of an episode | closed-bar detector also fires |
|---|---|
| bullish at 00:00 | 34.8% |
| bearish at 00:00 | 36.5% |
| bullish intraday | 12.7% (expected — intraday fires are meant to read the live bar) |
| bearish intraday | 10.1% |

So about **65% of 00:00 first fires exist only because of the flat bar.** They are
not worse than the 00:00 fires closed bars agree with (bullish alpha −1.28% vs
−2.31%), so this is recorded as a quirk, not a defect. A cleaner design would skip
the forming bar at the 00:00 run. Changing the detector is out of scope for a research
pass.

### Episode structure

- **Bullish first fires at 00:00 underperform**: alpha −1.64% [−2.76, −0.73] against
  +0.29% [−0.47, +1.10] for intraday first fires. **No mechanism found.** The
  flat-bar quirk does not explain it (above). Registered.
- **Bearish repeat fires look worse than first fires** in-sample: within the same
  episode, later fires are worse shorts by −0.85% [−1.20, −0.48]. Plausible
  mechanism: a bearish setup that keeps re-firing without the price falling is showing
  strength. Registered. (The first out-of-sample look, contaminated because the
  hypothesis was formed on all data, pointed the other way: +0.85, CI spanning zero.)
- Bullish raw return falls with position in the episode (+3.26% first fire → +0.54%
  fourth+). But the paired within-episode difference is not significant (+0.63%
  [−0.44, +1.86]). Long episodes happen in falling markets, so this is composition,
  not a rule.
- **Alpha is flat across horizons** for first fires in both directions: no horizon
  at which a selection edge builds.

### The feature scan, at episode level (first time)

Run with `--scan`: one number per episode, feature as at the first alert, BH-corrected
in-sample, checked after 2026-09-19.

- **Bullish:** `peak_pct` / `peak_ratio` remain the strongest (IC −0.14, q ≤ 0.004).
  Their out-of-sample confirmation shrinks at episode level: −0.05 [−0.11, +0.03],
  against −0.23 measured row-level earlier. Same sign, no longer significant.
- **`oi_to_vol` and `atr_ratio_14_50` flip sign out of sample** at episode level.
  [archive/confidence_v3_research.md](archive/confidence_v3_research.md) §3 called them replicated
  on row-level intervals. They do not survive.
- `dd_from_high_30` holds (IS +0.09, OOS +0.25 [+0.01, +0.49]), but it is a generic
  factor (it predicts alpha for random assets too).
- **Bearish: no feature reaches q ≤ 0.25.** Among ~60 indicators, nothing picks
  better shorts.

### Tooling fixes this pass

1. **Watchlist checks are scored only on fires from their registration date.** Before,
   every check was scored on the window after 2026-09-19. That window had already been
   looked at when most hypotheses were formed, so "confirmed" could be circular. This
   pass's 00:00 check had read **confirmed** at −5.96% on exactly that seen data. With
   the fix, every check is honestly *pending*: no data has yet arrived after any
   registration date. First scorable 7d outcomes land around 2026-10-22.
2. **Verdict bug fixed.** "Contradicted" checked one bound only, so checks expecting
   a negative value could read *contradicted* with an interval spanning zero. It now
   needs the whole interval on the wrong side.

### Registered this pass

- Bearish repeat fires vs first fires (alpha).
- Bullish 00:00 first fires vs intraday first fires (alpha).

Earlier today, from the strategy audit: v2's timing, the BTC-downtrend filter, and
ATR expansion as selection. Nine checks in all, all pending.
