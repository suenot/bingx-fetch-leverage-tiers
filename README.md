# bingx-leverages

[![PyPI version](https://badge.fury.io/py/bingx-leverages.svg)](https://badge.fury.io/py/bingx-leverages)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Discover leverage tiers for BingX perpetual futures contracts.

**Problem**: BingX lacks a dedicated leverage bracket endpoint (unlike Binance `/leverageBracket` or Bybit). This library discovers tier boundaries by probing the API.

## Installation

```bash
pip install bingx-leverages
```

## Quick Start

```python
from bingx_leverages import BingXClient

# Initialize client with API keys
client = BingXClient(
    api_key="your_api_key",
    api_secret="your_api_secret"
)

# Discover leverage tiers for BTC-USDT
tiers = client.discover_leverage_tiers("BTC-USDT")

for tier in tiers:
    print(f"{tier['leverage']}X: max {tier['max_position_val']:,} USDT")
```

Output:
```
150X: max 300,000 USDT
100X: max 800,000 USDT
75X: max 3,000,000 USDT
...
```

## Features

- Discover leverage tiers via API probing
- Reference data from BingX website (15 trading pairs)
- Validation tools to compare API vs reference data
- Public endpoints for contract info, market data, funding rates

## Supported Trading Pairs

Reference data available for:
`BTC`, `ETH`, `SOL`, `BNB`, `XRP`, `ADA`, `DOGE`, `LTC`, `AVAX`, `LINK`, `UNI`, `ATOM`, `SHIB`, `OP`, `AR` (all USDT pairs)

```python
from bingx_leverages import get_supported_symbols

print(get_supported_symbols())
# ['ADA-USDT', 'AR-USDT', 'ATOM-USDT', 'AVAX-USDT', 'BNB-USDT', ...]
```

## Configuration

Set API keys via environment variables or pass directly:

```python
# Option 1: Environment variables
import os
os.environ["BINGX_API_KEY"] = "your_key"
os.environ["BINGX_API_SECRET"] = "your_secret"

client = BingXClient()

# Option 2: Direct parameters
client = BingXClient(api_key="your_key", api_secret="your_secret")
```

Get API keys at: https://bingx.com/en/account/api/

## Command Line Usage

```bash
# Fetch leverage data for a symbol
python -m bingx_leverages BTC-USDT

# List supported symbols
python -m bingx_leverages --list

# Validate against reference data
python -m bingx_leverages --validate BTC-USDT
```

Or use the installed command:

```bash
bingx-leverages BTC-USDT
bingx-leverages --list
```

## API Reference

### BingXClient

```python
from bingx_leverages import BingXClient

client = BingXClient(api_key="...", api_secret="...")

# Discover leverage tiers (requires auth)
tiers = client.discover_leverage_tiers("BTC-USDT")

# Public endpoints (no auth required)
contracts = client.get_contracts()
ticker = client.get_ticker("BTC-USDT")
funding = client.get_funding_rate("BTC-USDT")
depth = client.get_depth("BTC-USDT", limit=20)

# Private endpoints (require auth)
balance = client.get_account_balance()
positions = client.get_positions()
leverage = client.get_leverage("BTC-USDT")
```

### Reference Data

```python
from bingx_leverages import (
    get_reference_tiers,
    get_supported_symbols,
    REFERENCE_TIERS
)

# Get reference tiers for a symbol
tiers = get_reference_tiers("BTC-USDT")
# [(1, 0, 300000, 150), (2, 300000, 800000, 100), ...]

# All reference data
print(REFERENCE_TIERS.keys())
```

### Validation

```python
from bingx_leverages import BingXClient, validate_symbol

client = BingXClient(api_key="...", api_secret="...")
results = validate_symbol(client, "BTC-USDT")

print(f"Accuracy: {results['boundary_matches']}/{results['total_boundaries']}")
```

## How It Works

Since BingX has no `/leverageBracket` endpoint, the library uses **probing**:

1. Calls `set_leverage` with different values (150, 125, 100, 75, ... 1)
2. API returns `maxPositionLongVal` - max position size for that leverage
3. When `maxPositionLongVal` changes, a tier boundary is found
4. Original leverage is restored after probing

**Safe**: No orders are created, only leverage setting is temporarily changed.

## Important Notes

- **KYC/VIP affects leverage**: Unverified accounts may see lower max leverage
- **Data changes**: BingX updates tier boundaries based on market conditions
- **API rate limits**: 10 req/s for trading endpoints
- **Boundaries approximate**: API may return slightly different values than website

## Development

```bash
# Clone repository
git clone https://github.com/suenot/bingx-fetch-leverage-tiers
cd bingx-leverages

# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
python test_leverage_tiers.py --offline
```

## License

MIT License - see [LICENSE](LICENSE) file.
