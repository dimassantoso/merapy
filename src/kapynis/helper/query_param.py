from __future__ import annotations

from typing import Any, Mapping, TypeVar

from pydantic import BaseModel, ValidationError

from kapynis.helper.multi_error import MultiError

T = TypeVar("T", bound=BaseModel)


def parse_from_query_param(params: Mapping[str, Any], model_cls: type[T]) -> T:
    """Parse a query-param mapping into a Pydantic model.

    Mirrors candi's ``candihelper.ParseFromQueryParam``. Errors are converted to
    ``MultiError`` so callers get a stable error envelope.
    """
    data = {k: v for k, v in params.items() if v is not None and v != ""}
    try:
        return model_cls.model_validate(data)
    except ValidationError as e:
        me = MultiError()
        for err in e.errors():
            loc = ".".join(str(x) for x in err["loc"]) or "_"
            me.append(loc, err["msg"])
        raise me from e
