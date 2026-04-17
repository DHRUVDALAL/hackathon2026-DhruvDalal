# Failure Modes

## Tool timeout / transient failure
- Behavior: tool call raises an exception (simulated failure)
- Handling: retry (limited attempts) → if still failing, auto-escalate case

## Invalid order
- Behavior: order_id missing or order not found
- Handling: decision agent chooses `ask_clarification` or `invalid_order` and plan executes `send_reply`

## Fraud detection
- Behavior: decision agent flags fraud
- Handling: decision agent chooses `flag_fraud` and plan executes `send_reply` (no automated refund/cancel)

## Invalid tool output
- Behavior: tool returns wrong schema
- Handling: schema validation fails → treated as tool failure → retry → auto-escalate
