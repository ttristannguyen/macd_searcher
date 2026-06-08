"""Read-only SQLite access for the dashboard API.

The dashboard must never write. We open the DB read-only so a bug can't mutate
or lock the scanner's data. WAL mode lets us read concurrently while the
scanner writes.
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

from ..config import load_config


def _project_root() -> Path:
    # src/macd_searcher/web/db.py -> parents[3] == project root
    return Path(__file__).resolve().parents[3]


def resolve_db_path() -> Path:
    """DB path from env override or config, resolved to an absolute path.

    `MACD_SEARCHER_DB_PATH` lets the local dashboard point at a copy of the DB
    pulled down from the VPS without editing config.
    """
    raw = os.environ.get("MACD_SEARCHER_DB_PATH") or load_config().database.path
    p = Path(raw)
    if not p.is_absolute():
        p = _project_root() / p
    return p


def connect(db_path: Path | None = None) -> sqlite3.Connection:
    """Open a read-only connection. Raises FileNotFoundError if the DB is absent.

    Tries a true read-only URI first; falls back to a normal connection pinned
    with `PRAGMA query_only` if the read-only+WAL combination can't open the
    shared-memory index in this environment.
    """
    path = db_path or resolve_db_path()
    if not path.exists():
        raise FileNotFoundError(str(path))

    try:
        conn = sqlite3.connect(
            f"file:{path}?mode=ro", uri=True, check_same_thread=False
        )
    except sqlite3.OperationalError:
        conn = sqlite3.connect(str(path), check_same_thread=False)
        conn.execute("PRAGMA query_only = ON")

    conn.row_factory = sqlite3.Row
    return conn
