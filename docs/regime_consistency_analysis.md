# Regime-consistency analysis — what actually survives?

Findings doc. Measured against `state/prod_snapshot.sqlite3` (2026-08-19 pull:
441 runs, 58,129 snapshots, 18,181 signals), **after** repairing the `px_14d`
bug documented in §5 — which nearly tripled the usable 14d sample and changed
several conclusions.

Question asked: *which token or signal type has performed consistently across
both regimes?*

**Headline: exactly one cohort survives — `crypto` + the shipped
`is_high_confidence` rule. No individual token does; per-symbol ranking is
worse than useless.**

## Method

Mirrors `web/perf.py::_base()` — deduped to one signal per (symbol, stage,
direction, UTC-day), direction-normalized, post-`DETECTOR_FIX_CUTOFF`,
`histogram_flattening` only. **3,833** signals scored at 7d, **3,459** at 14d,
across **186** symbols. Split at the median fire date: **H1 = 06-09→07-11**
(n=1,837), **H2 = 07-12→08-12** (n=1,996).

Two additions beyond the dashboard's own metrics:

- **Class-relative alpha** — the signal's direction-normalized move minus its
  *own asset class's* median move over the same window. `docs/research.md` §3
  specs this and it has never been built. It is the difference between edge and
  beta, and it is what separates the one real finding from the noise.
- **Both horizons.** Checking 7d and 14d on the same rows turned out to be the
  single most informative robustness test available (§1).

## 1. The regime effect is an artifact of holding period

Both halves were falling markets (median 7d-forward across kept assets: H1
−0.52%, H2 −0.28%), so this was never a bull/bear flip. At 7d the strategy
looks like it worked in H1 and broke in H2. **Score the exact same rows at 14d
and the sign flips both ways:**

| same rows | @7d win | @7d EV | @14d win | @14d EV |
|---|---|---|---|---|
| H1 (n=1,837) | 55.4% | **+0.80%** | 45.2% | **−1.00%** |
| H2 (n=1,622) | 46.9% | **−0.66%** | 50.8% | **+0.34%** |

Identical signals. The only thing that changed is how long you'd have held.
Whatever "H1 was a good regime" meant, it does not survive a one-week change in
exit timing — so it should not be read as a property of the market regime at
all. Overall alpha across the whole dataset is **−0.65%**: versus taking the
same directional exposure at random, the detector is behind.

## 2. No token persists — and ranking by past winners is actively harmful

121 symbols have ≥6 signals in both halves. 29 are EV-positive in both, which
sounds promising until you permute:

> **Permutation null (400 shuffles): expected passers 28.8 (median 29, p90 33).
> Observed 29. Empirical p = 0.527.**

Exactly what chance produces. Direct persistence tests agree, at both horizons:

| horizon | EV ρ | p | win-rate ρ | p |
|---|---|---|---|---|
| 7d (121 symbols) | +0.002 | 0.981 | −0.096 | 0.294 |
| 14d (115 symbols) | −0.035 | 0.714 | **−0.196** | **0.036** |

Zero on EV, and at 14d the win-rate correlation is *significantly negative* —
last period's winners are mildly **worse** than random next period. Sorting
symbols by H1 EV shows the collapse: a 14pp H1 spread (Q1 −6.82%, Q4 +7.25%)
lands at Q1 −1.34% vs Q4 −0.46% in H2, with the best quartile still negative.

Names topping the both-halves screen (ZRO +8.4%, LIT +7.8%, ZEC +7.4%) are
survivorship artifacts. **The Scorecard tab's ordering carries no forward
information.**

## 3. The one survivor: crypto × high-confidence bearish

`signals.py::is_high_confidence` (bearish ∧ `reduction<0.6` ∧ `top_n≥3` ∧
`peak_pct<40`) already exists and bolds Telegram rows. Applied across all
classes it **fails** the regime test. Restricted to **crypto** it is the only
cohort found that is positive in every half × horizon cell — including on alpha,
and including the horizon flip that inverts everything else in §1:

| | n | win | Wilson 95% | EV | alpha |
|---|---|---|---|---|---|
| 7d H1 | 177 | 70.6% | [63.5–76.8] | +3.05% | +0.48% |
| 7d H2 | 165 | 67.3% | [59.8–74.0] | +2.07% | +0.34% |
| 14d H1 | 177 | 65.0% | [57.7–71.6] | +1.43% | +0.48% |
| 14d H2 | 137 | 70.8% | [62.7–77.8] | +4.84% | +0.84% |

Every Wilson lower bound is comfortably above 50%. Alpha is positive in all
four cells and strikingly stable (+0.34% to +0.84%).

What else holds up:
- **Not concentrated** — 72 distinct symbols, top-5 = 21% of signals.
  Leave-one-symbol-out alpha stays in +0.274%…+0.776%, never flips sign.
- **Not one lucky week** — dropping the best week (06-15/21, 93.6% win) leaves
  win 65.2%, EV +1.75%, alpha +0.42% (essentially unchanged).
- **Beats its own control** — vs other crypto-bearish signals: Mann-Whitney
  p=0.0000 (H1), p=0.0173 (H2). vs 5,000 random same-size crypto-bearish
  subsamples: EV p=0.0000, alpha p=0.0026.
- **Coherent across horizons** — 1d +0.60%, 3d +1.67%, 7d +2.62%, 14d +2.59%.
- **Tradeable cadence** — median 32 signals/week.

### Three reasons to still hold it loosely

1. **Alpha's CI includes zero in every cell** (pooled +0.45% [−0.41, +1.26]).
   The headline +2.6% is mostly beta — shorting a falling crypto market. The
   skill component is real-looking but not statistically established.
2. **The genuine out-of-sample window does not confirm it.** The rule was fitted
   on the earlier 08-06 snapshot, so signals fired ≥07-30 are effectively
   unseen: n=38, win 50.0% [34.8–65.2], EV +0.01%, alpha −0.54%. Far too small
   to refute — and far too small to reassure.
3. **In-sample by construction.** `peak_pct<40` was derived from this dataset
   (`hist_peak_context.md`). The crypto restriction found here is a *further*
   in-sample cut. Both-halves consistency is a robustness check, not validation.

## 4. Robust negative: equity, and alpha is the honest lens

Equity's raw return is horizon-dependent — bad at 7d, roughly flat at 14d — but
**alpha is negative in all four cells**, tightly clustered:

| | n | win | EV | **alpha** |
|---|---|---|---|---|
| 7d H1 | 488 | 47.1% | −1.12% | **−0.79%** |
| 7d H2 | 637 | 45.7% | −1.66% | **−1.64%** |
| 14d H1 | 488 | 48.0% | −1.17% | **−0.79%** |
| 14d H2 | 517 | 51.6% | +0.52% | **−0.75%** |

Note the 14d-H2 row: raw EV +0.52% looks fine, alpha −0.75% says the assets
merely rose with their class. Judged on raw return you would keep trading
equities; judged on alpha you would not. This confirms the earlier 605-signal
observation and shows it is not a regime artifact — but the claim should be
made in alpha, not EV.

## 5. Bug found and fixed: `px_14d` was missing for 100% of 00:00-UTC signals

Found while checking horizon coverage. Among **finalized** signals px_1d/3d/7d
were ~100% present but **px_14d only 31.8%**, uniform across every class and
month — which ruled out trading calendars. By fire hour it was total:

| fire hour (UTC) | finalized n | had px_14d |
|---|---|---|
| **00** | 2,356 | **0 (0.0%)** |
| 04 / 08 / 12 / 16 / 20 | 1,102 | 99.6–100% |

**Mechanism.** A signal fired at 00:00 UTC crosses the 14-day threshold at 00:00
on day+14. The outcomes cron runs 01:30 that same morning, sees
`now − fired = 14.06d ≥ 14`, and finalizes it — but at 01:30 the day+14 bar is
still *forming*, and `_score_symbol` drops the forming bar before scoring. So
`px_14d` was never written, and `fetch_pending_signals` never revisits a
finalized row. The finalize-lag column was a perfect discriminator: every
missing row finalized at exactly 14.06d, every present row at 14.23–14.90d.

**Why it mattered disproportionately:** `_base()` dedups by `MIN(fired_at)` per
day, which preferentially keeps the 00:00 run — 68% of the deduped analysis set,
versus an even ~2,900/hour in the raw table. The dashboard's 14d column was
computed on a biased ~32% subsample that systematically *excluded* the
post-00:00-UTC closed-bar read PLAN.md §12 calls "the principled keeper."

**Fix (shipped).** `score_signal` now finalizes at `horizon_days + 1`, which
guarantees the horizon bar has closed regardless of fire hour or cron time.
Pinned by `test_finalize_waits_for_the_horizon_bar_to_close`, which asserts a
signal is *not* finalized at the timing that used to lose the column (14 days +
90 minutes) and *is* a day later.

**Repair result on the local snapshot:** hour-0 coverage 0% → 79.7%, broken rows
2,554 → 54, deduped 14d sample 1,100 → 3,459. (The 54 residual are assets that
genuinely did not trade on `fire_date + 14`; the ~20% hour-0 gap is signals too
recent to have matured.)

### Runbook — repairing the live VM DB

Idempotent and non-destructive: only re-opens rows provably missing the column.

```bash
ssh <your-vm> && cd ~/macd_searcher

# 1. Back up (WAL-safe; a plain cp can miss the -wal file).
.venv/bin/python -c "import sqlite3; s=sqlite3.connect('state/macd_searcher.sqlite3'); d=sqlite3.connect('state/macd_searcher.backup.sqlite3'); s.backup(d); d.close(); s.close(); print('backup ok')"

# 2. Deploy the fix.
git pull && uv sync --extra web

# 3. Re-open the frozen rows.
.venv/bin/python -c "
import sqlite3
c = sqlite3.connect('state/macd_searcher.sqlite3')
n = c.execute('UPDATE signals SET outcome_updated_at=NULL WHERE outcome_updated_at IS NOT NULL AND px_14d IS NULL').rowcount
c.commit(); print('re-opened', n)"

# 4. Re-score. Several minutes (one candle fetch per symbol, ~190 symbols).
#    Run away from the crons (scan 0 */4, outcomes 01:30 UTC). Safe to re-run
#    if interrupted — it commits per symbol and picks up where it left off.
.venv/bin/python -m macd_searcher.update_outcomes

# 5. Verify.
.venv/bin/python -c "
import sqlite3
c = sqlite3.connect('file:state/macd_searcher.sqlite3?mode=ro', uri=True)
f = c.execute('SELECT COUNT(*) FROM signals WHERE outcome_updated_at IS NOT NULL').fetchone()[0]
g = c.execute('SELECT COUNT(*) FROM signals WHERE outcome_updated_at IS NOT NULL AND px_14d IS NOT NULL').fetchone()[0]
print(f'{g}/{f} finalized rows have px_14d ({g/f*100:.1f}%)')"
```

Rollback: `mv state/macd_searcher.backup.sqlite3 state/macd_searcher.sqlite3`.

## What I'd do with this

1. **Run the §5 repair on the VM.** The dashboard's 14d column is currently
   wrong there in the way described above.
2. **Build `alpha_cls` into `perf.py` as a first-class metric.** It is what
   separated the one real finding from four spurious ones, and it flips the
   equity read at 14d. `docs/research.md` §3 already specs it.
3. **Add `asset_class = 'crypto'` to the confidence rule.** It is the difference
   between a rule that survives every half × horizon cell and one that doesn't.
   Treat as a hypothesis under test.
4. **Drop or de-weight equity signals** — negative alpha in all four cells.
5. **Stop ranking by per-symbol EV**, or relabel the Scorecard. ρ≈0 on EV and
   significantly negative on 14d win-rate: the ordering is anti-predictive.

## Caveats

- ~10 weeks, two halves of the *same* broadly-falling market. "Both regimes"
  means two adjacent down-market periods, not a genuine regime change. §1 shows
  even that split is fragile.
- Many looks at one dataset: classes × directions × confidence × several bucket
  dimensions × two horizons. Permutation and randomization tests guard the
  headline claims; the crypto-confident cell is the survivor of a wide search
  and should be read as a hypothesis, not a result.
- Class benchmark is the median move of kept assets in that class per day — a
  breadth proxy, not an index.
- H2's 14d rows cover fire days only through 08-05 (82% of the half); the rest
  had not matured. §1's reversal is not a truncation artifact — H1 is 100%
  covered and flips just as hard.
