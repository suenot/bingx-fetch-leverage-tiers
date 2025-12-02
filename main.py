#!/usr/bin/env python3
"""
BingX Position & Leverage Tiers Fetcher
=========================================
Fetches leverage bracket/tier data for perpetual futures contracts

This script retrieves the Position & Leverage data shown at:
https://bingx.com/en/tradeInfo/perpetual/margin/ETH-USDT

Setup:
    1. Create .env file with your API keys:
       BINGX_API_KEY=your_api_key_here
       BINGX_API_SECRET=your_api_secret_here
    
    2. Install dependencies:
       pip install requests python-dotenv

Usage:
    python bingx_leverage_fetcher.py [SYMBOL]
    python bingx_leverage_fetcher.py ETH-USDT
    python bingx_leverage_fetcher.py BTC-USDT
"""

import os
import sys
import time
import hmac
import hashlib
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urlencode

import requests
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configuration from .env
BASE_URL = os.getenv("BINGX_BASE_URL", "https://open-api.bingx.com")
API_KEY = os.getenv("BINGX_API_KEY", "")
API_SECRET = os.getenv("BINGX_API_SECRET", "")
DEFAULT_SYMBOL = os.getenv("SYMBOL", "ETH-USDT")


@dataclass
class LeverageTier:
    """Represents a single leverage tier"""
    tier: int
    notional_floor: float
    notional_cap: float
    max_leverage: int
    maint_margin_rate: float = 0.0
    cum: float = 0.0


class BingXClient:
    """BingX API Client with authentication support"""
    
    def __init__(self, api_key: str = "", api_secret: str = "", base_url: str = BASE_URL):
        self.api_key = api_key or API_KEY
        self.api_secret = api_secret or API_SECRET
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
            "X-BX-APIKEY": self.api_key
        })
    
    def _generate_signature(self, params: dict) -> str:
        """Generate HMAC SHA256 signature"""
        params_str = urlencode(sorted(params.items()))
        signature = hmac.new(
            self.api_secret.encode("utf-8"),
            params_str.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()
        return signature
    
    def _get_timestamp(self) -> int:
        """Get current timestamp in milliseconds"""
        return int(time.time() * 1000)
    
    def _request(self, method: str, endpoint: str, params: dict = None, 
                 signed: bool = False) -> dict:
        """Make API request"""
        url = f"{self.base_url}{endpoint}"
        params = params or {}
        
        if signed:
            if not self.api_key or not self.api_secret:
                return {"error": "API keys not configured. Please set BINGX_API_KEY and BINGX_API_SECRET in .env"}
            
            params["timestamp"] = self._get_timestamp()
            params["signature"] = self._generate_signature(params)
        
        try:
            if method.upper() == "GET":
                response = self.session.get(url, params=params, timeout=10)
            else:
                response = self.session.post(url, json=params, timeout=10)
            
            return response.json()
        except Exception as e:
            return {"error": str(e)}
    
    # ==================== PUBLIC ENDPOINTS ====================
    
    def get_contracts(self) -> dict:
        """Get all contract information"""
        return self._request("GET", "/openApi/swap/v2/quote/contracts")
    
    def get_contract_details(self, symbol: str) -> Optional[dict]:
        """Get specific contract details"""
        data = self.get_contracts()
        if data.get('code') == 0 and 'data' in data:
            for contract in data['data']:
                if contract.get('symbol') == symbol:
                    return contract
        return None
    
    def get_ticker(self, symbol: str) -> dict:
        """Get 24hr ticker price change statistics"""
        return self._request("GET", "/openApi/swap/v2/quote/ticker", {"symbol": symbol})
    
    def get_premium_index(self, symbol: str) -> dict:
        """Get premium index including mark price and funding rate"""
        return self._request("GET", "/openApi/swap/v2/quote/premiumIndex", {"symbol": symbol})
    
    def get_funding_rate(self, symbol: str) -> dict:
        """Get current funding rate"""
        return self._request("GET", "/openApi/swap/v2/quote/fundingRate", {"symbol": symbol})
    
    def get_depth(self, symbol: str, limit: int = 20) -> dict:
        """Get order book depth"""
        return self._request("GET", "/openApi/swap/v2/quote/depth", 
                           {"symbol": symbol, "limit": limit})
    
    def get_klines(self, symbol: str, interval: str = "1h", limit: int = 100) -> dict:
        """Get candlestick/kline data"""
        return self._request("GET", "/openApi/swap/v2/quote/klines",
                           {"symbol": symbol, "interval": interval, "limit": limit})
    
    # ==================== PRIVATE ENDPOINTS (require API key) ====================
    
    def get_margin_tiers(self, symbol: str) -> dict:
        """
        Get maintenance margin ratio tiers (requires authentication)
        Returns position tiers with maintMarginRatio from which max_leverage can be calculated
        """
        params = {"symbol": symbol}
        return self._request("GET", "/openApi/swap/v1/maintMarginRatio", params, signed=True)
    
    def get_account_balance(self) -> dict:
        """Get account balance (requires authentication)"""
        return self._request("GET", "/openApi/swap/v2/user/balance", signed=True)
    
    def get_positions(self, symbol: str = None) -> dict:
        """Get current positions (requires authentication)"""
        params = {}
        if symbol:
            params["symbol"] = symbol
        return self._request("GET", "/openApi/swap/v2/user/positions", params, signed=True)
    
    def get_leverage(self, symbol: str) -> dict:
        """Get current leverage for symbol (requires authentication)"""
        return self._request("GET", "/openApi/swap/v2/trade/leverage", 
                           {"symbol": symbol}, signed=True)
    
    def set_leverage(self, symbol: str, side: str, leverage: int) -> dict:
        """
        Set leverage for symbol (requires authentication)
        side: LONG or SHORT
        """
        # BingX requires POST with query params (not json body)
        # Must NOT send Content-Type: application/json header
        timestamp = self._get_timestamp()
        query_string = f"leverage={leverage}&side={side}&symbol={symbol}&timestamp={timestamp}"
        signature = self._generate_signature_from_string(query_string)

        url = f"{self.base_url}/openApi/swap/v2/trade/leverage?{query_string}&signature={signature}"
        try:
            # Use requests directly without session's Content-Type header
            response = requests.post(url, headers={"X-BX-APIKEY": self.api_key}, timeout=10)
            return response.json()
        except Exception as e:
            return {"error": str(e)}

    def _generate_signature_from_string(self, query_string: str) -> str:
        """Generate HMAC SHA256 signature from query string"""
        return hmac.new(
            self.api_secret.encode("utf-8"),
            query_string.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()

    def discover_leverage_tiers(
        self,
        symbol: str,
        restore_leverage: int = 10,
        probe_values: List[int] = None
    ) -> List[Dict]:
        """
        Discover leverage tiers by probing different leverage values.

        Args:
            symbol: Trading pair (e.g., "BTC-USDT")
            restore_leverage: Leverage value to restore after probing
            probe_values: Optional list of leverage values to probe.
                         If None, uses comprehensive default list.

        Returns:
            List of dicts with 'leverage' and 'max_position_val' keys,
            sorted from highest leverage to lowest.
        """
        if not self.api_key or not self.api_secret:
            return []

        # Default: comprehensive list covering all known BingX tier boundaries
        if probe_values is None:
            probe_values = [
                250, 200, 150, 125, 100, 75, 50, 40, 34, 30, 25, 20, 19, 17, 16, 15,
                14, 13, 12, 11, 10, 9, 8, 7, 6, 5, 4, 3, 2, 1
            ]
        else:
            # Ensure probe_values are sorted descending (high leverage first)
            probe_values = sorted(set(probe_values), reverse=True)

        tiers = []
        prev_max_val = None
        current_tier_lev = None

        for lev in probe_values:
            result = self.set_leverage(symbol, "LONG", lev)
            if result.get('code') == 0:
                data = result.get('data', {})
                max_val = float(data.get('maxPositionLongVal', 0))

                # Track the leverage for current tier
                if max_val != prev_max_val:
                    # New tier boundary - save previous tier if exists
                    if current_tier_lev is not None and prev_max_val is not None:
                        tiers.append({
                            'leverage': current_tier_lev,
                            'max_position_val': prev_max_val
                        })
                    current_tier_lev = lev
                    prev_max_val = max_val
                else:
                    # Same tier - update to lower leverage (this is the actual max for this tier)
                    current_tier_lev = lev

        # Don't forget the last tier
        if current_tier_lev is not None and prev_max_val is not None:
            tiers.append({
                'leverage': current_tier_lev,
                'max_position_val': prev_max_val
            })

        # Restore original leverage
        self.set_leverage(symbol, "LONG", restore_leverage)

        return tiers

    def get_leverage_tiers_with_reference(
        self,
        symbol: str,
        reference_leverages: List[int] = None
    ) -> List[Dict]:
        """
        Get leverage tiers, probing specific leverage values from reference data.

        This method is optimized for validation against known tier data:
        it probes only the leverage values that appear in reference data,
        reducing API calls and improving accuracy for exact matching.

        Args:
            symbol: Trading pair (e.g., "BTC-USDT")
            reference_leverages: List of leverage values to probe (from reference data)

        Returns:
            List of tier dicts with 'leverage' and 'max_position_val'
        """
        # Get current leverage to restore
        current_lev = 10
        lev_info = self.get_leverage(symbol)
        if lev_info.get('code') == 0 and 'data' in lev_info:
            current_lev = lev_info['data'].get('longLeverage', 10)

        return self.discover_leverage_tiers(
            symbol,
            restore_leverage=current_lev,
            probe_values=reference_leverages
        )


def print_separator(title: str = ""):
    print("\n" + "="*70)
    if title:
        print(title)
        print("="*70)


def print_table_header():
    print(f"\n{'Tier':<8} {'Position (Notional Value)':<30} {'Max Lev.':<12} {'Maint. Margin':<15}")
    print("-"*70)


def print_tier_row(tier: int, floor: float, cap: float, leverage: int, maint_margin: float = None):
    floor_str = f"{floor:,.0f}"
    cap_str = f"{cap:,.0f}"
    range_str = f"{floor_str} ~ {cap_str}"
    margin_str = f"{maint_margin:.2%}" if maint_margin is not None else "N/A"
    print(f"Tier {tier:<3} {range_str:<30} {leverage}X{'':<6} {margin_str}")


def estimate_leverage_tiers() -> List[tuple]:
    """
    Estimated leverage tiers based on typical BingX ETHUSDT structure.
    Returns list of (tier, floor, cap, max_leverage)
    """
    return [
        (1, 0, 300_000, 150),
        (2, 300_000, 800_000, 100),
        (3, 800_000, 3_000_000, 75),
        (4, 3_000_000, 12_000_000, 50),
        (5, 12_000_000, 50_000_000, 25),
        (6, 50_000_000, 65_000_000, 20),
        (7, 65_000_000, 150_000_000, 10),
        (8, 150_000_000, 320_000_000, 5),
        (9, 320_000_000, 400_000_000, 4),
        (10, 400_000_000, 530_000_000, 3),
        (11, 530_000_000, 800_000_000, 2),
        (12, 800_000_000, 1_200_000_000, 1),
    ]


def main(symbol: str = "ETH-USDT"):
    # Initialize client
    client = BingXClient()
    
    print(f"\n{'#'*70}")
    print(f"# BingX Position & Leverage Data for {symbol}")
    print(f"# Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"# API Key: {'✓ Configured' if client.api_key else '✗ Not configured'}")
    print(f"{'#'*70}")
    
    # 1. Contract Information (public + leverage from private API)
    print_separator("1. CONTRACT INFORMATION")

    contract = client.get_contract_details(symbol)

    # Get max leverage from authenticated endpoint
    max_long_leverage = None
    max_short_leverage = None
    if client.api_key and client.api_secret:
        leverage_info = client.get_leverage(symbol)
        if leverage_info.get('code') == 0 and 'data' in leverage_info:
            lev_data = leverage_info['data']
            max_long_leverage = lev_data.get('maxLongLeverage')
            max_short_leverage = lev_data.get('maxShortLeverage')

    if contract:
        print(f"Symbol:              {contract.get('symbol', 'N/A')}")
        print(f"Currency:            {contract.get('currency', 'N/A')}")
        print(f"Asset:               {contract.get('asset', 'N/A')}")
        print(f"Contract Size:       {contract.get('size', 'N/A')}")
        print(f"Max Long Leverage:   {max_long_leverage or contract.get('maxLongLeverage', 'N/A')}X")
        print(f"Max Short Leverage:  {max_short_leverage or contract.get('maxShortLeverage', 'N/A')}X")
        print(f"Price Precision:     {contract.get('pricePrecision', 'N/A')}")
        print(f"Quantity Precision:  {contract.get('quantityPrecision', 'N/A')}")
        print(f"Min Quantity:        {contract.get('tradeMinQuantity', 'N/A')}")
        print(f"Trade Min USDT:      {contract.get('tradeMinUSDT', 'N/A')}")
        print(f"Fee Rate:            {contract.get('feeRate', 'N/A')}")
        print(f"Status:              {contract.get('status', 'N/A')}")
    else:
        print(f"❌ Contract {symbol} not found!")
    
    # 2. Current Market Data (public)
    print_separator("2. CURRENT MARKET DATA")
    
    ticker = client.get_ticker(symbol)
    if ticker.get('code') == 0 and 'data' in ticker:
        t = ticker['data']
        print(f"Last Price:          {t.get('lastPrice', 'N/A')}")
        print(f"Mark Price:          {t.get('markPrice', 'N/A')}")
        print(f"Index Price:         {t.get('indexPrice', 'N/A')}")
        print(f"24h High:            {t.get('highPrice', 'N/A')}")
        print(f"24h Low:             {t.get('lowPrice', 'N/A')}")
        print(f"24h Volume:          {t.get('volume', 'N/A')}")
        print(f"24h Quote Volume:    {t.get('quoteVolume', 'N/A')}")
        print(f"24h Change %:        {t.get('priceChangePercent', 'N/A')}%")
    else:
        print(f"❌ Error: {ticker}")
    
    # 3. Funding Rate (public)
    print_separator("3. FUNDING RATE")
    
    premium = client.get_premium_index(symbol)
    if premium.get('code') == 0 and 'data' in premium:
        p = premium['data']
        print(f"Mark Price:          {p.get('markPrice', 'N/A')}")
        print(f"Index Price:         {p.get('indexPrice', 'N/A')}")
        print(f"Last Funding Rate:   {p.get('lastFundingRate', 'N/A')}")
        
        next_funding = p.get('nextFundingTime')
        if next_funding:
            try:
                next_time = datetime.fromtimestamp(int(next_funding)/1000)
                print(f"Next Funding Time:   {next_time.strftime('%Y-%m-%d %H:%M:%S')}")
            except:
                print(f"Next Funding Time:   {next_funding}")
    else:
        print(f"❌ Error: {premium}")
    
    # 4. Position & Leverage Tiers (requires auth)
    print_separator("4. POSITION & LEVERAGE TIERS")

    if client.api_key and client.api_secret:
        # Get current leverage to restore later
        current_leverage = 10
        lev_info = client.get_leverage(symbol)
        if lev_info.get('code') == 0 and 'data' in lev_info:
            current_leverage = lev_info['data'].get('longLeverage', 10)

        print("🔐 Discovering leverage tiers by probing...")
        print("   (This temporarily changes leverage settings, then restores)")

        tiers = client.discover_leverage_tiers(symbol, restore_leverage=current_leverage)

        if tiers:
            print(f"✓ Discovered {len(tiers)} tier boundaries")
            print(f"\n{'Tier':<8} {'Position (Notional Value)':<35} {'Max Leverage':<15}")
            print("-"*60)

            # Tiers are already sorted high leverage -> low leverage (high lev = small position)
            # We want to display: Tier 1 = highest leverage (smallest max position)
            for i, tier in enumerate(tiers):
                lev = tier['leverage']
                cap = tier['max_position_val']

                # Floor is previous tier's cap (or 0 for first/highest leverage tier)
                floor = 0 if i == 0 else tiers[i - 1]['max_position_val']

                print(f"Tier {i + 1:<3} {floor:>12,.0f} ~ {cap:<18,.0f} {lev}X")
        else:
            print("⚠️  Could not discover tiers")
            print("\n📊 Showing estimated tiers:")
            print_table_header()
            for tier, floor, cap, lev in estimate_leverage_tiers():
                print_tier_row(tier, floor, cap, lev)
    else:
        print("⚠️  API keys not configured in .env file")
        print("   To get exact leverage tiers, add to .env:")
        print("   BINGX_API_KEY=your_key")
        print("   BINGX_API_SECRET=your_secret")
        print("\n📊 Showing estimated tiers (based on typical ETHUSDT structure):")
        print_table_header()
        for tier, floor, cap, lev in estimate_leverage_tiers():
            print_tier_row(tier, floor, cap, lev)
    
    # 5. Account Info (if authenticated)
    if client.api_key and client.api_secret:
        print_separator("5. ACCOUNT INFORMATION")
        
        # Current leverage
        leverage = client.get_leverage(symbol)
        if leverage.get('code') == 0 and 'data' in leverage:
            lev_data = leverage['data']
            print(f"Current Long Leverage:  {lev_data.get('longLeverage', 'N/A')}X")
            print(f"Current Short Leverage: {lev_data.get('shortLeverage', 'N/A')}X")
        
        # Balance
        balance = client.get_account_balance()
        if balance.get('code') == 0 and 'data' in balance:
            bal = balance['data'].get('balance', {})
            print(f"\nAccount Balance:")
            print(f"  Available:  {bal.get('availableMargin', 'N/A')} USDT")
            print(f"  Used:       {bal.get('usedMargin', 'N/A')} USDT")
            print(f"  Total:      {bal.get('balance', 'N/A')} USDT")
    
    print_separator()
    print("✅ COMPLETE!")
    print("="*70)


if __name__ == "__main__":
    # Priority: command line arg > .env SYMBOL > default ETH-USDT
    symbol = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_SYMBOL

    # Ensure proper format
    if "/" in symbol:
        symbol = symbol.replace("/", "-")
    if "USDT" in symbol and "-" not in symbol:
        symbol = symbol.replace("USDT", "-USDT")

    main(symbol)
