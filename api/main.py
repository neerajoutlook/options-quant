"""
FastAPI WebSocket Server for HFT Trading Platform
Provides REST API + WebSocket for real-time price streaming
"""
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
import asyncio
import logging
from datetime import datetime
from pathlib import Path
import json
import pydantic

from core.market_data import market_data

logger = logging.getLogger(__name__)

app = FastAPI(title="Bank Nifty HFT API", version="1.0.0")

# Serve static files (frontend)
# Resolve path relative to this file (api/main.py) -> parent (project root) -> frontend
project_root = Path(__file__).parent.parent
frontend_path = project_root / "frontend"
static_path = frontend_path / "static"

if not static_path.exists():
    logger.error(f"Static path does not exist: {static_path}")
    # Create it if missing to avoid startup crash
    static_path.mkdir(parents=True, exist_ok=True)

app.mount("/static", StaticFiles(directory=str(static_path)), name="static")

# Active WebSocket connections
active_connections: set = set()

@app.get("/")
async def serve_dashboard():
    """Serve the live price dashboard"""
    html_file = frontend_path / "index.html"
    if html_file.exists():
        return FileResponse(html_file)
    return {"message": "Dashboard not found"}

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "active_connections": len(active_connections),
        "symbols_tracked": len(market_data.get_latest_prices())
    }

@app.get("/api/prices")
async def get_all_prices():
    """Get latest prices for all symbols (REST)"""
    return {
        "prices": market_data.get_latest_prices(),
        "timestamp": datetime.now().isoformat()
    }

@app.get("/api/config")
async def get_config():
    """Get configuration (Lot sizes, etc)"""
    try:
        from main import active_engine
        config = {
            "lot_sizes": {},
            "risk": {}
        }
        if active_engine:
             # Lot Sizes
             if hasattr(active_engine, 'instrument_mgr'):
                 config["lot_sizes"] = active_engine.instrument_mgr.lot_size_map
             
             # Risk Config
             if hasattr(active_engine, 'position_manager'):
                 config["risk"] = active_engine.position_manager.risk_config
        
        return config
    except Exception as e:
        logger.error(f"Config Error: {e}")
        return {"error": str(e)}

@app.get("/api/positions")
async def get_positions():
    """Get current positions and P&L"""
    try:
        from main import active_engine
        if active_engine and hasattr(active_engine, 'position_manager'):
            # Trigger P&L update with latest prices before returning
            pm = active_engine.position_manager
            pm.update_pnl(market_data.latest_prices)
            
            # Convert tuple keys (symbol, product) to strings for JSON
            serializable_positions = {}
            for (sym, prd), pos in pm.positions.items():
                price_data = market_data.latest_prices.get(sym, {})
                pos_data = pos.copy()
                pos_data['ltp'] = price_data.get('ltp', pos['avg_price'])
                serializable_positions[f"{sym}:{prd}"] = pos_data
            
            total_unrealized = sum(p['unrealized_pnl'] for p in pm.positions.values())
            
            return {
                "positions": serializable_positions,
                "total_pnl": pm.realized_pnl + total_unrealized
            }
        return {"positions": {}, "total_pnl": 0.0}
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/stats")
async def get_strategy_stats():
    """Get overall strategy status and risk metrics"""
    from core import config
    from main import active_engine
    
    stats = {
        "hedged_mode": config.HEDGED_ENTRIES,
        "straddle_mode": config.ENABLE_STRADDLES,
        "daily_loss_limit": config.MAX_DAILY_LOSS,
        "auto_exit_time": config.AUTO_EXIT_TIME,
        "current_pnl": 0.0,
        "auto_trade_enabled": False,
        "simulation_mode": config.SIMULATION_MODE,
        "simulation_speed": config.SIMULATION_SPEED
    }
    
    if active_engine:
        stats["auto_trade_enabled"] = active_engine.auto_trading_enabled
        if hasattr(active_engine, 'position_manager'):
            pm = active_engine.position_manager
            # Update P&L before returning
            total_unrealized = pm.update_pnl(market_data.latest_prices)
            stats["current_pnl"] = pm.realized_pnl + total_unrealized
            
    return stats

class SimConfig(pydantic.BaseModel):
    enabled: bool
    speed: float

@app.post("/api/simulation/config")
async def set_simulation_config(cfg: SimConfig):
    """Update simulation mode and speed"""
    from main import active_engine
    from core import config
    try:
        if not active_engine:
            return {"status": "error", "message": "Engine not active"}
        
        # Guard: Prevent switching from simulation to live mode if started offline
        if not cfg.enabled and config.SIMULATION_MODE:
            # Check if the API was ever logged in
            if hasattr(active_engine, 'offline') and active_engine.offline:
                logger.warning("⚠️ Cannot switch to live mode - engine started without API login")
                return {
                    "status": "error", 
                    "message": "Cannot switch to live mode. Restart the application without simulation mode to use live trading."
                }
        
        # If we're already in simulation mode and just changing speed
        if config.SIMULATION_MODE and cfg.enabled and hasattr(active_engine, 'simulator'):
            if cfg.speed != config.SIMULATION_SPEED:
                logger.info(f"⚡ Updating simulation speed: {config.SIMULATION_SPEED}x → {cfg.speed}x")
                config.SIMULATION_SPEED = cfg.speed
                if active_engine.simulator:
                    active_engine.simulator.speed = cfg.speed
                return {"status": "ok", "message": f"Speed updated to {cfg.speed}x"}
            return {"status": "ok", "message": "No change needed"}
        
        # Otherwise, do full mode switch (requires restart)
        if hasattr(active_engine, 'set_simulation_mode'):
            active_engine.set_simulation_mode(cfg.enabled, cfg.speed)
            return {"status": "ok", "message": f"Simulation set to {cfg.enabled} at {cfg.speed}x"}
        
        return {"status": "error", "message": "Engine not ready"}
    except AttributeError as e:
        # Handle missing attributes gracefully in offline mode
        logger.warning(f"Simulation config warning (offline mode): {e}")
        return {"status": "error", "message": "Cannot switch modes - restart required for live trading"}
    except Exception as e:
        logger.error(f"Error setting simulation config: {e}")
        return {"status": "error", "message": str(e)}

@app.get("/api/orders")
async def get_orders(date: str = None):
    """Get recent order history and logs, optionally filtered by date (YYYY-MM-DD)"""
    try:
        from core.database import db
        from core import config
        import json
        from pathlib import Path
        
        orders = []
        
        # 1. Fetch from DB (Real Trades)
        if date:
            orders = db.get_orders_by_date(date)
        else:
            from main import active_engine
            if active_engine and hasattr(active_engine, 'order_history') and active_engine.order_history:
                orders = active_engine.order_history
            else:
                orders = db.get_recent_orders()
        
        # 2. Fetch from Paper Trading JSON (Simulation/Paper)
        # We assume if the user is in simulation mode, they want to see these
        paper_file = Path("logs/paper_trades.json")
        if paper_file.exists():
            try:
                with open(paper_file, 'r') as f:
                    paper_trades = json.load(f)
                    
                # Filter for today/requested date if needed
                # For now, just append recent ones or all if date matches
                # PaperTrade format: entry_time (ISO), symbol (derived?), etc.
                # We need to adapt them to match DB schema for UI:
                # {id, symbol, side, qty, price, status, timestamp, message}
                
                for pt in reversed(paper_trades[-50:]): # Last 50 paper trades
                    entry_ts = pt.get('entry_time', '')
                    if date and not entry_ts.startswith(date):
                        continue
                        
                    # Adapt PaperTrade to Order Schema
                    status = pt.get('status', 'OPEN')
                    if pt.get('exit_time'):
                        status = "CLOSED"
                        
                    orders.append({
                        "id": pt.get('id', f"sim-{entry_ts[-6:]}"),
                        "symbol": pt.get('symbol', f"{pt.get('option_type')} {pt.get('entry_strike')}"),
                        "side": pt.get('side', "BUY"),
                        "qty": pt.get('quantity'),
                        "price": pt.get('entry_price'),
                        "status": f"SIM-{status}",
                        "timestamp": entry_ts,
                        "reason": pt.get('entry_reason', 'Paper Trade')
                    })
                    
                    # If closed, maybe show exit as separate line?
                    # For simplicity, just show entry for now.
                    
            except Exception as e:
                logger.error(f"Error reading paper trades: {e}")

        # Sort by timestamp desc
        orders.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        return {"orders": orders}

    except Exception as e:
        logger.error(f"API Orders Error: {e}")
        return {"error": str(e)}

@app.post("/api/orders/clear")
async def clear_orders(date: str = Query(...)):
    """Clear order history for a specific date"""
    try:
        from core.database import db
        db.clear_orders_for_date(date)
        
        # Also clear in-memory history if it's for today
        today = datetime.now().strftime("%Y-%m-%d")
        if date == today:
            from main import active_engine
            if active_engine and hasattr(active_engine, 'order_history'):
                active_engine.order_history = []
                
        return {"status": "success", "message": f"History for {date} cleared"}
    except Exception as e:
        logger.error(f"API Clear Error: {e}")
        return {"status": "error", "message": str(e)}


@app.get("/api/mode")
async def get_trading_mode():
    """Get the current trading mode (Real or Paper)"""
    from core import config
    from core.database import db
    # Sync with DB if available
    db_mode = db.get_state("paper_trading_mode")
    if db_mode is not None:
        config.PAPER_TRADING_MODE = (db_mode == "True")
    return {"paper_trading_mode": config.PAPER_TRADING_MODE}

@app.post("/api/mode")
async def set_trading_mode(paper_mode: bool = Query(...)):
    """Update the trading mode dynamically (Real or Paper)"""
    from core import config
    from core.database import db
    config.PAPER_TRADING_MODE = paper_mode
    db.save_state("paper_trading_mode", paper_mode)
    logger.warning(f"🔄 Trading mode changed to: {'PAPER' if paper_mode else 'REAL'}")
    return {"status": "success", "paper_trading_mode": config.PAPER_TRADING_MODE}
@app.get("/api/auto_trade")
async def get_auto_trade():
    """Get the current AI Auto-Trading status"""
    from main import active_engine
    enabled = False
    if active_engine and hasattr(active_engine, 'auto_trading_enabled'):
        enabled = active_engine.auto_trading_enabled
    return {"auto_trading_enabled": enabled}

@app.post("/api/auto_trade")
async def set_auto_trade(enabled: bool = Query(...)):
    """Toggle AI Auto-Trading status"""
    from main import active_engine
    from core.database import db
    if active_engine and hasattr(active_engine, 'auto_trading_enabled'):
        active_engine.auto_trading_enabled = enabled
        db.save_state("auto_trading_enabled", enabled)
        logger.info(f"🔄 AI Auto-Trading {'ENABLED' if enabled else 'DISABLED'}")
        return {"status": "success", "auto_trading_enabled": enabled}
    return {"status": "error", "message": "Engine not ready"}

@app.get("/api/risk")
async def get_risk_config():
    """Get risk configuration"""
    try:
        from main import active_engine
        if active_engine and hasattr(active_engine, 'position_manager'):
            return active_engine.position_manager.risk_config
        return {}
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/strategy/threshold")
async def get_strategy_threshold():
    """Get current strategy threshold"""
    try:
        from main import active_engine
        if active_engine and hasattr(active_engine, 'strategy'):
            return {
                "threshold": active_engine.strategy.threshold,
                "default": 2.5
            }
        return {"threshold": 2.5, "default": 2.5}
    except Exception as e:
        return {"error": str(e)}

@app.post("/api/strategy/threshold")
async def set_strategy_threshold(threshold: float = Query(...)):
    """Update strategy threshold dynamically"""
    try:
        from main import active_engine
        from core.database import db
        
        if active_engine and hasattr(active_engine, 'strategy'):
            active_engine.strategy.threshold = threshold
            db.save_state("strategy_threshold", threshold)
            logger.info(f"🎯 Strategy threshold updated to {threshold}")
            return {"status": "success", "threshold": threshold}
        return {"status": "error", "message": "Engine not ready"}
    except Exception as e:
        logger.error(f"Threshold update error: {e}")
        return {"status": "error", "message": str(e)}

@app.get("/api/strategy/timeframe")
async def get_strategy_timeframe():
    """Get current strategy timeframe (minutes)"""
    try:
        from main import active_engine
        timeframe = 5 # default
        if active_engine and hasattr(active_engine, 'active_timeframe'):
            timeframe = active_engine.active_timeframe
        
        return {
            "timeframe": timeframe,
            "available": [1, 3, 5, 15]
        }
    except Exception as e:
        return {"error": str(e)}

@app.post("/api/strategy/timeframe")
async def set_strategy_timeframe(minutes: int = Query(...)):
    """Update strategy timeframe dynamically"""
    try:
        from main import active_engine
        from core.database import db
        
        if active_engine and hasattr(active_engine, 'set_timeframe'):
            if active_engine.set_timeframe(minutes):
                db.save_state("strategy_timeframe", minutes)
                return {"status": "success", "timeframe": minutes}
            else:
                return {"status": "error", "message": f"Invalid timeframe {minutes}. Supported: 1, 3, 5, 15"}
            
        return {"status": "error", "message": "Engine not ready"}
    except Exception as e:
        logger.error(f"Timeframe update error: {e}")
        return {"status": "error", "message": str(e)}

@app.post("/api/test_trade")
async def test_trade():
    """Simulate a test trade for UI verification"""
    try:
        from main import active_engine
        import random
        
        if not active_engine:
            return {"status": "error", "message": "Engine not ready"}
        
        # Generate a random test order
        symbols = ["HDFCBANK", "ICICIBANK", "SBIN", "AXISBANK", "KOTAKBANK"]
        symbol = random.choice(symbols)
        side = random.choice(["BUY_CE", "BUY_PE"])
        price = round(random.uniform(50, 200), 2)
        
        # Create a test order entry
        test_order = {
            "symbol": f"{symbol}27JAN26{'C' if 'CE' in side else 'P'}1000",
            "side": side,
            "qty": 15,
            "price": price,
            "status": "FILLED (TEST)",
            "timestamp": datetime.now().isoformat(),
            "reason": "Manual test trade"
        }
        
        # Add to order history if available
        if hasattr(active_engine, 'order_history'):
            active_engine.order_history.append(test_order)
        
        logger.info(f"🧪 Test trade generated: {side} {test_order['symbol']} @ {price}")
        return {"status": "success", "order": test_order}
        
    except Exception as e:
        logger.error(f"Test trade error: {e}")
        return {"status": "error", "message": str(e)}

@app.get("/api/market/status")
async def get_market_status_api():
    """Get current market status (open/closed) and reason"""
    try:
        from core.market_hours import get_market_status
        return get_market_status()
    except Exception as e:
        logger.error(f"Market status error: {e}")
        return {"is_open": False, "reason": "Unknown", "mode": "SIMULATION"}

@app.get("/api/price/{symbol}")
async def get_symbol_price(symbol: str):
    """Get latest price for specific symbol"""
    price_data = market_data.get_price(symbol.upper())
    if not price_data:
        return {"error": "Symbol not found", "symbol": symbol}
    if not price_data:
        return {"error": "Symbol not found", "symbol": symbol}
    return price_data

@app.post("/api/control/{action}")
async def control_bot(action: str):
    """Control the trading bot (start/stop)"""
    action = action.lower()
    if action not in ["start", "stop"]:
        return {"error": "Invalid action. Use 'start' or 'stop'"}
    
    # In a real implementation, we would communicate with the bot thread nicely
    # For now, we'll set a flag or call a global function
    # TODO: Implement proper thread signaling
    
    return {"status": "success", "action": action, "message": f"Signal {action} received"}

@app.post("/api/simulate")
async def start_simulation(symbol: str = "SBIN"):
    """Start simulating ticks for a symbol (for visualization test)"""
    logger.info(f"Starting simulation for {symbol}")
    
    # Run simulation in background
    asyncio.create_task(_simulate_ticker(symbol))
    
    return {"status": "started", "symbol": symbol}

async def _simulate_ticker(symbol: str):
    """Background task to generate fake ticks"""
    import random
    price = 1000.0
    
    # Add dummy macro data for visualization
    # We need to access the TickEngine instance ideally, but here we just update market_data
    # For full simulation we might want to update macro_data in feed if possible
    # For now, just price updates
    
    try:
        while True:
            # Random Walk
            change = random.uniform(-1, 1)
            price += change
            
            payload = {
                'symbol': symbol,
                'ltp': round(price, 2),
                'volume': random.randint(100, 10000),
                'open': 1000.0,
                'high': round(price + 5, 2),
                'low': round(price - 5, 2),
                'change': round(price - 1000.0, 2),
                'vwap': round(price - 1, 2),
                'trend': "BULLISH" if price > 1000 else "BEARISH",
                'macro': {'trend': 'BULLISH', 'rsi': '60.5'}, # Fake Macro
                'timestamp': datetime.now().isoformat()
            }
            
            # Update market data which triggers websocket
            if hasattr(market_data, 'latest_prices'):
                market_data.latest_prices[symbol] = payload
            
            # Fire update to subscribers
            # Since market_data.latest_prices set item triggers subscribers if implemented
            # Let's check market_data implementation
            # It seems market_data is just a dict? No, it has notify/subscribe?
            # Let's look at core/market_data.py to be sure. 
            # Assuming market_data.latest_prices is a CustomDict or we need to call notify explicitly.
            # Based on previous logs: "New subscriber added", "Subscriber removed"
            # It likely has observer pattern.
            
            # Let's explicitly notify if possible, or assume setting latest_prices does it.
            # Note: The websocket endpoint adds a callback to market_data.
            # We need to make sure market_data calls it.
            
            # Wait 500ms
            await asyncio.sleep(0.5)
            
            # Wait 500ms
            await asyncio.sleep(0.5)
            
    except Exception as e:
        logger.error(f"Simulation error: {e}")

from pydantic import BaseModel

class OrderRequest(BaseModel):
    symbol: str
    side: str # BUY, SELL
    qty: int
    price: float = 0.0
    product_type: str = 'I' # Default to MIS

class GTTRequest(BaseModel):
    symbol: str
    side: str
    qty: int
    trigger_price: float
    product_type: str = 'I'

@app.post("/api/order")
async def place_order(order: OrderRequest):
    """Place a manual order"""
    try:
        from main import active_engine
        if not active_engine:
            return {"status": "error", "message": "Trading Engine not ready"}
            
        result = active_engine.place_manual_order(
            symbol=order.symbol.upper(),
            side=order.side.upper(),
            qty=order.qty,
            price=order.price,
            product_type=order.product_type
        )
        return result
    except Exception as e:
        logger.error(f"API Order Error: {e}")
        return {"status": "error", "message": str(e)}

@app.post("/api/order/cancel")
async def cancel_order(order_id: str = Query(...)):
    """Cancel an active order"""
    try:
        from main import active_engine
        if not active_engine:
            return {"status": "error", "message": "Trading Engine not ready"}
        return active_engine.cancel_order(order_id)
    except Exception as e:
        logger.error(f"API Cancel Error: {e}")
        return {"status": "error", "message": str(e)}

@app.post("/api/order/gtt")
async def place_gtt(order: GTTRequest):
    """Place a GTT order"""
    try:
        from main import active_engine
        if not active_engine:
            return {"status": "error", "message": "Trading Engine not ready"}
        return active_engine.place_gtt_order(
            symbol=order.symbol.upper(),
            side=order.side.upper(),
            qty=order.qty,
            trigger_price=order.trigger_price,
            product_type=order.product_type
        )
    except Exception as e:
        logger.error(f"API GTT Error: {e}")
        return {"status": "error", "message": str(e)}

@app.post("/api/panic")
async def panic_exit():
    """Close ALL positions immediately"""
    try:
        from main import active_engine
        if not active_engine:
            return {"status": "error", "message": "Engine not running"}
            
        await active_engine.order_manager.close_all_positions()
        return {"status": "success", "message": "Panic Exit Triggered"}
    except Exception as e:
        logger.error(f"Panic Exit Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/debug/prices")
async def debug_prices():
    """Debug endpoint to check backend market data state"""
    from core.market_data import market_data
    prices = market_data.get_latest_prices()
    logger.info(f"DEBUG: /api/debug/prices called. Items: {len(prices)}")
    return {
        "count": len(prices),
        "items": list(prices.values()),
        "keys": list(prices.keys()),
        "id": id(market_data),
        "module": market_data.__module__
    }

@app.websocket("/ws/prices")
async def websocket_prices(websocket: WebSocket):
    """WebSocket endpoint for real-time price streaming"""
    await websocket.accept()
    active_connections.add(websocket)
    
    # Create callback for this connection
    async def send_update(symbol: str, data: dict):
        """Send price update to this WebSocket client"""
        try:
            await websocket.send_json({
                "type": "price_update",
                "symbol": symbol,
                "data": data
            })
        except Exception as e:
            logger.error(f"Error sending to WebSocket: {e}")
    
    # Subscribe to market data
    market_data.subscribe(send_update)
    
    try:
        # Send initial snapshot
        initial_data = market_data.get_latest_prices()
        await websocket.send_json({
            "type": "snapshot",
            "data": initial_data,
            "timestamp": datetime.now().isoformat()
        })
        
        # Keep connection alive and handle incoming messages
        while True:
            try:
                # Wait for client messages (ping/pong for latency measurement)
                message = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                
                # Handle ping for latency measurement
                if message == "ping":
                    await websocket.send_text("pong")
                    
            except asyncio.TimeoutError:
                # Send keepalive ping
                await websocket.send_json({"type": "ping"})
                
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        # Cleanup
        market_data.unsubscribe(send_update)
        active_connections.discard(websocket)
        logger.info(f"Connection closed. Active: {len(active_connections)}")

@app.on_event("startup")
async def startup_event():
    """Initialize on startup"""
    logger.info("FastAPI HFT server starting...")
    # Start background broadcaster
    asyncio.create_task(broadcast_loop())

async def broadcast_loop():
    """Background task to poll for updates and broadcast"""
    last_broadcast = {}
    
    while True:
        try:
            # Get current snapshot
            current_prices = market_data.get_latest_prices()
            
            # Check for changes
            for symbol, data in current_prices.items():
                last_time = last_broadcast.get(symbol, {}).get('timestamp')
                curr_time = data.get('timestamp')
                
                # If timestamp changed, broadcast
                if curr_time != last_time:
                    # Broadcast to all connected clients
                    await market_data.broadcast(symbol, data)
                    last_broadcast[symbol] = data
            
            # Poll every 50ms (20 FPS)
            await asyncio.sleep(0.05)
            
        except Exception as e:
            logger.error(f"Broadcast loop error: {e}")
            await asyncio.sleep(1)

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("FastAPI HFT server shutting down...")
    # Close all WebSocket connections
    for ws in active_connections.copy():
        await ws.close()
