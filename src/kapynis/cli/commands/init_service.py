"""``kapynis init`` — scaffold a new service (interactive, mirrors candi -init)."""

from __future__ import annotations

import json
from pathlib import Path

import click

from kapynis.helper.string_case import to_kebab, to_pascal, to_snake
from kapynis.cli.render import render_tree


# ---------------------------------------------------------------------------
# Interactive prompts (mirrors candi's cli_parser.go readInput() flow)
# ---------------------------------------------------------------------------

def _ask(label: str) -> str:
    """Print *label* then collect input at a '>> ' prompt (mirrors candi style)."""
    click.echo(f"\n\033[1m{label}\033[0m")
    try:
        return input(">> ").strip()
    except EOFError:
        return ""


def _prompt_service_name(cwd: Path) -> str:
    while True:
        name = _ask("Please input service name")
        if not name:
            click.echo("\033[31mService name cannot be empty, try again\033[0m")
            continue
        target = cwd / name
        if target.exists():
            click.echo(f"\033[31mFolder '{name}' already exists, try again\033[0m")
            continue
        return name


def _prompt_modules() -> list[str]:
    while True:
        raw = _ask("Please input new module names (if more than one, separated by comma)")
        modules = [to_snake(m.strip()) for m in raw.split(",") if m.strip()]
        if not modules:
            click.echo("\033[31mModules cannot be empty, try again\033[0m")
            continue
        return modules


def _prompt_server_handlers() -> set[str]:
    _options: dict[str, str] = {"1": "rest", "2": "grpc", "3": "graphql"}
    while True:
        raw = _ask(
            "Please select server handlers (separated by comma, enter for skip)\n"
            "1) REST API\n2) GRPC\n3) GraphQL"
        )
        selected: set[str] = set()
        if not raw:
            click.echo("\033[31mNo server/worker handler selected, try again\033[0m")
            continue
        valid = True
        for token in raw.split(","):
            token = token.strip()
            if token in _options:
                selected.add(_options[token])
            elif token:
                click.echo(f"\033[31mInvalid option '{token}', try again\033[0m")
                valid = False
                break
        if valid and selected:
            return selected
        if valid:
            click.echo("\033[31mNo server/worker handler selected, try again\033[0m")


def _prompt_worker_handlers() -> set[str]:
    _options: dict[str, str] = {
        "1": "kafka",
        "2": "cron",
        "3": "redis",
        "4": "rabbitmq",
        "5": "postgres",
        "6": "task_queue",
    }
    while True:
        raw = _ask(
            "Please select worker handlers (separated by comma, enter to skip)\n"
            "1) Kafka\n2) Cron Scheduler\n3) Redis Subscriber\n"
            "4) RabbitMQ\n5) Postgres Listener\n6) Task Queue"
        )
        if not raw:
            return set()
        selected: set[str] = set()
        valid = True
        for token in raw.split(","):
            token = token.strip()
            if token in _options:
                selected.add(_options[token])
            elif token:
                click.echo(f"\033[31mInvalid option '{token}', try again\033[0m")
                valid = False
                break
        if valid:
            return selected


def _prompt_dependencies() -> set[str]:
    _options: dict[str, str] = {"1": "redis", "2": "sql", "3": "mongo"}
    while True:
        raw = _ask(
            "Please select dependencies (separated by comma, enter to skip)\n"
            "1) Redis\n2) SQL Database\n3) Mongo Database"
        )
        if not raw:
            return set()
        selected: set[str] = set()
        valid = True
        for token in raw.split(","):
            token = token.strip()
            if token in _options:
                selected.add(_options[token])
            elif token:
                click.echo(f"\033[31mInvalid option '{token}', try again\033[0m")
                valid = False
                break
        if valid:
            return selected


def _build_context(
    service_name: str,
    server_handlers: set[str],
    worker_handlers: set[str],
    dependencies: set[str],
) -> dict[str, object]:
    """Build the full Jinja2 context shared by service + module templates."""
    package = to_snake(service_name)
    return {
        "service_name": service_name,
        "service_snake": package,
        "service_kebab": to_kebab(service_name),
        "service_pascal": to_pascal(service_name),
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


# ---------------------------------------------------------------------------
# Command
# ---------------------------------------------------------------------------

@click.command(help="Scaffold a new kapynis service (interactive, mirrors candi -init).")
def init_service() -> None:
    try:
        import os
        cwd = Path(os.getcwd())
    except FileNotFoundError:
        raise click.ClickException(
            "current directory no longer exists — cd to a valid directory first"
        )
    service_name = _prompt_service_name(cwd)
    modules = _prompt_modules()
    server_handlers = _prompt_server_handlers()
    worker_handlers = _prompt_worker_handlers()
    dependencies = _prompt_dependencies()

    target = cwd / service_name
    target.mkdir(parents=True, exist_ok=True)

    context = _build_context(service_name, server_handlers, worker_handlers, dependencies)

    written = render_tree("service", target, context)

    # Scaffold each module and inject markers (same as add-module).
    from kapynis.cli.commands.add_module import (  # noqa: PLC0415
        _inject_repository_markers,
        _inject_service_markers,
        _inject_usecase_markers,
        _inject_graphql_schema_markers,
    )
    for module_snake in modules:
        module_pascal = to_pascal(module_snake)
        module_context = {
            **context,
            "module_name": module_snake,
            "module_snake": module_snake,
            "module_kebab": module_snake.replace("_", "-"),
            "module_pascal": module_pascal,
        }
        written += render_tree("module", target, module_context)
        _inject_usecase_markers(target, module_snake, module_pascal)
        _inject_repository_markers(target, module_snake, module_pascal)
        _inject_service_markers(target, module_snake, module_pascal)
        if "graphql" in server_handlers:
            _inject_graphql_schema_markers(target, module_snake, module_pascal)

    # Save kapynis.json — mirrors candi.json; read by add-module / add-handler.
    config_data = {
        "service_name": service_name,
        "package": to_snake(service_name),
        "modules": modules,
        "server_handlers": sorted(server_handlers),
        "worker_handlers": sorted(worker_handlers),
        "dependencies": sorted(dependencies),
    }
    (target / "kapynis.json").write_text(json.dumps(config_data, indent=2) + "\n")

    click.echo(f"\n\033[32m✓ service '{service_name}' scaffolded at {target}\033[0m")
    click.echo(f"  modules  : {', '.join(modules)}")
    click.echo(f"  servers  : {', '.join(sorted(server_handlers)) or '-'}")
    click.echo(f"  workers  : {', '.join(sorted(worker_handlers)) or '-'}")
    click.echo(f"  deps     : {', '.join(sorted(dependencies)) or '-'}")
    click.echo(f"  files    : {len(written)}")

    click.echo(f"\n  \033[1mcd {service_name}\033[0m")
    click.echo(f"  python3 -m venv .venv && .venv/bin/pip install -e \".[dev]\"")
    click.echo(f"  .venv/bin/kapynis add-module")
