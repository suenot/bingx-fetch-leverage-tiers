"""
BingX Leverage Tiers - Discover leverage brackets for BingX perpetual futures.

Since BingX lacks a dedicated leverage bracket endpoint (unlike Binance or Bybit),
this library discovers tier boundaries by probing the API.

Example:
    >>> from bingx_leverages import BingXClient
    >>> client = BingXClient(api_key="...", api_secret="...")
    >>> tiers = client.discover_leverage_tiers("BTC-USDT")
    >>> for tier in tiers:
    ...     print(f"{tier['leverage']}X: max {tier['max_position_val']:,} USDT")

Reference data is included for 15 major trading pairs.
"""

__version__ = "0.1.0"
__author__ = "suenot"

from .client import BingXClient, LeverageTier
from .reference import (
    load_tiers_from_csv,
    get_all_leverage_values,
    get_supported_symbols,
    get_reference_tiers,
    REFERENCE_TIERS,
    ALL_LEVERAGE_VALUES,
)
from .validation import (
    compare_tiers,
    validate_symbol,
    convert_discovered_to_expected_format,
)

__all__ = [
    # Client
    "BingXClient",
    "LeverageTier",
    # Reference data
    "load_tiers_from_csv",
    "get_all_leverage_values",
    "get_supported_symbols",
    "get_reference_tiers",
    "REFERENCE_TIERS",
    "ALL_LEVERAGE_VALUES",
    # Validation
    "compare_tiers",
    "validate_symbol",
    "convert_discovered_to_expected_format",
]
