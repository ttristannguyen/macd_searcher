"""Tests for the B3 backtester. Each rule of the book has a test on small synthetic
data. A golden test on the frozen panel pins the baseline numbers."""

from __future__ import annotations

import pickle
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from macd_searcher.research import backtest as bt
from macd_searcher.research.backtest import Fire, Position, account, target_book

D0 = date(2024, 3, 1)


def _d(k: int) -> date:
    return D0 + timedelta(days=k)


def _fire(symbol: str, leg: str | None, first: bool = True) -> Fire:
    side = 0 if leg is None else (1 if leg.startswith("L") else -1)
    return Fire(symbol, leg, side, first)


def _book(*fires: Fire) -> dict[str, Position]:
    book, _ = target_book(D0, fires, {}, listed={f.symbol for f in fires})
    return book


def _panel(tmp_path: Path, closes: dict[str, list[float]], fires=(), highs: dict | None = None) -> bt.Panel:
    """A frozen panel from daily closes. Bar k is day D0 + k - 1, so decision day D0
    trades at the close of bar 0. ``fires`` holds (symbol, decision day index,
    direction, peak_pct)."""
    start = D0 - timedelta(days=1)
    prices, coin_days = [], []
    for s, cs in closes.items():
        for k, c in enumerate(cs):
            day = (start + timedelta(days=k)).isoformat()
            prices.append(dict(symbol=s, day=day, open=c, high=(highs or {}).get((s, k), c), close=c))
            coin_days.append(dict(symbol=s, day=(start + timedelta(days=k + 1)).isoformat(), eligible=True,
                                  notional=1e6, hist=-1.0, state_pct=40.0, fire=None, red=0.5, sig_atr=-1.0))
    cd = pd.DataFrame(coin_days)
    for s, k, direction, pct in fires:
        i = cd.index[(cd.symbol == s) & (cd.day == _d(k).isoformat())]
        cd.loc[i, ["fire", "state_pct"]] = [direction, pct]
    path = tmp_path / "panel.pkl"
    path.write_bytes(pickle.dumps(dict(prices=pd.DataFrame(prices), coin_days=cd, source="test", built="test")))
    return bt.load_panel(path)


# ---------------------------------------------------------------- hold

def test_a_hold_ends_at_the_close_of_fire_day_plus_14():
    book = _book(_fire("A", "L1"))
    assert book["A"].entry == D0 and book["A"].last == _d(bt.HOLD_DAYS)
    book, _ = target_book(_d(14), [], book, {"A"})
    assert "A" in book
    book, _ = target_book(_d(15), [], book, {"A"})
    assert book == {}


def test_a_hold_earns_hold_days_plus_one_daily_returns(tmp_path):
    n = 30
    panel = _panel(tmp_path, {"A": [100 * 1.01 ** k for k in range(n)], "B": [100.0] * n},
                   fires=[("A", 0, "bullish", 10.0), ("B", 0, "bearish", 10.0)])
    run = bt.simulate(panel, bt.book_fires(panel))
    col = panel.symbols.index("A")
    assert np.count_nonzero(run.weights[:, col]) == bt.HOLD_DAYS + 1
    assert run.gross[0] == pytest.approx(0.10 * 0.01)            # 10% long, A up 1%


def test_per_leg_holds_are_an_explicit_argument():
    fires = [_fire("A", "L1"), _fire("B", "S1")]
    book, _ = target_book(D0, fires, {}, {"A", "B"}, holds={"S1": 21})
    assert book["A"].last == _d(14) and book["B"].last == _d(21)


# ---------------------------------------------------------------- sizing

def test_both_sides_are_sized_to_the_thinner_side():
    longs = [_fire(f"L{i}", "L2") for i in range(3)]
    shorts = [_fire(f"S{i}", "S2") for i in range(20)]
    _, w = target_book(D0, longs + shorts, {}, {f.symbol for f in longs + shorts})
    assert w["L0"] == pytest.approx(0.10) and w["S0"] == pytest.approx(-0.015)   # 30% a side
    assert sum(w.values()) == pytest.approx(0)


def test_a_book_with_one_side_only_holds_nothing():
    _, w = target_book(D0, [_fire("A", "L1"), _fire("B", "L2")], {}, {"A", "B"})
    assert w == {"A": 0.0, "B": 0.0}


def test_side_gross_is_at_most_100_percent():
    fires = [_fire(f"L{i}", "L1") for i in range(15)] + [_fire(f"S{i}", "S1") for i in range(12)]
    _, w = target_book(D0, fires, {}, {f.symbol for f in fires})
    assert sum(x for x in w.values() if x > 0) == pytest.approx(1.0)
    assert sum(x for x in w.values() if x < 0) == pytest.approx(-1.0)


def test_a_tilt_moves_weight_inside_a_side_and_the_cap_holds():
    fires = [_fire(f"L{i}", "L1") for i in range(3)] + [_fire(f"S{i}", "S1") for i in range(20)]
    tilt = lambda day, p: 2.0 if p.symbol == "L0" else 1.0  # noqa: E731
    _, w = target_book(D0, fires, {}, {f.symbol for f in fires}, tilt=tilt)
    assert w["L0"] == pytest.approx(0.10)            # 0.3 x 2/4 = 0.15, capped at 10%
    assert w["L1"] == pytest.approx(0.075) and w["S0"] == pytest.approx(-0.015)


def test_the_basket_fills_the_thin_side_and_nets_per_coin():
    fires = [_fire("A", "L1"), _fire("B", "L2")]
    _, w = target_book(D0, fires, {}, {"A", "B", "C", "D"}, basket=["A", "B", "C", "D"])
    assert w["C"] == pytest.approx(-0.05) and w["A"] == pytest.approx(0.10 - 0.05)
    assert sum(w.values()) == pytest.approx(0)


# ---------------------------------------------------------------- positions

def test_a_traded_first_fire_flips_or_restarts_the_position():
    book = _book(_fire("A", "L1"))
    book, _ = target_book(_d(3), [_fire("A", "S2")], book, {"A"})
    assert (book["A"].leg, book["A"].side, book["A"].entry) == ("S2", -1, _d(3))
    book, _ = target_book(_d(5), [_fire("A", "S1")], book, {"A"})
    assert (book["A"].leg, book["A"].entry, book["A"].last) == ("S1", _d(5), _d(19))


def test_a_fire_in_an_untraded_band_leaves_the_position_alone():
    book = _book(_fire("A", "L1"))
    after, _ = target_book(_d(3), [_fire("A", None)], book, {"A"})
    assert after == book


def test_only_the_first_fire_of_an_episode_opens_or_restarts():
    assert _book(_fire("A", "L1", first=False)) == {}
    book = _book(_fire("A", "L1"))
    after, _ = target_book(_d(1), [_fire("A", "L2", first=False)], book, {"A"})
    assert after == book
    after, _ = target_book(_d(1), [_fire("A", "L2", first=False)], book, {"A"}, first_only=False)
    assert after["A"].entry == _d(1)


def test_episodes_split_on_a_gap_of_more_than_one_day(tmp_path):
    fires = [("A", 0, "bullish", 10.0), ("A", 1, "bullish", 10.0), ("A", 3, "bullish", 10.0),
             ("A", 4, "bearish", 10.0)]
    panel = _panel(tmp_path, {"A": [100.0] * 10}, fires=fires)
    assert bt.book_fires(panel)["first"].tolist() == [True, False, True, True]


def test_book_fires_uses_the_leg_bands_of_the_live_book(tmp_path):
    fires = [("A", 0, "bullish", 10.0), ("B", 0, "bullish", 40.0), ("C", 0, "bearish", 80.0),
             ("D", 0, "bearish", 20.0), ("E", 0, "bullish", 75.0)]
    panel = _panel(tmp_path, {s: [100.0] * 5 for s in "ABCDE"}, fires=fires)
    f = bt.book_fires(panel).set_index("symbol")
    assert f["leg"].fillna("-").to_dict() == {"A": "L1", "B": "-", "C": "L2", "D": "S1", "E": "S2"}
    assert f["side"].to_dict() == {"A": 1, "B": 0, "C": 1, "D": -1, "E": -1}


def test_a_delisted_coin_exits_at_its_last_close(tmp_path):
    n = 20
    panel = _panel(tmp_path, {"A": [100.0] * n, "B": [100 * 1.02 ** k for k in range(6)]},
                   fires=[("A", 0, "bullish", 10.0), ("B", 0, "bearish", 10.0)])
    run = bt.simulate(panel, bt.book_fires(panel))
    col = panel.symbols.index("B")
    assert np.count_nonzero(run.weights[:, col]) == 5          # bars 1-5 are the last bars of B
    assert run.shorts[5] == 0 and run.longs[5] == 1
    assert run.gross[4] == pytest.approx(-0.10 * 0.02, rel=0.05)


def test_an_exit_rule_closes_at_the_next_rebalance(tmp_path):
    panel = _panel(tmp_path, {"A": [100.0] * 20, "B": [100.0] * 20},
                   fires=[("A", 0, "bullish", 10.0), ("B", 0, "bearish", 10.0)])
    run = bt.simulate(panel, bt.book_fires(panel), exit_rule=lambda day, p: day >= _d(3))
    assert run.longs[:3].tolist() == [1, 1, 1] and run.longs[3] == 0


def test_a_short_stop_fills_at_the_stop_and_closes_the_short(tmp_path):
    highs = {("B", 3): 160.0}                                    # bar 3 trades up to +60%
    panel = _panel(tmp_path, {"A": [100.0] * 20, "B": [100.0] * 20},
                   fires=[("A", 0, "bullish", 10.0), ("B", 0, "bearish", 10.0)], highs=highs)
    run = bt.simulate(panel, bt.book_fires(panel), short_stop=0.5)
    col = panel.symbols.index("B")
    assert run.ret[2, col] == pytest.approx(0.5)                # decision day 2 earns bar 3
    assert run.shorts[2] == 1 and run.shorts[3] == 0


# ---------------------------------------------------------------- accounting

def test_costs_apply_to_all_turnover_and_drift_is_charged():
    weights = np.array([[0.1, -0.1], [0.1, -0.1]])
    ret = np.array([[0.10, 0.0], [0.0, 0.0]])
    out = account(weights, ret)
    port = 0.1 * 0.10
    drift = abs(0.1 - 0.1 * 1.1 / (1 + port)) + abs(-0.1 + 0.1 / (1 + port))
    assert out["turnover"].tolist() == pytest.approx([0.2, drift])
    assert out["cost"].tolist() == pytest.approx([0.2 * bt.COST_PER_SIDE, drift * bt.COST_PER_SIDE])


def test_the_basket_rebalance_is_charged():
    _, w = target_book(D0, [_fire("A", "L1")], {}, {"A", "B", "C"}, basket=["B", "C"])
    cols = ["A", "B", "C"]
    weights = np.array([[w[c] for c in cols]] * 2)
    ret = np.array([[0.0, 0.2, 0.0], [0.0, 0.0, 0.0]])          # B drifts away from C
    assert account(weights, ret)["turnover"][1] > 0


def test_funding_is_flat_paid_on_longs_and_received_on_shorts():
    out = account(np.array([[0.5, -0.5]]), np.array([[0.0, 0.0]]))
    funding = (0.5 * bt.FUNDING_LONG_APR - 0.5 * bt.FUNDING_SHORT_APR) / 365
    assert out["funding"][0] == pytest.approx(funding)
    assert out["net"][0] == pytest.approx(-funding - 1.0 * bt.COST_PER_SIDE)


def test_a_drift_band_keeps_weights_inside_the_band():
    weights = np.array([[0.1, -0.1], [0.1, -0.1]])
    ret = np.array([[0.10, 0.0], [0.0, 0.0]])
    assert account(weights, ret, band=0.25)["turnover"][1] == 0
    assert account(weights, ret, band=0.01)["turnover"][1] > 0


# ---------------------------------------------------------------- inputs

def _csv(path: Path, days: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"ts": [f"{d} 00:00:00+00:00" for d in days], "open": 1.0, "high": 1.0, "low": 1.0,
                  "close": 1.0, "volume": 1.0}).to_csv(path, index=False)


def test_load_bars_never_reads_the_newest_cached_bar(tmp_path):
    days = [f"2026-10-{d:02d}" for d in range(1, 9)]
    _csv(tmp_path / "history" / "A.csv", days[:5])               # bar 5 was forming at fetch
    _csv(tmp_path / "candles" / "A.csv", days[3:])               # bar 8 was forming at fetch
    _csv(tmp_path / "history" / "B.csv", days[:5])               # no newer bars
    bars = bt.load_bars(tmp_path)
    assert bars["A"]["ts"].dt.strftime("%Y-%m-%d").tolist() == days[:7]
    assert bars["B"]["ts"].dt.strftime("%Y-%m-%d").tolist() == days[:4]


# ---------------------------------------------------------------- statistics

def test_paired_interval_of_a_book_against_itself_is_zero():
    r = np.random.default_rng(0).normal(0.001, 0.01, 400)
    assert bt.sharpe_diff_ci(r, r) == (0.0, 0.0, 0.0)


def test_intervals_are_deterministic():
    r = np.random.default_rng(0).normal(0.001, 0.01, 400)
    assert bt.sharpe_ci(r) == bt.sharpe_ci(r)


def test_period_returns_compound():
    days = [date(2024, 6, 30), date(2024, 7, 1), date(2024, 7, 2)]
    r = np.array([0.1, 0.1, -0.5])
    assert bt.period_returns(r, days, "half").to_dict() == pytest.approx({"2024H1": 0.1, "2024H2": 1.1 * 0.5 - 1})


# ---------------------------------------------------------------- golden

PANEL = Path(__file__).resolve().parents[1] / "state" / "research_cache" / bt.PANEL_FILE


@pytest.mark.skipif(not PANEL.exists(), reason="no frozen panel: run the backtester with --rebuild")
def test_the_baseline_on_the_frozen_panel_does_not_move():
    """Update these numbers only with a deliberate change to a rule or to the panel,
    and re-anchor the docs in the same change."""
    panel = bt.load_panel(PANEL)
    fires = bt.book_fires(panel)
    assert (panel.days[0], panel.days[-1], len(fires)) == (date(2023, 2, 28), date(2026, 10, 15), 26681)
    run = bt.simulate(panel, fires)
    assert bt.sharpe(run.net) == pytest.approx(1.495560, abs=1e-6)
    assert bt.cagr(run.net) == pytest.approx(0.384696, abs=1e-6)
    assert bt.max_drawdown(run.net) == pytest.approx(-0.183301, abs=1e-6)
