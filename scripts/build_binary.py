#!/usr/bin/env python3
"""Build a standalone ``merapy`` CLI binary and place release artifacts in ``release/``.

Usage::

    .venv/bin/python scripts/build_binary.py
    .venv/bin/python scripts/build_binary.py --with-dist
    .venv/bin/python scripts/build_binary.py --output-dir release
"""

from __future__ import annotations

import argparse
import hashlib
import os
import platform
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENTRY_POINT = ROOT / "src" / "merapy" / "cli" / "__main__.py"
TEMPLATES_DIR = ROOT / "src" / "merapy" / "cli" / "templates"

# Heavy runtime libraries that the CLI scaffolder never imports.
# Excluding them keeps the standalone CLI binary small and fast to start.
_EXCLUDED_MODULES = [
    "fastapi",
    "starlette",
    "litestar",
    "uvicorn",
    "uvloop",
    "httptools",
    "websockets",
    "watchfiles",
    "sqlalchemy",
    "asyncpg",
    "alembic",
    "mako",
    "motor",
    "pymongo",
    "bson",
    "redis",
    "aiokafka",
    "aio_pika",
    "aiormq",
    "pamqp",
    "croniter",
    "pydantic",
    "pydantic_core",
    "pydantic_settings",
    "jsonschema",
    "structlog",
    "opentelemetry",
    "cryptography",
    "grpc",
    "grpc_tools",
    "google.protobuf",
    "strawberry",
    "graphql",
    "psutil",
    "pytest",
    "mypy",
    "ruff",
    "httpx",
    "rich",
    "pygments",
    "faker",
    "polyfactory",
    "msgspec",
    "anyio",
]


def detect_target_name() -> str:
    """Return a normalized platform binary name like ``merapy-macos-arm64``."""
    sys_name = platform.system().lower()
    machine = platform.machine().lower()

    os_label = {
        "darwin": "macos",
        "linux": "linux",
        "windows": "windows",
    }.get(sys_name, sys_name)

    arch_label = {
        "x86_64": "x86_64",
        "amd64": "x86_64",
        "arm64": "arm64",
        "aarch64": "arm64",
    }.get(machine, machine)

    ext = ".exe" if os_label == "windows" else ""
    return f"merapy-{os_label}-{arch_label}{ext}"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def write_checksums(release_dir: Path) -> Path:
    checksum_file = release_dir / "SHA256SUMS.txt"
    lines: list[str] = []
    for item in sorted(release_dir.iterdir()):
        if not item.is_file() or item.name == "SHA256SUMS.txt" or item.name.startswith("."):
            continue
        lines.append(f"{sha256_file(item)}  {item.name}")
    checksum_file.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    return checksum_file


def build_binary(output_dir: Path, binary_name: str) -> Path:
    if not ENTRY_POINT.is_file():
        raise FileNotFoundError(f"CLI entry point not found: {ENTRY_POINT}")
    if not TEMPLATES_DIR.is_dir():
        raise FileNotFoundError(f"CLI templates directory not found: {TEMPLATES_DIR}")

    output_dir.mkdir(parents=True, exist_ok=True)
    data_sep = ";" if os.name == "nt" else ":"

    with tempfile.TemporaryDirectory(prefix="merapy-pyinstaller-") as tmp:
        tmp_path = Path(tmp)
        dist_dir = tmp_path / "dist"
        work_dir = tmp_path / "build"
        spec_dir = tmp_path / "spec"

        base_name = binary_name[:-4] if binary_name.endswith(".exe") else binary_name

        cmd = [
            sys.executable,
            "-m",
            "PyInstaller",
            "--onefile",
            "--clean",
            "--noconfirm",
            "--name",
            base_name,
            "--distpath",
            str(dist_dir),
            "--workpath",
            str(work_dir),
            "--specpath",
            str(spec_dir),
            "--paths",
            str(ROOT / "src"),
            "--add-data",
            f"{TEMPLATES_DIR}{data_sep}merapy/cli/templates",
            "--copy-metadata",
            "merapy",
            "--hidden-import",
            "merapy.cli.commands.init_service",
            "--hidden-import",
            "merapy.cli.commands.add_module",
            "--hidden-import",
            "merapy.cli.commands.add_handler",
            "--hidden-import",
            "merapy.cli.markers",
            "--hidden-import",
            "merapy.cli.render",
            "--hidden-import",
            "merapy.helper.string_case",
        ]
        for mod in _EXCLUDED_MODULES:
            cmd.extend(["--exclude-module", mod])
        cmd.append(str(ENTRY_POINT))

        print(f"Building standalone binary '{binary_name}'...")
        subprocess.run(cmd, cwd=str(ROOT), check=True)

        built_path = dist_dir / binary_name
        if not built_path.is_file():
            raise FileNotFoundError(f"Expected binary not produced at {built_path}")

        dest_path = output_dir / binary_name
        shutil.copy2(built_path, dest_path)
        if os.name != "nt":
            dest_path.chmod(0o755)
        return dest_path


def build_python_dist(output_dir: Path) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    copied: list[Path] = []
    with tempfile.TemporaryDirectory(prefix="merapy-dist-") as tmp:
        subprocess.run(
            [sys.executable, "-m", "build", "--outdir", tmp],
            cwd=str(ROOT),
            check=True,
        )
        for artifact in sorted(Path(tmp).iterdir()):
            if artifact.is_file():
                dest = output_dir / artifact.name
                shutil.copy2(artifact, dest)
                copied.append(dest)
    return copied


def main() -> int:
    parser = argparse.ArgumentParser(description="Build standalone merapy CLI binary.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "release",
        help="Directory where release artifacts are written (default: ./release).",
    )
    parser.add_argument(
        "--name",
        type=str,
        default="",
        help="Override output binary filename (default: merapy-<os>-<arch>).",
    )
    parser.add_argument(
        "--with-dist",
        action="store_true",
        help="Also build Python wheel and sdist into the release directory.",
    )
    args = parser.parse_args()

    out_dir = args.output_dir.resolve()
    binary_name = args.name.strip() or detect_target_name()

    # Basic filename validation to prevent path traversal
    if Path(binary_name).name != binary_name:
        raise ValueError(f"Invalid binary name: {binary_name!r}")

    binary_path = build_binary(out_dir, binary_name)
    size_mb = binary_path.stat().st_size / (1024 * 1024)
    print(f"Created {binary_path} ({size_mb:.1f} MB)")

    if args.with_dist:
        for dist_file in build_python_dist(out_dir):
            print(f"Created {dist_file}")

    checksum_path = write_checksums(out_dir)
    print(f"Updated {checksum_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
