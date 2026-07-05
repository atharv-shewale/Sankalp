import random
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, List
from .schemas import EventType
from .database import log_transaction

# Customer metadata mapping for demo
CUSTOMER_METADATA = {
    "CUST_STRONG_START": {
        "name": "Ramesh Dev",
        "location": "Pipariya, Madhya Pradesh",
        "mobile": "+91 98765 43210",
        "consent": True
    },
    "CUST_TRENDING_UP": {
        "name": "Sita Patil",
        "location": "Shirpur, Maharashtra",
        "mobile": "+91 87654 32109",
        "consent": True
    },
    "CUST_VOLATILE": {
        "name": "Vikram Singh",
        "location": "Alwar, Rajasthan",
        "mobile": "+91 76543 21098",
        "consent": False # Starts with false or can be True for testing rules
    }
}

def generate_event(customer_id: str, timestamp: datetime, is_live: bool = False, step: int = 0) -> Dict[str, Any]:
    event_id = f"evt_{uuid.uuid4().hex[:10]}"
    
    # 4 event types
    event_types = [EventType.UPI_TRANSFER, EventType.UTILITY_PAYMENT, EventType.MANDI_SALE, EventType.MOBILE_RECHARGE]
    
    # Selection weights based on customer profile
    if customer_id == "CUST_STRONG_START":
        # Strong agriculturalist, regular high inflows, on-time utility bills
        event_type = random.choices(
            event_types, 
            weights=[0.5, 0.2, 0.2, 0.1], 
            k=1
        )[0]
        
        status = "SUCCESS"
        if event_type == EventType.MANDI_SALE:
            amount = round(random.uniform(15000, 35000), 2)
            metadata = {"recipient": "Krishi Mandi Pipariya", "category": "Crop Sale", "payment_method": "Direct Bank"}
        elif event_type == EventType.UTILITY_PAYMENT:
            amount = round(random.uniform(1000, 2500), 2)
            metadata = {"recipient": "MP Electricity Board", "category": "Electricity Bill", "days_late": 0}
        elif event_type == EventType.MOBILE_RECHARGE:
            amount = 299.0
            metadata = {"recipient": "Jio Mobile", "category": "Telecom", "validity_days": 28}
        else: # UPI_TRANSFER
            # Mostly positive incoming or minor outgoing
            is_inflow = random.choice([True, True, False]) # 2/3 chance of inflow
            amount = round(random.uniform(500, 5000), 2)
            if is_inflow:
                metadata = {"sender": "Mukesh Dev", "category": "Family Transfer", "payment_method": "UPI"}
            else:
                metadata = {"recipient": "Local Kirana Store", "category": "Groceries", "payment_method": "UPI"}
                
    elif customer_id == "CUST_TRENDING_UP":
        # Starts weak but improves. We model this using 'step' which increases over time.
        # Early steps: low income, high utility delays. Late steps: higher income, no delays.
        event_type = random.choices(
            event_types, 
            weights=[0.5, 0.2, 0.2, 0.1], 
            k=1
        )[0]
        
        status = "SUCCESS"
        # If is_live, we use step to simulate improvement. If history, we scale based on how far back.
        improvement_factor = step / 30.0 if is_live else 0.2
        if improvement_factor > 1.0:
            improvement_factor = 1.0
            
        if event_type == EventType.MANDI_SALE:
            # Mandi sales value increases over time
            base_amount = 5000 if improvement_factor < 0.5 else 18000
            amount = round(random.uniform(base_amount, base_amount + 10000), 2)
            metadata = {"recipient": "Shirpur Mandi Cooperative", "category": "Cotton Sale", "payment_method": "Direct Bank"}
        elif event_type == EventType.UTILITY_PAYMENT:
            amount = round(random.uniform(500, 1500), 2)
            # Days late decreases as step improves
            days_late = max(0, int(15 * (1.0 - improvement_factor) + random.randint(-2, 2)))
            metadata = {"recipient": "MSEDCL Maharashtra", "category": "Electricity Bill", "days_late": days_late}
        elif event_type == EventType.MOBILE_RECHARGE:
            amount = 199.0
            metadata = {"recipient": "Airtel Mobile", "category": "Telecom", "validity_days": 28}
        else: # UPI_TRANSFER
            # More inflows, fewer failed transactions as factor grows
            is_inflow = random.random() < (0.3 + 0.4 * improvement_factor) # increases from 30% to 70% inflow
            amount = round(random.uniform(200, 3000), 2)
            if is_inflow:
                metadata = {"sender": "Anil Patil", "category": "Milk Dairy Payment", "payment_method": "UPI"}
            else:
                metadata = {"recipient": "Fertilizer Shop", "category": "Inputs", "payment_method": "UPI"}
                
    else: # CUST_VOLATILE
        # Highly erratic profile, low income, many delays, UPI failures
        event_type = random.choices(
            event_types, 
            weights=[0.6, 0.2, 0.1, 0.1], 
            k=1
        )[0]
        
        status = "SUCCESS" if random.random() > 0.3 else "FAILED" # 30% failure rate
        
        if event_type == EventType.MANDI_SALE:
            amount = round(random.uniform(3000, 10000), 2)
            metadata = {"recipient": "Alwar Mandi Market", "category": "Grain Sale", "payment_method": "Cash Deposit"}
        elif event_type == EventType.UTILITY_PAYMENT:
            amount = round(random.uniform(800, 2000), 2)
            days_late = random.randint(10, 35) # always late
            metadata = {"recipient": "Jaipur Vidyut Vitran", "category": "Electricity Bill", "days_late": days_late}
        elif event_type == EventType.MOBILE_RECHARGE:
            amount = 149.0
            metadata = {"recipient": "Vi Mobile", "category": "Telecom", "validity_days": 24}
        else: # UPI_TRANSFER
            # Mostly outflows
            is_inflow = random.random() < 0.2 # only 20% inflow
            amount = round(random.uniform(100, 4000), 2)
            if is_inflow:
                metadata = {"sender": "Friend", "category": "Borrowing", "payment_method": "UPI"}
            else:
                metadata = {"recipient": "Local Tea/Betel Shop", "category": "Miscellaneous", "payment_method": "UPI"}
                
    return {
        "customer_id": customer_id,
        "event_id": event_id,
        "timestamp": timestamp.isoformat() + "Z",
        "event_type": event_type.value,
        "amount": amount,
        "status": status,
        "metadata": metadata
    }

def seed_database_history():
    """Seeds the DB with 45 days of historical data for each profile."""
    print("Seeding database history...")
    start_time = datetime.utcnow() - timedelta(days=45)
    
    # Import log_agent_decision locally to avoid circular import issues
    from .database import log_agent_decision
    
    for customer_id in CUSTOMER_METADATA.keys():
        current_time = start_time
        # Generate ~1 transaction per day
        for day in range(45):
            # 1 to 2 events per day
            last_event_time = current_time
            for _ in range(random.randint(1, 2)):
                event_time = current_time + timedelta(hours=random.randint(0, 23), minutes=random.randint(0, 59))
                last_event_time = event_time
                # For trending customer, scale the trend historically from start to end of seeding
                step = day
                event = generate_event(customer_id, event_time, is_live=False, step=step)
                log_transaction(event)
            
            # Log a historical credit score log entry every 3 days to populate the chart
            if day % 3 == 0:
                if customer_id == "CUST_STRONG_START":
                    score = random.randint(88, 95)
                    factors = ["Impeccable utility payment regularity", "High total inflows from seasonal Mandi sales"]
                    explanation = "Strong baseline performance with high creditworthiness."
                elif customer_id == "CUST_TRENDING_UP":
                    score = int(42 + (33 * (day / 45.0)) + random.randint(-2, 2))
                    factors = ["Gradual stabilization of cash inflows", "Utility payment timeliness improving"]
                    explanation = "Demonstrates a positive upward credit trajectory."
                else: # CUST_VOLATILE
                    score = random.randint(38, 48)
                    factors = ["Frequent utility bill payment defaults", "High rate of UPI transaction failures"]
                    explanation = "Volatile behavior with elevated credit default risks."

                log_agent_decision(
                    customer_id=customer_id,
                    agent_name="ScoringAgent",
                    event_type="credit_scored",
                    payload={
                        "customer_id": customer_id,
                        "score": score,
                        "score_delta": 0,
                        "reasoning_factors": factors,
                        "explanation": explanation,
                        "timestamp": last_event_time.isoformat() + "Z"
                    }
                )
                
            current_time += timedelta(days=1)
    print("Database seeding completed.")
