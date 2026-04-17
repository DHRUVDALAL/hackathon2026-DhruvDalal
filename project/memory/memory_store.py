from __future__ import annotations

from typing import Any, Dict, List, Optional


memory: Dict[str, Any] = {
    "customers": {},
    "tickets": [],
}


def _refund_issued_from_execution(execution: Optional[Dict[str, Any]]) -> bool:
    if not execution or not isinstance(execution, dict):
        return False
    for r in execution.get("results") or []:
        if not isinstance(r, dict):
            continue
        if r.get("tool_used") == "issue_refund" and str((r.get("result") or {}).get("status", "")) == "success":
            return True
    return False


def update_memory(ticket: Dict[str, Any], decision: Dict[str, Any], execution: Optional[Dict[str, Any]] = None) -> None:
    """Store past decisions and track per-customer counts (basic Phase 2 memory)."""
    ticket_id = ticket.get("ticket_id")
    customer_id = ticket.get("customer_id")
    action = decision.get("action")

    memory["tickets"].append({"ticket_id": ticket_id, "customer_id": customer_id, "action": action})

    if not customer_id:
        return

    cust = memory["customers"].setdefault(customer_id, {"decisions": [], "refund_count": 0})
    cust["decisions"].append({"ticket_id": ticket_id, "action": action})

    # Phase 2 refinement: increment refund_count only when a refund was actually issued.
    # (Fallback for older flows where execution isn't provided.)
    if _refund_issued_from_execution(execution) or (execution is None and action == "approve_refund"):
        cust["refund_count"] += 1


def get_customer_history(customer_id: str) -> Dict[str, Any]:
    return memory["customers"].get(customer_id, {"decisions": [], "refund_count": 0})


# Dead-letter queue (DLQ) — final refinements
# Backwards compatible: existing callers can still pass (ticket_id, reason).
from datetime import datetime, timezone

_failed_tickets: List[Dict[str, Any]] = []


def add_failed_ticket(ticket_id: str, failed_step_or_reason: str, error_or_context: Optional[Dict[str, Any]] = None) -> None:
    """Dead-letter queue entry point.

    Backwards compatible:
    - New: add_failed_ticket(ticket_id, failed_step, error_dict)
    - Old: add_failed_ticket(ticket_id, reason, context_dict?)
    """

    ts = datetime.now(timezone.utc)

    # New signature: error dict has strict keys.
    if isinstance(error_or_context, dict) and (
        "error_code" in error_or_context or "retryable" in error_or_context or "error" in error_or_context
    ):
        err = error_or_context
        _failed_tickets.append(
            {
                "ticket_id": str(ticket_id),
                "failed_step": str(failed_step_or_reason),
                "reason": str((err or {}).get("error") or "unknown"),
                "error_code": (err or {}).get("error_code"),
                "timestamp": ts.isoformat(),
            }
        )
        return

    # Old signature: second arg is reason, third is optional context.
    ctx = error_or_context if isinstance(error_or_context, dict) else {}
    failed_step = ctx.get("failed_step") or "unknown"
    last_error_code = ctx.get("last_error_code")

    _failed_tickets.append(
        {
            "ticket_id": str(ticket_id),
            "failed_step": str(failed_step),
            "reason": str(failed_step_or_reason or "unknown"),
            "error_code": last_error_code,
            "timestamp": ts.isoformat(),
        }
    )


def get_failed_tickets() -> List[Dict[str, Any]]:
    return _failed_tickets
