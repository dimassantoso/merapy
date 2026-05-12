from kapynis.shared.meta import Meta


def test_meta_total_pages_rounds_up() -> None:
    m = Meta.new(page=1, limit=10, total_records=25)
    assert m.total_pages == 3
    assert m.total_records == 25
    assert m.page == 1
    assert m.limit == 10


def test_meta_zero_records() -> None:
    m = Meta.new(page=1, limit=10, total_records=0)
    assert m.total_pages == 0


def test_meta_alias_serialization() -> None:
    m = Meta.new(page=2, limit=5, total_records=12)
    dumped = m.model_dump(by_alias=True)
    assert dumped["totalRecords"] == 12
    assert dumped["totalPages"] == 3
