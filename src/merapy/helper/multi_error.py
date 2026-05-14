from __future__ import annotations

from typing import Any


class MultiError(Exception):
    """Aggregated field-level error.

    Mirrors candi's ``candihelper.MultiError``. Serialises to a JSON-friendly
    mapping ``{field: [messages]}`` via ``to_map()``.
    """

    def __init__(self, errors: dict[str, list[str]] | None = None) -> None:
        self.errors: dict[str, list[str]] = errors or {}
        super().__init__(self._summary())

    def append(self, field: str, message: str) -> None:
        self.errors.setdefault(field, []).append(message)

    def has_errors(self) -> bool:
        return any(self.errors.values())

    def to_map(self) -> dict[str, Any]:
        return {f: msgs for f, msgs in self.errors.items() if msgs}

    def _summary(self) -> str:
        if not self.errors:
            return "validation failed"
        parts = [f"{f}: {'; '.join(msgs)}" for f, msgs in self.errors.items()]
        return "; ".join(parts)
