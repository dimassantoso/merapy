"""``kapynis add-module <name>`` — add a new module + inject UOW markers."""

from __future__ import annotations

import json
from pathlib import Path

import click

from kapynis.helper.string_case import to_kebab, to_pascal, to_snake
from kapynis.cli.markers import inject
from kapynis.cli.render import render_tree


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


def _load_kapynis_json(service_root: Path) -> dict:
    """Load kapynis.json for server/worker handler flags."""
    p = service_root / "kapynis.json"
    if p.exists():
        return json.loads(p.read_text())
    return {}


def _src(root: Path) -> Path:
    return root / "src"


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
    cfg = _load_kapynis_json(service_root)

    server_handlers: set[str] = set(cfg.get("server_handlers", ["rest"]))
    worker_handlers: set[str] = set(cfg.get("worker_handlers", []))
    dependencies: set[str] = set(cfg.get("dependencies", []))

    context = {
        "module_name": name,
        "module_snake": snake,
        "module_kebab": to_kebab(name),
        "module_pascal": pascal,
        "package": package,
        # server handlers
        "use_rest": "rest" in server_handlers,
        "use_grpc": "grpc" in server_handlers,
        "use_graphql": "graphql" in server_handlers,
        # worker handlers
        "use_kafka": "kafka" in worker_handlers,
        "use_cron": "cron" in worker_handlers,
        "use_redis_subscriber": "redis" in worker_handlers,
        "use_rabbitmq": "rabbitmq" in worker_handlers,
        "use_postgres_listener": "postgres" in worker_handlers,
        "use_task_queue": "task_queue" in worker_handlers,
        # dependencies
        "use_sql": "sql" in dependencies,
        "use_redis": "redis" in dependencies or "redis" in worker_handlers,
        "use_mongo": "mongo" in dependencies,
    }

    module_dir = service_root / "src" / "internal" / "modules" / snake
    if module_dir.exists() and any(module_dir.iterdir()):
        raise click.ClickException(f"module {snake} already exists at {module_dir}")
    written = render_tree("module", service_root, context)

    _inject_usecase_markers(service_root, snake, pascal)
    _inject_repository_markers(service_root, snake, pascal)
    _inject_service_markers(service_root, snake, pascal)
    if "graphql" in server_handlers:
        _inject_graphql_schema_markers(service_root, snake, pascal)
    if "mongo" in dependencies:
        _inject_repository_mongo_markers(service_root, snake, pascal)

    # Update kapynis.json modules list.
    if cfg:
        modules: list[str] = cfg.get("modules", [])
        if snake not in modules:
            modules.append(snake)
            cfg["modules"] = modules
            (service_root / "kapynis.json").write_text(json.dumps(cfg, indent=2) + "\n")

    click.echo(f"✓ generated {len(written)} files for module '{snake}'")
    click.echo("  shared usecase + repository + service.py updated via markers")


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


def _inject_graphql_schema_markers(root: Path, snake: str, pascal: str) -> None:
    """Inject graphql schema root entries into api/graphql/_schema.graphql."""
    f = root / "api" / "graphql" / "_schema.graphql"
    if not f.exists():
        return
    from kapynis.cli.markers import inject as _inject
    _inject(f, "queryRoot", f"{snake}: {pascal}QueryResolver @auth(authType: BEARER)")
    _inject(f, "mutationRoot", f"{snake}: {pascal}MutationResolver @auth(authType: BEARER)")
    _inject(f, "subscriptionRoot", f"{snake}: {pascal}SubscriptionResolver")


def _inject_repository_mongo_markers(root: Path, snake: str, pascal: str) -> None:
    """Inject mongo repository markers into pkg/shared/repository/repository_mongo.py."""
    f = _src(root) / "pkg" / "shared" / "repository" / "repository_mongo.py"
    if not f.exists():
        return
    inject(f, "repositoryMongoImport", f"from src.internal.modules.{snake}.repository import {pascal}Repository, {pascal}RepoMongo")
    inject(f, "repositoryMongoMethod", f"def {snake}_repo(self) -> {pascal}Repository: ...")
    inject(f, "repositoryMongoField", f"_{snake}_repo: {pascal}Repository")
    inject(f, "repositoryMongoConstructor", f"impl._{snake}_repo = {pascal}RepoMongo(read_db, write_db)")
    inject(f, "repositoryMongoImplementation", f"def {snake}_repo(self) -> {pascal}Repository:\n    return self._{snake}_repo")
