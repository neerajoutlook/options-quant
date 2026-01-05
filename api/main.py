"""
FastAPI WebSocket Server for HFT Trading Platform
Provides REST API + WebSocket for real-time price streaming
"""
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
import asyncio
import logging
from datetime import datetime
from pathlib import Path
import json

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
            active_engine.position_manager.update_pnl(market_data.latest_prices)
            return {
                "positions": active_engine.position_manager.positions,
                "total_pnl": active_engine.position_manager.realized_pnl + sum(p['unrealized_pnl'] for p in active_engine.position_manager.positions.values())
            }
        return {"positions": {}, "total_pnl": 0.0}
    except Exception as e:
        return {"error": str(e)}

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
            price=order.price
        )
        return result
    except Exception as e:
        logger.error(f"API Order Error: {e}")
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
