#!/usr/bin/env python3
import asyncio
import websockets
import json

async def test_ws():
    uri = "ws://localhost:8000/ws/prices"
    try:
        async with websockets.connect(uri) as websocket:
            print("✅ Connected to WebSocket")
            
            # Wait for snapshot
            message = await asyncio.wait_for(websocket.recv(), timeout=5.0)
            data = json.loads(message)
            print(f"📦 Received: {data['type']}")
            if data['type'] == 'snapshot':
                print(f"   Items: {len(data.get('data', {}))}")
                print(f"   Keys: {list(data.get('data', {}).keys())[:5]}")
            
    except Exception as e:
        print(f"❌ Error: {e}")

asyncio.run(test_ws())
