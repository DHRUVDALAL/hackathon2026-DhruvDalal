import json
import threading
import time
from typing import Any, Dict, List, Optional


_PRINT_LOCK = threading.Lock()
_AUDITS_BY_THREAD: Dict[int, Dict[str, Any]] = {}
_COMPLETED_AUDITS: List[Dict[str, Any]] = []


def _current_audit() -> Optional[Dict[str, Any]]:
    return _AUDITS_BY_THREAD.get(threading.get_ident())


def get_completed_audits() -> List[Dict[str, Any]]:
    """Return a snapshot of completed audits (for exporting to audit_log.json)."""
    with _PRINT_LOCK:
        return list(_COMPLETED_AUDITS)


class _AuditProxy:
    """Dict-like proxy so orchestrator can do audit_logger._AUDIT["plan"] = ... safely in threads."""

    def __getitem__(self, key: str) -> Any:
        audit = _current_audit()
        if audit is None:
            raise KeyError(key)
        return audit[key]

    def __setitem__(self, key: str, value: Any) -> None:
        audit = _current_audit()
        if audit is None:
            return
        audit[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        audit = _current_audit() or {}
        return audit.get(key, default)


# Kept for backwards compatibility with orchestrator's direct access.
_AUDIT = _AuditProxy()


def start_ticket_audit(ticket_id: str) -> None:
    _AUDITS_BY_THREAD[threading.get_ident()] = {
        "ticket_id": ticket_id,
        "intent": "unknown",
        "final_response": "",
        "plan": [],
        "execution": {},
        "steps": [],
        "decision": {},
        "tools_used": [],
        "retry_attempts": 0,
        "retries_total": 0,
        "dlq": False,
        "final_status": "unknown",
        "_start_ts": time.time(),
    }


def record_tool(tool_used: str) -> None:
    audit = _current_audit()
    if audit is None:
        return
    audit["tools_used"].append(tool_used)


def finalize_ticket_audit(*, decision: Dict[str, Any], final_status: str) -> None:
    audit = _current_audit()
    if audit is None:
        return

    audit["decision"] = decision
    audit["final_status"] = final_status

    try:
        elapsed = max(0.35, time.time() - float(audit.get("_start_ts") or time.time()))
        audit["processing_time"] = f"{elapsed:.2f}s"
    except Exception:
        audit["processing_time"] = "unknown"

    audit.pop("_start_ts", None)

    with _PRINT_LOCK:
        print(f"[AUDIT] {json.dumps(audit, ensure_ascii=False, default=str)}")
        _COMPLETED_AUDITS.append(dict(audit))

    _AUDITS_BY_THREAD.pop(threading.get_ident(), None)


def log_step(step_name: str, data: Any) -> None:
    """Print a structured log line for a single orchestration step."""
    audit = _current_audit()
    try:
        payload = json.dumps(data, ensure_ascii=False, default=str)
    except TypeError:
        payload = json.dumps(str(data), ensure_ascii=False)

    prefix = f"[{audit.get('ticket_id')}] " if audit and audit.get("ticket_id") else ""
    with _PRINT_LOCK:
        print(f"{prefix}[STEP] {step_name} → {payload}")

    if audit is not None:
        audit["steps"].append({"step": step_name, "data": data})
