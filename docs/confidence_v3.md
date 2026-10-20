# Confidence rule v3 — `peak_pct`, shadow-run against v2

Working doc + plan + progress tracker. Evidence lives in
[confidence_v3_research.md](confidence_v3_research.md); method in
[research_method.md](research_method.md). This doc is what we build, and why the
rule should work.

## The rule

```
confident  =  bullish AND peak_pct <= 50 AND reduction_from_peak < 0.6
warning    =  bullish AND peak_pct = 100            (record trough — shown, not gated)
shadow     =  bearish AND peak_pct <= 25            (tracked only)
```

`peak_pct` is `fire_hist_peak_pct`: where this excursion's histogram extreme ranks
among the token's own completed excursions of the same sign in the ~200-bar window
(`signals._peak_vs_history`). 100 = the deepest selling-momentum swing in that window.

## Why v3 works

Measured on 964 bullish episodes (first fire of each, 7d alpha vs the same-run class
mean, week-block intervals):

```
peak_pct       alpha 7d              pre-fire vs class (14d)   breaks 30d low   crosses zero ≤7d
0–25          +1.38 [-0.37,+3.18]          -2.40%                  26.2%             41.0%
25–50         +0.63 [-0.48,+1.88]          -3.19%                  23.7%             55.4%
50–75         +0.11 [-1.88,+2.22]          -4.34%                  20.2%             53.1%
75–<100       -2.01 [-4.05,-1.05]          -4.44%                  30.8%             45.0%
100 (record)  -3.99 [-7.56,-0.65]         -10.41%                  34.2%             44.1%
```

**A record trough is usually a token-specific collapse, and those keep drifting.**
The `peak_pct = 100` episodes had underperformed their own class by a median 10.4%
over the 14 days before the fire — two to four times the other bands. That is the
signature of something happening *to this token* (an unlock, an exploit, a delisting
rumour, a bad earnings print), not to the market. The evidence that this is the
mechanism, rather than a coincidence:

1. **The penalty concentrates where the drop was idiosyncratic.** Split by how far the
   asset fell relative to its class before the fire, record troughs return −5.28% when
   the fall was token-specific and −0.45% when the asset merely fell with its class
   (a market-wide sell-off, which reverts with the market).`
2. **They break down further.** 34% of record-trough episodes trade below their prior
   30-day low within a week, against 26% for the lowest band.
3. **It is a drift, not an overshoot.** Record-trough alpha goes −1.0 → −1.5 → −4.0%
   over 1 / 3 / 7 days; the low band goes +0.6 → +1.2 → +1.4 → +1.9% out to 14d. An
   overshoot would snap back in a day or two.
4. **The histogram knows something the price does not.** Pre-fire relative weakness
   on its own has no predictive power (IC +0.03 [−0.06, +0.11]); in a joint rank
   regression `peak_pct` keeps its whole effect (−0.138) and relative weakness adds
   nothing (+0.005). What matters is not *that* the token fell, but that it fell
   faster than it ever has in its own recent history.

So the detector's reading — "the histogram is flattening, selling is exhausting" — is
right for an ordinary swing and wrong for an unprecedented one. After a record
acceleration, a flattening histogram is the decline slowing from extreme to merely
fast; the information that caused it is still being priced. A modest trough is the
token's normal rhythm, carries no news, and mean-reverts against its peers.

This matches a known pattern in markets — moves driven by information continue,
moves without it reverse — but we cannot observe news directly, so treat that as the
most plausible explanation, not a measured fact.

**What v3 is *not* exploiting:** v2's mechanism. Zero-cross completion is not monotone
in `peak_pct`, and the best band (0–25) completes *least* often (41%). v3 and v2
measure different things.

**Where the edge actually sits.** Most of the slope comes from the *bottom* of the
table: the low band's +1.38% has a CI that includes zero at episode level, while the
two top bands are clearly negative. v3 works mainly by **excluding** the near-record
and record troughs that v2 and plain bullish include. That is why the warning ships
first and the confident marker is shadow-run.

## Decisions

- **Shadow before switching.** v3 is computed and shown on the Confidence tab beside
  v2; Telegram bolding stays on v2 until the watchlist (`research/rules.py`) confirms
  v3 out of sample. Promotion criteria are below — written before the data exists.
- **Thresholds live in `signals.py`**, beside v2's, and are imported by `perf.py` and
  `research/rules.py` — one home, as with v2.
- **Dashboard alpha uses snapshot exits** (DB-only, ~2.4s per request). That benchmark
  drops assets that fall out of the liquidity filter, biasing alpha against bullish
  signals by about 0.2pp. Acceptable for monitoring; the panel says so, and the
  research report (candle exits) stays authoritative.
- **Episodes counted with the research definition** (re-fire within 1 day continues an
  episode), implemented once in `stats.py` and shared.

## Progress checklist

### Phase 0 — Research tooling ✅
- [x] `python -m macd_searcher.research` pipeline, method doc, 18 tests (commit `62f5578`).

### Phase 1 — Mechanism ✅
- [x] Measured above; recorded in the findings doc §4.

### Phase 2 — Shadow v3 on the Confidence tab ✅
- [x] `signals.py`: `CONFIDENCE_V3_*` thresholds + `is_v3_confident(s)` and
      `is_record_peak(s)`; `research/rules.py` imports them.
- [x] `stats.py`: `block_ci` and `episodes` moved here (pure); research and
      `perf.py` share them.
- [x] `perf.py`: same-run class benchmark; `confidence_compare(conn, horizon, classes)`
      → per rule (v2 live, v3 shadow, bearish shadow, record warning, everything): n,
      episodes, win, raw EV, market move, alpha with an episode-level week-block CI,
      and alpha by month.
      *Deviation:* the benchmark and the flagged rows are two queries joined in Python,
      not one SQL join. As one join, SQLite's planner took 60s+ with a class filter
      (2.4s without); as two queries it is 2.2–2.6s for every filter.
- [x] `models.py` / `app.py`: `GET /api/perf/confidence-compare`.
- [x] Frontend: `RuleComparison` panel at the top of the Confidence tab — raw EV split
      into market + alpha, episodes beside n, alpha by month, the survivorship caveat.
      CI coloured only when it excludes zero; `n` and win hide on phones so alpha stays
      on screen.
- [x] Tests (5): Python↔SQL agreement for the v3 and record predicates;
      `raw = market + alpha` for both directions on a fixture where the benchmark is
      exactly +10%; episodes < n for a repeat fire; alpha by month; no benchmark below
      10 same-class symbols.

### Phase 3 — Record-trough warning ✅
- [x] Telegram row: bullish rows with `peak_pct = 100` end in `⚠ record` (still sent).
- [x] `SignalsFeed`: Peak cell amber with ⚠ and a verdict tooltip for record troughs;
      bullish modest troughs say they are the v3 side. `AssetSignalsTable`: same marker
      on the Pct column.
- [x] Tests (4): warned for bullish p100 only — not p87.5, not missing context, not bearish.

### Verification (2026-10-14)
- [x] `uv run pytest -q` — 199 passed. `npm --prefix frontend run build` — clean.
- [x] Real uvicorn server against `prod_snapshot`: `/api/perf/confidence-compare` 200
      for 3d/7d/14d and every class filter, 2.2–2.6s each.
- [x] Rendered in headless Edge at 1440px and 420px and inspected. Two fixes from the
      look: CI bounds to 2 decimals (the record row read `[-5.5, -0.0]`, which looks
      like it touches zero — it is −0.04), and the phone layout above. The page already
      overflows horizontally at 420px because of the header nav — pre-existing, not
      this panel, which scrolls inside its card.
- [x] Dashboard vs report: v3 alpha +0.66% (snapshot exits) vs +0.83% (candle exits) —
      the documented ~0.2pp survivorship gap, in the documented direction.

**Watchlist baseline, first pass (snapshot 2026-10-14):** v3 bullish undecided
(45 OOS episodes, +0.91% [−2.06, +3.05]); bearish shadow undecided; record warning
pending at 22 episodes (−5.52% so far); v2 pending at 11.

**Pass 2026-10-18 (snapshot through 2026-10-17 12:00):** every check is scored only
from its registration date now, and none has an outcome yet (first ~2026-10-22).
For orientation only, since 2026-09-19: v3 bullish +0.41% [−2.38, +3.04] (48 ep),
record warning −4.84% [−6.66, −3.38] (24 ep).

### Phase 4 — Promotion (gated — do not start before the criteria hold)
- [ ] Criteria: the watchlist's v3 bullish check reads **confirmed** (≥ 30
      out-of-sample episodes, alpha CI above zero) on two consecutive passes.
- [ ] `fire_confidence_rule` version column, written at fire time, *before* switching.
- [ ] Switch `is_high_confidence` to v3; update tab copy; move `DEFAULT_OOS_FROM`.

### Later
- Log pre-filter universe prices each scan, so snapshot exits stop dropping assets
  that leave the liquidity filter — removes the dashboard's survivorship bias going
  forward.
- Re-test the out-of-sample funding effect (findings §8) once the market turns.
