from __future__ import annotations

from math import ceil

from pydantic import BaseModel, Field


class Meta(BaseModel):
    """Pagination metadata. Mirrors candi's ``candishared.Meta``."""

    page: int = Field(default=1, ge=1)
    limit: int = Field(default=10, ge=1)
    total_records: int = Field(default=0, ge=0, alias="totalRecords")
    total_pages: int = Field(default=0, ge=0, alias="totalPages")

    model_config = {"populate_by_name": True}

    @classmethod
    def new(cls, page: int, limit: int, total_records: int) -> "Meta":
        total_pages = ceil(total_records / limit) if limit > 0 else 0
        return cls(
            page=page,
            limit=limit,
            total_records=total_records,
            total_pages=total_pages,
        )
