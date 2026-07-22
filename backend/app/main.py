from fastapi import FastAPI

from app.core.config import settings
from app.api.routes import achievements, auth, blocks, chat, favorites, matches, onboarding, pet_photos, pets, reports, users

from app.core.cors import setup_cors

app = FastAPI(
    title="PawSome API", 
    description="DOG MATCHING AND CHATTING APP",
    version="1.0.0"
)

setup_cors(app)

@app.on_event("startup")
async def startup_event():
    print("\n" + "="*60)
    print("🐾 PawSome Backend Starting...")
    print("="*60)
    print(f"📍 Environment: {settings.app_env}")
    print(f"🌐 API Docs: http://localhost:8000/docs")
    print(f"💚 Health Check: http://localhost:8000/health")
    print(f"🔗 Frontend URL: {settings.frontend_url}")
    print("="*60 + "\n")

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

@app.get("/")
def root():
    return {"message": "PawSome API", "docs": "/docs", "health": "/health"}


@app.get("/health")
def health():
    return {
        "status": "healthy",
        "env": settings.app_env,
    }
