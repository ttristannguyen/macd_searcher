# Scorecard → per-asset detail view

Working doc + plan + progress tracker. Makes each Scorecard row selectable, opening
a drill-down for that symbol: a **candlestick chart with every measured signal
marked**, **MACD** and **RSI** panes beneath it, and a hover card showing that
signal's full record. Nothing is built yet; this is the plan.

## Context / why

The Scorecard says *ETH has 62% win / +1.8% EV over n=14*. It cannot say **which
fourteen**, what the chart looked like when they fired, or whether the winners
share a shape the losers don't. That's the gap between a ranking and a reason.

This is also the first view that puts a signal back in its **price context**. Every
other panel in the app is aggregate; none of them let you look at a fire and ask
"would I have taken that?"

## Decisions (locked in)

### Candles are fetched live from Hyperliquid, not stored and not reconstructed

The DB has three tables and none of them hold OHLC. `asset_snapshots` carries
`close` and `live_close` per run — a ~4-hourly close-only series that only reaches
back to when logging started (441 rows for BTC, ~74 days). **You cannot draw a
candle from it**, and it would not cover the 200-bar MACD warmup.

So the options were: add a candles table + a fetch job, or fetch on demand. On
demand wins:

- `hyperliquid.fetch_candles(client, symbol, cfg, start_ms, end_ms)` already exists,
  with retry/backoff — the backfills in `update_outcomes` use exactly this path.
- One request per drill-down, ~200 daily bars, ~20 KB. Cached, it's near-free.
- Storing candles duplicates an authoritative upstream source and adds a job that
  can silently fall behind. Redundant state we'd have to keep correct.

**The tradeoff, stated plainly:** this is the first time the dashboard makes an
*outbound* call. It does not break the read-only guardrail — that's about never
writing to the DB — but the dashboard stops being purely local. Consequences the
build must handle: a short TTL cache (10 min; daily bars barely move), graceful
degradation when Hyperliquid is unreachable, and **symbol validation against the
DB** before any value reaches an outbound URL.

### Indicators are computed server-side, from `indicators.py`

Not in JavaScript. The whole point of the view is to show what the detector saw; a
JS reimplementation of MACD/RSI would be a second source of truth that could drift
from the Python by a rounding rule or an EWM seeding difference and quietly
misrepresent history. The API returns `macd`, `signal`, `hist`, `rsi` alongside
OHLC, computed by the same functions the scanner runs.

This also makes the panes free — the series arrive with the candles, no second call.

### The drill-down shows exactly the cohort the Scorecard measured

`by_symbol_scorecard` reads `_base()`: post-`DETECTOR_FIX_CUTOFF`, deduped to the
earliest fire per (symbol, direction, UTC-day), scored at the chosen horizon. The
detail view **must** use the same filter, or the markers won't add up to the `n`
shown in the row above and the view becomes a source of confusion instead of
explanation.

Same-day repeats are therefore *not* plotted. Rather than silently omitting them,
the header reports the count — "14 measured · 3 same-day repeats excluded" — so a
missing marker on a day you remember is explained rather than mysterious.

### Recharts, not a new charting library

Candlesticks aren't a built-in Recharts type, so this needs a custom shape on a
`Bar`. That's real work, but the alternative — adding `lightweight-charts` — brings
a second charting paradigm into a codebase where every existing panel is Recharts.
Recharts also has **`syncId`**, which gives synchronised crosshair and tooltip
across the price/MACD/RSI panes for free, which was the main thing a dedicated
library would have bought us.

Fallback if the custom shape fights us: an OHLC bar or a close-line with high/low
whiskers reads almost as well and is far less fiddly. Reach for a new dependency
only if both fail.

### Two endpoints, not one

Candles and signals are always fetched together, so one combined endpoint is
tempting. Keep them separate anyway: the candle call depends on an external service
and can fail, while the signals call is local and always succeeds. Split, the
signals table and hover data still render when Hyperliquid is down — the view
degrades to "no chart" instead of "no page".

### What the hover shows

The ask left this open. A tooltip that lists twenty columns is unreadable, so it
carries only what answers *"was this a good signal, and did it work?"*; everything
else goes in the table below, where it can be scanned and compared.

**Tooltip (on a marker):**

| line | fields | why |
|---|---|---|
| header | date · direction badge · **confident** marker | what and which cohort |
| entry | `fire_close` | anchors the marker to the price axis |
| trigger | `↓{reduction}%` from peak | the firing metric |
| context | peak pct + `n=` · RSI · sig % of price | the three quality dimensions we measure |
| outcome | **7d return** (coloured), MFE / MAE | did it work, and how far it swung |
| status | finalized, or "pending — N of 14 days elapsed" | stops an unscored signal reading as a loss |

**Table below the chart** adds `1d / 3d / 14d` returns, `bars_to_zero_cross`,
`fire_hist_peak_ratio`, and `fire_macd`, sortable, one row per marker with
click-to-highlight on the chart.

Deliberately omitted from both: `run_id`, `signal_id`, `stage` (always
`histogram_flattening`), and the legacy Stage-3 columns — noise for this purpose.

### Selection is page state, not a route

The app has no router; tabs are `useState` in `App.tsx`. Clicking a row sets
`selectedSymbol` on the Scorecard page, which swaps the table for the detail view
plus a "← all assets" button. No URL to deep-link, which is a real loss — noted
under Out of scope rather than pretending otherwise.

## Progress checklist

### Phase 1 — Backend: per-asset signals
- [ ] `web/perf.py` `signals_for_symbol(conn, symbol, horizon)` → the deduped,
      post-fix rows for one symbol with every fire + outcome column, plus the
      derived `sig_pct_of_price` and the `_CONFIDENCE_SQL` cohort, ordered by
      `fired_at`. Reuse `_base()` so the cohort provably matches the Scorecard.
- [ ] A companion count of same-day repeats excluded by the dedup (raw post-fix
      count for that symbol minus the deduped count).
- [ ] `web/models.py` `AssetSignalRow` + `AssetSignals` (rows + counts).
- [ ] `web/app.py` `GET /api/assets/{symbol}/signals?horizon=`.
- [ ] Tests: the returned rows match `by_symbol_scorecard`'s `n` for the same
      symbol/horizon **exactly** (the anti-confusion guarantee); dedup drops the
      same-day repeat and reports it; unknown symbol → empty, not 500.

### Phase 2 — Backend: candles + indicators
- [ ] `web/candles.py` (new module — keeps outbound I/O out of `perf.py`, which is
      pure SQL): `fetch_asset_series(symbol, cfg, bars)` → OHLC + `macd`/`signal`/
      `hist`/`rsi`, computed via `indicators.py`.
- [ ] **Symbol validation before the call** — reject anything not present in
      `signals.symbol`, so no user-supplied string reaches an outbound URL.
- [ ] TTL cache (10 min, keyed by symbol+bars) so re-opening an asset is instant
      and a click-happy session doesn't hammer the upstream.
- [ ] Window: earliest signal for that symbol minus `lookback_days` warmup, capped
      at ~400 bars for legibility.
- [ ] `GET /api/assets/{symbol}/candles?bars=` → **503 with a clear detail** when
      the fetch fails, so the frontend can show "chart unavailable" and still
      render the table.
- [ ] Tests: indicators match `indicators.macd`/`rsi` on the same input; unknown
      symbol → 404 without an outbound call (assert the client is never invoked);
      upstream failure → 503, not a 500 traceback; cache returns without refetching.

### Phase 3 — Frontend data layer
- [ ] `api/types.ts`: `AssetSignalRow`, `AssetSignals`, `AssetCandle`, `AssetSeries`.
- [ ] `api/client.ts`: `useAssetSignals(symbol, horizon)`, `useAssetCandles(symbol)`
      — both `enabled: !!symbol` so nothing fires until a row is picked.

### Phase 4 — Frontend: the chart
- [ ] `components/AssetChart.tsx` — three stacked Recharts panes sharing one
      `syncId`: price (candles), MACD (line + signal + hist bars), RSI (line with
      30/70 guides).
- [ ] Custom candle shape: a `Bar` whose shape draws the wick and body, green/red
      by close vs open. *(This is the risky bit — see the fallback in Decisions.)*
- [ ] Signal markers on the price pane: `ReferenceDot` per signal at
      `(fire date, fire_close)`, ▼ bearish / ▲ bullish, filled when confident.
- [ ] Hover card with the fields in the table above. Custom tooltip content, since
      the default only knows the series value, not the joined signal record.
- [ ] "Chart unavailable" state when the candle call 503s — the rest still renders.

### Phase 5 — Frontend: table + wiring
- [ ] `components/AssetSignalsTable.tsx` — every marker as a row, sortable,
      click-to-highlight the corresponding marker.
- [ ] `ScorecardTable`: rows become buttons; `onSelect(symbol)` up to the page.
- [ ] `pages/Scorecard.tsx`: `selectedSymbol` state, "← all assets" back button,
      header repeating that symbol's Scorecard figures so the detail is anchored to
      the number it explains.

### Phase 6 — Docs
- [ ] `docs/schema.md`: note that candles are **not** stored and where the detail
      view gets them, so nobody looks for a candles table.
- [ ] README: one line that the dashboard now makes an outbound Hyperliquid call
      for this view — relevant to anyone running it somewhere without egress.

### Verification
- [ ] `uv run pytest -q` green.
- [ ] `npm --prefix frontend run build` clean.
- [ ] Against `state/prod_snapshot.sqlite3`: open a high-`n` symbol; marker count
      equals the Scorecard `n`; MACD pane visibly agrees with the fire (histogram
      shrinking toward zero at each marker — if it doesn't, the view and the
      detector disagree and the view is wrong).
- [ ] Kill network / point at a bad base URL → chart degrades, table still renders.

## Caveats to keep honest

- **Outbound dependency.** The chart is only as available as Hyperliquid. Everything
  else in this dashboard works offline against the DB; this pane doesn't.
- **Candles are today's, signals are history's.** Hyperliquid may revise or
  re-timestamp old bars; a marker sitting slightly off its candle is more likely a
  data-vintage artifact than a bug. The signal's own `fire_close` is authoritative
  for what the detector saw — plot the marker at that price, not at the candle close.
- **Fire time vs bar.** Signals fire mid-day on a *forming* bar (`use_forming_candle`),
  so a marker anchors to a bar whose final close differs from `fire_close`. Expect
  markers not to sit exactly on a candle body. Same seam documented in
  [hist_peak_context.md](hist_peak_context.md).
- **`min_n = 3`.** The Scorecard only lists symbols with 3+ scored signals, so the
  drill-down inherits that floor; thinly-traded symbols simply aren't reachable here.
- This is an **inspection** tool. Eyeballing a dozen charts and concluding the
  winners "look different" is exactly how a story gets fitted to noise — anything
  spotted here is a hypothesis for the bucket-analysis machinery, not a finding.

## Out of scope / future

- Deep-linking to an asset (needs a router; the whole app is `useState` tabs).
- Intraday candles — the detector is daily; a 1h view would be a different question.
- Drawing MFE/MAE excursion bands, or the forward-return window, on the price pane.
  Genuinely useful, and the natural follow-on once the base chart works.
- Chart on the Confidence tab for a single confident signal — same components,
  different entry point.

## Reference — reused code

- `fetch_candles` — `hyperliquid.py`; `macd`, `rsi` — `indicators.py`.
- `_base()`, `_CONFIDENCE_SQL`, `by_symbol_scorecard`, `parse_classes` — `web/perf.py`.
- `recent_signals` (row shape), `SignalRow` — `web/queries.py` / `web/models.py`.
- `ScorecardTable`, `ScorecardLegend` — `components/Scorecard.tsx`;
  `pages/Scorecard.tsx` for the page shell.
- Recharts patterns (`ComposedChart`, `ReferenceLine`, custom tooltips) —
  `components/OutcomesCharts.tsx`; `Card`, `StateMsg`, `Badge` — `components/ui.tsx`.
- `signal_line_pct_of_price` — `signals.py` (for the hover's `sig %`).
