"""``kapynis add-module <name>`` — add a new module + inject UOW markers."""

from __future__ import annotations

from pathlib import Path

import click

from kapynis.helper.string_case import to_kebab, to_pascal, to_snake
from kapynis.cli.markers import inject
from kapynis.cli.render import render_tree


@click.command(help="Add a new module to an existing kapynis service.")
@click.argument("name")
@click.option(
    "--service-root",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=Path.cwd,
)
def add_module(name: str, service_root: Path) -> None:
    snake = to_snake(name)
    pascal = to_pascal(name)
    package = _detect_package(service_root)
    context = {
        "module_name": name,
        "module_snake": snake,
        "module_kebab": to_kebab(name),
        "module_pascal": pascal,
        "package": package,
    }

    module_dir = service_root / "src" / "internal" / "modules" / snake
    if module_dir.exists() and any(module_dir.iterdir()):
        raise click.ClickException(f"module {snake} already exists at {module_dir}")
    written = render_tree("module", service_root, context)

    _inject_usecase_markers(service_root, snake, pascal)
    _inject_repository_markers(service_root, snake, pascal)
    _inject_service_markers(service_root, snake, pascal)

    click.echo(f"✓ generated {len(written)} files for module '{snake}'")
    click.echo("  shared usecase + repository + service.py updated via markers")


def _detect_package(service_root: Path) -> str:
    """Locate the service package name from pyproject.toml [project] name."""
    pyproj = service_root / "pyproject.toml"
    if not pyproj.exists():
        raise click.ClickException("pyproject.toml not found — run from a service root")
    text = pyproj.read_text()
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("name") and "=" in line:
            return line.split("=", 1)[1].strip().strip('"').strip("'").replace("-", "_")
    raise click.ClickException("could not parse [project] name from pyproject.toml")


def _src(root: Path) -> Path:
    return root / "src"


def _inject_usecase_markers(root: Path, snake: str, pascal: str) -> None:
    f = _src(root) / "pkg" / "shared" / "usecase" / "usecase.py"
    if not f.exists():
        return
    inject(f, "usecaseImport", f"from src.internal.modules.{snake}.usecase import {pascal}Usecase, new_{snake}_usecase")
    inject(f, "usecaseMethod", f"def {snake}(self) -> {pascal}Usecase: ...")
    inject(f, "usecaseField", f"_{snake}: {pascal}Usecase")
    inject(
        f,
        "usecaseCommon",
        f"{snake}_uc, {snake}_wire = new_{snake}_usecase(deps)\nusecase_inst._{snake} = {snake}_uc\nset_shared_funcs.append({snake}_wire)",
    )
    inject(
        f,
        "usecaseImplementation",
        f"def {snake}(self) -> {pascal}Usecase:\n    return self._{snake}",
    )


def _inject_repository_markers(root: Path, snake: str, pascal: str) -> None:
    f = _src(root) / "pkg" / "shared" / "repository" / "repository.py"
    if not f.exists():
        return
    inject(f, "repositoryImport", f"from src.internal.modules.{snake}.repository import {pascal}Repository, {pascal}RepoSQL")
    inject(f, "repositoryMethod", f"def {snake}_repo(self) -> {pascal}Repository: ...")
    inject(f, "repositoryField", f"_{snake}_repo: {pascal}Repository")
    inject(
        f,
        "repositoryConstructor",
        f"impl._{snake}_repo = {pascal}RepoSQL(session_factory)",
    )
    inject(
        f,
        "repositoryImplementation",
        f"def {snake}_repo(self) -> {pascal}Repository:\n    return self._{snake}_repo",
    )


def _inject_service_markers(root: Path, snake: str, pascal: str) -> None:
    f = _src(root) / "internal" / "service.py"
    if not f.exists():
        return
    inject(f, "moduleImport", f"from src.internal.modules.{snake}.module import {pascal}Module")
    inject(f, "moduleInit", f"{pascal}Module(deps),")
