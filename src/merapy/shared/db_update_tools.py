"""Partial-update helper.

Allows usecase code to say "only update these fields" without forcing the
repository to know the entity shape:

    await repo.save(entity, db_update_set_updated_fields("name", "email"))
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable


@dataclass(slots=True)
class DBUpdateTools:
    """Tracks which fields a partial update should touch."""

    updated_fields: set[str] = field(default_factory=set)
    ignore_fields: set[str] = field(default_factory=set)

    def should_update(self, field_name: str) -> bool:
        if field_name in self.ignore_fields:
            return False
        if not self.updated_fields:
            return True  # no explicit list => update everything
        return field_name in self.updated_fields


DBUpdateOptionFunc = Callable[[DBUpdateTools], None]


def db_update_set_updated_fields(*fields: str) -> DBUpdateOptionFunc:
    def apply(tools: DBUpdateTools) -> None:
        tools.updated_fields.update(fields)

    return apply


def db_update_ignore_fields(*fields: str) -> DBUpdateOptionFunc:
    def apply(tools: DBUpdateTools) -> None:
        tools.ignore_fields.update(fields)

    return apply


def build_update_tools(*opts: DBUpdateOptionFunc) -> DBUpdateTools:
    tools = DBUpdateTools()
    for opt in opts:
        opt(tools)
    return tools
