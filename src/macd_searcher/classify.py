"""Asset-class classification for logging/analytics.

Core perps (no DEX prefix) are crypto. HIP-3 perps carry a `dex:` prefix
(e.g. `xyz:TSLA`); we sub-classify those by their base symbol. The lookup sets
are heuristic and easily extended as the `xyz` DEX lists new markets — an
unrecognized prefixed symbol defaults to "equity", which is the most common
case on that DEX.
"""

from __future__ import annotations

_COMMODITIES = {
    "GOLD", "SILVER", "COPPER", "ALUMINIUM", "ALUMINUM", "PLATINUM", "PALLADIUM",
    "BRENTOIL", "CL", "WTI", "NATGAS", "CORN", "WHEAT", "SOYBEAN", "SUGAR",
    "COFFEE", "COCOA", "COTTON",
}
_FX = {
    "EUR", "GBP", "JPY", "AUD", "CAD", "CHF", "NZD", "CNH", "DXY", "MXN",
    "SEK", "NOK",
}
_INDICES = {"XYZ100", "SP500", "NAS100", "US30", "DJI", "NDX"}


def classify_asset(symbol: str) -> str:
    """Return one of: crypto | equity | commodity | fx | index."""
    if ":" not in symbol:
        return "crypto"
    base = symbol.split(":", 1)[1].upper()
    if base in _COMMODITIES:
        return "commodity"
    if base in _FX:
        return "fx"
    if base in _INDICES:
        return "index"
    return "equity"
