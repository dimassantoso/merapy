from merapy.helper.multi_error import MultiError
from merapy.shared.meta import Meta
from merapy.wrapper.http_response import HTTPResponse


def test_success_routes_data() -> None:
    resp = HTTPResponse.new(200, "ok", {"foo": "bar"})
    assert resp.success is True
    assert resp.code == 200
    assert resp.data == {"foo": "bar"}
    assert resp.errors is None
    assert resp.meta is None


def test_failure_routes_multi_error_to_errors() -> None:
    me = MultiError()
    me.append("name", "is required")
    resp = HTTPResponse.new(400, "validation failed", me)
    assert resp.success is False
    assert resp.errors == {"name": ["is required"]}
    assert resp.data is None


def test_meta_routed() -> None:
    meta = Meta.new(page=1, limit=10, total_records=42)
    resp = HTTPResponse.new(200, "ok", meta, [{"id": 1}])
    assert resp.meta is not None
    assert resp.meta["totalRecords"] == 42
    assert resp.data == [{"id": 1}]


def test_to_response_status_matches() -> None:
    resp = HTTPResponse.new(404, "not found")
    starlette_resp = resp.to_response()
    assert starlette_resp.status_code == 404
