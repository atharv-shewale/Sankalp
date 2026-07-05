import os
import json
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, List, Tuple
from pydantic import BaseModel

from .config import ANTHROPIC_API_KEY, GEMINI_API_KEY, MOCK_LLM_MODE
from .database import get_customer_transactions, log_agent_decision
from .schemas import (
    AggregatedFeatures, ScoringResult, RiskResult, 
    ComplianceResult, TriggeredRule, NotificationResult
)
from .simulator import CUSTOMER_METADATA

# Initialize LLM Clients if keys exist
gemini_client = None
if GEMINI_API_KEY:
    try:
        from google import genai
        gemini_client = genai.Client(api_key=GEMINI_API_KEY)
    except Exception as e:
        print(f"Error initializing Gemini client: {e}")

anthropic_client = None
if ANTHROPIC_API_KEY:
    try:
        import anthropic
        anthropic_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    except Exception as e:
        print(f"Error initializing Anthropic client: {e}")


# =====================================================================
# 1. DATA AGGREGATION AGENT
# =====================================================================
class DataAggregationAgent:
    @staticmethod
    def process(customer_id: str) -> AggregatedFeatures:
        # Fetch last 100 transactions from DB
        txs = get_customer_transactions(customer_id, limit=100)
        
        # Default empty features in case of no transactions
        if not txs:
            now = datetime.utcnow()
            return AggregatedFeatures(
                customer_id=customer_id,
                last_updated=now,
                total_inflow=0.0,
                total_outflow=0.0,
                net_savings_ratio=0.0,
                utility_payment_regularity=1.0,
                upi_transaction_count=0,
                average_transaction_value=0.0,
                mandi_sales_frequency=0,
                mandi_sales_total=0.0,
                recharge_frequency_days=28,
                data_history_days=0,
                consent_flag=CUSTOMER_METADATA.get(customer_id, {}).get("consent", False)
            )

        success_txs = [t for t in txs if t["status"] == "SUCCESS"]
        
        # Calculate inflows
        total_inflow = 0.0
        mandi_sales_total = 0.0
        mandi_sales_frequency = 0
        
        for t in success_txs:
            etype = t["event_type"]
            amount = t["amount"]
            meta = t["metadata"]
            
            if etype == "MANDI_SALE":
                total_inflow += amount
                mandi_sales_total += amount
                mandi_sales_frequency += 1
            elif etype == "UPI_TRANSFER" and "sender" in meta:
                total_inflow += amount

        # Calculate outflows
        total_outflow = 0.0
        utility_count = 0
        utility_on_time = 0
        
        for t in success_txs:
            etype = t["event_type"]
            amount = t["amount"]
            meta = t["metadata"]
            
            if etype == "UTILITY_PAYMENT":
                total_outflow += amount
                utility_count += 1
                if meta.get("days_late", 0) == 0:
                    utility_on_time += 1
            elif etype == "MOBILE_RECHARGE":
                total_outflow += amount
            elif etype == "UPI_TRANSFER" and "recipient" in meta:
                total_outflow += amount

        # Net Savings Ratio
        if total_inflow > 0:
            net_savings_ratio = round((total_inflow - total_outflow) / total_inflow, 2)
            net_savings_ratio = max(-1.0, min(1.0, net_savings_ratio)) # clamp
        else:
            net_savings_ratio = -0.5 if total_outflow > 0 else 0.0

        # Utility regularity (ratio of on-time utility payments)
        utility_payment_regularity = 1.0
        if utility_count > 0:
            utility_payment_regularity = round(utility_on_time / utility_count, 2)

        # UPI count
        upi_count = sum(1 for t in success_txs if t["event_type"] == "UPI_TRANSFER")
        
        # Average transaction value
        avg_val = 0.0
        if success_txs:
            avg_val = round(sum(t["amount"] for t in success_txs) / len(success_txs), 2)

        # History length (days)
        timestamps = [datetime.fromisoformat(t["timestamp"].rstrip("Z")) for t in txs]
        if timestamps:
            history_days = (max(timestamps) - min(timestamps)).days
        else:
            history_days = 0

        # Load mobile recharge frequency
        recharge_freq = 28
        if customer_id == "CUST_VOLATILE":
            recharge_freq = 24

        consent = CUSTOMER_METADATA.get(customer_id, {}).get("consent", False)

        features = AggregatedFeatures(
            customer_id=customer_id,
            last_updated=datetime.utcnow(),
            total_inflow=round(total_inflow, 2),
            total_outflow=round(total_outflow, 2),
            net_savings_ratio=net_savings_ratio,
            utility_payment_regularity=utility_payment_regularity,
            upi_transaction_count=upi_count,
            average_transaction_value=avg_val,
            mandi_sales_frequency=mandi_sales_frequency,
            mandi_sales_total=round(mandi_sales_total, 2),
            recharge_frequency_days=recharge_freq,
            data_history_days=max(history_days, 1),
            consent_flag=consent
        )
        
        # Log decision / feature set to Audit Log
        log_agent_decision(
            customer_id=customer_id,
            agent_name="DataAggregator",
            event_type="features_computed",
            payload=features.model_dump()
        )
        
        return features


# =====================================================================
# 2. SCORING AGENT
# =====================================================================
class ScoringAgent:
    @staticmethod
    def _compute_deterministic_score(features: AggregatedFeatures) -> Tuple[int, List[str], str]:
        """Calculates score + reasoning deterministically for fast local testing/fallback."""
        # Baseline score
        score = 50
        factors = []
        
        # 1. Savings Ratio (Max +15, Min -15)
        if features.net_savings_ratio > 0.5:
            score += 15
            factors.append(f"Excellent net savings ratio of {int(features.net_savings_ratio*100)}% indicates strong cash retention.")
        elif features.net_savings_ratio > 0.2:
            score += 8
            factors.append(f"Healthy net savings ratio of {int(features.net_savings_ratio*100)}% indicating budget discipline.")
        elif features.net_savings_ratio < 0:
            score -= 15
            factors.append("Outflow exceeds inflow, leading to capital depletion and negative savings.")
        else:
            factors.append(f"Modest savings ratio ({int(features.net_savings_ratio*100)}%) leaves limited safety margin.")

        # 2. Utility Regularity (Max +20, Min -20)
        if features.utility_payment_regularity > 0.9:
            score += 20
            factors.append("Perfect or near-perfect utility payment regularity indicates high bill-paying discipline.")
        elif features.utility_payment_regularity > 0.6:
            score += 5
            factors.append("Utility payments are mostly regular, but with minor delays.")
        else:
            score -= 20
            factors.append("Frequent utility payment delays flag potential cashflow gaps or lack of payment intent.")

        # 3. Mandi Sales (Max +20)
        if features.mandi_sales_total > 30000:
            score += 20
            factors.append(f"Substantial agricultural income (INR {features.mandi_sales_total:,.2f} mandi sales) verified.")
        elif features.mandi_sales_total > 10000:
            score += 10
            factors.append(f"Moderate agricultural income (INR {features.mandi_sales_total:,.2f} mandi sales) detected.")
        elif features.mandi_sales_total > 0:
            score += 5
            factors.append("Minor crop sales recorded; basic crop cycle cashflow exists.")
        else:
            score -= 10
            factors.append("No mandi sales detected. Lacks verifiable crop income proxy.")

        # 4. UPI/Recharge Patterns (Max +10)
        if features.upi_transaction_count > 25:
            score += 10
            factors.append("High volume of active UPI usage reflects integration into the digital transaction ecosystem.")
        elif features.upi_transaction_count > 10:
            score += 5
            factors.append("Moderate digital transactions through UPI observed.")
        
        # Clamp score between 30 and 95
        score = max(30, min(95, score))

        # Generate explanation based on score
        if score >= 75:
            explanation = (
                f"Customer demonstrates excellent creditworthiness. Regular mandi inflows of "
                f"INR {features.mandi_sales_total:,.2f} and utility payment regularity of "
                f"{int(features.utility_payment_regularity*100)}% indicate a highly stable profile, "
                f"comfortably compensating for the absence of standard credit history."
            )
        elif score >= 55:
            explanation = (
                f"Customer displays a moderate credit profile. Income from mandi sales is present but "
                f"savings buffer is modest ({int(features.net_savings_ratio*100)}%). Financial behavior "
                f"is generally disciplined, showing consistent utility payments but low capital cushion."
            )
        else:
            explanation = (
                f"High-risk profile. The customer exhibits erratic cash inflows, low net savings ratio, "
                f"and poor bill payment regularity ({int(features.utility_payment_regularity*100)}%). "
                f"Requires structural credit caution."
            )

        return score, factors, explanation

    @classmethod
    async def process(cls, features: AggregatedFeatures, previous_score: int = 50) -> ScoringResult:
        # Compute deterministic baseline first
        det_score, det_factors, det_explanation = cls._compute_deterministic_score(features)
        
        score = det_score
        factors = det_factors
        explanation = det_explanation

        # If LLM keys are configured, use LLM to perform reasoning
        if not MOCK_LLM_MODE:
            prompt = f"""
            Analyze the following alternative credit features of a customer and output a credit score (0-100), 
            a list of 3 key positive/negative reasoning factors, and a summary explanation of their credit profile.
            
            Customer Features:
            - Net Savings Ratio: {features.net_savings_ratio} (1.0 = saves everything, negative = spends more than income)
            - Utility Bill Payment Regularity: {features.utility_payment_regularity} (1.0 = always on time, 0.0 = always late)
            - Total Mandi Crop Sales: INR {features.mandi_sales_total} ({features.mandi_sales_frequency} sales transactions)
            - UPI Digital Transaction Count: {features.upi_transaction_count}
            - Average Transaction Size: INR {features.average_transaction_value}
            - Mobile Recharge Validity Frequency: {features.recharge_frequency_days} days
            - History Length: {features.data_history_days} days
            
            Strictly respond in JSON format with keys:
            {{
                "score": int (30 to 95),
                "reasoning_factors": ["factor 1", "factor 2", "factor 3"],
                "explanation": "summary explanation string"
            }}
            """
            
            try:
                if GEMINI_API_KEY and gemini_client:
                    # Call Gemini
                    response = gemini_client.models.generate_content(
                        model='gemini-2.5-flash',
                        contents=prompt,
                    )
                    # Clean up markdown JSON wrapper if present
                    text = response.text.strip().replace("```json", "").replace("```", "").strip()
                    res = json.loads(text)
                    score = int(res["score"])
                    factors = res["reasoning_factors"]
                    explanation = res["explanation"]
                    
                elif ANTHROPIC_API_KEY and anthropic_client:
                    # Call Claude
                    response = anthropic_client.messages.create(
                        model="claude-3-5-sonnet-20241022",
                        max_tokens=500,
                        messages=[{"role": "user", "content": prompt}]
                    )
                    text = response.content[0].text.strip().replace("```json", "").replace("```", "").strip()
                    res = json.loads(text)
                    score = int(res["score"])
                    factors = res["reasoning_factors"]
                    explanation = res["explanation"]
                    
            except Exception as e:
                print(f"LLM Scoring Agent call failed: {e}. Falling back to rule-based engine.")

        score_delta = score - previous_score
        
        result = ScoringResult(
            customer_id=features.customer_id,
            score=score,
            score_delta=score_delta,
            reasoning_factors=factors,
            explanation=explanation,
            timestamp=datetime.utcnow()
        )
        
        log_agent_decision(
            customer_id=features.customer_id,
            agent_name="ScoringAgent",
            event_type="credit_scored",
            payload=result.model_dump()
        )
        
        return result


# =====================================================================
# 3. RISK AGENT
# =====================================================================
class RiskAgent:
    @staticmethod
    def _compute_deterministic_risk(score: int, features: AggregatedFeatures) -> Tuple[str, float, str]:
        """Calculates risk parameters deterministically for fast local testing/fallback."""
        # Risk Tier
        if score >= 75:
            risk_tier = "Low"
            # Capped at 60% of monthly average inflow (total_inflow / 2 since history is 30 days usually)
            limit_multiplier = 0.60
        elif score >= 55:
            risk_tier = "Medium"
            limit_multiplier = 0.35
        else:
            risk_tier = "High"
            limit_multiplier = 0.0

        # Compute average monthly inflow (features represents the last 30-day window)
        monthly_inflow = features.total_inflow
        raw_limit = monthly_inflow * limit_multiplier
        
        # Round to nearest 500
        max_loan_limit = round(raw_limit / 500.0) * 500.0
        
        # Absolute caps
        if risk_tier == "Low":
            max_loan_limit = max(5000.0, min(50000.0, max_loan_limit))
        elif risk_tier == "Medium":
            max_loan_limit = max(2000.0, min(20000.0, max_loan_limit))
        else:
            max_loan_limit = 0.0

        justification = (
            f"Assigned risk tier: {risk_tier}. Exposure set to {int(limit_multiplier*100)}% of average "
            f"monthly inflow (INR {monthly_inflow:,.2f}) based on credit score {score}. "
        )
        if risk_tier == "High":
            justification += "No credit exposure recommended due to high probability of default indicators."
        else:
            justification += f"Proposed maximum microloan ceiling is INR {max_loan_limit:,.2f}."

        return risk_tier, max_loan_limit, justification

    @classmethod
    async def process(cls, scoring_result: ScoringResult, features: AggregatedFeatures) -> RiskResult:
        score = scoring_result.score
        
        det_tier, det_limit, det_justification = cls._compute_deterministic_risk(score, features)
        
        risk_tier = det_tier
        max_loan_limit = det_limit
        justification = det_justification
        
        if not MOCK_LLM_MODE:
            prompt = f"""
            Act as a Microfinance Risk Officer. Evaluate this candidate for credit risk and set a recommended 
            loan ceiling.
            
            Customer Profile:
            - Shadow Credit Score: {score}
            - Total Inflow (Monthly): INR {features.total_inflow}
            - Total Outflow (Monthly): INR {features.total_outflow}
            - Net Savings Ratio: {features.net_savings_ratio}
            - Utility bill regularity: {features.utility_payment_regularity}
            
            Rules:
            1. Risk Tier is 'Low' if score >= 75. Exposure limit is up to 60% of monthly inflow (Max INR 50k).
            2. Risk Tier is 'Medium' if score >= 55 and < 75. Exposure limit is up to 35% of monthly inflow (Max INR 20k).
            3. Risk Tier is 'High' if score < 55. Exposure limit is 0 (Reject).
            
            Respond strictly in JSON with keys:
            {{
                "risk_tier": "Low" | "Medium" | "High",
                "max_loan_limit": float,
                "justification": "Short reasoning explaining the limit, tier, and monthly income multiple used."
            }}
            """
            
            try:
                if GEMINI_API_KEY and gemini_client:
                    response = gemini_client.models.generate_content(
                        model='gemini-2.5-flash',
                        contents=prompt,
                    )
                    text = response.text.strip().replace("```json", "").replace("```", "").strip()
                    res = json.loads(text)
                    risk_tier = res["risk_tier"]
                    max_loan_limit = float(res["max_loan_limit"])
                    justification = res["justification"]
                    
                elif ANTHROPIC_API_KEY and anthropic_client:
                    response = anthropic_client.messages.create(
                        model="claude-3-5-sonnet-20241022",
                        max_tokens=500,
                        messages=[{"role": "user", "content": prompt}]
                    )
                    text = response.content[0].text.strip().replace("```json", "").replace("```", "").strip()
                    res = json.loads(text)
                    risk_tier = res["risk_tier"]
                    max_loan_limit = float(res["max_loan_limit"])
                    justification = res["justification"]
                    
            except Exception as e:
                print(f"LLM Risk Agent call failed: {e}. Falling back to risk engine.")

        result = RiskResult(
            customer_id=features.customer_id,
            shadow_score=score,
            risk_tier=risk_tier,
            max_loan_limit=max_loan_limit,
            justification=justification,
            timestamp=datetime.utcnow()
        )
        
        log_agent_decision(
            customer_id=features.customer_id,
            agent_name="RiskAgent",
            event_type="risk_evaluated",
            payload=result.model_dump()
        )
        
        return result


# =====================================================================
# 4. COMPLIANCE AGENT (Strictly Deterministic Rule Engine)
# =====================================================================
class ComplianceAgent:
    @staticmethod
    def process(risk_result: RiskResult, features: AggregatedFeatures) -> ComplianceResult:
        rules = []
        
        # Rule 1: Consent present
        consent_passed = features.consent_flag == True
        rules.append(TriggeredRule(
            rule_id="RULE_CONSENT",
            description="Verify customer consent is explicitly granted for alternate data underwriting",
            passed=consent_passed,
            value=features.consent_flag
        ))
        
        # Rule 2: Minimum history length (>= 30 days)
        # Note: In our synthetic database we seed 30 days, so this is critical
        history_passed = features.data_history_days >= 30
        rules.append(TriggeredRule(
            rule_id="RULE_MIN_HISTORY",
            description="Verify minimum data stream history of 30 days is available",
            passed=history_passed,
            value=f"{features.data_history_days} days"
        ))
        
        # Rule 3: Exposure Limit Bounds (<= INR 50,000 regulatory cap)
        limit_passed = risk_result.max_loan_limit <= 50000.0
        rules.append(TriggeredRule(
            rule_id="RULE_LIMIT_BOUNDS",
            description="Proposed exposure limit must be within regulatory microloan ceiling (INR 50,000)",
            passed=limit_passed,
            value=risk_result.max_loan_limit
        ))
        
        # Rule 4: Active Inflows
        inflow_passed = features.total_inflow > 0
        rules.append(TriggeredRule(
            rule_id="RULE_ACTIVE_INFLOWS",
            description="Customer must have recorded positive agricultural or digital cash inflows",
            passed=inflow_passed,
            value=features.total_inflow
        ))

        # Check final status
        all_passed = all(r.passed for r in rules)
        
        status = "APPROVED"
        rejection_reason = None
        
        if not all_passed:
            failed_ids = [r.rule_id for r in rules if not r.passed]
            status = "REJECTED"
            rejection_reason = f"Regulatory compliance rules failed: {', '.join(failed_ids)}"
        elif risk_result.risk_tier == "High" or risk_result.max_loan_limit == 0:
            status = "HOLD"
            rejection_reason = "Risk rating exceeds risk-tolerance thresholds. Placed on credit review hold."

        result = ComplianceResult(
            customer_id=features.customer_id,
            status=status,
            triggered_rules=rules,
            rejection_reason=rejection_reason,
            decision_timestamp=datetime.utcnow()
        )
        
        log_agent_decision(
            customer_id=features.customer_id,
            agent_name="ComplianceAgent",
            event_type="compliance_audited",
            payload=result.model_dump()
        )
        
        return result


# =====================================================================
# 5. BANK MITRA NOTIFICATION AGENT
# =====================================================================
class BankMitraNotificationAgent:
    @staticmethod
    def process(compliance_result: ComplianceResult, risk_result: RiskResult) -> NotificationResult:
        customer_id = compliance_result.customer_id
        meta = CUSTOMER_METADATA.get(customer_id, {})
        customer_name = meta.get("name", "Unnamed Customer")
        
        # Only build real notification if approved
        if compliance_result.status == "APPROVED" and risk_result.max_loan_limit > 0:
            approved_amount = risk_result.max_loan_limit
            interest_rate = 12.0 # Standard 12% p.a.
            tenure_months = 6     # Standard 6 months
            
            # Repayment calculations (Weekly installments)
            # Total Repayment = Principal + (Principal * Rate * (Tenure/12))
            total_repayment = approved_amount * (1.0 + (interest_rate / 100.0) * (tenure_months / 12.0))
            weeks = tenure_months * 4.0
            repayment_amount = round(total_repayment / weeks, 2)
            
            sms_preview = (
                f"Namaste {customer_name}, you have been PRE-APPROVED for a microloan of "
                f"INR {approved_amount:,.0f} (Weekly repayment: INR {repayment_amount:.0f}). "
                f"Our Bank Mitra Rajesh will contact you shortly to complete disbursal."
            )
            status = "PENDING_DISBURSAL"
        else:
            approved_amount = 0.0
            interest_rate = 0.0
            tenure_months = 0
            repayment_amount = 0.0
            sms_preview = "No approved credit offer package available for this customer profile."
            status = "REJECTED_BY_CUSTOMER" if compliance_result.status == "REJECTED" else "PENDING_DISBURSAL"
            
        notification = NotificationResult(
            notification_id=f"notif_{uuid_gen()}",
            customer_id=customer_id,
            customer_name=customer_name,
            approved_amount=approved_amount,
            interest_rate_annual=interest_rate,
            tenure_months=tenure_months,
            repayment_frequency="Weekly",
            repayment_amount=repayment_amount,
            sms_preview=sms_preview,
            status=status,
            timestamp=datetime.utcnow()
        )
        
        log_agent_decision(
            customer_id=customer_id,
            agent_name="NotificationAgent",
            event_type="notification_formatted",
            payload=notification.model_dump()
        )
        
        return notification

def uuid_gen() -> str:
    import uuid
    return uuid.uuid4().hex[:10]
