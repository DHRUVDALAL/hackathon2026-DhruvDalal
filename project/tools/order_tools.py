from __future__ import annotations

import threading
from typing import Any, Dict, List, Optional


# Thread-local datasets so parallel ticket processing doesn't clobber shared state.
_DATASETS_BY_THREAD: Dict[int, Dict[str, List[Dict[str, Any]]]] = {}


def _datasets() -> Dict[str, List[Dict[str, Any]]]:
    tid = threading.get_ident()
    if tid not in _DATASETS_BY_THREAD:
        _DATASETS_BY_THREAD[tid] = {"orders": [], "customers": [], "products": []}
    return _DATASETS_BY_THREAD[tid]


def init_datasets(*, orders: List[Dict[str, Any]], customers: List[Dict[str, Any]], products: List[Dict[str, Any]]) -> None:
    """Initialize in-memory datasets for tool access (Phase 2, no external APIs)."""
    ds = _datasets()
    ds["orders"] = orders or []
    ds["customers"] = customers or []
    ds["products"] = products or []


def get_order(order_id: str) -> Optional[Dict[str, Any]]:
    oid = str(order_id).upper()
    return next((o for o in _datasets()["orders"] if str(o.get("order_id", "")).upper() == oid), None)


def get_customer(customer_id: str) -> Optional[Dict[str, Any]]:
    cid = str(customer_id).upper()
    return next((c for c in _datasets()["customers"] if str(c.get("customer_id", "")).upper() == cid), None)


def get_product(product_id: str) -> Optional[Dict[str, Any]]:
    pid = str(product_id).upper()
    return next((p for p in _datasets()["products"] if str(p.get("product_id", "")).upper() == pid), None)


def search_knowledge_base(query: str, knowledge_text: str) -> str:
    """Hackathon tool: simple keyword-based KB lookup."""
    q = str(query or "").lower()
    if "return" in q:
        return "Returns allowed within product-specific return window."
    if "refund" in q:
        return "Refunds processed if eligible or defective."
    return "Refer to company policy."
