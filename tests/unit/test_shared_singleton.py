import pytest

from kapynis.repository.uow import SharedSingleton


def test_set_once_is_idempotent() -> None:
    s: SharedSingleton[str] = SharedSingleton(name="test")
    s.set("first")
    s.set("second")  # ignored — mirrors sync.Once
    assert s.get() == "first"


def test_get_before_set_raises() -> None:
    s: SharedSingleton[str] = SharedSingleton(name="test")
    with pytest.raises(RuntimeError, match="accessed before initialization"):
        s.get()


def test_reset_for_tests() -> None:
    s: SharedSingleton[str] = SharedSingleton(name="test")
    s.set("first")
    s.reset_for_tests()
    s.set("second")
    assert s.get() == "second"
