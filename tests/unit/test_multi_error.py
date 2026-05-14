from merapy.helper.multi_error import MultiError


def test_append_and_to_map() -> None:
    me = MultiError()
    me.append("name", "is required")
    me.append("name", "too short")
    me.append("email", "invalid format")
    assert me.has_errors()
    assert me.to_map() == {
        "name": ["is required", "too short"],
        "email": ["invalid format"],
    }


def test_no_errors() -> None:
    me = MultiError()
    assert not me.has_errors()
    assert me.to_map() == {}
