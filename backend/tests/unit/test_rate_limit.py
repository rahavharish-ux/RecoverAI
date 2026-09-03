"""Pure logic tests for SlidingWindowLimiter — no FastAPI, no app, no
settings/lru_cache involved, so these can never be flaky or interfere
with the rest of the test suite (see tests/conftest.py for how the
FastAPI-facing dependency form is disabled during the rest of the suite)."""

from app.core.rate_limit import SlidingWindowLimiter


def test_allows_requests_up_to_the_limit():
    limiter = SlidingWindowLimiter(max_requests=3, window_seconds=60)
    assert limiter.allow("client-a", now=0.0) is True
    assert limiter.allow("client-a", now=1.0) is True
    assert limiter.allow("client-a", now=2.0) is True


def test_blocks_once_the_limit_is_reached():
    limiter = SlidingWindowLimiter(max_requests=3, window_seconds=60)
    for t in (0.0, 1.0, 2.0):
        assert limiter.allow("client-a", now=t) is True
    assert limiter.allow("client-a", now=3.0) is False


def test_window_slides_and_old_hits_expire():
    limiter = SlidingWindowLimiter(max_requests=2, window_seconds=10)
    assert limiter.allow("client-a", now=0.0) is True
    assert limiter.allow("client-a", now=1.0) is True
    assert limiter.allow("client-a", now=2.0) is False  # limit hit within the window

    # Once the window has fully slid past both earlier hits, room opens up.
    assert limiter.allow("client-a", now=11.5) is True


def test_different_keys_are_tracked_independently():
    limiter = SlidingWindowLimiter(max_requests=1, window_seconds=60)
    assert limiter.allow("client-a", now=0.0) is True
    assert limiter.allow("client-a", now=0.5) is False
    assert limiter.allow("client-b", now=0.5) is True  # a different client is unaffected
