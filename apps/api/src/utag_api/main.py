from contextlib import asynccontextmanager
from time import perf_counter
from uuid import uuid4

from fastapi import FastAPI, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from redis.asyncio import Redis
from sqlalchemy import text
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.responses import Response

from utag_api import __version__
from utag_api.config import get_settings
from utag_api.database import engine
from utag_api.errors import install_exception_handlers
from utag_api.observability import (
    HTTP_DURATION,
    HTTP_REQUESTS,
    configure_logging,
    get_logger,
    request_id_context,
)
from utag_api.realtime.router import router as realtime_router
from utag_api.routers.admin import router as admin_router
from utag_api.routers.adverts import router as adverts_router
from utag_api.routers.auth import router as auth_router
from utag_api.routers.chat import router as chat_router
from utag_api.routers.content import router as content_router
from utag_api.routers.dashboard import router as dashboard_router
from utag_api.routers.documents import router as documents_router
from utag_api.routers.events import router as events_router
from utag_api.routers.executives import router as executives_router
from utag_api.routers.galleries import router as galleries_router
from utag_api.routers.media import router as media_router
from utag_api.routers.members import router as members_router
from utag_api.routers.moderation import router as moderation_router
from utag_api.routers.notifications import router as notifications_router
from utag_api.routers.organization import router as organization_router
from utag_api.routers.public import router as public_router
from utag_api.security import constant_time_equal

settings = get_settings()
configure_logging(settings.debug)
logger = get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):  # type: ignore[no-untyped-def]
    logger.info("application_started", version=__version__, environment=settings.environment)
    yield
    logger.info("application_stopped")


app = FastAPI(
    title=settings.app_name,
    version=__version__,
    docs_url="/docs" if not settings.is_production else None,
    redoc_url=None,
    lifespan=lifespan,
)
install_exception_handlers(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-CSRF-Token", "Idempotency-Key", "If-Match"],
    expose_headers=["X-Request-ID", "ETag"],
)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts)
app.add_middleware(GZipMiddleware, minimum_size=1024)


@app.middleware("http")
async def request_context(request: Request, call_next):  # type: ignore[no-untyped-def]
    request_id = request.headers.get("X-Request-ID") or str(uuid4())
    token = request_id_context.set(request_id)
    started = perf_counter()
    try:
        response = await call_next(request)
    finally:
        request_id_context.reset(token)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
    if settings.is_production:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    route_object = request.scope.get("route")
    route = getattr(route_object, "path", "unmatched")
    duration_seconds = perf_counter() - started
    HTTP_REQUESTS.labels(request.method, route, str(response.status_code)).inc()
    HTTP_DURATION.labels(request.method, route).observe(duration_seconds)
    logger.info(
        "http_request",
        request_id=request_id,
        method=request.method,
        route=route,
        status=response.status_code,
        duration_ms=round(duration_seconds * 1000, 2),
    )
    return response


@app.get("/health/live", tags=["health"])
async def liveness() -> dict[str, str]:
    return {"status": "ok", "version": __version__}


@app.get("/health/ready", tags=["health"])
async def readiness() -> dict[str, str]:
    async with engine.connect() as connection:
        await connection.execute(text("SELECT 1"))
    redis = Redis.from_url(settings.redis_url)
    try:
        await redis.ping()
    finally:
        await redis.aclose()
    return {"status": "ready", "database": "ok", "redis": "ok"}


@app.get("/metrics", include_in_schema=False)
async def metrics(authorization: str | None = Header(default=None)) -> Response:
    if not settings.metrics_enabled:
        return Response(status_code=404)
    if settings.is_production:
        expected = settings.metrics_bearer_token
        supplied = authorization.removeprefix("Bearer ") if authorization else ""
        if not expected or not constant_time_equal(expected.get_secret_value(), supplied):
            return Response(status_code=401)
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


for api_router in (
    auth_router,
    public_router,
    dashboard_router,
    members_router,
    executives_router,
    organization_router,
    content_router,
    events_router,
    documents_router,
    media_router,
    moderation_router,
    notifications_router,
    chat_router,
    galleries_router,
    adverts_router,
    admin_router,
    realtime_router,
):
    app.include_router(api_router, prefix=settings.api_prefix)
