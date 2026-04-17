from __future__ import annotations

import threading
import time
from typing import Any, Callable, Dict, Optional, Tuple

from utils.errors import ToolError, error_result


_CTX = threading.local()
_METRICS_LOCK = threading.Lock()
_TOTAL_RETRIES = 0  # counts retries (not attempts)
_RETRIES_BY_TICKET: Dict[str, int] = {}


def set_retry_context(*, ticket_id: Optional[str], tool_name: Optional[str]) -> None:
    """Set context so retry() can print production-grade logs without changing its signature."""
    _CTX.ticket_id = str(ticket_id) if ticket_id is not None else None
    _CTX.tool_name = str(tool_name) if tool_name is not None else None
    _CTX.last_attempts = 0
    _CTX.last_retries = 0


def get_last_retry_info() -> Tuple[int, int]:
    """Return (attempts_made, retries_made) for the most recent retry() call in this thread."""
    return int(getattr(_CTX, "last_attempts", 0) or 0), int(getattr(_CTX, "last_retries", 0) or 0)


def get_retry_metrics_snapshot() -> Dict[str, Any]:
    with _METRICS_LOCK:
        return {
            "total_retries": int(_TOTAL_RETRIES),
            "retries_by_ticket": dict(_RETRIES_BY_TICKET),
        }


def _prefix() -> str:
    tid = getattr(_CTX, "ticket_id", None)
    return f"[{tid}] " if tid else ""


def _tool() -> str:
    return str(getattr(_CTX, "tool_name", None) or "tool")


def _normalize_exception(e: Exception) -> Dict[str, Any]:
    if isinstance(e, ToolError):
        return error_result(
            error_code=e.error_code,
            error=e.message,
            retryable=bool(e.retryable),
            details=e.details if isinstance(e.details, dict) else None,
        )

    msg = str(e) or "unknown"
    low = msg.lower()

    if "schema validation failed" in low:
        return error_result(error_code="SCHEMA_VALIDATION_FAILED", error=msg, retryable=False)
    if "timeout" in low:
        return error_result(error_code="PAYMENT_TIMEOUT", error="Payment service timeout", retryable=True)
    if "rate limit" in low or "429" in low:
        return error_result(error_code="RATE_LIMIT", error="Third-party API rate limit exceeded", retryable=True)
    if "db" in low or "database" in low:
        return error_result(error_code="DB_CONNECTION_LOST", error="Database connection lost", retryable=True)
    if "validation" in low:
        return error_result(error_code="REFUND_VALIDATION_ERROR", error=f"Refund API validation error: {msg}", retryable=False)

    return error_result(error_code="UNKNOWN_ERROR", error=msg, retryable=True)


def retry(func: Callable[[], Any], retries: int = 3) -> Any:
    """Production-grade retry with exponential backoff.

    Rules (hackathon demo):
    - max_attempts = 3
    - delays = 0.5 → 1.0 → 2.0 (exponential backoff)
    - retry ONLY if result["retryable"] == True

    Logs:
      [{ticket}] [RETRY 1/3] <tool> failed → retrying in 0.5s...
      [{ticket}] [RETRY SUCCESS] <tool> succeeded on attempt 2
    """

    max_attempts = int(retries or 3)
    base_delay = 0.5

    retries_made = 0
    last_err: Optional[Dict[str, Any]] = None

    for attempt in range(1, max_attempts + 1):
        out: Any
        try:
            out = func()
        except Exception as e:  # noqa: BLE001
            out = _normalize_exception(e)

        # Tools may return a structured failure dict instead of raising.
        if isinstance(out, dict) and str(out.get("status", "")) == "failed":
            last_err = out
            retryable = bool(out.get("retryable") is True)

            if attempt < max_attempts and retryable:
                delay = base_delay * (2 ** (attempt - 1))
                retries_made += 1

                with _METRICS_LOCK:
                    global _TOTAL_RETRIES
                    _TOTAL_RETRIES += 1
                    tid = getattr(_CTX, "ticket_id", None)
                    if tid:
                        _RETRIES_BY_TICKET[tid] = int(_RETRIES_BY_TICKET.get(tid, 0)) + 1

                print(f"{_prefix()}[RETRY {attempt}/{max_attempts}] {_tool()} failed → retrying in {delay:.1f}s...")
                time.sleep(delay)
                continue

            # retries exhausted OR non-retryable
            print(f"{_prefix()}[RETRY {attempt}/{max_attempts}] {_tool()} failed → moving to DLQ")

            setattr(_CTX, "last_attempts", attempt)
            setattr(_CTX, "last_retries", retries_made)
            res = dict(out)
            res["retry_attempts"] = int(attempt)
            return res

        # success path
        setattr(_CTX, "last_attempts", attempt)
        setattr(_CTX, "last_retries", retries_made)
        if attempt > 1:
            print(f"{_prefix()}[RETRY SUCCESS] {_tool()} succeeded on attempt {attempt}")
        return out

    setattr(_CTX, "last_attempts", max_attempts)
    setattr(_CTX, "last_retries", retries_made)
    res = dict(last_err or error_result(error_code="UNKNOWN_ERROR", error="unknown", retryable=False))
    res["retry_attempts"] = int(max_attempts)
    return res
