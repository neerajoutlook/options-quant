# Project Organization

## Folders

### `tests/`
Test scripts for various components:
- `test_order_with_correct_symbols.py` - Order placement tests
- `test_telegram.py` - Telegram integration tests
- `test_login.py` - Shoonya login tests

### `logs/`
Log files from running the bot:
- `trading.log` - Main trading system logs

### `data/`
Downloaded instruments and cached data:
- `NSE_instruments.txt` - NSE stocks (~8,785 instruments)
- `NFO_instruments.txt` - NFO derivatives (~85,310 instruments)
- `BSE_instruments.txt` - BSE stocks (~12,536 instruments)
- `BFO_instruments.txt` - BFO derivatives (~35,777 instruments)
- `instruments_metadata.json` - Download timestamp

**Downloading instruments:**
```bash
python data/download_instruments.py
```

**Searching symbols:**
```bash
python data/download_instruments.py search "BANKNIFTY" NFO
```

## Important Notes

### Bank Nifty Options
- **Weekly options discontinued** after Nov 13, 2024
- Now using **monthly expiry** (last Wednesday of month)
- Symbol format: `BANKNIFTY27DEC24CE51500` (DDMMMYY + CE/PE + Strike)

### Symbol Format Examples
- NSE Equity: `SBIN-EQ`
- NFO Option: `BANKNIFTY27DEC24CE51500`
- NFO Future: `BANKNIFTY27DEC24FUT`

### Log Location
All logs are written to `logs/trading.log`
