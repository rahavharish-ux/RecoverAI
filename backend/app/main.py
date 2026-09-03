from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from app.api.routes import agent, cases, dashboard, demo, health, ml, payment_attempts, policy
from app.core.config import get_settings
from app.core.http_hardening import MaxBodySizeMiddleware, SecurityHeadersMiddleware

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Dev/demo convenience only. Real environments should use versioned
    # migrations (Alembic — flagged, not yet added, per the approved
    # blueprint's Phase 6) instead of relying on create_all().
    if settings.auto_create_tables:
        from app.db.session import engine
        from app.models import Base

        Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)

# Ordered outermost-first. CORS must be outermost so it can answer
# preflight OPTIONS requests before anything else runs.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],  # the only methods any route uses
    allow_headers=["Content-Type"],  # the only header the frontend sends
)
# "*" (the default) is a deliberate no-op — the real deployment host isn't
# known ahead of time. Restrict via TRUSTED_HOSTS once it is.
app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.trusted_hosts)
app.add_middleware(MaxBodySizeMiddleware, max_bytes=settings.max_request_body_bytes)
app.add_middleware(SecurityHeadersMiddleware)

app.include_router(health.router, prefix=settings.api_prefix)
app.include_router(payment_attempts.router, prefix=settings.api_v1_prefix)
app.include_router(cases.router, prefix=settings.api_v1_prefix)
app.include_router(policy.router, prefix=settings.api_v1_prefix)
app.include_router(ml.router, prefix=settings.api_v1_prefix)
app.include_router(agent.router, prefix=settings.api_v1_prefix)
app.include_router(dashboard.router, prefix=settings.api_v1_prefix)
app.include_router(demo.router, prefix=settings.api_v1_prefix)
