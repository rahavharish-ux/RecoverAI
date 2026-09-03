"""Small, dependency-free ASGI/Starlette middlewares for a publicly
reachable demo deployment — no new infrastructure, just safe defaults
FastAPI doesn't apply out of the box."""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Baseline response headers with no functional downside for a pure
    JSON API: they don't affect any existing behavior, they only remove
    ambiguity a browser could otherwise exploit (MIME sniffing, framing)."""

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        return response


class MaxBodySizeMiddleware(BaseHTTPMiddleware):
    """Rejects a request whose declared Content-Length exceeds `max_bytes`
    before it's read into memory. This API's real payloads are small JSON
    (well under 10 KB); the cap is generous on purpose — it exists to stop
    a deliberately oversized body, not to constrain legitimate use."""

    def __init__(self, app, *, max_bytes: int) -> None:
        super().__init__(app)
        self.max_bytes = max_bytes

    async def dispatch(self, request: Request, call_next) -> Response:
        content_length = request.headers.get("content-length")
        if content_length is not None:
            try:
                too_large = int(content_length) > self.max_bytes
            except ValueError:
                too_large = False
            if too_large:
                return JSONResponse({"detail": "Request body too large."}, status_code=413)
        return await call_next(request)
