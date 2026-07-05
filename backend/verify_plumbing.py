import asyncio
import websockets
import json

async def test_websocket():
    uri = "ws://localhost:8000/ws"
    print(f"Connecting to {uri}...")
    try:
        async with websockets.connect(uri) as websocket:
            print("Successfully connected!")
            
            # Receive initial message
            welcome = await websocket.recv()
            print(f"Welcome msg: {welcome}")
            
            # Read next 3 messages
            for i in range(3):
                message = await websocket.recv()
                data = json.loads(message)
                print(f"\nReceived message {i+1}:")
                print(json.dumps(data, indent=2))
                
    except Exception as e:
        print(f"Error connecting or communicating with WebSocket: {e}")

if __name__ == "__main__":
    asyncio.run(test_websocket())
