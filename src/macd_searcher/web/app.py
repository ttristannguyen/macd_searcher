"""FastAPI app for the macd_searcher dashboard.

Serves a read-only JSON API under /api and (when built) the React app at /.
Bind to 127.0.0.1 in production and reach it via an SSH tunnel — nothing is
exposed publicly.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from . import perf, queries
from .db import connect
from .models import (
    ClassCountRow,
    DayCount,
    Health,
    LatestRun,
    NotifyStatusRow,
    PerfBucket,
    PerfClassStage,
    PerfDistribution,
    PerfHorizon,
    PerfLeadTime,
    PerfReadiness,
    PerfStageDirection,
    PerfSymbol,
    ProximityHeadroom,
    RunRow,
    SignalRow,
    StageDirectionRow,
    SymbolCountRow,
    TableCounts,
)
from .perf import Horizon, Metric, ThresholdKind

# The scan cron runs every 4h; used to judge whether the latest run is fresh.
EXPECTED_INTERVAL_SECONDS = 4 * 60 * 60

app = FastAPI(title="macd_searcher dashboard API", version="0.1.0")

# Dev only: the Vite dev server (5173) calls the API on a different port. In
# production the React build is served same-origin, so CORS is a no-op.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


def get_conn() -> Iterator[sqlite3.Connection]:
    """Per-request read-only connection. 503 if the DB doesn't exist yet."""
    try:
        conn = connect()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=f"database not found: {exc}")
    try:
        yield conn
    finally:
        conn.close()


@app.get("/api/health", response_model=Health)
def health(conn: sqlite3.Connection = Depends(get_conn)) -> Health:
    counts = queries.table_counts(conn)
    latest = queries.latest_run(conn)

    age: float | None = None
    status = "down"
    if latest:
        started = datetime.fromisoformat(latest["started_at"])
        age = (datetime.now(timezone.utc) - started).total_seconds()
        if age <= EXPECTED_INTERVAL_SECONDS * 1.5:
            status = "ok"
        elif age <= EXPECTED_INTERVAL_SECONDS * 3:
            status = "stale"
        else:
            status = "down"

    return Health(
        status=status,
        counts=TableCounts(**counts),
        latest_run=LatestRun(**latest) if latest else None,
        last_run_age_seconds=age,
        expected_interval_seconds=EXPECTED_INTERVAL_SECONDS,
    )


@app.get("/api/runs", response_model=list[RunRow])
def runs(limit: int = 20, conn: sqlite3.Connection = Depends(get_conn)) -> list[RunRow]:
    return [RunRow(**r) for r in queries.recent_runs(conn, limit)]


@app.get("/api/stats/runs-per-day", response_model=list[DayCount])
def runs_per_day(days: int = 14, conn: sqlite3.Connection = Depends(get_conn)) -> list[DayCount]:
    return [DayCount(**r) for r in queries.runs_per_day(conn, days)]


@app.get("/api/stats/notify-status", response_model=list[NotifyStatusRow])
def notify_status(conn: sqlite3.Connection = Depends(get_conn)) -> list[NotifyStatusRow]:
    return [NotifyStatusRow(**r) for r in queries.notify_status_breakdown(conn)]


@app.get("/api/signals/recent", response_model=list[SignalRow])
def recent_signals(limit: int = 50, conn: sqlite3.Connection = Depends(get_conn)) -> list[SignalRow]:
    return [SignalRow(**r) for r in queries.recent_signals(conn, limit)]


@app.get("/api/stats/by-stage-direction", response_model=list[StageDirectionRow])
def by_stage_direction(conn: sqlite3.Connection = Depends(get_conn)) -> list[StageDirectionRow]:
    return [StageDirectionRow(**r) for r in queries.by_stage_direction(conn)]


@app.get("/api/stats/by-class", response_model=list[ClassCountRow])
def by_class(conn: sqlite3.Connection = Depends(get_conn)) -> list[ClassCountRow]:
    return [ClassCountRow(**r) for r in queries.by_asset_class(conn)]


@app.get("/api/stats/top-symbols", response_model=list[SymbolCountRow])
def top_symbols(limit: int = 20, conn: sqlite3.Connection = Depends(get_conn)) -> list[SymbolCountRow]:
    return [SymbolCountRow(**r) for r in queries.top_symbols(conn, limit)]


@app.get("/api/stats/signals-per-day", response_model=list[DayCount])
def signals_per_day(days: int = 14, conn: sqlite3.Connection = Depends(get_conn)) -> list[DayCount]:
    return [DayCount(**r) for r in queries.signals_per_day(conn, days)]


@app.get("/api/stats/proximity-headroom", response_model=ProximityHeadroom)
def proximity_headroom(conn: sqlite3.Connection = Depends(get_conn)) -> ProximityHeadroom:
    return ProximityHeadroom(**queries.proximity_headroom(conn))


# ---------- performance / outcomes ----------
#
# All /api/perf endpoints read a deduped (one-per-asset-day) view of post-fix
# signals and return direction-normalized returns; see web/perf.py. Most are
# empty until outcomes mature (~14 days after firing).


@app.get("/api/perf/readiness", response_model=PerfReadiness)
def perf_readiness(conn: sqlite3.Connection = Depends(get_conn)) -> PerfReadiness:
    return PerfReadiness(**perf.readiness(conn))


@app.get("/api/perf/summary", response_model=list[PerfStageDirection])
def perf_summary(
    horizon: Horizon = "7d",
    min_n: int = 1,
    conn: sqlite3.Connection = Depends(get_conn),
) -> list[PerfStageDirection]:
    return [PerfStageDirection(**r) for r in perf.summary(conn, horizon, min_n)]


@app.get("/api/perf/by-horizon", response_model=list[PerfHorizon])
def perf_by_horizon(conn: sqlite3.Connection = Depends(get_conn)) -> list[PerfHorizon]:
    return [PerfHorizon(**r) for r in perf.by_horizon(conn)]


@app.get("/api/perf/lead-time", response_model=list[PerfLeadTime])
def perf_lead_time(conn: sqlite3.Connection = Depends(get_conn)) -> list[PerfLeadTime]:
    return [PerfLeadTime(**r) for r in perf.lead_time(conn)]


@app.get("/api/perf/by-symbol", response_model=list[PerfSymbol])
def perf_by_symbol(
    horizon: Horizon = "7d",
    min_n: int = 5,
    conn: sqlite3.Connection = Depends(get_conn),
) -> list[PerfSymbol]:
    return [PerfSymbol(**r) for r in perf.by_symbol(conn, horizon, min_n)]


@app.get("/api/perf/by-class", response_model=list[PerfClassStage])
def perf_by_class(
    horizon: Horizon = "7d",
    min_n: int = 1,
    conn: sqlite3.Connection = Depends(get_conn),
) -> list[PerfClassStage]:
    return [PerfClassStage(**r) for r in perf.by_class(conn, horizon, min_n)]


@app.get("/api/perf/thresholds", response_model=list[PerfBucket])
def perf_thresholds(
    kind: ThresholdKind = "proximity",
    horizon: Horizon = "7d",
    conn: sqlite3.Connection = Depends(get_conn),
) -> list[PerfBucket]:
    return [PerfBucket(**r) for r in perf.thresholds(conn, kind, horizon)]


@app.get("/api/perf/distribution", response_model=list[PerfDistribution])
def perf_distribution(
    metric: Metric = "ret_7d",
    min_n: int = 1,
    conn: sqlite3.Connection = Depends(get_conn),
) -> list[PerfDistribution]:
    return [PerfDistribution(**r) for r in perf.distribution(conn, metric, min_n)]


# Serve the built React app at / when it exists (production / one-port mode).
_DIST = Path(__file__).resolve().parents[3] / "frontend" / "dist"
if _DIST.is_dir():
    from fastapi.staticfiles import StaticFiles

    app.mount("/", StaticFiles(directory=str(_DIST), html=True), name="frontend")
else:
    @app.get("/")
    def root() -> dict:
        return {
            "service": "macd_searcher dashboard API",
            "docs": "/docs",
            "note": "frontend not built yet; API is live under /api",
        }


def main() -> None:
    """Console entrypoint: `macd-searcher-web`. Localhost-only by default."""
    import argparse

    import uvicorn

    p = argparse.ArgumentParser(prog="macd-searcher-web")
    p.add_argument("--host", default="127.0.0.1", help="bind address (default: localhost only)")
    p.add_argument("--port", type=int, default=8000)
    p.add_argument("--reload", action="store_true", help="dev autoreload")
    args = p.parse_args()

    uvicorn.run(
        "macd_searcher.web.app:app",
        host=args.host, port=args.port, reload=args.reload,
    )


if __name__ == "__main__":
    main()
