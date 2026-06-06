# macd_searcher

A scheduled signal scanner that surfaces Hyperliquid perps approaching a MACD zero-line cross on the 1-day timeframe, and pushes the results to Telegram.

The universe covers Hyperliquid's core crypto perps plus the HIP-3 `xyz` builder DEX, which exposes equities (TSLA, NVDA, META, ...), commodities (GOLD, SILVER, BRENTOIL, COPPER, ...), and FX (EUR, GBP, JPY, ...) as perps — every alerted ticker is one you can actually trade on the platform.

This is a **research / signal tool**, not a trading bot. It surfaces interesting tickers; you make the trading decision.

---

## What it does

Every 4 hours, the scanner:

1. Pulls the full Hyperliquid perp universe (core + HIP-3 DEXes configured in `extra_dexes`).
2. Drops anything illiquid (default: 24h notional volume < $1M *or* open interest < $1M) so only tradeable markets remain.
3. Fetches the last ~200 daily candles per surviving asset, concurrently.
4. Runs two MACD-based detectors on each asset and emits at most one signal per asset (the higher-priority of the two if both fire).
5. Formats a single Telegram message grouped by stage and direction, ordered by signal strength.

Quiet hours (`Australia/Melbourne` 00:00–08:00 by default) suppress the Telegram send but the scan still runs and prints to stdout so the cron log captures it.

---

## How it works: the two-stage model

A MACD zero-line cross is a momentum regime change. By the time it happens you're often late to the trade — so the scanner emits *graduated warnings* before the cross:

### Stage 1 — Histogram flattening (earliest warning)

The MACD histogram (`macd - signal_line`) peaks *before* MACD itself reaches zero. When `|hist|` has been strictly shrinking from a meaningful peak, momentum is exhausting — the cross is coming, you still have time to research the setup.

This is the **fast/live** detector: it reads today's still-forming daily bar so it can join momentum intraday, and uses a short 2-bar shrink window (today vs. yesterday). It therefore *repaints* — a signal can appear, change, or disappear across the day's runs as price moves. That's the intended trade-off for early entry.

**Direction:**
- Hist peaked positive, now shrinking → **bearish setup** (top forming, expect cross down)
- Hist troughed negative, now shrinking → **bullish setup** (bottom forming, expect cross up)

Guards (all tunable):
- **Noise floor**: `|hist|_peak / close >= 0.2%` so micro-wiggles don't fire
- **Reduction**: current `|hist|` must be at least 30% below the recent peak
- **Strict shrink**: `|hist|` strictly decreasing over the last 2 bars (incl. today's forming bar)
- **Peak window**: peak located within the last 10 bars

### Stage 3 — Zero-line proximity (latest warning)

MACD is near zero **and** strictly moving toward it. The cross is imminent. This is the **confirmed** detector: it reads only closed daily bars (ignores today's forming bar), so its "imminent cross" alerts are stable and don't repaint intraday.

Three modes for what "near" means:
| Mode | Definition | Default |
|---|---|---|
| `price_pct` | `\|MACD\| / close < threshold` | 0.5% |
| `atr` | `\|MACD\| < multiple × ATR(14)` | 0.25× |
| `rank` | Top N closest-to-zero across the universe | top 15 |

Direction classifier (shared across modes):
- MACD < 0 and strictly rising for last 3 bars → **bullish**
- MACD > 0 and strictly falling for last 3 bars → **bearish**

### Priority pick

When both stages fire on the same asset, the later stage wins (the cross is closer, more actionable). This keeps each asset to one line in the alert.

---

## Example Telegram output

```
📊 MACD scan — 2026-05-29 06:49 UTC
142 assets scanned, 31 signal(s)

🎯 Stage 3 — zero-line proximity (5)
🔴 BEARISH (3)
  PENDLE     MACD +0.003725   |M|/px 0.26%   px $1.4576
  ASTER      MACD +0.002852   |M|/px 0.42%   px $0.6756
  BNB        MACD +2.908      |M|/px 0.46%   px $638.07
🟢 BULLISH (2)
  xyz:META   MACD -0.1598     |M|/px 0.03%   px $633.46
  ICP        MACD -0.006782   |M|/px 0.25%   px $2.7326

📉 Stage 1 — histogram flattening (26)
🔴 BEARISH (13)
  PURR       hist +0.000148 (↓98% from +0.006445)  px $0.0949
  ATOM       hist +0.001451 (↓86% from +0.01061)   px $2.0588
  ...
🟢 BULLISH (13)
  xyz:CRWV   hist -0.115 (↓95% from -2.435)   px $107.58
  xyz:AMZN   hist -0.1233 (↓95% from -2.579)  px $272.89
  ...
```

---

## Quickstart (local dev)

```bash
uv sync                                       # creates .venv, installs deps
cp .env.example .env                          # fill in TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID
uv run python -m macd_searcher --dry-run      # prints the message instead of sending
```

CLI:

```
macd-searcher [-c PATH] [--dry-run] [--log-level {DEBUG,INFO,WARNING,ERROR}]
```

- `-c / --config PATH` — override the config file location (also honors the `MACD_SEARCHER_CONFIG` env var)
- `--dry-run` — force-skip the Telegram send and print to stdout
- `--log-level` — override `log_level` in config for one run

---

## Configuration

All tunables live in [config.yaml](config.yaml); secrets in `.env`. Highlights:

| Section | Purpose |
|---|---|
| `signal` | Stage 1 / Stage 3 thresholds, modes, shrink lookbacks |
| `macd` | EMA periods (default 12/26/9) |
| `candles` | Interval, lookback depth, whether to include the still-forming current bar |
| `hyperliquid` | Base URL, concurrency, retries, `extra_dexes` (HIP-3 DEX list) |
| `universe_filter` | Liquidity floors (`min_24h_volume_usd`, `min_open_interest_usd`) |
| `notify` | Telegram dispatch gates: `dry_run`, `send_when_empty`, `quiet_hours` |

The config file is loaded fresh on every run, so changes take effect on the next cron cycle without a restart.

---

## Deployment (Ubuntu/Debian VPS, cron)

These steps clone from GitHub and run via cron as your normal (non-root) user. `uv` manages the Python toolchain, so the system Python version doesn't matter.

### 1. Install prerequisites

```bash
sudo apt update && sudo apt install -y git curl
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.bashrc          # put uv on PATH (or open a new shell)
uv --version              # confirm
```

### 2. Clone and install

```bash
cd ~
git clone https://github.com/ttristannguyen/macd_searcher.git
cd macd_searcher
uv sync                   # creates .venv and downloads Python 3.11+ if needed
```

### 3. Configure secrets

```bash
cp .env.example .env
nano .env                 # set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID
```

Tune `config.yaml` if desired (thresholds, liquidity floors, quiet hours). It's re-read every run.

### 4. Test before scheduling

```bash
uv run python -m macd_searcher --dry-run     # prints the message, sends nothing
uv run python -m macd_searcher               # real run — should hit Telegram (outside quiet hours)
```

### 5. Schedule with cron

Create a log dir, then edit your crontab (`crontab -e`):

```bash
mkdir -p ~/macd_searcher/logs
```

```cron
# Pin cron to UTC so the 4-hourly slots line up with the 00:00 UTC daily candle close.
CRON_TZ=UTC

# Scan every 4 hours. cd into the project so relative paths (state/, logs/) resolve there.
0 */4 * * * cd $HOME/macd_searcher && .venv/bin/macd-searcher >> $HOME/macd_searcher/logs/scan.log 2>&1

# Daily signal-outcome backfill (scores fired signals as forward bars complete).
30 1 * * * cd $HOME/macd_searcher && .venv/bin/python -m macd_searcher.update_outcomes >> $HOME/macd_searcher/logs/outcomes.log 2>&1
```

`config.yaml` and `.env` are located relative to the project root (not the cwd), so they're always found. The SQLite DB and logs are written under the project dir **because** the cron line `cd`s there first — keep that `cd` (or set `database.path` to an absolute path).

The 1-day candles close at 00:00 UTC: Stage 1 reads today's forming bar (fresh every 4h run); Stage 3 reads only closed bars (changes once daily at the 00:00 UTC close).

### 6. Log rotation (optional)

`sudo nano /etc/logrotate.d/macd_searcher`:

```
/home/YOUR_USER/macd_searcher/logs/*.log {
    weekly
    rotate 8
    compress
    missingok
    notifempty
    copytruncate
}
```

### 7. Updating later

```bash
cd ~/macd_searcher && git pull && uv sync
```

---

## Data logging

The scanner persists everything it observes — not just alerts — to a local SQLite file (`state/macd_searcher.sqlite3`). The point is to enable **empirical tuning**: instead of guessing whether `price_pct_threshold: 0.005` is the right value, you query historical snapshots and find out what *would* have fired at any other threshold, and what happened to the price afterwards.

Three tables. Each one exists for a specific analytical purpose:

### `runs` — operational log + reproducibility anchor

One row per cron invocation. Records when the run started and finished, how long it took, what version of the code ran, a full JSON snapshot of the config that was active, the universe sizes before/after the liquidity filter, the dispatch outcome (`sent` / `quiet_hours` / `dry_run` / `no_creds` / `empty` / `failed`), and any exception traceback if the run blew up.

**Why this exists:** every other table refers back to a `run_id`. Without the run's config snapshot, you can't reproduce *why* a signal fired in week 3 if you tweaked thresholds in week 5 — you'd just see numbers without their interpretive context. This table is the source of truth for "what was the model doing at that moment."

### `asset_snapshots` — substrate for counterfactual threshold tuning

One row per `(run, asset)` — every asset that survived the liquidity filter, *whether or not it fired a signal*. Stores all detector intermediates: last close, MACD/signal/hist values, ATR, `|MACD|/price`, `|hist|/price`, the recent histogram peak, the reduction-from-peak, how many consecutive bars `|MACD|` and `|hist|` have been shrinking.

**Why this exists:** it's the table that lets you ask "what would alerts have looked like if I'd used a 0.7% threshold?" *without re-fetching candles from Hyperliquid*. All the inputs to the detectors are already there. You can sweep thresholds, swap signal logic, or evaluate new detector ideas entirely offline.

By volume this is the largest table (~50 MB/year at current universe size and cadence), and it's where the most valuable analyses come from — every other table is downstream of decisions whose alternatives you can only explore using this one.

### `signals` — alert ledger + outcome tracking

One row per fired alert. Captures the detector state at fire time (close, MACD, hist, the stage-specific metrics that triggered it), and — filled in later by the `update_outcomes` job (`python -m macd_searcher.update_outcomes`, run daily) — what happened next: how many bars until MACD actually crossed zero, prices at +1d / +3d / +7d / +14d, and the maximum favorable/adverse move (MFE/MAE) within the 14-day horizon. Outcomes fill in progressively as forward bars complete and the row finalizes (`outcome_updated_at` set) once 14 days have elapsed.

**Why this exists:** this is the table that tells you whether the model *works*. With a few months of these rows you can answer:

- Win-rate by stage × direction × asset class (does Stage 1 beat random? Do equities behave differently from crypto?)
- Distribution of bars-to-cross for Stage 1 — how much real lead time it gives you
- Whether Stage 3 hits closer to zero correspond to faster / larger subsequent moves
- Per-symbol reliability — which tickers' signals you can trust

Outcomes are computed by a separate daily job rather than the main scan because they need bars that haven't formed yet at fire time.

### How the three fit together

| Table | Answers |
|---|---|
| `runs` | "Did the scan run? With what config? Did it succeed?" |
| `asset_snapshots` | "What was the market state? What *would* have fired with different thresholds?" |
| `signals` | "What did the model predict, and was it right?" |

Together they give you both the data and the reproducibility to do real tuning instead of guessing.

Full column-by-column reference: [docs/schema.md](docs/schema.md).

---

## Project status

| Component | State |
|---|---|
| Config loader + .env handling | ✅ done |
| Hyperliquid client (core + HIP-3 DEXes) | ✅ done |
| MACD + ATR indicators + tests | ✅ done |
| Stage 1 + Stage 3 detectors + tests | ✅ done |
| Telegram formatter + quiet hours + dry-run | ✅ done |
| `__main__` entrypoint + CLI | ✅ done |
| SQLite data logging (3 tables above) | ✅ done |
| `update_outcomes` job for signal outcomes | ✅ done |
| VPS install / cron / logrotate instructions | ✅ done |
| Analytical query examples | 🚧 planned |

See [PLAN.md](PLAN.md) for the full implementation roadmap.

---

## Disclaimer

Signal output is not financial advice. Markets are noisy; technical indicators give probabilistic edges at best. This tool exists to surface candidates for *your* research and judgement — it does not place trades, and no part of the project should be construed as a recommendation to enter, exit, or size any position.
