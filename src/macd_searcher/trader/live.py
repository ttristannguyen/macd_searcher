"""The live broker: orders go to Hyperliquid through an API agent wallet
(docs/trading_strategy.md §8.4).

An agent wallet can trade for the account, but it cannot withdraw. Its key and the
account address come from the environment: ``HYPERLIQUID_AGENT_KEY`` and
``HYPERLIQUID_ACCOUNT``. You set them in ``.env``.

The exchange holds the positions. The ledger records each order that the bot sends
and each fill that the exchange reports. The daily run halts when the two do not
agree. Use an account for the bot only: each run cancels every open order on it.

It has the same methods as the paper broker (``paper.py``). Install the SDK with
``uv sync --extra live``. Only ``connect`` imports it, so the tests can give
``LiveBroker`` a fake exchange.
"""

from __future__ import annotations

import os
import sqlite3
from datetime import date, datetime, time, timedelta, timezone
from typing import Any

import httpx
import pandas as pd

from macd_searcher.config import AppConfig

from . import ledger, plan
from .paper import Book


def _now() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _day_start_ms(day: date) -> int:
    return int(datetime.combine(day, time(0), tzinfo=timezone.utc).timestamp() * 1000)


def round_px(px: float, sz_decimals: int) -> float:
    """A perp price that Hyperliquid accepts: at most 5 significant figures and at
    most 6 - szDecimals decimals. Prices from the order book already obey it."""
    return round(float(f"{px:.5g}"), 6 - sz_decimals)


def _statuses(response: Any) -> list[dict]:
    """One status for each order of a bulk request. A refused request stops the
    run: the bot cannot know which orders rest."""
    if not isinstance(response, dict) or response.get("status") != "ok":
        raise RuntimeError(f"Hyperliquid refused the request: {response}")
    return response["response"]["data"]["statuses"]


def _oid(status: dict | str) -> tuple[int | None, str | None]:
    """The order id of a resting or filled order, or the error of a rejected one."""
    if isinstance(status, dict):
        for key in ("resting", "filled"):
            if key in status:
                return int(status[key]["oid"]), None
        if "error" in status:
            return None, str(status["error"])
    return None, f"unexpected status {status!r}"


class LiveBroker:
    name = "live"

    def __init__(self, conn: sqlite3.Connection, exchange: Any, account: str):
        self.conn = conn
        self.exchange = exchange
        self.info = exchange.info
        self.account = account

    def held(self) -> dict[str, float]:
        positions = self.info.user_state(self.account)["assetPositions"]
        return {p["position"]["coin"]: float(p["position"]["szi"]) for p in positions
                if float(p["position"]["szi"]) != 0}

    def equity(self, mids: dict[str, float]) -> float:
        return float(self.info.user_state(self.account)["marginSummary"]["accountValue"])

    async def sync(self, client: httpx.AsyncClient, cfg: AppConfig, day: date,
                   bars: dict[str, pd.DataFrame], mids: dict[str, float]) -> None:
        """Close the previous day. Cancel the orders that still rest, then record the
        fills and the funding that the exchange reports. The cancel comes first, so
        that no fill can arrive after the record and before the ledger check."""
        resting = self.info.open_orders(self.account)
        if resting:
            # An order that filled before its cancel gives an error status. That is
            # harmless: the fill is in the record below.
            _statuses(self.exchange.bulk_cancel([{"coin": o["coin"], "oid": o["oid"]} for o in resting]))
        ledger.cancel_open(self.conn)

        first = ledger.first_day(self.conn) or day
        since = ledger.last_fill_ms(self.conn) or _day_start_ms(first)
        for f in self.info.user_fills_by_time(self.account, since):
            ledger.record_exchange_fill(self.conn, f)

        # Funding is paid at the end of each hour: after 00:00 and up to the next 00:00.
        done = ledger.funded(self.conn, day)
        paid: dict[str, float] = {}
        size: dict[str, float] = {}
        rows = self.info.user_funding_history(self.account, _day_start_ms(day - timedelta(days=1)) + 1,
                                              _day_start_ms(day))
        for r in rows:
            d = r["delta"]
            paid[d["coin"]] = paid.get(d["coin"], 0.0) - float(d["usdc"])     # usdc > 0 means received
            size[d["coin"]] = float(d["szi"])
        for coin, amount in paid.items():
            if coin not in done and coin in mids:
                ledger.record_funding(self.conn, day, coin, size[coin], mids[coin], amount)

    def place(self, day: date, orders: list[plan.Order], books: dict[str, Book]) -> list[str]:
        """One post-only limit order for each coin, at the touch. A close is reduce-only.
        Post-only means that the exchange rejects an order that would take liquidity."""
        if not orders:
            return []
        requests = []
        for o in orders:
            bids, asks = books[o.symbol]
            requests.append({"coin": o.symbol, "is_buy": o.size > 0, "sz": abs(o.size),
                             "limit_px": plan.touch(o.size, bids, asks), "order_type": {"limit": {"tif": "Alo"}},
                             "reduce_only": o.target == 0})
        problems = []
        for o, r, st in zip(orders, requests, _statuses(self.exchange.bulk_orders(requests))):
            bids, asks = books[o.symbol]
            oid, error = _oid(st)
            ledger.record_order(self.conn, day, _now(), o.symbol, "limit", o.size, r["limit_px"],
                                (bids[0][0] + asks[0][0]) / 2, oid=oid, status="rejected" if error else "open",
                                error=error)
            if error:
                problems.append(f"{o.symbol}: {error}")
        return problems

    def place_stops(self, day: date, stops: list[plan.StopOrder], sz_decimals: dict[str, int]) -> list[str]:
        """A reduce-only stop-market buy for each held short. It rests on the exchange,
        so no process has to watch the price during the day."""
        if not stops:
            return []
        requests = []
        for st in stops:
            px = round_px(st.trigger, sz_decimals[st.symbol])
            requests.append({"coin": st.symbol, "is_buy": True, "sz": st.size, "limit_px": px,
                             "order_type": {"trigger": {"triggerPx": px, "isMarket": True, "tpsl": "sl"}},
                             "reduce_only": True})
        problems = []
        for st, r, status in zip(stops, requests, _statuses(self.exchange.bulk_orders(requests))):
            oid, error = _oid(status)
            ledger.record_order(self.conn, day, _now(), st.symbol, "stop", st.size, r["limit_px"], r["limit_px"],
                                st.entry, oid, "rejected" if error else "open", error)
            if error:
                problems.append(f"{st.symbol} stop: {error}")
        return problems

    async def close_all(self, client: httpx.AsyncClient, cfg: AppConfig, day: date,
                        mids: dict[str, float]) -> list[str]:
        """Close every position with a reduce-only market order. The next run records
        the fills."""
        problems = []
        for coin, size in self.held().items():
            response = self.exchange.market_close(coin)
            oid, error = _oid(_statuses(response)[0]) if response else (None, "no position")
            mid = mids.get(coin, 0.0)
            ledger.record_order(self.conn, day, _now(), coin, "halt", -size, mid, mid, oid=oid,
                                status="rejected" if error else "filled", error=error)
            if error:
                problems.append(f"{coin}: the close failed: {error}")
        return problems


def connect(conn: sqlite3.Connection, url: str) -> LiveBroker:
    """The live broker for the account in the environment, on the exchange at ``url``."""
    key, account = os.environ.get("HYPERLIQUID_AGENT_KEY"), os.environ.get("HYPERLIQUID_ACCOUNT")
    if not key or not account:
        raise RuntimeError("set HYPERLIQUID_AGENT_KEY and HYPERLIQUID_ACCOUNT in .env for a live run")
    from eth_account import Account
    from hyperliquid.exchange import Exchange

    return LiveBroker(conn, Exchange(Account.from_key(key), url, account_address=account), account)
