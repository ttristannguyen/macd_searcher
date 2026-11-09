"""One rebalance of the B3 book a day (docs/trading_bot.md).

    uv run python -m macd_searcher.trader               # today's paper rebalance
    uv run python -m macd_searcher.trader --live        # today's live rebalance (live_url in trader.yaml)
    uv run python -m macd_searcher.trader --report      # the measurements (add --live for the live ledger)
    uv run python -m macd_searcher.trader --clear-halt  # restart after a halt

Run it once a day after the 00:00 UTC close. A second run on the same day does
nothing. A run after a failure sends only the orders that are still necessary.

Each run sends one post-only limit order for each coin, at the touch. The order rests
until the next run, which cancels it if it did not fill. Paper and live have the same
steps. Only the broker is different: ``paper.py`` fills the orders from the daily
bars, and ``live.py`` sends them to Hyperliquid.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
import traceback
from datetime import date, datetime, timedelta, timezone

import httpx
import pandas as pd

from macd_searcher.config import AppConfig
from macd_searcher.hyperliquid import PerpSpec, fetch_all_candles, fetch_core_perps, fetch_l2_book
from macd_searcher.notify import send_raw_text
from macd_searcher.target import COST_PER_SIDE, FUNDING_LONG_APR, FUNDING_SHORT_APR, history_days, target_from_candles

from . import ledger, plan, risk, settings
from .paper import PaperBroker

log = logging.getLogger("macd_searcher.trader")

# The candle fetch of the full core universe uses most of the API's weight budget of
# one minute. Then the order books get HTTP 429 (smoke run, 2026-11-06). The waits
# of 5, 10, 20, 40 and 80 s are more than one minute in total, so the budget refills.
RETRY_ATTEMPTS = 6
RETRY_BACKOFF_S = 5.0


def _now() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _patient(cfg: AppConfig, base_url: str | None = None) -> AppConfig:
    """``cfg`` with the bot's retries, and with ``base_url`` if one is given."""
    update: dict = {"retry_attempts": RETRY_ATTEMPTS, "retry_backoff_s": RETRY_BACKOFF_S}
    if base_url:
        update["base_url"] = base_url
    return cfg.model_copy(update={"hyperliquid": cfg.hyperliquid.model_copy(update=update)})


def _prior_day_volume(candles: dict[str, pd.DataFrame], day: date) -> dict[str, float]:
    """The notional volume of each coin's bar of ``day`` - 1, as the volume floor reads it."""
    out = {}
    for s, df in candles.items():
        bar = df[df["ts"].dt.date == day - timedelta(days=1)]
        if not bar.empty:
            out[s] = float(bar["volume"].iloc[0] * bar["close"].iloc[0])
    return out


def _value(held: dict[str, float], mids: dict[str, float]) -> dict[str, float]:
    """The signed USD value of each position. A held coin with no mid stops the run:
    the bot cannot mark the account, and a person must close that position."""
    missing = sorted(set(held) - set(mids))
    if missing:
        raise RuntimeError(f"no mid for the held coins {', '.join(missing)}: close them by hand")
    return {s: size * mids[s] for s, size in held.items()}


async def rebalance(cfg: AppConfig, conn, day: date, broker, venue_url: str | None = None) -> str:
    """Today's rebalance. Return the Telegram message.

    The signals always come from the main API (``hyperliquid.base_url``). The orders,
    the prices and the coin specs come from ``venue_url`` when it is given, for
    example the testnet.
    """
    data, venue_cfg = _patient(cfg), _patient(cfg, venue_url)
    async with httpx.AsyncClient() as client:
        perps: dict[str, PerpSpec] = {p.name: p for p in await fetch_core_perps(client, data)}
        candles = await fetch_all_candles(client, list(perps), data, history_days(cfg))
        # The book reads a coin with no candles as not listed, and closes it. Thus a
        # failed fetch must stop the run. The scanner can drop the coin, but the bot cannot.
        missing = sorted(set(perps) - set(candles))
        if missing:
            raise RuntimeError(f"no candles for {len(missing)} coins: {', '.join(missing[:10])}")
        venue = perps if not venue_url else {p.name: p for p in await fetch_core_perps(client, venue_cfg)}
        mids = {s: p.mid_px for s, p in venue.items()}
        sz_decimals = {s: p.sz_decimals for s, p in venue.items()}

        await broker.sync(client, venue_cfg, day, candles, mids)
        held = broker.held()
        _value(held, mids)
        equity = broker.equity(mids)
        peak = max(ledger.peak_equity(conn) or equity, equity)
        prev = ledger.previous_equity(conn, day)

        reason = risk.ledger_mismatch(held, ledger.held(conn)) or risk.halt_reason(equity, peak)
        if reason:
            # Close first, then record the halt. If the closes fail, the next run
            # sees the same reason and closes again.
            problems = await broker.close_all(client, venue_cfg, day, mids)
            ledger.halt(conn, _now(), reason)
            ledger.finish(conn, day, _now(), "halted", equity)
            return "\n".join([f"🛑 B3 {broker.name} · {day} · HALT", reason,
                              "The bot closed the book. Run --clear-halt to restart it.", *problems])

        book = target_from_candles(day, candles, cfg, ledger.stopped(conn), ledger.first_day(conn) or day)
        positions = book.positions
        problems = [f"{s}: not on the exchange" for s in sorted(book.weights) if s not in venue]
        weights = plan.volume_capped({s: w for s, w in book.weights.items() if s in venue},
                                     _prior_day_volume(candles, day), equity)
        ledger.record_targets(conn, day, positions, weights)

        orders = plan.rebalance_orders(weights, held, equity, mids, sz_decimals)
        net = risk.planned_net(held, orders, mids, equity)
        if abs(net) > risk.MAX_NET:
            # The $10 minimum dropped too many orders on one side. Do not open an
            # unhedged book. The closes still go, because they cut the risk.
            orders = [o for o in orders if o.target == 0]
            problems.append(f"the planned book is net {net:+.0%}, so only the closes go: "
                            f"the equity is too small for the ${plan.MIN_ORDER_USD:.0f} minimum order")
        books = {o.symbol: await fetch_l2_book(client, o.symbol, venue_cfg) for o in orders}
        thin = sorted(s for s, (bids, asks) in books.items() if not bids or not asks)
        problems += [f"{s}: the order book is empty" for s in thin]
        orders = [o for o in orders if o.symbol not in thin]
        problems += broker.place(day, orders, books)
        stops = plan.stop_orders(held, weights, [*book.yesterday.values(), *positions.values()], candles)
        problems += broker.place_stops(day, stops, sz_decimals)

    planned = dict(held)
    for o in orders:
        planned[o.symbol] = planned.get(o.symbol, 0.0) + o.size
    planned_value = _value({s: x for s, x in planned.items() if x}, mids)
    margin = risk.margin_needed(planned_value, {s: p.max_leverage for s, p in venue.items()})
    longs = sum(p.side > 0 for p in positions.values())
    ledger.finish(conn, day, _now(), "done", equity, longs, len(positions) - longs)
    venue_name = broker.name + (" testnet" if venue_url and "testnet" in venue_url else "")
    lines = [
        f"📒 B3 {venue_name} · {day}",
        f"equity ${equity:,.0f} ({f'{equity / prev - 1:+.2%} day, ' if prev else ''}"
        f"{equity / peak - 1:+.1%} from peak)",
        f"target {longs} long / {len(positions) - longs} short · held {sum(x > 0 for x in held.values())} long / "
        f"{sum(x < 0 for x in held.values())} short",
        f"orders {len(orders)} limit (${sum(abs(o.size) * mids[o.symbol] for o in orders):,.0f}) · "
        f"{len(stops)} stops",
    ]
    return "\n".join(lines + [f"⚠️ {p}" for p in problems + risk.alerts(planned_value, equity, prev, margin)])


def report(conn) -> str:
    """The measurements so far, against the backtest assumptions (§8.3)."""
    days = conn.execute("SELECT COUNT(*), MIN(day), MAX(day) FROM rebalances WHERE status = 'done'").fetchone()
    lines = [f"rebalances {days[0]} ({days[1]} → {days[2]})"]
    last, first = ledger.previous_equity(conn, date.max), conn.execute(
        "SELECT equity FROM rebalances WHERE equity IS NOT NULL ORDER BY day LIMIT 1").fetchone()
    if last:
        lines.append(f"equity ${last:,.0f}, {last / first[0] - 1:+.1%} since the start, "
                     f"{last / ledger.peak_equity(conn) - 1:+.1%} from peak")
    rate = ledger.limit_fill_rate(conn)
    lines.append("limit orders filled: " + (f"{rate:.0%} of the size" if rate is not None else "none yet"))
    costs = ledger.cost_per_side(conn)
    lines.append(f"cost a side (backtest {COST_PER_SIDE:.3%}):" + ("" if costs else " none yet"))
    for r in costs:
        lines.append(f"  {r['kind']}: {r['slippage'] + r['fee_rate']:.3%} = {r['slippage']:+.3%} from the mid "
                     f"+ {r['fee_rate']:.3%} fee ({r['fills']} fills, ${r['notional']:,.0f})")
    assumed = {"long": FUNDING_LONG_APR, "short": FUNDING_SHORT_APR}
    funding = ledger.funding_apr(conn)
    lines.append("funding APR, paid by longs and received by shorts:" + ("" if funding else " none yet"))
    for r in funding:
        lines.append(f"  {r['side']}: {r['apr']:+.1%} (backtest {assumed[r['side']]:+.1%}, "
                     f"{r['position_days']} position-days)")
    return "\n".join(lines)


async def _send(cfg: AppConfig, text: str) -> None:
    """Print the message, and send it to Telegram unless this is a dry run."""
    print(text)
    if not cfg.notify.dry_run:
        await send_raw_text(text, cfg)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m macd_searcher.trader", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-c", "--config", default=None, help="the bot's settings (default trader.yaml)")
    ap.add_argument("--live", action="store_true", help="send real orders to live_url")
    ap.add_argument("--dry-run", action="store_true", help="print the message, do not send it to Telegram")
    ap.add_argument("--report", action="store_true", help="print the measurements and stop")
    ap.add_argument("--clear-halt", action="store_true", help="restart the bot after a halt")
    args = ap.parse_args(argv)
    cfg, trader = settings.load(args.config)
    if args.dry_run:
        cfg = cfg.model_copy(update={"notify": cfg.notify.model_copy(update={"dry_run": True})})
    logging.basicConfig(level=cfg.log_level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    except (AttributeError, ValueError):
        pass

    conn = ledger.connect(trader.live_db_path if args.live else trader.db_path)
    if args.report:
        print(report(conn))
        return 0
    if args.clear_halt:
        print(f"cleared {ledger.clear_halts(conn, _now())} halt(s)")
        return 0

    day = datetime.now(tz=timezone.utc).date()
    halt = ledger.active_halt(conn)
    if halt:
        print(f"halted since {halt['at']}: {halt['reason']}. Run --clear-halt to restart.")
        return 0
    if ledger.day_done(conn, day):
        log.info("The rebalance of %s is done already", day)
        return 0

    if args.live:
        from . import live
        try:
            broker = live.connect(conn, trader.live_url)
        except RuntimeError as exc:
            print(exc, file=sys.stderr)
            return 2
        venue_url: str | None = trader.live_url
    else:
        broker, venue_url = PaperBroker(conn, trader.paper_equity_usd), None

    ledger.start(conn, day, _now())
    try:
        text = asyncio.run(rebalance(cfg, conn, day, broker, venue_url))
    except Exception as exc:
        log.exception("The rebalance failed")
        err = "".join(traceback.format_exception_only(type(exc), exc)).strip()
        ledger.finish(conn, day, _now(), "failed", error=err)
        asyncio.run(_send(cfg, f"🛑 B3 {broker.name} · {day} · the rebalance failed\n\n{err}"))
        return 1
    asyncio.run(_send(cfg, text))
    return 0


if __name__ == "__main__":
    sys.exit(main())
