"""Marker injection engine.

Replaces a ``# @kapynis:<name>`` comment with::

    # @kapynis:<name>
    <new code>

The marker stays in place so subsequent additions can keep appending. This
mirrors candi's string-replace strategy from
``project_generator_add_handler.go``.
"""

from __future__ import annotations

from pathlib import Path


def inject(path: Path, marker: str, code: str) -> bool:
    """Inject ``code`` after the line containing ``# @kapynis:<marker>``.

    Idempotent: if ``code`` is already present somewhere in the file (exact
    string match), this is a no-op and returns ``False``. Otherwise the
    code is inserted and the function returns ``True``.

    Raises ``KeyError`` if the marker is not found — surfaces wiring bugs
    instead of silently doing nothing.
    """
    needle = f"# @kapynis:{marker}"
    text = path.read_text()
    if code.strip() in text:
        return False
    if needle not in text:
        raise KeyError(f"marker '{needle}' not found in {path}")

    lines = text.splitlines(keepends=True)
    out: list[str] = []
    inserted = False
    for line in lines:
        out.append(line)
        if not inserted and needle in line:
            indent = line[: len(line) - len(line.lstrip())]
            for code_line in code.splitlines():
                out.append(f"{indent}{code_line}\n")
            inserted = True
    path.write_text("".join(out))
    return True


def has_marker(path: Path, marker: str) -> bool:
    return f"# @kapynis:{marker}" in path.read_text()
