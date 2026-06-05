"""Entrypoint: `python -m macd_searcher` (or `macd-searcher` from the venv).

Runs one scan-and-notify cycle and exits. Cron handles cadence.

Exit codes:
  0   success (signals sent or correctly suppressed by quiet hours / dry-run)
  1   unhandled exception
  2   bad CLI arguments or config (handled by argparse)
  130 interrupted by Ctrl-C
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import sqlite3
import sys
import time
import traceback
import uuid
from datetime import datetime, timezone

from . import db
from .config import AppConfig, load_config
from .hyperliquid import fetch_universe_and_candles
from .notify import send_raw_text, send_signals
from .signals import compute_all_metrics, evaluate_all


log = logging.getLogger("macd_searcher")


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _config_snapshot(cfg: AppConfig) -> tuple[str, str]:
    """Return (config_json, config_hash), excluding telegram secrets."""
    dump = cfg.model_dump(mode="json", exclude={"telegram"})
    config_json = json.dumps(dump, sort_keys=True, default=str)
    config_hash = hashlib.sha256(config_json.encode("utf-8")).hexdigest()[:16]
    return config_json, config_hash


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="macd-searcher",
        description="Scan Hyperliquid perps for MACD zero-line approaches and alert via Telegram.",
    )
    p.add_argument(
        "-c", "--config",
        default=None,
        metavar="PATH",
        help="Path to config.yaml. Overrides MACD_SEARCHER_CONFIG and the project default.",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Force notify.dry_run=true regardless of config: print the message instead of sending.",
    )
    p.add_argument(
        "--log-level",
        default=None,
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Override config.log_level for this run.",
    )
    p.add_argument(
        "--no-db",
        action="store_true",
        help="Disable SQLite logging for this run regardless of config.",
    )
    return p.parse_args(argv)


def _setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    # httpx is chatty at INFO; cap it at WARNING.
    logging.getLogger("httpx").setLevel(logging.WARNING)


async def _run_once(
    cfg: AppConfig,
    conn: sqlite3.Connection | None = None,
    run_id: str | None = None,
    started_at: str | None = None,
) -> None:
    started = time.perf_counter()
    assets, candles, universe_total = await fetch_universe_and_candles(cfg)
    signals = evaluate_all(candles, cfg)

    # Per-asset snapshots (every asset, fired or not) — best-effort.
    if conn is not None and run_id is not None:
        try:
            metrics = compute_all_metrics(candles, cfg)
            db.insert_snapshots(conn, run_id, {a.name: a for a in assets}, metrics)
        except Exception:
            log.exception("Failed to write asset_snapshots")

    status = await send_signals(signals, scanned_count=len(candles), cfg=cfg)

    if conn is not None and run_id is not None:
        try:
            db.insert_signals(conn, run_id, signals, started_at or _now_iso())
            db.finalize_run(
                conn, run_id,
                completed_at=_now_iso(),
                duration_s=time.perf_counter() - started,
                universe_total=universe_total,
                universe_kept=len(assets),
                signals_count=len(signals),
                notify_status=status,
            )
        except Exception:
            log.exception("Failed to write signals / finalize run row")

    log.info("Scan complete in %.2fs (%d assets, %d signals, notify=%s)",
             time.perf_counter() - started, len(candles), len(signals), status)


async def _try_send_error_alert(cfg: AppConfig, exc: BaseException) -> None:
    """Best-effort one-shot Telegram alert when the run blows up.

    Silent if Telegram isn't configured or the send itself fails — we already
    logged the original exception.
    """
    if not cfg.telegram.configured or cfg.notify.dry_run:
        return
    body = "🛑 macd_searcher run failed\n\n" + "".join(
        traceback.format_exception_only(type(exc), exc)
    ).strip()
    try:
        await send_raw_text(body, cfg)
    except Exception:
        log.exception("Failed to send error alert to Telegram")


def main(argv: list[str] | None = None) -> int:
    # Windows consoles default to cp1252 which can't encode the emoji glyphs
    # in our Telegram message body. Linux/VPS already defaults to utf-8.
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    except (AttributeError, ValueError):
        pass

    args = _parse_args(argv)

    try:
        cfg = load_config(args.config)
    except Exception as exc:
        print(f"Failed to load config: {exc}", file=sys.stderr)
        return 2

    if args.dry_run:
        cfg = cfg.model_copy(update={
            "notify": cfg.notify.model_copy(update={"dry_run": True}),
        })
    if args.log_level:
        cfg = cfg.model_copy(update={"log_level": args.log_level})

    _setup_logging(cfg.log_level)

    # Open the DB and record the run row up front (best-effort — a DB problem
    # must never prevent the scan/notify from running).
    conn: sqlite3.Connection | None = None
    run_id: str | None = None
    started_at = _now_iso()
    if cfg.database.enabled and not args.no_db:
        try:
            conn = db.connect(cfg.database.path)
            db.init_schema(conn)
            run_id = uuid.uuid4().hex
            config_json, config_hash = _config_snapshot(cfg)
            db.start_run(conn, run_id, started_at, db.git_short_sha(), config_hash, config_json)
        except Exception:
            log.exception("DB init failed; continuing without logging")
            conn = None
            run_id = None

    try:
        asyncio.run(_run_once(cfg, conn, run_id, started_at))
        return 0
    except KeyboardInterrupt:
        log.warning("Interrupted")
        return 130
    except Exception as exc:
        log.exception("Run failed")
        if conn is not None and run_id is not None:
            try:
                err = "".join(traceback.format_exception_only(type(exc), exc)).strip()
                db.finalize_run(conn, run_id, completed_at=_now_iso(),
                                notify_status="failed", error=err)
            except Exception:
                log.exception("Failed to record run failure")
        try:
            asyncio.run(_try_send_error_alert(cfg, exc))
        except Exception:
            pass
        return 1
    finally:
        if conn is not None:
            conn.close()


if __name__ == "__main__":
    sys.exit(main())
