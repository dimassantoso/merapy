from merapy.shared.filter import Filter
from merapy.shared.meta import Meta


def test_filter_offset() -> None:
    f = Filter(page=3, limit=20)
    assert f.offset == 40


def test_filter_calculate_meta() -> None:
    f = Filter(page=2, limit=10)
    meta = f.calculate_meta(35)
    assert isinstance(meta, Meta)
    assert meta.page == 2
    assert meta.total_pages == 4


def test_filter_default_sort_is_desc() -> None:
    f = Filter()
    assert f.sort == "desc"
    assert f.page == 1
    assert f.limit == 10
