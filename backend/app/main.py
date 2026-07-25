import sys

# Some Windows terminals default to a codepage (e.g. cp1252) that can't encode
# emoji, which crashes any print() containing one before the app even starts
# (hit this three times now across main.py, cors.py, email.py). Reconfiguring
# stdout/stderr to UTF-8 here fixes it for every print in the process instead
# of stripping emoji one file at a time as they're found.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

from fastapi import FastAPI

from app.core.config import settings
from app.api.routes import achievements, auth, blocks, chat, events, favorites, geocoding, matches, onboarding, pet_photos, pets, playdates, reports, users

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
app.include_router(playdates.router)
app.include_router(events.router)
app.include_router(geocoding.router)

@app.get("/")
def root():
    return {"message": "PawSome API", "docs": "/docs", "health": "/health"}


@app.get("/health")
def health():
    return {
        "status": "healthy",
        "env": settings.app_env,
    }
