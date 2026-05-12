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

from typing import Any

from fastapi.responses import JSONResponse
from pydantic import BaseModel

from kapynis.helper.multi_error import MultiError
from kapynis.shared.meta import Meta


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
        - anything else            → ``data``
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
                resp.data = p
        return resp

    def to_response(self) -> JSONResponse:
        return JSONResponse(
            status_code=self.code,
            content=self.model_dump(exclude_none=True),
        )
