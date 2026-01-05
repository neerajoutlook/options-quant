# System Documentation

## Log Files
- **Location**: `trading.log` in the project root directory
- **Format**: Timestamped entries with level, module name, and message
- **Content**: Login events, token resolution, tick data, signals, and order execution

## Exit Logic (How It Works)
The system does NOT need to store ticks. It works in real-time:

1. **Every Tick Updates Strength**: Each price update recalculates the weighted strength
2. **Strategy Checks Current State**: On every tick, the strategy checks:
   - **If No Position**: Enter if strength > 5.0 (BUY CE) or < -5.0 (BUY PE)
   - **If Holding CE**: Exit if strength drops below 1.0 (reversal detection)
   - **If Holding PE**: Exit if strength rises above -1.0 (reversal detection)
3. **Position Maintained in Memory**: `strategy.position` tracks current state (`None`, `"CE"`, or `"PE"`)

## Order ID Tracking
- **Current Order ID**: Stored in `engine.current_order_id`
- **Current Symbol**: Stored in `engine.current_symbol`
- **Updates**: Set when order placed, cleared on exit (can be enhanced)

## Telegram Alerts
All events send Telegram notifications:
1. **Startup**: "🚀 Bot STARTED"
2. **Ready**: "✅ Bot Ready - Connecting to live feed"
3. **Signal Generated**: "🟢 BUY CE" or "🔴 BUY PE"
4. **Order Placed**: "✅ Order Placed: [details]"
5. **Order Failed**: "❌ Order Failed"
6. **Exit Signal**: "EXIT [position]"
7. **Shutdown**: "⏹️ Bot STOPPED"
8. **Crash**: "❌ Bot CRASHED: [error]"
9. **Offline**: "💤 Bot Offline"

## Testing Telegram
Run: `python test_telegram.py`

## Known Issues
- **Symbol TMPV**: User changed TATAMOTORS to TMPV - verify this is a valid symbol
- **Symbol Matching**: Some symbols (SBIN, LT, M&M) may still resolve incorrectly if using old code
  - Ensure latest code with exact matching is running
