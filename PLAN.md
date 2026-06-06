# MACD Zero-Line Scanner — Implementation Plan

A Python service that scans every asset listed on Hyperliquid (crypto perps + HIP-3 / equity-style perps) on the **1-day** timeframe and posts a Telegram alert when an asset's MACD line is approaching the zero line, classifying the cross as bullish or bearish.

---

## 1. Scope & Decisions (confirmed)

| Area | Decision |
|---|---|
| Language | Python 3.11+ |
| Dependency manager | `uv` |
| Asset universe | Hyperliquid **perps only** (`metaAndAssetCtxs`). No spot. |
| Liquidity filter | Skip asset if 24h notional volume < **$1M** OR open interest < **$1M** — applied *before* candle fetch to save bandwidth |
| Timeframe | 1D candles only |
| MACD parameters | Standard **12 / 26 / 9** |
| Signal definition | MACD line near zero AND \|MACD\| shrinking — three threshold modes, config-switchable (see §4) |
| Output | Telegram bot message |
| Schedule | Every 4 hours via cron on user's VPS |
| Quiet hours | Suppress Telegram sends between **00:00–08:00 Australia/Melbourne** (still run the scan; just don't send) |
| Dedupe | None — alert every cycle while condition holds |
| HTTP client | Raw `httpx` against the public `/info` endpoint — no Hyperliquid SDK |
| Backtesting | Out of scope for MVP |

---

## 2. Architecture

```
┌────────────────┐    1D candles     ┌──────────────┐
│ Hyperliquid    │ ────────────────▶ │  Fetcher     │
│ Info API       │                   │  (async)     │
└────────────────┘                   └──────┬───────┘
                                            │ DataFrame per asset
                                            ▼
                                    ┌───────────────┐
                                    │ MACD compute  │
                                    │ (pandas)      │
                                    └──────┬────────┘
                                           ▼
                                    ┌───────────────┐
                                    │ Signal filter │
                                    │ (3 modes)     │
                                    └──────┬────────┘
                                           ▼
                                    ┌───────────────┐
                                    │ Telegram push │
                                    └───────────────┘
```

Single process, runs to completion, exits. Cron handles cadence.

---

## 3. Project layout

```
macd_searcher/
├── PLAN.md                  ← this file
├── README.md                ← setup & cron instructions
├── pyproject.toml           ← deps via uv or poetry
├── config.yaml              ← thresholds, modes, secrets path
├── .env.example             ← TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
├── src/
│   └── macd_searcher/
│       ├── __init__.py
│       ├── __main__.py      ← entrypoint: `python -m macd_searcher`
│       ├── hyperliquid.py   ← universe + candle fetch
│       ├── indicators.py    ← MACD + ATR computation
│       ├── signals.py       ← three filter modes
│       ├── notify.py        ← Telegram send
│       └── config.py        ← pydantic settings model
└── tests/
    ├── test_indicators.py   ← MACD math vs known reference values
    └── test_signals.py      ← threshold logic per mode
```

---

## 4. Signal logic — two stages, three proximity modes

Two detectors run per asset. When both fire, the higher-priority (later) stage wins so each asset appears at most once in the output.

### Stage 1 — `histogram_flattening` (earliest warning)

MACD histogram (`macd - signal_line`) peaked above the noise floor and is now shrinking strictly back toward zero. Direction set by which side of zero the histogram peaked on:
- **Bearish setup**: hist peaked positive, now shrinking → momentum exhaustion at a high
- **Bullish setup**: hist troughed negative, now shrinking → momentum exhaustion at a low

Stage 1 is the **fast/live** detector: it reads today's still-forming daily bar (`histogram_flattening.use_forming_candle: true`) and uses a short 2-bar shrink window, so it joins momentum intraday and produces fresh reads on every 4h run. It therefore repaints. Stage 3 stays on closed bars (see below).

Guards (config-tunable):
- Noise floor: `|hist|_peak / close >= min_peak_pct_of_price` (default 0.2%)
- Reduction: `|hist[now]| <= (1 - min_reduction_from_peak) * |hist|_peak` (default 30%)
- Strict shrink: `|hist|` strictly decreasing over the last `shrink_lookback` bars (default 2, incl. forming bar)
- Peak search window: last `peak_lookback` bars (default 10)

### Stage 3 — `zero_line_proximity` (the original target, latest warning)

Selected by `signal.mode` in `config.yaml`. All modes share the **direction classifier**:

- **Bullish-approaching**: MACD < 0 and rising (last 3 bars' MACD strictly increasing toward 0)
- **Bearish-approaching**: MACD > 0 and falling (last 3 bars' MACD strictly decreasing toward 0)

Modes differ only in **proximity test**:

#### Mode A — `price_pct` (default)
`|MACD| / close < signal.price_pct_threshold` (default `0.005` = 0.5%).
Price-normalized; works uniformly across BTC and micro-caps.

#### Mode B — `atr`
`|MACD| < signal.atr_multiple * ATR(14)` (default multiple `0.25`).
Volatility-normalized; quieter in choppy regimes.

#### Mode C — `rank`
Of all assets meeting the direction test, take the top `signal.rank_top_n` (default `15`) ranked by ascending `|MACD| / close`. Always returns N candidates. The global rank filter runs *before* the priority pick, so an asset bumped out of Stage 3 by the rank cap can still surface via Stage 1.

`config.yaml` excerpt:

```yaml
signal:
  # Stage 3 — zero-line proximity
  zero_line_enabled: true
  mode: price_pct        # price_pct | atr | rank
  price_pct_threshold: 0.005
  atr_multiple: 0.25
  rank_top_n: 15
  shrink_lookback: 3     # bars over which |MACD| must be strictly decreasing
  # Stage 1 — histogram flattening
  histogram_flattening:
    enabled: true
    shrink_lookback: 2
    min_peak_pct_of_price: 0.002
    min_reduction_from_peak: 0.3
    peak_lookback: 10
    use_forming_candle: true   # Stage 1 reads today's forming bar
macd:
  fast: 12
  slow: 26
  signal: 9
candles:
  use_forming_candle: false   # true = include current incomplete day
  lookback_days: 200          # >= 35 needed for stable MACD
hyperliquid:
  base_url: https://api.hyperliquid.xyz
  concurrency: 10
  request_timeout_s: 15
  retry_attempts: 3
universe_filter:
  min_24h_volume_usd: 1_000_000
  min_open_interest_usd: 1_000_000
notify:
  send_when_empty: true
  quiet_hours:
    timezone: Australia/Melbourne
    start: "00:00"            # inclusive
    end:   "08:00"            # exclusive
```

---

## 5. Data fetching (Hyperliquid, raw HTTP)

Single endpoint, two payloads. All requests are `POST https://api.hyperliquid.xyz/info` with `Content-Type: application/json`.

### 5.1 Universe + liquidity filter (one call per DEX)

```json
{"type": "metaAndAssetCtxs"}                       // core perps
{"type": "metaAndAssetCtxs", "dex": "xyz"}         // HIP-3 (equities, commodities, FX)
```

Each call returns `[meta, assetCtxs]` where:
- `meta.universe[i].name` → symbol (HIP-3 entries are pre-prefixed, e.g. `xyz:TSLA`)
- `assetCtxs[i].dayNtlVlm` → 24h notional volume in USD (string)
- `assetCtxs[i].openInterest` → OI in coin units (string)
- `assetCtxs[i].markPx` → mark price (string)

**Filter step (before any candle fetch):** keep asset `i` only if
`float(dayNtlVlm) >= 1_000_000` **AND** `float(openInterest) * float(markPx) >= 1_000_000`.
HIP-3 universe entries also carry a `growthMode` field; anything other than `"enabled"` is skipped.
This drops a large fraction of each DEX up front, saving the cost of fetching candles for dead markets.

### 5.2 Candle fetch per surviving asset

```json
{
  "type": "candleSnapshot",
  "req": {
    "coin": "BTC",
    "interval": "1d",
    "startTime": <now_ms - 200 * 86400000>,
    "endTime":   <now_ms>
  }
}
```

Returns a list of `{t, T, s, i, o, c, h, l, v, n}` candles → assemble into a DataFrame `[ts, open, high, low, close, volume]`.

### 5.3 Concurrency & resilience

- `httpx.AsyncClient` with `asyncio.Semaphore(10)`.
- Retry: 3 attempts with exponential backoff on 429 / 5xx / network errors.
- Per-request timeout: 15s.
- Skip (don't fail the whole run) if an individual asset's candles can't be fetched — log and continue.

### 5.4 Forming-candle handling

Since the job runs every 4h, most runs hit a still-forming daily candle (1D candles close at 00:00 UTC). The data layer **always** returns the forming bar; each detector decides whether to use it (handled in `signals.py`, not `hyperliquid.py`):
- **Stage 1** uses it (`histogram_flattening.use_forming_candle: true`) → live, repaints intraday.
- **Stage 3** ignores it (`candles.use_forming_candle: false`) → closed bars only, stable.

This works without recomputation because MACD/ATR use causal EWM (`adjust=False`): trimming the last row of the pre-computed frame yields exactly the closed-bar result.

---

## 6. MACD computation

Use `pandas` directly (no TA-Lib install pain on Windows / VPS):

```python
ema_fast = close.ewm(span=12, adjust=False).mean()
ema_slow = close.ewm(span=26, adjust=False).mean()
macd     = ema_fast - ema_slow
signal   = macd.ewm(span=9, adjust=False).mean()
hist     = macd - signal
```

ATR for Mode B: standard Wilder's 14.

Tested against known reference values in `tests/test_indicators.py` to catch any drift.

---

## 7. Telegram delivery

- Use raw HTTP (`POST https://api.telegram.org/bot<TOKEN>/sendMessage`) via `httpx` — no extra SDK needed.
- One message per run, batched: all hits formatted as a single Markdown table.
- Secrets via env vars loaded from `.env` (gitignored): `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`.
- **Quiet hours:** scan still runs, but the Telegram send is skipped when current `Australia/Melbourne` time falls in `[00:00, 08:00)`. The scan summary is logged to stdout/log file so cron output is preserved.
- Message format:

```
📉 MACD zero-line scan — 2026-05-25 12:00 UTC
Mode: price_pct (threshold 0.50%)

🟢 BULLISH approaching:
  HYPE    MACD -0.018  (-0.32% of px)   |MACD| ↓ 3 bars
  SOL     MACD -0.41   (-0.28% of px)   |MACD| ↓ 4 bars

🔴 BEARISH approaching:
  BTC     MACD +127.4  (+0.21% of px)   |MACD| ↓ 3 bars

(7 assets scanned, 3 hits)
```

If zero hits, send a compact one-liner so you can confirm the job is alive (or set `notify.send_when_empty: false` to silence).

---

## 8. Hosting on the VPS

Add to crontab (every 4h on the hour):

```cron
0 */4 * * * cd /opt/macd_searcher && /opt/macd_searcher/.venv/bin/python -m macd_searcher >> /var/log/macd_searcher.log 2>&1
```

- Use `uv` or `python -m venv .venv` for the environment.
- Log rotation via `logrotate` (sample config in README).
- Exit code non-zero on uncaught error so cron's MAILTO (if set) catches failures; also send a Telegram error message before exiting.

---

## 9. Build order (suggested commits)

- [x] **1.** `pyproject.toml`, project skeleton, `config.yaml` + pydantic loader, `.env.example`, `.gitignore`, README stub. Verified by smoke-test: `load_config()` returns expected values.
- [x] **2.** `hyperliquid.py` — `metaAndAssetCtxs` (core + each configured HIP-3 DEX via `dex=` param) + liquidity filter (drops `isDelisted` and HIP-3 entries with `growthMode != "enabled"`) + concurrent `candleSnapshot` with retries. HIP-3 symbols already arrive prefixed (e.g. `xyz:TSLA`) and pass straight through to `candleSnapshot`. Live smoke (`scripts/smoke_hyperliquid.py`): 230 core + 82 HIP-3 → 144 kept; all candle fetches OK in ~3s.
- [x] **3.** `indicators.py` — MACD (pandas EWM, `adjust=False`) + Wilder's ATR. Tests cross-check against hand-rolled reference EMAs; 9/9 pass.
- [x] **4.** `signals.py` — Stage 1 (histogram flattening) + Stage 3 (zero-line proximity, three modes) + per-asset priority pick + rank-mode global filter. 14 unit tests pass. Live `scripts/smoke_signals.py` against Hyperliquid produced 42 signals (41 Stage 1 / 1 Stage 3) on 99 assets, all classifications visually plausible.
- [x] **5.** `notify.py` — message formatter (stage/direction grouping, strength-sorted, price-aware number formatting), `chunk_for_telegram` for the 4096-char limit, quiet-hours gate (`Australia/Melbourne` window with wraparound support), dry-run mode, graceful fallback to stdout when secrets are missing or quiet hours active. 13 new unit tests, 36 total pass. Live `scripts/smoke_notify.py` dry-run rendered a clean 23-signal message.
- [x] **6.** `__main__.py` — `argparse` CLI (`--config / -c`, `--dry-run`, `--log-level`, `--no-db`), UTF-8 stdout reconfigure for Windows, logging setup with httpx capped at WARNING, structured exit codes (0/1/2/130), best-effort Telegram error alert on uncaught exception via new `notify.send_raw_text` helper. End-to-end `python -m macd_searcher --dry-run` works against live Hyperliquid.
- [x] **7.** README — purpose, two-stage model, config reference, example output, the three-table data-logging design, disclaimer. (VPS install / logrotate specifics still to fill in under commit 10.)
- [x] **8.** SQLite data logging (§11) — `db.py` (`runs` / `asset_snapshots` / `signals` + indexes, WAL, FKs), `classify.py` (asset-class), `signals.compute_all_metrics` (per-asset detector intermediates, both confirmed + live views), `universe_total` threaded through the fetch, wired into `__main__` as a best-effort pre/post-run write (`--no-db` to disable). 15 new tests (51 total). Live run populated all three tables: 134 snapshots, 21 signals, 5 asset classes.
- [x] **9.** `update_outcomes.py` — daily entrypoint that backfills `signals` outcome columns (forward closes 1/3/7/14d, direction-normalized MFE/MAE, bars-to-zero-cross) for fired signals. Closed-bar scoring, progressive fill, finalize at `outcomes.horizon_days` (14). `score_signal` takes the MACD series as an arg so the cross logic is unit-tested with injected data; 12 outcome tests + 2 db roundtrips (64 total pass). Live run scored 88 pending signals across 25 symbols, exit 0, no errors. Counterfactual *loosening* (scoring `asset_snapshots`) deferred.
- [x] **10.** README VPS deployment guide (install, scan + outcomes cron, logrotate) — done; first real Telegram send pending on the user's server.

---

## 10. Decisions resolved

1. **Universe:** perps only (`metaAndAssetCtxs`). Spot deferred.
2. **HTTP:** raw `httpx` against `/info` — plan detailed in §5.
3. **Deps:** `uv`.
4. **Quiet hours:** Telegram silenced 00:00–08:00 Australia/Melbourne; scan still runs and logs locally.
5. **Liquidity filter:** require 24h notional volume ≥ $1M **and** open interest ≥ $1M (USD-converted via `markPx`). Filter is applied to the universe before candles are fetched. *(Volume floor since tuned down to $300k in `config.yaml`.)*

---

## 11. Data logging (SQLite) — implemented

Local SQLite file at `database.path` (default `state/macd_searcher.sqlite3`), WAL mode, foreign keys on. Writing is **best-effort**: any DB error is logged and swallowed so it can never block a scan or a Telegram send. Disable per-run with `--no-db` or globally with `database.enabled: false`. See the README "Data logging" section for the analytical rationale; this section is the implementation map.

**Module: `db.py`**
- `connect(path)` — makes parent dirs, sets `journal_mode=WAL`, `foreign_keys=ON`.
- `init_schema(conn)` — idempotent `CREATE TABLE/INDEX IF NOT EXISTS`.
- `git_short_sha()` — best-effort code version (NULL until the repo has commits).
- `start_run` / `finalize_run` — open the run row up front, update it on completion (or with `notify_status='failed'` + traceback on error).
- `insert_snapshots` — `INSERT OR REPLACE` keyed on `(run_id, symbol)` (idempotent per run).
- `insert_signals` — one row per fired alert, fresh `uuid4` id, outcome columns left NULL.

**Tables**
- `runs` — one row per invocation; carries `config_json` (telegram secrets excluded) + `config_hash` for reproducibility, universe sizes, `signals_count`, `notify_status`, `error`.
- `asset_snapshots` — one row per `(run, asset)` for every asset with ≥ `slow + peak_lookback + 5` bars, fired or not. Stores both the **confirmed** (closed-bar / Stage 3) and **live** (forming-bar / Stage 1) views of MACD/hist/ATR plus derived intermediates (`macd_pct_of_price`, `hist_recent_peak`, `hist_reduction_from_peak`, `*_shrinking_n_bars`) so any threshold can be re-evaluated offline without re-fetching candles.
- `signals` — alert ledger; detector state at fire time now, outcome columns (`bars_to_zero_cross`, `px_1d/3d/7d/14d`, `max_favorable/adverse_move_pct`) filled in later by the planned `update_outcomes` job (commit 9).

**Supporting changes**
- `classify.py` — `classify_asset(symbol)` → crypto | equity | commodity | fx | index.
- `signals.compute_all_metrics(candles, cfg)` — computes `AssetMetrics` per asset (shares `_view` / `_last_bar_is_forming` with the detectors so logged values match what fired).
- `fetch_universe` now returns `(assets, universe_total)`; `fetch_universe_and_candles` returns `(assets, candles, universe_total)`.

**Outcome scoring (`update_outcomes.py`)**
- `db.fetch_pending_signals` (`outcome_updated_at IS NULL`) + `db.update_signal_outcome`; `hyperliquid.fetch_candles` public wrapper.
- `score_signal(df, macd_line, fired_at, fire_close, direction, horizon_days, now)` → `Outcome`. Anchors on the daily bar at-or-before `fired_at`, drops the forming bar (closed-bar scoring), computes forward closes at fixed 1/3/7/14d offsets, direction-normalized MFE/MAE over the window, and first forward bar where MACD crosses zero in the predicted direction (`bars_to_zero_cross`; NULL after finalize = never crossed in window).
- Idempotent and re-runnable: fills available columns each run, finalizes once `horizon_days` elapsed. Fetches once per symbol.
- **Scope (v1):** fired signals only — supports threshold *tightening*. Scoring `asset_snapshots` for counterfactual *loosening* is a deferred follow-up.
