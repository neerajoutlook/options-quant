import unittest
from unittest.mock import MagicMock, patch
import logging
import sys
import os
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent.parent))

from core import config
from core.feed import TickEngine
from core.strategy import Strategy, Signal
# Import relative to where pytest is run or modify path
try:
    from tests.regression.data_generator import DataGenerator
except ImportError:
    # If tests dir is not in path, try direct import
    sys.path.append(str(Path(__file__).parent))
    from data_generator import DataGenerator

# Configure logging for test
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TestRegressionTradeFlow(unittest.TestCase):
    def setUp(self):
        """Setup Test Environment"""
        # 1. Mock External Dependencies
        self.mock_shoonya = MagicMock()
        self.mock_telegram = MagicMock()
        
        # 2. Configure System for Test
        config.SIMULATION_MODE = True
        config.PAPER_TRADING_MODE = True
        # config.StrategyConfig.THRESHOLD = 0.5 # REMOVED: Invalid Attribute
        
        # 3. Initialize Engine
        with patch('core.feed.ShoonyaSession', return_value=self.mock_shoonya), \
             patch('core.feed.log_signal'), \
             patch('core.feed.log_order_attempt'), \
             patch('core.feed.log_order_result'), \
             patch('core.feed.log_order_update'):
            self.engine = TickEngine()
            
        # Inject Mocks
        self.engine.telegram = self.mock_telegram
        self.engine.shoonya = self.mock_shoonya
        self.engine.auto_trading_enabled = True # Force ON
        
        # Reset PositionManager State (Prevent Hard Stop from stale PnL)
        # Just clear attributes of the existing real PositionManager
        if hasattr(self.engine, 'position_manager'):
             self.engine.position_manager.positions = {}
             self.engine.position_manager.realized_pnl = 0.0
             self.engine.position_manager.unrealized_pnl = 0.0
        
        # 4. Prepare Data Generator
        self.token_map = {"BANKNIFTY": "26009"}
        self.data_gen = DataGenerator(self.token_map)
        
        # Setup Instrument Manager Mock to return token 26009 for BANKNIFTY
        self.engine.instrument_mgr.get_lot_size = MagicMock(return_value=15)
        self.engine.token_map = self.token_map
        self.engine.reverse_token_map = {"26009": "BANKNIFTY"}
        self.engine.subscribed_tokens = {"26009"}
        
        # Prepare Mock Weightage Calc
        self.mock_weightage = MagicMock()
        self.mock_weightage.calculate_weighted_strength.return_value = 0.0
        self.engine.weightage_calc = self.mock_weightage
        
        # IMPORTANT: Initialize Strategy with test threshold
        self.engine.strategy = Strategy(weightage_calc=self.mock_weightage)
        self.engine.strategy.threshold = 0.5
        
        # 5. Seed Engine State (required for Strategy to work)
        
    def test_complete_trade_cycle(self):
        """
        Test a full Buy -> Sell cycle using synthetic data.
        Sine wave pattern should trigger:
        1. Uptrend -> BUY CE
        2. Downtrend -> SELL CE (Exit) and/or BUY PE
        """
        logger.info("🎬 Starting Regression Test: Trade Cycle")
        
        # Generate 15 minutes of data (3 full 5-min cycles)
        ticks = self.data_gen.generate_sine_wave(
            "BANKNIFTY", 
            duration_minutes=15, 
            period_minutes=5
        )
        
        initial_trades = len(self.engine.paper_trading.closed_trades)
        active_position = None
        
        logger.info(f"Feeding {len(ticks)} ticks...")
        
        for i, tick in enumerate(ticks):
            # Dynamic Strength Mocking (Optional: Sync with sine wave)
            # sin(angle) from data gen... 
            # For simplicity, let's toggle strength based on index to help the strategy
            # if i % 300 < 150: strength = 2.0 (Bulish) else -2.0 (Bearish)
            
            # 1. Process Tick
            self.engine.on_tick(tick)
            
            # 2. Check if position opened (Long/Short)
            current_paper_pos = self.engine.paper_trading.current_position
            
            if current_paper_pos and not active_position:
                logger.info(f"✅ Position ENTERED at Tick {i}: {current_paper_pos.option_type} @ {current_paper_pos.entry_price}")
                active_position = current_paper_pos
                
            # 3. Check if position closed
            if active_position and not current_paper_pos:
                 # It was closed!
                 closed_trade = self.engine.paper_trading.closed_trades[-1]
                 logger.info(f"✅ Position CLOSED at Tick {i}: P&L {closed_trade.pnl:.2f}")
                 active_position = None
                 
            # Speed Checks
            if i % 100 == 0:
                logger.info(f"Tick {i} processed...")

        # Assertions
        total_closed = len(self.engine.paper_trading.closed_trades)
        logger.info(f"🏁 Test Complete. Total Closed Trades: {total_closed}")
        
        # We expect at least one complete cycle (Buy -> Sell)
        self.assertTrue(total_closed > 0, "No trades were completed during the simulation cycle")
        
        # Verify Position Manager Sync
        # At the end, if all closed, net_qty should be 0 for the contracts used
        for key, pos in self.engine.position_manager.positions.items():
            if pos['net_qty'] != 0:
                 logger.warning(f"Position remaining: {key} Qty: {pos['net_qty']}")
                 
            # Ideally should be 0 or small if strategy held till end
            # Sine wave logic implies reversals, so likely exits happened.
            
if __name__ == '__main__':
    unittest.main()
