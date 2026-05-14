from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class Validator(Protocol):
    """Unified validator — JSON schema or Pydantic struct."""

    def validate(self, schema_id: str, document: Any) -> None:
        """Validate ``document`` against the JSON schema identified by ``schema_id``.

        Raises ``MultiError`` on validation failure.
        Alias for ``validate_document`` — the primary API used by generated handlers.
        """
        ...

    def validate_document(self, schema_id: str, document: Any) -> None: ...
    def validate_struct(self, data: Any) -> None: ...
