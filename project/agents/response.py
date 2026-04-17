from typing import Dict, Iterable, Optional


def _tracking_from_reasons(reasons: Iterable[object]) -> Optional[str]:
    for r in reasons:
        s = str(r)
        if s.lower().startswith("tracking id:"):
            return s.split(":", 1)[1].strip() or None
    return None


def generate_response(decision: Dict[str, object]) -> str:
    action = str(decision.get("action", "general_response"))
    reasons = decision.get("reason", [])

    if action == "ask_clarification":
        return "Please provide your order ID so I can assist you."
    if action == "invalid_order":
        return "I couldn’t find that order ID. Please double-check it and try again."
    if action == "inform_already_refunded":
        return "Your order has already been refunded."

    if action == "provide_order_status":
        tracking = _tracking_from_reasons(reasons if isinstance(reasons, list) else [])
        if tracking:
            return f"Your order is currently in transit. Tracking ID: {tracking}"
        return "Your order is currently in transit."

    if action == "initiate_exchange":
        return "It looks like you received the wrong item. We’ll arrange an exchange or provide a refund if needed."

    if action == "approve_refund":
        return "We’re sorry about the issue — your item qualifies for a refund."
    if action == "approve_return":
        return "Your order is within the return window — we can help you start a return."
    if action == "approve_return_exception":
        return "We can make an exception and approve this return."
    if action == "reject_return":
        return "This item is outside the return window and cannot be returned."
    if action == "escalate_warranty":
        return "This appears to be a warranty issue — I’m escalating it to our support team."

    if action == "cancel_order":
        return "Your order is eligible for cancellation."
    if action == "cannot_cancel":
        return "This order can’t be cancelled because it’s no longer in processing."

    if action == "flag_fraud":
        return "We’re unable to process this request. Please contact support for verification."

    if action == "answer_general_query":
        return "Here’s our general policy: returns are time-bound by category, and defective items are handled via refund or warranty depending on timing. Share your order ID for a precise answer."

    return "Thanks for reaching out — I’m reviewing your request."
