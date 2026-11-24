import pytest

from app.core import rate_limit


class FakeRedis:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def eval(self, script, key_count, key, window):
        self.calls.append((script, key_count, key, window))
        return self.result


def test_rate_limit_is_disabled_by_default(monkeypatch) -> None:
    monkeypatch.delenv("AUTH_RATE_LIMIT_ENABLED", raising=False)

    def unexpected_client(_url):
        raise AssertionError("Redis must not be contacted when the feature is disabled.")

    monkeypatch.setattr(rate_limit, "_redis_client", unexpected_client)

    rate_limit.enforce_rate_limit(
        "login-email",
        "account@example.com",
        limit=8,
        window_seconds=900,
    )


def test_rate_limit_uses_shared_redis_counter_and_hashed_identifier(monkeypatch) -> None:
    monkeypatch.setenv("AUTH_RATE_LIMIT_ENABLED", "true")
    monkeypatch.setenv("REDIS_URL", "rediss://redis.example.com:6380/0")
    monkeypatch.setenv("AUTH_EMAIL_INDEX_KEY", "i" * 48)
    fake = FakeRedis([4, 700])
    monkeypatch.setattr(rate_limit, "_redis_client", lambda _url: fake)

    rate_limit.enforce_rate_limit(
        "login-email",
        "Account@Example.com",
        limit=8,
        window_seconds=900,
    )

    _, key_count, key, window = fake.calls[0]
    assert key_count == 1
    assert key.startswith("finance-advisor:auth-rate:login-email:")
    assert "account@example.com" not in key
    assert window == 900


def test_rate_limit_rejects_requests_over_the_limit(monkeypatch) -> None:
    monkeypatch.setenv("AUTH_RATE_LIMIT_ENABLED", "true")
    monkeypatch.setenv("REDIS_URL", "rediss://redis.example.com:6380/0")
    monkeypatch.setenv("AUTH_EMAIL_INDEX_KEY", "i" * 48)
    monkeypatch.setattr(
        rate_limit,
        "_redis_client",
        lambda _url: FakeRedis([9, 712]),
    )

    with pytest.raises(rate_limit.RateLimitExceeded) as exc:
        rate_limit.enforce_rate_limit(
            "login-email",
            "account@example.com",
            limit=8,
            window_seconds=900,
        )

    assert exc.value.retry_after == 712


def test_rate_limit_fails_closed_when_redis_is_not_configured(monkeypatch) -> None:
    monkeypatch.setenv("AUTH_RATE_LIMIT_ENABLED", "true")
    monkeypatch.delenv("REDIS_URL", raising=False)

    with pytest.raises(rate_limit.RateLimitUnavailable):
        rate_limit.enforce_rate_limit(
            "login-email",
            "account@example.com",
            limit=8,
            window_seconds=900,
        )


def test_rate_limit_fails_closed_when_redis_is_unavailable(monkeypatch) -> None:
    monkeypatch.setenv("AUTH_RATE_LIMIT_ENABLED", "true")
    monkeypatch.setenv("REDIS_URL", "rediss://redis.example.com:6380/0")
    monkeypatch.setenv("AUTH_EMAIL_INDEX_KEY", "i" * 48)

    def fail(_url):
        raise OSError("unavailable")

    monkeypatch.setattr(rate_limit, "_redis_client", fail)

    with pytest.raises(rate_limit.RateLimitUnavailable):
        rate_limit.enforce_rate_limit(
            "login-email",
            "account@example.com",
            limit=8,
            window_seconds=900,
        )
