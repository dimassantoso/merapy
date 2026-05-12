"""JSON-Schema validator with in-memory schema storage.

Mirrors candi's ``validator/json_schema.go``. Schemas are loaded from a
directory once at boot and looked up by their ``$id`` (falling back to
the filename stem).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError as JSONSchemaValidationError

from kapynis.helper.multi_error import MultiError


class JSONSchemaValidator:
    __slots__ = ("_validators",)

    def __init__(self, schemas_dir: str | Path) -> None:
        self._validators: dict[str, Draft202012Validator] = {}
        self._load(Path(schemas_dir))

    def _load(self, directory: Path) -> None:
        if not directory.exists():
            return
        for path in directory.rglob("*.json"):
            with path.open("rb") as f:
                schema = json.load(f)
            schema_id = schema.get("$id") or path.stem
            self._validators[schema_id] = Draft202012Validator(schema)

    def validate_document(self, schema_id: str, document: Any) -> None:
        validator = self._validators.get(schema_id)
        if validator is None:
            raise KeyError(f"json schema not found: {schema_id}")
        errors = list(validator.iter_errors(document))
        if not errors:
            return
        me = MultiError()
        for err in errors:
            loc = ".".join(str(x) for x in err.absolute_path) or "_"
            me.append(loc, err.message)
        raise me

    @property
    def schema_ids(self) -> list[str]:
        return list(self._validators.keys())
