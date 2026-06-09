# Frontend Plan — macd_searcher dashboard

A web dashboard to monitor the scanner and explore its findings. Companion to the backend [PLAN.md](PLAN.md); reads the same SQLite DB. This is a living document — items get checked off and amended as we build.

---

## 1. Decisions (from requirements Q&A)

| Area | Decision |
|---|---|
| Stack | **FastAPI (JSON API) + React + TypeScript (Vite)**. Chosen over Streamlit for design control, a reusable API, and because it's the stack the user wants to build in. |
| Hosting | Runs on the VPS **bound to `127.0.0.1` only** (no public exposure, UFW unchanged); accessed from the PC via **SSH local port-forward**. Developed locally first. |
| Data access | **Read-only** SQLite connection (`mode=ro`). The dashboard never writes; WAL lets it read safely while the scanner writes. |
| MVP scope | **Operational health + latest-signals feed + signal composition** — everything answerable from day-one data (queries.sql sections B, C, J). Performance analytics (E–I) deferred to Phase 2 until outcomes mature. |
| Look & feel | **Dark, desktop-first, responsive.** Dense data layout tuned for a monitor, still usable on a phone. |

---

## 2. Architecture

```
        your PC                     SSH tunnel                 VPS (localhost only)
┌───────────────────────┐      ssh -L 8000:…           ┌──────────────────────────────┐
│ browser → localhost:8000│ ───────────────────────────▶│ FastAPI (uvicorn) 127.0.0.1:8000│
└───────────────────────┘                              │   ├── /api/*  → JSON          │
                                                        │   └── /      → React dist/    │
                                                        │            │ read-only        │
                                                        │            ▼                  │
                                                        │   state/macd_searcher.sqlite3 │
                                                        └──────────────────────────────┘
```

- **One process, one port:** FastAPI serves both the JSON API (`/api/*`) and the built React static files (`/`). Simplest to tunnel and deploy.
- **Dev mode** differs: Vite dev server (`:5173`) with hot reload proxies `/api` to FastAPI (`:8000`). No CORS needed.

---

## 3. Repo layout (additions)

```
macd_searcher/
├── src/macd_searcher/
│   └── web/                     ← new: the API (reuses config for DB path)
│       ├── __init__.py
│       ├── app.py               ← FastAPI app, static mount, localhost bind
│       ├── db.py                ← read-only connection helper
│       ├── queries.py           ← parametrized SQL (the queries.sql logic)
│       └── models.py            ← pydantic response models (typed API)
├── frontend/                    ← new: Vite + React + TS
│   ├── index.html
│   ├── package.json
│   ├── vite.config.ts           ← dev proxy /api → :8000
│   ├── tailwind.config.ts
│   └── src/
│       ├── main.tsx, App.tsx
│       ├── api/                 ← typed fetch hooks (TanStack Query)
│       ├── components/          ← HealthBanner, RunsTable, SignalsFeed, charts…
│       └── pages/Dashboard.tsx
│       └── dist/                ← build output, served by FastAPI (gitignored or shipped)
└── pyproject.toml               ← add optional `web` extra: fastapi, uvicorn[standard]
```

`web` deps go in an **optional extra** so the core scanner install stays lean:
`uv sync --extra web` only on machines that run the dashboard.

---

## 4. Backend — API endpoints (MVP)

Thin, read-only JSON wrappers over the immediate queries. All return typed pydantic models.

| Endpoint | Maps to | Returns |
|---|---|---|
| `GET /api/health` | B1 + B2(top) | Row counts, latest run (time, notify_status, universe kept, signals_count, duration) + a derived status (`ok`/`stale`/`down`) from last-run age vs the 4h cadence. |
| `GET /api/runs?limit=20` | B2 | Recent runs. |
| `GET /api/stats/runs-per-day?days=14` | B4 | Cadence (bar chart). |
| `GET /api/stats/notify-status` | B3 | Dispatch breakdown (donut). |
| `GET /api/signals/recent?limit=50` | feed | Latest signals + `asset_class` (joined), stage, direction, fire metrics. |
| `GET /api/stats/by-stage-direction` | C1 | Counts (grouped bars). |
| `GET /api/stats/by-class` | C2 | Counts by asset class. |
| `GET /api/stats/top-symbols?limit=20` | C3 | Most active symbols. |
| `GET /api/stats/signals-per-day?days=14` | C4 | Volume over time (line). |
| `GET /api/stats/proximity-headroom` | J1 | Avg assets/run within 0.2/0.5/1% of zero — "alert headroom". |

**Deferred to Phase 2** (outcomes-dependent): `GET /api/perf/*` for win-rate, returns-by-horizon, lead-time, threshold buckets, MFE/MAE, per-symbol (E–I). The panels will render an "accumulating data…" state until populated.

Good practices: read-only DB URI; DB path from `macd_searcher.config`; pydantic models so the API is self-documenting (FastAPI `/docs` Swagger UI for free); pytest with FastAPI `TestClient` against a fixture DB.

---

## 5. Frontend — stack & layout

- **Vite + React + TypeScript** — fast dev, typed.
- **Tailwind CSS** — rapid dark/dense theming (optionally `shadcn/ui` later for polished components).
- **TanStack Query (react-query)** — data fetching with auto-refresh/polling (e.g. health every 30s, rest every 60s) + caching + loading/error states.
- **Recharts** — bar/line/donut for the stats (swappable; lightweight, composable).

**MVP single-page dashboard (top → bottom):**
1. **Health banner** — big status pill (green `ok` / amber `stale` / red `down`), last-run time + "next expected", universe kept, signals last run.
2. **Cadence + recent runs** — runs/day bar chart beside the last-10-runs table (notify_status colored).
3. **Notify-status** donut.
4. **Signals feed** — latest signals table: time, symbol, asset-class badge, stage badge, direction (green/red), key metric (proximity or reduction).
5. **Composition** — stage×direction grouped bars, by-asset-class bars, signals/day line.
6. **Alert headroom** — the proximity-band stat (small KPI cards).

Responsive: multi-column on desktop, stacks to one column on narrow screens.

---

## 6. Running it

**Local development (now):**
```bash
uv sync --extra web
# point the API at a copy of the DB (scp it down, or use the local state/ DB)
uv run uvicorn macd_searcher.web.app:app --reload --port 8000
cd frontend && npm install && npm run dev      # Vite on :5173, proxies /api
```

**On the VPS, private, via SSH tunnel (when you want live data):**
```bash
# build the React app LOCALLY (avoids a heavy Node build on the 1GB droplet),
# ship frontend/dist to the VPS (git or scp), then on the droplet:
uv run uvicorn macd_searcher.web.app:app --host 127.0.0.1 --port 8000
```
```powershell
# from your PC:
ssh -L 8000:localhost:8000 tristan@YOUR_VPS_IP
# browse http://localhost:8000
```
Optional: a `systemd --user` unit (or a `web` cron `@reboot`) to keep uvicorn running on the droplet. No UFW change; nothing exposed.

---

## 7. Build order

- [x] **1.** Backend skeleton — `web` optional extra (`fastapi`, `uvicorn[standard]`), `web/db.py` read-only connection (path resolver + `MACD_SEARCHER_DB_PATH` override + WAL-safe `mode=ro`→`query_only` fallback), `web/app.py` FastAPI app with `get_conn` dependency (503 when DB absent), `macd-searcher-web` console script (localhost-bound by default).
- [x] **2.** All MVP endpoints + typed pydantic models + dev CORS + optional static mount. `asset_class` joined inline (read-only can't create the `signal_perf` view). 9 `TestClient` tests vs a seeded fixture DB (`importorskip` so the core suite runs without the extra); 73 total pass. All 10 endpoints verified live against the local DB.
- [x] **3.** Frontend scaffold — Vite 6 + React 18 + TS (strict) + Tailwind 3 + TanStack Query + Recharts. Typed API client (`api/types.ts` mirrors the pydantic models) with polling hooks, `lib/format.ts` helpers, dark theme. `npm install` clean (0 vulns).
- [x] **4.** Dashboard sections — `HealthBanner`, stage×direction / by-class / notify-status / signals-per-day / runs-per-day charts, `SignalsFeed`, `RunsTable`, `TopSymbols`, `Headroom`. Reusable `ui.tsx` (Card/Badge/Metric/StateMsg with loading/empty/error states). Dark, responsive grid. `npm run build` passes `tsc --noEmit` + bundles.
- [x] **5.** Static serving — FastAPI conditionally mounts `frontend/dist` at `/` (after the API routes, so `/api/*` keeps precedence). Verified via TestClient: `/` serves the SPA, `/api/health` returns JSON.
- [ ] **6.** VPS deploy guide — build-locally → ship dist → localhost uvicorn → SSH tunnel; optional keep-alive unit. Add to README.
- [ ] **7. (Phase 2)** Performance/analytics endpoints + panels once outcomes mature (E–I).

---

## 8. Open questions / future

- **Keep-alive:** run uvicorn on demand (start when you tunnel in) or always-on via systemd? Default: on-demand for the MVP.
- **Charting lib** Recharts vs visx — starting with Recharts; revisit if a chart needs more control. (Recharts is ~620 kB unsplit — fine over localhost; if it ever matters, lazy-load the charts or set `manualChunks`. Recharts v2 also nudges toward v3.)
- **Auth:** none needed while it's localhost-only behind SSH. Only relevant if you ever choose public hosting.
- **Phase 3+:** filters (date range, asset class, stage), per-symbol drill-down, threshold-tuning explorer, CSV export.

---

## 9. Next steps (frontend)

Suggested order when resuming:
1. **Sortable tables (order-bys)** — click column headers in `SignalsFeed` + `RunsTable` to sort (time, symbol, MACD, proximity, price). Client-side sort state + sortable `<th>`. Quick, high value.
2. **More feed filters** — asset-class filter + symbol search box (extends the `Segmented` pattern).
3. **Recharts label casing** — `tickFormatter` on the by-class axis + legend `formatter` on the dispatch donut + capitalize the health "Dispatch" value (can't use the `ui.tsx` `capitalize` class — Recharts renders its own text).
4. **Phase-2 performance panels** — win-rate / return-by-horizon / lead-time / MFE-MAE / threshold-bucket charts. Map to `docs/queries.sql` E–I → new `/api/perf/*` endpoints + chart components, with an "accumulating data…" state until outcomes exist.
5. **Polish** — "last updated" indicator + manual refresh button, loading skeletons, error toast (vs the bare banner).
6. **Deploy (commit 6)** — build → ship `dist` → localhost uvicorn + SSH tunnel + optional `systemd` keep-alive.
7. **Bundle** — lazy-load charts / `manualChunks` to cut the ~620 kB if it ever matters.
