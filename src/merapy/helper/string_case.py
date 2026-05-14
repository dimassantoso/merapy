from __future__ import annotations

import re

_FIRST_CAP = re.compile(r"(.)([A-Z][a-z]+)")
_ALL_CAP = re.compile(r"([a-z0-9])([A-Z])")


def to_snake(s: str) -> str:
    s = _FIRST_CAP.sub(r"\1_\2", s)
    s = _ALL_CAP.sub(r"\1_\2", s)
    return s.replace("-", "_").lower()


def to_kebab(s: str) -> str:
    return to_snake(s).replace("_", "-")


def to_camel(s: str) -> str:
    parts = to_snake(s).split("_")
    return parts[0] + "".join(p.title() for p in parts[1:])


def to_pascal(s: str) -> str:
    return "".join(p.title() for p in to_snake(s).split("_"))
