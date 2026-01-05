import pytest
from core.strategy import Strategy, WeightageCalculator, Signal
from core import config

@pytest.fixture
def mock_strategy():
    wc = WeightageCalculator(weights={})
    # Threshold 2.5, Confirmation 1 for instant response in tests
    return Strategy(wc, min_strength=2.5, min_confirmation=1, min_hold_time=0)

def test_straddle_signal_generation(mock_strategy):
    """Test that valid Straddle signals are generated under specific conditions"""
    # Enable Straddles for this test
    config.ENABLE_STRADDLES = True
    
    # Condition: Low Conviction (Score near 0), High Momentum (>1.5)
    # Price = 50000 -> 50100 (Momentum +high)
    # VWAP = 50100 (Price == VWAP, score 0)
    # Macro = NEUTRAL (score 0)
    # Strength = 0
    # Conviction = 0
    
    # 1. Base State
    mock_strategy.on_tick(50000, 1000)
    
    # 2. Spike in price (High Momentum), but neutral conviction context
    # Momentum score calc: (50200 - 50000) = +200 points.
    # In strategy.py: mom_score = change (200) / 100 * 1.5 = +3.0
    # Score = 0 (VWAP) + 0 (Macro) + 0 (Strength) + 3.0 (Mom) = 3.0 Total
    # Conviction = Total (3.0) - Mom (3.0) = 0.0
    
    # We need to manually set vwap and macro to ensure conviction stays low
    signal = mock_strategy.on_tick(50200, 1001, vwap=50200, macro_trend="NEUTRAL")
    
    assert signal is not None
    assert signal.type == "BUY_STRADDLE"
    assert "Straddle: Conviction 0.0" in signal.reason
    assert mock_strategy.position == "STRADDLE"

def test_straddle_disabled_config(mock_strategy):
    """Test that Straddles are NOT generated if disabled in config"""
    config.ENABLE_STRADDLES = False
    
    mock_strategy.on_tick(50000, 1000)
    
    # 2. Strong Directional Move (Price > VWAP + Momentum)
    # Price 50000 -> 50300 (+300 pts)
    # Mom Score = +1.5 (for >60pts)
    # VWAP Score = +1.0 (Price 50300 > VWAP 50000)
    # Macro Score = 0 (NEUTRAL)
    # Total Score = 2.5 (Threshold met)
    
    signal = mock_strategy.on_tick(50300, 1001, vwap=50000, macro_trend="NEUTRAL")
    
    # Should be High Conviction Directional because Total Score is 3.0 (>2.5)
    # NOT Straddle because config is False
    assert signal is not None
    assert signal.type == "BUY_CE"
    assert mock_strategy.position == "CE"

def test_straddle_exit_on_momentum_fade(mock_strategy):
    """Test that Straddle position exits when momentum fades"""
    config.ENABLE_STRADDLES = True
    
    # Enter Straddle
    mock_strategy.position = "STRADDLE"
    mock_strategy.last_signal_time = 1000
    
    # Low Momentum Update 
    # Price stays flat: 50200 -> 50210
    # Momentum ~ 0
    signal = mock_strategy.on_tick(50210, 1002, vwap=50210, macro_trend="NEUTRAL")
    
    assert signal is not None
    assert signal.type == "EXIT"
    assert "Straddle fade" in signal.reason
    assert mock_strategy.position is None

def test_straddle_exit_on_conviction_shift(mock_strategy):
    """Test that Straddle exits if market develops strong directional conviction"""
    config.ENABLE_STRADDLES = True
    
    # Enter Straddle
    mock_strategy.position = "STRADDLE"
    mock_strategy.last_signal_time = 1000
    
    # High Conviction Update
    # Price stays volatile (Mom high), but Macro shifts to BULLISH and Price > VWAP
    # Mom Score = 1.5
    # Score = 1.0 (BULLISH) + 1.0 (Price > VWAP) + 1.5 (Mom) = 3.5 Total
    # Conviction = 2.0 (High enough to maybe switch, but logic says exit straddle if score > threshold)
    
    signal = mock_strategy.on_tick(50300, 1002, vwap=50200, macro_trend="BULLISH")
    
    # Logic: if abs(avg_score) > self.threshold (2.5) -> Exit Straddle
    assert signal is not None
    assert signal.type == "EXIT"
    assert mock_strategy.position is None
