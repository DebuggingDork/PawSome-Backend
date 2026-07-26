from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings

def _parse_cors_origins(raw:str) -> list[str]:
    return [origin.strip() for origin in raw.split(",") if origin.strip()]

def setup_cors(app:FastAPI) -> None:
    origins = _parse_cors_origins(settings.cors_origins)
    # Vercel gives every preview deploy its own hostname, so an exact-match list can
    # only ever cover the production URL. CORS_ORIGIN_REGEX covers the rest.
    origin_regex = settings.cors_origin_regex.strip() or None
    # Plain ASCII only — some Windows terminals default to a codepage (e.g. cp1252)
    # that can't encode this emoji, which crashed the server on import before it
    # ever got to bind a socket.
    print(f"CORS enabled for origins: {origins} regex={origin_regex}")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_origin_regex=origin_regex,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
        allow_headers=["*"],
        expose_headers=["*"],
        max_age=3600,  # Cache preflight requests for 1 hour
    )