# Autonomous Support Agent

## How to run

```bash
python3 main.py
```

## Features

- Multi-agent reasoning (rule-based)
- Tool chaining (3+ tools where applicable)
- Retry & failure handling (with simulated failures)
- Memory system
- Audit logging + export to `audit_log.json`

## Tools Used

- get_order
- get_customer
- get_product
- search_knowledge_base
- check_refund_eligibility
- issue_refund
- cancel_order
- send_reply
- escalate_case

## Architecture

Understanding → Decision → Planning → Tool Execution → Response → Memory → Audit
