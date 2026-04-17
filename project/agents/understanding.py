import re
from typing import Any, Dict, Optional


# Allow alphanumeric order IDs for synthetic failure cases (e.g., ORD-FAIL) while still matching ORD-1001.
_ORDER_ID_RE = re.compile(r"\bORD-[A-Z0-9]+\b", re.IGNORECASE)


def _ticket_text(ticket: Any) -> str:
    if isinstance(ticket, str):
        return ticket

    if isinstance(ticket, dict):
        for key in ("message", "description", "text", "body", "content"):
            val = ticket.get(key)
            if isinstance(val, str) and val.strip():
                return val
        # Fallback: concatenate string fields for robustness.
        parts = [str(v) for v in ticket.values() if isinstance(v, (str, int, float))]
        return " ".join(parts)

    return str(ticket)


def _extract_order_id(text: str) -> Optional[str]:
    m = _ORDER_ID_RE.search(text)
    return m.group(0).upper() if m else None


def _detect_intent(text: str) -> str:
    t = text.lower()
    if "policy" in t:
        return "policy_query"
    if "refund" in t:
        return "refund_request"
    if "return" in t:
        return "return_request"
    if "cancel" in t:
        return "cancel_request"
    if "where" in t or "status" in t or "track" in t or "tracking" in t:
        return "order_status"
    return "unknown"


def understand_ticket(ticket: Any) -> Dict[str, Any]:
    """Infer structured intent + order_id from a raw ticket using simple rules."""
    text = _ticket_text(ticket)
    order_id = _extract_order_id(text)
    intent = _detect_intent(text)

    return {
        "intent": intent,
        "order_id": order_id,
        "has_order": order_id is not None,
    }
