# Research — algorithms, patterns & indicators for the analysis roadmap

A methods reference for the analytical and signal-quality items in
[NEXT_STEPS.md](../NEXT_STEPS.md) (§2 analysis & outcome engine, §4 signal
quality). For each, the concrete algorithm/indicator/pattern, the formula, and
how it lands in *our* stack — so this is a build sheet, not a reading list.

## Ground rules for this codebase

- **Stack:** `numpy` + `pandas` + **`scipy`** (the standard scientific-Python
  lib; an approved runtime dep). Use `scipy.stats` for the CI/IC stats (§0) —
  don't hand-roll standard routines. Its ~50 MB import RSS is fine for a private,
  low-traffic dashboard on the 1 GB VM, and scipy is only imported where the
  analysis actually runs.
- **SQLite can't** do median/stddev/percentile/correlation. Pull the raw deduped
  rows via the `perf` CTE in [`web/perf.py`](../src/macd_searcher/web/perf.py) and
  compute in Python. [`stats.py`](../src/macd_searcher/stats.py) holds only the
  project-specific `summarize` (quantiles + winsorized mean); the rest is
  `scipy.stats` (§0).
- **Cross-refs:** in a section header `(§N)` names the *NEXT_STEPS* item addressed;
  a bare `§N` in the body refers to a section of *this* doc.
- **Philosophy:** this is a *loose gauge*, not an edge engine. Prefer **robust**
  (median/winsorized over mean), **confidence-bounded** (rank by a lower bound,
  not a point estimate), and **sample-gated** (min-n) estimates. One market
  regime — every number carries that caveat.

---

## 0. Stats library — use `scipy.stats`

These are solved problems; use `scipy.stats` (an approved runtime dep, §ground
rules) directly rather than hand-rolling. The calls to reach for in §1–§4:

| Need | Call | Notes |
|---|---|---|
| Wilson CI for a proportion | `stats.binomtest(k, n).proportion_ci(method="wilson")` | correct at small n / p≈0,1; returns `(low, high)` |
| Bootstrap CI for the mean | `stats.bootstrap((x,), np.mean, method="BCa", random_state=0).confidence_interval` | BCa is bias-corrected for skew; seed for reproducibility |
| Spearman rank corr (IC) | `stats.spearmanr(a, b, nan_policy="omit").statistic` | averages tied ranks + drops NaN pairs natively |
| quantiles / winsorized mean | `summarize(x)` in [`stats.py`](../src/macd_searcher/stats.py) | project-specific bundle; numpy, no scipy equivalent |

(`from scipy import stats`.) **Caller still guards the edges** — these also gate
the scorecard, so it's free: BCa bootstrap needs n ≥ 2 and non-zero variance;
`spearmanr` returns nan for < 2 pairs or constant input; `binomtest` needs
0 ≤ k ≤ n. scipy is imported only where the analysis runs, so the idle dashboard
pays nothing until a perf endpoint actually calls it.

---

## 1. Confidence intervals (the "is it real / reliable" layer)

### 1a. Win-rate → Wilson score interval

A proportion (k wins of n). **Don't use the Wald/normal interval** `p ± z·√(p(1−p)/n)` — it collapses to zero width at p=1 and can fall outside [0,1]. **Wilson** — `scipy.stats.binomtest(k, n).proportion_ci(method="wilson")` (§0) — is the standard fix and behaves at small n / extreme p. *Alternatives:* Agresti–Coull, Jeffreys (`Beta(k+½, n−k+½)`). Wilson is the right default.

> Use the **lower bound** when ranking: a 100%/n=3 token has a Wilson lower bound of ≈0.44, so it can't outrank a 65%/n=40 token (lower bound ≈ 0.50).

### 1b. Expectancy / mean return → bootstrap CI

Returns are fat-tailed and right-skewed, so the normal/t-interval's assumptions are weak. The **bootstrap** makes no distributional assumption: resample with replacement, recompute the mean, read the interval off the resamples. Use `scipy.stats.bootstrap((x,), np.mean, method="BCa", random_state=0)` (§0) — **BCa** (bias-corrected & accelerated) handles the skew better than a plain percentile interval.

### 1c. Small-n shrinkage → empirical Bayes (Beta–Binomial)

The principled cure for "lots of symbols, few signals each." Model each symbol's wins as `Binomial(n_i, p_i)` with a shared prior `Beta(α, β)` fit to the *population* of per-symbol win-rates (method of moments on the observed mean/variance). The shrunk estimate is the posterior mean:

```
p̂_i = (k_i + α) / (n_i + α + β)
```

Small-n symbols get pulled toward the global rate; high-n symbols barely move. This (James–Stein flavour) is more elegant than a hard min-n cutoff and ranks symbols more fairly. Treat as a v2 refinement over Wilson gating.

---

## 2. Per-symbol edge / expectancy scorecard (§2 ★)

The headline ranking: *which tokens have a reliably positive EV per signal.*
**Win-rate ≠ EV** — fold in payoff. All over deduped, post-fix, finalized,
direction-normalized returns `r_i` per symbol.

| Metric | Formula | Reads as |
|---|---|---|
| **Expectancy (EV)** | winsorized `mean(r_i)` | avg return per signal (robust) |
| **Payoff ratio** | `mean(r⁺) / mean(\|r⁻\|)` | size of wins vs losses |
| **Profit factor** | `Σr⁺ / Σ\|r⁻\|` | >1 = net positive across all trades |
| **Expectancy in R** | `mean(r_i / risk_i)` | EV in units of risk taken |
| **SQN** (Van Tharp) | `mean(R) / std(R) · √n` (n capped 100) | quality = edge × consistency × sample |
| **Kelly fraction** | `p − (1−p)/b`, `b`=payoff | optional position sizing (use ½-Kelly) |

**Risk per trade `risk_i` (for R-multiples):** define it *at entry*, not from the
outcome. Cleanest is **ATR-based**: `risk_i = k · ATR_at_fire` (we already compute
ATR(14)). Avoid using the realized `|MAE_i|` as the denominator — that's
outcome-conditioned and inflates R artificially.

**SQN is the natural single score** here — it literally rewards "predictable
(low std) and good EV (high mean) with enough samples." Van Tharp bands: <1.6
poor, 1.6–2.0 average, 2.0–3.0 good, >3.0 excellent.

**Ranking rule:** sort by the **bootstrap-CI lower bound of EV** (conservative),
or by SQN; **gate** on min n (≈20 before any trust; show-but-grey below). Apply
§1c shrinkage if many symbols are thin. Carry the regime ⚠️ — and note that
ranking *many* symbols invites **selection bias** (the top of the list is partly
luck); the lower-CI-bound ordering + shrinkage mitigate it, but treat the leaders
as hypotheses, not winners.

Surfaces in the per-symbol panel (NEXT_STEPS §1; make it sortable). Backend: a new
`perf.by_symbol_scorecard()` that pulls per-symbol `r_i` arrays via the `perf`
CTE and runs them through the §0 stats.

---

## 3. Benchmark & skill metrics (§2 ★ benchmark column)

"Is there edge, or am I just long a rising market?"

- **Benchmark forward return:** in `update_outcomes`, fetch BTC candles once and
  store `bench_ret = BTC_close[t+N]/BTC_close[t] − 1` per signal window. Add a
  `benchmark_ret_*` column alongside `px_*`.
- **Alpha:** `edge = signal_ret − bench_ret` (direction-normalized). Rank/aggregate
  edge instead of raw return.
- **Direction nuance (important):** for a *bearish* signal, "beat long-BTC" is the
  wrong frame. The honest skill test is **vs a random-entry baseline of the same
  asset and direction mix**, or market-neutral (`asset_ret − bench_ret` for longs,
  `bench_ret − asset_ret` for shorts). Decide the baseline explicitly and write it
  down; an apples-to-oranges benchmark is worse than none.
- **Information Coefficient (IC):** the Spearman rank correlation
  (`scipy.stats.spearmanr`, §0) of signal strength vs forward return — does a
  *tighter* proximity / *deeper* histogram reduction predict a *bigger* move?
  Rank correlation is robust to outliers. In quant, |IC| ≳ 0.03–0.05 is already
  "something." This doubles as the threshold-tuning signal (§4).

---

## 4. Counterfactual loosening & threshold tuning (§2 + §4)

Answer "what if the threshold were looser/tighter?" with real returns.

- **Snapshot scoring:** generalize the scoring function so it scores *any*
  `(symbol, date, direction)` anchor, then run it over `asset_snapshots` (the
  assets that were *near* firing but didn't), not just fired `signals`. Store the
  outcomes (new columns/table). Now every candidate threshold has real forward
  returns behind it.
- **Parameter sweep:** grid the threshold (e.g. `price_pct_threshold ∈
  {0.001…0.01}`), compute EV + Wilson-lower-bound win-rate + count in each bucket
  (we already bucket in `perf.thresholds`). Pick the knee that maximizes
  lower-bound EV **subject to** acceptable volume.
- **Overfitting guards (do not skip):** coarse buckets, min-n per bucket, and
  ideally **out-of-sample / walk-forward** evaluation (fit threshold on an early
  window, test on a later one). With one regime, treat any "optimal" threshold as
  provisional. If we ever go rigorous: purged/embargoed CV and the
  deflated-Sharpe idea (López de Prado) guard against multiple-testing — almost
  certainly overkill here, noted for completeness.

---

## 5. Indicator — Stage 2: MACD deceleration (§4)

Earlier warning than Stage 1's histogram flattening: catch momentum *losing
steam* before the histogram even rolls over. Let `M_t` = MACD line.

- **Finite differences:** velocity `ΔM_t = M_t − M_{t-1}` (momentum), acceleration
  `Δ²M_t = ΔM_t − ΔM_{t-1}` (deceleration).
- **Bullish setup:** `M_t` falling (`ΔM_t < 0`) **but** `Δ²M_t > 0` for k
  consecutive bars → the decline is decelerating, momentum bottoming. Mirror
  (`ΔM_t > 0`, `Δ²M_t < 0`) for bearish.
- **Relation to Stage 1:** the histogram `H = M − signal` flattening (Stage 1)
  already captures convergence; Stage 2 reads curvature of `M` itself, which can
  turn a bar or two earlier.
- **Noise:** differencing amplifies noise, and daily bars give little data —
  **smooth first** (EMA the differences, or require k≥2–3 consecutive
  decelerating bars) and demand a minimum slope magnitude so flat noise doesn't
  trigger. We dropped Stage 2 earlier as low-impact; revisit only if outcome data
  shows S1 firing too late.

---

## 6. Patterns — alerting & ops (§4)

### 6a. Telegram dedup / state-change (the §4 unblocker)

A **state machine** keyed by `(symbol, stage, direction)`:

- **Store** (a `state/` SQLite table `alert_state`, or JSON): per key, the
  `last_fired_date`, last salient fields (`close`, `macd_pct`/`hist_reduction`,
  sign of hist), and `last_alerted_at`.
- **Emit when:** key unseen **or** `last_fired_date < today` (once-per-asset-day),
  **or** a real state change (direction flip, crossed a proximity band). Suppress
  re-fires that are unchanged within the day.
- **TTL/decay:** if a key hasn't fired for N days, drop it so a fresh re-fire
  later re-alerts (don't suppress forever).
- **Idempotency:** hashing the salient fields gives a cheap "did anything
  meaningful change?" check.
- **Guardrail:** state read/write is **best-effort** — wrap in try/except so a
  state glitch never blocks an alert or breaks the scan ([CLAUDE.md](../CLAUDE.md)).

### 6b. Health alerting — dead-man's switch (§4)

- **Self-hosted:** a watchdog cron reads `MAX(runs.started_at)`; if `now − last >
  threshold`, Telegram-ping. Simple, but **dies with the VM** (the case you most
  want to catch).
- **External (preferred):** ping a dead-man's-switch service (e.g.
  healthchecks.io) at the end of each scan; *it* alerts if a ping is missed.
  Survives total VM death. This is the standard "heartbeat / dead man's switch"
  pattern.

### 6c. Alert enrichment — closing the loop (§4 ★)

At fire time, look up the per-symbol stats (§2/§3) for `(symbol, stage,
direction)` and fold a one-liner into the Telegram message — median return,
typical drawdown (MAE p10 → stop), MFE median/p90 (→ target), R:R, n. **Call the
pure `perf.py` functions directly** (the scanner already holds a read-write DB
handle) rather than HTTP'ing the API. **Gate on min n** and on mature outcomes,
else omit the brief. Depends on 6a (same alert path).

---

## 7. Build order & where code lives

1. ✅ **scipy is a dependency** — use `scipy.stats` for Wilson / BCa bootstrap /
   Spearman (§0); `stats.py::summarize` stays for the quantile bundle. Unblocks
   the stats in §1–§4 (their first real scipy consumers).
2. ~ **`perf.by_symbol_scorecard()`** — shipped first cut: win-rate Wilson CI +
   EV BCa-bootstrap CI, ranked by the EV lower bound, in the per-symbol panel.
   Remaining: efficiency (R-multiples / SQN), payoff decomposition, shrinkage,
   sortable columns. *Quality matures with per-symbol n (slowest cut).*
3. **`update_outcomes` benchmark + snapshot scoring** (§3/§4) — schema change +
   re-score; the honest-edge unlock. *Needs mature outcomes.*
4. **Telegram dedup `state/`** (§6a) — **do-now, no data wait**; unblocks 6c.
5. **Health dead-man's switch** (§6b) — cheap insurance, do-now.
6. **Stage 2 indicator** (§5) — only if outcome data shows S1 fires too late.

Data-maturity gates 2–3; 4–5 are the immediately actionable builds.

## References (look-ups, not required reading)

- Wilson, *J. Am. Stat. Assoc.* 1927 — score interval for a proportion.
- Efron & Tibshirani, *An Introduction to the Bootstrap* — percentile/BCa CIs.
- Van Tharp, *Trade Your Way to Financial Freedom* — expectancy in R, SQN.
- Grinold & Kahn, *Active Portfolio Management* — Information Coefficient.
- López de Prado, *Advances in Financial Machine Learning* — purged CV,
  deflated Sharpe (rigor, if ever needed).
