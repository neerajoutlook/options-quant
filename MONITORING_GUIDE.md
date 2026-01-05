# Quick Start - Monitoring Paper Trading

## ✅ Bot Updated and Deployed (Dec 15)

**What Changed**:
1. ✅ Paper trading mode enabled
2. ✅ Signal threshold: 4.0 → 5.5 (higher conviction)
3. ✅ Signal cooldown: 60 seconds
4. ✅ Updated monitoring script (pi_monitor.sh)

---

## Monitor Bot Status

### Check Status
```bash
./pi_monitor.sh status
```

### View Paper Trades
```bash
./pi_monitor.sh trades
```

### Check Recent Signals
```bash
./pi_monitor.sh signals
```

### Live Logs
```bash
./pi_monitor.sh logs-live
```

### Download Paper Trading Data
```bash
./pi_monitor.sh download
# Creates ./pi_logs/ with all files
```

---

## Verify Paper Trading is Working

Look for these in logs:
```
📝 PAPER ENTRY
Symbol: BANKNIFTY31DEC25C59500
Action: B 20 lots
Price: ₹59,500.00
```

```
📝 💚 PAPER EXIT
P&L: ₹1,240.00
```

---

## Expected Behavior (Next 3 Days)

**With MIN_SIGNAL_STRENGTH=5.5:**
- **Fewer signals** (maybe 2-5 per day vs. 25+)
- **Higher quality** entries
- **Better P&L** (should see some wins)

**If you see NO signals for a whole day:**
- Market not volatile enough
- Consider lowering to 5.0

---

## Check Results After 3 Days

```bash
ssh -i ~/.ssh/id_ed25519_raspi -p 2222 neerajsharma@100.76.123.9 \
  'cd ~/options-quant && docker-compose exec -T trading-bot python generate_paper_pnl.py'
```

This will show:
- Total trades
- Win rate
- Gross P&L
- Individual trade details

**Decision Point**:
- If P&L > 0 over 3 days → Consider real trading (after fixing symbol/NFO)
- If P&L < 0 → Adjust strategy parameters

---

## Key Files to Review

- [BOT_STATUS_REPORT_DEC15.md](./BOT_STATUS_REPORT_DEC15.md) - Full analysis
- [RECENT_CHANGES.md](./RECENT_CHANGES.md) - What changed Dec 10
- Paper trades: `ssh raspi9 'cat ~/options-quant/logs/paper_trades.json'`
