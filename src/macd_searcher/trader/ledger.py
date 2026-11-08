"""The ledger of the trading bot: SQLite, in its own file (``trader.db_path`` on
paper, ``trader.live_db_path`` live).

The ledger has the orders that the bot sent and the fills that they got. On paper,
the positions are the sum of the fills. Live, the exchange holds the positions, and
the bot halts if they are not the sum of the fills (docs/trading_strategy.md §5).

The key of a rebalance is its UTC decision day. The bot does not trade again on a
day with the status 'done' (docs/trading_strategy.md §8.4).
"""

from __future__ import annotations

import sqlite3
from datetime import date, datetime, timezone
from pathlib import Path

from ..research.backtest import Position

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS rebalances (
    day           TEXT PRIMARY KEY,     -- the UTC decision day
    started_at    TEXT NOT NULL,
    completed_at  TEXT,
    status        TEXT NOT NULL,        -- 'started' | 'done' | 'halted' | 'failed'
    equity        REAL,                 -- before the orders
    longs         INTEGER,
    shorts        INTEGER,
    error         TEXT
);

-- The target book of each day, for the backtest replay of the same days (§8.3).
CREATE TABLE IF NOT EXISTS targets (
    day     TEXT NOT NULL,
    symbol  TEXT NOT NULL,
    leg     TEXT NOT NULL,
    entry   TEXT NOT NULL,              -- the fire day
    last    TEXT NOT NULL,              -- the position exits at the close of this day
    weight  REAL NOT NULL,              -- a fraction of equity: + long, - short
    PRIMARY KEY (day, symbol)
);

-- An order rests until it fills or until the next run cancels it.
CREATE TABLE IF NOT EXISTS orders (
    id      INTEGER PRIMARY KEY,
    day     TEXT NOT NULL,              -- the decision day
    at      TEXT NOT NULL,
    symbol  TEXT NOT NULL,
    kind    TEXT NOT NULL,              -- 'limit' | 'stop' | 'halt'
    size    REAL NOT NULL,              -- coins: + buy, - sell
    px      REAL NOT NULL,              -- the limit price, or the trigger of a stop
    mid     REAL NOT NULL,              -- the mid at the decision: the cost benchmark
    entry   TEXT,                       -- for a stop: the entry day of the short
    oid     INTEGER,                    -- the exchange order id (live only)
    status  TEXT NOT NULL,              -- 'open' | 'filled' | 'cancelled' | 'rejected'
    error   TEXT
);

CREATE TABLE IF NOT EXISTS fills (
    id        INTEGER PRIMARY KEY,
    day       TEXT NOT NULL,            -- the UTC day of the fill
    at        TEXT NOT NULL,
    symbol    TEXT NOT NULL,
    kind      TEXT NOT NULL,            -- 'rebalance' | 'stop' | 'halt' | 'other'
    size      REAL NOT NULL,            -- coins: + bought, - sold
    mid       REAL NOT NULL,            -- the mid of the decision
    px        REAL NOT NULL,
    fee       REAL NOT NULL,            -- USD
    entry     TEXT,                     -- for a stop: the entry day of the short it closed
    order_id  INTEGER REFERENCES orders (id),
    tid       INTEGER UNIQUE            -- the exchange trade id (live only)
);

-- Funding of each held coin over the day before the decision day.
CREATE TABLE IF NOT EXISTS funding (
    day     TEXT NOT NULL,
    symbol  TEXT NOT NULL,
    size    REAL NOT NULL,
    mid     REAL NOT NULL,
    amount  REAL NOT NULL,              -- USD: + paid, - received
    PRIMARY KEY (day, symbol)
);

CREATE TABLE IF NOT EXISTS halts (
    at          TEXT PRIMARY KEY,
    reason      TEXT NOT NULL,
    cleared_at  TEXT                    -- NULL while the halt is active
);
"""

# The fill kind of each order kind.
FILL_KIND = {"limit": "rebalance", "stop": "stop", "halt": "halt"}


def connect(path: str) -> sqlite3.Connection:
    if path != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA_SQL)
    return conn


def _iso_ms(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).isoformat()


# ---------------------------------------------------------------- rebalances

def day_done(conn: sqlite3.Connection, day: date) -> bool:
    row = conn.execute("SELECT status FROM rebalances WHERE day = ?", (day.isoformat(),)).fetchone()
    return row is not None and row["status"] in ("done", "halted")


def first_day(conn: sqlite3.Connection) -> date | None:
    """The day of the first run. The book opens no position from a fire before it."""
    day = conn.execute("SELECT MIN(day) FROM rebalances").fetchone()[0]
    return date.fromisoformat(day) if day else None


def start(conn: sqlite3.Connection, day: date, at: str) -> None:
    """Open the rebalance of ``day``. A failed or interrupted run of the same day
    starts again. Its fills stay, and the new orders are the difference."""
    with conn:
        conn.execute("INSERT INTO rebalances (day, started_at, status) VALUES (?, ?, 'started') "
                     "ON CONFLICT (day) DO UPDATE SET started_at = excluded.started_at, status = 'started', "
                     "error = NULL", (day.isoformat(), at))


def finish(conn: sqlite3.Connection, day: date, at: str, status: str, equity: float | None = None,
           longs: int | None = None, shorts: int | None = None, error: str | None = None) -> None:
    with conn:
        conn.execute("UPDATE rebalances SET completed_at = ?, status = ?, equity = ?, longs = ?, shorts = ?, "
                     "error = ? WHERE day = ?", (at, status, equity, longs, shorts, error, day.isoformat()))


def record_targets(conn: sqlite3.Connection, day: date, positions: dict[str, Position],
                   weights: dict[str, float]) -> None:
    with conn:
        conn.execute("DELETE FROM targets WHERE day = ?", (day.isoformat(),))
        conn.executemany("INSERT INTO targets VALUES (?, ?, ?, ?, ?, ?)",
                         [(day.isoformat(), s, p.leg, p.entry.isoformat(), p.last.isoformat(), weights.get(s, 0.0))
                          for s, p in positions.items()])


def peak_equity(conn: sqlite3.Connection) -> float | None:
    return conn.execute("SELECT MAX(equity) FROM rebalances").fetchone()[0]


def previous_equity(conn: sqlite3.Connection, day: date) -> float | None:
    row = conn.execute("SELECT equity FROM rebalances WHERE day < ? AND equity IS NOT NULL ORDER BY day DESC "
                       "LIMIT 1", (day.isoformat(),)).fetchone()
    return row["equity"] if row else None


# ---------------------------------------------------------------- orders

def record_order(conn: sqlite3.Connection, day: date, at: str, symbol: str, kind: str, size: float, px: float,
                 mid: float, entry: date | None = None, oid: int | None = None, status: str = "open",
                 error: str | None = None) -> int:
    with conn:
        cur = conn.execute("INSERT INTO orders (day, at, symbol, kind, size, px, mid, entry, oid, status, error) "
                           "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                           (day.isoformat(), at, symbol, kind, size, px, mid,
                            entry.isoformat() if entry else None, oid, status, error))
    return int(cur.lastrowid)


def open_orders(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM orders WHERE status = 'open' ORDER BY id").fetchall()


def set_status(conn: sqlite3.Connection, order_id: int, status: str) -> None:
    with conn:
        conn.execute("UPDATE orders SET status = ? WHERE id = ?", (status, order_id))


def cancel_open(conn: sqlite3.Connection) -> None:
    with conn:
        conn.execute("UPDATE orders SET status = 'cancelled' WHERE status = 'open'")


# ---------------------------------------------------------------- fills and funding

def record_fill(conn: sqlite3.Connection, day: date, at: str, symbol: str, kind: str, size: float,
                mid: float, px: float, fee: float, entry: date | None = None, order_id: int | None = None,
                tid: int | None = None) -> None:
    """Add one fill. A live fill that the ledger has already (the same ``tid``) is
    not added again."""
    with conn:
        conn.execute("INSERT OR IGNORE INTO fills (day, at, symbol, kind, size, mid, px, fee, entry, order_id, tid) "
                     "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                     (day.isoformat(), at, symbol, kind, size, mid, px, fee,
                      entry.isoformat() if entry else None, order_id, tid))


def record_exchange_fill(conn: sqlite3.Connection, f: dict) -> None:
    """Add one fill from Hyperliquid's ``userFillsByTime``. The order id tells the
    kind of the fill. A fill of an order that the bot did not send is 'other'."""
    order = conn.execute("SELECT * FROM orders WHERE oid = ?", (f["oid"],)).fetchone()
    size = float(f["sz"]) * (1 if f["side"] == "B" else -1)
    px = float(f["px"])
    at = _iso_ms(int(f["time"]))
    record_fill(conn, date.fromisoformat(at[:10]), at, f["coin"], FILL_KIND[order["kind"]] if order else "other",
                size, order["mid"] if order else px, px, float(f["fee"]),
                date.fromisoformat(order["entry"]) if order and order["entry"] else None,
                order["id"] if order else None, int(f["tid"]))


def last_fill_ms(conn: sqlite3.Connection) -> int | None:
    at = conn.execute("SELECT MAX(at) FROM fills WHERE tid IS NOT NULL").fetchone()[0]
    return int(datetime.fromisoformat(at).timestamp() * 1000) if at else None


def record_funding(conn: sqlite3.Connection, day: date, symbol: str, size: float, mid: float,
                   amount: float) -> None:
    with conn:
        conn.execute("INSERT OR IGNORE INTO funding VALUES (?, ?, ?, ?, ?)",
                     (day.isoformat(), symbol, size, mid, amount))


def funded(conn: sqlite3.Connection, day: date) -> set[str]:
    """The coins that already have a funding row for ``day``."""
    return {r["symbol"] for r in conn.execute("SELECT symbol FROM funding WHERE day = ?", (day.isoformat(),))}


def held(conn: sqlite3.Connection) -> dict[str, float]:
    """The signed size of each open position, in coins: the sum of its fills."""
    rows = conn.execute("SELECT symbol, SUM(size) AS size FROM fills GROUP BY symbol")
    # Sizes are sums of decimals, so a closed position can leave a float residue.
    return {r["symbol"]: round(r["size"], 10) for r in rows if round(r["size"], 10) != 0}


def cash(conn: sqlite3.Connection, start_equity: float) -> float:
    """The starting equity less the fills, the fees and the funding. The paper equity
    is this cash plus the value of the held positions at the mids."""
    traded = conn.execute("SELECT COALESCE(SUM(size * px + fee), 0) FROM fills").fetchone()[0]
    paid = conn.execute("SELECT COALESCE(SUM(amount), 0) FROM funding").fetchone()[0]
    return start_equity - traded - paid


def stopped(conn: sqlite3.Connection) -> set[tuple[str, date]]:
    """The (symbol, entry day) of each short that its tail stop closed."""
    return {(r["symbol"], date.fromisoformat(r["entry"]))
            for r in conn.execute("SELECT DISTINCT symbol, entry FROM fills WHERE kind = 'stop'")}


# ---------------------------------------------------------------- halts

def active_halt(conn: sqlite3.Connection) -> sqlite3.Row | None:
    return conn.execute("SELECT at, reason FROM halts WHERE cleared_at IS NULL ORDER BY at LIMIT 1").fetchone()


def halt(conn: sqlite3.Connection, at: str, reason: str) -> None:
    with conn:
        conn.execute("INSERT INTO halts (at, reason) VALUES (?, ?)", (at, reason))


def clear_halts(conn: sqlite3.Connection, at: str) -> int:
    """Restart the bot after a halt. Return the number of halts cleared."""
    with conn:
        return conn.execute("UPDATE halts SET cleared_at = ? WHERE cleared_at IS NULL", (at,)).rowcount


# ---------------------------------------------------------------- measurements (§8.3)

def cost_per_side(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """The all-in cost of each kind of fill, as a fraction of the notional traded:
    the distance from the decision mid plus the fee. A maker fill below the mid has
    a negative distance."""
    return conn.execute(
        "SELECT kind, COUNT(*) AS fills, SUM(ABS(size) * mid) AS notional, "
        "SUM((px - mid) * size) / SUM(ABS(size) * mid) AS slippage, "
        "SUM(fee) / SUM(ABS(size) * mid) AS fee_rate FROM fills WHERE size != 0 "
        "GROUP BY kind ORDER BY kind").fetchall()


def limit_fill_rate(conn: sqlite3.Connection) -> float | None:
    """The share of the size of the limit orders that filled, of the orders that the
    bot sent and that are no longer open."""
    sent = conn.execute("SELECT SUM(ABS(size)) FROM orders WHERE kind = 'limit' AND status IN ('filled', 'cancelled')"
                        ).fetchone()[0]
    filled = conn.execute("SELECT SUM(ABS(f.size)) FROM fills f JOIN orders o ON o.id = f.order_id "
                          "WHERE o.kind = 'limit' AND o.status IN ('filled', 'cancelled')").fetchone()[0]
    return (filled or 0.0) / sent if sent else None


def funding_apr(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """The funding that longs paid and shorts received, as an APR of their notional.
    Each row of the funding table is one day of one position."""
    return conn.execute(
        "SELECT CASE WHEN size > 0 THEN 'long' ELSE 'short' END AS side, COUNT(*) AS position_days, "
        "365 * SUM(amount) / SUM(size * mid) AS apr FROM funding GROUP BY side ORDER BY side").fetchall()
