from fastapi import FastAPI

from app.core.config import settings
from app.api.routes import auth

from app.core.cors import setup_cors

app = FastAPI(title="PawSome API", description="DOG MATCHING AND CHATTING APP")

setup_cors(app)

app.include_router(auth.router)

@app.get("/")
def root():
    return {"message": "PawSome API", "docs": "/docs", "health": "/health"}


@app.get("/health")
def health():
    return {
        "status": "healthy",
        "env": settings.app_env,
    }
