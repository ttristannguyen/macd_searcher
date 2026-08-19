"""Backfill outcome columns on logged signals.

Run daily (after the scan cron):  python -m macd_searcher.update_outcomes

For every signal whose outcomes aren't finalized yet, this re-fetches the
symbol's daily candles and measures what actually happened after the signal
fired: forward closes (1/3/7/14d), the best/worst excursion in the predicted
direction (MFE/MAE), and how many bars until MACD actually crossed zero.

Scope (v1): fired signals only — answers "were my alerts any good?" and
supports threshold *tightening*. Scoring non-fired `asset_snapshots` (for
counterfactual *loosening*) is a separate, larger job.

Conventions:
  - Everything anchors on the daily bar containing the signal's `fired_at` (UTC).
  - Closed bars only: the still-forming current day is dropped before scoring.
  - A signal is finalized (`outcome_updated_at` set) once `horizon_days` have
    elapsed since it fired; until then it's re-scored each run as bars complete.
  - `bars_to_zero_cross` NULL after finalization == the predicted cross never
    happened within the horizon.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import httpx
import pandas as pd

from . import db
from .config import AppConfig, load_config
from .hyperliquid import fetch_candles
from .indicators import macd as compute_macd
from .indicators import rsi as compute_rsi
from .signals import _last_bar_is_forming, _peak_vs_history


log = logging.getLogger("macd_searcher.update_outcomes")

# Days of history to pull before the earliest pending signal so MACD is warm.
_WARMUP_DAYS = 60


@dataclass
class Outcome:
    px_1d: float | None = None
    px_3d: float | None = None
    px_7d: float | None = None
    px_14d: float | None = None
    max_favorable_move_pct: float | None = None
    max_adverse_move_pct: float | None = None
    bars_to_zero_cross: int | None = None
    zero_cross_observed_at: str | None = None
    finalize: bool = False


def _bar_index_at_or_before(df: pd.DataFrame, dt: datetime) -> int | None:
    """Index of the last daily bar whose date is <= dt's date."""
    target = dt.date()
    idxs = [i for i, ts in enumerate(df["ts"]) if ts.date() <= target]
    return idxs[-1] if idxs else None


def score_signal(
    df: pd.DataFrame,
    macd_line: pd.Series,
    fired_at: datetime,
    fire_close: float | None,
    direction: str,
    horizon_days: int,
    now_dt: datetime,
) -> Outcome:
    """Compute outcomes for one signal against the symbol's closed-bar candles.

    `df` must be closed bars only (forming bar already dropped) and `macd_line`
    must share its positional index.
    """
    out = Outcome(finalize=(now_dt - fired_at) >= timedelta(days=horizon_days))

    fire_idx = _bar_index_at_or_before(df, fired_at)
    if fire_idx is None or not fire_close or fire_close <= 0:
        return out  # unscorable; finalize flag still lets the caller stop revisiting it

    fire_date = df["ts"].iloc[fire_idx].date()
    date_to_idx = {ts.date(): i for i, ts in enumerate(df["ts"])}

    # Forward closes at fixed offsets (NULL until that bar exists).
    for n, attr in ((1, "px_1d"), (3, "px_3d"), (7, "px_7d"), (14, "px_14d")):
        idx = date_to_idx.get(fire_date + timedelta(days=n))
        if idx is not None:
            setattr(out, attr, float(df["close"].iloc[idx]))

    # MFE / MAE over the completed forward window, normalized to the predicted
    # direction (favorable >= 0 means the trade worked).
    window = df.iloc[fire_idx + 1 : fire_idx + 1 + horizon_days]
    if len(window) > 0:
        hi = float(window["high"].max())
        lo = float(window["low"].min())
        if direction == "bullish":
            out.max_favorable_move_pct = (hi - fire_close) / fire_close
            out.max_adverse_move_pct = (lo - fire_close) / fire_close
        else:
            out.max_favorable_move_pct = (fire_close - lo) / fire_close
            out.max_adverse_move_pct = (fire_close - hi) / fire_close

    # Zero-line cross in the predicted direction.
    def _crossed(value: float) -> bool:
        return value >= 0 if direction == "bullish" else value <= 0

    m_fire = float(macd_line.iloc[fire_idx])
    if _crossed(m_fire):
        out.bars_to_zero_cross = 0
        out.zero_cross_observed_at = df["ts"].iloc[fire_idx].isoformat()
    else:
        for i in range(1, horizon_days + 1):
            j = fire_idx + i
            if j >= len(macd_line):
                break
            if _crossed(float(macd_line.iloc[j])):
                out.bars_to_zero_cross = i
                out.zero_cross_observed_at = df["ts"].iloc[j].isoformat()
                break

    return out


async def _score_symbol(
    client: httpx.AsyncClient,
    symbol: str,
    sigs: list,
    cfg: AppConfig,
    now_dt: datetime,
    conn,
) -> int:
    earliest = min(datetime.fromisoformat(s["fired_at"]) for s in sigs)
    start_ms = int((earliest - timedelta(days=_WARMUP_DAYS)).timestamp() * 1000)
    end_ms = int(now_dt.timestamp() * 1000)

    try:
        df = await fetch_candles(client, symbol, cfg, start_ms, end_ms)
    except Exception as exc:  # noqa: BLE001 — skip this symbol, keep going
        log.warning("Outcome candle fetch failed for %s: %s", symbol, exc)
        return 0

    if _last_bar_is_forming(df, cfg) and len(df) > 0:
        df = df.iloc[:-1].reset_index(drop=True)
    if len(df) < cfg.macd.slow + 2:
        log.warning("Not enough closed bars for %s (%d); skipping", symbol, len(df))
        return 0

    macd_line = compute_macd(
        df["close"], cfg.macd.fast, cfg.macd.slow, cfg.macd.signal
    )["macd"]

    scored = 0
    for s in sigs:
        out = score_signal(
            df, macd_line,
            datetime.fromisoformat(s["fired_at"]),
            s["fire_close"], s["direction"],
            cfg.outcomes.horizon_days, now_dt,
        )
        db.update_signal_outcome(
            conn, s["signal_id"],
            px_1d=out.px_1d, px_3d=out.px_3d, px_7d=out.px_7d, px_14d=out.px_14d,
            max_favorable_move_pct=out.max_favorable_move_pct,
            max_adverse_move_pct=out.max_adverse_move_pct,
            bars_to_zero_cross=out.bars_to_zero_cross,
            zero_cross_observed_at=out.zero_cross_observed_at,
            outcome_updated_at=now_dt.isoformat() if out.finalize else None,
        )
        scored += 1
    return scored


async def _run(cfg: AppConfig, conn) -> None:
    rows = db.fetch_pending_signals(conn)
    if not rows:
        log.info("No pending signals to score.")
        return

    by_symbol: dict[str, list] = defaultdict(list)
    for r in rows:
        by_symbol[r["symbol"]].append(r)

    now_dt = datetime.now(tz=timezone.utc)
    total = 0
    async with httpx.AsyncClient() as client:
        for symbol, sigs in by_symbol.items():
            total += await _score_symbol(client, symbol, sigs, cfg, now_dt, conn)

    finalized = conn.execute(
        "SELECT COUNT(*) FROM signals WHERE outcome_updated_at IS NOT NULL"
    ).fetchone()[0]
    log.info("Scored %d pending signal(s) across %d symbol(s); %d finalized total.",
             total, len(by_symbol), finalized)


# ---------- one-off: backfill peak-vs-history on historical signals ----------
#
# The scanner computes these at fire time from the 200-bar `hist` it holds in
# memory, but that series is never persisted (asset_snapshots stores derived
# scalars only). So the backfill re-fetches candles — one request per symbol
# covering every one of its signals — and reconstructs the fire-time view.


async def _backfill_symbol(
    client: httpx.AsyncClient,
    symbol: str,
    sigs: list,
    cfg: AppConfig,
    conn,
) -> int:
    """Recompute peak-vs-history for one symbol's signals. Returns rows written."""
    earliest = min(datetime.fromisoformat(s["fired_at"]) for s in sigs)
    latest = max(datetime.fromisoformat(s["fired_at"]) for s in sigs)
    # Reach back a full detector window before the earliest fire so the oldest
    # signal still has 200 bars of excursion history behind it.
    start_ms = int((earliest - timedelta(days=cfg.candles.lookback_days + _WARMUP_DAYS)).timestamp() * 1000)
    end_ms = int((latest + timedelta(days=1)).timestamp() * 1000)

    try:
        df = await fetch_candles(client, symbol, cfg, start_ms, end_ms)
    except Exception as exc:  # noqa: BLE001 — skip this symbol, keep going
        log.warning("Peak-context candle fetch failed for %s: %s", symbol, exc)
        return 0
    if len(df) < cfg.macd.slow + 2:
        log.warning("Not enough bars for %s (%d); skipping", symbol, len(df))
        return 0

    written = 0
    for s in sigs:
        idx = _bar_index_at_or_before(df, datetime.fromisoformat(s["fired_at"]))
        if idx is None or idx < 1 or s["fire_close"] is None:
            continue
        # Stage 1 fires mid-day on a *forming* bar, so its close was the scan-time
        # price — `fire_close` — not the settled close a later fetch returns. Splice
        # it back on to rebuild the exact series the detector saw, then trim to the
        # `lookback_days` window it could see. (This matters far less here than for
        # RSI: the detector only fires once |hist| has shrunk >=30% off its peak, so
        # the fire bar is never the peak and usually doesn't affect the result at
        # all — but it can shift the excursion boundary, and did for ~3% of signals.)
        lo = max(0, idx + 1 - cfg.candles.lookback_days)
        closes = pd.concat(
            [df["close"].iloc[lo:idx], pd.Series([float(s["fire_close"])])],
            ignore_index=True,
        )
        hist = compute_macd(closes, cfg.macd.fast, cfg.macd.slow, cfg.macd.signal)["hist"]
        ratio, pct, top_n = _peak_vs_history(hist, s["direction"])
        db.update_signal_peak_context(
            conn, s["signal_id"], ratio=ratio, pct=pct, top_n=top_n
        )
        written += 1
    conn.commit()
    return written


async def _backfill_rsi_symbol(
    client: httpx.AsyncClient,
    symbol: str,
    sigs: list,
    cfg: AppConfig,
    conn,
) -> int:
    """Recompute RSI(14) as the detector saw it, for one symbol's signals.

    The subtlety is the fire bar. Stage 1 runs mid-day with `use_forming_candle`,
    so it computed RSI on a *forming* bar whose close was the price at scan time —
    not the settled midnight close that a later candle fetch returns. Reading the
    settled bar instead misses by a median 1.6 RSI points and puts 16.5% of signals
    in a different 10-wide bucket, which would blur the very gradient this backfill
    exists to measure.

    `fire_close` is exactly that scan-time price (the detector builds `Signal.close`
    from the same bar), so splicing it onto the settled history reconstructs the
    detector's series rather than approximating it — median error drops to 0.4
    points, 3.9% bucket disagreement. The residual is EWM seeding: we warm up over
    `lookback_days` bars to match the scanner's window as closely as a later fetch
    allows.
    """
    earliest = min(datetime.fromisoformat(s["fired_at"]) for s in sigs)
    latest = max(datetime.fromisoformat(s["fired_at"]) for s in sigs)
    start_ms = int((earliest - timedelta(days=cfg.candles.lookback_days)).timestamp() * 1000)
    end_ms = int((latest + timedelta(days=1)).timestamp() * 1000)

    try:
        df = await fetch_candles(client, symbol, cfg, start_ms, end_ms)
    except Exception as exc:  # noqa: BLE001 — skip this symbol, keep going
        log.warning("RSI candle fetch failed for %s: %s", symbol, exc)
        return 0
    if len(df) < 20:
        return 0

    written = 0
    for s in sigs:
        idx = _bar_index_at_or_before(df, datetime.fromisoformat(s["fired_at"]))
        # idx < 1 leaves nothing to warm up on; fire_close is required for the splice.
        if idx is None or idx < 1 or s["fire_close"] is None:
            continue
        closes = pd.concat(
            [df["close"].iloc[:idx], pd.Series([float(s["fire_close"])])],
            ignore_index=True,
        )
        val = float(compute_rsi(closes).iloc[-1])
        db.update_signal_rsi(conn, s["signal_id"], None if pd.isna(val) else val)
        written += 1
    conn.commit()
    return written


async def _run_rsi_backfill(cfg: AppConfig, conn) -> None:
    rows = db.fetch_signals_missing_rsi(conn)
    if not rows:
        log.info("No signals missing RSI.")
        return
    by_symbol: dict[str, list] = defaultdict(list)
    for r in rows:
        by_symbol[r["symbol"]].append(r)
    log.info("Backfilling RSI for %d signal(s) across %d symbol(s)...",
             len(rows), len(by_symbol))

    total = 0
    async with httpx.AsyncClient() as client:
        for i, (symbol, sigs) in enumerate(by_symbol.items(), 1):
            total += await _backfill_rsi_symbol(client, symbol, sigs, cfg, conn)
            if i % 25 == 0:
                log.info("  ... %d/%d symbols, %d rows written", i, len(by_symbol), total)

    have = conn.execute("SELECT COUNT(fire_rsi_14) FROM signals").fetchone()[0]
    log.info("RSI backfill wrote %d row(s); %d signal(s) now carry RSI.", total, have)


async def _run_backfill(cfg: AppConfig, conn) -> None:
    rows = db.fetch_signals_missing_peak_context(conn)
    if not rows:
        log.info("No signals missing peak-vs-history context.")
        return

    by_symbol: dict[str, list] = defaultdict(list)
    for r in rows:
        by_symbol[r["symbol"]].append(r)
    log.info("Backfilling peak context for %d signal(s) across %d symbol(s)...",
             len(rows), len(by_symbol))

    total = 0
    async with httpx.AsyncClient() as client:
        for i, (symbol, sigs) in enumerate(by_symbol.items(), 1):
            total += await _backfill_symbol(client, symbol, sigs, cfg, conn)
            if i % 25 == 0:
                log.info("  ... %d/%d symbols, %d rows written", i, len(by_symbol), total)

    with_baseline = conn.execute(
        "SELECT COUNT(*) FROM signals WHERE fire_hist_top_n > 0"
    ).fetchone()[0]
    log.info("Backfill wrote %d row(s); %d signal(s) now have a peak baseline.",
             total, with_baseline)


def _setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="macd-searcher-outcomes",
        description="Backfill outcome columns on logged macd_searcher signals.",
    )
    p.add_argument("-c", "--config", default=None, metavar="PATH",
                   help="Path to config.yaml.")
    p.add_argument("--log-level", default=None,
                   choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    p.add_argument("--backfill-peak-context", action="store_true",
                   help="One-off: recompute peak-vs-history on signals that predate "
                        "those columns, instead of scoring outcomes.")
    p.add_argument("--backfill-rsi", action="store_true",
                   help="One-off: compute fire_rsi_14 on signals that predate RSI "
                        "logging, so RSI spans more than one market regime.")
    args = p.parse_args(argv)

    try:
        cfg = load_config(args.config)
    except Exception as exc:
        print(f"Failed to load config: {exc}", file=sys.stderr)
        return 2

    _setup_logging(args.log_level or cfg.log_level)

    if not cfg.database.enabled:
        log.warning("database.enabled is false; nothing to score.")
        return 0

    conn = db.connect(cfg.database.path)
    db.init_schema(conn)
    if args.backfill_peak_context:
        job = _run_backfill(cfg, conn)
    elif args.backfill_rsi:
        job = _run_rsi_backfill(cfg, conn)
    else:
        job = _run(cfg, conn)

    try:
        asyncio.run(job)
        return 0
    except KeyboardInterrupt:
        log.warning("Interrupted")
        return 130
    except Exception:
        log.exception("Outcome update failed")
        return 1
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
