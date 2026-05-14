"""``merapy`` CLI entry point.

Running ``merapy`` with no subcommand shows an interactive menu.
Named subcommands also work directly:
``merapy init``, ``merapy add-module``, ``merapy add-handler``.
"""

from __future__ import annotations

import os
from pathlib import Path

import click

from merapy.cli.commands.add_handler import add_handler, _VALID_TYPES

# Human-readable labels for handler types shown in the interactive menu
_HANDLER_LABELS: dict[str, str] = {
    "rest":       "REST API",
    "grpc":       "gRPC",
    "graphql":    "GraphQL",
    "cron":       "Cron Scheduler",
    "kafka":      "Kafka Consumer",
    "rabbitmq":   "RabbitMQ Consumer",
    "redis":      "Redis Subscriber",
    "postgres":   "Postgres Listener",
    "task_queue": "Task Queue",
}
from merapy.cli.commands.add_module import add_module
from merapy.cli.commands.init_service import init_service

_BANNER = (
    "\n"
    "\033[34;1m███╗   ███╗\033[33;1m███████╗\033[34;1m██████╗ \033[33;1m █████╗ \033[34;1m██████╗ \033[33;1m██╗   ██╗\033[0m\n"
    "\033[34;1m████╗ ████║\033[33;1m██╔════╝\033[34;1m██╔══██╗\033[33;1m██╔══██╗\033[34;1m██╔══██╗\033[33;1m╚██╗ ██╔╝\033[0m\n"
    "\033[34;1m██╔████╔██║\033[33;1m█████╗  \033[34;1m██████╔╝\033[33;1m███████║\033[34;1m██████╔╝\033[33;1m ╚████╔╝ \033[0m\n"
    "\033[34;1m██║╚██╔╝██║\033[33;1m██╔══╝  \033[34;1m██╔══██╗\033[33;1m██╔══██║\033[34;1m██╔═══╝ \033[33;1m  ╚██╔╝  \033[0m\n"
    "\033[34;1m██║ ╚═╝ ██║\033[33;1m███████╗\033[34;1m██║  ██║\033[33;1m██║  ██║\033[34;1m██║     \033[33;1m   ██║   \033[0m\n"
    "\033[34;1m╚═╝     ╚═╝\033[33;1m╚══════╝\033[34;1m╚═╝  ╚═╝\033[33;1m╚═╝  ╚═╝\033[34;1m╚═╝     \033[33;1m   ╚═╝   \033[0m\n"
    "\033[2m  Python clean-architecture microservice framework\033[0m\n"
)

_MENU = """\033[1mWhat do you want?
1) Init service
2) Add module(s) in service
3) Add delivery handler(s) in module\033[0m"""


def _ask(label: str) -> str:
    click.echo(f"\n\033[1m{label}\033[0m")
    try:
        return input(">> ").strip()
    except EOFError:
        return ""


def _find_service_root() -> Path | None:
    """Return cwd if it looks like a service root, else None."""
    cwd = Path(os.getcwd())
    if (cwd / "pyproject.toml").exists() and (cwd / "merapy.json").exists():
        return cwd
    return None


def _require_service_root() -> Path:
    """Return the service root or exit with a helpful message."""
    root = _find_service_root()
    if root is None:
        click.echo(
            "\033[31m✗ Not inside a merapy service directory.\033[0m\n"
            "  Run this command from the service root (where pyproject.toml and merapy.json live).\n"
            "  Use option 1 to scaffold a new service first."
        )
        raise SystemExit(1)
    return root


def _run_add_module(ctx: click.Context) -> None:
    """Interactive wrapper for add-module (option 2)."""
    service_root = _require_service_root()

    while True:
        raw = _ask("Please input module name(s) to add (separated by comma)")
        names = [n.strip() for n in raw.split(",") if n.strip()]
        if names:
            break
        click.echo("\033[31mModule name cannot be empty, try again\033[0m")

    for name in names:
        ctx.invoke(add_module, name=name, service_root=service_root)


def _run_add_handler(ctx: click.Context) -> None:
    """Interactive wrapper for add-handler (option 3)."""
    service_root = _require_service_root()

    while True:
        module = _ask("Please input the module name")
        if module.strip():
            break
        click.echo("\033[31mModule name cannot be empty, try again\033[0m")

    # Build numbered menu from valid types
    type_options = {str(i + 1): t for i, t in enumerate(_VALID_TYPES)}
    menu_lines = "\n".join(f"{k}) {_HANDLER_LABELS[v]}" for k, v in type_options.items())

    while True:
        raw = _ask(
            f"Please select handler type(s) to add (separated by comma)\n{menu_lines}"
        )
        selected = []
        valid = True
        for token in raw.split(","):
            token = token.strip()
            if token in type_options:
                selected.append(type_options[token])
            elif token in _VALID_TYPES:
                selected.append(token)
            elif token:
                click.echo(f"\033[31mInvalid option '{token}', try again\033[0m")
                valid = False
                break
        if valid and selected:
            break
        if valid:
            click.echo("\033[31mNo handler type selected, try again\033[0m")

    for handler_type in selected:
        ctx.invoke(add_handler, module=module.strip(), handler_type=handler_type, service_root=service_root)

@click.group(
    invoke_without_command=True,
    help="Scaffold and extend merapy-based services.",
)
@click.version_option(package_name="merapy", prog_name="merapy")
@click.pass_context
def cli(ctx: click.Context) -> None:
    if ctx.invoked_subcommand is not None:
        return
    # No subcommand — show banner + interactive menu.
    click.echo(_BANNER)
    while True:
        click.echo(_MENU)
        choice = input(">> ").strip()
        if choice == "1":
            ctx.invoke(init_service)
            return
        elif choice == "2":
            _run_add_module(ctx)
            return
        elif choice == "3":
            _run_add_handler(ctx)
            return
        else:
            click.echo(f"\033[31mInvalid option '{choice}', try again\033[0m\n")


cli.add_command(init_service, name="init")
cli.add_command(add_module, name="add-module")
cli.add_command(add_handler, name="add-handler")


if __name__ == "__main__":
    cli()
