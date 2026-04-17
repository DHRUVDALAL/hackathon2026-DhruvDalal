from __future__ import annotations

import os
import random
from typing import Any, Dict, Optional

from utils.errors import ToolError, error_result


# Deterministic-by-default: random flakiness can be enabled for stress demos.
# Set TOOL_FAIL_RATE (0..1) to a small value like 0.02 to simulate real-world instability.
try:
    _TOOL_FAIL_RATE = float(os.getenv("TOOL_FAIL_RATE", "0"))
except Exception:
    _TOOL_FAIL_RATE = 0.0


def _maybe_fail() -> None:
    # Phase 3+: simulate flaky tool execution with realistic production errors.
    # IMPORTANT: Only retryable failures here to keep the demo stable.
    if _TOOL_FAIL_RATE <= 0:
        return

    if random.random() < _TOOL_FAIL_RATE:
        choice = random.random()
        if choice < 0.34:
            raise ToolError("PAYMENT_TIMEOUT", "Payment service timeout", retryable=True)
        if choice < 0.67:
            raise ToolError("DB_CONNECTION_LOST", "Database connection lost", retryable=True)
        raise ToolError("RATE_LIMIT", "Third-party API rate limit exceeded", retryable=True)


def check_refund_eligibility(order: Optional[Dict[str, Any]], product: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Hackathon tool: simple refund eligibility check (no external APIs)."""
    # Deterministic API-timeout demo (eligibility service)
    oid = str((order or {}).get("order_id") or "")
    if oid == "ORD-ELIG-RETRY" and oid not in _FORCED_REFUND_FAILURES:
        _FORCED_REFUND_FAILURES.add(oid)
        return error_result(
            error_code="RATE_LIMIT",
            error="Third-party API rate limit exceeded",
            retryable=True,
        )

    try:
        _maybe_fail()
    except ToolError as e:
        return error_result(error_code=e.error_code, error=e.message, retryable=bool(e.retryable), details=e.details)

    if not order or not product:
        return {"eligible": False, "reason": "Missing data"}

    if order.get("status") != "delivered":
        return {"eligible": False, "reason": "Order not delivered"}

    days = order.get("days_since_delivery", 0)
    try:
        days = int(days or 0)
    except Exception:
        days = 0

    win = product.get("return_window_days", 0)
    try:
        win = int(win or 0)
    except Exception:
        win = 0

    if days <= win:
        return {"eligible": True, "reason": "Within return window"}

    wm = product.get("warranty_months", 0)
    try:
        wm = int(wm or 0)
    except Exception:
        wm = 0

    if wm > 0:
        return {"eligible": False, "reason": "Warranty case"}

    return {"eligible": False, "reason": "Outside return window"}


# One-time forced failure for retry demo (hackathon judging)
_FORCED_REFUND_FAILURES: set[str] = set()
# Per-order attempt counts (used only for deterministic demo orders)
_REFUND_ATTEMPTS: dict[str, int] = {}


def issue_refund(order: Dict[str, Any]) -> Dict[str, Any]:
    order_id = str(order.get("order_id") or "")

    # DLQ demo: this order always fails.
    # Use a structured error *response* (not an exception) to demo schema + DLQ wiring.
    if order_id == "ORD-FAIL":
        return {
            "status": "failed",
            "error_code": "PAYMENT_TIMEOUT",
            "error": "Payment gateway timeout",
            "retryable": False,
        }

    # Retry success demo: ORD-2001 fails first 2 attempts, succeeds on 3rd.
    if order_id == "ORD-2001":
        n = int(_REFUND_ATTEMPTS.get(order_id, 0)) + 1
        _REFUND_ATTEMPTS[order_id] = n
        if n < 3:
            return {
                "status": "failed",
                "error_code": "PAYMENT_TIMEOUT",
                "error": "Payment gateway timeout",
                "retryable": True,
            }

    # Retry demo (existing dataset): fail once for ORD-1015, then succeed deterministically
    if order_id == "ORD-1015" and order_id not in _FORCED_REFUND_FAILURES:
        _FORCED_REFUND_FAILURES.add(order_id)
        return error_result(
            error_code="PAYMENT_TIMEOUT",
            error="Payment gateway timeout",
            retryable=True,
        )

    # New partial recovery dataset: first attempt hits rate limit, then succeeds
    if order_id == "ORD-2002" and order_id not in _FORCED_REFUND_FAILURES:
        _FORCED_REFUND_FAILURES.add(order_id)
        return error_result(
            error_code="RATE_LIMIT",
            error="Third-party API rate limit exceeded",
            retryable=True,
        )

    # Non-retryable validation error dataset
    if order_id == "ORD-VALFAIL":
        return error_result(
            error_code="REFUND_VALIDATION_ERROR",
            error="Refund API validation error: missing transaction_id",
            retryable=False,
        )

    # For deterministic demo orders, skip random failures.
    if order_id not in {"ORD-1015", "ORD-2001", "ORD-2002"}:
        try:
            _maybe_fail()
        except ToolError as e:
            return error_result(error_code=e.error_code, error=e.message, retryable=bool(e.retryable), details=e.details)

    amt = float(order.get("amount") or 0.0)
    if amt <= 0:
        return error_result(
            error_code="INVALID_REFUND_AMOUNT",
            error="Invalid refund amount",
            retryable=False,
        )

    return {
        "status": "success",
        "refund_amount": amt,
    }


def cancel_order(order: Dict[str, Any]) -> Dict[str, Any]:
    try:
        _maybe_fail()
    except ToolError as e:
        return error_result(error_code=e.error_code, error=e.message, retryable=bool(e.retryable), details=e.details)
    return {"status": "cancelled"}


def send_reply(message: str) -> Dict[str, Any]:
    try:
        _maybe_fail()
    except ToolError as e:
        return error_result(error_code=e.error_code, error=e.message, retryable=bool(e.retryable), details=e.details)
    return {"status": "sent"}


def escalate_case(summary: str) -> Dict[str, Any]:
    # DLQ demo: escalation service rate limiting for the synthetic ticket only
    if "TKT-021" in str(summary):
        return error_result(
            error_code="RATE_LIMIT",
            error="Third-party API rate limit exceeded",
            retryable=True,
        )

    try:
        _maybe_fail()
    except ToolError as e:
        return error_result(error_code=e.error_code, error=e.message, retryable=bool(e.retryable), details=e.details)
    return {"status": "escalated"}
