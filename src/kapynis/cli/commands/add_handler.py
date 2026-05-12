"""``kapynis add-handler <module> <type>`` — add a delivery handler."""

from __future__ import annotations

from pathlib import Path

import click

from kapynis.helper.string_case import to_pascal, to_snake
from kapynis.cli.render import render_tree

def _detect_package(service_root: Path) -> str:
    pyproj = service_root / "pyproject.toml"
    if not pyproj.exists():
        raise click.ClickException("pyproject.toml not found — run from a service root")
    for line in pyproj.read_text().splitlines():
        line = line.strip()
        if line.startswith("name") and "=" in line:
            return line.split("=", 1)[1].strip().strip('"').strip("'").replace("-", "_")
    raise click.ClickException("could not parse [project] name from pyproject.toml")


_VALID_TYPES = (
    "rest",
    "grpc",
    "graphql",
    "cron",
    "kafka",
    "rabbitmq",
    "redis",
    "postgres",
    "task_queue",
)


@click.command(help="Add a delivery handler (rest/grpc/graphql/<worker>) to a module.")
@click.argument("module")
@click.argument("handler_type", type=click.Choice(_VALID_TYPES))
@click.option(
    "--service-root",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=Path.cwd,
)
def add_handler(module: str, handler_type: str, service_root: Path) -> None:
    snake = to_snake(module)
    package = _detect_package(service_root)
    module_dir = service_root / package / "internal" / "modules" / snake
    if not module_dir.exists():
        raise click.ClickException(f"module {snake} not found at {module_dir}")

    context = {
        "module_name": module,
        "module_snake": snake,
        "module_pascal": to_pascal(module),
        "package": package,
    }
    written = render_tree(f"handler/{handler_type}", service_root, context)
    click.echo(f"✓ generated {len(written)} files for {handler_type} handler in module '{snake}'")
