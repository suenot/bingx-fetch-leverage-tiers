"""
Validation utilities for comparing discovered tiers with reference data.
"""

from typing import List, Dict, Tuple

from .reference import REFERENCE_TIERS, load_tiers_from_csv


def convert_discovered_to_expected_format(tiers: List[Dict]) -> List[Tuple]:
    """
    Convert discovered tiers to (tier_num, floor, cap, leverage) format.

    Args:
        tiers: List of dicts with 'leverage' and 'max_position_val' keys.

    Returns:
        List of (tier_num, floor, cap, leverage) tuples.
    """
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
    1. Primary: Match by position boundaries (cap values)
    2. Secondary: Compare leverage values for matched boundaries
    3. Track exact matches, close matches, and mismatches

    Args:
        expected: List of (tier_num, floor, cap, leverage) tuples from reference.
        discovered: List of (tier_num, floor, cap, leverage) tuples from API.
        symbol: Symbol being compared.

    Returns:
        Dict with comparison results including matches, mismatches, and accuracy metrics.
    """
    results = {
        'symbol': symbol,
        'expected_count': len(expected),
        'discovered_count': len(discovered),
        'exact_matches': [],
        'close_matches': [],
        'mismatches': [],
        'missing_leverages': [],
        'extra_leverages': [],
        'boundary_matches': 0,
        'total_boundaries': 0,
        'boundary_exact': 0,
    }

    discovered_by_cap = {t[2]: t for t in discovered}
    expected_by_lev = {t[3]: t for t in expected}

    for exp in expected:
        tier_num, exp_floor, exp_cap, exp_lev = exp
        results['total_boundaries'] += 1

        if exp_cap in discovered_by_cap:
            disc = discovered_by_cap[exp_cap]
            disc_floor, disc_cap, disc_lev = disc[1], disc[2], disc[3]
            results['boundary_exact'] += 1
            results['boundary_matches'] += 1

            match_info = {
                'tier': tier_num,
                'leverage': exp_lev,
                'discovered_leverage': disc_lev,
                'expected': (exp_floor, exp_cap),
                'discovered': (disc_floor, disc_cap),
                'floor_diff': abs(disc_floor - exp_floor),
                'cap_diff': 0,
                'leverage_match': exp_lev == disc_lev,
            }

            if exp_lev == disc_lev and disc_floor == exp_floor:
                results['exact_matches'].append(match_info)
            else:
                results['close_matches'].append(match_info)
        else:
            found = False
            for disc in discovered:
                disc_floor, disc_cap, disc_lev = disc[1], disc[2], disc[3]
                tolerance = calculate_tolerance(exp_cap)
                if abs(disc_cap - exp_cap) <= tolerance:
                    found = True
                    results['boundary_matches'] += 1

                    match_info = {
                        'tier': tier_num,
                        'leverage': exp_lev,
                        'discovered_leverage': disc_lev,
                        'expected': (exp_floor, exp_cap),
                        'discovered': (disc_floor, disc_cap),
                        'floor_diff': abs(disc_floor - exp_floor),
                        'cap_diff': abs(disc_cap - exp_cap),
                        'leverage_match': exp_lev == disc_lev,
                    }
                    results['close_matches'].append(match_info)
                    break

            if not found:
                results['mismatches'].append({
                    'tier': tier_num,
                    'leverage': exp_lev,
                    'expected': (exp_floor, exp_cap),
                })

    discovered_by_lev = {t[3]: t for t in discovered}
    for exp in expected:
        tier_num, exp_floor, exp_cap, exp_lev = exp
        if exp_lev not in discovered_by_lev:
            results['missing_leverages'].append({
                'tier': tier_num,
                'leverage': exp_lev,
                'expected': (exp_floor, exp_cap),
            })

    for disc in discovered:
        disc_lev = disc[3]
        if disc_lev not in expected_by_lev:
            results['extra_leverages'].append({
                'leverage': disc_lev,
                'discovered': (disc[1], disc[2]),
            })

    return results


def validate_symbol(client, symbol: str, verbose: bool = True) -> Dict:
    """
    Validate discovered tiers against reference data for a symbol.

    Args:
        client: BingXClient instance with API credentials.
        symbol: Trading pair to validate (e.g., "BTC-USDT").
        verbose: Whether to print detailed output.

    Returns:
        Comparison results dict.
    """
    if symbol not in REFERENCE_TIERS:
        if verbose:
            print(f"No reference data for {symbol}")
        return None

    # Get current leverage to restore
    lev_info = client.get_leverage(symbol)
    current_lev = 10
    if lev_info.get('code') == 0 and 'data' in lev_info:
        current_lev = lev_info['data'].get('longLeverage', 10)

    # Discover tiers
    tiers = client.discover_leverage_tiers(symbol, restore_leverage=current_lev)

    if not tiers:
        if verbose:
            print(f"Could not discover tiers for {symbol}")
        return None

    discovered = convert_discovered_to_expected_format(tiers)
    expected = REFERENCE_TIERS[symbol]

    results = compare_tiers(expected, discovered, symbol)

    if verbose:
        print_comparison_results(results)

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

    if exact and verbose:
        print(f"\n EXACT MATCHES ({len(exact)}):")
        for m in exact:
            print(f"  Tier {m['tier']:>2} | {m['leverage']:>3}X | {m['expected'][0]:>12,} ~ {m['expected'][1]:,}")

    if close and verbose:
        print(f"\n BOUNDARY MATCHES ({len(close)}):")
        for m in close:
            lev_indicator = "=" if m.get('leverage_match') else "!="
            disc_lev = m.get('discovered_leverage', '?')
            print(f"  Tier {m['tier']:>2} | {m['leverage']:>3}X {lev_indicator} {disc_lev}X | cap={m['expected'][1]:,}")

    if mismatches:
        print(f"\n NO BOUNDARY MATCH ({len(mismatches)}):")
        for m in mismatches:
            print(f"  Tier {m['tier']:>2} | {m['leverage']:>3}X | {m['expected'][0]:>12,} ~ {m['expected'][1]:,}")

    # Summary
    total = results['expected_count']
    exact_count = len(exact)
    close_count = len(close)

    boundary_total = results['total_boundaries']
    boundary_matches = results['boundary_matches']
    boundary_acc = (boundary_matches / boundary_total * 100) if boundary_total > 0 else 0

    print(f"\n{'-'*40}")
    print(f"ACCURACY:")
    if total > 0:
        print(f"   Boundary match: {boundary_matches:>3}/{boundary_total} ({boundary_acc:.1f}%)")
        print(f"   Exact match:    {exact_count:>3}/{total} ({exact_count/total*100:.1f}%)")
