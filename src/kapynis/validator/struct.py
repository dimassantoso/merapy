"""Pydantic-based struct validator."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ValidationError

from kapynis.helper.multi_error import MultiError


class StructValidator:
    """Validate Pydantic models (or coerce dicts into them)."""

    def validate_struct(self, data: Any) -> None:
        if isinstance(data, BaseModel):
            # Pydantic already validated on construction; nothing to do.
            return
        # Anything else: cannot validate without a target schema.
        raise TypeError(
            "validate_struct expects a Pydantic BaseModel; use validate_document for raw payloads"
        )

    def coerce(self, data: Any, model_cls: type[BaseModel]) -> BaseModel:
        try:
            return model_cls.model_validate(data)
        except ValidationError as e:
            me = MultiError()
            for err in e.errors():
                loc = ".".join(str(x) for x in err["loc"]) or "_"
                me.append(loc, err["msg"])
            raise me from e
