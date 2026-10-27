# Exits for B3: what was tested, and what to change

Research doc, 2026-10-27. B3 ([trading_strategy.md](trading_strategy.md)) holds every leg
for 14 days and exits on time only. This doc tests whether a different exit makes more
money or loses less: per-leg holds, stops, take-profits, trailing stops, MACD events,
the MACD state after entry, and the proposed short tail stop. Each is tested per trade
and then as a portfolio.

**Data.** The closed-candle detector rerun over the history CSVs (to 2026-10-15),
extended with the live candle cache (to 2026-10-24). Fires 2023-03-02 → 2026-10-08,
first fire per episode, B3's four legs. The rerun reproduces
`history_rebuild.pkl`: 26,565 of its 26,569 fires, identical `peak_pct`, and identical
7d and 14d alpha except 11 fires on 2026-10-02 (the rebuild read a forming bar).
**The legs and the 14-day hold were found on this same history**, so nothing here is
out of sample. To limit the damage, every rule is reported on 2023–24 and 2025–26
separately. A rule counts only if it helps in both.

## Headline

1. **Hold the shorts (S1, S2) 21 days and keep the longs at 14.** Their alpha keeps
   accruing in week 3, positive every year in both legs, while the longs' alpha has
   stopped by day 14. As a portfolio this adds **+0.27 [−0.05, +0.58] Sharpe** (paired),
   +0.18 in 2023–24 and +0.37 in 2025–26. CAGR goes from +37% to +45%, and max
   drawdown from −18% to −20%. Short holds of 21–30 days form a plateau, and the gain
   holds at every cost level tested. It is the one tangible result here, and it is
   in-sample.
2. **No exit rule improves the longs.** Cutting L2 at 7 days (the §8.2 candidate) is
   neutral: Sharpe 1.40 against 1.42, with 14% more turnover.
3. **Exits on the trade's path are noise or cost alpha.** That covers stops,
   take-profits and trailing stops on alpha, and exits on a zero-cross or an
   opposite fire. None helps in both periods. The good legs lean towards *reversal*
   after a bad start, so stops sell just before the recovery, which is C6a's result
   again.
4. **One exit with a mechanism is still only a hypothesis.** Exit when the coin moves
   into a MACD state that keeps going against the trade: a long whose coin is now in a
   deep dip, or a short whose coin is now in a strong rally. In the portfolio it adds
   +0.29 Sharpe, but +0.63 of that is 2023–24 and −0.03 is 2025–26.
5. **The proposed short tail stop costs money and doesn't cut drawdown.** At +50% it
   costs 0.11 [−0.33, +0.11] Sharpe. Squeezed shorts partly revert: 63% of the shorts
   that touch +50% end the 14 days better than the stop would have. Keep it only as
   insurance against what daily bars can't show, and set it wide (+100% costs 0.06).

## Backtest

Built as [trading_strategy.md](trading_strategy.md) §1.2: one position per coin, first
fires only, both sides sized to the thinner one (side gross = min(100%, 10% × names on
the thinner side)), equal weight within a side. Costs are 0.10% a side on all turnover,
including the daily re-equalisation of drifted weights. Funding is a flat 9% APR paid
on longs and 6.5% APR received on shorts. Returns run 2023-03-02 → 2026-10-15.

**Calibration.** This build scores Sharpe **1.42 [0.50, 2.51]**, CAGR +37%, max
drawdown −18%. The earlier scratch builds of the same book scored 1.22–1.29. The fires
and per-trade alpha match exactly, so the gap comes from construction rules those
scripts didn't record (§8.1 already calls for this). Every comparison below is paired
against this one baseline, so the gap doesn't move the differences. It does show why
§8.1's committed backtester comes first.

## 1. Where each leg's alpha accrues

Alpha in the trade's direction, gained within each window of days after entry. The
first row of each leg is first fires, with years positive (out of 4) in brackets. The
second row is same-state non-fires: eligible coins in the leg's MACD state with no
same-side fire in the last 5 days (the 2026-10-25 counterfactual).

| leg | | days 0–3 | 3–7 | 7–14 | 14–21 | 21–30 |
|---|---|---|---|---|---|---|
| L1 long | fires (1,013 ep) | **+0.80** (4) | +0.35 (2) | +0.43 (3) | +0.01 (3) | −0.16 (3) |
| | same state | +0.24 | +0.26 | +0.49 | +0.64 | +1.02 |
| L2 long | fires (3,461 ep) | **+0.42** (4) | **+0.48** (4) | −0.01 (1) | −0.00 (2) | **−0.59** (1) |
| | same state | −0.14 | +0.06 | +0.60 | +0.49 | −0.40 |
| S1 short | fires (1,560 ep) | +0.32 (3) | **+0.58** (3) | +0.31 (4) | +0.50 (4) | −0.07 (3) |
| | same state | −0.49 | +0.04 | +0.38 | +0.33 | −0.36 |
| S2 short | fires (2,184 ep) | **+0.28** (3) | −0.00 (2) | +0.40 (4) | **+0.71** (4) | +0.06 (2) |
| | same state | +0.19 | +0.10 | +0.21 | +0.30 | +0.45 |

Bold: week-block 95% interval excludes zero.

- **The legs run on different clocks.** The longs' fire edge has all arrived by day 14.
  L2's has arrived by day 7. The shorts keep earning through day 21. Days 14–21 are
  positive in every year for both short legs (S1 +0.64 / +0.96 / +0.38 / +0.34,
  S2 +1.64 / +0.97 / +0.44 / +0.61 for 2023 / 24 / 25 / 26). Nothing is gained after
  day 21.
- **The longs pay early and then fall behind their own state.** L1 fires gain +0.80 in
  three days, against +0.24 for non-firing coins in the same state. In days 14–21 they
  gain +0.01 against the state's +0.64. L2 shows the same pattern from day 7.
- *Mechanism (hypothesis):* a long fire marks the *end* of a move: a dip that is
  already over (L1) or a leader cooling off (L2). The reversion is paid within days
  and then it is spent. A short fire marks a failed bounce in a weak coin. That
  weakness resolves slowly. Non-firing coins in the S2 state (deep dips) drift down
  steadily for the whole 30 days, which is the 2026-10-25 finding that deep dips
  persist, and the fires drift faster than the state. *What drives* the slow selling
  is not explained. Liquidity doesn't account for it on its own: S1's week-3 alpha is
  the same in the thinnest and most liquid thirds of coins (+0.67 / +0.63). S2's is
  larger in thinner coins (+0.92 vs +0.37), but the intervals overlap.

## 2. Does the trade's path or state predict the rest?

**Path: no.** Split each leg's trades into thirds by alpha at bar 3 or bar 7. Within a
leg, the forward alpha to day 14 of the worst and best thirds overlaps at every
checkpoint. The good longs lean towards reversal: at bar 3, L1's worst third earns
+1.24 afterwards and its best third +0.28. Non-firing coins in the same state lean the
other way. This is C6a's finding from the other side: a trade that starts badly hasn't
failed, so stops and trailing stops sell it before it recovers.

**State: partly.** Forward alpha to day 14 by the coin's MACD state at bars 3, 5, 7 and
10 (fires; trades counted once per state):

| leg | coin now in | forward alpha to day 14 | trades |
|---|---|---|---|
| L2 long | mild dip (hist < 0, `peak_pct ≤ 25`) | +0.69 [+0.17, +1.24] | 1,352 |
| | mid dip (25–75) | +0.21 | 1,617 |
| | **deep dip (75 to < 100)** | **−1.57 [−2.48, −0.69]** | 609 |
| | record dip (100) | −0.85 | 340 |
| | any rally below the record | +0.6 to +0.9 | |
| S2 short | any dip, or a mild or mid rally | +0.3 to +0.7 | |
| | **strong rally (hist > 0, 75 to < 100)** | −1.37 [−3.89, +1.17] | 178 |
| | record rally | −3.82 [−13.4, +3.7] | 72 |

A long whose coin has fallen into a deep dip, or a short whose coin has rallied hard,
keeps losing. That matches the universe-wide states of 2026-10-25 (deep dip −1.38 and
strong rally +1.86 at 14d). L1 and S1 coins rarely reach those states within 14 days
(4–5% of trades).

## 3. Exit rules, per trade

Exit alpha minus 14-day-hold alpha, first fires, 2023–24 / 2025–26. Bold: the 95%
interval excludes zero. A rule's exit is decided on a closed bar and taken at that
close, so there is no look-ahead. ATR is the coin's daily ATR at entry (median about 6%
of price).

| rule | L1 | L2 | S1 | S2 |
|---|---|---|---|---|
| hold 7 days | +0.67 / −0.78 | −0.04 / +0.05 | −0.63 / −0.21 | **−0.78** / −0.22 |
| hold 10 days | +0.72 / −0.25 | −0.32 / +0.38 | −0.34 / −0.10 | −0.26 / −0.39 |
| **hold 21 days** | +1.11 / −0.33 | −0.36 / +0.24 | +0.91 / +0.36 | **+1.15** / +0.50 |
| adverse state (long: deep dip; short: strong rally) | −0.19 / −0.05 | **+0.65** / +0.13 | **−0.55** / −0.08 | +0.34 / +0.19 |
| take profit at alpha ≥ 2 ATR | **+1.41** / −0.33 | −0.51 / **+0.57** | +0.01 / −0.10 | **−0.25** / +0.03 |
| take profit at alpha ≥ 3 ATR | **+0.89** / −0.25 | −0.24 / **+0.60** | −0.02 / −0.01 | −0.12 / −0.00 |
| stop at alpha ≤ −2 ATR | −0.36 / **−0.19** | +0.40 / −0.02 | **−0.79** / −0.13 | +0.13 / +0.11 |
| stop at alpha ≤ −3 ATR | −0.34 / **−0.11** | +0.21 / **−0.06** | **−0.64** / −0.11 | +0.12 / +0.20 |
| trailing: 2 ATR below the best alpha | −0.07 / −0.21 | +0.16 / +0.09 | **−0.79** / −0.16 | +0.13 / +0.12 |
| histogram crosses zero (the move completes) | +0.30 / **−1.41** | — | −0.68 / **−0.74** | — |
| coin fires the opposite direction, any band | +0.39 / −0.38 | +0.15 / −0.03 | −0.50 / **−0.70** | −0.56 / **−0.77** |

- **Only the 21-day hold for the shorts is positive in both periods on both legs.** On
  non-firing coins in the same states it is +0.80 / +0.18 (S1) and +0.19 / +0.35 (S2),
  so part of it is the state persisting.
- **Take-profits flip with the market.** On L1 and L2 they win in one period and lose
  in the other. The same-state counterfactual flips with them (L2 2 ATR: −1.64 / +0.40).
  This is reversal in the 2025 alt crash, not a property of the signal.
- **Stops and trailing stops** cost alpha on S1 and L1, and are noise elsewhere.
- **Exiting when the move completes** (histogram crosses zero), or on the next opposite
  fire, gives up the edge before it is paid. That is the same reason the failed-cross
  exit fails (C6a).
- **The adverse-state exit** helps the two legs where it triggers often (L2 29% of
  trades, S2 13%) and costs a little on the two where it rarely does. On non-firing L2
  coins it is +0.23 / −0.22, so it isn't a clean state effect either.

## 4. As portfolios

Sharpe difference against the baseline, using paired 30-day block bootstraps (the same
blocks for both books):

| book | Sharpe | Δ vs baseline [95%] | Δ 2023–24 | Δ 2025–26 | CAGR | max DD |
|---|---|---|---|---|---|---|
| **baseline: every leg 14 days** | 1.42 | — | — | — | +36.9% | −18% |
| every leg 7 days | 1.55 | | +0.21 | −0.13 | +44.7% | −23% |
| every leg 21 days | 1.60 | +0.17 [−0.36, +0.65] | +0.28 | +0.05 | +38.7% | −21% |
| L2 7 days, rest 14 | 1.40 | | +0.20 | −0.20 | +38.3% | −17% |
| **shorts 21 days, longs 14** | **1.70** | **+0.27 [−0.05, +0.58]** | **+0.18** | **+0.37** | +44.6% | −20% |
| L2 7, L1 14, shorts 21 | 1.63 | +0.21 [−0.42, +0.77] | +0.31 | +0.15 | +45.4% | −18% |
| + adverse-state exit (L2, S2) | 1.71 | +0.29 [−0.17, +0.71] | +0.63 | −0.03 | +48.2% | −20% |
| + adverse-state exit (all legs) | 1.63 | +0.21 [−0.26, +0.65] | +0.51 | −0.09 | +45.5% | −21% |
| shorts 21 + adverse-state exit (all legs) | 1.73 | +0.31 [−0.24, +0.79] | +0.45 | +0.20 | +48.2% | −24% |
| + short tail stop at +30% | 1.27 | | +0.00 | −0.31 | +30.8% | −20% |
| + short tail stop at +50% | 1.32 | −0.11 [−0.33, +0.11] | +0.12 | −0.34 | +33.1% | −20% |
| + short tail stop at +100% | 1.36 | | +0.06 | −0.18 | +34.9% | −18% |

Blank Δ cells were not bootstrapped. With 3.6 years, one Sharpe has a standard error of
about ±0.5. Hold lengths shared by every leg (7, 14, 21) are indistinguishable. Only
the short extension improves on the baseline in both periods with a paired interval
that nearly clears zero.

## 5. Holding the shorts 21 days

| check | baseline | shorts 21 | Δ [95% paired] |
|---|---|---|---|
| short hold 10 / 14 / 17 / 21 / 25 / 30 days | | 1.25 / 1.42 / 1.53 / 1.70 / 1.69 / 1.65 | −0.17 / 0 / +0.11 / +0.27 / +0.27 / +0.23 |
| cost 0.05% a side | 1.70 | 1.96 | +0.26 [−0.06, +0.57] |
| cost 0.20% a side | 0.87 | 1.17 | +0.30 [−0.02, +0.60] |
| all fires (re-fires restart the clock) | 1.39 | 1.61 | +0.21 [−0.06, +0.47] |
| S1 alone to 21 days | 1.42 | 1.62 | +0.20 [+0.01, +0.37] |
| S2 alone to 21 days | 1.42 | 1.54 | +0.12 [−0.12, +0.39] |
| half-years 2023H1 → 2026H2 (return, pts) | | | +2.8 / +7.7 / −3.1 / +0.3 / +17.6 / −5.9 / −1.5 / +6.9 |

- **Not a knife edge.** Sharpe rises from 10 to 21 days and stays flat to 30. Chosen on
  2023–24 alone, the grid would have picked 25 days (+0.35). In 2025–26, 25 days adds
  +0.20 and 21 days +0.37. 21 is a round three weeks inside the plateau.
- **Not more exposure.** Average gross goes from 0.83 to 0.85, and book volatility
  falls slightly (24.1% → 23.4%). Longer holds widen the short side (27 → 32 names on
  average). Short returns are right-skewed, so a broader short side is also harder to
  squeeze (profit_strategies.md §3, the random-20 basket).
- **Not a bear-market effect.** Week-3 short alpha was largest in 2023 and 2024, the
  years alts rallied.
- **What it doesn't fix.** The portfolio gain is uneven: 5 of 8 half-years, with +17.6
  points from 2025H1. Max drawdown is slightly deeper (−20% vs −18%).

## 6. The short tail stop

Of 3,744 short first fires, 185 (4.9%) trade 50% above entry within 14 days. Held to
day 14 they end at −48% on average (median −44%), and 63% end better than −50%. A stop
at +50% therefore saves nothing on average. It sells near the top of squeezes that
partly revert, and gaps through the stop fill worse than the stop. Non-firing coins in
the same states behave the same way (5.0%, −45%). So this is how squeezes in alts
behave, not anything specific to the signals.

The stop is still insurance against what a daily-close backtest can't show, such as a
5x move within a day or a forced liquidation. If it stays, set it wide: +100% costs 0.06
Sharpe, against 0.11 at +50% and 0.15 at +30%.

## 7. What to change

- **Make "shorts 21 days" the per-leg hold variant in §8.2 #5**, replacing "L2 at 7d",
  which is neutral as a portfolio. Adopt it only after a live check agrees, as §7
  requires for horizons found on this history.
- **Registered watchlist checks** (2026-10-27, `research/rules.py`). Each is scored
  only on fires from that date, crypto first fires:
  1. `crypto bearish peak_pct <= 25, first fires` (S1): `alpha_from_14d_21d` > 0. That
     is entry at the 14d exit's close and exit at day 21, against the same-run class
     mean over the same bars.
  2. `crypto bullish 50 < peak_pct < 100, first fires` (S2): the same measure, < 0
     long-side.
  3. `crypto pullback, first fires, deep dip by day 13` (L2): `alpha_from_dip_14d`,
     from the close of the first deep-dip day to the 14d exit, > 0 short-side, i.e. the
     long loses.

  In the pipeline's day convention (the 14d exit is the close of fire day + 14) the
  history reads S1 +0.40 [−0.13, +0.91], S2 +0.38 [−0.18, +0.92] as a short, and L2
  −1.19 [−2.02, −0.42] long-side. That is a little weaker for the shorts than
  §1's days 14–21.
- **Don't add** stops, take-profits or trailing stops on alpha, zero-cross exits, or
  opposite-fire exits.
- **The short tail stop is insurance with a small cost, not a free control.** Set it at
  +100%, not +50%.

## Caveats

- **In-sample.** The legs, the 14-day baseline and now the 21-day short hold were all
  found on 2023–26. The period split protects against picking an exit that only worked
  in the 2025 crash. It doesn't make the legs themselves out of sample.
- **Flat funding.** A short held 21 days receives a flat 6.5% APR here. Real per-coin
  funding on weak coins can turn negative (shorts pay), and a week longer on the short
  side means more exposure to that.
- **Closed-candle detector, daily closes.** Same limits as profit_strategies.md §5.
  Intraday stops are modelled as fills at the stop or the open, whichever is worse.

## Reproduction

Scratch scripts, not committed, as for earlier passes. Inputs:
`state/research_cache/history/*.csv` extended with `state/research_cache/candles/`
(bars 2026-10-16 → 10-24). The panel reruns `signals._check_histogram_flattening` and
`_peak_vs_history` on every coin-day. The book follows "Backtest" above.
