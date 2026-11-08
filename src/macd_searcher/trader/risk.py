"""The risk controls of docs/trading_strategy.md §5, as pure functions.

A halt closes the book and stops the bot until a person restarts it. An alert only
sends a message: in the v2 tests, soft halts that blocked entries deadlocked the book
(trading_strategy.md, appendix).
"""

from __future__ import annotations

# The account halt: 30% below the peak equity. This is a proposal (§10): about 1.6x
# B3's −18% backtest drawdown.
HALT_DRAWDOWN = 0.30

# Alerts. The target book is dollar-neutral at 1x, so it holds at most 100% of equity
# on each side (2x gross). The 0.05 above 2x is for the rounding of order sizes and for
# resizes below the minimum order. A day worse than −5% sends an alert.
MAX_NET = 0.10
MAX_GROSS = 2.05
DAILY_LOSS_ALERT = 0.05


def halt_reason(equity: float, peak: float) -> str | None:
    """The reason to halt the account, or None."""
    if equity <= (1 - HALT_DRAWDOWN) * peak:
        return f"equity ${equity:,.0f} is {equity / peak - 1:.1%} from its peak ${peak:,.0f}"
    return None


def ledger_mismatch(exchange: dict[str, float], recorded: dict[str, float]) -> str | None:
    """The reason to halt when the exchange positions are not the sum of the fills
    in the ledger (§5). On paper, the two are the same by construction."""
    coins = sorted(s for s in set(exchange) | set(recorded)
                   if abs(exchange.get(s, 0.0) - recorded.get(s, 0.0)) > 1e-9 * max(1.0, abs(exchange.get(s, 0.0))))
    if coins:
        return f"the exchange positions differ from the ledger: {', '.join(coins)}"
    return None


def planned_net(held: dict[str, float], orders: list, mids: dict[str, float], equity: float) -> float:
    """The net exposure of the book if every order fills, as a fraction of equity."""
    after = dict(held)
    for o in orders:
        after[o.symbol] = after.get(o.symbol, 0.0) + o.size
    return sum(size * mids[s] for s, size in after.items() if size) / equity


def margin_needed(notional: dict[str, float], max_leverage: dict[str, int]) -> float:
    """The initial margin of the book at each coin's maximum leverage, in USD. The
    account uses cross margin, so this is one sum for the account (§4)."""
    return sum(abs(n) / max_leverage[s] for s, n in notional.items())


def alerts(notional: dict[str, float], equity: float, prev_equity: float | None, margin: float) -> list[str]:
    """The §5 alerts for the book after the rebalance. ``notional`` is the signed
    USD value of each position."""
    out = []
    net = sum(notional.values()) / equity
    gross = sum(abs(n) for n in notional.values()) / equity
    if abs(net) > MAX_NET:
        out.append(f"net exposure {net:+.1%} is more than ±{MAX_NET:.0%}")
    if gross > MAX_GROSS:
        out.append(f"gross {gross:.2f}x is more than {MAX_GROSS:.1f}x")
    if margin > equity:
        out.append(f"margin ${margin:,.0f} is more than the equity ${equity:,.0f}")
    if prev_equity and equity / prev_equity - 1 < -DAILY_LOSS_ALERT:
        out.append(f"day {equity / prev_equity - 1:+.1%}")
    return out
