# Research log

One dated entry per periodic pass of [research_method.md](research_method.md), newest
first. Each entry records what the pass learned about the dataset, what it changed
in the tooling, and what it registered on the watchlist. Topic deep-dives keep their
own docs ([confidence_v3_research.md](confidence_v3_research.md),
[confidence_v3.md](confidence_v3.md)); this is the running record.

---

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
