# Advanced Options Selection Strategy

## Strike Selection Logic

### Goal: ~50% Win Probability

The bot now uses intelligent strike selection based on signal strength to target approximately 50% probability of success (equivalent to Delta ~0.5).

### Strike Selection Rules

**For CALLS (BUY_CE):**
- **Very Strong Signal** (Strength > 8.0):
  - Strike: ATM + 200 (2 strikes OTM)
  - Delta: ~0.40-0.45
  - Probability: ~45%
  - Rationale: High conviction, go for better leverage
  
- **Strong Signal** (Strength 6.5-8.0):
  - Strike: ATM + 100 (1 strike OTM)
  - Delta: ~0.45-0.48
  - Probability: ~47%
  - Rationale: Good conviction, slight OTM for leverage
  
- **Moderate Signal** (Strength 4.0-6.5):
  - Strike: ATM (At-The-Money)
  - Delta: ~0.50
  - Probability: ~50%
  - Rationale: Standard risk/reward

**For PUTS (BUY_PE):**
- Same logic, but offset goes below current price

**For EXIT:**
- Uses the same strike as entry (tracked via `current_symbol`)

### Entry Threshold
- Lowered to **4.0** (from 5.0) to generate more trading signals
- Provides more opportunities to see algo in action

### Example
- Bank Nifty @ 59,600
- Strength = 7.5 (strong bullish)
- Signal: BUY_CE
- **Selected Strike:** 59,700 CE (1 strike OTM)
- **Probability:** ~47%

## Benefits
1. **Balanced Risk/Reward** - Not too aggressive, not too conservative
2. **Leverage on Strong Signals** - Better returns when confidence is high
3. **Safety on Weak Signals** - ATM for better probability
4. **Frequent Trading** - Lower threshold ensures regular signals
