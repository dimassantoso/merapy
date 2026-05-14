"""Composite validator that fans out to JSON-Schema + struct backends."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from merapy.validator.json_schema import JSONSchemaValidator
from merapy.validator.struct import StructValidator


class CompositeValidator:
    """Implements the :class:`Validator` Protocol structurally."""

    __slots__ = ("_json", "_struct")

    def __init__(
        self,
        json_schema: JSONSchemaValidator | None = None,
        struct: StructValidator | None = None,
    ) -> None:
        self._json = json_schema
        self._struct = struct or StructValidator()

    def validate_document(self, schema_id: str, document: Any) -> None:
        if self._json is None:
            raise RuntimeError("JSON-Schema validator not configured")
        self._json.validate_document(schema_id, document)

    def validate_struct(self, data: Any) -> None:
        self._struct.validate_struct(data)

    def coerce(self, data: Any, model_cls: type[BaseModel]) -> BaseModel:
        return self._struct.coerce(data, model_cls)
