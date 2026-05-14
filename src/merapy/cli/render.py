"""Jinja2 rendering for CLI templates."""

from __future__ import annotations

from importlib import resources
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from merapy.helper.string_case import to_kebab, to_pascal, to_snake


def _templates_dir() -> Path:
    """Return the on-disk path to the bundled template tree."""
    pkg = resources.files("merapy.cli")
    return Path(str(pkg)) / "templates"


def _env(template_root: Path) -> Environment:
    env = Environment(
        loader=FileSystemLoader(template_root),
        undefined=StrictUndefined,
        keep_trailing_newline=True,
        autoescape=False,
    )
    env.filters["snake"] = to_snake
    env.filters["pascal"] = to_pascal
    env.filters["kebab"] = to_kebab
    return env


def render_tree(
    template_subdir: str,
    target_dir: Path,
    context: dict[str, Any],
    *,
    overwrite: bool = False,
) -> list[Path]:
    """Render every ``.j2`` file under ``templates/<subdir>/`` into ``target_dir``.

    File path placeholders in template names are also rendered: a template
    named ``{{module_snake}}/usecase.py.j2`` writes to
    ``<module>/usecase.py``.
    """
    root = _templates_dir() / template_subdir
    env = _env(root)
    written: list[Path] = []
    for src in root.rglob("*.j2"):
        rel = src.relative_to(root).as_posix()
        out_rel = env.from_string(rel.removesuffix(".j2")).render(**context)
        out_path = target_dir / out_rel
        out_path.parent.mkdir(parents=True, exist_ok=True)
        if out_path.exists() and not overwrite:
            continue
        tmpl = env.get_template(rel)
        out_path.write_text(tmpl.render(**context))
        written.append(out_path)
    return written
