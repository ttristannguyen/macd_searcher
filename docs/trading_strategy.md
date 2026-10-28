# Automated trading — strategy plan

Planning doc, **redesigned 2026-10-26** around the portfolio backtests in
[profit_strategies.md](profit_strategies.md). It replaces the v2 plan, a levered
long-only book of v2 bullish fires. That plan's own audit showed its returns were
market timing on two sell-offs, not selection. Its lessons are kept in the
[appendix](#appendix-the-v2-plan-and-its-audit). **Nothing here is built.** Every
number is in-sample on the 2023-03 → 2026-10 crypto rebuild unless marked, so read
each one as a ceiling.

## 0. Summary

**What to trade: B3.** A dollar-neutral crypto-perp book, long the fires the research
calls good and short the fires it calls bad, each held 14 days. Net Sharpe 1.11
[0.12, 2.22], CAGR +23%, max drawdown −22%, correlation −0.02 with both BTC and the alt
index. A BTC trend sleeve can sit beside it as a separate decision (§6).

**Why it replaces the v2 plan:**
- The selection edge is worth +0.5 to +1.5% a week, and the alt market moves ±40% in
  a half-year. Long books track the alt index (beta ≈ 1.0): the combined good-fires
  book made −11% a year, and −63% in 2025. Only a neutral book keeps the edge.
- The hedge has to look like the long leg. Hedged with BTC or the top 20 coins, the
  same longs lose 19–27% a year. The bad fires are that look-alike hedge, and they
  earn alpha of their own.

**Where the redesign wins efficiency.** At the assumed 0.10% a side, costs take about
a third of B3's gross return. Most of the changes below are about trading the same
book more cheaply and more faithfully:
1. **Closed-bar signals, once a day** (§2). The bot trades the strategy that was
   backtested, not production's forming-candle cousin.
2. **First fire per episode only** (§1.2). Sharpe 1.22–1.29 against 1.11 for all
   fires, with fewer orders.
3. **Maker-first entries worked over hours** (§3.1). The fire bar doesn't matter for
   these legs, so there's no reason to cross the spread at 00:00.
4. **One netted rebalance a day** (§3.2). Entries, exits and flips become one order
   per coin, and names that only drift are left alone.
5. **One target-book function shared by the backtester and the bot** (§8.1). Live
   trades exactly what was tested.

**What to expect.** Somewhere between the variant built only from pre-registered
pieces (Sharpe 0.23) and the in-sample 1.1–1.3. In-sample that meant roughly
+10–25% a year at 1x neutral, with flat years: 2023 and 2024 made +1% each in the
main backtest. Paper trading measures costs and fidelity. The edge itself is confirmed
leg by leg on the research watchlist (§7).

### What changed

| axis | v2 plan (to 2026-10-25) | this plan | why |
|---|---|---|---|
| what is traded | v2 bullish fires, long | four `peak_pct` legs, long and short | v2 has no selection edge (H4); `peak_pct` does (H1, H3) |
| market exposure | long, up to 3.5x | dollar-neutral | long alt books track the alt index (beta ≈ 1.0), which fell 71% in 2025 |
| hedge | none (BTC as a diagnostic) | the bad fires | BTC and top-20 hedges lose 19–27% a year |
| signal source | production alerts, forming candle | closed-bar detector at 00:00 UTC | the backtest is closed-bar; 65% of 00:00 first fires exist only on the flat bar |
| trigger | every confident fire | first fire of an episode | higher Sharpe, fewer orders; matches H9 on S1 |
| entry | market order at fire | maker-first over a window | the fire bar doesn't matter for these legs |
| hold / exit | 7d, stops and failed-cross exits considered | 14d, time exit only | the low-band edge grows with the hold; exits cost alpha (C6a) |
| size | 2–5% margin a trade at 5x | 1x neutral (2x gross), ≤ 10% a name | Kelly at a haircut Sharpe is ~1.5–1.7x |
| margin | isolated | cross, with a short tail stop | the legs offset each other |
| halt | −50% | −30% proposed (−50% with the BTC sleeve) | about 1.4x each book's backtest drawdown |

## 1. The book

### 1.1 Legs

Alpha is against the equal-weight eligible universe and signed in the direction
traded, so positive means the trade won. Per-trade numbers come from the research
log's band table (2026-10-18) and pullback pass (2026-10-16). "Fire − state" is the
2026-10-25 panel: the fire against non-firing coins in the same MACD state.

| leg | fire | side | alpha 7d / 14d | fire − state 7d / 14d | mechanism (hypothesis) |
|---|---|---|---|---|---|
| **L1** | bullish, `peak_pct ≤ 25` | long | +1.51 / +1.92 | **+1.10 / +1.62** | a dip that is mild by the coin's own standards and already over; noise around its trend, so it reverts |
| **L2** | bearish, `peak_pct ≥ 50` (the pullback) | long | +1.16 to +2.34 (three periods) / +0.5 to +2.0 by band | **+1.12** / +0.33 | a pullback in a leader: a strong trend cooling, and trends persist |
| **S1** | bearish, `peak_pct ≤ 25` | short | +0.55 / +1.04 | **+0.99 / +1.18** | a feeble rally in a weak coin, already over |
| **S2** | bullish, `50 < peak_pct < 100` | short | ≈ 0 / +0.70 to +0.85 | −0.02 / +0.35 | a deep dip is a breakdown and keeps drifting; the state does it, not the fire |

- **Not traded:** both directions at `peak_pct` 25–50 (≈ 0 at every horizon), and
  bullish record troughs (`peak_pct = 100`), which are +0.01 across history and so
  neither a long nor a short.
- **S2 is the weak leg on its own and still earns its place.** As B3's only short it
  makes Sharpe 0.73, against 0.98 for S1. Dropping it halves the book's Sharpe
  (1.14 → 0.65): it has more episodes than S1 (2,179 vs 1,557) and makes the short
  side broad enough to hedge. Trading it as the MACD state on any coin gives the same
  book (1.06), so it stays a fire: fewer names, one signal stream for all four legs.

### 1.2 Construction

- **Universe.** Hyperliquid core crypto perps above the scanner's $300k prior-day
  volume floor, with 200+ closed daily bars. The rebuild had no OI history, so it did
  not apply the $1M OI floor. The bot doesn't either, so it matches the backtest.
- **Trigger: the first fire of an episode.** An episode is a run of same-direction
  fires with no gap over a day. Re-fires inside it don't extend the hold. A new episode
  on the same coin restarts the clock. The book scored higher this way in both builds
  (1.22 in profit_strategies.md, 1.29 against 1.14 in the 2026-10-25 rebuild). On S1
  it also follows H9: bearish re-fires are worse shorts, −1.01 every year. H9 implies
  that bearish re-fires are *better* L2 longs, but the first-fire book still scored
  higher overall, so the rule is not tuned per leg.
- **Hold:** 14 daily closes from entry. The exit happens at that day's rebalance.
- **One position per coin.** A new first fire in a traded band sets the side and
  restarts the clock, so a flip is one netted order. A fire in an untraded band
  leaves the position alone. *The scratch backtests didn't record their rule for
  this. The committed backtester pins it (§8.1).*
- **Weights.** Equal weight within each side, at most 10% of equity per name. Both
  sides are sized to the thinner one: side gross = min(100%, 10% × names on the
  thinner side). With 3 longs and 20 shorts, that is 30% a side, 10% per long and 1.5%
  per short. The rest sits in cash. Topping up the thin side with a universe basket is
  a variant (§8.2).

## 2. Signals: closed bars, once a day

**The bot runs the production detector itself, on closed daily bars**
(`use_forming_candle: false`), once a day just after the 00:00 UTC close. That is the
detector `scripts/historical_rebuild.py` uses, and the one every number here comes
from. The bot does not read the scanner's alerts.

- **Fidelity.** A bot on production alerts would be a different strategy from the one
  backtested (profit_strategies.md §5). Production repaints intraday. About 65% of its
  00:00 first fires exist only because the 00:00 run reads a seconds-old, near-flat
  bar.
- **The forming candle's head start cancels out in a long/short book.** Forming fires
  come a median 20h earlier. In that time price has moved +0.92% (bullish) and +0.65%
  (bearish) in the fire's direction (raw, live data). Entering early helps L1 and S1
  by those amounts and hurts S2 and L2 by the same amounts. It is also raw market move,
  which a neutral book doesn't keep.
- **Simpler operations.** One decision a day that doesn't change intraday, with no
  dedup across the 4-hourly runs.

The scanner and the dashboard stay as they are. Telegram carries both views
(`book.py`, from 2026-10-26). The 00:00 UTC run sends this closed-bar book: every open
position by leg, today's entries in bold, and today's exits. The other runs send that
day's forming-candle fires, grouped by leg, as an early look. Only the 00:00 message
is the book.

## 3. Execution: costs are the lever

B3's Sharpe at 0 / 0.05 / 0.10 / 0.20% per side is **1.65 / 1.38 / 1.11 / 0.58**.
From that row and B3's volatility (~19%, its CAGR over its Sharpe), the assumed 0.10%
costs about 10% a year, roughly a third of gross return. Halving the cost is worth more than any filter on the
table.

### 3.1 Patient, maker-first entries

- **The fire bar doesn't matter for these legs.** Same-state coins on the day *after*
  a fire do as well as the fire. For L1 at 7d that is +2.03 (252 rows) against +1.31
  for first fires (research log 2026-10-25). The edge is slow selection that builds
  over weeks (C6a). That was measured on L1 only. Paper trading checks the other legs.
- **How:** post-only limit orders at the touch from 00:05 UTC, re-quoted through a
  fixed window (8h to start), then cross whatever is still unfilled. Hyperliquid's base
  fees are 0.015% maker against 0.045% taker.
- **This is not the v2 lesson reversed.** For v2, entering a day late cost −2.58%
  (appendix). v2 is a bounce trade that pays in its first days. These legs pay over
  weeks.
- Exits get the same treatment. The 14-day clock is in no hurry either.
- **Unknowns to log:** fill rate, and adverse selection (resting bids fill when the
  price is falling).

### 3.2 One netted rebalance a day

Each daily run computes the target book, diffs it against the open positions, and
sends one net order per coin. A coin moving from L2 to S1 on the same day trades once.
Equal weights re-spread whenever a name opens or closes. To stop that from resizing
every position each day, a name is traded only when it is more than ±25% off its
target weight. The band changes turnover, not selection. The backtester measures its
cost against tracking error (§8.2).

### 3.3 Capacity

Cap each position at about 1% of the coin's prior-day volume. At $10k equity a 10%
position is $1k, 0.3% of the $300k floor, so the cap only binds at larger size. The
edge isn't confined to illiquid coins: restricted to ≥ $2M / $10M / $50M prior-day
volume, B3 makes 0.74 / 1.69 / 1.21. That is non-monotone, so it reads as "no
liquidity dependence", not as a threshold to pick.

### 3.4 Exits

- **Time only:** close at the 14th daily close.
- **Candidate: hold the shorts 21 days** (2026-10-27,
  [exit_research.md](exit_research.md)). By day 14 the longs' alpha has stopped
  accruing. S1 and S2 keep earning in week 3, positive every year. As a portfolio
  it adds +0.27 [−0.05, +0.58] Sharpe, in both 2023–24 and 2025–26, and short holds of
  21–30 days form a plateau. It was found on this history, so it waits for its check
  (§7).
- **No path-based exit.** Stops, take-profits and trailing stops on alpha, and
  zero-cross and opposite-fire exits, were tested on all four legs. None helps in both
  halves of the history (exit_research.md §3).
- **No stop on longs.** Stops cap the tail and add no alpha (C6, appendix).
- **No failed-cross exit.** On the good fires, it sells the uncrossed trades at bar 3,
  just before they earn their alpha (C6a, 3.6 years, portfolio level).
- **Shorts get a tail stop only** (§5).

## 4. Sizing and margin

- **1x neutral (2x gross) until live data confirms the edge.** With half the backtest
  Sharpe, half-Kelly is about 1.5–1.7x. Full Kelly from the in-sample Sharpe (6.4x for
  B2) is not usable. Never size from these numbers.
- **Cross margin, not isolated.** The legs offset each other: an alt rally that hurts
  the shorts lifts the longs. Isolated margin would liquidate shorts on moves the book
  absorbs as a whole. Per-name tail risk gets its own stop instead (§5). The v2 plan
  chose isolated margin for a levered long book, where nothing offsets.
- **Gross ≤ 2x, or ≤ 3x with the BTC sleeve.** The margin needed is roughly the sum
  of each notional over its asset's max leverage. Even at a 3x alt maximum, that is
  about two-thirds of equity. The bot checks it at startup.

## 5. Risk controls

A neutral book's drawdown comes from the spread between legs, not from the market. The
v2 plan's main control, a total-exposure cap on a long book, becomes neutrality itself
plus:

| control | rule | why |
|---|---|---|
| net exposure | \|long − short\| ≤ 10% of equity after each rebalance | stays neutral as names open and close |
| per name | ≤ 10% of equity, ≤ 1% of prior-day volume | backtest construction; capacity |
| short tail stop | a resting exchange trigger order, placed at entry, closes a short that is up e.g. +50% against it | alt returns are right-skewed: B2 hedged with 20 random alts lost 36% in 2024, because a small short basket sometimes holds the one that goes 5x. Set wide enough to catch only squeezes. *Measured 2026-10-27:* at +50% it costs 0.11 Sharpe and doesn't cut drawdown, because squeezes partly revert. At +100% it costs 0.06 (exit_research.md §6) |
| account halt | at −30% from peak: close all, cancel orders, manual restart (proposal, §10) | about 1.4x B3's −22% backtest drawdown |
| ledger check | halt if exchange positions ≠ ledger | carried over |
| daily alert | Telegram message on a day worse than −5% | an alert, not a block: in the v2 tests, soft halts deadlocked |
| leg kill | drop a leg at the next rebalance if its watchlist check is contradicted | the edge is confirmed leg by leg |

**No regime switch.** B3 earned most in alt sell-offs and high-dispersion months. In
alt rallies it made less: +2.2% a month, positive in 44% of 9 such months. But no
timing rule survived history (H5, H6), so a switch would fit one cycle. Expect flat
stretches and sit through them.

## 6. Optional: a BTC trend sleeve (C1, giving B4)

- **Rule:** long the BTC perp at 1x equity when the prior daily close is above its
  N-day SMA, otherwise flat, checked at the same daily run. At N = 50 it switches about
  22 times a year.
- **Evidence:** alone (SMA50), Sharpe 1.08, max drawdown −29%. With B3: **1.51 [0.46,
  2.65]**, CAGR +67%, max drawdown −36%, positive every year. With SMA100 or SMA200 the
  combination makes 1.24 or 1.25.
- **What is robust** is that the two streams don't correlate. **What isn't** is the
  level: SMA50 was the best of four averages tried, and B3 is in-sample. Expect about
  1.2.
- **It is a market bet.** Its case rests on outside evidence (time-series trend in
  crypto is widely documented) plus one bull run, and nothing the detector knows. It
  takes the backtest drawdown from −22% to −36%. Decide it apart from B3. If yes, fix N
  before paper trading and don't change it afterwards.

## 7. Refinements wait for the watchlist

Every leg was found on the history it is backtested on. The variant built only from
pre-registered pieces makes Sharpe 0.23. So the book's *selection* doesn't change
on more backtests of that history. Each refinement waits for its out-of-sample check in
`research/rules.py`, scored only on fires from its registration date, and is adopted
one at a time.

| refinement | leg | watchlist check (registered) | on confirmation |
|---|---|---|---|
| L1 as a leg | L1 | `bullish peak_pct <= 25`, 7d and 14d (10-16, 10-18) | keep; contradicted → drop |
| L2 as a leg | L2 | `bearish pullback (peak_pct >= 50)` (10-16) | keep; contradicted → drop |
| S1 as a leg | S1 | `v3 bearish (shadow)`, 7d and 14d (10-14, 10-18) | keep; contradicted → drop |
| short S2 only if uncrossed at bar 3, entered at the bar-3 close | S2 | `bullish 50 < peak_pct < 100, uncrossed at bar 3` (10-23) | switch: ~59% of the capital for about the same drift (−1.08 vs −0.15 crossed), though ~40% of it is the state |
| skip L1 when 7d funding ≥ 15% APR | L1 | `bullish, 7d funding >= 15% APR` (10-25) | skip those longs: crowded longs still to unwind. High-funding S2 fires are already short |
| drop early-recovery coins (above SMA50, below SMA200) from S2 | S2 | `bullish 50 < peak_pct < 100, early recovery` (10-24) | only once a mechanism exists; it is a post hoc 2×2 cut |
| hold S1 21 days instead of 14 | S1 | `crypto bearish peak_pct <= 25, first fires`, 14d exit → 21d (10-27) | hold S1 21 days |
| hold S2 21 days instead of 14 | S2 | `crypto bullish 50 < peak_pct < 100, first fires`, 14d exit → 21d (10-27) | hold S2 21 days |
| exit a long whose coin enters a deep dip (hist < 0, state `peak_pct ≥ 75`) | L2 | `crypto pullback, first fires, deep dip by day 13` (10-27) | add the exit; its history gain is mostly 2023–24 |
| L2 only at 75 ≤ `peak_pct` < 100 | L2 | `crypto pullback 75 <= peak_pct < 100, first fires` against the rest of the pullback, 14d (10-28) | remove the 50–75 band and record peaks from L2 |
| no record peaks in L2 | L2 | the same band against `crypto pullback peak_pct >= 75, first fires`, 14d (10-28) | remove record peaks from L2 |
| pullback above SMA200 | L2 | `crypto pullback above SMA200` (10-19) | relevant only with a 7d L2 hold: the trend changes how fast the pullback pays, not how much |
| v3 on index equities | new sleeve | `v3 bullish, S&P 500 / Nasdaq-100` (10-19) | a separate equity book, backtested first |

profit_strategies.md §6.1 also asked for portfolio-level checks. The paper book
provides the first one: B3's long-minus-short spread, logged from the day paper
trading starts and never backfilled (§8.3).

## 8. Build and evaluation

### 8.1 Commit the backtester first, and calibrate it

- The profit_strategies.md backtests were scratch scripts. Commit one, with tests,
  that reproduces B3 on the cached history (`state/research_cache/`): Sharpe about 1.1
  on all fires, 1.2–1.3 on first fires. This is the same discipline as
  [historical_rebuild.md](historical_rebuild.md)'s calibration. If it lands far off,
  find out why before going further.
- **One pure target-book function** maps fires, closed bars and the open positions to
  target weights. The backtester and the live bot both call it, so live trades what
  was tested. Candles, the exchange and the ledger stay outside it, the same layering
  as `stats.py` → `web/perf.py`. The rules §1.2 leaves open (side conflicts, thin
  sides) are pinned here, with tests.

### 8.2 Execution variants only

More selection changes on this history would add more in-sample selection. So the
backtester tests only how the book is executed, each variant against the calibrated
baseline:

1. first fire per episode vs all fires (the baseline is first fires)
2. the ±25% drift band, against daily re-weighting: turnover vs tracking
3. the short tail stop's level: is its alpha cost ≈ 0?
4. thin side scaled down vs topped up with a universe basket: capital use
5. per-leg holds: shorts at 21d, longs at 14d (+0.27 Sharpe in-sample,
   exit_research.md). This replaces the earlier candidate, L2 at 7d. L2's fire edge is
   front-loaded, but as a portfolio the change is neutral (1.40 vs 1.42) and adds 14%
   turnover. It is a horizon found on this history, so it is adopted only if its live
   check agrees (§7)
6. costs at the per-side figure paper trading measures

Report for each: Sharpe with a 30-day block-bootstrap 95% interval, CAGR, max
drawdown, years and half-years, turnover, average names per side, and cost and
funding drag.

### 8.3 Paper trading, 8 weeks or more

The live bot runs against real order books, with simulated fills logged to a new table
next to a backtest replay of the same days.

**It measures:**
- **Real costs per side:** spread, slippage, maker fill rate, adverse selection. This
  is the biggest unknown. At 0.20% the Sharpe halves.
- **Fidelity:** paper book vs replay. Every gap is a bug or a cost.
- **Real funding per coin.** The backtest assumes a flat 9% APR paid on longs and 6.5%
  received on shorts.

**It can't measure the edge.** Over 8 weeks a Sharpe's standard error is about ±2.5,
so 8 weeks of P&L is noise. The legs are confirmed on the watchlist, which counts
episodes, not weeks.

**Go to small live when all of these hold:**
1. Measured all-in cost ≤ 0.10% a side.
2. Paper vs replay differences are explained by costs and timing, with no unexplained
   position mismatch.
3. No leg's watchlist check is contradicted.

**Stop and rethink if** costs stay above 0.20% a side after maker execution, or two
legs are contradicted.

### 8.4 Small live, then scale

- Real orders at small size through a Hyperliquid **API agent wallet**, which can
  trade but not withdraw. Every §5 control is mandatory.
- Scale capital only after live tracks paper. Raise gross towards ~1.5x only after
  the watchlist confirms the legs.

**Architecture guardrails:**
- **A separate process.** Trading must never break a scan, and a scan never places an
  order.
- **Idempotent by construction.** The target book is a function of closed bars, so
  re-running a day gives the same orders. The ledger keys each rebalance by its UTC
  day.
- **Once a day.** The only intraday logic is the short tail stop, and it rests on the
  exchange, so no intraday process is needed.
- **The API key lives in `.env`, which I never read.** Wiring it up is a step for
  you.

## 9. Left out on purpose

| idea | why not | source |
|---|---|---|
| long-only signal books | they ride the alt index (beta ≈ 1.0) | profit_strategies.md A1 |
| BTC or top-20 hedge | adds the majors-minus-alts gap: −19% to −27% a year | B2 hedge table |
| v3 bullish at 7d, universe-hedged | costs take it from 0.59 gross to 0.00 net | B1 |
| market timing (v2, BTC downtrend, signal clusters) | no timing hypothesis survived history | H4–H6, A4, C2 |
| stops on longs, Bollinger and failed-cross exits | no alpha; the failed-cross exit gives up unpaid edge | C6, C6a |
| stops, take-profits and trailing stops on alpha; zero-cross and opposite-fire exits | none helps in both halves of the history; take-profits flip sign with the market | exit_research.md §3 |
| sizing by sig/ATR | sig carries no selection information | confidence_v3_research.md §1 |
| SMA filter on the pullback at 14d | the gap is gone by 14d | research log 2026-10-24 |
| ATR expansion | timing, not selection | H7 |
| record-trough gate | doesn't generalise (+0.01 across history) | H2 |
| equities | no candles before 2025-11; a sleeve only if its check confirms | §7 |
| funding carry, maker-order reversal | don't use the signals; can't be backtested here | C3, C7 |

## 10. Decisions only you can make

- **Capital and maximum acceptable drawdown.** *Open.* They set the halt and the gross.
- **Leverage.** The 5–10x proposal (2026-10-14) was for a long-only book and is
  **superseded**. *Proposal:* 1x neutral (2x gross), at most ~1.5x after the
  watchlist confirms.
- **Account halt.** −50% was decided (2026-10-14) for the v2 book. **Re-opened.**
  *Proposal:* −30% for B3 alone and −50% with the BTC sleeve, about 1.4x each book's
  backtest drawdown (−22%, −36%).
- **BTC sleeve.** *Open:* whether to run it, and which N, fixed before paper trading.
- **Automation.** *Decided:* fully automatic (2026-10-14). That stands, and the §5
  controls are mandatory.
- **Venue.** *Decided:* Hyperliquid only (2026-10-14). That stands. Every core perp
  can be shorted, and shorts receive funding at the baseline rate.

## 11. Caveats

- **In-sample ceiling.** The legs, the 14-day hold and SMA50 were all found on
  2023–26. The pre-registered variant made 0.23.
- **One regime carries the result.** Most of the profit came in 2025H2 and 2026H1
  (+48%, +14%), an alt sell-off with high dispersion.
- **Costs, funding and short availability are assumed.** Squeezes and borrow at size
  are unknown until paper and small live.
- **Only the daily message is the book.** The intraday Telegram alerts are
  forming-candle fires and won't match it one-to-one, by design (§2).
- **Crypto only.** Every interval is about ±1 Sharpe wide. B3 is better than zero, and
  only just at the lower bound.

## Appendix: the v2 plan and its audit

The plan before 2026-10-26 traded v2 confident bullish fires long, at 2–5% margin per
trade, 5x, with a total-exposure cap around 3.5x. The full text is in git history:
`git show bfdbc5d:docs/trading_strategy.md`.

**The audit (2026-10-15).** v2's raw 7d return of +3.85% per episode was +4.24% market
move and −0.36% alpha. Its picks did no better than random same-class coins bought at
the same instant. The money came from buying after crypto sell-offs that bounced,
during two BTC-downtrend stretches. The historical rebuild then found no v2 selection
edge (H4) and no timing rule that holds (H5, H6). That left nothing to trade in the
v2 plan, and led to profit_strategies.md and this redesign.

The plan's two candidate filters are still tracked on the watchlist. **§3G** was a
regime switch: trade only while BTC's own MACD signal line is below zero. **§3H** was
ATR expansion, ATR14 over its value 30 bars earlier > 1.10. Both turned out to be
timing, not selection (H6, H7).

**Lessons that carry over:**

| lesson | evidence (v2, Jun–Oct 2026) | where it lands now |
|---|---|---|
| drawdown is set by total exposure, not per-trade stops | 2% margin at 5x: −39.8% max drawdown uncapped, −29.7% with exposure ≤ 3x; a stop bounded one trade at ~0.7% of equity | neutrality plus a gross cap (§4, §5) |
| soft halts deadlock | stopping entries below −25% sat out 82 days and cut return from +83% to +11% | hard manual halt; the daily loss is an alert (§5) |
| high leverage liquidates on ordinary dips | at 10x, 32–40% of trades were liquidated before the 7d exit | ≤ 2x gross (§4) |
| stops cap the tail and add no EV | lower Bollinger band −2%: +3.34% → +2.90%; fixed −8%: +3.25% | no long stops; a short tail stop only (§3.4) |
| the failed-cross exit needs hindsight | the 16% vs 66% win split is known only afterwards; walk-forward +0.14 [−0.16, +0.40] | rejected again over 3.6 years (C6a) |
| entering late cost v2 | d+1 entry: −2.58 [−3.73, −1.09] | v2 is a bounce trade; these legs aren't (§3.1) |
| the equity split (US tech wins; Korea, China, IPOs lose) is sector repricing | the losing group's alpha was −2.34 for *all* bullish equity signals, not just v2 | equities wait for their own check (§7) |
| clustered signals make capital the constraint | v2 held a median 18 positions, p90 73 | 10% cap, equal weight, first fires only (§1.2) |
