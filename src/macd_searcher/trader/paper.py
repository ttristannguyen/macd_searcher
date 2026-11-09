"""The paper broker: orders rest in the ledger, and the daily bars fill them.

It has the same methods as the live broker (``live.py``), so that the daily run
(``__main__``) does not know which one it has. On paper, the positions are the sum of
the fills, and the cash is the starting equity less the fills, the fees and the
funding.
"""

from __future__ import annotations

import sqlite3
from datetime import date, datetime, time, timedelta, timezone

import httpx
import pandas as pd

from macd_searcher.config import AppConfig
from macd_searcher.hyperliquid import fetch_funding_history, fetch_l2_book

from . import ledger, plan

Book = tuple[list[tuple[float, float]], list[tuple[float, float]]]


def _now() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _day_start(day: date) -> pd.Timestamp:
    return pd.Timestamp(datetime.combine(day, time(0), tzinfo=timezone.utc))


class PaperBroker:
    name = "paper"

    def __init__(self, conn: sqlite3.Connection, start_equity: float):
        self.conn = conn
        self.start_equity = start_equity

    def held(self) -> dict[str, float]:
        return ledger.held(self.conn)

    def equity(self, mids: dict[str, float]) -> float:
        return ledger.cash(self.conn, self.start_equity) + sum(s * mids[c] for c, s in self.held().items())

    async def sync(self, client: httpx.AsyncClient, cfg: AppConfig, day: date,
                   bars: dict[str, pd.DataFrame], mids: dict[str, float]) -> None:
        """Close the previous day. Record its funding, fill the resting orders that the
        bars reached, and cancel the rest.

        A stop fills before the limit orders of its coin, and the bot cancels them:
        a squeeze that reaches the stop comes first.
        """
        await self._funding(client, cfg, day, mids)
        stopped = set()
        for o in sorted(ledger.open_orders(self.conn), key=lambda o: o["kind"] != "stop"):
            if o["symbol"] in stopped or o["symbol"] not in bars:
                continue
            hit = plan.resting_fill(o["kind"], o["size"], o["px"], bars[o["symbol"]],
                                    date.fromisoformat(o["day"]), day)
            if hit is None:
                continue
            bar_day, px = hit
            size = o["size"]
            if o["kind"] == "stop":
                size = min(size, -self.held().get(o["symbol"], 0.0))   # never more than the short
                stopped.add(o["symbol"])
                if size <= 0:
                    continue
            fee = abs(size * px) * (plan.TAKER_FEE if o["kind"] == "stop" else plan.MAKER_FEE)
            ledger.record_fill(self.conn, bar_day, _now(), o["symbol"], ledger.FILL_KIND[o["kind"]], size,
                               o["mid"], px, fee, date.fromisoformat(o["entry"]) if o["entry"] else None, o["id"])
            ledger.set_status(self.conn, o["id"], "filled")
        ledger.cancel_open(self.conn)

    async def _funding(self, client: httpx.AsyncClient, cfg: AppConfig, day: date, mids: dict[str, float]) -> None:
        """The real hourly funding of each held coin over the day before ``day``. Each
        row of fundingHistory is the payment at the end of its hour, so the 24
        payments of the day are after its 00:00 and up to the next 00:00."""
        start, end = _day_start(day - timedelta(days=1)), _day_start(day)
        done = ledger.funded(self.conn, day)
        for s, size in self.held().items():
            if s in done or s not in mids:
                continue
            df = await fetch_funding_history(client, s, cfg, int(start.timestamp() * 1000))
            rate = float(df.loc[(df["ts"] > start) & (df["ts"] <= end), "funding"].sum())   # + means longs pay
            ledger.record_funding(self.conn, day, s, size, mids[s], size * mids[s] * rate)

    def place(self, day: date, orders: list[plan.Order], books: dict[str, Book]) -> list[str]:
        for o in orders:
            bids, asks = books[o.symbol]
            mid = (bids[0][0] + asks[0][0]) / 2
            ledger.record_order(self.conn, day, _now(), o.symbol, "limit", o.size, plan.touch(o.size, bids, asks), mid)
        return []

    def place_stops(self, day: date, stops: list[plan.StopOrder], sz_decimals: dict[str, int]) -> list[str]:
        for st in stops:
            ledger.record_order(self.conn, day, _now(), st.symbol, "stop", st.size, st.trigger, st.trigger, st.entry)
        return []

    async def close_all(self, client: httpx.AsyncClient, cfg: AppConfig, day: date,
                        mids: dict[str, float]) -> list[str]:
        """Close every position at the market, against the live order book."""
        problems = []
        for s, size in self.held().items():
            bids, asks = await fetch_l2_book(client, s, cfg)
            px = plan.taker_fill(-size, bids, asks)
            if px is None or not bids or not asks:
                problems.append(f"{s}: the book is too thin to close {size:+g}")
                continue
            ledger.record_fill(self.conn, day, _now(), s, "halt", -size, (bids[0][0] + asks[0][0]) / 2, px,
                               abs(size * px) * plan.TAKER_FEE)
        return problems
