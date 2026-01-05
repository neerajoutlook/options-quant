# Trading P&L Tracking

## Features Added

### 1. Position Tracker
- Tracks entry and exit prices
- Calculates P&L for each trade
- Saves all trades to `logs/trades.json`

### 2. Enhanced Telegram Alerts

**Entry Signal:**
```
✅ ENTRY ORDER PLACED
Symbol: BANKNIFTY30DEC25C59700
Action: BUY 20 lots
Type: BUY_CE
Entry Price (est): ₹59,633.30
Strike: 59700
Order ID: 25120500XXXXX
```

**Exit Signal:**
```
💚 EXIT ORDER PLACED
Symbol: BANKNIFTY30DEC25C59700
Action: SELL 20 lots
Exit Price (est): ₹59,680.50
Entry Price (est): ₹59,633.30
P&L: ₹940.00
Order ID: 25120500XXXXX
```

### 3. End-of-Day P&L Report

**Generate Report:**
```bash
python generate_pnl_report.py
```

**Report Format:**
```
💚 END OF DAY P&L REPORT
📅 Date: 2025-12-05

📊 Summary
Total Trades: 5
Winning: 3 ✅
Losing: 2 ❌
Win Rate: 60.0%

💰 Gross P&L: ₹2,450.00

📋 Trade Details:
1. ✅ BANKNIFTY30DEC25C59700
   Entry: ₹59,633.30 → Exit: ₹59,680.50
   P&L: ₹940.00

2. ❌ BANKNIFTY30DEC25P59500
   Entry: ₹59,584.50 → Exit: ₹59,545.20
   P&L: ₹-786.00
...
```

## Files

- `core/position_tracker.py` - Position tracking and P&L calculation
- `logs/trades.json` - All trade history with prices
- `generate_pnl_report.py` - Daily P&L report generator

## Usage

**Automatic:**
- Entry/exit prices shown in Telegram when orders placed
- P&L calculated and shown on exit

**Manual:**
```bash
# Generate end-of-day report
python generate_pnl_report.py

# Schedule daily at market close (3:30 PM)
# Add to crontab:
30 15 * * 1-5 cd /path/to/bot && python generate_pnl_report.py
```

## Notes
- Prices are **estimates** based on Bank Nifty spot price (not actual fill prices)
- For exact P&L, integrate with broker's order book API
- Trades saved permanently in `logs/trades.json`
