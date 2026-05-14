"""``merapy add-handler <module> <type>`` — add a delivery handler to a module."""

from __future__ import annotations

import json
from pathlib import Path

import click

from merapy.helper.string_case import to_kebab, to_pascal, to_snake
from merapy.cli.markers import inject
from merapy.cli.render import render_tree


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

# Maps handler type → Worker enum member name used in module.py
_WORKER_ENUM = {
    "kafka": "Worker.KAFKA",
    "cron": "Worker.SCHEDULER",
    "redis": "Worker.REDIS_SUBSCRIBER",
    "rabbitmq": "Worker.RABBITMQ",
    "postgres": "Worker.POSTGRES_LISTENER",
    "task_queue": "Worker.TASK_QUEUE",
}

# Maps handler type → class name suffix
_CLASS_SUFFIX = {
    "rest": "RESTHandler",
    "grpc": "GRPCHandler",
    "graphql": "GraphQLHandler",
    "kafka": "KafkaHandler",
    "cron": "CronHandler",
    "redis": "RedisHandler",
    "rabbitmq": "RabbitMQHandler",
    "postgres": "PostgresHandler",
    "task_queue": "TaskQueueHandler",
}

# Maps handler type → delivery file name (without .py)
_FILE_NAME = {
    "rest": "rest_handler",
    "grpc": "grpc_handler",
    "graphql": "graphql_handler",
    "kafka": "kafka_handler",
    "cron": "cron_handler",
    "redis": "redis_handler",
    "rabbitmq": "rabbitmq_handler",
    "postgres": "postgres_handler",
    "task_queue": "task_queue_handler",
}


def _load_kapynis_json(service_root: Path) -> dict:
    """Load kapynis.json for service-level context (server/worker flags)."""
    p = service_root / "kapynis.json"
    if p.exists():
        return json.loads(p.read_text())
    return {}


def _detect_package(service_root: Path) -> str:
    pyproj = service_root / "pyproject.toml"
    if not pyproj.exists():
        raise click.ClickException("pyproject.toml not found — run from a service root")
    for line in pyproj.read_text().splitlines():
        line = line.strip()
        if line.startswith("name") and "=" in line:
            return line.split("=", 1)[1].strip().strip('"').strip("'").replace("-", "_")
    raise click.ClickException("could not parse [project] name from pyproject.toml")


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
    pascal = to_pascal(snake)
    package = _detect_package(service_root)

    # Module must already exist (created by add-module).
    module_dir = service_root / "src" / "internal" / "modules" / snake
    if not module_dir.exists():
        raise click.ClickException(
            f"module '{snake}' not found at {module_dir} — run 'merapy add-module {snake}' first"
        )

    # Build context — all flags default False; only the requested type is True.
    cfg = _load_kapynis_json(service_root)
    server_handlers: set[str] = set(cfg.get("server_handlers", []))
    worker_handlers: set[str] = set(cfg.get("worker_handlers", []))

    context = {
        "module_name": module,
        "module_snake": snake,
        "module_kebab": to_kebab(snake),
        "module_pascal": pascal,
        "package": package,
        # All handler flags — only the new one is True so templates render correctly.
        "use_rest": handler_type == "rest",
        "use_grpc": handler_type == "grpc",
        "use_graphql": handler_type == "graphql",
        "use_kafka": handler_type == "kafka",
        "use_cron": handler_type == "cron",
        "use_redis_subscriber": handler_type == "redis",
        "use_rabbitmq": handler_type == "rabbitmq",
        "use_postgres_listener": handler_type == "postgres",
        "use_task_queue": handler_type == "task_queue",
        "use_sql": "sql" in cfg.get("dependencies", []),
        "use_redis": "redis" in cfg.get("dependencies", []) or "redis" in worker_handlers,
        "use_mongo": "mongo" in cfg.get("dependencies", []),
    }

    written = render_tree(f"handler/{handler_type}", service_root, context)

    # Wire the new handler into module.py.
    _wire_module(service_root, snake, pascal, handler_type)

    # Update kapynis.json so future add-handler calls see the full picture.
    _update_kapynis_json(service_root, handler_type)

    click.echo(
        f"✓ generated {len(written)} file(s) for '{handler_type}' handler in module '{snake}'"
    )
    click.echo("  module.py updated")


def _wire_module(
    service_root: Path, snake: str, pascal: str, handler_type: str
) -> None:
    """Inject import + wiring into the module's module.py."""
    module_py = service_root / "src" / "internal" / "modules" / snake / "module.py"
    if not module_py.exists():
        return

    class_name = f"{pascal}{_CLASS_SUFFIX[handler_type]}"
    file_name = _FILE_NAME[handler_type]
    import_line = (
        f"from src.internal.modules.{snake}.delivery.{file_name} import {class_name}"
    )

    text = module_py.read_text()

    # Add import if not already present.
    if import_line not in text:
        # Insert after the last existing delivery import block or after the
        # kapynis imports block — find a safe insertion point.
        lines = text.splitlines(keepends=True)
        insert_at = 0
        for i, line in enumerate(lines):
            if line.startswith("from src.internal.modules.") and ".delivery." in line:
                insert_at = i + 1
            elif line.startswith("from kapynis.") or line.startswith("from src."):
                insert_at = i + 1
        lines.insert(insert_at, import_line + "\n")
        text = "".join(lines)

    # Wire into __init__ and the appropriate handler method.
    attr = f"_{snake}_{handler_type}" if handler_type not in ("rest", "grpc", "graphql") else f"_{handler_type}"
    init_line = f"        self.{attr} = {class_name}()"
    if handler_type == "rest":
        init_line = f"        self.{attr} = {class_name}(deps)"

    if init_line.strip() not in text:
        # Insert into __init__ body — after the last self._ assignment or after def __init__
        lines = text.splitlines(keepends=True)
        insert_at = 0
        in_init = False
        for i, line in enumerate(lines):
            if "def __init__" in line:
                in_init = True
            if in_init and line.strip().startswith("self._"):
                insert_at = i + 1
            if in_init and line.strip() == "" and insert_at > 0:
                break
        if insert_at:
            lines.insert(insert_at, init_line + "\n")
            text = "".join(lines)

    # Update the return value of the appropriate handler method.
    if handler_type == "rest":
        text = text.replace(
            "    def rest_handler(self) -> RESTHandler | None:\n        return None",
            f"    def rest_handler(self) -> RESTHandler | None:\n        return self.{attr}",
        )
    elif handler_type == "grpc":
        text = text.replace(
            "    def grpc_handler(self) -> GRPCHandler | None:\n        return None",
            f"    def grpc_handler(self) -> GRPCHandler | None:\n        return self.{attr}",
        )
    elif handler_type == "graphql":
        text = text.replace(
            "    def graphql_handler(self) -> GraphQLHandler | None:\n        return None",
            f"    def graphql_handler(self) -> GraphQLHandler | None:\n        return self.{attr}",
        )
    else:
        # Worker — add to _map in worker_handler or replace "return None"
        worker_enum = _WORKER_ENUM[handler_type]
        map_entry = f"            {worker_enum}: self.{attr},"
        if map_entry not in text:
            if "_map = {" in text:
                text = text.replace("_map = {", f"_map = {{\n{map_entry}", 1)
            else:
                # Replace bare "return None" in worker_handler with a _map
                text = text.replace(
                    "    def worker_handler(self, worker_type: Worker) -> WorkerHandler | None:\n        return None",
                    f"    def worker_handler(self, worker_type: Worker) -> WorkerHandler | None:\n"
                    f"        _map = {{\n{map_entry}\n        }}\n        return _map.get(worker_type)",
                )

    module_py.write_text(text)


def _update_kapynis_json(service_root: Path, handler_type: str) -> None:
    """Add the new handler type to kapynis.json so it's tracked."""
    p = service_root / "kapynis.json"
    if not p.exists():
        return
    data = json.loads(p.read_text())
    server_types = {"rest", "grpc", "graphql"}
    key = "server_handlers" if handler_type in server_types else "worker_handlers"
    existing: list[str] = data.get(key, [])
    if handler_type not in existing:
        existing.append(handler_type)
        data[key] = sorted(existing)
        p.write_text(json.dumps(data, indent=2) + "\n")
