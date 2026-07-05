import asyncio
import json
import random
from datetime import datetime
from typing import List, Set
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .config import HOST, PORT
from .database import init_db, log_transaction, get_customer_transactions, get_audit_logs, clear_db
from .simulator import seed_database_history, generate_event, CUSTOMER_METADATA
from .agents import (
    DataAggregationAgent, ScoringAgent, RiskAgent,
    ComplianceAgent, BankMitraNotificationAgent
)

app = FastAPI(title="Sankalp Backend", description="Agentic AI Credit Scout Dashboard API")

# Add CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory set of active WebSocket connections
active_connections: Set[WebSocket] = set()

# Background generator task reference
generator_task = None
is_generating = False
simulation_step = 0

async def broadcast_message(message: dict):
    """Broadcasts a JSON message to all connected clients."""
    if not active_connections:
        return
    
    dead_connections = set()
    message_str = json.dumps(message)
    
    for connection in active_connections:
        try:
            await connection.send_text(message_str)
        except Exception:
            dead_connections.add(connection)
            
    for dead in dead_connections:
        active_connections.remove(dead)

async def transaction_simulator_loop():
    """Background task generating a live synthetic transaction every 2 seconds."""
    global is_generating, simulation_step
    print("Starting transaction simulator loop...")
    is_generating = True
    
    customers = list(CUSTOMER_METADATA.keys())
    
    try:
        while is_generating:
            await asyncio.sleep(2.0)
            
            # Select customer and generate event
            # For CUST_TRENDING_UP, the improvement increases with simulation_step
            customer_id = random_customer = random.choice(customers)
            now = datetime.utcnow()
            
            # Increment simulation step for CUST_TRENDING_UP
            if customer_id == "CUST_TRENDING_UP":
                simulation_step += 1
                
            event = generate_event(customer_id, now, is_live=True, step=simulation_step)
            
            # 1. Log transaction to database
            log_transaction(event)
            
            # 2. Get previous score from DB
            previous_score = 50
            try:
                from .database import get_db_connection
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT payload FROM audit_logs WHERE customer_id = ? AND agent_name = 'ScoringAgent' ORDER BY id DESC LIMIT 1",
                    (customer_id,)
                )
                row = cursor.fetchone()
                conn.close()
                if row:
                    payload = json.loads(row[0])
                    previous_score = payload.get("score", 50)
            except Exception as e:
                print(f"Error fetching previous score: {e}")

            # 3. Data Aggregator Agent
            features = DataAggregationAgent.process(customer_id)

            # 4. Scoring Agent
            scoring_res = await ScoringAgent.process(features, previous_score=previous_score)

            # 5. Risk Agent
            risk_res = await RiskAgent.process(scoring_res, features)

            # 6. Compliance Agent
            compliance_res = ComplianceAgent.process(risk_res, features)

            # 7. Bank Mitra Notification Agent
            notification_res = BankMitraNotificationAgent.process(compliance_res, risk_res)

            # 8. Broadcast complete update to frontend
            await broadcast_message({
                "type": "PIPELINE_UPDATE",
                "customer_id": customer_id,
                "event": event,
                "features": features.model_dump(mode='json'),
                "score": scoring_res.model_dump(mode='json'),
                "risk": risk_res.model_dump(mode='json'),
                "compliance": compliance_res.model_dump(mode='json'),
                "notification": notification_res.model_dump(mode='json')
            })
            
    except asyncio.CancelledError:
        print("Transaction simulator loop cancelled.")
    finally:
        is_generating = False

@app.on_event("startup")
async def startup_event():
    global generator_task
    # Initialize and seed database on startup
    init_db()
    
    # Check if we already have transactions, if not, seed history
    existing = get_audit_logs(limit=1)
    # Check transactions instead of audit logs since seed_database_history only generates transactions
    try:
        from .database import get_db_connection
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM transactions")
        count = cursor.fetchone()[0]
        conn.close()
        if count == 0:
            seed_database_history()
    except Exception as e:
        print(f"Error checking transaction count: {e}")
        seed_database_history()
        
    generator_task = asyncio.create_task(transaction_simulator_loop())

@app.on_event("shutdown")
async def shutdown_event():
    global generator_task, is_generating
    is_generating = False
    if generator_task:
        generator_task.cancel()
        try:
            await generator_task
        except asyncio.CancelledError:
            pass

@app.get("/api/customers")
def get_customers():
    """Return all available customer profiles."""
    return [
        {
            "customer_id": cid,
            "name": info["name"],
            "location": info["location"],
            "mobile": info["mobile"],
            "consent": info["consent"]
        }
        for cid, info in CUSTOMER_METADATA.items()
    ]

@app.get("/api/transactions/{customer_id}")
def get_transactions(customer_id: str, limit: int = 50):
    """Retrieve historical transactions for a customer."""
    return get_customer_transactions(customer_id, limit)

@app.get("/api/audit-logs")
def get_logs(customer_id: str = None, limit: int = 100):
    """Retrieve audit logs."""
    return get_audit_logs(customer_id, limit)

@app.post("/api/reset-demo")
def reset_demo():
    """Reset database and re-seed history for a clean demo run."""
    global simulation_step
    simulation_step = 0
    clear_db()
    seed_database_history()
    return {"status": "success", "message": "Database reset and history seeded."}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_connections.add(websocket)
    print(f"New client connected. Active connections: {len(active_connections)}")
    
    # Send initial welcome state
    await websocket.send_text(json.dumps({
        "type": "SYSTEM_INFO",
        "message": "Connected to Sankalp Credit Scout Live Event Server"
    }))
    
    try:
        while True:
            # Keep connection alive, listen for any frontend messages (e.g., manual triggers)
            data = await websocket.receive_text()
            # Can add manual triggers if needed
    except WebSocketDisconnect:
        active_connections.remove(websocket)
        print(f"Client disconnected. Active connections: {len(active_connections)}")
    except Exception as e:
        if websocket in active_connections:
            active_connections.remove(websocket)
        print(f"WebSocket error: {e}")
