import pytest
from core.strategy import Strategy, WeightageCalculator, Signal

@pytest.fixture
def weightage_calc():
    # Setup a mock weightage with a few stocks
    weights = {"HDFCBANK": 50.0, "ICICIBANK": 50.0}
    wc = WeightageCalculator(weights=weights)
    wc.update_data("HDFCBANK", 1000, is_open=True)
    wc.update_data("ICICIBANK", 1000, is_open=True)
    return wc

def test_weightage_strength_calc(weightage_calc):
    # If HDFCBANK goes up 1%, ICICIBANK stays same
    weightage_calc.update_data("HDFCBANK", 1010) 
    strength = weightage_calc.calculate_weighted_strength()
    # 50% weight * 1% change = 50.0 total strength (using whole numbers)
    assert strength == 50.0

def test_strategy_momentum_boost():
    wc = WeightageCalculator(weights={})
    # Threshold 2.5, Confirmation 1, min_hold_time 0 (for simple test)
    strat = Strategy(wc, min_strength=2.5, min_confirmation=1, min_hold_time=0)
    
    # Simulate rapid 100 point recovery over 30 seconds
    timestamp = 1000
    strat.on_tick(50000, timestamp)
    timestamp += 30
    signal = strat.on_tick(50100, timestamp) # +100 points
    
    # Total score calculation:
    # Intraday level (if vwap=0): 0
    # Macro (neutral): 0
    # Strength: 0
    # Momentum (+100): +1.5
    # Since 1.5 < 2.5, no signal yet
    assert signal is None
    
    # Add Strength and Macro to push it over 2.5
    signal = strat.on_tick(50100, timestamp + 1, vwap=50000, macro_trend="BULLISH")
    # Score = +1.0 (Price > VWAP) + 1.0 (BULLISH) + 1.5 (Mom) = 3.5
    assert signal is not None
    assert signal.type == "BUY_CE"

def test_strategy_confirmation_buffer():
    wc = WeightageCalculator(weights={})
    # Threshold 1.0, Confirmation 3, min_hold_time 0 
    strat = Strategy(wc, min_strength=1.0, min_confirmation=3, min_hold_time=0)
    
    # Send high score ticks
    t = 1000
    # Tick 1
    assert strat.on_tick(110, t, vwap=100) is None # Score 1.0, but only 1 tick
    # Tick 2
    assert strat.on_tick(110, t + 1, vwap=100) is None # 2 ticks
    # Tick 3 - Should trigger
    signal = strat.on_tick(110, t + 2, vwap=100)
    assert signal is not None
    assert signal.type == "BUY_CE"

def test_strategy_exit_logic():
    wc = WeightageCalculator(weights={})
    # min_hold_time=0 is critical for rapid-fire test ticks
    strat = Strategy(wc, min_strength=1.0, min_confirmation=1, min_hold_time=0)
    
    # Enter Position
    strat.on_tick(110, 1000, vwap=100)
    assert strat.position == "CE"
    
    # Fade score to trigger EXIT (Price falls to VWAP)
    signal = strat.on_tick(100, 1001, vwap=100)
    assert signal is not None
    assert signal.type == "EXIT"
    assert strat.position is None
