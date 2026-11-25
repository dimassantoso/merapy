"""End-to-end unit tests for smooth Task Queue onboarding via CLI."""

from __future__ import annotations

import json
import py_compile
from pathlib import Path

from click.testing import CliRunner

from merapy.cli.__main__ import cli


def test_init_with_task_queue_enables_sql_and_dep(tmp_path: Path, monkeypatch: object) -> None:
    monkeypatch.chdir(tmp_path)  # type: ignore[attr-defined]
    runner = CliRunner()
    # Select REST (1), Task Queue (6), skip dependencies (empty) -> SQL auto-enabled!
    res = runner.invoke(cli, ["init"], input="billing-svc\ninvoice\n1\n6\n\n")
    assert res.exit_code == 0, res.output

    svc = tmp_path / "billing-svc"
    assert (svc / "src" / "internal" / "modules" / "invoice" / "delivery" / "task_queue_handler.py").is_file()

    env_text = (svc / ".env").read_text()
    assert "USE_TASK_QUEUE_WORKER=true" in env_text
    assert "TASK_QUEUE_DASHBOARD_PORT=8080" in env_text
    assert "SQL_DSN_WRITE=" in env_text

    pyproj_text = (svc / "pyproject.toml").read_text()
    assert "merapy-taskqueue[sql,metrics]" in pyproj_text

    cfg = json.loads((svc / "merapy.json").read_text())
    assert "task_queue" in cfg["worker_handlers"]
    assert "sql" in cfg["dependencies"]

    py_compile.compile(str(svc / "src" / "internal" / "service.py"), doraise=True)


def test_add_handler_task_queue_wires_module_env_and_pyproject(
    tmp_path: Path, monkeypatch: object
) -> None:
    monkeypatch.chdir(tmp_path)  # type: ignore[attr-defined]
    runner = CliRunner()
    # Initially scaffold WITHOUT task_queue (REST only + SQL)
    res_init = runner.invoke(cli, ["init"], input="shop-svc\norder\n1\n\n2\n")
    assert res_init.exit_code == 0, res_init.output

    svc = tmp_path / "shop-svc"
    assert "USE_TASK_QUEUE_WORKER=false" in (svc / ".env").read_text()
    assert "merapy-taskqueue" not in (svc / "pyproject.toml").read_text()

    # Now add task_queue handler to order module
    res_add = runner.invoke(cli, ["add-handler", "order", "task_queue", "--service-root", str(svc)])
    assert res_add.exit_code == 0, res_add.output

    assert (svc / "src" / "internal" / "modules" / "order" / "delivery" / "task_queue_handler.py").is_file()

    module_text = (svc / "src" / "internal" / "modules" / "order" / "module.py").read_text()
    assert "OrderTaskQueueHandler" in module_text
    assert "Worker.TASK_QUEUE" in module_text

    env_text = (svc / ".env").read_text()
    assert "USE_TASK_QUEUE_WORKER=true" in env_text
    assert "TASK_QUEUE_DASHBOARD_PORT=8080" in env_text
    assert "TASK_QUEUE_DASHBOARD_MAX_CLIENT=5" in env_text

    pyproj_text = (svc / "pyproject.toml").read_text()
    assert pyproj_text.count("merapy-taskqueue") == 1

    # Running add-handler a second time must remain idempotent
    res_add2 = runner.invoke(cli, ["add-handler", "order", "task_queue", "--service-root", str(svc)])
    assert res_add2.exit_code == 0, res_add2.output
    assert (svc / "pyproject.toml").read_text().count("merapy-taskqueue") == 1

    py_compile.compile(str(svc / "src" / "internal" / "modules" / "order" / "module.py"), doraise=True)
    py_compile.compile(str(svc / "src" / "internal" / "service.py"), doraise=True)
