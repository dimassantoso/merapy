"""Standard JSON response envelope. Mirrors candi's ``wrapper.NewHTTPResponse``.

Always returns the shape::

    {
        "success": true/false,        # auto-set: code < 400
        "code": 200,
        "message": "Success",
        "meta": { ... },              # pagination
        "data": { ... },              # business payload
        "errors": { ... }             # field-level errors (MultiError to_map)
    }
"""

from __future__ import annotations

import dataclasses
import datetime
import decimal
import uuid
from typing import Any

from fastapi.responses import JSONResponse
from pydantic import BaseModel

from kapynis.helper.multi_error import MultiError
from kapynis.shared.meta import Meta


def _safe_serializable(obj: Any) -> Any:
    """Recursively coerce ``obj`` into a JSON-serializable structure.

    Handles the most common non-serializable types that leak out of SQLAlchemy
    models, Pydantic models, or plain Python objects:

    - ``datetime``, ``date``, ``time``  → ISO-8601 string
    - ``Decimal``                        → float
    - ``UUID``                           → str
    - ``bytes``                          → base64 string
    - dataclasses                        → dict (recursed)
    - Pydantic ``BaseModel``             → dict (recursed)
    - ``set``, ``frozenset``             → list (recursed)
    - ``dict``                           → dict (keys stringified, values recursed)
    - ``list`` / ``tuple``               → list (recursed)
    - anything else                      → ``str(obj)`` as last resort
    """
    if obj is None or isinstance(obj, (bool, int, float, str)):
        return obj
    if isinstance(obj, (datetime.datetime, datetime.date, datetime.time)):
        return obj.isoformat()
    if isinstance(obj, decimal.Decimal):
        return float(obj)
    if isinstance(obj, uuid.UUID):
        return str(obj)
    if isinstance(obj, bytes):
        import base64
        return base64.b64encode(obj).decode()
    if isinstance(obj, BaseModel):
        return _safe_serializable(obj.model_dump(by_alias=True))
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return _safe_serializable(dataclasses.asdict(obj))  # type: ignore[call-overload]
    if isinstance(obj, (set, frozenset)):
        return [_safe_serializable(v) for v in obj]
    if isinstance(obj, (list, tuple)):
        return [_safe_serializable(v) for v in obj]
    if isinstance(obj, dict):
        return {str(k): _safe_serializable(v) for k, v in obj.items()}
    # Last resort — avoids crashing with a 500 on unknown types.
    return str(obj)


class HTTPResponse(BaseModel):
    success: bool
    code: int
    message: str
    meta: dict[str, Any] | None = None
    data: Any = None
    errors: Any = None

    model_config = {"populate_by_name": True}

    @classmethod
    def new(cls, code: int, message: str, *params: Any) -> "HTTPResponse":
        """Build a response. Each ``param`` is routed by type to the right slot.

        - :class:`Meta`            → ``meta``
        - :class:`MultiError`      → ``errors`` (as map)
        - :class:`Exception`       → ``errors`` (as ``{"_": [str(err)]}``)
        - anything else            → ``data`` (coerced to JSON-safe via ``_safe_serializable``)
        """
        resp = cls(success=code < 400, code=code, message=message)
        for p in params:
            if isinstance(p, Meta):
                resp.meta = p.model_dump(by_alias=True)
            elif isinstance(p, MultiError):
                resp.errors = p.to_map()
            elif isinstance(p, Exception):
                resp.errors = {"_": [str(p)]}
            elif isinstance(p, BaseModel):
                resp.data = p.model_dump(by_alias=True)
            else:
                resp.data = _safe_serializable(p)
        return resp

    def to_response(self) -> JSONResponse:
        return JSONResponse(
            status_code=self.code,
            content=self.model_dump(exclude_none=True),
        )
