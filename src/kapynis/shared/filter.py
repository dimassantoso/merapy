from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class Filter(BaseModel):
    """Base list/query filter. Mirrors candi's ``candishared.Filter``.

    Module-specific filters subclass this and add their own fields.
    Use ``offset`` for SQL pagination: ``offset = (page - 1) * limit``.
    """

    page: int = Field(default=1, ge=1)
    limit: int = Field(default=10, ge=1, le=200)
    order_by: str | None = Field(default=None, alias="orderBy")
    sort: str = Field(default="desc", pattern="^(asc|desc)$")
    search: str | None = None
    show_all: bool = Field(default=False, alias="showAll")

    model_config = {"populate_by_name": True, "extra": "allow"}

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.limit

    def calculate_meta(self, total_records: int) -> Any:
        from kapynis.shared.meta import Meta

        return Meta.new(page=self.page, limit=self.limit, total_records=total_records)
