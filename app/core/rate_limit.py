"""Shared Redis-backed rate limiting for authentication endpoints."""

import hashlib
import hmac
from functools import lru_cache

from redis import Redis
from redis.exceptions import RedisError

from app.core.config import get_setting

_WINDOW_SCRIPT = """
local count = redis.call('INCR', KEYS[1])
if count == 1 then
  redis.call('EXPIRE', KEYS[1], ARGV[1])
end
local ttl = redis.call('TTL', KEYS[1])
return {count, ttl}
"""


class RateLimitExceeded(RuntimeError):
    """Raised when an identity exceeds its configured request allowance."""

    def __init__(self, retry_after: int) -> None:
        self.retry_after = max(1, retry_after)
        super().__init__("The request limit has been reached.")


class RateLimitUnavailable(RuntimeError):
    """Raised when rate limiting is enabled but its shared store is unavailable."""


@lru_cache(maxsize=1)
def _redis_client(redis_url: str) -> Redis:
    """Create one bounded-timeout Redis client for this application process."""
    return Redis.from_url(
        redis_url,
        decode_responses=True,
        socket_connect_timeout=2,
        socket_timeout=2,
        health_check_interval=30,
    )


def reset_rate_limit_client() -> None:
    """Clear the cached client after configuration changes or in isolated tests."""
    _redis_client.cache_clear()


def enforce_rate_limit(
    action: str,
    identifier: str,
    *,
    limit: int,
    window_seconds: int,
) -> None:
    """Enforce a fixed-window limit using an atomic Redis script.

    Identifiers are HMACed before they are written to Redis. The counter is
    shared across Code Engine instances, unlike a process-local memory counter.
    """
    enabled = (get_setting("AUTH_RATE_LIMIT_ENABLED", "false") or "false").strip().casefold()
    if enabled not in {"1", "true", "yes", "on"}:
        return

    redis_url = get_setting("REDIS_URL")
    if not redis_url:
        raise RateLimitUnavailable("The shared rate-limit store is not configured.")

    if limit < 1 or window_seconds < 1:
        raise ValueError("Rate-limit values must be positive.")

    hash_key = get_setting("AUTH_EMAIL_INDEX_KEY")
    if not hash_key or len(hash_key.encode("utf-8")) < 32:
        raise RateLimitUnavailable("The rate-limit identifier key is not configured.")

    normalized = identifier.strip().casefold()
    digest = hmac.new(
        hash_key.encode("utf-8"),
        normalized.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    redis_key = f"finance-advisor:auth-rate:{action}:{digest}"

    try:
        result = _redis_client(redis_url).eval(
            _WINDOW_SCRIPT,
            1,
            redis_key,
            window_seconds,
        )
        count, ttl = int(result[0]), int(result[1])
    except (RedisError, OSError, TypeError, ValueError, IndexError) as exc:
        raise RateLimitUnavailable("The shared rate-limit store is unavailable.") from exc

    if count > limit:
        raise RateLimitExceeded(ttl)
