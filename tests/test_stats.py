"""Unit tests for the robust stats helpers (no DB / web needed)."""

from __future__ import annotations

from macd_searcher.stats import summarize


def test_empty_returns_none():
    assert summarize([]) is None
    assert summarize([None, None]) is None


def test_symmetric_quartiles():
    s = summarize([1, 2, 3, 4, 5])
    assert s["n"] == 5
    assert s["median"] == 3.0
    assert s["mean"] == 3.0
    assert s["p25"] == 2.0
    assert s["p75"] == 4.0
    assert s["min"] == 1.0 and s["max"] == 5.0


def test_none_values_dropped():
    s = summarize([10.0, None, 20.0])
    assert s["n"] == 2
    assert s["median"] == 15.0


def test_winsor_caps_right_skew():
    # One moonshot drags the mean but not the median; winsorized sits between.
    s = summarize([0, 0, 0, 0, 100], winsor=0.1)
    assert s["median"] == 0.0
    assert s["mean"] == 20.0
    assert s["winsorized_mean"] < s["mean"]


def test_single_value_has_no_std():
    s = summarize([7.0])
    assert s["n"] == 1
    assert s["std"] is None
    assert s["median"] == 7.0
