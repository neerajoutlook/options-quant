
from unittest.mock import MagicMock, patch
from core import config
from core.feed import TickEngine
from core.strategy import Signal

def test_hedged_entry_execution():
    """Test that directional signals generate wings when HEDGED_ENTRIES is True"""
    
    # Mock dependencies for TickEngine
    mock_shoonya = MagicMock()
    mock_inst_mgr = MagicMock()
    mock_inst_mgr.get_lot_size.return_value = 15
    mock_weight_calc = MagicMock()
    mock_weight_calc.calculate_weighted_strength.return_value = 5.0 # Moderate strength
    
    # Mock TickEngine class to avoid real init
    with patch('core.feed.TickEngine.__init__', return_value=None):
        engine = TickEngine()
        
    engine.shoonya = mock_shoonya
    engine.instrument_mgr = mock_inst_mgr
    engine.weightage_calc = mock_weight_calc
    # Mock internal helpers
    engine._get_option_symbol = MagicMock(side_effect=lambda type, strike: f"BANKNIFTYXP{type}{strike}")
    engine._place_order_internal = MagicMock()
    engine.telegram = MagicMock()
    engine.offline = False
    engine.position_manager = MagicMock()
    engine.position_manager.positions = {}
    
    # Enable Hedged Entries
    config.HEDGED_ENTRIES = True
    config.HEDGE_OTM_STEP = 1000
    config.QUANTITY = 1
    
    # Simulate BUY_CE Signal
    # Price = 50000 -> ATM = 50000
    signal = Signal("BUY_CE", "BANKNIFTY", 50020, "Test Signal", 1000)
    
    engine.execute_signal(signal)
    
    # Verification: Two orders should be placed
    assert engine._place_order_internal.call_count == 2
    
    # Order 1: MAIN CE at 50000 (ATM)
    call_args_1 = engine._place_order_internal.call_args_list[0]
    assert call_args_1[0][3] == "MAIN" # tag
    assert "C50000" in call_args_1[0][0] # symbol
    
    # Order 2: WING PE at 49000 (ATM - 1000)
    call_args_2 = engine._place_order_internal.call_args_list[1]
    assert call_args_2[0][3] == "WING" # tag
    assert "P49000" in call_args_2[0][0] # symbol 
