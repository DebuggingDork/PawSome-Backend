from fastapi import FastAPI

from app.core.config import settings

app = FastAPI(title="PawSome API", description="DOG MATCHING AND CHATTING APP")


@app.get("/")
def root():
    return {"message": "PawSome API", "docs": "/docs", "health": "/health"}


@app.get("/health")
def health():
    return {
        "status": "healthy",
        "env": settings.app_env,
    }
