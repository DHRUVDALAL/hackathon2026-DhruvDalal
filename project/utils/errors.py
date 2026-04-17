from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class ToolError(Exception):
    """Structured tool exception to enable production-grade retry + DLQ handling."""

    error_code: str
    message: str
    retryable: bool = True
    details: Optional[Dict[str, Any]] = None

    def __str__(self) -> str:  # pragma: no cover
        return self.message


def error_result(
    *,
    error_code: str,
    error: str,
    retryable: bool,
    details: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "status": "failed",
        "error_code": str(error_code),
        "error": str(error),
        "retryable": bool(retryable),
    }
    if isinstance(details, dict) and details:
        out["details"] = details
    return out
