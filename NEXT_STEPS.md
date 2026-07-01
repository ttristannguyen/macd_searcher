# Next steps

Forward roadmap for macd_searcher. Companion to [PLAN.md](PLAN.md) (backend) and [FRONTEND_PLAN.md](FRONTEND_PLAN.md) (dashboard). Living document — check items off as they land.

> **How to build the §2/§4 analysis items:** [docs/research.md](docs/research.md) maps each to concrete algorithms, formulas, indicators, and stack-specific implementation notes (Wilson CIs, bootstrap, expectancy/SQN, MACD deceleration, dedup state machine, dead-man's switch…).

> **Scope reminder:** this is a discretionary **signalling aid** ("flag good catches"), not a quantitative edge engine. Treat outcome data as a *loose sanity gauge*; the statistical-rigor items only matter if you later decide to quantify edge.

---

## 1. Frontend — Outcomes / Performance tab
- [x] New `/api/perf/*` endpoints wrapping `docs/queries.sql` E–I: readiness, win-rate & return by stage×direction, return-by-horizon, lead-time (S1 vs S3), MFE/MAE, per-symbol, by-class, threshold buckets. (`web/perf.py`; tests in `tests/test_web_perf.py`.)
- [x] A second tab/page rendering those (`pages/Outcomes.tsx`, `components/Outcomes.tsx`), with an **"accumulating data…"** readiness banner until outcomes mature (~1–2 weeks).
- [x] **Dedup per asset-day** baked into every perf query (earliest fire per symbol/stage/direction/UTC-day).
- [x] Post-fix filtering: hard-wired to `DETECTOR_FIX_CUTOFF` in `web/perf.py` (pre-fix Stage-1 data is simply excluded from every perf query — no UI knob, per KISS).
- [x] **by-class** (win/EV by asset class × stage) and **threshold buckets** (win/EV by proximity/reduction bucket, with a kind toggle) rendered on the Outcomes tab (`ByClass`, `Thresholds`).
- [ ] Carry-overs: **sortable** tables (order-bys), asset-class / symbol-search filters, Recharts label casing (by-class axis, dispatch legend, health "Dispatch" value).

## 2. Analysis & outcome engine
- [ ] ★ **Benchmark column** in `update_outcomes` — forward return vs buy-and-hold (or BTC) over the same window. The honest "is there edge" test.
- [~] **Counterfactual loosening** — score `asset_snapshots` (not just fired signals) so "what if thresholds were looser?" is answerable with real returns. *(S1/reduction first cut shipped: `/api/perf/reduction-counterfactual` + the Reduction-counterfactual panel — self-join forward returns from stored closes, extending the reduction buckets below the 0.3 fire threshold. EV/win faithful; drawdown is a close-based proxy. Still open: bar-based true MAE, and the Stage-3 proximity counterfactual.)*
- [x] Decide the **`compute_asset_metrics` peak** question — **aligned to the detector's same-sign excursion** (shared `_excursion_peak` in `signals.py`), so a snapshot's `hist_reduction_from_peak` matches what would have fired. Counterfactual snapshots are counted only from `SNAPSHOT_FIX_CUTOFF` onward (pre-fix used the old raw-window peak).
- [ ] Small **Python analysis script/notebook** for medians + binomial confidence intervals (SQLite lacks `MEDIAN`; means are outlier-skewed).
- [~] ★ **Per-symbol edge / expectancy scorecard** — rank tokens by *reliably positive expected value* per signal (long or short, per the fired direction). **Key insight: win-rate alone ≠ EV** — 40% winners can beat 70% if the winners are bigger, so rank by expectancy, not hit-rate. *(First cut shipped: `/api/perf/scorecard` + the per-symbol panel.)*
  - [x] **Expectancy (EV)** — mean direction-normalized return per signal (the EV *is* the mean; the CI carries the skew).
  - [x] **Reliability** — win-rate **Wilson CI** + EV **BCa-bootstrap CI** (scipy), **ranked by the EV lower bound** so small-n/outliers can't fake an edge. Gated on min n; rendered in the per-symbol panel.
  - [ ] **Efficiency = risk-adjusted EV** — EV per unit risk: expectancy ÷ |median MAE|, per-trade R-multiples (`r / k·ATR`), and/or EV ÷ std (per-signal Sharpe) / **SQN**.
  - [ ] **Decomposition (intuition)** — payoff ratio (avg win / |avg loss|) alongside win-rate: edge from being right often vs rare big winners.
  - [ ] **Shrinkage** — empirical-Bayes (Beta–Binomial) for very thin symbols; **sortable** columns.
  - ⚠️ per-symbol n is small and matures slowly — a loose gauge; see the regime caveat below. (Liquidity / executability is a separate future filter, not part of this edge metric.)
- ⚠️ **Regime caveat:** current data is one market regime — note it in any analysis.

## 3. Permanent uptime / hosting
- [x] **Service uptime:** API runs as a **systemd service** on the VM (`deploy/macd-searcher-web.service`) — auto-start, restart-on-failure, survives reboot, bound to `127.0.0.1`. Still TODO: confirm the scan + `update_outcomes` crons are healthy.
- [ ] **Access anywhere without opening ports** (pick one):
  - **Tailscale** — private mesh VPN; reach the VM service from any device, nothing public. Simplest for personal multi-device.
  - **Cloudflare Tunnel** — exposes localhost:8000 via Cloudflare with optional Access login; no open ports, free.
  - **Caddy reverse proxy + Let's Encrypt + basic auth** — a real public HTTPS site, but opens 443 and needs a domain.
- Note: local-machine hosting (Task Scheduler at logon) only runs while your PC is on — the VM is the better "permanent" home since the data already lives there.
- [ ] Frontend deploy mechanics (FRONTEND_PLAN commit 6): build locally → ship `dist` (scp) or build on VM; or commit `dist` for pure `git pull` deploys.

## 4. Signal quality, tuning & ops
- [ ] **Telegram noise control** — dedup alerts (once per asset-day, or on state-change) via the deferred `state/` file.
- [ ] ★ **Close the loop — enrich alerts with outcome stats.** Fold a one-line historical brief into the Telegram message so the alert itself carries the decision context that currently only lives in the Outcomes tab. E.g. `BTC bullish S1 — median +X% / typical drawdown −Y% / R:R 1.8×, n=22`, with a suggested stop (MAE p10) and target (MFE median/p90). Reuses the `/api/perf/*` stats (per-symbol win-rate, return distribution, MFE/MAE → R:R). Turns "something's happening" into "here's what these usually do and where to put a stop." *Depends on:* the `state/` dedup work (same alert path) **and** mature post-fix outcomes (~1–2 weeks of finalized data) so the numbers aren't noise. Gate the brief behind a minimum n.
- [ ] **Threshold tuning loop** — feed outcome findings back into `config.yaml`; consider per-asset-class thresholds.
- [ ] **DB backups** — DO weekly bac  kups or a scheduled `scp` of the SQLite file (the one irreplaceable asset).
- [ ] **Health alerting** — Telegram ping if no scan has run in > X hours (cron died).
- [ ] **CI** — GitHub Actions running `pytest` on push.
- [ ] Optional: revisit **Stage 2 (MACD deceleration)**; **universe expansion** (spot / more HIP-3 DEXes).

---

## Suggested sequence
1. **systemd service + Tailscale/Cloudflare** → a permanent, reachable dashboard now.
2. **`/api/perf/*` + Outcomes tab** (with `code_version` filter + asset-day dedup) → ready for when data matures.
3. **Benchmark column** → unlocks the honest effectiveness read.
4. **Telegram dedup, backups, CI** → polish.
