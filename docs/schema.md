# Database schema — field reference

The scanner logs to a local SQLite file (`state/macd_searcher.sqlite3`) with three tables. This document describes every column. See the README "Data logging" section for the *why*; this is the *what*.

**Conventions used throughout:**
- All timestamps are **ISO-8601 UTC strings** (e.g. `2026-06-05T12:00:00+00:00`).
- Two "views" of the indicators appear in `asset_snapshots`:
  - **confirmed** = computed on **closed** daily bars only (today's forming bar dropped). This is what **Stage 3** sees and never repaints.
  - **live** = computed **including** today's still-forming bar. This is what **Stage 1** sees; it moves intraday.
- Returns are derived as `px_Nd / fire_close − 1` (not stored as a column).

---

## `runs` — one row per scan invocation

Operational log + reproducibility anchor. Every other table's `run_id` points here.

| Column | Type | Description |
|---|---|---|
| `run_id` | TEXT (PK) | Unique id for the run (`uuid4` hex). |
| `started_at` | TEXT | When the run began. |
| `completed_at` | TEXT | When it finished. NULL if the run crashed before finalizing. |
| `duration_s` | REAL | Wall-clock seconds for the whole scan. |
| `code_version` | TEXT | Git short commit SHA the run executed (NULL if the repo has no commits / git unavailable). |
| `config_hash` | TEXT | First 16 hex chars of `sha256(config_json)` — a quick key to group runs by identical config. |
| `config_json` | TEXT | Full config snapshot as JSON, **excluding Telegram secrets**. Lets you reproduce exactly what the model was doing on any past run. |
| `universe_total` | INTEGER | Assets seen across all DEXes **before** the liquidity filter. |
| `universe_kept` | INTEGER | Assets that **passed** the liquidity filter (volume + OI floors). |
| `signals_count` | INTEGER | Number of signals fired this run. |
| `notify_status` | TEXT | Dispatch outcome: `sent`, `empty_suppressed`, `dry_run`, `quiet_hours`, `no_creds`, or `failed`. |
| `error` | TEXT | Exception summary if the run failed; NULL otherwise. |

---

## `asset_snapshots` — one row per (run, asset)

Every asset that passed the liquidity filter and had enough candles for MACD, **whether or not it fired**. The substrate for offline threshold tuning. Primary key is `(run_id, symbol)`.

| Column | Type | Description |
|---|---|---|
| `run_id` | TEXT (FK→runs) | The run this snapshot belongs to. |
| `symbol` | TEXT | Hyperliquid symbol. Core perps are bare (`BTC`); HIP-3 perps are prefixed (`xyz:TSLA`). |
| `asset_class` | TEXT | `crypto` \| `equity` \| `commodity` \| `fx` \| `index` (derived from the symbol). |
| `mark_px` | REAL | Mark price at scan time (from Hyperliquid's asset context). |
| `day_ntl_vlm_usd` | REAL | 24h notional traded volume, USD. |
| `open_interest_usd` | REAL | Open interest in USD (`open_interest_coin × mark_px`). |
| `close` | REAL | Last **closed** daily close (confirmed view). |
| `macd` | REAL | MACD line, confirmed view. |
| `macd_signal` | REAL | Signal line (EMA of MACD), confirmed view. |
| `hist` | REAL | Histogram (`macd − macd_signal`), confirmed view. |
| `atr` | REAL | Wilder's ATR(14), confirmed view. |
| `macd_pct_of_price` | REAL | `|macd| / close`, confirmed. The **Stage 3** proximity metric — how close MACD is to zero. |
| `macd_shrinking_n_bars` | INTEGER | Consecutive most-recent bars where `|macd|` strictly decreased, confirmed view. |
| `live_close` | REAL | Latest price **including** today's forming bar (live view). |
| `live_hist` | REAL | Histogram including the forming bar (live view). |
| `live_hist_pct_of_price` | REAL | `|live_hist| / live_close`. |
| `hist_recent_peak` | REAL | The signed peak of `hist` within the peak-lookback window (live view) — the high/low the histogram reached before flattening. |
| `hist_reduction_from_peak` | REAL | `1 − |live_hist| / |hist_recent_peak|` — fraction the histogram has shrunk from its peak. The **Stage 1** trigger metric (NULL if no valid peak). Since the same-sign-excursion alignment (`SNAPSHOT_FIX_CUTOFF`) this uses the detector's excursion-confined peak, matching what would have fired; earlier rows used a raw `peak_lookback`-window peak and can read higher. |
| `hist_shrinking_n_bars` | INTEGER | Consecutive most-recent bars where `|hist|` strictly decreased, live view. |

---

## `signals` — one row per fired alert

One asset that triggered an alert in a given run. The `fire_*` columns capture the detector state at fire time; the outcome columns are **NULL initially** and backfilled later by `update_outcomes` as forward bars complete.

### Identity & fire-time state

| Column | Type | Description |
|---|---|---|
| `signal_id` | TEXT (PK) | Unique id for the alert (`uuid4` hex). |
| `run_id` | TEXT (FK→runs) | The run that produced this alert. |
| `symbol` | TEXT | The asset. |
| `stage` | TEXT | `histogram_flattening` (Stage 1, earliest) or `zero_line_proximity` (Stage 3, imminent). Only the higher-priority stage is recorded when both fire. |
| `direction` | TEXT | `bullish` (expecting an upward cross) or `bearish` (downward). |
| `fired_at` | TEXT | When the signal fired (equals the run's `started_at`). |
| `fire_close` | REAL | Price used at fire time — **live** price for Stage 1, **closed** close for Stage 3. The entry reference for return calculations. |
| `fire_macd` | REAL | MACD value at fire. |
| `fire_hist` | REAL | Histogram value at fire. |
| `fire_macd_pct_of_price` | REAL | `|macd|/price` at fire. Populated for Stage 3; NULL for Stage 1. |
| `fire_atr_multiple` | REAL | `|macd|/ATR` at fire. Populated only for Stage 3 in `atr` mode; NULL otherwise. |
| `fire_hist_peak` | REAL | Histogram peak at fire (Stage 1); NULL for Stage 3. |
| `fire_reduction_from_peak` | REAL | Reduction-from-peak at fire (Stage 1); NULL for Stage 3. |

### Outcome columns (backfilled by `update_outcomes`)

Anchored on the daily bar at-or-before `fired_at`, scored on **closed** bars over the configured horizon (default 14 days).

| Column | Type | Description |
|---|---|---|
| `bars_to_zero_cross` | INTEGER | Daily bars after the fire bar until MACD actually crossed zero in the predicted direction. `0` = already crossed by the fire bar. NULL **after finalization** = it never crossed within the horizon. |
| `zero_cross_observed_at` | TEXT | Timestamp of the bar where the cross occurred (NULL if no cross). |
| `px_1d` / `px_3d` / `px_7d` / `px_14d` | REAL | Closing price 1 / 3 / 7 / 14 days after the fire bar's date. NULL until that bar exists. Return = `px_Nd / fire_close − 1`. |
| `max_favorable_move_pct` | REAL | Best price excursion within the window, **in the predicted direction** (≥ 0 means the trade worked). Bullish uses highs; bearish uses lows. (MFE) |
| `max_adverse_move_pct` | REAL | Worst excursion **against** the direction (≤ 0 typically). The drawdown you'd have had to survive. (MAE) |
| `outcome_updated_at` | TEXT | Set once the signal is fully scored (horizon elapsed). **NULL = still pending** — `update_outcomes` revisits it on later runs as bars complete. |

---

## How they relate

```
runs (1) ──< asset_snapshots   (every kept asset, every run)
runs (1) ──< signals           (only assets that fired, every run)
```

- `runs` answers *"did the scan run, with what config, did it succeed?"*
- `asset_snapshots` answers *"what was the market state — and what would have fired under different thresholds?"*
- `signals` answers *"what did the model predict, and (via the outcome columns) was it right?"*
