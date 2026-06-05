"""Diagnostic: find bars where Stage 1 / Stage 3 should fire."""

from __future__ import annotations

import numpy as np
import pandas as pd

from macd_searcher.config import AppConfig
from macd_searcher.indicators import macd as compute_macd


def show(label: str, prices: list[float]) -> None:
    cfg = AppConfig()
    s = pd.Series(prices, dtype=float)
    df = compute_macd(s, cfg.macd.fast, cfg.macd.slow, cfg.macd.signal)
    df["px"] = s.values
    df["|hist|"] = df["hist"].abs()
    df["|macd|"] = df["macd"].abs()
    df["|m|/px"] = df["|macd|"] / df["px"]
    print(f"\n=== {label} (n={len(prices)}) ===")
    print(df.tail(20).to_string())


# Stronger rally, shorter fade — keep hist positive at the end
def rally_fade(rally_n=40, b=1.0, fade_n=5):
    rally = [100.0 + b * i for i in range(rally_n)]
    last = rally[-1]
    out = list(rally)
    for k in range(fade_n):
        step = b * (1 - (k + 1) / (fade_n + 1))
        last += step
        out.append(last)
    return out


show("rally_fade(40,1,5)", rally_fade(40, 1.0, 5))
show("rally_fade(30,2,4)", rally_fade(30, 2.0, 4))

# Stage 3: long rally then long flat → MACD decays back through near-zero
prices = list(np.linspace(100, 130, 30)) + [130.0] * 60
show("rally_then_flat", prices)
