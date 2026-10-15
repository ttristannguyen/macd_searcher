# Research log

One dated entry per periodic pass of [research_method.md](research_method.md), newest
first. Each entry records what the pass learned about the dataset, what it changed
in the tooling, and what it registered on the watchlist. Topic deep-dives keep their
own docs ([confidence_v3_research.md](confidence_v3_research.md),
[confidence_v3.md](confidence_v3.md)); this is the running record.

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
