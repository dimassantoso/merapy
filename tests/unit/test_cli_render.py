"""Tests for CLI template resolution and entry point metadata."""

from __future__ import annotations

import sys
from pathlib import Path

from click.testing import CliRunner

from merapy import __version__
from merapy.cli.__main__ import cli
from merapy.cli.render import _templates_dir


def test_templates_dir_exists() -> None:
    tdir = _templates_dir()
    assert tdir.is_dir()
    assert (tdir / "service").is_dir()
    assert (tdir / "module").is_dir()
    assert (tdir / "handler").is_dir()


def test_templates_dir_uses_meipass_when_frozen(tmp_path: Path, monkeypatch: object) -> None:
    fake_templates = tmp_path / "merapy" / "cli" / "templates"
    fake_templates.mkdir(parents=True)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)  # type: ignore[attr-defined]
    assert _templates_dir() == fake_templates


def test_cli_version_and_help() -> None:
    runner = CliRunner()
    ver = runner.invoke(cli, ["--version"])
    assert ver.exit_code == 0
    assert __version__ in ver.output

    hlp = runner.invoke(cli, ["--help"])
    assert hlp.exit_code == 0
    assert "init" in hlp.output
    assert "add-module" in hlp.output
    assert "add-handler" in hlp.output
