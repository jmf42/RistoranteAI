from app.core.rate_limit import InMemoryRateLimiter


def test_rate_limiter_blocks_after_limit() -> None:
    limiter = InMemoryRateLimiter()
    assert limiter.allow(key="ip:/login", limit=2, window_seconds=60, now=100.0) == (True, 0)
    assert limiter.allow(key="ip:/login", limit=2, window_seconds=60, now=101.0) == (True, 0)
    allowed, retry_after = limiter.allow(key="ip:/login", limit=2, window_seconds=60, now=102.0)
    assert allowed is False
    assert retry_after > 0


def test_rate_limiter_prunes_old_entries() -> None:
    limiter = InMemoryRateLimiter()
    limiter.allow(key="ip:/api", limit=1, window_seconds=60, now=100.0)
    allowed, retry_after = limiter.allow(key="ip:/api", limit=1, window_seconds=60, now=161.0)
    assert allowed is True
    assert retry_after == 0
