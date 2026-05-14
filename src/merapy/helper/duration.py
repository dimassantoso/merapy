"""Duration string parser."""

from __future__ import annotations

import re

_UNITS: dict[str, float] = {"ms": 0.001, "s": 1.0, "m": 60.0, "h": 3600.0}


def parse_duration(value: object) -> float:
    """Parse a duration string into seconds.

    Supported units: ``ms`` (milliseconds), ``s`` (seconds),
    ``m`` (minutes), ``h`` (hours). Units can be combined.

    Examples::

        "30s"    -> 30.0
        "5m"     -> 300.0
        "1h"     -> 3600.0
        "1h30m"  -> 5400.0
        "500ms"  -> 0.5
        "30"     -> 30.0   (plain number treated as seconds)
        30       -> 30.0

    Usage anywhere::

        from merapy.helper import parse_duration

        timeout = parse_duration(os.getenv("MY_TIMEOUT", "30s"))
    """
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip()
    if re.fullmatch(r"[0-9]+(\.[0-9]+)?", s):
        return float(s)
    matches = re.findall(r"(\d+(?:\.\d+)?)(ms|[smh])", s)
    if not matches:
        raise ValueError(
            f"cannot parse duration {value!r} — "
            "use a plain number (seconds) or a string like '30s', '5m', '1h', '500ms'"
        )
    return sum(float(n) * _UNITS[u] for n, u in matches)
