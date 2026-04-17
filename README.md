# AI Customer Support Resolution System

Production-grade **Multi-Agent AI Customer Support Automation System** built for enterprise-style reliability, observability, and failure recovery.

This is **not** a chatbot. It is a decision-making, tool-orchestrating AI operations system that processes support tickets end-to-end with **strict validation**, **retries**, **escalation workflows**, **Dead Letter Queue (DLQ)** handling, and **full audit logging**.

---

## What This System Demonstrates

- **Multi-agent orchestration** for real support operations (understanding → decisions → planning → tool execution)
- **Reliability-first execution** with strict schemas and controlled failure handling
- **Observability and compliance** via step-by-step audit trails (`audit_log.json`)
- **Resilience patterns** used in production systems: retries, escalation, DLQ routing
- **Hackathon-ready demos** of deterministic retry success and DLQ failure containment

---

## Core System Flow

```
User Ticket
→ Understanding Agent
→ Decision Agent
→ Planner Agent
→ Tool Executor Agent
→ Validation Layer
→ Retry Engine
→ Escalation Logic
→ DLQ (if unrecoverable)
→ Final Response
→ Audit Log Export
```

---

## Multi-Agent Architecture

### 1) Understanding Agent
Responsible for converting raw, ambiguous tickets into structured signals:
- intent extraction
- entity detection
- ticket understanding

### 2) Decision Agent
Applies policy + business rules to determine the correct action:
- policy decisions
- confidence scoring
- business rule validation
- escalation logic

### 3) Planner Agent
Generates safe, minimum viable tool chains before execution:
- tool chain generation
- minimum 3-step safe execution plans

### 4) Tool Executor Agent
Executes tool calls with production-style safeguards:
- safe tool execution
- schema validation
- retry handling
- escalation fallback
- DLQ routing

---

## Tools Used (Simulated Enterprise Tooling)

The system orchestrates a realistic tool surface, including:

- `get_customer()`
- `get_order()`
- `get_product()`
- `issue_refund()`
- `approve_return()`
- `reject_return()`
- `initiate_exchange()`
- `cancel_order()`
- `send_reply()`
- `escalate_case()`
- `knowledge_search()`
- `refund_eligibility_check()`

These tools are treated like real integrations: every call is validated, failures are structured, and retries/escalations are handled deterministically.

---

## Reliability & Safety Features

### 1) Strict Schema Validation (Non-Negotiable)

All tool failures must conform to a strict failure schema:

```json
{
  "status": "failed",
  "error_code": "PAYMENT_TIMEOUT",
  "error": "Payment gateway timeout",
  "retryable": true
}
```

This makes failures:
- machine-actionable
- traceable
- safe to retry
- consistent across tools

### 2) Retry Engine (Max 3, Exponential Backoff)

- Maximum retries: **3**
- Backoff pattern:

```
0.5s
1.0s
2.0s
```

Retries are logged and auditable, and the system stops retrying when failures are marked `retryable: false`.

### 3) Dead Letter Queue (DLQ) for Unrecoverable Failures

When a tool failure cannot be recovered:
- tool failure
  → escalation
  → final failure
  → **DLQ**

DLQ ensures the system fails safely without losing context and enables operational handoff.

### 4) Full Audit Logging

Every ticket produces an audit trail with step payloads and final outcomes.

Exported to:

- `audit_log.json`

This is designed for:
- debugging
- incident analysis
- compliance narratives
- judge/recruiter transparency

---

## Demo Scenarios (Deterministic, Judge-Friendly)

### TKT-023 — Retry Success Demo
Demonstrates resilience under transient failures:
- refund tool fails **twice**
- succeeds on **attempt 3**
- shows retry engine + backoff working as designed

### TKT-021 — DLQ Demo
Demonstrates safe failure containment:
- refund tool permanently fails
- escalation also fails
- ticket is moved to **DLQ**

---

## Final System Metrics

| Metric | Value |
|---|---:|
| Total Tickets | 29 |
| Success | 28 |
| Failed | 1 |
| DLQ | 1 |
| Success Rate | 96.6% |
| Total Retries | 6 |
| Avg Processing Time | ~0.9s |

---

## Frontend Dashboard (Premium Demo UI)

A professional static dashboard is included for demos and judge review. It visualizes:
- KPI cards
- Ticket table
- Retry demo
- DLQ panel
- Audit trail
- Architecture flow
- Executive summary

**Frontend stack**
- HTML
- CSS
- JavaScript

**Data source**
- `frontend/assets/sample-data.json`

The dashboard is intentionally decoupled from backend runtime APIs to keep demos stable and reproducible.

---

## Tech Stack

### Backend
- Python 3
- JSON-based data and execution traces
- Rule-based orchestration
- Retry engine (max 3, exponential backoff)
- Validation layer (strict schemas)
- Memory store (support context)
- Audit export (`audit_log.json`)

### Frontend
- HTML
- CSS
- JavaScript

---

## How to Run

### Backend

```bash
cd project
python3 main.py
```

### Frontend

```bash
cd frontend
npx live-server
```

Open:

- http://127.0.0.1:8080

---

## Why This Project Wins

Most “AI support” hackathon projects are chat demos. This system is built like an **enterprise AI operations platform**:

- **Not a chatbot**: structured decision-making + tool orchestration
- **Reliability-first**: strict schema validation prevents ambiguous tool failures
- **Resilient execution**: bounded retries + exponential backoff
- **Safe failure handling**: escalation pathways and DLQ containment
- **Operational transparency**: full audit logging suitable for compliance and debugging
- **Demo readiness**: deterministic scenarios (retry success + DLQ) that showcase production-grade behavior

If you want to evaluate real-world readiness of AI automation, this is the bar: **observability, control, and safety** — not just responses.

---

## Future Scope

- LLM integration (intent extraction + reasoning upgrades)
- CRM integrations
- database persistence
- production deployment
- analytics dashboards
- email automation
- Slack escalation workflows
