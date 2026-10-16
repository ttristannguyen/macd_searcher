# Historical rebuild — pre-registration

**Status: frozen before any historical data is fetched.** Everything below (data
construction, hypotheses, thresholds, decision rules) is fixed now. The results get
appended at the bottom; the sections above them do not change after the first fetch.
If a better threshold shows up in history, it is **not** adopted here. It becomes a new
watchlist hypothesis, tested on live data that hasn't been seen.

## Why

Every finding so far rests on Jun 9 – Oct 8 2026: about 2,400 episodes and one market
cycle (a June crash, an Aug–Sep rally, a falling October). The live watchlist will take
2–6 weeks to score most hypotheses, and the timing questions need market regimes that
4 months cannot supply. Hyperliquid has daily candles for the major crypto perps back to
at least 2022-01-01. Rebuilding the detector on that history gives the hypotheses below
data they were never fitted to, across several regimes, including the 2022 bear market.

## What is rebuilt (frozen)

- **Period.** Confirmatory test: **2022-01-01 → 2026-06-08**, entirely before the live
  data the hypotheses came from. The live period (2026-06-09 → 2026-10-08) is rebuilt
  too, but only as a calibration check (below), never as evidence.
- **Assets.** Crypto only. Equities have candles only from 2025-11. Include every
  crypto symbol the API returns candles for. Check whether delisted coins return
  candles. If they don't, the survivorship bias is recorded with its direction rather
  than fixed.
- **Universe per day.** A symbol is eligible on day D if its prior-day notional volume
  (candle volume × close) ≥ **$300,000**, the scanner's `min_24h_volume_usd`. Open
  interest history doesn't exist, so the $1M OI floor is not applied. It needs 200+
  closed bars.
- **Detector.** The production code, unchanged: `signals._check_histogram_flattening`
  plus `_peak_vs_history`, current `config.yaml` (MACD 12/26/9, shrink 2, reduction ≥
  0.3, peak lookback 10, noise floor 0.2%), on a **200-bar window of closed daily bars**,
  evaluated once per symbol per day at the open. This is the closed-candle detector,
  which reproduced 85% of production's 00:00 fires on live data.
- **Entry / exit.** Entry at the open of day D (the prior close). Exit at the close of
  day D+N, N ∈ {1, 3, 7, 14}. **The primary horizon is 7d.** The direction-normalised
  return is `r`.
- **Benchmark.** The equal-weight **mean** N-day return of every eligible crypto symbol
  that day, same entry and exit bars, needing ≥ 10 symbols. `alpha = sign × (raw −
  benchmark)`. All exits from candles, so a symbol later dropping below the volume
  floor is still counted.
- **Features at fire.** As in production and `research/dataset.py`: `peak_pct`, `red`,
  `sig_atr` (ATR14 on closed bars), `atr_change_30`, BTC's MACD signal line as of
  D−1.
- **Inference.** Episodes (a re-fire within 1 day continues one). Episode-level means
  with week-block 95% intervals. Calendar years reported separately.

## Calibration — before reading any history

Rebuild 2026-06-09 → 2026-10-08 with the code above and compare it with the
closed-candle reconstruction already measured on live snapshots (2026-10-15). It
should land close to: v3 bullish alpha +0.44%, record trough −3.07%, bullish all
−0.69%. **If the rebuild is far off, stop and find out why before reading 2022–2026.**
The two differ in universe (volume-only proxy vs snapshot) and benchmark (rebuilt
universe vs snapshot class), so exact agreement is not expected. Agreement in sign
and rough size is.

## Hypotheses (frozen)

Each has an expected sign. **Confirmed** = the whole 95% episode-level interval on the
expected side over 2022-01 → 2026-06, **and** the point estimate on the expected side in
at least 3 of the 5 calendar years 2022–2026. **Contradicted** = the whole interval on
the other side. Anything else is **undecided**.

| # | hypothesis | measure | expected |
|---|---|---|---|
| H1 | v3 bullish (`peak_pct` ≤ 50, `red` < 0.6) picks better assets | 7d alpha | > 0 |
| H2 | bullish fires on a record trough (`peak_pct` = 100) underperform | 7d alpha | < 0 |
| H3 | among bullish fires, lower `peak_pct` → better alpha | episode Spearman IC(`peak_pct`, alpha) | < 0 |
| H4 | v2 (`sig_atr` < −0.5, `red` < 0.6) picks better assets | 7d alpha | > 0 *(current evidence: no)* |
| H5 | v2's fires catch better market moves than other bullish fires (timing) | market move: v2 − rest of bullish | > 0 |
| H6 | bullish fires while BTC's signal line < 0 beat the rest (regime filter) | raw `r`: in-regime − rest | > 0, **and ≥ 5 independent BTC-downtrend stretches** before it is admissible |
| H7 | ATR expansion (`atr_change_30` > 1.10) picks better assets | 7d alpha | > 0 *(current evidence: no — it is timing)* |
| H8 | bearish low peak (`peak_pct` ≤ 25) is a better short | 7d short-side alpha | > 0 |
| H9 | bearish repeat fires are worse shorts than first fires | alpha: repeat − first, same episode | < 0 |

**Not testable here, so not tested:** anything needing the forming candle (the
~0.9% early-entry gain, repaint, the 00:00 first-fire effect), funding, equities.

## What each outcome would change

- **H1 and H2 confirmed** → v3 and the record-trough warning are no longer one-cycle
  findings. Promote v3 if the live watchlist does not contradict it. Treat the record
  warning as a candidate *gate*, not just a marker.
- **H3 confirmed, H1 not** → `peak_pct` matters but the ≤ 50 cut is wrong. Register a
  new threshold hypothesis for live data; do not change it from history.
- **H4 contradicted or undecided** → confirms retiring v2's selection logic.
- **H5 or H6 confirmed (with H6's ≥ 5 stretches)** → the timing layer of
  `trading_strategy.md` has evidence across regimes. That is the single biggest open
  question for the strategy.
- **H7** → whether §3H belongs in the strategy as selection or only as timing.
- **H8 / H9** → only relevant if shorts are ever traded.

## How the live watchlist changes afterwards (frozen)

History tests the closed-candle idea; the live watchlist tests the deployed,
forming-candle system going forward. After the run, each live check takes the role
below.

| live check | history | if confirmed in history | otherwise |
|---|---|---|---|
| v3 bullish | H1 | **monitor**: promote once live has ≥ 30 episodes and does not contradict | stays a discovery test |
| record-peak warning | H2 | **monitor**; becomes a gate candidate | stays a discovery test |
| v2 selection | H4 | — | stays a monitor (expected: no edge) |
| v2 timing | H5 | **monitor** | stays a discovery test |
| BTC downtrend | H6 | **monitor** | stays a discovery test |
| ATR expanding | H7 | **monitor** | stays a discovery test |
| v3 bearish shadow | H8 | **monitor** | stays a discovery test |
| bearish repeat fires | H9 | **monitor** | stays a discovery test |
| bullish 00:00 first fire | not testable | — | unchanged: live is the only test |

A **monitor** acts once it has ≥ 30 live episodes and its interval is not entirely on
the wrong side. A **discovery test** needs the full live confirmation. A hypothesis
*contradicted* in history is dropped from the watchlist. Anything new found in history
is registered as a fresh live check and confirmed only on live data.

## Known biases, with direction

- **Closed candle only.** It misses the earlier forming-candle entry (+0.65–0.92% on
  live data), so raw returns understate production. Relative comparisons (alpha, and
  rule vs rest) are much less affected.
- **Liquidity proxy.** Volume only, no OI floor, so the universe is broader than
  production's. The direction is unclear; it is checked in calibration.
- **Survivorship**, if delisted coins are missing. Signals and benchmark come from the
  same survivors, so alpha is partly protected and raw returns are inflated.
- **Thin early universe.** Fewer eligible symbols in 2022–2023, so some days fail the
  10-symbol benchmark floor. The coverage per year is reported.
- **Multiple testing.** Nine hypotheses at 95%: about 0.45 false confirmations
  expected by chance. The per-year consistency requirement is the guard. A lone
  confirmation should be read with that in mind.

## Results

*(Appended after the run. Nothing above this line changes.)*

Run 2026-10-16 with `scripts/historical_rebuild.py` (48s, cached in
`state/research_cache/history_rebuild.pkl`).

### Data-construction notes, found before any outcome was read

- **Survivorship: none for coins that ever listed.** All 234 core perps returned
  history, including all 56 flagged delisted. Hyperliquid keeps delisted coins in its
  asset list.
- **2022 is empty, and 2023 is thin.** Candles go back to 2021, but under the frozen
  $300k notional floor no coin is eligible in 2022 (Hyperliquid's own market was too
  small). Only a median 16 coins per day are eligible in 2023 (81% of days have a
  benchmark), against 66–95 from 2024. The effective window is **2023 → 2026-06-08**.
  The rules were not relaxed: "3 of 5 years" now in practice means 3 of the 4 years
  with data.
- Confirmatory sample: 23,125 fires in 10,372 episodes, about 4× the live dataset.

### Calibration — passed

| live period, rebuilt | rebuilt | snapshot reconstruction |
|---|---|---|
| v3 bullish | +0.13 [−0.98, +1.29] | +0.44 |
| record trough | −3.82 [−6.47, −0.79] | −3.07 |
| all bullish | −0.68 [−1.49, +0.09] | −0.69 |
| all bearish | −1.13 [−1.79, −0.52] | −1.04 |

Same sign and similar size on every line, so the rebuild measures what the live data
measured.

### Confirmatory — 2022-01-01 → 2026-06-08, 7d, episode-level, week-block 95% CI

| # | hypothesis | result | by year (2023 / 24 / 25 / 26) | verdict |
|---|---|---|---|---|
| H1 | v3 bullish alpha > 0 | **+0.58 [+0.04, +1.15]**, 1,441 ep | +0.59 / +0.80 / +0.44 / +0.62 | **CONFIRMED** |
| H2 | record trough alpha < 0 | +0.01 [−0.87, +0.94], 728 ep | +1.11 / −0.71 / +1.24 / +1.55 | undecided |
| H3 | IC(`peak_pct`, alpha) < 0 | **−0.06 [−0.09, −0.02]**, 4,748 ep | −0.05 / −0.05 / −0.05 / −0.09 | **CONFIRMED** |
| H4 | v2 alpha > 0 | +0.08 [−0.42, +0.60] | −0.72 / +0.46 / −0.01 / +0.08 | undecided (no edge, as expected) |
| H5 | v2 timing (market, v2 − rest) > 0 | +1.73 [−1.48, +4.91] | −0.57 / +2.60 / +2.42 / +1.92 | undecided |
| H6 | BTC-downtrend raw, in − out > 0 | +2.10 [−2.08, +6.28]; 21 stretches (admissible) | −8.00 / +2.63 / +6.61 / −1.67 | undecided |
| H7 | ATR expansion alpha > 0 | −0.33 [−0.89, +0.26] | +0.87 / −0.44 / −0.11 / −1.17 | undecided (no selection, as expected) |
| H8 | bearish low-peak short alpha > 0 | +0.55 [−0.11, +1.20] | +1.28 / +0.03 / +1.03 / +0.08 | undecided |
| H9 | bearish repeat − first < 0 | **−1.01 [−1.29, −0.73]**, 3,148 ep | −1.31 / −1.18 / −0.85 / −0.95 | **CONFIRMED** |

### What it means

- **v3's selection edge is real but small.** +0.58% a week against the asset's own
  universe, positive in every year with data. That is about two-thirds of the live
  estimate (+0.88%), the usual shrinkage of an estimate made on the data it was found
  in. The historical number is the less biased one. `peak_pct` matters (H3) in every
  year, at a modest IC of −0.06.
- **The record-trough warning does not generalise.** It was strongly negative in the
  2026 live period (and again in the rebuilt live period, −3.82%), but across
  2023–2026 it is +0.01%, positive in three of four years. Its live strength was
  specific to this cycle. Under the frozen mapping it stays a discovery test and is
  **not** a gate candidate. The Telegram/dashboard warning, and the strong language
  around it in `signals.py` and `confidence_v3.md`, should be revisited.
- **Bearish repeat fires really are worse shorts** (H9): −1.01% every year. A bearish
  setup that keeps re-firing without the price falling is showing strength.
- **No timing hypothesis is confirmed.** v2's timing (H5) is positive in the three most
  recent years but the interval spans zero. The BTC-downtrend filter (H6) had 21
  regime stretches to prove itself and was inconsistent: −8.0 in 2023, +6.6 in 2025.
  The timing layer of `trading_strategy.md` still has no cross-regime evidence.
- **v2 has no selection edge, and ATR expansion adds no selection**, in history as live.
- Three of nine confirmed, against about 0.45 expected by chance. All three are
  consistent in every year with data, which chance rarely produces.

### Live watchlist, per the frozen mapping

- **Become monitors** (act at ≥ 30 live episodes unless contradicted): v3 bullish (H1)
  and bearish repeat fires (H9). The v2-selection check keeps its discovery form,
  since it is watching for an edge v2 has never shown.
- **Stay discovery tests:** record trough (H2), v2 timing (H5), BTC downtrend (H6), ATR
  expansion (H7), bearish low peak (H8), and the 00:00 first fire (not testable here).
- Nothing was contradicted, so nothing is dropped.
