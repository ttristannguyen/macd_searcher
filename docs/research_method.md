# Research method — how signal-quality analysis is done here

The conventions for any analysis of signal outcomes, and the pipeline that
implements them. Every rule below exists because breaking it produced a wrong
conclusion at least once; the "why" is the mistake it prevents. Each pass is logged
in [research_log.md](research_log.md); topic deep-dives live in their own docs
(currently [confidence_v3_research.md](confidence_v3_research.md)). This doc is only
the method.

## Running it

```
uv run python -m macd_searcher.research              # top up cache, print markdown report
uv run python -m macd_searcher.research --offline    # cache only, no API calls (~25s)
uv run python -m macd_searcher.research --scan       # also scan every feature (slow)
uv run python -m macd_searcher.research --out report.md
```

Reads `state/prod_snapshot.sqlite3` (synced daily by `scripts/sync_prod_db.ps1`)
read-only. Candles and hourly funding are cached under `state/research_cache/` and
topped up incrementally. The first run's funding fetch takes ~45 minutes because the
API rate-limits history requests; later runs take a minute or two. A symbol that
fails is skipped and retried next run.

The report has four parts: rule cohorts (`research/rules.py`) with raw = market +
alpha, the pre-registered watchlist, funding carry, and optionally a feature scan.

## A periodic pass

1. Sync the database, run the report.
2. **Read the watchlist first.** Those hypotheses were written down before this data
   existed; they are the only results that are genuinely out of sample. Each check is
   scored only on fires from its `registered` date. A hypothesis formed while looking
   at a window cannot be confirmed by that same window.
3. Update the findings doc with what moved. Cite the snapshot date — magnitudes
   shift with every sync; signs and orderings should not.
4. Write every new hypothesis into `rules.WATCHLIST` with today's `registered`
   date, so the *next* pass tests it on data nobody has seen. Log the pass in
   [research_log.md](research_log.md).
5. If the live rule is retuned, move `DEFAULT_OOS_FROM` to the day after its new fit
   window.

## Know the dataset (as of 2026-10-15)

Structural facts that change how any result should be read. Re-check them when they
look stale.

- **Signals are common.** ~39% of the day's universe fires at least once. 30.6k raw
  alerts collapse to 7.9k after per-day dedup and **~2.4k episodes**. The episode is
  the unit of evidence.
- **One market cycle.** June crash, Aug–Sep rally, falling October. Anything that
  depends on market direction has about one turn behind it.
- **Commodity, fx and index have no benchmark** (fewer than 10 same-run symbols each),
  so ~6% of scored rows carry no alpha.
- **The 00:00 run reads a near-flat forming candle,** which mechanically shrinks the
  histogram. About 65% of 00:00 first fires would not fire on closed bars. Split by
  hour when a result looks odd.

## The rules

**1. Measure alpha against the same-run, same-class MEAN.** For each signal, the
benchmark is the mean forward return of every same-class symbol in that run's
snapshot, entered at that run's `live_close` and exited on the same daily bar as
`px_Nd`. A random pick scores exactly zero. *Why:* returns are right-skewed, so a
**median** benchmark hands every selection about +1.1% of free "alpha" at 7d — a
random one included. A first draft of
[direction_asymmetry_analysis.md](direction_asymmetry_analysis.md) reported a
split-half-robust edge that was entirely this bias.

**2. Take exit prices from candles, not snapshots.** *Why:* a snapshot only exists
while the symbol is inside the liquidity filter, and the assets that fall out are the
losers (−2.5% over 7d against +2.1% for those that stay). Snapshot-only exits inflate
the benchmark and bias alpha against bullish signals.

**3. Judge rules on alpha, not raw EV.** Raw EV = market move + alpha, and neither
the detector nor any market-regime feature tested has predicted the market move out
of sample. *Why:* confidence v1 was retired on a −10.4% month that was the market
rallying 10.45% against its shorts (its alpha that month: −0.19%), and v2 was adopted
on +3.8% EV that was +4.6% market move and −0.6% alpha.

**4. Compare every rate with the counterfactual.** Before calling "X% of signals do
Y" a finding, measure the same rate for random same-class assets on the same days.
*Why:* "20% of bearish signals blow up >10%" was exactly the base rate (21.4% vs
21.5%) — there was nothing to explain. The same applies to features: a feature that
predicts alpha for random universe assets too is a generic factor (e.g. low
volatility), not something the detector knows.

**5. Count episodes, not rows.** ~69% of deduped signals also fired the day before,
with near-identical forward windows. Group repeat fires into episodes
(`dataset.assign_episodes`, gap ≤ 1 day by default), report episodes next to `n`, and
give intervals at episode level with **week**-block resampling. *Why:* only ~26% of
rows are independent; day-block intervals made a bearish leg look robust that does not
survive episode-level inference.

**6. Split in- and out-of-sample by date.** Out of sample starts the day after the
live rule's fit window. New thresholds are set in-sample (medians or round numbers,
not optimised) and then checked out of sample. Scan many features with a
Benjamini–Hochberg correction. *Why:* market-timing features (BTC trend, breadth)
were the strongest in-sample predictors of raw return in the whole scan and all
flipped sign out of sample.

**7. No look-ahead.** Features come from bars closed **before** the fire day. Never
use a forward-window column as a feature: `bars_to_zero_cross`,
`max_favorable_move_pct`, `max_adverse_move_pct`, `outcome_updated_at`, `carry_7d`.
*Why:* "never crossed zero" looked like a +6.7% predictor until restricted to
"crossed by day 3", when the effect reversed.

**8. Check absolute thresholds against volatility.** Median daily ATR in this
universe is ~6% of price; a ">10% move in 14 days" is 1.6 daily ATRs. *Why:* half of
the so-called bearish "blow-ups" were under 3 ATR — ordinary noise.

**9. Explain the mechanism before recommending.** A pattern with no mechanism and no
counterfactual check is a hypothesis for the watchlist, not a rule change.
