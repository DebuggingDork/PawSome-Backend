import sys

# Some Windows terminals default to a codepage (e.g. cp1252) that can't encode
# emoji, which crashes any print() containing one before the app even starts
# (hit this three times now across main.py, cors.py, email.py). Reconfiguring
# stdout/stderr to UTF-8 here fixes it for every print in the process instead
# of stripping emoji one file at a time as they're found.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

import logging
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.config import settings
from app.api.routes import achievements, auth, blocks, chat, conditions, events, favorites, geocoding, matches, onboarding, pet_photos, pets, places, playdates, reports, travel, users

from app.core.cors import setup_cors
from app.core.logging import setup_logging

setup_logging(getattr(logging, settings.log_level.upper(), logging.INFO))
logger = logging.getLogger("pawsome")

app = FastAPI(
    title="PawSome API",
    description="DOG MATCHING AND CHATTING APP",
    version="1.0.0"
)

setup_cors(app)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """One line per request, with a request id, the status and how long it took.

    The id is echoed back as `X-Request-ID` and included on every log record
    emitted while handling the request, so a rejection reason logged deep in a
    route can be tied to the exact request the client saw fail.
    """
    request_id = uuid.uuid4().hex[:8]
    request.state.request_id = request_id
    started = time.perf_counter()

    try:
        response = await call_next(request)
    except Exception:
        elapsed_ms = (time.perf_counter() - started) * 1000
        # The generic handler below logs the traceback; this records the timing
        # and request id alongside it.
        logger.error(
            "req=%s %s %s -> UNHANDLED EXCEPTION after %.0fms",
            request_id, request.method, request.url.path, elapsed_ms,
        )
        raise

    elapsed_ms = (time.perf_counter() - started) * 1000
    response.headers["X-Request-ID"] = request_id

    # 5xx is a bug, 4xx is a rejection worth seeing, 2xx/3xx is noise at INFO.
    if response.status_code >= 500:
        level = logging.ERROR
    elif response.status_code >= 400:
        level = logging.WARNING
    else:
        level = logging.INFO

    logger.log(
        level,
        "req=%s %s %s -> %s (%.0fms)",
        request_id, request.method, request.url.path, response.status_code, elapsed_ms,
    )
    return response


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Log *why* a request was refused, not just that it was.

    A wall of `400 Bad Request` in the access log carries no reason at all. The
    detail string is already written for the client; this puts it in the server
    log too, next to the path and request id.
    """
    request_id = getattr(request.state, "request_id", "-")
    if exc.status_code >= 500:
        logger.error("req=%s %s %s refused %s: %s", request_id, request.method, request.url.path, exc.status_code, exc.detail)
    elif exc.status_code >= 400:
        logger.warning("req=%s %s %s refused %s: %s", request_id, request.method, request.url.path, exc.status_code, exc.detail)

    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers=getattr(exc, "headers", None),
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """422s are usually a client/server contract mismatch — log the offending fields."""
    request_id = getattr(request.state, "request_id", "-")
    logger.warning(
        "req=%s %s %s rejected 422 (validation): %s",
        request_id, request.method, request.url.path, exc.errors(),
    )
    return JSONResponse(status_code=422, content={"detail": exc.errors()})


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Anything that reaches here is a bug: log it with a traceback."""
    request_id = getattr(request.state, "request_id", "-")
    logger.exception(
        "req=%s %s %s failed with an unhandled %s",
        request_id, request.method, request.url.path, type(exc).__name__,
    )
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


@app.on_event("startup")
async def startup_event():
    logger.info("=" * 60)
    logger.info("PawSome backend starting")
    logger.info("environment : %s", settings.app_env)
    logger.info("frontend url: %s", settings.frontend_url)

    # Check both backing services up front and say plainly whether each is
    # usable. Without this the first sign of a dead Redis was a swipe failing
    # for no visible reason, minutes or hours after the process started.
    from sqlalchemy import text

    from app.core.database import engine
    from app.core.redis import check_redis

    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        logger.info("database    : OK")
    except Exception as exc:  # noqa: BLE001
        logger.error("database    : UNAVAILABLE (%s: %s)", type(exc).__name__, exc)
        logger.error("              every authenticated request will fail until this is fixed")

    redis_ok, redis_error = await check_redis()
    if redis_ok:
        logger.info("redis       : OK")

        # Wire the real-time fan-out here rather than lazily from the WebSocket
        # routes. Those only ran when someone opened a socket, so on a worker
        # where nobody had, the managers held no Redis client and every push
        # published nothing — likes and matches were saved but never delivered
        # live to anyone.
        from app.core.redis import get_redis
        from app.services.chat_manager import manager as chat_manager
        from app.services.notification_manager import manager as notif_manager

        redis = await get_redis()
        await chat_manager.initialize(redis)
        await notif_manager.initialize(redis)
    else:
        logger.error("redis       : UNAVAILABLE (%s)", redis_error)
        logger.error("              rate limits (Super Woof, undo) and cross-worker")
        logger.error("              chat/notification delivery will not work")

    logger.info("=" * 60)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(onboarding.router)
app.include_router(achievements.router)
app.include_router(pets.router)
app.include_router(pet_photos.router)
app.include_router(matches.router)
app.include_router(favorites.router)
app.include_router(blocks.router)
app.include_router(chat.router)
app.include_router(reports.router)
app.include_router(playdates.router)
app.include_router(events.router)
app.include_router(geocoding.router)
app.include_router(conditions.router)
app.include_router(places.router)
app.include_router(travel.router)

@app.get("/")
def root():
    return {"message": "PawSome API", "docs": "/docs", "health": "/health"}


@app.get("/health")
async def health():
    """Reports the backing services individually rather than a flat "healthy".

    A green health check that only proves the process is running is what let a
    dead Redis look like a working backend.
    """
    from sqlalchemy import text

    from app.core.database import engine
    from app.core.redis import check_redis

    db_ok, db_error = True, None
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001
        db_ok, db_error = False, f"{type(exc).__name__}: {exc}"
        logger.error("health check: database UNAVAILABLE (%s)", db_error)

    redis_ok, redis_error = await check_redis()
    if not redis_ok:
        logger.error("health check: redis UNAVAILABLE (%s)", redis_error)

    return {
        "status": "healthy" if (db_ok and redis_ok) else "degraded",
        "env": settings.app_env,
        "services": {
            "database": {"ok": db_ok, "error": db_error},
            "redis": {"ok": redis_ok, "error": redis_error},
        },
    }
