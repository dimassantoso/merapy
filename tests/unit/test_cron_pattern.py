from datetime import datetime, timezone

from kapynis.codebase.app.cron_worker.worker import _next_delay_seconds


def test_every_pattern_returns_interval_seconds() -> None:
    now = datetime(2026, 5, 12, tzinfo=timezone.utc)
    assert _next_delay_seconds("@every 30s", now) == 30
    assert _next_delay_seconds("@every 5m", now) == 300
    assert _next_delay_seconds("@every 2h", now) == 7200


def test_cron_pattern_returns_positive_delay() -> None:
    now = datetime(2026, 5, 12, 12, 0, 30, tzinfo=timezone.utc)
    # Every minute on the minute mark.
    delay = _next_delay_seconds("* * * * *", now)
    assert 0 < delay <= 60
