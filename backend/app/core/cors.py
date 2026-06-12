from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings

def _parse_cors_origins(raw:str) -> list[str]:
    return [origin.strip() for origin in raw.split(",") if origin.strip()]

def setup_cors(app:FastAPI) -> None:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_parse_cors_origins(settings.cors_origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )