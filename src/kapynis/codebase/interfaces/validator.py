from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class Validator(Protocol):
    """Unified validator — JSON schema or Pydantic struct.

    Mirrors candi's ``interfaces.Validator`` which composed
    ``JSONSchemaValidator`` and ``StructValidator``.
    """

    def validate_document(self, schema_id: str, document: Any) -> None: ...
    def validate_struct(self, data: Any) -> None: ...
