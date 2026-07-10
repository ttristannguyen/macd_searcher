# RSI(14) on every signal — compute, alert, log

Working doc + progress tracker. Adds a **14-day Wilder RSI** computed at fire time
to every signal: shown in the Telegram alert, stored on the `signals` row, and
surfaced in the dashboard feed. **Capture-only** — the RSI-vs-outcome analysis is a
future follow-up. Check items off as they land.

## Context / why

Bank RSI alongside outcomes so we can later test whether it sharpens signal quality
beyond the flat 30% histogram-reduction gate (a bearish flatten at RSI 70 is a
stronger read than at 40).

## Decisions (locked in)

- RSI = Wilder smoothing (`ewm(alpha=1/period, adjust=False)`), same as `atr` →
  view-consistent with the detector (the `_view` forming-bar trim applies).
- Scope = fired signals (`signals` table), not `asset_snapshots`. No analysis view yet.
- Non-destructive DB: add `fire_rsi_14` via an idempotent `init_schema` migration.
- Period hardcoded to 14.

## Progress checklist

### Phase 1 — Indicator (`src/macd_searcher/indicators.py`)
- [x] `rsi(close, period=14) -> pd.Series` (Wilder); `avg_loss=0→100`, `avg_gain=0→0`.
- [x] `tests/test_indicators.py`: up→100, down→0, mixed series, range [0,100].

### Phase 2 — Detector (`src/macd_searcher/signals.py`)
- [x] `Signal`: add `rsi_14: float | None = None`.
- [x] `_detect_for_asset`: compute `rsi(df["close"])`, pick fire-bar value matching
      the view (`iloc[-2]` iff forming bar dropped, else `iloc[-1]`), `replace(sig, rsi_14=…)`, NaN→None.
- [x] `tests/test_signals.py`: fired signal has `rsi_14` in [0,100].

### Phase 3 — Database (`src/macd_searcher/db.py`)
- [x] `SCHEMA_SQL`: `fire_rsi_14 REAL` on `signals`.
- [x] `init_schema`: idempotent `_add_missing_columns` migration (ALTER ADD COLUMN).
- [x] `insert_signals`: write `s.rsi_14` → `fire_rsi_14`.
- [x] `tests/test_db.py`: migration adds column on a legacy table; roundtrip.

### Phase 4 — Telegram (`src/macd_searcher/notify.py`)
- [x] `_fmt_stage1_row`: append `RSI {rsi:.0f}` when present.
- [x] `tests/test_notify.py`: message contains `RSI`.

### Phase 5 — Dashboard report
- [x] `web/queries.py` `recent_signals`: add `fire_rsi_14` to SELECT.
- [x] `web/models.py` `SignalRow` + `frontend/src/api/types.ts`: add `fire_rsi_14`.
- [x] `components/SignalsFeed.tsx`: RSI column.

### Phase 6 — Docs
- [x] `docs/schema.md` (new `fire_rsi_14` row), `README.md` (RSI in alert example),
      note period hardcoded 14.

### Phase 7 — (Optional) backfill historical RSI — DEFERRED
- [ ] `update_outcomes --backfill-rsi` (or standalone): per symbol with NULL
      `fire_rsi_14`, re-fetch candles, compute RSI at each fire bar. Not built —
      new signals get RSI automatically; do this only if we want RSI on the
      pre-existing signal history for earlier analysis.

### Verification
- [x] `uv run pytest -q` green.
- [x] `npm --prefix frontend run build` clean.
- [x] `python -m macd_searcher --dry-run --no-db` → alert rows show an RSI value.

## Reference — reused code
- `atr` (Wilder EWM style) — `src/macd_searcher/indicators.py`.
- `_view` / `_detect_for_asset` / `Signal` — `src/macd_searcher/signals.py`.
- `insert_signals` / `SCHEMA_SQL` / `init_schema` — `src/macd_searcher/db.py`.
- `_fmt_stage1_row` — `src/macd_searcher/notify.py`.
- `recent_signals` — `web/queries.py`; `SignalRow` — `web/models.py`; `SignalsFeed.tsx`.
