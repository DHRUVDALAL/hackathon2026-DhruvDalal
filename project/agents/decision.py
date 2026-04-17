from __future__ import annotations

import json
import re
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from memory.memory_store import get_customer_history
from tools.order_tools import get_customer as tool_get_customer
from tools.order_tools import get_product as tool_get_product


_DEFECT_RE = re.compile(r"\b(broken|damaged|defect|defective|not\s+working|isnt\s+working|isn't\s+working|stopped\s+working)\b", re.IGNORECASE)
_CLAIM_TIER_RE = re.compile(r"\b(vip|premium)\b", re.IGNORECASE)
_WARRANTY_UNTIL_RE = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")
_TRACKING_RE = re.compile(r"\bTRK-[A-Z0-9]+\b", re.IGNORECASE)


def _ticket_text(ticket: Any) -> str:
    if isinstance(ticket, str):
        return ticket
    if isinstance(ticket, dict):
        return f"{ticket.get('subject','')} {ticket.get('body','')}".strip()
    return str(ticket)


_CUSTOMERS_CACHE: Optional[List[Dict[str, Any]]] = None


def _load_customers() -> List[Dict[str, Any]]:
    global _CUSTOMERS_CACHE
    if _CUSTOMERS_CACHE is not None:
        return _CUSTOMERS_CACHE

    data_dir = Path(__file__).resolve().parent.parent / "data"
    path = data_dir / "customers.json"
    with path.open("r", encoding="utf-8") as f:
        _CUSTOMERS_CACHE = json.load(f)
    return _CUSTOMERS_CACHE


def _find_product(products: List[Dict[str, Any]], product_id: Optional[str]) -> Optional[Dict[str, Any]]:
    if not product_id:
        return None

    # Prefer tool usage (Phase 3 final fixes)
    try:
        p = tool_get_product(str(product_id))
        if p:
            return p
    except Exception:
        pass

    pid = str(product_id).upper()
    return next((p for p in products if str(p.get("product_id", "")).upper() == pid), None)


def _find_customer(order: Optional[Dict[str, Any]], ticket: Any) -> Optional[Dict[str, Any]]:
    # Prefer tool usage (Phase 3 final fixes)
    cid = str(order.get("customer_id")) if isinstance(order, dict) and order.get("customer_id") else None
    if cid:
        try:
            c = tool_get_customer(str(cid))
            if c:
                return c
        except Exception:
            pass

    # Fallback to local file scan (keeps Phase 1/2 behavior intact)
    customers = _load_customers()

    if cid:
        match = next((c for c in customers if str(c.get("customer_id", "")).upper() == cid.upper()), None)
        if match:
            return match

    email = ticket.get("customer_email") if isinstance(ticket, dict) else None
    if email:
        match = next((c for c in customers if str(c.get("email", "")).lower() == str(email).lower()), None)
        if match:
            return match

    return None


def _parse_ticket_date(ticket: Any) -> Optional[date]:
    if not isinstance(ticket, dict):
        return None
    raw = ticket.get("created_at")
    if not raw:
        return None
    try:
        # Handles 'Z' suffix.
        dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.date()
    except Exception:
        return None


def _parse_ymd(d: Any) -> Optional[date]:
    if not d:
        return None
    try:
        return date.fromisoformat(str(d))
    except Exception:
        return None


def _add_months(d: date, months: int) -> date:
    # Month arithmetic without external libs.
    y = d.year + (d.month - 1 + months) // 12
    m = (d.month - 1 + months) % 12 + 1
    # Clamp day to end-of-month.
    if m == 2:
        leap = (y % 4 == 0 and (y % 100 != 0 or y % 400 == 0))
        last = 29 if leap else 28
    elif m in {1, 3, 5, 7, 8, 10, 12}:
        last = 31
    else:
        last = 30
    return date(y, m, min(d.day, last))


def _return_deadline(order: Dict[str, Any], product: Optional[Dict[str, Any]]) -> Optional[date]:
    # Prefer explicit deadline from orders dataset.
    deadline = _parse_ymd(order.get("return_deadline"))
    if deadline:
        return deadline

    delivery = _parse_ymd(order.get("delivery_date"))
    if not delivery:
        return None

    days = None
    if product and isinstance(product.get("return_window_days"), int):
        days = int(product["return_window_days"])
    if days is None:
        days = 30

    # Avoid importing timedelta repeatedly in hot path.
    from datetime import timedelta

    return delivery + timedelta(days=days)


def _warranty_end(order: Dict[str, Any], product: Optional[Dict[str, Any]]) -> Optional[date]:
    # If order notes include an explicit warranty date, use it.
    notes = str(order.get("notes", ""))
    m = _WARRANTY_UNTIL_RE.search(notes)
    if "warranty" in notes.lower() and m:
        dt = _parse_ymd(m.group(1))
        if dt:
            return dt

    delivery = _parse_ymd(order.get("delivery_date"))
    if not delivery or not product:
        return None

    months = product.get("warranty_months")
    if not isinstance(months, int) or months <= 0:
        return None

    return _add_months(delivery, int(months))


def _detect_claimed_tier(text: str) -> Optional[str]:
    m = _CLAIM_TIER_RE.search(text)
    return m.group(1).lower() if m else None


def _extract_tracking_id(order: Dict[str, Any]) -> Optional[str]:
    notes = str(order.get("notes", ""))
    m = _TRACKING_RE.search(notes)
    return m.group(0).upper() if m else None


def _looks_like_policy_question(text: str) -> bool:
    t = text.lower()
    return any(k in t for k in ("policy", "return policy", "refund policy", "how long", "do you offer exchanges", "exchange"))


def _confidence(level: str) -> float:
    return {"clear": 0.9, "partial": 0.75, "unclear": 0.6}.get(level, 0.6)


def _apply_confidence_delta(decision: Dict[str, Any], delta: float) -> Dict[str, Any]:
    try:
        c = float(decision.get("confidence") or 0.0)
    except Exception:
        return decision
    decision = dict(decision)
    decision["confidence"] = min(0.95, round(c + float(delta), 2))
    return decision


def _baseline_refund_count(customer: Optional[Dict[str, Any]]) -> int:
    """Heuristic: extract historic refund count from customer notes.

    This makes memory-based rules deterministic even under parallel execution.
    """
    if not customer:
        return 0
    notes = str(customer.get("notes") or "").lower()
    m = re.search(r"(\d+)\s+refund", notes)
    if not m:
        return 0
    try:
        return int(m.group(1))
    except Exception:
        return 0


def _finalize_decision(
    decision: Dict[str, Any],
    *,
    customer: Optional[Dict[str, Any]],
    history: Dict[str, Any],
    is_refund_request: bool = False,
) -> Dict[str, Any]:
    """Phase 3: apply memory rules + confidence refinement + low-confidence escalation."""

    # Smart memory usage: frequent refund abuse (escalate on refund requests)
    try:
        if is_refund_request and int(history.get("refund_count") or 0) >= 2:
            decision = {
                "action": "escalate_case",
                "reason": ["Repeated refund requests detected"],
                "confidence": 0.85,
            }
    except Exception:
        pass

    # Phase 2 refinement (kept): excessive refunds always escalate
    try:
        if int(history.get("refund_count") or 0) >= 3:
            decision = {
                "action": "escalate_case",
                "reason": ["Customer has high refund frequency — manual review required."],
                "confidence": 0.85,
            }
    except Exception:
        pass

    # First-time customer: slight confidence bump.
    if customer and customer.get("total_orders") == 1:
        decision = _apply_confidence_delta(decision, 0.05)

    # High-value customer: slight confidence bump.
    try:
        if customer and float(customer.get("total_spent") or 0.0) > 5000:
            decision = _apply_confidence_delta(decision, 0.05)
    except Exception:
        pass

    # If we have prior history for this customer in this run, boost confidence slightly.
    try:
        if history and (history.get("decisions") or []):
            decision = _apply_confidence_delta(decision, 0.03)
    except Exception:
        pass

    # Confidence-based escalation (Phase 3)
    try:
        if float(decision.get("confidence") or 0.0) < 0.7:
            return {
                "action": "escalate_case",
                "reason": ["Low confidence decision — needs manual review."],
                "confidence": 0.7,
            }
    except Exception:
        return {
            "action": "escalate_case",
            "reason": ["Low confidence decision — needs manual review."],
            "confidence": 0.7,
        }

    return decision


def decide_action(
    ticket: Any,
    understanding: Dict[str, Any],
    order: Optional[Dict[str, Any]],
    products: List[Dict[str, Any]],
) -> Dict[str, Any]:
    reasons: List[str] = []

    text = _ticket_text(ticket)
    intent = str(understanding.get("intent", "unknown"))
    order_id = understanding.get("order_id")
    tlow = text.lower()

    # Defaults for finalize() until we have an order
    customer: Optional[Dict[str, Any]] = None
    history: Dict[str, Any] = {"decisions": [], "refund_count": 0}

    def finalize(decision: Dict[str, Any], *, is_refund_request: bool | None = None) -> Dict[str, Any]:
        if is_refund_request is None:
            is_refund_request = intent == "refund_request"
        return _finalize_decision(decision, customer=customer, history=history, is_refund_request=bool(is_refund_request))

    # STEP 1: Basic cases
    if not order_id:
        if _looks_like_policy_question(text) or intent == "policy_query":
            return finalize(
                {
                    "action": "policy_query",
                    "reason": ["User asked policy question"],
                    "confidence": 0.9,
                }
            )

        level = "partial" if intent != "unknown" else "unclear"
        return finalize(
            {
                "action": "ask_clarification",
                "reason": ["Missing order_id; need order ID to proceed."],
                "confidence": _confidence(level),
            }
        )

    if order is None:
        return finalize(
            {
                "action": "invalid_order",
                "reason": [f"Order '{order_id}' was not found in orders dataset."],
                "confidence": _confidence("clear"),
            }
        )

    refund_status = str(order.get("refund_status") or "").lower()
    if refund_status == "refunded":
        return finalize(
            {
                "action": "inform_already_refunded",
                "reason": ["Order refund_status is already 'refunded'."],
                "confidence": _confidence("clear"),
            }
        )

    # STEP 2: Related data
    product = _find_product(products, order.get("product_id"))
    customer = _find_customer(order, ticket)
    customer_tier = str((customer or {}).get("tier", "")).lower()

    customer_id = str(order.get("customer_id")) if isinstance(order, dict) and order.get("customer_id") else None
    history = get_customer_history(customer_id) if customer_id else {"decisions": [], "refund_count": 0}
    # Seed refund_count from known customer profile to make memory rules reliable under concurrency.
    try:
        seeded = max(int(history.get("refund_count") or 0), _baseline_refund_count(customer))
        history = dict(history)
        history["refund_count"] = seeded
    except Exception:
        pass

    # TASK 1: Order status handling
    looks_like_status = any(
        k in tlow
        for k in (
            "where is my order",
            "where's my order",
            "not received",
            "haven't received",
            "havent received",
            "tracking",
            "track",
        )
    )
    if intent == "order_status" or (intent == "unknown" and looks_like_status):
        status = str(order.get("status", "")).lower()
        if status == "shipped":
            reasons = ["Order is in transit."]
            tracking_id = _extract_tracking_id(order)
            if tracking_id:
                reasons.append(f"Tracking ID: {tracking_id}")
            return finalize(
                {
                    "action": "provide_order_status",
                    "reason": reasons,
                    "confidence": 0.9,
                }
            )

    # STEP 5: Fraud / risk detection
    claimed = _detect_claimed_tier(text)
    if claimed and customer_tier and claimed != customer_tier:
        return finalize(
            {
                "action": "flag_fraud",
                "reason": [f"Customer claimed tier '{claimed}' but actual tier is '{customer_tier}'."],
                "confidence": _confidence("clear"),
            }
        )

    # STEP 4: Cancel logic
    if intent == "cancel_request":
        status = str(order.get("status", "")).lower()
        if status == "processing":
            return finalize(
                {
                    "action": "cancel_order",
                    "reason": ["Order status is 'processing'."],
                    "confidence": _confidence("clear"),
                }
            )
        return finalize(
            {
                "action": "cannot_cancel",
                "reason": [f"Order status is '{order.get('status')}', cannot cancel unless 'processing'."],
                "confidence": _confidence("clear"),
            }
        )

    # Dates for return/warranty
    ticket_dt = _parse_ticket_date(ticket)
    deadline = _return_deadline(order, product)
    within_return = None
    if ticket_dt and deadline:
        within_return = ticket_dt <= deadline

    warranty_end = _warranty_end(order, product)
    warranty_active = bool(ticket_dt and warranty_end and ticket_dt <= warranty_end)

    defect = bool(_DEFECT_RE.search(text))

    # TASK 2: Wrong item / exchange handling
    wrong_item = any(k in tlow for k in ("wrong size", "wrong colour", "wrong color", "incorrect", "wrong"))
    return_refund_related = (
        intent in {"return_request", "refund_request"}
        or any(k in tlow for k in ("return", "refund", "exchange", "replacement", "replace"))
        or "please fix" in tlow
    )
    if wrong_item and return_refund_related:
        return finalize(
            {
                "action": "initiate_exchange",
                "reason": ["Customer received wrong item."],
                "confidence": 0.9,
            }
        )

    # STEP 3: Return / refund / warranty logic
    if defect:
        if within_return is False and warranty_active:
            return finalize(
                {
                    "action": "escalate_warranty",
                    "reason": ["Return window expired but warranty is still active."],
                    "confidence": _confidence("clear"),
                }
            )
        return finalize(
            {
                "action": "approve_refund",
                "reason": ["defective item"],
                "confidence": _confidence("clear"),
            },
            is_refund_request=True,
        )

    is_return_like = intent in {"return_request", "refund_request"} or "return" in tlow
    if is_return_like:
        if product is not None and product.get("returnable") is False:
            return finalize(
                {
                    "action": "reject_return",
                    "reason": ["Item is marked as non-returnable."],
                    "confidence": _confidence("clear"),
                }
            )

        if within_return is True:
            return finalize(
                {
                    "action": "approve_return",
                    "reason": ["Within return window."],
                    "confidence": _confidence("clear"),
                }
            )

        if within_return is False:
            notes = " ".join(
                [
                    str(order.get("notes", "")),
                    str((customer or {}).get("notes", "")),
                    text,
                ]
            ).lower()
            has_exception = "exception" in notes or "extended return" in notes or "pre-approved" in notes
            if customer_tier == "vip" and has_exception:
                return finalize(
                    {
                        "action": "approve_return_exception",
                        "reason": ["Return window expired, but VIP exception applies."],
                        "confidence": _confidence("clear"),
                    }
                )

            # Phase 2 refinement: VIP priority for borderline reject_return
            if customer_tier == "vip":
                return finalize(
                    {
                        "action": "approve_return_exception",
                        "reason": ["VIP priority applied for borderline return window case."],
                        "confidence": 0.85,
                    }
                )

            return finalize(
                {
                    "action": "reject_return",
                    "reason": ["Return window expired."],
                    "confidence": _confidence("clear"),
                }
            )

        # If we couldn't compute dates, be conservative.
        return finalize(
            {
                "action": "ask_clarification",
                "reason": ["Unable to determine return eligibility; need more details."],
                "confidence": _confidence("unclear"),
            }
        )

    # STEP 7: General query (with order present but policy intent)
    if intent == "policy_query":
        return finalize(
            {
                "action": "policy_query",
                "reason": ["User asked policy question"],
                "confidence": 0.9,
            }
        )

    # Default
    return finalize(
        {
            "action": "general_response",
            "reason": [f"No rule matched for intent '{intent}'."],
            "confidence": _confidence("partial"),
        }
    )
