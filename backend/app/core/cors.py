from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings

def _parse_cors_origins(raw:str) -> list[str]:
    return [origin.strip() for origin in raw.split(",") if origin.strip()]

def setup_cors(app:FastAPI) -> None:
    origins = _parse_cors_origins(settings.cors_origins)
    print(f"🔒 CORS enabled for origins: {origins}")
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
        allow_headers=["*"],
        expose_headers=["*"],
        max_age=3600,  # Cache preflight requests for 1 hour
    )