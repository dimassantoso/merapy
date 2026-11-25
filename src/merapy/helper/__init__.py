"""Generic helpers for merapy services."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from merapy.helper.duration import parse_duration
from merapy.helper.multi_error import MultiError
from merapy.helper.string_case import to_camel, to_kebab, to_pascal, to_snake

if TYPE_CHECKING:
    from merapy.helper.query_param import parse_from_query_param

__all__ = [
    "MultiError",
    "parse_duration",
    "parse_from_query_param",
    "to_camel",
    "to_kebab",
    "to_pascal",
    "to_snake",
]


def __getattr__(name: str) -> Any:
    if name == "parse_from_query_param":
        from merapy.helper.query_param import parse_from_query_param  # noqa: PLC0415

        return parse_from_query_param
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
