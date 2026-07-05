import sqlite3
import json
from datetime import datetime
from typing import List, Dict, Any
from .config import DB_PATH

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Create transactions table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_id TEXT UNIQUE,
        customer_id TEXT,
        timestamp TEXT,
        event_type TEXT,
        amount REAL,
        status TEXT,
        metadata TEXT
    )
    """)
    
    # Create audit_logs table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS audit_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT,
        customer_id TEXT,
        agent_name TEXT,
        event_type TEXT,
        payload TEXT
    )
    """)
    
    conn.commit()
    conn.close()

def log_transaction(event_dict: Dict[str, Any]):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            INSERT OR IGNORE INTO transactions 
            (event_id, customer_id, timestamp, event_type, amount, status, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_dict.get("event_id"),
                event_dict.get("customer_id"),
                event_dict.get("timestamp"),
                event_dict.get("event_type"),
                event_dict.get("amount"),
                event_dict.get("status"),
                json.dumps(event_dict.get("metadata", {}))
            )
        )
        conn.commit()
    except Exception as e:
        print(f"Error logging transaction: {e}")
    finally:
        conn.close()

def get_customer_transactions(customer_id: str, limit: int = 100) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM transactions WHERE customer_id = ? ORDER BY timestamp DESC LIMIT ?",
        (customer_id, limit)
    )
    rows = cursor.fetchall()
    conn.close()
    
    transactions = []
    for r in rows:
        t = dict(r)
        t["metadata"] = json.loads(t["metadata"])
        transactions.append(t)
    return transactions

def log_agent_decision(customer_id: str, agent_name: str, event_type: str, payload: Dict[str, Any]):
    conn = get_db_connection()
    cursor = conn.cursor()
    timestamp = datetime.utcnow().isoformat()
    try:
        cursor.execute(
            """
            INSERT INTO audit_logs (timestamp, customer_id, agent_name, event_type, payload)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                timestamp,
                customer_id,
                agent_name,
                event_type,
                json.dumps(payload)
            )
        )
        conn.commit()
    except Exception as e:
        print(f"Error logging agent decision: {e}")
    finally:
        conn.close()

def get_audit_logs(customer_id: str = None, limit: int = 100) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    if customer_id:
        cursor.execute(
            "SELECT * FROM audit_logs WHERE customer_id = ? ORDER BY id DESC LIMIT ?",
            (customer_id, limit)
        )
    else:
        cursor.execute(
            "SELECT * FROM audit_logs ORDER BY id DESC LIMIT ?",
            (limit,)
        )
    rows = cursor.fetchall()
    conn.close()
    
    logs = []
    for r in rows:
        l = dict(r)
        l["payload"] = json.loads(l["payload"])
        logs.append(l)
    return logs

def clear_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DROP TABLE IF EXISTS transactions")
    cursor.execute("DROP TABLE IF EXISTS audit_logs")
    conn.commit()
    conn.close()
    init_db()
