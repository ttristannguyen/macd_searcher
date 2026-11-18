"""Fetch the hourly funding of each history/ coin from 2023-12-01 to 2026-05-15.

    uv run python scripts/fetch_funding_history.py

``backtest.load_funding`` reads the files. The live cache (``funding/``) starts on
2026-05-15, so this one-off fetch stops there. A coin with a file is skipped, so a run
that stops can start again. The fetch takes about 2.5 hours: the API limits the rate of
history requests.

The window starts one month before the walk-forward sleeve (2024-01), so a trailing
funding feature has data on its first day.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import httpx
import pandas as pd

ROOT = Path("state/research_cache")
OUT = ROOT / "funding_history"
START = pd.Timestamp("2023-12-01", tz="UTC")
END = pd.Timestamp("2026-05-15", tz="UTC")
URL = "https://api.hyperliquid.xyz/info"
PAGE = 500              # fundingHistory gives at most this many rows a call
# A shorter pause gets HTTP 429 replies, and their wait costs more than the pause saves.
PAUSE_S = 0.8


def _ms(ts: pd.Timestamp) -> int:
    return int(ts.timestamp() * 1000)


def _post(client: httpx.Client, body: dict) -> list:
    for attempt in range(8):
        try:
            r = client.post(URL, json=body, timeout=30)
            if r.status_code == 200:
                return r.json()
        except httpx.HTTPError:
            pass
        time.sleep(5 * 2 ** min(attempt, 4))
    raise RuntimeError(f"fundingHistory failed 8 times: {body}")


def fetch(client: httpx.Client, coin: str, start: pd.Timestamp) -> pd.DataFrame:
    rows, since = [], _ms(start)
    while since < _ms(END):
        page = _post(client, {"type": "fundingHistory", "coin": coin, "startTime": since, "endTime": _ms(END)})
        rows.extend(page)
        time.sleep(PAUSE_S)
        if len(page) < PAGE:
            break
        since = max(int(r["time"]) for r in page) + 1
    if not rows:
        return pd.DataFrame(columns=["ts", "funding"])
    df = pd.DataFrame(rows)
    df["ts"] = pd.to_datetime(df["time"].astype("int64"), unit="ms", utc=True)
    df["funding"] = df["fundingRate"].astype(float)
    return df[["ts", "funding"]].drop_duplicates("ts").sort_values("ts")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    OUT.mkdir(parents=True, exist_ok=True)
    paths = sorted((ROOT / "history").glob("*.csv"))
    with httpx.Client() as client:
        for i, path in enumerate(paths, 1):
            out = OUT / path.name
            if out.exists():
                continue
            first = pd.Timestamp(pd.read_csv(path, usecols=["ts"], nrows=1)["ts"].iloc[0])
            first = first.tz_localize("UTC") if first.tzinfo is None else first.tz_convert("UTC")
            df = fetch(client, path.stem.replace("__", ":"), max(START, first))
            tmp = out.with_suffix(".tmp")        # a stopped run leaves no half file
            df.to_csv(tmp, index=False)
            tmp.replace(out)
            print(f"{i}/{len(paths)} {path.stem}: {len(df)} rows", flush=True)


if __name__ == "__main__":
    main()
