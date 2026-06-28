# =============================================================================
# instrument.py — Fetches the Angel One instrument master at runtime and
# resolves a stock symbol to its numeric token.
#
# WHY runtime fetch? Angel One updates this file daily before market open.
# Hardcoding tokens means they silently break after corporate actions or
# symbol changes. Always download fresh.
# =============================================================================

import json
import logging
from typing import Optional

import requests

import config

logger = logging.getLogger(__name__)


class InstrumentNotFoundError(Exception):
    """Raised when a symbol cannot be found in the Angel One master list."""
    pass


def fetch_instrument_master() -> list[dict]:
    """
    Download the Angel One instrument master JSON file at runtime.

    Returns:
        List of instrument dicts, each containing symbol, token, exchange, etc.

    Raises:
        requests.HTTPError: If the download fails.
    """
    logger.info("Downloading Angel One instrument master...")
    response = requests.get(config.INSTRUMENT_MASTER_URL, timeout=30)
    response.raise_for_status()
    instruments: list[dict] = response.json()
    logger.info(f"Loaded {len(instruments):,} instruments from master.")
    return instruments


def find_token(
    instruments: list[dict],
    symbol: str,
    exchange: str,
) -> str:
    """
    Find the numeric instrument token for a given symbol and exchange.

    Angel One uses numeric tokens (not ticker symbols) for websocket
    subscriptions. The token is different from the ISIN and changes
    occasionally — never hardcode it.

    Args:
        instruments: Full instrument list from fetch_instrument_master().
        symbol:      NSE ticker symbol, e.g. "RELIANCE".
        exchange:    Exchange string, e.g. "NSE" or "NFO".

    Returns:
        Token as a string (Angel One expects string format in subscriptions).

    Raises:
        InstrumentNotFoundError: If the symbol is not found; lists close matches.
    """
    symbol_upper = symbol.strip().upper()
    exchange_upper = exchange.strip().upper()

    # Exact match first — symbol must match AND exchange must match.
    # Many symbols exist on both NSE and NFO with different tokens.
    for inst in instruments:
        if (
            inst.get("symbol", "").upper() == symbol_upper
            and inst.get("exch_seg", "").upper() == exchange_upper
        ):
            token = inst.get("token", "")
            logger.info(
                f"Found token for {symbol_upper} on {exchange_upper}: {token}"
            )
            return str(token)

    # No exact match — find close suggestions to help the user correct typos.
    suggestions = [
        inst["symbol"]
        for inst in instruments
        if symbol_upper in inst.get("symbol", "").upper()
        and inst.get("exch_seg", "").upper() == exchange_upper
    ][:10]  # Cap at 10 suggestions

    suggestion_str = (
        f"\nDid you mean one of these? {suggestions}" if suggestions else ""
    )
    raise InstrumentNotFoundError(
        f"Symbol '{symbol_upper}' not found on {exchange_upper}.{suggestion_str}\n"
        f"Check config.py → STOCK_SYMBOL and EXCHANGE."
    )


def resolve_symbol_to_token(symbol: str, exchange: str) -> str:
    """
    Convenience wrapper: downloads master + resolves token in one call.

    Args:
        symbol:   NSE ticker symbol.
        exchange: Exchange string ("NSE" or "NFO").

    Returns:
        Instrument token as string.
    """
    instruments = fetch_instrument_master()
    return find_token(instruments, symbol, exchange)
