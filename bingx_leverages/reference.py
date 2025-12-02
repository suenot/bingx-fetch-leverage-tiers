"""
Reference data utilities for leverage tier validation.
"""

import csv
import os
from typing import Dict, List, Tuple

# Path to CSV file with reference data from BingX website
_DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
CSV_PATH = os.path.join(_DATA_DIR, "tiers_from_website.csv")


def load_tiers_from_csv(csv_path: str = CSV_PATH) -> Dict[str, List[Tuple]]:
    """
    Load leverage tier data from CSV file.

    CSV format: Pair,Tier,Position (Notional Value),Max. Leverage
    Example: BTCUSDT,Tier 1,0 ~ 300000,150X

    Returns:
        Dict mapping symbol to list of (tier_num, floor, cap, leverage) tuples.
        Example: {"BTC-USDT": [(1, 0, 300000, 150), ...], ...}
    """
    tiers = {}

    if not os.path.exists(csv_path):
        return tiers

    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)

        for row in reader:
            # Parse pair: BTCUSDT -> BTC-USDT
            pair_raw = row['Pair'].strip()
            if 'USDT' in pair_raw and '-' not in pair_raw:
                pair = pair_raw.replace('USDT', '-USDT')
            else:
                pair = pair_raw

            # Parse tier number: "Tier 1" -> 1
            tier_str = row['Tier'].strip()
            tier_num = int(tier_str.replace('Tier ', ''))

            # Parse position range: "0 ~ 300000" -> (0, 300000)
            position_str = row['Position (Notional Value)'].strip()
            parts = position_str.split('~')
            floor = int(parts[0].strip())
            cap = int(parts[1].strip())

            # Parse leverage: "150X" -> 150
            leverage_str = row['Max. Leverage'].strip()
            leverage = int(leverage_str.replace('X', ''))

            # Add to dict
            if pair not in tiers:
                tiers[pair] = []
            tiers[pair].append((tier_num, floor, cap, leverage))

    # Sort tiers by tier number for each pair
    for pair in tiers:
        tiers[pair].sort(key=lambda x: x[0])

    return tiers


def get_all_leverage_values(tiers: Dict[str, List[Tuple]] = None) -> List[int]:
    """
    Extract all unique leverage values from tier data, sorted descending.

    Args:
        tiers: Tier data dict. If None, loads from CSV.

    Returns:
        List of unique leverage values in descending order.
    """
    if tiers is None:
        tiers = load_tiers_from_csv()

    leverages = set()
    for pair_tiers in tiers.values():
        for tier in pair_tiers:
            leverages.add(tier[3])  # leverage is 4th element
    return sorted(leverages, reverse=True)


def get_supported_symbols() -> List[str]:
    """
    Get list of symbols with reference data available.

    Returns:
        List of symbol strings (e.g., ["BTC-USDT", "ETH-USDT", ...])
    """
    tiers = load_tiers_from_csv()
    return sorted(tiers.keys())


def get_reference_tiers(symbol: str) -> List[Tuple]:
    """
    Get reference tier data for a specific symbol.

    Args:
        symbol: Trading pair (e.g., "BTC-USDT")

    Returns:
        List of (tier_num, floor, cap, leverage) tuples, or empty list if not found.
    """
    tiers = load_tiers_from_csv()
    return tiers.get(symbol, [])


# Pre-loaded data for quick access
REFERENCE_TIERS = load_tiers_from_csv()
ALL_LEVERAGE_VALUES = get_all_leverage_values(REFERENCE_TIERS)
