# Build Prompt: Sankalp — Agentic AI Credit Scout

Copy everything below the line into your coding tool (Claude Code, Cursor, etc.) as the initial project prompt.

---

## Role
You are a senior full-stack engineer and AI systems architect. You are building a working hackathon prototype in a 24–48 hour window. Prioritize a runnable, demoable end-to-end system over completeness — a thin vertical slice that actually works beats a broad system that's half-wired.

## Project Context
"Sankalp" is an agentic AI system that identifies creditworthy individuals who are invisible to traditional credit-bureau underwriting — people in rural/semi-urban India with no formal credit history but consistent informal financial behavior (utility bill payments, UPI/mandi transaction regularity, mobile recharge patterns). The system continuously scores these customers from alternative data and autonomously pre-approves microloans, routed through a correspondent-banking field-agent (a "Bank Mitra") for human-delivered disbursal.

The demo's centerpiece must be a **live, visibly-updating credit score** — not a static number. Judges need to watch a synthetic transaction stream come in and see the score, risk tier, and pre-approval decision update in real time on screen.

## Core Objective
Build an end-to-end working prototype with four cooperating agents, a live data simulation layer, and a dashboard that visualizes the whole pipeline updating in real time.

## Agent Specification
Implement each as a distinct, separately callable module (not one monolithic prompt) so the architecture is visibly modular in code and in the demo narration:

1. **Data Aggregation Agent**
   - Input: a stream of synthetic transaction/event records (utility payment, UPI transfer, mandi sale, mobile recharge)
   - Output: a structured, normalized feature set per customer (payment regularity, average transaction size, income proxy, seasonality pattern)
   - Must run continuously against a simulated live feed, not a one-shot batch call

2. **Scoring Agent**
   - Input: normalized features from the Data Aggregation Agent
   - Output: a 0–100 "shadow credit score" plus a natural-language explanation of the key factors driving the score (use the LLM here — this is the agent that should visibly "reason," not just run arithmetic)
   - Must update incrementally as new events arrive, not recompute from scratch with a full re-prompt each time — describe your incremental-update approach before implementing it

3. **Risk Agent**
   - Input: shadow credit score + normalized features
   - Output: a recommended loan-limit ceiling and risk tier (Low/Medium/High), reasoned against configurable exposure rules (e.g., max exposure as a multiple of average monthly inflow)
   - Must produce a short justification string, not just a number

4. **Compliance Agent**
   - Input: proposed loan offer from the Risk Agent
   - Output: approve / hold / reject, checked against a small explicit rule set (e.g., minimum data history length, consent flag present, exposure within regulatory-style bounds you define)
   - This agent's decisions must be logged with the specific rule that triggered them — the audit trail is a first-class feature, not an afterthought

5. **Bank Mitra Notification Agent**
   - Input: compliance-approved offer
   - Output: a formatted pre-approval notification (render this as a second, distinct UI view — a mobile-style "field agent" screen — showing what a Bank Mitra would see)

## Data Simulation Requirements
- Since no real transaction API is available, build a **synthetic event generator** that streams realistic-looking events (utility bill payment, UPI transaction, mandi sale, recharge) for 2–3 demo customer profiles, at a rate visible to a live audience (roughly 1 event every 1–3 seconds)
- Push events over a WebSocket (or Server-Sent Events) from a backend service to the frontend, so the dashboard updates without polling or manual refresh
- Include at least one demo customer whose events show a clear improving trend (score rises visibly during the demo) and one whose profile is already strong (fast pre-approval) — two distinct visible outcomes in one demo run

## Technology Stack
- **Backend:** Python (FastAPI) for the agent pipeline and WebSocket server
- **AI layer:** Claude API (Anthropic) for the Scoring Agent's reasoning/explanation and the Risk Agent's justification text; keep prompts short and structured (return JSON) so they're fast enough for a live-feeling update loop
- **Event bus:** in-process async queue is fine for a hackathon scope — do not over-engineer with Kafka/RabbitMQ unless time allows
- **Frontend:** React, WebSocket client, a live-updating score gauge/chart component (use a charting library such as Recharts) and a running event-log feed
- **Storage:** SQLite or in-memory store is sufficient — this is a demo, not production; keep it simple and fast to set up
- **Audit log:** a simple structured log (JSON lines file or SQLite table) capturing every agent decision with a timestamp and the triggering rule/reason

## Process Flow (for your own reference and for the architecture diagram)
```
Synthetic Event Stream
   -> Data Aggregation Agent (normalizes features)
   -> Scoring Agent (LLM: score + explanation)
   -> Risk Agent (LLM: loan ceiling + risk tier + justification)
   -> Compliance Agent (rule-based gate: approve/hold/reject)
   -> Bank Mitra Notification Agent (formats pre-approval)
   -> Frontend (live dashboard + field-agent view), fed via WebSocket
   -> Audit Log (every agent decision, every step)
```

## Deliverables
1. A running backend that generates the synthetic stream and processes it through all four agents
2. A React frontend with two views: (a) the live customer-scoring dashboard, (b) the Bank Mitra field-agent notification view
3. A visible, readable audit trail (a simple table or log viewer is fine) showing each agent's decision and reasoning for at least one full customer journey
4. A short `README.md` explaining what's real (the agent logic, the compliance gating) versus what's simulated (the transaction data source) — be explicit about this distinction, since judges will ask

## Constraints and Guardrails
- Do not fabricate real API integrations you don't have — clearly label the data source as "simulated live feed representing UPI/CBS/utility data" in both the UI and the README. Judges respect honesty about what's mocked far more than a claim that collapses under a follow-up question.
- Keep each agent's LLM call fast (small, structured prompts, JSON output) — a live demo cannot tolerate multi-second lag per event
- Build the Compliance Agent's rules as actual explicit code (if/else or a small rules table), not an LLM call — this agent needs to be deterministic and auditable, which is part of the pitch
- Prioritize in this order if time runs short: (1) working live score update on screen, (2) audit trail visible, (3) Bank Mitra view, (4) polish/animation

## First Steps — What I Want From You Right Now
1. Propose a concrete file/folder structure for this project
2. Propose the JSON schema for a single synthetic transaction event and for each agent's output
3. Then scaffold the backend (FastAPI app, WebSocket endpoint, synthetic event generator) before writing any agent logic, so we can verify the live-stream plumbing works first
4. Confirm each step with me before moving to the next agent — build and test incrementally, one agent at a time, rather than writing the whole pipeline at once
