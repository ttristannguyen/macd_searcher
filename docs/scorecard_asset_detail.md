# Scorecard → per-asset signal dataset

Working doc + plan + progress tracker. Makes each Scorecard row selectable, opening
a drill-down for that symbol: **every measured signal for that token as a full
record**, one row each, with the fire-time state and every outcome column side by
side. **Built** — all four phases done; one visual check outstanding.

## Context / why

The Scorecard says *ETH has 62% win / +1.8% EV over n=14*. It cannot say **which
fourteen**, what state each was in when it fired, or whether the winners differ
from the losers on any dimension we already measure. That's the gap between a
ranking and the records behind it.

Every other panel in the app is an aggregate — a bucket, a mean, a heatmap cell.
None of them let you look at the individual rows that produced a number. This is
the view that does.

## Decisions (locked in)

### No chart — this is a dataset view

An earlier draft of this plan centred on a candlestick chart with signal markers,
MACD/RSI panes, and a hover card. That is dropped. Recording why, so it isn't
re-proposed by accident:

- **It required an outbound call.** The DB holds no OHLC (`asset_snapshots` has
  close-only, ~4-hourly, starting when logging started — not enough for a candle,
  let alone the 200-bar MACD warmup). Drawing candles meant the dashboard calling
  Hyperliquid live, which breaks "works offline against the DB" and adds a failure
  mode to a pane that otherwise cannot fail.
- **It needed a custom Recharts shape.** Candlesticks aren't a built-in type, so it
  meant hand-drawing wicks and bodies on a `Bar` — real work, with a live fallback
  plan admitting it might not come off.
- **It duplicated indicator logic** into a second surface that could drift from
  `indicators.py`.
- **The payoff was the weakest part.** The chart's job was "eyeball the setups" —
  and this doc's own caveat says eyeballing a dozen charts and concluding the
  winners look different is precisely how a story gets fitted to noise. We'd have
  paid three real costs for the affordance most likely to mislead.

The records themselves carry the information without any of that. Everything below
is local SQL against columns that already exist.

### The drill-down shows exactly the cohort the Scorecard measured

`by_symbol_scorecard` reads `_base()`: post-`DETECTOR_FIX_CUTOFF`, deduped to the
earliest fire per (symbol, direction, UTC-day), scored at the chosen horizon. The
detail view **must** use the same filter, or the row count won't add up to the `n`
shown in the Scorecard and the view becomes a source of confusion instead of
explanation.

Same-day repeats are therefore *not* listed. Rather than silently omitting them,
the header reports the count — "14 measured · 3 same-day repeats excluded" — so a
missing date you remember is explained rather than mysterious.

### Show all four horizons per row, not just the selected one

The Scorecard picks one horizon. The detail table should show **1d / 3d / 7d / 14d
side by side** for each signal, because the horizon profile is itself the
interesting object: `regime_consistency_analysis.md` §1 found the same rows flip
sign between 7d and 14d, and the falling-histogram work found deep-MACD bullish
signals peak near 3d and give it back by 14d. A per-signal view that shows only the
selected horizon hides exactly that shape.

### What the table shows

Grouped left to right, so a scan reads *when → why it fired → what state it was in
→ what happened*:

| group | columns |
|---|---|
| identity | `fired_at` (date), direction badge, **confident** marker |
| trigger | `fire_close`, `↓{reduction}%` from peak |
| peak context | `fire_hist_peak_ratio` (×), `fire_hist_peak_pct` (pct), `fire_hist_top_n` (n) |
| state | `fire_rsi_14`, signal line as % of price, `fire_macd` |
| outcome | `ret_1d` / `ret_3d` / `ret_7d` / `ret_14d`, MFE, MAE |
| cross | `bars_to_zero_cross` |
| status | finalized, or "pending — N of 15 days elapsed" |

Sortable by any column, default `fired_at` descending. The status column matters:
without it an unscored recent signal reads as a flat/zero result rather than "not
answered yet".

Deliberately omitted: `run_id`, `signal_id`, `stage` (always
`histogram_flattening`), and the legacy Stage-3 columns — noise for this purpose.

### One endpoint, all local

With candles gone there is no second data source and no failure mode to design
around. A single `GET /api/assets/{symbol}/signals` returning rows + counts is the
whole backend.

### Selection is page state, not a route

The app has no router; tabs are `useState` in `App.tsx`. Clicking a row sets
`selectedSymbol` on the Scorecard page, which swaps the table for the detail view
plus a "← all assets" button. No URL to deep-link, which is a real loss — noted
under Out of scope rather than pretending otherwise.

## Progress checklist

### Phase 1 — Backend ✅
- [x] `web/perf.py` `signals_for_symbol(conn, symbol, horizon)` → the deduped,
      post-fix rows for one symbol with every fire + outcome column, all four
      `ret_*`, MFE/MAE, plus the derived signal-line-%-of-price and the
      `_CONFIDENCE_SQL` cohort flag, ordered by `fired_at` desc. Reuses `_base()`
      so the cohort provably matches the Scorecard.
      *Two deviations from the plan, both deliberate:* it takes `horizon` (needed
      to compute `measured`, which is what has to equal the Scorecard's `n`), and
      it drops the `classes` parameter — the Scorecard sits outside the Outcomes
      tab's class scope so nothing would pass one, and omitting it keeps
      `same_day_excluded` exact (a class filter drops rows the raw count still counts).
- [x] A companion count of same-day repeats excluded by the dedup (raw post-fix
      count for that symbol minus the deduped count).
- [x] `web/models.py`: `AssetSignalRow` + `AssetSignals` (rows + `measured` /
      `pending` / `same_day_excluded`).
- [x] `web/app.py`: `GET /api/assets/{symbol}/signals?horizon=` — declared before
      the `/` static mount so it isn't shadowed.
- [x] Tests (8): `measured` matches `by_symbol_scorecard`'s `n` for **every**
      symbol at that horizon; the same-day repeat is dropped *and* reported;
      pending rows return flagged rather than as a zero; all four horizons carried;
      colon symbols route raw and percent-encoded; pre-fix excluded without
      driving the excluded count negative; unknown symbol → empty, not 500;
      `confident` agrees row-for-row with `is_high_confidence`.

Verified against `state/prod_snapshot.sqlite3`: `xyz:MSTR` → 42 rows, 38 measured,
4 pending, 150 same-day repeats excluded, against a Scorecard `n` of 38. ✓

### Phase 2 — Frontend data layer ✅
- [x] `api/types.ts`: `AssetSignalRow`, `AssetSignals`.
- [x] `api/client.ts`: `useAssetSignals(symbol, horizon)` — `enabled: !!symbol` so
      nothing fires until a row is picked; `encodeURIComponent` on the symbol for
      the HIP-3 colon.

### Phase 3 — Frontend: table + wiring ✅
- [x] `components/AssetSignalsTable.tsx` — one row per measured signal, **every
      column sortable** (nulls always last, in either direction — a column of
      em-dashes on top is never what you wanted), `tone()` colouring on the four
      return columns, pending rows dimmed, `★` on confident rows, and header
      tooltips explaining the peak-context columns.
- [x] `ScorecardTable`: optional `onSelect` makes rows clickable (and keeps the
      component usable without it).
- [x] `pages/Scorecard.tsx`: `selected` state, "← all assets" back button, and a
      `SelectedSummary` strip repeating that symbol's Scorecard n / win / EV / CI /
      SQN. It reads the *same cached* `usePerfScorecard` query the table used, so
      drilling in costs no extra request.

### Phase 4 — Docs ✅
- [x] `docs/schema.md`: new "Things the dashboard shows that are *not* stored"
      section — the derived columns and, explicitly, that no OHLC exists anywhere,
      so nobody looks for a candles table.

### Verification
- [x] `uv run pytest -q` — 164 passed (8 new).
- [x] `npm --prefix frontend run build` — clean.
- [x] Against `state/prod_snapshot.sqlite3`, through a **real uvicorn server** (not
      just TestClient): `/` serves the built app; `xyz:MSTR` → 42 rows, 38 measured
      (= Scorecard `n`), 4 pending, 150 same-day repeats excluded; all 19 fields the
      table reads are present; colon symbols route over real HTTP.
- [ ] **Visual eyeball not done** — the render was type-checked and its data
      verified, but no browser confirmed the layout. 18 columns is wide; the
      container scrolls, but check it reads sensibly before trusting it.

## Caveats to keep honest

- **`min_n = 3`.** The Scorecard only lists symbols with 3+ scored signals, so the
  drill-down inherits that floor; thinly-traded symbols aren't reachable here.
- **`fire_close` is a live-bar price.** Signals fire mid-day on a *forming* bar
  (`use_forming_candle`), so `fire_close` is the scan-time price, not that day's
  settled close. Anyone reconciling a row against a chart elsewhere will see a small
  gap. Same seam documented in [hist_peak_context.md](hist_peak_context.md).
- **Per-symbol `n` is small and per-symbol edge does not persist.**
  `regime_consistency_analysis.md` §2 found H1→H2 rank correlation of ≈0 on EV and
  *significantly negative* on 14d win-rate. This view explains a number that is
  itself mostly noise — treat it as "what happened", never as "what this token
  does".
- This is an **inspection** tool. Reading a dozen rows and concluding the winners
  share a property is exactly how a story gets fitted to noise. Anything spotted
  here is a hypothesis for the bucket-analysis machinery, not a finding.

## Out of scope / future

- **The candlestick chart.** Dropped for the reasons above, not forgotten — if the
  case for price context ever becomes strong enough to justify an outbound
  dependency, the earlier plan is in this file's git history.
- CSV export of a symbol's rows — a natural "dataset" affordance, and cheap, but
  not needed to answer *which fourteen*.
- Deep-linking to an asset (needs a router; the whole app is `useState` tabs).
- Cross-symbol comparison (two symbols side by side) — a different view.
- The same table filtered to the confident cohort, reachable from the Confidence
  tab — same component, different entry point.

## Reference — reused code

- `_base()`, `_CONFIDENCE_SQL`, `by_symbol_scorecard` — `web/perf.py`.
- `recent_signals` (row shape), `SignalRow` — `web/queries.py` / `web/models.py`.
- `ScorecardTable`, `ScorecardLegend` — `components/Scorecard.tsx`;
  `pages/Scorecard.tsx` for the page shell.
- `SignalsFeed.tsx` — closest existing table: sticky header, badges, `tabular-nums`,
  per-column formatting. Start from its markup.
- `Card`, `StateMsg`, `Badge`, `tone` — `components/ui.tsx`;
  `fmtPctPts`, `fmtPrice`, `relativeTime` — `lib/format.ts`.
- `signal_line_pct_of_price` — `signals.py` (for the state group's `sig %`).
