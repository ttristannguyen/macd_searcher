# Next steps

Forward roadmap for macd_searcher. Companion to [PLAN.md](PLAN.md) (backend) and [FRONTEND_PLAN.md](FRONTEND_PLAN.md) (dashboard). Living document — check items off as they land.

> **Scope reminder:** this is a discretionary **signalling aid** ("flag good catches"), not a quantitative edge engine. Treat outcome data as a *loose sanity gauge*; the statistical-rigor items only matter if you later decide to quantify edge.

---

## 1. Frontend — Outcomes / Performance tab
- [ ] New `/api/perf/*` endpoints wrapping `docs/queries.sql` E–I: win-rate & return by stage×direction, return-by-horizon, lead-time (S1 vs S3), threshold buckets, MFE/MAE, per-symbol.
- [ ] A second tab/page rendering those, with an **"accumulating data…"** state until outcomes mature (~1–2 weeks).
- [ ] Bake in the corrections: filter to post-fix signals via `runs.code_version`, and **dedup per asset-day** so same-day repeats don't inflate stats.
- [ ] Carry-overs: sortable tables (order-bys), asset-class / symbol-search filters, Recharts label casing (by-class axis, dispatch legend, health "Dispatch" value).

## 2. Analysis & outcome engine
- [ ] ★ **Benchmark column** in `update_outcomes` — forward return vs buy-and-hold (or BTC) over the same window. The honest "is there edge" test.
- [ ] **Counterfactual loosening** — score `asset_snapshots` (not just fired signals) so "what if thresholds were looser?" is answerable with real returns. Needs outcome storage on snapshots + generalized scoring.
- [ ] Decide the **`compute_asset_metrics` peak** question — keep as the raw 10-bar window (analysis substrate) or align to the detector's new same-sign excursion.
- [ ] Small **Python analysis script/notebook** for medians + binomial confidence intervals (SQLite lacks `MEDIAN`; means are outlier-skewed).
- ⚠️ **Regime caveat:** current data is one market regime — note it in any analysis.

## 3. Permanent uptime / hosting
- [ ] **Service uptime (do first):** run the API as a **systemd service** on the VM (auto-start, restart-on-failure, survives reboot), bound to `127.0.0.1`. Confirm the scan + `update_outcomes` crons are healthy.
- [ ] **Access anywhere without opening ports** (pick one):
  - **Tailscale** — private mesh VPN; reach the VM service from any device, nothing public. Simplest for personal multi-device.
  - **Cloudflare Tunnel** — exposes localhost:8000 via Cloudflare with optional Access login; no open ports, free.
  - **Caddy reverse proxy + Let's Encrypt + basic auth** — a real public HTTPS site, but opens 443 and needs a domain.
- Note: local-machine hosting (Task Scheduler at logon) only runs while your PC is on — the VM is the better "permanent" home since the data already lives there.
- [ ] Frontend deploy mechanics (FRONTEND_PLAN commit 6): build locally → ship `dist` (scp) or build on VM; or commit `dist` for pure `git pull` deploys.

## 4. Signal quality, tuning & ops
- [ ] **Telegram noise control** — dedup alerts (once per asset-day, or on state-change) via the deferred `state/` file.
- [ ] **Threshold tuning loop** — feed outcome findings back into `config.yaml`; consider per-asset-class thresholds.
- [ ] **DB backups** — DO weekly backups or a scheduled `scp` of the SQLite file (the one irreplaceable asset).
- [ ] **Health alerting** — Telegram ping if no scan has run in > X hours (cron died).
- [ ] **CI** — GitHub Actions running `pytest` on push.
- [ ] Optional: revisit **Stage 2 (MACD deceleration)**; **universe expansion** (spot / more HIP-3 DEXes).

---

## Suggested sequence
1. **systemd service + Tailscale/Cloudflare** → a permanent, reachable dashboard now.
2. **`/api/perf/*` + Outcomes tab** (with `code_version` filter + asset-day dedup) → ready for when data matures.
3. **Benchmark column** → unlocks the honest effectiveness read.
4. **Telegram dedup, backups, CI** → polish.
