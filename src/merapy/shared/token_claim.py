from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class TokenClaim(BaseModel):
    """JWT / bearer-token claim payload."""

    subject: str = Field(default="", alias="sub")
    audience: list[str] = Field(default_factory=list, alias="aud")
    issuer: str = Field(default="", alias="iss")
    role: str = ""
    additional: dict[str, Any] = Field(default_factory=dict)
    expires_at: int = Field(default=0, alias="exp")
    issued_at: int = Field(default=0, alias="iat")

    model_config = {"populate_by_name": True, "extra": "allow"}
