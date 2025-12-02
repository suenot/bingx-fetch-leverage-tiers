#!/usr/bin/env python3
"""
Test suite to compare discovered leverage tiers with BingX website data.

This module loads reference tier data from tiers_from_website.csv and compares
it against data discovered via the BingX API probing method.
"""

import csv
import os
import sys
import time
from typing import List, Dict, Tuple, Optional

# Path to CSV file with reference data from BingX website
CSV_PATH = os.path.join(os.path.dirname(__file__), "tiers_from_website.csv")


def load_tiers_from_csv(csv_path: str = CSV_PATH) -> Dict[str, List[Tuple]]:
    """
    Load leverage tier data from CSV file.

    CSV format: Pair,Tier,Position (Notional Value),Max. Leverage
    Example: BTCUSDT,Tier 1,0 ~ 300000,150X

    Returns dict: {"BTC-USDT": [(1, 0, 300000, 150), ...], ...}
    """
    tiers = {}

    if not os.path.exists(csv_path):
        print(f"⚠️  CSV file not found: {csv_path}")
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


def get_all_leverage_values(tiers: Dict[str, List[Tuple]]) -> List[int]:
    """Extract all unique leverage values from tier data, sorted descending."""
    leverages = set()
    for pair_tiers in tiers.values():
        for tier in pair_tiers:
            leverages.add(tier[3])  # leverage is 4th element
    return sorted(leverages, reverse=True)


# Load expected tiers from CSV
EXPECTED_TIERS = load_tiers_from_csv()

# Extract all leverage values we need to probe
ALL_LEVERAGE_VALUES = get_all_leverage_values(EXPECTED_TIERS)


def convert_discovered_to_expected_format(tiers: List[Dict]) -> List[Tuple]:
    """Convert discovered tiers to (tier_num, floor, cap, leverage) format."""
    result = []
    for i, tier in enumerate(tiers):
        lev = tier['leverage']
        cap = int(tier['max_position_val'])
        floor = 0 if i == 0 else int(tiers[i - 1]['max_position_val'])
        result.append((i + 1, floor, cap, lev))
    return result


def calculate_tolerance(value: float, base_tolerance: float = 0.05, min_tolerance: int = 1000) -> float:
    """
    Calculate tolerance for comparing position values.
    Uses percentage tolerance with a minimum absolute value.
    """
    return max(value * base_tolerance, min_tolerance)


def compare_tiers(expected: List[Tuple], discovered: List[Tuple], symbol: str) -> Dict:
    """
    Compare expected vs discovered tiers and return detailed comparison results.

    Matching strategy:
    1. Match by leverage value first (primary key)
    2. Compare position boundaries with tolerance
    3. Track exact matches, close matches, and mismatches
    """
    results = {
        'symbol': symbol,
        'expected_count': len(expected),
        'discovered_count': len(discovered),
        'exact_matches': [],      # Leverage + boundaries match exactly
        'close_matches': [],      # Leverage matches, boundaries within tolerance
        'mismatches': [],         # Leverage matches but boundaries differ significantly
        'missing_leverages': [],  # Expected leverage not found in discovered
        'extra_leverages': [],    # Discovered leverage not in expected
        'boundary_matches': 0,
        'total_boundaries': 0,
    }

    # Extract all cap values (tier boundaries) from expected
    expected_caps = set(t[2] for t in expected)
    discovered_caps = set(t[2] for t in discovered)

    # Count matching boundaries (with tolerance)
    for exp_cap in expected_caps:
        results['total_boundaries'] += 1
        for disc_cap in discovered_caps:
            tolerance = calculate_tolerance(exp_cap)
            if abs(disc_cap - exp_cap) <= tolerance:
                results['boundary_matches'] += 1
                break

    # Create lookup by leverage for discovered tiers
    discovered_by_lev = {t[3]: t for t in discovered}
    expected_by_lev = {t[3]: t for t in expected}

    # Check each expected tier
    for exp in expected:
        tier_num, exp_floor, exp_cap, exp_lev = exp

        if exp_lev in discovered_by_lev:
            disc = discovered_by_lev[exp_lev]
            disc_floor, disc_cap = disc[1], disc[2]

            # Calculate tolerances
            floor_tolerance = calculate_tolerance(exp_floor) if exp_floor > 0 else 1000
            cap_tolerance = calculate_tolerance(exp_cap)

            floor_diff = abs(disc_floor - exp_floor)
            cap_diff = abs(disc_cap - exp_cap)

            # Check match quality
            floor_exact = floor_diff == 0
            cap_exact = cap_diff == 0
            floor_close = floor_diff <= floor_tolerance
            cap_close = cap_diff <= cap_tolerance

            match_info = {
                'tier': tier_num,
                'leverage': exp_lev,
                'expected': (exp_floor, exp_cap),
                'discovered': (disc_floor, disc_cap),
                'floor_diff': floor_diff,
                'cap_diff': cap_diff,
            }

            if floor_exact and cap_exact:
                results['exact_matches'].append(match_info)
            elif floor_close and cap_close:
                results['close_matches'].append(match_info)
            else:
                results['mismatches'].append(match_info)
        else:
            results['missing_leverages'].append({
                'tier': tier_num,
                'leverage': exp_lev,
                'expected': (exp_floor, exp_cap),
            })

    # Check for extra discovered tiers
    for disc in discovered:
        disc_lev = disc[3]
        if disc_lev not in expected_by_lev:
            results['extra_leverages'].append({
                'leverage': disc_lev,
                'discovered': (disc[1], disc[2]),
            })

    return results


def print_comparison_results(results: Dict, verbose: bool = True):
    """Print comparison results in a readable format."""
    symbol = results['symbol']
    print(f"\n{'='*70}")
    print(f"COMPARISON: {symbol}")
    print(f"{'='*70}")
    print(f"Expected tiers: {results['expected_count']}, Discovered: {results['discovered_count']}")

    exact = results['exact_matches']
    close = results['close_matches']
    mismatches = results['mismatches']
    missing = results['missing_leverages']
    extra = results['extra_leverages']

    if exact and verbose:
        print(f"\n✓ EXACT MATCHES ({len(exact)}):")
        for m in exact:
            print(f"  Tier {m['tier']:>2} | {m['leverage']:>3}X | {m['expected'][0]:>12,} ~ {m['expected'][1]:,}")

    if close and verbose:
        print(f"\n≈ CLOSE MATCHES ({len(close)}):")
        for m in close:
            print(f"  Tier {m['tier']:>2} | {m['leverage']:>3}X")
            print(f"         Expected:   {m['expected'][0]:>12,} ~ {m['expected'][1]:,}")
            print(f"         Discovered: {m['discovered'][0]:>12,} ~ {m['discovered'][1]:,}")
            print(f"         Diff: floor={m['floor_diff']:,}, cap={m['cap_diff']:,}")

    if mismatches:
        print(f"\n⚠ MISMATCHES ({len(mismatches)}):")
        for m in mismatches:
            print(f"  Tier {m['tier']:>2} | {m['leverage']:>3}X")
            print(f"         Expected:   {m['expected'][0]:>12,} ~ {m['expected'][1]:,}")
            print(f"         Discovered: {m['discovered'][0]:>12,} ~ {m['discovered'][1]:,}")
            print(f"         Diff: floor={m['floor_diff']:,}, cap={m['cap_diff']:,}")

    if missing:
        print(f"\n✗ MISSING LEVERAGES ({len(missing)}):")
        for m in missing:
            print(f"  Tier {m['tier']:>2} | {m['leverage']:>3}X | {m['expected'][0]:>12,} ~ {m['expected'][1]:,}")

    if extra:
        print(f"\n+ EXTRA LEVERAGES ({len(extra)}):")
        for m in extra:
            print(f"         | {m['leverage']:>3}X | {m['discovered'][0]:>12,} ~ {m['discovered'][1]:,}")

    # Summary
    total = results['expected_count']
    exact_count = len(exact)
    close_count = len(close)
    matched = exact_count + close_count

    print(f"\n{'─'*40}")
    print(f"📊 ACCURACY SUMMARY:")
    print(f"   Exact matches:  {exact_count:>3}/{total} ({exact_count/total*100:.1f}%)" if total > 0 else "")
    print(f"   Close matches:  {close_count:>3}/{total} ({close_count/total*100:.1f}%)" if total > 0 else "")
    print(f"   Total matched:  {matched:>3}/{total} ({matched/total*100:.1f}%)" if total > 0 else "")

    # Boundary accuracy
    boundary_total = results['total_boundaries']
    boundary_matches = results['boundary_matches']
    boundary_acc = (boundary_matches / boundary_total * 100) if boundary_total > 0 else 0
    print(f"   Boundary match: {boundary_matches:>3}/{boundary_total} ({boundary_acc:.1f}%)")


def run_tests(symbols: List[str] = None, delay: float = 0.5, verbose: bool = True):
    """Run comparison tests for specified symbols."""
    from main import BingXClient

    client = BingXClient()

    if not client.api_key or not client.api_secret:
        print("❌ API keys not configured. Please set BINGX_API_KEY and BINGX_API_SECRET in .env")
        return None

    if symbols is None:
        symbols = list(EXPECTED_TIERS.keys())

    all_results = []

    for symbol in symbols:
        if symbol not in EXPECTED_TIERS:
            print(f"⚠ No expected data for {symbol}, skipping...")
            continue

        print(f"\n🔍 Testing {symbol}...")

        # Get current leverage to restore
        lev_info = client.get_leverage(symbol)
        current_lev = 10
        if lev_info.get('code') == 0 and 'data' in lev_info:
            current_lev = lev_info['data'].get('longLeverage', 10)

        # Get expected leverage values for this symbol to ensure we probe all of them
        expected_leverages = [t[3] for t in EXPECTED_TIERS[symbol]]

        # Discover tiers using symbol-specific leverage values
        tiers = client.discover_leverage_tiers(
            symbol,
            restore_leverage=current_lev,
            probe_values=expected_leverages
        )

        if not tiers:
            print(f"  ❌ Could not discover tiers for {symbol}")
            continue

        # Convert and compare
        discovered = convert_discovered_to_expected_format(tiers)
        expected = EXPECTED_TIERS[symbol]

        results = compare_tiers(expected, discovered, symbol)
        all_results.append(results)

        print_comparison_results(results, verbose=verbose)

        # Delay between symbols to avoid rate limiting
        if delay > 0:
            time.sleep(delay)

    # Overall summary
    print(f"\n{'='*70}")
    print("OVERALL SUMMARY")
    print(f"{'='*70}")

    if not all_results:
        print("No results to summarize.")
        return None

    total_expected = sum(r['expected_count'] for r in all_results)
    total_exact = sum(len(r['exact_matches']) for r in all_results)
    total_close = sum(len(r['close_matches']) for r in all_results)
    total_mismatches = sum(len(r['mismatches']) for r in all_results)
    total_missing = sum(len(r['missing_leverages']) for r in all_results)
    total_matched = total_exact + total_close

    print(f"Symbols tested:     {len(all_results)}")
    print(f"Total tiers:        {total_expected}")
    print(f"Exact matches:      {total_exact}")
    print(f"Close matches:      {total_close}")
    print(f"Mismatches:         {total_mismatches}")
    print(f"Missing leverages:  {total_missing}")

    if total_expected > 0:
        exact_acc = total_exact / total_expected * 100
        total_acc = total_matched / total_expected * 100
        print(f"\n📊 Exact accuracy:   {exact_acc:.1f}%")
        print(f"📊 Total accuracy:   {total_acc:.1f}%")

    return all_results


def run_offline_validation():
    """
    Validate CSV data without API calls.
    Useful for checking data integrity.
    """
    print("=" * 70)
    print("OFFLINE VALIDATION: tiers_from_website.csv")
    print("=" * 70)

    if not EXPECTED_TIERS:
        print("❌ No data loaded from CSV")
        return

    print(f"\nLoaded {len(EXPECTED_TIERS)} symbols:")

    for symbol, tiers in sorted(EXPECTED_TIERS.items()):
        leverages = [t[3] for t in tiers]
        max_lev = max(leverages)
        min_lev = min(leverages)
        max_pos = max(t[2] for t in tiers)

        print(f"\n  {symbol}:")
        print(f"    Tiers: {len(tiers)}")
        print(f"    Leverage range: {min_lev}X - {max_lev}X")
        print(f"    Max position: {max_pos:,} USDT")

        # Validate tier continuity
        for i in range(1, len(tiers)):
            prev_cap = tiers[i - 1][2]
            curr_floor = tiers[i][1]
            if prev_cap != curr_floor:
                print(f"    ⚠️  Gap between tier {i} and {i+1}: {prev_cap:,} vs {curr_floor:,}")

    print(f"\n\nAll leverage values in dataset: {sorted(ALL_LEVERAGE_VALUES, reverse=True)}")


if __name__ == "__main__":
    # Parse command line arguments
    args = sys.argv[1:]

    # Check for flags
    offline_mode = "--offline" in args or "-o" in args
    verbose = "--verbose" in args or "-v" in args
    quiet = "--quiet" in args or "-q" in args

    # Remove flags from args
    symbols = [s for s in args if not s.startswith("-")]
    symbols = [s.upper().replace('/', '-') for s in symbols]
    symbols = [s if '-' in s else s.replace('USDT', '-USDT') for s in symbols]

    if offline_mode:
        run_offline_validation()
    else:
        print("BingX Leverage Tiers Comparison Test")
        print("====================================")

        if not symbols:
            # Default: test all symbols from CSV
            symbols = list(EXPECTED_TIERS.keys())

        print(f"Testing {len(symbols)} symbols: {', '.join(symbols[:5])}{'...' if len(symbols) > 5 else ''}")
        print(f"Reference data: {CSV_PATH}")

        run_tests(symbols, verbose=not quiet)
