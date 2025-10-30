from __future__ import annotations

from typing import Any, Dict, Optional


def success(data: Any = None, **meta: Any) -> Dict[str, Any]:
    out = {"status": "success"}
    if data is not None:
        out["data"] = data
    if meta:
        out["meta"] = meta
    return out


def failure(message: str, code: int = 400, **details: Any) -> Dict[str, Any]:
    out = {"status": "error", "message": message, "code": code}
    if details:
        out["details"] = details
    return out
