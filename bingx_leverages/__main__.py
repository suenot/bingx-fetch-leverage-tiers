"""
Command-line interface for bingx-leverages.

Usage:
    python -m bingx_leverages [SYMBOL]
    python -m bingx_leverages BTC-USDT
    python -m bingx_leverages --list
    python -m bingx_leverages --validate BTC-USDT
"""

import sys
import os
from datetime import datetime

from .client import BingXClient
from .reference import get_supported_symbols, REFERENCE_TIERS
from .validation import validate_symbol


def print_separator(title: str = ""):
    print("\n" + "=" * 70)
    if title:
        print(title)
        print("=" * 70)


def print_table_header():
    print(f"\n{'Tier':<8} {'Position (Notional Value)':<30} {'Max Lev.':<12}")
    print("-" * 55)


def main():
    args = sys.argv[1:]

    # Handle flags
    if "--list" in args or "-l" in args:
        print("Supported symbols with reference data:")
        for sym in get_supported_symbols():
            tiers = REFERENCE_TIERS[sym]
            max_lev = max(t[3] for t in tiers)
            print(f"  {sym}: {len(tiers)} tiers, max {max_lev}X")
        return

    if "--validate" in args or "-v" in args:
        args = [a for a in args if a not in ("--validate", "-v")]
        symbols = args if args else list(REFERENCE_TIERS.keys())

        client = BingXClient()
        if not client.api_key:
            print("Error: API keys required for validation")
            print("Set BINGX_API_KEY and BINGX_API_SECRET environment variables")
            return

        for symbol in symbols:
            symbol = normalize_symbol(symbol)
            validate_symbol(client, symbol)
        return

    if "--help" in args or "-h" in args:
        print(__doc__)
        return

    # Default: fetch leverage data for symbol
    symbol = args[0] if args else os.getenv("SYMBOL", "ETH-USDT")
    symbol = normalize_symbol(symbol)

    client = BingXClient()

    print(f"\n{'#' * 70}")
    print(f"# BingX Position & Leverage Data for {symbol}")
    print(f"# Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"# API Key: {'Configured' if client.api_key else 'Not configured'}")
    print(f"{'#' * 70}")

    # Contract info
    print_separator("CONTRACT INFORMATION")
    contract = client.get_contract_details(symbol)
    if contract:
        print(f"Symbol:              {contract.get('symbol', 'N/A')}")
        print(f"Max Long Leverage:   {contract.get('maxLongLeverage', 'N/A')}X")
        print(f"Max Short Leverage:  {contract.get('maxShortLeverage', 'N/A')}X")
        print(f"Price Precision:     {contract.get('pricePrecision', 'N/A')}")
        print(f"Min Trade USDT:      {contract.get('tradeMinUSDT', 'N/A')}")
    else:
        print(f"Contract {symbol} not found!")
        return

    # Market data
    print_separator("MARKET DATA")
    ticker = client.get_ticker(symbol)
    if ticker.get('code') == 0 and 'data' in ticker:
        t = ticker['data']
        print(f"Last Price:          {t.get('lastPrice', 'N/A')}")
        print(f"Mark Price:          {t.get('markPrice', 'N/A')}")
        print(f"24h Change:          {t.get('priceChangePercent', 'N/A')}%")

    # Leverage tiers
    print_separator("LEVERAGE TIERS")

    if client.api_key and client.api_secret:
        print("Discovering leverage tiers...")

        lev_info = client.get_leverage(symbol)
        current_lev = 10
        if lev_info.get('code') == 0 and 'data' in lev_info:
            current_lev = lev_info['data'].get('longLeverage', 10)

        tiers = client.discover_leverage_tiers(symbol, restore_leverage=current_lev)

        if tiers:
            print(f"Discovered {len(tiers)} tier boundaries\n")
            print(f"{'Tier':<8} {'Position (Notional Value)':<35} {'Max Leverage':<15}")
            print("-" * 60)

            for i, tier in enumerate(tiers):
                lev = tier['leverage']
                cap = tier['max_position_val']
                floor = 0 if i == 0 else tiers[i - 1]['max_position_val']
                print(f"Tier {i + 1:<3} {floor:>12,.0f} ~ {cap:<18,.0f} {lev}X")
        else:
            print("Could not discover tiers")
    else:
        print("API keys not configured")
        print("Set BINGX_API_KEY and BINGX_API_SECRET to discover tiers")

        if symbol in REFERENCE_TIERS:
            print(f"\nReference data for {symbol}:")
            print_table_header()
            for tier_num, floor, cap, lev in REFERENCE_TIERS[symbol]:
                print(f"Tier {tier_num:<3} {floor:>12,} ~ {cap:<14,} {lev}X")

    print_separator()
    print("COMPLETE!")


def normalize_symbol(symbol: str) -> str:
    """Normalize symbol format to BTC-USDT style."""
    symbol = symbol.upper()
    if "/" in symbol:
        symbol = symbol.replace("/", "-")
    if "USDT" in symbol and "-" not in symbol:
        symbol = symbol.replace("USDT", "-USDT")
    return symbol


if __name__ == "__main__":
    main()
