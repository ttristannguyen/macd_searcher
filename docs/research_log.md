# Research log

One dated entry per periodic pass of [research_method.md](research_method.md), newest
first. Each entry records what the pass learned about the dataset, what it changed
in the tooling, and what it registered on the watchlist. Topic deep-dives keep their
own docs ([confidence_v3_research.md](confidence_v3_research.md),
[confidence_v3.md](confidence_v3.md)); this is the running record.

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

Question (profit_strategies.md §6.5): is B3 an own-history momentum sort that the
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

**As portfolios.** Built as in profit_strategies.md: 14d hold, 0.10% a side, flat funding.

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
coin-specific collapses ([confidence_v3.md](confidence_v3.md)), the effect should fade
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
[profit_strategies.md](profit_strategies.md) §C6a.

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

The index-name v3 result matches §3A of trading_strategy.md (tech wins, Korea/China/
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
[historical_rebuild.md](historical_rebuild.md), which has the full results.
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
  [confidence_v3_research.md](confidence_v3_research.md) §3 called them replicated
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
