# Sankalp — Agentic AI Credit Scout

Sankalp is an agentic AI credit scoring and autonomous microloan underwriting system designed for rural and semi-urban India. It identifies creditworthy individuals who are "invisible" to traditional credit bureaus by analyzing alternate data streams (Mandi transactions, UPI payment frequency, utility bills, and mobile recharges).

---

## 🏛 Architecture & Process Flow

Sankalp is built with a decoupled, modular multi-agent pipeline:

```
Synthetic Event Stream (UPI, Mandi, Utility, Recharge)
   -> 1. Data Aggregation Agent (features normalization)
   -> 2. Scoring Agent (LLM / Fallback: shadow score + explanation)
   -> 3. Risk Agent (LLM / Fallback: loan ceiling + risk tier + justification)
   -> 4. Compliance Agent (Rule-based: deterministic regulatory gates)
   -> 5. Bank Mitra Notification Agent (formats approved offer)
   -> Frontend Dashboard (live admin feed + Bank Mitra phone mockup), fed via WebSockets
   -> Audit Log Database (captures every step, payload, and rule triggered)
```

---

## 🔍 What's Real vs. What's Simulated?

Judges at the hackathon will ask about the fidelity of the prototype. Here is the explicit breakdown:

| Component | What's Real | What's Simulated |
| :--- | :--- | :--- |
| **Data Aggregator Agent** | Actual Pydantic parsing and SQLite queries calculating true math aggregates (net savings, timeliness, transaction frequencies). | None. Runs actual calculations. |
| **Scoring & Risk Agents** | Real pipeline integration supporting **Gemini 2.5** and **Claude 3.5** API prompts returning JSON, alongside a deterministic rule-based fallback engine. | The API keys are loaded via a `.env` file; if missing, it runs the fallback engine. |
| **Compliance Agent** | Strictly deterministic rule-based validator evaluating regulatory boundaries (consent, minimum history length, max limits). | None. Operates exactly like a production core banking rule engine. |
| **Bank Mitra Agent** | Formats real Weekly repayment packages based on standard interest math (12% p.a. over 6 months) and pushes to the client. | None. |
| **Transaction Feed** | None. | Fully synthetic event generator that streams randomized transactional events every 2 seconds to simulate live mobile/agricultural activity. |
| **Audit Trail Logs** | Every decision, rule evaluate, and payload is written to a real SQLite database (`sankalp.db`) and queried dynamically in the UI. | None. |

---

## 👥 Demo Customer Profiles

We simulate three distinct personas to showcase the system's underwriting intelligence:

1. **Ramesh Dev (`CUST_STRONG_START`)**: A seasoned farmer with high Mandi crop inflows, active UPI digital transaction volumes, and 100% utility payment regularity. **Result: High Credit Score (95), Approved for maximum ₹50,000 package.**
2. **Sita Patil (`CUST_TRENDING_UP`)**: A dairy worker who starts with minor inflows and late utility bills, but improves her metrics significantly over time (increasing Mandi sales, zero late days). **Result: Shadow score rises dynamically on screen from 42 to 75, leading to Medium Risk Approval.**
3. **Vikram Singh (`CUST_VOLATILE`)**: An erratic client with multiple failed UPI transactions, constant utility defaults (10-35 days late), and has NOT providedAlternate underwriting consent. **Result: Score remains low (~45), Compliance blocks the application on `RULE_CONSENT` (Rejected/Hold).**

---

## 🚀 How to Run the Project

### Prerequisites
- Python 3.13+ (or standard Windows Launcher `py`)
- Node.js LTS (24.18.0) and npm (11.16.0)

### Step 1: Start the FastAPI Backend
1. Open a terminal in the root workspace `d:\SBI`.
2. Run:
   ```powershell
   backend\venv\Scripts\python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
   ```
   *Note: On first boot, the backend automatically seeds a 45-day historical baseline into `backend/sankalp.db`.*

### Step 2: Start the React + Vite Frontend
1. Open a separate terminal in `d:\SBI\frontend`.
2. Ensure you bypass script restrictions and append Node.js to your path if it's a new shell session:
   ```powershell
   Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope Process
   $env:Path += ';C:\Program Files\nodejs'
   npm run dev
   ```
3. Open your browser and navigate to **[http://localhost:5173/](http://localhost:5173/)**.

---

## 🛠 Tech Stack Details
- **Backend:** Python, FastAPI, Uvicorn, SQLite, Pydantic v2, websockets, python-dotenv, google-genai, anthropic.
- **Frontend:** React, Vite, Recharts (responsive line charts), Lucide React (premium iconography).
