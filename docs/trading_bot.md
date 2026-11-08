# The B3 trading bot

This doc tells how the bot works. [trading_strategy.md](trading_strategy.md) tells
what it trades and why.

## 1. Status (2026-11-06)

| part | status |
|---|---|
| target book: closed-bar fires → `backtest.target_book`, from zero on day 1 | built, `trader/plan.py` |
| orders: one post-only limit order a coin, at the touch | built, `trader/plan.py` |
| paper broker: the daily bars fill the resting orders | built, `trader/paper.py` |
| live broker: Hyperliquid SDK, API agent wallet | built, `trader/live.py`; not run yet |
| short tail stop at +100%, as a resting stop-market order | built |
| account halt, ledger check, net, gross, margin and daily-loss alerts | built, `trader/risk.py` |
| ledger and measurement report | built, `trader/ledger.py` |
| backtest replay of the traded days (fidelity) | not built (§8) |
| BTC trend sleeve | not wanted (decided 2026-11-06) |

## 2. Decisions (2026-11-06)

| question | decision |
|---|---|
| execution | one post-only limit order a coin a day, at the touch. It rests until the next run. The bot does not cross the spread |
| tail-stop level | +100% (§4) |
| capital and halt | deferred. The halt stays at −30% |
| first day | the book starts from zero. A fire before the first run opens no position |
| BTC sleeve | no |
| where | the scanner's VPS, a separate process, cron at 00:10 UTC (§3) |
| live signing | `hyperliquid-python-sdk` (`uv sync --extra live`) |
| drift band | none (decided 2026-11-08, §7) |
| testnet | none (decided 2026-11-08): we cannot get testnet funds (§6) |

## 3. Commands

```bash
uv run python -m macd_searcher.trader --dry-run
```

This command does today's paper rebalance and prints the message. Without
`--dry-run`, the bot also sends it to Telegram. A second run on the same UTC day does
nothing.

```bash
uv run python -m macd_searcher.trader --live --dry-run
```

This command sends real orders to `trader.live_url`. It needs
`HYPERLIQUID_AGENT_KEY` and `HYPERLIQUID_ACCOUNT` in `.env` (§6).

```bash
uv run python -m macd_searcher.trader --report
```

This command prints the measured cost a side, the limit fill rate and the funding
APR, next to the backtest assumptions. Add `--live` for the live ledger.

```bash
uv run python -m macd_searcher.trader --clear-halt
```

This command restarts the bot after a halt. Add `--live` for the live bot.

**Where to run it.** Use the scanner's VPS. It is always on, its cron is in UTC, and
it has `uv` and the Telegram settings. Run the bot as its own cron line, so that a
trading error cannot stop a scan. Run it at 00:10 UTC: the scanner uses the API at
00:00, and the two runs must not share the API's rate limit.

```
10 0 * * * cd /path/to/macd_searcher && uv run python -m macd_searcher.trader >> logs/trader.log 2>&1
```

**Telegram.** Set `TRADER_TELEGRAM_CHAT_ID` to send the trading messages to their own
chat, with the same bot. A halt or a failed rebalance needs an action, and the
scanner sends about six messages a day. Without the variable, the messages go to the
scanner's chat.

## 4. The daily cycle

Paper and live have the same steps. Only the broker is different.

1. Stop if a halt is active, or if the day has the status `done`.
2. Get every core perp that is not delisted, and 317 days of daily candles for each.
   The detector applies the volume floor to the closed bar, as in the backtest.
3. Stop if the candle fetch failed for a coin. The book reads a coin with no candles
   as delisted, and it would close that position.
4. Run the closed-bar detector (`book.closed_bar_fires`) for the last 17 fire days.
5. **Sync the broker.** It cancels the orders that still rest, and records the fills
   and the funding of the previous day. On paper, the daily bars fill the orders.
   Live, the exchange reports the fills.
6. Mark the account. Halt if the exchange positions are not the ledger positions, or
   if the equity is 30% or more below its peak. A halt closes the book at the
   market first, then records the halt.
7. Replay `target_book` for today, and record the target book.
8. Make one net order for each coin. If the $10 minimum drops so many orders that the
   planned book is more than ±10% net, send only the closes.
9. Send one post-only limit order for each coin, at the touch. Send a stop-market buy
   for each held short.
10. Check the alerts, record the day as `done`, and send the message.

**Why a replay.** The bot does not keep its book from day to day. Each day, it
replays `target_book` from an empty book over the 15 days that can still hold a
position. Thus the book is a function of closed bars and of the recorded stops
only. A test checks that the replay gives the backtest's book on each of 60 days of
random fires.

**Why a failed run is safe.** The key of each rebalance is its UTC day, and each
order is the difference between the target and the held book. Thus a run after a
failure sends only the orders that are still necessary.

**What resting orders change.** A limit order fills only if the price comes to it,
so the held book lags the target. A buy at the bid fills when the price falls, and a
sell at the ask fills when it rises. The report measures this: the limit fill rate,
and the distance of each fill from the decision mid. On paper, an order fills only if
a later bar trades through its price, because an order at the touch waits behind the
queue.

## 5. The rules and their source

The book rules come from `research/backtest.py`. The bot does not copy them. These
are the rules that the bot adds:

| rule | value | source |
|---|---|---|
| start | no position from a fire before the first run | decision, 2026-11-06 |
| fire days read | 17 | 15 hold days, 1 for yesterday's book, 1 for the first-fire flag |
| orders | post-only (`Alo`) at the touch; a close is reduce-only | decision, 2026-11-06 |
| minimum order | $10 notional; a full close is always sent | Hyperliquid's minimum |
| volume cap | 1% of the prior-day notional a name | §3.3 |
| short tail stop | close before entry × 2, stop-market, reduce-only | §5; exit_research.md §6 |
| account halt | 30% below the peak equity | §10 proposal |
| ledger check | halt if the exchange positions are not the sum of the fills | §5 |
| alerts | net > ±10%, gross > 2.05x, margin > equity, day < −5% | §5 |
| fees on paper | 0.015% maker for a limit fill, 0.045% taker for a stop or a halt | Hyperliquid base tier |
| traded legs | L1, L2, S1, S2 | remove a leg from `TRADED_LEGS` for a leg kill (§5) |

**Why +100% for the stop.** Of 3,744 short first fires, 4.9% trade 50% above entry
within 14 days. Held to day 14, 63% of them end better than −50%, because squeezes
partly revert. A stop at +50% sells near the top of those squeezes. In the backtest
it costs 0.16 Sharpe, and +100% costs 0.08. Neither cuts the drawdown. The stop is
insurance against a 5x day or a liquidation only, so the wider level is better. The
smoke run agrees: in 10 days, two +50% stops (NIL, SOPH) were wicks that reverted.

The gross alert is at 2.05x, not 2x. The target book is at most 2x, but order sizes
are rounded, and a resize below the minimum order does not go.

## 6. The live broker

The live broker uses an **API agent wallet**. The agent can trade for the account,
but it cannot withdraw. Do these steps to set it up:

1. Use a Hyperliquid account for the bot only. Each run cancels every open order on
   it, and the ledger check halts on a position that the bot did not open.
2. On the Hyperliquid app, create an API wallet for that account.
3. Put its private key in `.env` as `HYPERLIQUID_AGENT_KEY`, and the address of the
   main account as `HYPERLIQUID_ACCOUNT`.
4. Run `uv sync --extra live` to install the SDK.
5. Set `trader.live_url` to `https://api.hyperliquid.xyz`. The default is the testnet,
   so that a run with real money needs a deliberate edit.
6. Run the check of phase G of [trader_repo_plan.md](trader_repo_plan.md). It uses one
   position of about $11, for less than a minute.

We cannot get testnet funds, so the sequence is paper trading, then that check, then
the live book. Paper trading does not measure the cost of the orders: a paper limit
fill is at its limit price with the maker fee. Only real fills measure it.

**Known gaps.**
- A short that a resting order opens gets its stop at the next run. For up to one
  day, it has no stop. The backtest shows that this costs nothing more than the stop
  itself (research log, 2026-11-07).
- Hyperliquid may refuse a close below $10. The check of phase G shows it.
- The SDK calls block the event loop. Nothing else runs during the rebalance, so this
  has no effect.

## 7. Capital

Hyperliquid refuses an order below $10. The B3 book holds a median of 31 longs and
23 shorts, and each side is at most 100% of equity. Thus a small account cannot hold
the tested book. These values use the bot's execution with no drift band: limit
orders, and the stop from the next day (committed backtest, 2023-02-28 → 2026-10-15,
research log 2026-11-07). The baseline is Sharpe 1.50.

| equity | Sharpe | Δ vs baseline [95%] | days with only the closes |
|---|---|---|---|
| $500 | 0.63 | −0.86 [−2.13, +0.22] | 68% |
| $1,000 | 0.83 | −0.66 [−1.39, +0.15] | 47% |
| $2,000 | 1.28 | −0.22 [−0.59, +0.21] | 19% |
| $3,000 | 1.45 | −0.04 [−0.27, +0.19] | 7% |
| **$5,000** | 1.49 | −0.00 [−0.16, +0.15] | 0% |
| $10,000 | 1.46 | −0.03 [−0.17, +0.08] | 0% |
| no minimum | 1.44 | −0.05 [−0.19, +0.07] | 0% |

**$5,000 is the smallest tested account that trades the tested book.** Below it, a
name is small. When a name opens or closes, each other name of that side changes by
less than $10. Those resizes do not go, the side drifts, and the planned book goes
above ±10% net. Then the bot sends only the closes (§4, step 8).

**Why there is no drift band.** With a ±25% band, the held weights drift, and the book
goes net. Then the bot sends only the closes on about a third of days, at each
account size, $10,000 included. At the maker fee, the band saves only 0.3% a year.

At $100, the daily run cannot hold the book. That amount pays for the check of §6.

## 8. Next steps

1. **Fidelity replay.** Add a report that runs `backtest.account` over the recorded
   targets, with close-to-close returns. Compare it with the equity.
   Each gap is a bug, a cost, an unfilled order, or the time between the close and
   the fill.
2. **One source for the book rules.** `book.py` has its own copy of the rules for the
   Telegram book. It can call `trader.plan.target_on`, and then the message shows
   the book that the bot trades.

## 9. Smoke runs (2026-11-06)

These numbers come from single days, at the wrong hour. They show that the parts
work, and they are not evidence of costs.

**10:18 UTC, the full book, market orders** (before the decisions of §2):
- 17 longs (L1 4, L2 13) and 62 shorts (S1 12, S2 50). Gross 2.00x, net 0.0%.
- 79 market orders, $20,015 in total: 0.081% a side, 0.036% from the mid plus the
  0.045% taker fee. The backtest assumes 0.10%.
- Two +50% tail stops: NIL (short from 10-25, stopped on 10-27) and SOPH (short from
  10-29, stopped on 10-30). Each bar closed far below its high.
- After the candle fetch of 179 coins, the order books got HTTP 429. Now the bot
  waits up to 155 s on a 429. The first try lost coins in the candle fetch and gave
  a book of 64 names. Now a failed fetch stops the run (§4, step 3).

**11:33 UTC, from zero, resting limit orders:**
- Day 1 holds only the first fires of the day: 1 long (L2) and 4 shorts (S1 3,
  S2 1). Each side is 10% of equity.
- 5 post-only orders, $2,000, at the touch. They fill or are cancelled at the next run.
