"""
BingX API Client with leverage tier discovery.
"""

import os
import time
import hmac
import hashlib
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from urllib.parse import urlencode

import requests


@dataclass
class LeverageTier:
    """Represents a single leverage tier."""
    tier: int
    notional_floor: float
    notional_cap: float
    max_leverage: int
    maint_margin_rate: float = 0.0
    cum: float = 0.0


class BingXClient:
    """
    BingX API Client with authentication support.

    Args:
        api_key: BingX API key (or set BINGX_API_KEY env var)
        api_secret: BingX API secret (or set BINGX_API_SECRET env var)
        base_url: API base URL (default: https://open-api.bingx.com)

    Example:
        >>> from bingx_leverages import BingXClient
        >>> client = BingXClient(api_key="...", api_secret="...")
        >>> tiers = client.discover_leverage_tiers("BTC-USDT")
    """

    DEFAULT_BASE_URL = "https://open-api.bingx.com"

    def __init__(
        self,
        api_key: str = "",
        api_secret: str = "",
        base_url: str = ""
    ):
        self.api_key = api_key or os.getenv("BINGX_API_KEY", "")
        self.api_secret = api_secret or os.getenv("BINGX_API_SECRET", "")
        self.base_url = base_url or os.getenv("BINGX_BASE_URL", self.DEFAULT_BASE_URL)
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
            "X-BX-APIKEY": self.api_key
        })

    def _generate_signature(self, params: dict) -> str:
        """Generate HMAC SHA256 signature."""
        params_str = urlencode(sorted(params.items()))
        signature = hmac.new(
            self.api_secret.encode("utf-8"),
            params_str.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()
        return signature

    def _generate_signature_from_string(self, query_string: str) -> str:
        """Generate HMAC SHA256 signature from query string."""
        return hmac.new(
            self.api_secret.encode("utf-8"),
            query_string.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()

    def _get_timestamp(self) -> int:
        """Get current timestamp in milliseconds."""
        return int(time.time() * 1000)

    def _request(
        self,
        method: str,
        endpoint: str,
        params: dict = None,
        signed: bool = False
    ) -> dict:
        """Make API request."""
        url = f"{self.base_url}{endpoint}"
        params = params or {}

        if signed:
            if not self.api_key or not self.api_secret:
                return {
                    "error": "API keys not configured. "
                    "Please set api_key/api_secret or BINGX_API_KEY/BINGX_API_SECRET env vars"
                }

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
        """Get all contract information."""
        return self._request("GET", "/openApi/swap/v2/quote/contracts")

    def get_contract_details(self, symbol: str) -> Optional[dict]:
        """Get specific contract details."""
        data = self.get_contracts()
        if data.get('code') == 0 and 'data' in data:
            for contract in data['data']:
                if contract.get('symbol') == symbol:
                    return contract
        return None

    def get_ticker(self, symbol: str) -> dict:
        """Get 24hr ticker price change statistics."""
        return self._request("GET", "/openApi/swap/v2/quote/ticker", {"symbol": symbol})

    def get_premium_index(self, symbol: str) -> dict:
        """Get premium index including mark price and funding rate."""
        return self._request("GET", "/openApi/swap/v2/quote/premiumIndex", {"symbol": symbol})

    def get_funding_rate(self, symbol: str) -> dict:
        """Get current funding rate."""
        return self._request("GET", "/openApi/swap/v2/quote/fundingRate", {"symbol": symbol})

    def get_depth(self, symbol: str, limit: int = 20) -> dict:
        """Get order book depth."""
        return self._request(
            "GET",
            "/openApi/swap/v2/quote/depth",
            {"symbol": symbol, "limit": limit}
        )

    def get_klines(self, symbol: str, interval: str = "1h", limit: int = 100) -> dict:
        """Get candlestick/kline data."""
        return self._request(
            "GET",
            "/openApi/swap/v2/quote/klines",
            {"symbol": symbol, "interval": interval, "limit": limit}
        )

    # ==================== PRIVATE ENDPOINTS (require API key) ====================

    def get_margin_tiers(self, symbol: str) -> dict:
        """
        Get maintenance margin ratio tiers (requires authentication).

        Returns position tiers with maintMarginRatio from which max_leverage
        can be calculated.
        """
        params = {"symbol": symbol}
        return self._request("GET", "/openApi/swap/v1/maintMarginRatio", params, signed=True)

    def get_account_balance(self) -> dict:
        """Get account balance (requires authentication)."""
        return self._request("GET", "/openApi/swap/v2/user/balance", signed=True)

    def get_positions(self, symbol: str = None) -> dict:
        """Get current positions (requires authentication)."""
        params = {}
        if symbol:
            params["symbol"] = symbol
        return self._request("GET", "/openApi/swap/v2/user/positions", params, signed=True)

    def get_leverage(self, symbol: str) -> dict:
        """Get current leverage for symbol (requires authentication)."""
        return self._request(
            "GET",
            "/openApi/swap/v2/trade/leverage",
            {"symbol": symbol},
            signed=True
        )

    def set_leverage(self, symbol: str, side: str, leverage: int) -> dict:
        """
        Set leverage for symbol (requires authentication).

        Args:
            symbol: Trading pair (e.g., "BTC-USDT")
            side: "LONG" or "SHORT"
            leverage: Leverage value
        """
        timestamp = self._get_timestamp()
        query_string = f"leverage={leverage}&side={side}&symbol={symbol}&timestamp={timestamp}"
        signature = self._generate_signature_from_string(query_string)

        url = f"{self.base_url}/openApi/swap/v2/trade/leverage?{query_string}&signature={signature}"
        try:
            response = requests.post(
                url,
                headers={"X-BX-APIKEY": self.api_key},
                timeout=10
            )
            return response.json()
        except Exception as e:
            return {"error": str(e)}

    def discover_leverage_tiers(
        self,
        symbol: str,
        restore_leverage: int = 10,
        probe_values: List[int] = None
    ) -> List[Dict]:
        """
        Discover leverage tiers by probing different leverage values.

        Since BingX lacks a dedicated leverage bracket endpoint, this method
        discovers tier boundaries by setting different leverage values and
        observing the returned max position limits.

        Args:
            symbol: Trading pair (e.g., "BTC-USDT")
            restore_leverage: Leverage value to restore after probing
            probe_values: Optional list of leverage values to probe.
                         If None, uses comprehensive default list.

        Returns:
            List of dicts with 'leverage' and 'max_position_val' keys,
            sorted from highest leverage to lowest.

        Example:
            >>> client = BingXClient(api_key="...", api_secret="...")
            >>> tiers = client.discover_leverage_tiers("BTC-USDT")
            >>> for tier in tiers:
            ...     print(f"{tier['leverage']}X: max {tier['max_position_val']:,} USDT")
        """
        if not self.api_key or not self.api_secret:
            return []

        if probe_values is None:
            probe_values = [
                250, 200, 150, 125, 100, 75, 50, 40, 34, 30, 25, 20, 19, 17, 16, 15,
                14, 13, 12, 11, 10, 9, 8, 7, 6, 5, 4, 3, 2, 1
            ]
        else:
            probe_values = sorted(set(probe_values), reverse=True)

        tiers = []
        prev_max_val = None
        current_tier_lev = None

        for lev in probe_values:
            result = self.set_leverage(symbol, "LONG", lev)
            if result.get('code') == 0:
                data = result.get('data', {})
                max_val = float(data.get('maxPositionLongVal', 0))

                if max_val != prev_max_val:
                    if current_tier_lev is not None and prev_max_val is not None:
                        tiers.append({
                            'leverage': current_tier_lev,
                            'max_position_val': prev_max_val
                        })
                    current_tier_lev = lev
                    prev_max_val = max_val
                else:
                    current_tier_lev = lev

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
        current_lev = 10
        lev_info = self.get_leverage(symbol)
        if lev_info.get('code') == 0 and 'data' in lev_info:
            current_lev = lev_info['data'].get('longLeverage', 10)

        return self.discover_leverage_tiers(
            symbol,
            restore_leverage=current_lev,
            probe_values=reference_leverages
        )
