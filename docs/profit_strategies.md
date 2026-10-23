# Profit strategies: what the signal research could support, backtested as portfolios

Exploratory doc, 2026-10-19. It turns the findings in
[confidence_v3_research.md](confidence_v3_research.md),
[research_log.md](research_log.md) and [historical_rebuild.md](historical_rebuild.md)
into tradeable strategies. Each one is backtested as a **portfolio**, with costs, funding,
overlapping positions and a hedge you could actually hold. It does not pick a winner.
It says which ideas have money in them, which don't, and how far to trust each one.

[trading_strategy.md](trading_strategy.md) is the earlier plan built around v2. Its
operations and risk sections (§6–7) still apply. Its account simulations (+83% at 5x)
ran on v2 over Jun–Oct 2026, and [its own audit](trading_strategy.md#0-audit-against-the-research-method-2026-10-15)
shows that return was market move, not selection. This doc re-asks "what to trade" on
3.6 years of history instead of 4 months.

**Data.** Historical rebuild: the closed-candle detector over the crypto perps, fires
2023-03-02 → 2026-10-08 (`state/research_cache/history_rebuild.pkl`, built 2026-10-16).
Daily candles run to 2026-10-15. **Almost every strategy below was assembled from
findings made on this same history**, so the numbers are in-sample unless marked
otherwise. Read them as upper bounds.

## Headline

1. **Going long on the signals lost money over 2023–26, whatever the filter.** The
   equal-weight alt universe fell 71% in 2025 and every long-only alt book went with it.
   The selection edge is worth roughly +0.5 to +1.5% a week. The alt market moved ±40%
   in a single half-year. A long book's profit is a bet on alts, not on the detector.
2. **The selection edge only pays market-neutral, and only against the same kind of
   coins.** Hedged against the equal-weight alt universe, the best signal book makes a
   net Sharpe of about 0.9. Hedged against BTC or the top 20 coins by volume, the same
   book **loses 19–27% a year**. The most executable form is **long the good fires,
   short the bad fires**, both legs from the signal stream: Sharpe **1.11 [0.12, 2.22]**
   net, with about zero correlation to BTC or the alt index.
3. **Costs decide it.** A 7-day hold turns the book over 80–100 times a year. At
   0.10% a side that costs 8–10% a year. That wipes out v3's edge: Sharpe 0.52 gross,
   **0.00 net**. Longer holds and the stronger `peak_pct` bands survive.
4. **The only rule fixed *before* this history was examined does not make money as a
   portfolio.** That rule is v3 bullish at 7d (H1, confirmed per trade). The books that
   do make money use `peak_pct ≤ 25`, the bearish pullback and a 14-day hold, and all
   three were *found* on this history. A Sharpe of about 1 is an optimistic ceiling.
5. **Best risk-adjusted combination tested:** BTC trend-following (long BTC above its
   50-day average, flat otherwise) plus the long/short signal book. Sharpe **1.51**,
   CAGR **+67%**, max drawdown −36%, positive every year. It stacks two in-sample picks.
   With the 100- or 200-day average it is 1.24–1.25.
6. **Several ideas don't work here:** market timing from signal clusters (buying
   capitulation), plain momentum, a plain "pullback in a leader" sort, and long-only
   with a trend switch.

## The menu

All net of 0.10% per side and funding. 2023-03-02 → 2026-10-15. The Sharpe interval is a
30-day block bootstrap. Year returns are 2023 / 2024 / 2025 / 2026 (2023 from March,
2026 to mid-October).

| # | strategy | aim | CAGR | Sharpe [95%] | max DD | by year | my confidence |
|---|---|---|---|---|---|---|---|
| — | BTC buy & hold *(reference)* | — | +41.0% | 0.97 [−0.10, 2.09] | −53% | +79 / +121 / −6 / −6 | — |
| — | equal-weight alt universe *(reference)* | — | −20.2% | 0.07 | −89% | +39 / +25 / −71 / −14 | — |
| A1 | long v3 bullish, 7d | gains | −22.7% | −0.26 | −84% | +14 / +23 / −73 / +3 | **high that it's bad** |
| A1 | long bearish pullback + sig ≥ 0.5, 7d | gains | +17.6% | 0.58 [−0.28, 1.51] | −46% | +43 / −3 / −3 / +34 | low |
| A2 | B2 at 2x leverage | gains | +24.7% | 0.92 | −39% | −8 / −23 / +71 / +83 | low |
| A3 | BTC + B3 overlay | gains | +73.8% | 1.35 [0.25, 2.48] | −48% | +82 / +120 / +64 / +13 | low–medium |
| B1 | v3 bullish 7d, universe-hedged | Sharpe | −1.3% | 0.00 | −27% | −5 / +7 / −22 / +20 | **high that costs kill it** |
| B2 | good fires 14d, universe-hedged | Sharpe | +12.8% | 0.92 [−0.10, 1.87] | −21% | −4 / −11 / +33 / +37 | low–medium |
| B3 | **good fires long / bad fires short, 14d** | Sharpe | +23.0% | **1.11 [0.12, 2.22]** | −22% | +1 / +1 / +73 / +20 | medium-low |
| B4 | **BTC > SMA50 + B3** | both | **+67.3%** | **1.51 [0.46, 2.65]** | −36% | +65 / +67 / +74 / +34 | low–medium |
| C1 | BTC > SMA50 trend, alone | other | +35.9% | 1.08 [0.03, 2.16] | −29% | +63 / +67 / +0 / +12 | medium |
| C2 | buy after ≥ 20% of the universe fires bullish (BTC, 7d) | timing | −2.8% | 0.06 | −48% | +25 / +14 / −13 / −27 | **high that it's bad** |

*Good fires* = bullish `peak_pct ≤ 25`, plus bearish `peak_pct ≥ 50` held long (the
pullback). *Bad fires* = bearish `peak_pct ≤ 25`, plus bullish `50 < peak_pct < 100`,
both held **short**: a bullish fire in that band is a false dawn, so it is shorted.

## How the backtest works

- **Positions.** One per symbol. It is held for N days after the most recent qualifying
  fire, so a re-fire extends it. It enters at 00:00 UTC on the fire day (the previous
  bar's close), as the closed-candle detector would. Production enters about 20h earlier on the forming candle
  ([research_log.md](research_log.md) 2026-10-16). Returns are daily close to close.
- **Weights.** Equal weight across open names, capped at 10% of equity per name. With
  fewer than 10 names the rest sits in cash. On average a book holds 7–37 names
  depending on the filter.
- **Hedges.** *Universe*: short the equal-weight mean of every eligible coin that day,
  the same benchmark the research uses for alpha. *BTC*, *top 20* (by prior-day volume),
  and the others are named where used. Hedge size follows the net long, rebalanced
  daily.
- **Costs.** 0.10% per unit traded per side: Hyperliquid's 0.045% taker fee plus an
  assumed 0.055% slippage. Funding is a flat 9% APR paid on longs and 6.5% APR received
  on shorts, from the live measurements (+0.176% and +0.124% a week,
  [confidence_v3_research.md](confidence_v3_research.md) §8). The universe hedge's own
  daily rebalancing is *not* charged, which flatters B2 slightly.
- **Statistics.** Annualised Sharpe on daily returns (×√365), with a 95% interval from a
  30-day block bootstrap. With 3.6 years, a Sharpe has a standard error of roughly
  ±0.5, so 0.9 and 1.3 are not distinguishable.
- **Why a portfolio and not per-trade alpha.** Per-trade alpha ignores four things that
  decide whether money is made: costs, uneven exposure (busy days hold 40 names, quiet
  days one), the hedge you can actually trade, and alt-market drift between the legs.
  Each of them moves the answer below.

## 1. What there is to trade

The per-trade evidence for each edge, from the research docs, 7d alpha by episode
unless noted. **Alpha is signed in the direction of the trade**: positive means the
trade beat the equal-weight universe, whether it is a long or a short. The research
docs sign bullish fires as longs and bearish fires as shorts, so a fire traded the
other way has its sign flipped here.

| edge | trade | per-trade evidence | status | mechanism (as currently understood) |
|---|---|---|---|---|
| v3 bullish (`peak_pct ≤ 50`, `red < 0.6`) | long | +0.58 [+0.04, +1.15], every year 2023–26 | **pre-registered, confirmed** | shallow dip in a coin that isn't weak mean-reverts against peers |
| bullish `peak_pct ≤ 25` | long | +1.51 (7d), +1.92 (14d), +2.04 (30d) | found on history (exploratory) | same, stronger; the edge grows with the hold |
| bearish pullback (`peak_pct ≥ 50`) | **long** | +1.16 / +1.43 / +2.34 across three periods | seen on all periods at once | a pullback in a leader; trend persistence |
| bearish high sig (`sig_atr ≥ 0.5`) | **long** | +1.45 (2023–25), +2.25 (2026H1) | about half is generic momentum | the same thing on a different gauge |
| bearish `peak_pct ≤ 25` | **short** | +0.55 (7d, spans 0), +1.04 (14d) | exploratory | a feeble rally in a weak coin |
| bullish `50 < peak_pct < 100` | **short** | 50–75: +0.70 (14d), +1.57 (30d); 75–<100: +0.85 (14d), +1.41 (30d); about 0 at 7d | exploratory | deep, often coin-specific selling keeps drifting |
| bearish repeat fires vs first fires | short (filter) | repeat fires are worse shorts by 1.01 [0.73, 1.29] | confirmed (H9) | a setup that keeps re-firing without falling is showing strength |
| record trough (`peak_pct = 100`) | — (warning on longs) | −3.8 live, **+0.01 history** | not general | — |
| any market timing (v2, BTC trend, clusters) | — | none confirmed (H5, H6) | — | — |

What these have in common: `peak_pct` ranks today's MACD excursion against *the coin's
own* last ~200 bars. Long the coins whose moves are mild by their own standards, short
the ones whose moves are unusually bad. That is a relative-strength sort in each coin's
own units. Everything that works below is built on it.

## 2. Strategies to maximise gains

### A1. Long-only signal books: they don't work in this history

| long-only, net | CAGR | Sharpe | max DD | 2025 |
|---|---|---|---|---|
| all bullish fires, 7d | −36.3% | −0.32 | −94% | −80% |
| v3 bullish, 7d | −22.7% | −0.26 | −84% | −73% |
| bullish `peak_pct ≤ 25`, 14d | +3.6% | 0.33 | −62% | −43% |
| bearish pullback, 14d | −13.8% | 0.13 | −87% | −65% |
| bearish pullback + sig ≥ 0.5, 7d | +17.6% | 0.58 | −46% | −3% |
| good fires combined, 14d | −11.2% | 0.19 | −84% | −63% |
| … only while the alt index is above its 50-day SMA | +7.7% | 0.39 | −62% | −17% |

**Why.** A long book of small and mid alts behaves like the alt index (beta ≈ 1.0 for
every book), and the alt index fell 49% in 2025H1, 42% in 2025H2 and 41% in 2026H1. A
+1% weekly edge cannot carry that. In 2023–24, when alts rallied, the same books
returned between −4% and +61% a year, tracking the market.

The bearish pullback + high sig book is the one long book that held up in 2025. It
selects strong coins in strong trends, so in a falling alt market it holds the
survivors. That is the most plausible explanation, but it is one book and one year.

**Verdict:** don't run a long-only alt book on the signals unless you separately want
alt exposure and have a view on alts. If you do, it should be sized as a market bet.

### A2. Leverage on a neutral book

Leverage scales return and drawdown together. B2 (universe-hedged good fires, 14d):

| leverage | CAGR | max DD | worst year |
|---|---|---|---|
| 1x | +12.8% | −21% | 2024 −11% |
| 2x | +24.7% | −39% | 2024 −23% |
| 3x | +35.1% | −54% | 2024 −34% |
| 4x | +43.5% | −66% | 2024 −44% |

Full Kelly from the in-sample Sharpe says 6.4x. That is not usable: the Sharpe's 95%
interval reaches below zero, and Kelly at an overestimated edge is the fastest way to
ruin. Assume the true Sharpe is about half the backtest's (0.5). Then half-Kelly is
about **1.7x**. Until live data confirms the edge, 1x is the defensible size.

Note that "1x" in a neutral book means 2x gross: $1 long plus $1 short per $1 of equity.
Hyperliquid margin has to cover both legs.

### A3. BTC plus a neutral overlay (portable alpha)

Hold BTC for the market return and run the neutral book on top. Their returns are
uncorrelated (−0.02 to −0.06), so each adds return without adding much risk:

| | CAGR | Sharpe | max DD | by year |
|---|---|---|---|---|
| BTC buy & hold | +41.0% | 0.97 | −53% | +79 / +121 / −6 / −6 |
| BTC + B2 (universe-hedged) | +59.7% | 1.22 | −44% | +73 / +95 / +25 / +29 |
| BTC + B3 (good/bad L/S) | +73.8% | 1.35 | −48% | +82 / +120 / +64 / +13 |
| BTC + B1 (v3 7d, the out-of-sample rule) | +39.0% | 0.91 | −55% | +71 / +136 / −27 / +13 |

This is the highest raw return in the doc. Most of it is BTC's 2023–24 bull market, and
nothing in this research predicts BTC. The overlay's contribution is the gap between the
rows: +19 to +33 percentage points a year in-sample, and about −2 for the one rule that
was out of sample.

### A4. Market timing from the signal stream: doesn't work

| capitulation trigger → hold 7d | triggers | long alt universe | long BTC |
|---|---|---|---|
| ≥ 10% of the universe fires bullish | 102 | −33.8% CAGR | +12.2%, Sharpe 0.49 |
| ≥ 20% | 70 | −34.9% | −2.8%, Sharpe 0.06 |
| ≥ 30% | 59 | −25.8% | +3.1%, Sharpe 0.25 |

It matches the research: no timing hypothesis survived history (H5 and H6 undecided,
BTC-downtrend inconsistent by year). Buying alt capitulations made money in 2023 and
lost heavily in 2025. **High confidence this is not an edge.**

## 3. Strategies for a high Sharpe ratio

### B1/B2. Universe-hedged signal books

Long the qualifying fires, short the equal-weight universe for the same dollar amount:

| universe-hedged, net | CAGR | vol | Sharpe [95%] | gross Sharpe | max DD |
|---|---|---|---|---|---|
| all bullish, 7d | −17.4% | 18% | −0.97 | −0.19 | −51% |
| **v3 bullish, 7d** | −1.3% | 16% | **0.00** [−0.78, 0.58] | 0.59 | −27% |
| v3 bullish, 14d | −0.4% | 17% | 0.06 | 0.53 | −26% |
| bullish `peak_pct ≤ 25`, 14d | +13.4% | 17% | 0.84 [0.04, 1.60] | 1.20 | −15% |
| bearish pullback (long), 14d | +10.2% | 18% | 0.62 [−0.39, 1.63] | 1.10 | −20% |
| bearish pullback + sig, 7d | +16.7% | 21% | 0.84 [−0.12, 1.84] | 1.14 | −23% |
| **good fires combined, 14d (B2)** | +12.8% | 14% | **0.92** [−0.10, 1.87] | 1.50 | −21% |

**Is it hidden market exposure?** No. Each hedged book's daily beta to the alt index is
between −0.04 and +0.01 in every year.

**Is it a known factor?** Mostly not. The same universe was sorted on generic factors
(weekly rebalance, top minus bottom quintile, net):

| generic factor | Sharpe | note |
|---|---|---|
| 7d momentum | −0.83 | loses every year but 2025 |
| 30d momentum | −0.06 | |
| 90d momentum | −0.28 | +66% in 2023, −56% in 2024 |
| low volatility | 0.25 | the factor the research flagged; weak here |
| liquidity (big minus small) | 0.20 | |
| 3-day reversal | 0.16 | gross 1.13, but 126% daily turnover eats it |
| "pullback in a leader" (30d rank ≥ 70%, 3d rank ≤ 30%) | −0.27 | a plain-price proxy for the bearish pullback |

Regress the signal books on all of these plus the market. They explain 5–20% of the
variance and leave a residual Sharpe of 0.57–1.28. The bearish-pullback books load
+0.12 to +0.13 on 30d momentum, which matches the log's "about half generic momentum". The
detector carries something these simple sorts don't. **The likeliest reason (a
hypothesis):** `peak_pct` scores each move against the coin's *own* history, while a
return ranking compares a volatile coin's normal swing with a quiet coin's unusual
one. An "own-history-normalised momentum" sort without the MACD would test this.

**The hedge decides whether the edge exists.** B2 with different shorts:

| short leg | CAGR | Sharpe | 2024 |
|---|---|---|---|
| equal-weight eligible universe | +12.8% | 0.92 | −11% |
| coins ranked 21+ by volume | +28.7% | 1.31 | +1% |
| 20 random eligible coins, redrawn weekly | −3.5% | −0.04 | **−36%** |
| top 20 by volume | −19.1% | −0.83 | −33% |
| BTC | −27.3% | −0.44 | −48% |

Over this period the top 20 compounded at +8.9% a year and BTC at +41%. The
equal-weight alt universe compounded at **−20%**. Alpha in the research is measured
against that equal-weight universe. Hedging with the majors adds the full
majors-minus-alts gap, about 30–60 points a year, and it swamps a 15–20% edge. That
generalises [confidence_v3_research.md](confidence_v3_research.md) §7 ("hedging against
BTC is not the same as hedging against the class") from BTC to any large-cap basket.
The random-20 row shows the opposite danger. Alt returns are right-skewed, so a short
basket of 20 random alts sometimes holds the one that goes 5x. **A short leg has to be
broad and look like the long leg.**

### B3. Long good fires / short bad fires, both from the signal stream

The natural answer to the hedge problem: the short leg is the fires the research says
are bad. Both legs are then the same kind of coin. Equal dollar size on each side,
capped at 10% a name, 14-day hold:

| short leg | CAGR | Sharpe [95%] | max DD | by year |
|---|---|---|---|---|
| bearish `peak_pct ≤ 25` | +19.7% | 0.98 [−0.02, 1.96] | −23% | +10 / +8 / +44 / +12 |
| bullish `50 < peak_pct < 100` | +14.9% | 0.73 [−0.26, 1.72] | −24% | −6 / −4 / +59 / +14 |
| **both (B3)** | **+23.0%** | **1.11 [0.12, 2.22]** | −22% | +1 / +1 / +73 / +20 |

Correlation with BTC −0.02, with the alt index −0.02, and with B2 +0.73.

**Robustness of B3** (Sharpe, net):

| variant | Sharpe |
|---|---|
| hold 7 / 14 / 21 days | 1.28 / 1.11 / 0.99 |
| first fire of each episode only | 1.22 |
| only coins with ≥ $2M / $10M / $50M prior-day volume | 0.74 / 1.69 / 1.21 |
| cost 0 / 0.05 / 0.10 / 0.20% per side | 1.65 / 1.38 / 1.11 / 0.58 |
| half-years 2023H1 → 2026H2 (return) | −2 / +4 / +10 / −8 / +17 / +48 / +14 / +5% |
| **the out-of-sample version:** v3 bullish long / bullish `peak_pct > 50` short, 7d | **0.23** [−0.73, 0.93] |

What holds up: the edge is **not confined to illiquid coins**, so it has capacity. It
survives first-fire-only and a range of holds, and it is positive in 6 of 8
half-years. What doesn't: most of the money came in 2025H2 (+48%). The variant built
only from pre-registered pieces makes almost nothing. At 0.20% a side, half the Sharpe
is gone.

**When it works.** Monthly gross returns by the alt index's move over the prior 90 days
(41 months):

| regime at month start | months | B2 mean / % positive | B3 mean / % positive |
|---|---|---|---|
| alt index down > 20% | 13 | +2.8% / 92% | +2.2% / 77% |
| in between | 19 | +2.7% / 53% | +4.7% / 79% |
| alt index up > 20% | 9 | −0.8% / 56% | +2.2% / 44% |

Both books earn more in months of high cross-sectional dispersion (B3: +4.7% vs +2.1%
a month). *Hypothesis:* in alt sell-offs and high-dispersion markets, the gaps between
coins come from coin-specific breakdowns and surviving leaders, which is exactly what
`peak_pct` ranks. In a broad alt rally, everything rises on beta and the ranking has
less to work with. Nine rally months is too few to say whether B3 breaks in a real
alt season. 2023H2, the one big alt rally in sample (+59%), gave B3 +4%.

### B4. BTC trend + B3: the highest Sharpe tested

| | CAGR | Sharpe [95%] | max DD | by year |
|---|---|---|---|---|
| BTC > SMA50 + B3 | +67.3% | 1.51 [0.46, 2.65] | −36% | +65 / +67 / +74 / +34 |
| BTC > SMA100 + B3 | +52.0% | 1.24 [0.12, 2.40] | −43% | +33 / +54 / +75 / +27 |
| BTC > SMA200 + B3 | +55.9% | 1.25 [0.21, 2.39] | −36% | +57 / +68 / +36 / +40 |
| BTC > SMA50 + B1 (out-of-sample rule) | +34.1% | 0.97 | −36% | +56 / +79 / −22 / +34 |

Two return streams with no correlation between them: BTC trend (which pays in trending
markets) and B3 (which paid most in the alt sell-off). That they diversify is the
robust part. The level (1.5) is not robust: SMA50 is the best of the four averages
tried, and B3 is assembled in-sample. Expect less.

## 4. Other strategies

**C1. BTC trend-following, no signals at all.** Long BTC when yesterday's close is above
its N-day average, flat otherwise:

| N | CAGR | Sharpe | max DD | time in market |
|---|---|---|---|---|
| 20 | +16.0% | 0.61 | −34% | 54% |
| 50 | +35.9% | 1.08 | −29% | 58% |
| 100 | +23.5% | 0.78 | −38% | 61% |
| 200 | +26.8% | 0.82 | −33% | 65% |

Every length cut BTC's drawdown (−53% buy and hold) by between a quarter and a half,
at the cost of some return. Time-series trend in crypto is widely documented outside this repo, so I
trust its sign more than anything signal-based here. I trust its size less: it is one
asset and essentially one long bull run (2023–24), and in 2025 it went sideways. It is
also simple to run: SMA50 enters or exits about 22 times a year.

**C2. Short-side books.** Short the bad fires and hedge long with the universe:
bearish `peak_pct ≤ 25`, 7d, Sharpe 0.51; bullish `peak_pct ≥ 75`, 7d, Sharpe 0.67. On
their own they are weaker than the long legs. Their real use is as B3's short side.
Shorting *all* bearish fires against the universe has Sharpe **−1.55**. As a group,
bearish fires are good *longs* relative to their peers, which fits the H9 and pullback
findings.

**C3. Funding carry (not tested; general knowledge, not this repo's data).** On
Hyperliquid, longs pay shorts about 10–11% APR at the baseline rate. The research
measured a median 9.8–10.7% APR at fire. Long spot / short perp on the same coin
collects that with little price risk. It doesn't use the signals. The risks are
different in kind: funding can flip negative, Hyperliquid spot listings are limited (so
the long leg may need another venue), and there is exchange and counterparty risk.
Funding history is cached only from 2026-05-15, so it can't be backtested here across
regimes.

**C4. Funding as a filter.** Out of sample, high funding started marking bad bullish
fires (IC about −0.19, ~90 episodes, one regime). It is a hypothesis on the watchlist,
not a rule. If it holds in a rising market, it is a natural addition to B3's short leg.

**C5. Holding period.** The per-trade research says the low-band edge grows with the
hold. As portfolios, B2's Sharpe by hold is 1.10 / 1.37 / 0.92 / 0.56 / 0.41 at
7 / 10 / 14 / 21 / 30 days. Longer holds cut costs but dilute the edge with time
outside the signal window. Somewhere in 7–14 days looks right. The jumps between
neighbouring holds are noise.

**C6. Signal-specific exits.** Already tested and rejected in
[trading_strategy.md](trading_strategy.md): Bollinger exits, failed-cross exits, stops.
None adds alpha. Stops are tail control. Nothing here changes that.

**C7. Short-term reversal with maker orders.** 3-day reversal has a gross Sharpe of
1.13, but it trades 126% of the book a day. With resting limit orders at Hyperliquid's
0.015% maker fee instead of taker, it might clear its costs. Untested. It would also
need an execution model that daily candles can't provide.

## 5. Where I am not confident

- **In-sample construction.** The pieces that make B2, B3 and B4 profitable (the
  `peak_pct ≤ 25` cut, the bearish pullback, the bad-fire legs, the 14-day hold, SMA50)
  were all found while looking at 2023–26. The one combination fixed beforehand (v3 at
  7d) makes Sharpe 0.0–0.23 as a portfolio. The honest expectation is somewhere
  between those numbers and the in-sample ones, and I can't say where.
- **One regime carries the result.** Most of B2's and B3's profit is 2025H2–2026H1, an
  alt sell-off with high dispersion. 2023–24 was about flat after costs. That could be
  "works in bear markets, idles in bull markets" (plausible mechanism above) or one
  good year. 3.6 years can't separate them.
- **Costs are assumed, not measured.** 0.10% a side is a guess for alts with $0.6–5M
  daily volume (the middle half of fires). At 0.20% B3 halves. A short leg of 20–40
  small alts may also be hard to borrow on Hyperliquid at size, or squeezed. Real fills
  are the biggest unknown.
- **Funding is flat.** A real book pays and receives each coin's actual hourly funding.
  Crowded longs in a rally can pay far more than 9% APR.
- **The backtest is not production.** It uses the closed-candle detector. Production
  fires on the forming candle: it enters about 20h earlier (worth +0.65–0.92% raw on
  live data), and about 65% of its 00:00 first fires would not exist on closed bars. A
  bot on production signals is a *different* strategy from the one tested here.
- **Crypto only.** Equities have candles only from 2025-11 and were not backtested.
- **Sharpe intervals are wide.** Every interval in this doc is about ±1 wide. None of
  the strategies is clearly better than another, only better than zero, and several
  only just.

What I'm fairly confident of: long-only alt books ride the alt market; BTC and
large-cap hedges don't capture the alpha; a 7-day v3 book doesn't survive costs; and
timing from signal clusters doesn't work.

## 6. If you want to pursue one

1. **Pre-register portfolio-level checks before looking further.** Add to
   `rules.WATCHLIST` (or a sibling list), scored only on fires after today: B3's weekly
   long-minus-short spread > 0; B2's > 0; the bearish pullback as a long. That gets the
   first clean answer on whether the in-sample edge is real.
2. **Paper-trade B3 next to C1**, following the path in
   [trading_strategy.md](trading_strategy.md) §6. Log intended and simulated fills,
   per-coin funding, and spreads at entry. That measures the two biggest unknowns: real
   costs, and whether forming-candle fires behave like the closed-candle backtest.
3. **Decide on C1 separately.** BTC trend-following needs none of the signal research.
   Its case rests on outside evidence plus this sample, not on anything the detector
   knows.
4. **Size at 1x neutral (2x gross) until live data confirms**, and never by Kelly from
   these numbers.
5. **Test the mechanism directly:** own-history-normalised momentum without the MACD
   (§3). If it matches B3, the strategy can be simpler. If it doesn't, the detector is
   doing real work.

## Reproduction

Like the 2026-10-16 passes, the backtest scripts were scratch and are not committed.
Inputs: `state/research_cache/history_rebuild.pkl` (fires and features) and
`state/research_cache/history/*.csv` (daily candles). The construction rules in
"How the backtest works" are enough to rebuild them. If any of this becomes a candidate
for real money, the backtester should be committed with tests first.
