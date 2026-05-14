from pathlib import Path

import pytest

from merapy.cli.markers import has_marker, inject


def test_inject_after_marker(tmp_path: Path) -> None:
    f = tmp_path / "f.py"
    f.write_text("class A:\n    # @merapy:slot\n    pass\n")
    assert inject(f, "slot", "x = 1") is True
    text = f.read_text()
    assert "# @merapy:slot" in text  # marker preserved
    assert "x = 1" in text


def test_inject_idempotent(tmp_path: Path) -> None:
    f = tmp_path / "f.py"
    f.write_text("# @merapy:slot\n")
    inject(f, "slot", "x = 1")
    second = inject(f, "slot", "x = 1")
    assert second is False  # second call no-op
    assert f.read_text().count("x = 1") == 1


def test_inject_unknown_marker_raises(tmp_path: Path) -> None:
    f = tmp_path / "f.py"
    f.write_text("pass\n")
    with pytest.raises(KeyError, match="marker"):
        inject(f, "missing", "x = 1")


def test_inject_preserves_indent(tmp_path: Path) -> None:
    f = tmp_path / "f.py"
    f.write_text("class A:\n    # @merapy:slot\n    pass\n")
    inject(f, "slot", "x = 1\ny = 2")
    text = f.read_text()
    assert "    x = 1\n" in text
    assert "    y = 2\n" in text


def test_has_marker(tmp_path: Path) -> None:
    f = tmp_path / "f.py"
    f.write_text("# @merapy:foo\n")
    assert has_marker(f, "foo")
    assert not has_marker(f, "bar")
