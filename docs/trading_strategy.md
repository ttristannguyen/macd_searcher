# Automated trading — strategy options and how to choose between them

Planning doc. **No strategy is chosen yet** — this lays out the option space, the
evidence each option rests on, and an evaluation protocol that picks the winner on
out-of-sample, after-cost results rather than on the headline numbers. Nothing here
is built.

## 0. Audit against the research method (2026-10-15)

Every quantitative claim below was re-run under
[research_method.md](research_method.md): 7d alpha against the same-run, same-class
mean (exits from candles), repeat fires collapsed to episodes (re-fire within a day),
week-block 95% intervals, and a date-based walk-forward. Snapshot synced 2026-10-15
14:00 (7,877 deduped signals). Brackets are those intervals.

**The finding that reframes the whole plan: this strategy trades market *timing*,
not asset *selection*.** The v2 cohort's raw 7d return, +3.85% [+0.29, +6.73] per
episode, is +4.24% market move and **−0.36% alpha**. The coins it picks do no better
than random same-class coins bought at the same instant. The money comes from *when*
it buys: after crypto sell-offs that, in this sample, bounced. v2 earned +5.61% raw
on signals fired while BTC's own signal line was below zero and **−0.22%** on the
rest. That below-zero condition held during exactly **two stretches** (Jun 9 – Jul 20
and Aug 15 – 19).

So the edge's real sample is two market episodes, not 89 days or 272 episodes.
October, the first month nobody fitted anything to, had no BTC downtrend, and every
long cohort lost about 5%.

| § | claim | verdict | evidence |
|---|---|---|---|
| 1 | v2 +3.80% at 7d | **holds raw, but it is the market** | raw +3.85 [+0.29, +6.73]; market +4.24; alpha −0.36 [−1.71, +0.88] |
| 1 | real sample ~89 days | **fewer still** | 272 episodes over ~21 weeks; the timing edge rests on 2 regime stretches |
| 3A | crypto only, excl Jun 9–12: +4.68% | **true, but it is crypto's move** | v2 crypto: raw +5.50 = market +5.72, alpha −0.63. *Every* bullish crypto signal: raw +5.20, alpha +0.57. v2 adds nothing over taking them all |
| 3A | equity split: tech wins, Korea/China/IPO loses | **holds, but the doc's explanation is wrong** | group B alpha −2.88 [−4.90, −1.35] for v2, and **−2.34 [−3.69, −1.08] for *all* bullish equity signals**. These stocks underperformed their class in this period whatever fired. It is a sector repricing, not a v2-specific flaw, and `peak_pct` doesn't explain it (17% record troughs in group B vs 30% in A) |
| 3B | waiting to enter lowers returns | **confirmed** | entering at d+1 vs at fire: v2 −2.58 [−3.73, −1.09], consistent with buying a bounce whose first day matters |
| 3C | failed-cross exit is the biggest lever | **rejected as an EV lever** | timing stats verified (median 3 bars; 55 / 80 / 94% by bar 3 / 5 / 10; 0.4% never). But exiting uncrossed trades at bar *k* changes nothing. Best in-sample *k* (5) on the Aug–Sep test: v2 +0.14 [−0.16, +0.40], v3 +0.00; bullish crypto at *k*=4: −0.17. The 65.6% vs 16.0% split is look-ahead: completion is known only after the fact, and by bar *k* the loss is already taken |
| 3C | Bollinger stop adds no EV | unchanged | — |
| 3D | conviction sizing by sig/ATR depth | **drop** | sig/ATR carries no selection information (episode IC −0.025 [−0.120, +0.060]) |
| 3F | BTC hedge is the key diagnostic | **done: v2's edge is beta** | v2 crypto hedged against BTC, excl Jun 9–12: −0.11 [−1.85, +1.85]. Hedged returns elsewhere are mostly alts beating BTC, which every bullish crypto signal gets (+2.92) |
| 3G | BTC-signal-line regime filter | **cannot be validated yet** | it is where all of v2's raw EV sits, but on 2 stretches. Pre-registered on the research watchlist |
| 3H | ATR expansion: +4.85% vs +1.70%, crypto +7.24% | **raw reproduces, but it is timing again** | alpha −0.07 vs −0.08 (crypto +0.46 vs +0.38). Random crypto assets with expanding ATR also out-returned (+3.63% vs +1.90% raw) at zero alpha (+0.01). It marks post-sell-off market state, the same bet as v2 and §3G. "Doubles the pool" means more of the same market exposure |
| 1, 8 | funding not modelled | **now measured** | a 7d long pays +0.16% of notional (≈8.3%/yr; p90 +0.38%). At the proposed 3.5x total exposure, fully deployed, that is ≈0.56% of equity a week. Real, not fatal, and it scales with exposure |

**What this changes in the plan:**

1. **Split the strategy into its two layers and test them separately.**
   - *Timing:* whether to be long at all. This is where the money and the risk are,
     and it is unproven: 2 episodes.
   - *Selection:* which coin. This layer is worth ~+1% a week at best. On crypto
     excluding Jun 9–12, v3 had alpha +1.50 [−0.03, +3.31]. Bullish crypto minus
     record troughs had raw +5.63 and alpha +1.08 [−0.19, +2.36], a bigger pool than
     v2 for the same timing.
2. **If timing is the edge, consider trading it directly.** BTC/ETH or a liquid
   crypto basket when the timing condition fires could be the vehicle. Spreading the
   same market bet across 40 thin alts adds slippage without adding return.
3. **Add two gates to §5:**
   - Report each candidate's alpha (or BTC-hedged return) beside its raw return, so
     you know which layer is paying.
   - Before admitting any timing filter, count its independent regime stretches and
     require at least 5.

   Use week-block, episode-level intervals in place of "one vote per day".
4. **Treat October as the first real test**, ahead of the Aug–Sep split, which the
   plan's authors had already seen.
5. **The §7 account simulations ran on v2,** whose returns are market moves. So the
   account behaves like leveraged crypto beta bought after sell-offs. That is why
   total exposure, not per-trade risk, set the drawdown. Re-run them on whichever
   candidate replaces v2.

Pre-registered on the research watchlist (`research/rules.py`) on 2026-10-15: v2's
timing, the BTC-downtrend filter, and §3H as selection. Each is scored only on fires
from that date, so all three are pending until fresh outcomes arrive (~2026-10-22).
An earlier draft of this line quoted "baselines" from a window that had already been
seen; see [research_log.md](research_log.md).

## 1. What the data supports — and what it doesn't

The starting point is the v2 confidence cohort (bullish, sig/ATR < −0.5, reduction
0.3–0.6 — see [confidence_v2.md](confidence_v2.md)):

| | n | win | EV (7d) |
|---|---|---|---|
| all confident signals | 515 | 63.1% | +3.80% |
| at 3d instead | 517 | 70.6% | +3.54% |
| avg best move (MFE) / worst move (MAE) | | | +15.7% / −7.6% |

Three measurements, taken for this plan, change how that headline should be read:

**The signals are clustered, so the real sample is ~89 days, not 515 trades.**
Confident signals fire on a median of 3 per active day, but p90 is 14 and the
busiest day had 40. They cluster on market-wide turns. Giving each active day one
vote instead of each signal:

| | n | win | EV (7d) |
|---|---|---|---|
| one vote per day | 89 days | 51.7% | +1.93% |

Still positive, but it is a coin-flip hit rate with positive skew, not a 63% machine.

**One week carries a lot of it.** June 9–12 alone produced 128 signals (a single
market bottom). Removing those four days:

| | n | win | EV (7d) |
|---|---|---|---|
| excluding Jun 9–12 | 387 | 55.8% | +2.57% |
| crypto only, excluding Jun 9–12 | 202 | 58.9% | **+4.68%** |

Crypto survives the removal almost untouched; the rest of the book leans on that
week. That is the strongest single argument for a crypto-only universe.

**Capital is the binding constraint, not signal count.** Holding every confident
signal for 7 days means a median of 18 open positions, p90 of 73, and a peak of 152.
Any real strategy has to decide what happens on the 40-signal day.

**Not yet in any number:** exchange fees, funding payments on perpetuals, and
slippage. Every EV above is close-to-close from the fire price. *(Funding since
measured: a 7d long pays +0.16% of notional on average — §0.)*

## 2. What "most profit" should mean

Maximising raw expected profit has a trivial and ruinous answer: maximum leverage on
every signal. So the objective is **the highest return at a drawdown you can live
with** — formally, maximise expected log growth subject to a maximum drawdown limit.
In practice every candidate is ranked on net return ÷ max drawdown, with raw net
return as the tiebreak. The drawdown limit is a number only you can set (see §7).

## 3. The decision space

A strategy is one choice on each axis. The axes are independent, which is what makes
the space searchable.

### A. Universe
| option | evidence |
|---|---|
| all classes | headline +3.80%, but leans on one week |
| **crypto only** | +4.68% with the June burst removed; equity +0.21% throughout |
| crypto, liquidity-filtered | same edge, fewer thin books to fill in; cuts slippage |
| crypto + selected equities | see below — the equity +0.16% hides two opposite groups |

**Why equity averages ~0 (researched 2026-10-01).** Confident equity signals split
into two populations that cancel out:

| confident equity signals | n | win | EV (7d) |
|---|---|---|---|
| US mega/large-cap tech + crypto-proxy stocks (COIN, MSTR, HOOD, CRCL…) | 86 | 72.1% | +3.81% |
| Korea/memory, China, recent IPOs, speculative small caps | 84 | 27.4% | −3.57% |

The split holds in both regime halves (+3.08% / +4.87% vs −6.14% / −2.42%) and with
the Jul 20–22 cluster removed (+4.54% vs −2.00%). It does **not** hold for bullish
equity signals in general, so it is the v2 rule that works only on some stocks.

> **Audit 2026-10-15:** measured as alpha, it *does* hold for all bullish equity
> signals: group B −2.34% [−3.69, −1.08] against its class whatever fired. The
> losing stocks were repricing as a group, which is not a property of the v2 rule.
> See §0.

The losing groups share a cause: an ongoing *fundamental* repricing, where a deep
negative signal line means "trend", not "stretched".
- **BABA** (14 signals, 14% win, −6.33%): four straight disappointing quarters; June
  quarter net income −75% on AI spending, EPS $1.01 vs $1.78 expected, ADR −8.6% the
  next day.
- **Korea/memory** (SK Hynix, Samsung, DRAM, Micron, SanDisk, KOSPI): a multi-wave
  July rout after >200% YTD gains. SK Hynix fell 14.6% on Jul 2 and 15% on Jul 13 (Q2
  estimate 8% under consensus, slow HBM4 shipments). Our Jul 20–22 fires landed
  mid-rout: 31 signals, −198pp combined.
- **SpaceX (SPCX)**: IPO'd Jun 12 at $135, peaked $201.8, below IPO price by mid-July
  with ~1.4bn shares unlocking in phases from Aug 6.

A hand-picked whitelist would overfit, so the candidates to test are *rule-based*
versions of the same idea: an earnings-window exclusion (needs an earnings calendar),
a recent-IPO / lockup exclusion, a sector-trend filter (e.g. skip a memory name while
the DRAM index's own signal line is falling), and a liquidity/market-cap floor.

### B. Entry
| option | evidence |
|---|---|
| **market order at fire** | measured best |
| limit order a fraction below fire | may improve price, risks missing the fast movers — the ones that complete the cross |
| ~~wait for confirmation~~ | **rejected on data**: entering 1d or 3d later lowered returns in every cohort tested |

### C. Exit — probably the biggest lever
| option | idea | evidence |
|---|---|---|
| fixed 3d | take the peak win-rate horizon | 70.6% win, +3.54% |
| fixed 7d | take the peak EV horizon | 63.1% win, +3.80% |
| **failed-cross exit** | exit if the histogram has not crossed back above zero within *k* bars | bullish crosses that fail run **16.0% win / −6.11%**, completed ones **65.6% / +4.93%**; you learn which within a few bars |
| take-profit / stop-loss bracket | size the bracket from the MFE/MAE distributions | MFE +15.7% vs MAE −7.6% says a lot of upside is given back by 7d |
| trail after the cross completes | lock in once the thesis is confirmed | untested |
| opposite-signal exit | close if the same symbol fires bearish | untested |

**Timing for *k* (measured 2026-10-01, daily bars, 20-bar follow-through):** confident
signals cross a median of 3 bars after firing. 56% have crossed by bar 3, 80% by bar
5 and 94% by bar 10, and none failed to cross within 20 bars. A signal still uncrossed
at bar 5 is already in the slowest fifth, so test *k* ∈ {4, 5, 6, 8}.

The failed-cross exit is the most promising idea on the table. It is the only exit
built on the single largest effect in the dataset, and it cuts losers early without
touching winners — exactly the asymmetry that grows profit.

> **Audit 2026-10-15 — rejected as an EV lever.** Simulated on daily closes
> (exit at bar *k* if the histogram hasn't crossed, else hold 7d), walk-forward:
> the best in-sample *k* adds +0.14% [−0.16, +0.40] on Aug–Sep for v2 and +0.00% for
> v3. The 16% vs 66% split needs hindsight. By bar *k* an uncrossed trade has
> already lost most of what it will lose. It does cut 16–30% of trades early at no
> EV cost, so it may still earn a place as a way to free capital under the §7
> exposure cap. See §0.

**Bollinger-band stop (tested 2026-10-14).** Stop at the lower BB(20, 2) minus a
buffer, 544 confident signals, daily bars, 7-day hold, gap fills at the open:

| stop | hit | win | EV (1x, after taker fees) | worst trade |
|---|---|---|---|---|
| none | — | 62% | +3.34% | −20.4% |
| lower band − 2% | 24% | 57% | +2.90% | −17.6% |
| lower band − 3% | 20% | 59% | +3.03% | −18.5% |
| fixed −8% | 18% | 61% | +3.25% | −10.9% |
| fixed −5% | 40% | 51% | +2.43% | −10.9% |

No stop *adds* EV: each one also exits trades that dip and then recover. A stop's
job here is capping the tail. The lower band sits a median 4.9% below entry, so the
band-minus-2% stop is a median 6.9% away and 13.2% at p10. That variable distance is
fine **if position size is set from it** (risk a fixed % of the account, size =
risk ÷ stop distance). Used with a fixed leverage, it is not.

### D. Position sizing
| option | idea |
|---|---|
| equal notional | simplest baseline |
| **volatility-scaled** | size by 1/ATR so every trade risks the same; ATR as a % of price ranges roughly 2–8% across this universe, so equal notional gives a volatile coin 4x the risk of a quiet one |
| conviction-scaled | bigger size for deeper sig/ATR, which completes the cross more often (88% below −1 vs 83% at −1 to −0.5) |
| fractional Kelly | size from measured edge and variance; only once the edge is known out-of-sample |

### E. Portfolio limits
Max concurrent positions, max new entries per day (the 40-signal day), max per
symbol, and a cap on total BTC-beta. On a burst day the question becomes *which* 10
of 40 to take — ranked by sig/ATR depth, liquidity, or at random.

### F. Hedging
| option | what it answers |
|---|---|
| unhedged long | maximum return in an up market |
| **BTC-beta-hedged** (long the signals, short BTC against them) | whether the edge is real selection or just being long at market bottoms. Given how much of it sits in one bottoming week, this is the most important *diagnostic* in the plan, even if the hedged version isn't what you trade |

### G. Regime filter
A market-level switch, such as only trading while BTC's own signal line sits below
zero. Tempting after July's −1.08%, but a filter fitted to four months is the easiest
way in this plan to overfit. It is only admissible if it wins on data it wasn't
chosen on.

### H. Volatility state at fire (added after the AMD review, 2026-09-29)

Prompted by xyz:AMD's Sep 3 bullish fire. It came after four quiet months: price
flat, the MACD decaying to just below zero (sig/ATR −0.41, so v2 skipped it), and ATR
nearly halving. It then ran +38%. Tested across all 2,751 bullish signals, **that
quiet "squeeze" shape does not repeat**. Signals with the full AMD shape win 41% of
the time for +0.65% at 7d, and the squeeze flips sign between regime halves
(−5.71% then +5.65%).

The **opposite** state does work. Bullish fires where ATR has *expanded* over the
prior 30 bars (ratio > 1.10):

| | n | win | EV (7d) |
|---|---|---|---|
| expanding | 905 | 60.8% | +4.85% |
| the rest | 1,846 | 49.4% | +1.70% |
| expanding, crypto | 642 | 65.1% | **+7.24%** |
| expanding, equity | 198 | 46.5% | −1.46% |

Mann-Whitney p = 2.2e-9. It beats the rest in both halves (+0.59% vs −0.75%, then
+8.46% vs +4.21%) and survives removing the June burst (+4.46%).

> **Audit 2026-10-15:** all of that gap is market move. Alpha is −0.07% vs −0.08%,
> and random crypto assets with expanding ATR out-returned too (+3.63% vs +1.90%) at
> zero alpha. It marks a post-sell-off market, the same timing bet as v2. See §0. **90% of these
signals are not in the v2 rule**, so it could roughly double the crypto candidate
pool. The weak point is the first half: +0.59% is barely positive in absolute terms.
It goes into the §5 protocol as a candidate filter, not a finding.

### Out of scope for now: shorts
Bearish signals are negative EV across the book, with an MFE/MAE ratio near 0.6. The
retired v1 rule shows what happens when you trade them anyway. Revisit only with a
new, separately validated rule.

## 4. Candidate strategies to test

A starting set, chosen to span the axes rather than to guess the winner:

| id | universe | exit | sizing | limits | purpose |
|---|---|---|---|---|---|
| **S0** | all | fixed 7d | equal | none | the benchmark — the headline as a strategy |
| S1 | crypto | fixed 3d | equal | none | does the cleaner universe + faster exit beat S0? |
| S2 | crypto | failed-cross at *k*, else 7d | equal | none | the main hypothesis |
| S3 | crypto | TP/SL bracket | equal | none | does a bracket beat the signal-based exit? |
| S4 | crypto | best of S1–S3 | vol-scaled | caps | does it survive realistic capital limits? |
| S5 | = S4 | = S4 | = S4 | = S4 + BTC hedge | how much is alpha vs beta? |

The winners then get the regime filter and conviction sizing layered on, one at a
time, each required to earn its place out-of-sample.

## 5. Evaluation protocol — how we avoid fooling ourselves

**Backtester.** Daily Hyperliquid candles (the backfills already fetch and splice
these), simulating each exit rule bar by bar. Daily bars don't say whether the high or
the low came first, so when a bar touches both the stop and the target, **assume the
stop hit first**. Pessimistic by construction.

**Costs, all modelled.**
- Taker fees on both legs.
- Funding paid or received for every hour held. Pull Hyperliquid's funding history per
  symbol rather than assuming a rate.
- Slippage scaled to each asset's 24h volume, which `asset_snapshots` already logs.

**Walk-forward split.** Choose every parameter (*k*, bracket levels, caps) on
June–July. Report results on August–September, which the parameters never saw. The
out-of-sample number is the one that counts.

**Robustness gates.** A strategy is rejected if any of these fail:
1. Positive net of costs on the out-of-sample months.
2. Still positive with June 9–12 removed.
3. Still positive with one vote per day.
4. No single month's loss exceeds your drawdown limit.

**Metrics reported for every candidate:** net return, max drawdown, return ÷ drawdown,
Sortino, profit factor, time in market, worst day, and number of independent trading
days.

## 6. Path from backtest to live

1. **Paper trading, 4+ weeks.** The winning strategy runs live on real signals with
   simulated fills logged to a new table. Compare with what the backtest predicted
   for the same period; a large gap means the backtest is wrong somewhere.
2. **Small live.** Real orders at small size through a Hyperliquid **API agent
   wallet**, which can trade but cannot withdraw. Hard kill-switches: a daily loss
   limit, max open positions, max leverage, and a halt if exchange positions don't
   match the ledger.
3. **Scale** only after live results track paper results.

**Architecture guardrails, carried over from this repo:**
- The trader is a **separate process**, not part of the scanner. "Logging must never
  break a scan" extends naturally: trading must never break a scan either.
- Entries are idempotent. The scanner re-fires the same setup every 4h, so use the
  same per-symbol-per-day dedup the dashboard uses, or you'll quadruple into positions.
- The API key lives in `.env`, which I never read. Wiring it up is a step for you.

**A middle option worth considering:** semi-automation. The bot posts a proposed
order to Telegram and places it only when you tap confirm. You keep a veto while the
strategy earns trust, and the whole ledger and risk layer still get built.

## 7. Decisions only you can make

- **Capital and max acceptable drawdown.** This defines "most profit" (§2). *Open.*
- **Leverage.** *User's proposal (2026-10-14): 5–10x.* Tested against the confident
  cohort with liquidation approximated at a (1/L − 5%) adverse move:

  | leverage | liquidated before the 7-day exit | note |
  |---|---|---|
  | 5x, with a stop inside ~−15% | ~1% (gap-throughs) | workable |
  | 10x | **32–40%** | liquidation sits near −5%; the median 7-day intrabar dip is −3.9% and p25 is −6.7% |

  At 10x the exchange liquidates before the band stop (median −6.9%) can ever fire,
  so a third of trades lose 100% of their margin during dips this signal routinely
  recovers from. **Recommendation:** cap at 5x, use isolated margin, and treat
  leverage as an output of risk-based sizing (§3D), not a setting. A small account
  doesn't change this: the ruin risk per trade is the same at any account size.
  Per-asset maximums on Hyperliquid also apply; many alts allow far less than 10x.
- **Sizing.** *User's proposal (2026-10-14): 2–5% of equity as margin per trade, by
  confidence, 5x, stop at lower Bollinger band − 2%.* Account-level simulation of the
  544 confident signals (Jun 9 – Oct 7, daily mark-to-market, taker fees, **no
  funding**; skip a trade if margin is exhausted):

  | sizing | return | max drawdown | worst day |
  |---|---|---|---|
  | 2% flat | +83% | −39.8% | −21.5% |
  | 2% flat, total exposure ≤ 3x | +44% | −29.7% | −16.3% |
  | 2% flat, total exposure ≤ 2x | +20% | −23.4% | −10.9% |
  | confidence 2–5% | +57% | −38.7% | −24.2% |
  | 5% flat | +23% | −53.5% | −25.1% |

  The stop bounds *one trade* (2% × 5x × a median 6.9% stop ≈ 0.7% of equity), but
  **drawdown is set by total exposure**: signals cluster, so up to ~50 positions at
  2% margin can be open together, i.e. 5x the account long one market move. Larger
  per-trade size did *worse*, not better, and confidence-scaling did not help (its
  input, sig/ATR depth, barely changes EV inside the rule). The real controls are a
  **total-exposure cap**, a per-day entry cap, a per-sector cap, and an account-level
  halt. All of these numbers are in-sample on ~90 independent days; treat the
  differences between rows as noisy and the 20–55% drawdown range as the robust part.
- **Account halt.** *Decided (2026-10-14): −50% from peak equity.* Rationale: the
  simulated max drawdown at 2% sizing is ~−40%, so a fall past −50% means something
  is wrong rather than normal variance. Measured on Hyperliquid account value
  (mark-to-market, including unrealised PnL). On trigger: close all positions,
  cancel orders, stop new entries, and require a **manual** restart.
  - *Caveats recorded with the decision:* the −40% is in-sample, before funding, on
    ~90 independent days, so live drawdowns can run deeper without anything being
    broken. A −50% halt also cannot stop a single-move gap: with 5x total exposure a
    10% market drop is −50% before the bot can act. That is the job of the exposure
    cap, not the halt. Recovering from −50% needs +100%.
  - *Soft halt and daily loss limit — tested and rejected (2026-10-14).* Simulated on
    the same 544 signals, 2% margin, 5x, hard halt −50%:

    | added control | return | max drawdown |
    |---|---|---|
    | none | +83% | −39.8% |
    | stop entries below −25%, resume above −15% | +11% | −37.7% |
    | halve size below −25%, restore above −15% | +45% | −38.7% |
    | total exposure ≤ 3x instead | +44% | **−29.7%** |

    The entry halt deadlocks: with no new trades the account can't climb back above
    −15%, so it sat out 82 days. More fundamentally, this strategy's drawdowns happen
    during selloffs, which is exactly when confident bullish signals fire. Pausing
    after a loss removes the trades that do the recovering, so it cut return 7x while
    barely touching the drawdown. A daily loss limit fired on only 1–2 days and can't
    reduce a loss that happens within the day.

    **Drawdown is controlled at entry, not after the loss**: the total-exposure cap
    is the one control that cut it. The daily figure is kept only as an alert (a
    Telegram message on any day worse than −15%), not as a trading block.
  - *Exposure-cap sweep (2026-10-14),* 2% margin, 5x, return / max drawdown:

    | cap | full period | 1st half | 2nd half | excl Jun 9–12 |
    |---|---|---|---|---|
    | 1x | −2% / −17.5% | −0% / −10.4% | −2% / −17.0% | −5% / −17.2% |
    | 2x | +20% / −23.4% | +11% / −14.2% | +9% / −18.8% | +10% / −23.1% |
    | 3x | +44% / −29.7% | +26% / −16.4% | +14% / −25.5% | +13% / −31.1% |
    | 3.5x | +55% / −34.2% | +32% / −19.3% | **+17% / −29.2%** | +21% / −34.2% |
    | 4x | +72% / −36.7% | +47% / −20.0% | +17% / −34.5% | **+27% / −36.7%** |
    | none | +83% / −39.8% | +63% / −20.4% | +13% / −36.0% | +28% / −39.8% |

    "No cap" only wins when the June bottom is in the sample. Without it, and in the
    more recent half, return stops rising around 3.5–4x while drawdown keeps rising.
    Below 2x the strategy doesn't make money in any split. No single cap is best
    everywhere, so take the middle of the plateau rather than the brightest cell.
    Funding, not yet modelled, grows with exposure and pushes toward the lower end.
  - *Proposed (open):* total exposure ≤ **3.5x** equity as the primary drawdown
    control, with the −50% hard halt as the emergency backstop.
- **Automation.** *Decided: fully automatic* (2026-10-14). The §6 kill-switches become
  mandatory, not optional.
- **Venue.** *Decided: Hyperliquid only* (2026-10-14).

## 8. Caveats to keep honest

- About 3.5 months of data, one broad market regime, and thresholds fitted on the same
  data. The walk-forward split in §5 is the main defence, and it is a thin one.
- ~89 independent days is a small sample. Treat any backtest Sharpe from it with
  suspicion.
- Every return in this doc is gross. Funding on 7-day perp longs in a hot market is
  the cost most likely to surprise.
- Automated trading turns bugs directly into losses. The paper-trading phase exists as
  much to catch code defects as to validate the edge.
