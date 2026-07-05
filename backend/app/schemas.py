from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from enum import Enum
from datetime import datetime

class EventType(str, Enum):
    UPI_TRANSFER = "UPI_TRANSFER"
    UTILITY_PAYMENT = "UTILITY_PAYMENT"
    MANDI_SALE = "MANDI_SALE"
    MOBILE_RECHARGE = "MOBILE_RECHARGE"

class TransactionEvent(BaseModel):
    customer_id: str
    event_id: str
    timestamp: datetime
    event_type: EventType
    amount: float
    status: str  # SUCCESS, FAILED
    metadata: Dict[str, Any] = Field(default_factory=dict)

class AggregatedFeatures(BaseModel):
    customer_id: str
    last_updated: datetime
    total_inflow: float
    total_outflow: float
    net_savings_ratio: float
    utility_payment_regularity: float
    upi_transaction_count: int
    average_transaction_value: float
    mandi_sales_frequency: int
    mandi_sales_total: float
    recharge_frequency_days: int
    data_history_days: int
    consent_flag: bool

class ScoringResult(BaseModel):
    customer_id: str
    score: int
    score_delta: int
    reasoning_factors: List[str]
    explanation: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class RiskResult(BaseModel):
    customer_id: str
    shadow_score: int
    risk_tier: str  # Low, Medium, High
    max_loan_limit: float
    justification: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class TriggeredRule(BaseModel):
    rule_id: str
    description: str
    passed: bool
    value: Optional[Any] = None

class ComplianceResult(BaseModel):
    customer_id: str
    status: str  # APPROVED, HOLD, REJECTED
    triggered_rules: List[TriggeredRule]
    rejection_reason: Optional[str] = None
    decision_timestamp: datetime = Field(default_factory=datetime.utcnow)

class NotificationResult(BaseModel):
    notification_id: str
    customer_id: str
    customer_name: str
    approved_amount: float
    interest_rate_annual: float
    tenure_months: int
    repayment_frequency: str
    repayment_amount: float
    sms_preview: str
    status: str  # PENDING_DISBURSAL, DISBURSED, REJECTED_BY_CUSTOMER
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class AuditLogEntry(BaseModel):
    id: Optional[int] = None
    timestamp: datetime
    customer_id: str
    agent_name: str  # DataAggregator, Scorer, Risk, Compliance, Notification
    event_type: str  # input_received, decision_made, rule_triggered, etc.
    payload: Dict[str, Any]
