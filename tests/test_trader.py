"""Tests for the trading bot: the pure core, the risk controls, the ledger, both
brokers, and the daily run with the network replaced."""

from __future__ import annotations

import ast
import asyncio
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import pytest

from macd_searcher import target
from macd_searcher.book import Fire as BarFire
from macd_searcher.config import AppConfig
from macd_searcher.hyperliquid import PerpSpec
from macd_searcher.research import backtest as bt
from macd_searcher.trader import __main__ as bot
from macd_searcher.trader import ledger, live, paper, plan, risk, settings

D0 = date(2026, 11, 1)


def _d(k: int) -> date:
    return D0 + timedelta(days=k)


def _bars(closes: list[float], first: date, highs: dict[int, float] | None = None,
          lows: dict[int, float] | None = None, opens: dict[int, float] | None = None) -> pd.DataFrame:
    """Daily bars from ``first``. ``highs``, ``lows`` and ``opens`` replace the value of bar k."""
    return pd.DataFrame({
        "ts": pd.date_range(pd.Timestamp(first, tz="UTC"), periods=len(closes), freq="1D"),
        "open": [(opens or {}).get(k, c) for k, c in enumerate(closes)],
        "high": [(highs or {}).get(k, c) for k, c in enumerate(closes)],
        "low": [(lows or {}).get(k, c) for k, c in enumerate(closes)],
        "close": [float(c) for c in closes], "volume": [1e6] * len(closes),
    })


@pytest.fixture
def conn():
    c = ledger.connect(":memory:")
    yield c
    c.close()


# ---------------------------------------------------------------- the volume cap

def test_volume_cap_cuts_a_weight_to_1_percent_of_volume():
    w = plan.volume_capped({"A": 0.10, "B": -0.10}, {"A": 50_000, "B": 1e9}, equity=10_000)
    assert w == {"A": pytest.approx(0.05), "B": -0.10}


# ---------------------------------------------------------------- orders

SZ = {"A": 2, "B": 2, "C": 0}


def test_orders_open_close_and_flip_with_one_net_order_per_coin():
    orders = plan.rebalance_orders({"A": 0.10, "B": -0.10}, {"B": 5.0, "C": 3.0}, 10_000,
                                   {"A": 100.0, "B": 100.0, "C": 50.0}, SZ)
    assert orders == [plan.Order("A", 10.0, 0.10), plan.Order("B", -15.0, -0.10), plan.Order("C", -3.0, 0.0)]


def test_a_drifted_weight_trades_back_to_its_target():
    mids = {"A": 100.0}
    assert plan.rebalance_orders({"A": 0.10}, {"A": 8.0}, 10_000, mids, SZ) == [plan.Order("A", 2.0, 0.10)]
    assert plan.rebalance_orders({"A": 0.10}, {"A": 12.0}, 10_000, mids, SZ) == [plan.Order("A", -2.0, 0.10)]
    assert plan.rebalance_orders({"A": 0.10}, {"A": 9.95}, 10_000, mids, SZ) == []         # a $5 resize


def test_an_order_below_10_dollars_is_not_sent_but_a_close_is():
    assert plan.rebalance_orders({"A": 0.0008}, {}, 10_000, {"A": 100.0}, SZ) == []       # $8
    assert plan.rebalance_orders({}, {"A": 0.05}, 10_000, {"A": 100.0}, SZ) == [plan.Order("A", -0.05, 0.0)]


def test_order_sizes_use_the_coin_s_decimals():
    [o] = plan.rebalance_orders({"C": 0.10}, {}, 10_000, {"C": 3.0}, SZ)
    assert o.size == 333.0


def test_a_limit_order_rests_at_the_touch():
    assert plan.touch(1.0, [(99.0, 1.0)], [(101.0, 1.0)]) == 99.0
    assert plan.touch(-1.0, [(99.0, 1.0)], [(101.0, 1.0)]) == 101.0


def test_a_taker_fill_takes_each_level_in_sequence():
    asks = [(10.0, 1.0), (11.0, 1.0)]
    assert plan.taker_fill(1.5, [], asks) == pytest.approx((10.0 + 0.5 * 11.0) / 1.5)
    assert plan.taker_fill(-1.0, [(9.0, 5.0)], asks) == 9.0
    assert plan.taker_fill(3.0, [], asks) is None


def test_a_resting_limit_fills_only_when_the_price_trades_through_it():
    bars = _bars([100.0] * 5, _d(0), lows={1: 99.0, 3: 98.0}, highs={2: 102.0})
    assert plan.resting_fill("limit", 1.0, 99.0, bars, _d(1), _d(5)) == (_d(3), 99.0)     # 99 is not through
    assert plan.resting_fill("limit", -1.0, 101.0, bars, _d(1), _d(5)) == (_d(2), 101.0)
    assert plan.resting_fill("limit", 1.0, 98.5, bars, _d(1), _d(3)) is None              # bar 3 is not closed


def test_a_resting_stop_fills_at_its_trigger_or_at_a_gap_open():
    bars = _bars([100.0] * 4, _d(0), highs={1: 200.0, 2: 260.0}, opens={2: 250.0})
    assert plan.resting_fill("stop", 1.0, 200.0, bars, _d(0), _d(4)) == (_d(1), 200.0)
    assert plan.resting_fill("stop", 1.0, 220.0, bars, _d(0), _d(4)) == (_d(2), 250.0)


# ---------------------------------------------------------------- the short tail stop

def _short(symbol: str, entry: int) -> bt.Position:
    return bt.Position(symbol, "S1", -1, _d(entry), _d(entry + bt.HOLD_DAYS))


def test_a_held_short_gets_a_stop_at_twice_the_close_before_entry():
    bars = {s: _bars([100.0, 50.0, 60.0], _d(0)) for s in ("S", "X", "F", "L")}
    held = {"S": -2.0, "X": -1.0, "F": -1.0, "L": 3.0}
    positions = [_short("X", 2), _short("S", 1), _short("F", 1),
                 bt.Position("L", "L1", 1, _d(1), _d(15))]
    weights = {"S": -0.1, "F": 0.1, "L": 0.1}     # X exits today, and F flips to a long
    stops = plan.stop_orders(held, weights, positions, bars)
    assert stops == [plan.StopOrder("S", 2.0, 200.0, _d(1)), plan.StopOrder("X", 1.0, 100.0, _d(2))]


# ---------------------------------------------------------------- risk

def test_the_halt_is_at_30_percent_below_the_peak():
    assert risk.halt_reason(7_001, 10_000) is None
    assert "-30.0%" in risk.halt_reason(7_000, 10_000)


def test_alerts_for_net_gross_margin_and_a_bad_day():
    book = {"A": 6_000.0, "B": -4_000.0}
    assert risk.alerts(book, 10_000, 10_000, margin=1_000) == ["net exposure +20.0% is more than ±10%"]
    big = {"A": 13_000.0, "B": -13_000.0}
    assert len(risk.alerts(big, 10_000, None, margin=12_000)) == 2         # gross and margin
    rounded = {"A": 10_020.0, "B": -10_000.0}                              # order sizes are rounded
    assert risk.alerts(rounded, 10_000, None, margin=0) == []
    assert risk.alerts({}, 9_400, 10_000, margin=0) == ["day -6.0%"]


def test_margin_is_each_notional_over_its_max_leverage():
    assert risk.margin_needed({"A": 3_000.0, "B": -1_000.0}, {"A": 3, "B": 10}) == pytest.approx(1_100)


def test_the_ledger_check_names_each_coin_that_differs():
    assert risk.ledger_mismatch({"A": 1.0, "B": -2.0}, {"A": 1.0, "B": -2.0}) is None
    assert risk.ledger_mismatch({"A": 1.0, "C": 3.0}, {"A": 1.5}).endswith("A, C")


def test_planned_net_adds_the_orders_to_the_held_book():
    orders = [plan.Order("A", 1.0, 0.1), plan.Order("B", -1.0, 0.0)]
    assert risk.planned_net({"B": 1.0}, orders, {"A": 100.0, "B": 50.0}, 1_000) == pytest.approx(0.10)


# ---------------------------------------------------------------- the ledger

def test_positions_and_cash_are_the_sum_of_the_fills(conn):
    ledger.record_fill(conn, _d(0), "t", "A", "rebalance", 10.0, 100.0, 100.1, 0.45)
    ledger.record_fill(conn, _d(1), "t", "A", "rebalance", -10.0, 110.0, 109.9, 0.49)
    ledger.record_fill(conn, _d(1), "t", "B", "rebalance", -2.0, 50.0, 49.9, 0.05)
    ledger.record_funding(conn, _d(1), "A", 10.0, 105.0, 1.0)
    assert ledger.held(conn) == {"B": -2.0}
    assert ledger.cash(conn, 10_000) == pytest.approx(10_000 - 1001 + 1099 + 99.8 - 0.99 - 1.0)


def test_a_failed_day_runs_again_and_a_done_day_does_not(conn):
    ledger.start(conn, _d(0), "t0")
    ledger.finish(conn, _d(0), "t1", "failed", error="boom")
    assert not ledger.day_done(conn, _d(0))
    ledger.start(conn, _d(0), "t2")
    ledger.finish(conn, _d(0), "t3", "done", 10_500.0, 3, 4)
    assert ledger.day_done(conn, _d(0)) and ledger.first_day(conn) == _d(0)
    assert ledger.peak_equity(conn) == 10_500 and ledger.previous_equity(conn, _d(1)) == 10_500


def test_halts_stay_until_cleared(conn):
    ledger.halt(conn, "t0", "drawdown")
    assert ledger.active_halt(conn)["reason"] == "drawdown"
    assert ledger.clear_halts(conn, "t1") == 1 and ledger.active_halt(conn) is None


def test_stops_and_the_limit_fill_rate(conn):
    a = ledger.record_order(conn, _d(0), "t", "A", "limit", 10.0, 99.0, 100.0)
    ledger.record_order(conn, _d(0), "t", "B", "limit", -10.0, 101.0, 100.0)
    ledger.record_fill(conn, _d(0), "t", "A", "rebalance", 10.0, 100.0, 99.0, 0.15, order_id=a)
    ledger.set_status(conn, a, "filled")
    ledger.cancel_open(conn)
    assert ledger.limit_fill_rate(conn) == pytest.approx(0.5)
    ledger.record_fill(conn, _d(2), "t", "S", "stop", 2.0, 150.0, 150.0, 0.1, entry=_d(1))
    assert ledger.stopped(conn) == {("S", _d(1))}


def test_cost_and_funding_measurements(conn):
    ledger.record_fill(conn, _d(0), "t", "A", "rebalance", 10.0, 100.0, 99.9, 0.15)       # maker: below the mid
    ledger.record_fill(conn, _d(0), "t", "B", "rebalance", -10.0, 100.0, 100.1, 0.15)
    [cost] = ledger.cost_per_side(conn)
    assert cost["slippage"] == pytest.approx(-0.001) and cost["fee_rate"] == pytest.approx(0.00015)
    ledger.record_funding(conn, _d(1), "A", 10.0, 100.0, 1000 * 0.09 / 365)
    ledger.record_funding(conn, _d(1), "B", -10.0, 100.0, -1000 * 0.065 / 365)
    assert {r["side"]: round(r["apr"], 6) for r in ledger.funding_apr(conn)} == {"long": 0.09, "short": 0.065}


def _ms(day: date, hour: int = 1) -> int:
    return int(datetime(day.year, day.month, day.day, hour, tzinfo=timezone.utc).timestamp() * 1000)


def test_an_exchange_fill_takes_its_kind_from_the_order_and_is_added_once(conn):
    ledger.record_order(conn, _d(0), "t", "S", "stop", 2.0, 150.0, 150.0, entry=_d(0), oid=7)
    fill = {"coin": "S", "px": "151", "sz": "2", "side": "B", "time": _ms(_d(1)), "fee": "0.1", "oid": 7, "tid": 1}
    ledger.record_exchange_fill(conn, fill)
    ledger.record_exchange_fill(conn, fill)
    ledger.record_exchange_fill(conn, {**fill, "oid": 99, "tid": 2, "side": "A"})           # not our order
    rows = [tuple(r) for r in conn.execute("SELECT kind, size, mid, entry FROM fills ORDER BY id")]
    assert rows == [("stop", 2.0, 150.0, "2026-11-01"), ("other", -2.0, 151.0, None)]
    assert ledger.last_fill_ms(conn) == _ms(_d(1))


# ---------------------------------------------------------------- the live broker (a fake exchange)

class FakeInfo:
    def __init__(self):
        self.positions: dict[str, float] = {}
        self.resting: list[dict] = []
        self.fills: list[dict] = []
        self.funding: list[dict] = []

    def user_state(self, account):
        return {"assetPositions": [{"position": {"coin": c, "szi": str(s)}} for c, s in self.positions.items()],
                "marginSummary": {"accountValue": "123.45"}}

    def open_orders(self, account):
        return self.resting

    def user_fills_by_time(self, account, start):
        return [f for f in self.fills if f["time"] >= start]

    def user_funding_history(self, account, start, end):
        return self.funding


class FakeExchange:
    """Rests each order with a new oid, and rejects each order on coin R."""

    def __init__(self):
        self.info = FakeInfo()
        self.sent: list[dict] = []
        self.cancelled: list[dict] = []

    def bulk_orders(self, requests):
        self.sent += requests
        statuses = [{"error": "Post only order would have immediately matched"} if r["coin"] == "R"
                    else {"resting": {"oid": 100 + len(self.sent) + i}} for i, r in enumerate(requests)]
        return {"status": "ok", "response": {"type": "order", "data": {"statuses": statuses}}}

    def bulk_cancel(self, requests):
        self.cancelled += requests
        return {"status": "ok", "response": {"type": "cancel", "data": {"statuses": ["success"] * len(requests)}}}


@pytest.fixture
def exchange():
    return FakeExchange()


def test_live_orders_are_post_only_at_the_touch_and_a_close_is_reduce_only(conn, exchange):
    broker = live.LiveBroker(conn, exchange, "0xabc")
    books = {"A": ([(9.9, 1.0)], [(10.1, 1.0)]), "B": ([(4.9, 1.0)], [(5.1, 1.0)]), "R": ([(1.0, 1.0)], [(1.1, 1.0)])}
    orders = [plan.Order("A", 2.0, 0.1), plan.Order("B", -1.0, 0.0), plan.Order("R", 5.0, 0.1)]
    problems = broker.place(_d(0), orders, books)
    assert [(r["coin"], r["is_buy"], r["sz"], r["limit_px"], r["reduce_only"]) for r in exchange.sent] == [
        ("A", True, 2.0, 9.9, False), ("B", False, 1.0, 5.1, True), ("R", True, 5.0, 1.0, False)]
    assert all(r["order_type"] == {"limit": {"tif": "Alo"}} for r in exchange.sent)
    assert problems == ["R: Post only order would have immediately matched"]
    rows = [tuple(r) for r in conn.execute("SELECT symbol, status, mid FROM orders ORDER BY id")]
    assert rows == [("A", "open", 10.0), ("B", "open", 5.0), ("R", "rejected", 1.05)]


def test_live_stops_are_reduce_only_stop_market_buys(conn, exchange):
    broker = live.LiveBroker(conn, exchange, "0xabc")
    broker.place_stops(_d(0), [plan.StopOrder("S", 3.0, 0.123456789, _d(0))], {"S": 0})
    [r] = exchange.sent
    assert r["limit_px"] == 0.12346 and r["reduce_only"] and r["is_buy"]
    assert r["order_type"] == {"trigger": {"triggerPx": 0.12346, "isMarket": True, "tpsl": "sl"}}


def test_live_sync_cancels_the_resting_orders_then_records_fills_and_funding(conn, exchange):
    broker = live.LiveBroker(conn, exchange, "0xabc")
    ledger.start(conn, _d(0), "t")
    broker.place(_d(0), [plan.Order("A", 2.0, 0.1)], {"A": ([(9.9, 1.0)], [(10.1, 1.0)])})
    oid = conn.execute("SELECT oid FROM orders").fetchone()[0]
    exchange.info.resting = [{"coin": "A", "oid": oid}]
    exchange.info.fills = [{"coin": "A", "px": "9.9", "sz": "1", "side": "B", "time": _ms(_d(0), 5),
                            "fee": "0.0015", "oid": oid, "tid": 11}]
    exchange.info.funding = [{"time": _ms(_d(1), h), "delta": {"coin": "A", "usdc": "-0.01", "szi": "1.0"}}
                             for h in (1, 2)]
    asyncio.run(broker.sync(None, AppConfig(), _d(1), {}, {"A": 10.0}))
    assert exchange.cancelled == [{"coin": "A", "oid": oid}]
    assert ledger.open_orders(conn) == [] and ledger.held(conn) == {"A": 1.0}
    assert tuple(conn.execute("SELECT kind, mid FROM fills").fetchone()) == ("rebalance", 10.0)
    assert conn.execute("SELECT amount FROM funding").fetchone()[0] == pytest.approx(0.02)


def test_live_positions_and_equity_come_from_the_exchange(conn, exchange):
    exchange.info.positions = {"A": 1.5, "B": -2.0, "C": 0.0}
    broker = live.LiveBroker(conn, exchange, "0xabc")
    assert broker.held() == {"A": 1.5, "B": -2.0} and broker.equity({}) == 123.45


def test_a_refused_request_stops_the_run(conn, exchange):
    exchange.bulk_orders = lambda requests: {"status": "err", "response": "bad signature"}
    with pytest.raises(RuntimeError, match="refused"):
        live.LiveBroker(conn, exchange, "0xabc").place(_d(0), [plan.Order("A", 2.0, 0.1)],
                                                       {"A": ([(9.9, 1.0)], [(10.1, 1.0)])})


def test_prices_are_rounded_as_hyperliquid_requires():
    assert live.round_px(12345.678, 2) == 12346.0
    assert live.round_px(0.000123456, 0) == 0.000123


# ---------------------------------------------------------------- the daily run on paper

DAY = date(2026, 11, 6)


@pytest.fixture
def market(monkeypatch):
    """Core perps at $100 with candles to DAY + 1. Each bar trades from 99 to 101, so
    a resting order at the touch (99.9 / 100.1) fills on the next bar. Edit
    ``market["fires"]``, or remove a coin from ``market["candles"]`` to fail its fetch."""
    state = {"symbols": ["L", "S", "X"], "candles": {"L", "S", "X"},
             "fires": {"L": [BarFire("L", DAY, "bullish", 10.0)], "S": [BarFire("S", DAY, "bearish", 10.0)]}}
    closes = [100.0] * 31
    bars = _bars(closes, DAY - timedelta(days=29), highs={k: 101.0 for k in range(31)},
                 lows={k: 99.0 for k in range(31)})

    async def core_perps(client, cfg):
        return [PerpSpec(s, 2, 5, 100.0) for s in state["symbols"]]

    async def candles(client, coins, cfg, lookback):
        return {s: bars for s in coins if s in state["candles"]}

    async def funding(client, coin, cfg, start_ms):
        return pd.DataFrame({"ts": [pd.Timestamp(DAY, tz="UTC")], "funding": [0.0001], "premium": [0.0]})

    async def book(client, coin, cfg):
        return [(99.9, 1e6)], [(100.1, 1e6)]

    monkeypatch.setattr(bot, "fetch_core_perps", core_perps)
    monkeypatch.setattr(bot, "fetch_all_candles", candles)
    monkeypatch.setattr(bot, "fetch_l2_book", book)
    monkeypatch.setattr(paper, "fetch_funding_history", funding)
    monkeypatch.setattr(target, "closed_bar_fires", lambda s, df, cfg, days: state["fires"].get(s, []))
    return state


def _run(conn, day: date, equity: float = 10_000) -> str:
    ledger.start(conn, day, "t")
    return asyncio.run(bot.rebalance(AppConfig(), conn, day, paper.PaperBroker(conn, equity)))


def test_orders_rest_for_a_day_then_fill_and_the_short_gets_its_stop(market, conn):
    text = _run(conn, DAY)
    assert "target 1 long / 1 short · held 0 long / 0 short" in text and "orders 2 limit ($2,000)" in text
    assert [tuple(r) for r in conn.execute("SELECT symbol, size, px, status FROM orders ORDER BY symbol")] == [
        ("L", 10.0, 99.9, "open"), ("S", -10.0, 100.1, "open")]
    assert ledger.held(conn) == {}

    text = _run(conn, DAY + timedelta(days=1))
    assert ledger.held(conn) == {"L": 10.0, "S": -10.0}           # the bar of DAY traded through both
    assert "orders 0 limit" in text and "1 stops" in text and "⚠️" not in text
    stop = conn.execute("SELECT symbol, size, px FROM orders WHERE kind = 'stop'").fetchone()
    assert tuple(stop) == ("S", 10.0, 200.0)                         # the close before entry x 2
    [cost] = ledger.cost_per_side(conn)
    assert cost["slippage"] == pytest.approx(-0.001) and cost["fee_rate"] == pytest.approx(plan.MAKER_FEE)


def test_a_small_account_sends_only_closes_when_the_minimum_unhedges_the_book(market, conn):
    shorts = [f"S{i}" for i in range(9)]
    market["symbols"] = market["candles"] = ["L", "M", *shorts]
    market["fires"] = {"L": [BarFire("L", DAY, "bullish", 10.0)], "M": [BarFire("M", DAY, "bullish", 10.0)],
                       **{s: [BarFire(s, DAY, "bearish", 10.0)] for s in shorts}}
    text = _run(conn, DAY, equity=100)                # longs $10 each, shorts $2.22 each
    assert "orders 0 limit" in text and "only the closes go" in text


def test_a_failed_candle_fetch_stops_the_run_before_any_order(market, conn):
    market["candles"].discard("S")
    with pytest.raises(RuntimeError, match="no candles for 1 coins: S"):
        _run(conn, DAY)
    assert ledger.open_orders(conn) == []


# ---------------------------------------------------------------- the boundary with macd_searcher

ALLOWED = {"macd_searcher.config", "macd_searcher.hyperliquid", "macd_searcher.notify", "macd_searcher.target"}


def test_the_bot_imports_only_the_boundary_of_macd_searcher():
    """The bot moves to its own repository (docs/trader_repo_plan.md). Then these
    modules are all that it can use."""
    for path in Path(plan.__file__).parent.glob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.ImportFrom):
                assert node.level <= 1, f"{path.name}: a relative import leaves the bot"
                names = [node.module or ""] if node.level == 0 else []
            elif isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            else:
                continue
            for name in names:
                assert not name.startswith("macd_searcher") or name in ALLOWED, f"{path.name}: {name}"


# ---------------------------------------------------------------- settings

@pytest.fixture
def bot_folder(monkeypatch, tmp_path):
    """A working directory with a settings file. No test reads a real ``.env``."""
    (tmp_path / "trader.yaml").write_text('db_path: "x.sqlite3"\npaper_equity_usd: 500\n', encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(settings, "load_dotenv", lambda path, override: None)
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "scanner")
    monkeypatch.delenv("TRADER_TELEGRAM_CHAT_ID", raising=False)
    return tmp_path


def test_settings_come_from_the_bot_and_the_detector_from_the_package(bot_folder):
    cfg, trader = settings.load()
    assert trader.db_path == "x.sqlite3" and trader.paper_equity_usd == 500
    assert cfg.universe_filter.min_24h_volume_usd == 300_000                # config.yaml, not the code default
    assert cfg.telegram.bot_token == "token" and cfg.telegram.chat_id == "scanner"


def test_the_bot_has_its_own_telegram_chat_when_it_is_set(bot_folder, monkeypatch):
    monkeypatch.setenv("TRADER_TELEGRAM_CHAT_ID", "bot")
    cfg, _ = settings.load()
    assert cfg.telegram.chat_id == "bot"


def test_env_is_read_from_the_working_directory(bot_folder, monkeypatch):
    seen = []
    monkeypatch.setattr(settings, "load_dotenv", lambda path, override: seen.append(path))
    settings.load()
    assert seen == [bot_folder / ".env"]
