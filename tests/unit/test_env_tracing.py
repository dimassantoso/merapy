from merapy.config.env import Env


def test_jaeger_otlp_endpoint_env(monkeypatch) -> None:
    monkeypatch.setenv("JAEGER_OTLP_ENDPOINT", "http://localhost:4317")
    monkeypatch.setenv("JAEGER_BASE_URL", "http://localhost:16686")
    monkeypatch.setenv("TRACE_BODY_MAX_SIZE", "1234")

    env = Env(_env_file=None)

    assert env.jaeger_otlp_endpoint == "http://localhost:4317"
    assert env.jaeger_base_url == "http://localhost:16686"
    assert env.trace_body_max_size == 1234
