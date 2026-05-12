"""``kapynis`` CLI entry point.

Running ``kapynis`` with no subcommand shows an interactive menu (mirrors
candi's ``What do you want?`` prompt). Named subcommands also work directly:
``kapynis init``, ``kapynis add-module``, ``kapynis add-handler``.
"""

from __future__ import annotations

import click

from kapynis.cli.commands.add_handler import add_handler
from kapynis.cli.commands.add_module import add_module
from kapynis.cli.commands.init_service import init_service

_BANNER = (
    "\033[32;1m\n"
    " _  __  ___  ____  _  _  _  _  ___  ____\n"
    "| |/ / / _ \\|  _ \\| || || \\| ||_ _|/ ___|\n"
    "| ' / | |_| | |_) | || || .  | | | \\___ \\\n"
    "| . \\ |  _  |  __/  \\/ | | |\\  | | |  ___) |\n"
    "|_|\\_\\|_| |_|_|     \\/  |_| \\_||___||____/\n"
    "\033[0m"
)

_MENU = """\033[1mWhat do you want?
1) Init service
2) Add module(s) in service
3) Add delivery handler(s) in module\033[0m"""

_SCOPE_MAP = {"1": "init", "2": "add-module", "3": "add-handler"}


@click.group(
    invoke_without_command=True,
    help="Scaffold and extend kapynis-based services.",
)
@click.version_option(package_name="kapynis", prog_name="kapynis")
@click.pass_context
def cli(ctx: click.Context) -> None:
    if ctx.invoked_subcommand is not None:
        return
    # No subcommand — show banner + interactive menu like candi.
    click.echo(_BANNER)
    while True:
        click.echo(_MENU)
        choice = input(">> ").strip()
        cmd_name = _SCOPE_MAP.get(choice)
        if cmd_name:
            ctx.invoke(cli.commands[cmd_name])  # type: ignore[attr-defined]
            return
        click.echo(f"\033[31mInvalid option '{choice}', try again\033[0m\n")


cli.add_command(init_service, name="init")
cli.add_command(add_module, name="add-module")
cli.add_command(add_handler, name="add-handler")


if __name__ == "__main__":
    cli()
