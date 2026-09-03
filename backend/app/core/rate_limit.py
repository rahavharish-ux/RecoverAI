"""A minimal, dependency-free, in-process sliding-window rate limiter for
the handful of expensive endpoints (agent decisions/execution, demo
scenario runs) that a public, unauthenticated demo deployment could
otherwise have scripted against without any cost control — generating
unbounded synthetic data or, if an LLM provider key is configured,
burning through API credits with no limit.

Single-process, in-memory only, and intentionally so: this demo runs as
one process, and a distributed limiter (Redis, etc.) would be
disproportionate infrastructure for what it protects. Each guarded route
gets its own `SlidingWindowLimiter` instance (see api/routes/agent.py,
api/routes/demo.py); a test — or a deployer who wants no limiting at all
for a given route — can override that specific instance via
`app.dependency_overrides[<the_limiter_instance>] = lambda: None`, the
same pattern already used for `get_payment_gateway` in tests/conftest.py.
"""

import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request


class SlidingWindowLimiter:
    """The counting logic (`allow`) is pure and independent of FastAPI —
    trivially unit-testable with fake timestamps. `__call__` is the
    FastAPI-dependency form used via `Depends(...)` on a route."""

    def __init__(self, *, max_requests: int, window_seconds: float) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._hits: dict[str, deque] = defaultdict(deque)

    def allow(self, key: str, now: float | None = None) -> bool:
        now = time.monotonic() if now is None else now
        window = self._hits[key]
        while window and now - window[0] > self.window_seconds:
            window.popleft()
        if len(window) >= self.max_requests:
            return False
        window.append(now)
        return True

    @staticmethod
    def _client_key(request: Request) -> str:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    def __call__(self, request: Request) -> None:
        if not self.allow(self._client_key(request)):
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded for this endpoint — please slow down and try again shortly.",
            )
