"""Migration guard — run before starting the app.

Checks whether the database schema is up to date with the SQLAlchemy models.
If tables are missing, auto-generates an alembic revision file and exits with
a clear message telling the user to run ``make migration`` first.

Usage in ``main.py``::

    from kapynis.config.migration import check_pending_migrations
    await check_pending_migrations(cfg)
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kapynis.config.config import Config


async def check_pending_migrations(cfg: "Config", service_root: Path | None = None) -> None:
    """Check for missing tables and auto-generate a migration if needed.

    Args:
        cfg: The loaded service config (must have sql_db wired).
        service_root: Path to the service root directory. Defaults to cwd.

    If the schema is out of date:
    1. Auto-generates an alembic revision file (``alembic revision --autogenerate``).
    2. Prints a clear message.
    3. Exits with code 1 so ``make run`` stops cleanly.
    """
    from kapynis.codebase.factory.dependency import get_dependency

    sql_db = get_dependency().sql_db()
    if sql_db is None:
        return  # No SQL configured — nothing to check.

    root = service_root or Path.cwd()
    alembic_ini = root / "alembic.ini"
    if not alembic_ini.exists():
        return  # Not an alembic-managed service.

    missing = await _find_missing_tables(sql_db, root, cfg)
    if not missing:
        return  # Schema is up to date.

    _print_warning(missing)
    generated = _autogenerate_revision(root, missing)
    if generated:
        print(
            f"\n\033[32m✓ Migration file created.\033[0m Run:\n\n"
            f"    make migration\n\n"
            f"Then restart with:\n\n"
            f"    make run\n",
            file=sys.stderr,
        )
    else:
        print(
            "\n\033[33mCould not auto-generate migration. "
            "Run 'make migration-create name=init' manually.\033[0m\n",
            file=sys.stderr,
        )
    sys.exit(1)


async def _find_missing_tables(sql_db: object, root: Path, cfg: "Config | None" = None) -> list[str]:
    """Return table names that exist in SQLAlchemy metadata but not in the DB."""
    from sqlalchemy import inspect
    from sqlalchemy.ext.asyncio import AsyncEngine

    engine: AsyncEngine = sql_db.write_engine()  # type: ignore[attr-defined]

    # Collect all table names from all registered metadata objects.
    expected: set[str] = set()

    # Service models — import Base from the service's shared domain.
    try:
        import importlib.util, sys as _sys
        src_path = str(root / "src")
        if src_path not in _sys.path:
            _sys.path.insert(0, src_path)
        spec = importlib.util.spec_from_file_location(
            "pkg.shared.domain", root / "src" / "pkg" / "shared" / "domain" / "__init__.py"
        )
        if spec and spec.loader:
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)  # type: ignore[union-attr]
            base = getattr(mod, "Base", None)
            if base is not None:
                expected.update(base.metadata.tables.keys())
    except Exception:
        pass

    # kapynis_tasks — only when task queue worker is enabled.
    if cfg is not None and cfg.env.use_task_queue_worker:
        from kapynis.codebase.app.task_queue_worker.model import TaskQueueBase
        expected.update(TaskQueueBase.metadata.tables.keys())

    if not expected:
        return []

    # Check which tables actually exist in the DB.
    async with engine.connect() as conn:
        existing: set[str] = set(
            await conn.run_sync(lambda sync_conn: inspect(sync_conn).get_table_names())
        )

    return sorted(expected - existing)


def _print_warning(missing: list[str]) -> None:
    tables = ", ".join(f"'{t}'" for t in missing)
    print(
        f"\n\033[31m✗ Database schema is out of date.\033[0m\n"
        f"  Missing tables: {tables}\n",
        file=sys.stderr,
    )


def _autogenerate_revision(root: Path, missing: list[str]) -> bool:
    """Run ``alembic revision --autogenerate`` and return True if successful."""
    import subprocess

    message = "add_" + "_".join(missing[:3]).replace(" ", "_")
    try:
        result = subprocess.run(
            ["alembic", "revision", "--autogenerate", "-m", message],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            # Print the generated file path from alembic output.
            for line in result.stdout.splitlines():
                if "Generating" in line or "revision" in line.lower():
                    print(f"  {line.strip()}", file=sys.stderr)
            return True
        else:
            print(result.stderr, file=sys.stderr)
            return False
    except Exception as e:
        print(f"  alembic error: {e}", file=sys.stderr)
        return False
