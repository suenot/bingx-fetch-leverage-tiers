# BingX Leverage Tiers Fetcher

Fetch leverage bracket/tier data for BingX perpetual futures contracts.

**Problem**: BingX lacks a dedicated leverage bracket endpoint (unlike Binance `/leverageBracket` or Bybit). This tool discovers tier boundaries by probing the API.

## Features

- Discover leverage tiers via API probing
- Reference data from BingX website (15 trading pairs)
- Validation tests to compare API vs website data
- Contract information, market data, funding rates

## Supported Trading Pairs

Reference data available for:
`BTC`, `ETH`, `SOL`, `BNB`, `XRP`, `ADA`, `DOGE`, `LTC`, `AVAX`, `LINK`, `UNI`, `ATOM`, `SHIB`, `OP`, `AR`

## Installation

```bash
pip install -r requirements.txt
```

## Configuration

Create `.env` file:

```env
# Required for tier discovery
BINGX_API_KEY=your_api_key_here
BINGX_API_SECRET=your_api_secret_here

# Optional
SYMBOL=BTC-USDT
BINGX_BASE_URL=https://open-api.bingx.com
```

Get API keys at: https://bingx.com/en/account/api/

## Usage

### Fetch Leverage Data

```bash
# Use default symbol (ETH-USDT)
python main.py

# Specify symbol
python main.py BTC-USDT
python main.py SOL-USDT
```

### Run Validation Tests

```bash
# Test specific symbols
python test_leverage_tiers.py BTC-USDT ETH-USDT

# Test all 15 reference symbols
python test_leverage_tiers.py

# Quick test (less verbose)
python test_leverage_tiers.py -q BTC-USDT

# Offline validation (check CSV data integrity)
python test_leverage_tiers.py --offline
```

## How It Works

Since BingX has no `/leverageBracket` endpoint, the tool uses **probing**:

1. Calls `set_leverage` with different values (150, 125, 100, 75, ... 1)
2. API returns `maxPositionLongVal` - max position size for that leverage
3. When `maxPositionLongVal` changes, we've found a tier boundary
4. Original leverage is restored after probing

**Safe**: No orders created, only leverage setting is temporarily changed.

## Data Structure

### Reference Data (tiers_from_website.csv)

```
Pair,Tier,Position (Notional Value),Max. Leverage
BTCUSDT,Tier 1,0 ~ 300000,150X
BTCUSDT,Tier 2,300000 ~ 800000,100X
...
```

### Discovered Tier Format

```python
{
    'leverage': 150,
    'max_position_val': 300000.0
}
```

## Example Output

```
======================================================================
4. POSITION & LEVERAGE TIERS
======================================================================
Discovering leverage tiers by probing...

Tier     Position (Notional Value)           Max Leverage
------------------------------------------------------------
Tier 1            0 ~ 300,000                 150X
Tier 2      300,000 ~ 800,000                 100X
Tier 3      800,000 ~ 3,000,000               75X
...
```

## Test Results

Test output shows match quality:

```
COMPARISON: BTC-USDT
======================================================================
Expected tiers: 12, Discovered: 12

EXACT MATCHES (10):
  Tier  1 | 150X |            0 ~ 300,000
  Tier  2 | 100X |      300,000 ~ 800,000
  ...

CLOSE MATCHES (2):
  Tier 11 |   2X
         Expected:      800,000,000 ~ 1,200,000,000
         Discovered:    805,000,000 ~ 1,205,000,000
         Diff: floor=5,000,000, cap=5,000,000

ACCURACY SUMMARY:
   Exact matches:   10/12 (83.3%)
   Close matches:    2/12 (16.7%)
   Total matched:   12/12 (100.0%)
```

## Important Notes

- **KYC/VIP affects leverage**: Unverified accounts may see lower max leverage (5X limit)
- **Data changes**: BingX updates tier boundaries based on market conditions
- **API rate limits**: 10 req/s for trading endpoints; tests include delays
- **Boundaries approximate**: API may return slightly different values than website

## API Endpoints Used

| Endpoint | Auth | Description |
|----------|------|-------------|
| `GET /openApi/swap/v2/quote/contracts` | No | Contract info |
| `GET /openApi/swap/v2/trade/leverage` | Yes | Current leverage |
| `POST /openApi/swap/v2/trade/leverage` | Yes | Set leverage (for probing) |

## Project Structure

```
bingx-leverages/
├── main.py                  # API client & tier discovery
├── test_leverage_tiers.py   # Validation tests
├── tiers_from_website.csv   # Reference data (15 pairs)
├── requirements.txt
├── .env                     # API keys (not in repo)
└── README.md
```

## References

- [BingX API Documentation](https://bingx-api.github.io/docs/)
- [BingX Trading Rules](https://bingx.com/en/tradeInfo/perpetual/margin/)
- [Leverage Tiers Info](https://bingx.com/en/tradeInfo/perpetual/margin/ETH-USDT)
