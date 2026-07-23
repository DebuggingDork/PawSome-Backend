# 🐾 PawSome Backend

FastAPI backend for **PawSome** — a Tinder-style matchmaking platform for pets. Handles auth, pet profiles, geolocation-based discovery, swiping, matching, and real-time chat.

Pairs with the [PawSome frontend](https://github.com/DebuggingDork/PawSomeFrontend) (React + Vite).

## 🏗️ Tech Stack

| Layer | Choice |
|---|---|
| Framework | FastAPI (Python 3.12) |
| Database | PostgreSQL (Neon) + SQLAlchemy 2.0 (async) |
| Migrations | Alembic |
| Cache / real-time | Redis (Upstash) |
| Auth | JWT (access + refresh tokens) |
| File storage | Cloudflare R2 (S3-compatible) |
| Package manager | [uv](https://github.com/astral-sh/uv) |

## 📦 Project Structure

```
backend/
├── app/
│   ├── api/routes/    # auth, users, pets, matches, chat, favorites, blocks, reports, ...
│   ├── core/          # config, security, db session
│   ├── models/        # SQLAlchemy models
│   ├── schemas/       # Pydantic request/response schemas
│   ├── services/      # business logic
│   └── utils/         # helpers
├── alembic/           # database migrations
└── docs/              # API specs and feature guides

docs/                  # setup, architecture, troubleshooting
START_BOTH.bat         # convenience: run backend + frontend together locally
TEST_CONNECTION.bat    # convenience: sanity-check both services are reachable
```

## 🚀 Getting Started

### Prerequisites
- Python 3.12+
- [uv](https://github.com/astral-sh/uv)
- PostgreSQL and Redis instances (local or hosted)

### Setup

```bash
cd backend
uv sync                        # install dependencies
cp .env.example .env           # fill in your own values
uv run alembic upgrade head    # apply migrations
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

The API is now available at `http://localhost:8000` — interactive docs at `/docs`.

> ⚠️ After pulling updates, always restart the server to load new environment variables.

### Running both services locally

If you also have the [frontend repo](https://github.com/DebuggingDork/PawSomeFrontend) checked out alongside this one as a sibling `frontend/` folder, `START_BOTH.bat` will launch both dev servers, and `TEST_CONNECTION.bat` will verify they're reachable.

## 🔑 Environment Variables

See [`backend/.env.example`](backend/.env.example) for the full list.

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | PostgreSQL connection string |
| `REDIS_URL` | Redis connection string |
| `JWT_SECRET` | Secret used to sign access/refresh tokens |
| `CORS_ORIGINS` | Must include the frontend's dev URL, e.g. `http://localhost:5174` |
| `FRONTEND_URL` | Used for links generated in emails/notifications |
| `R2_*` | Cloudflare R2 credentials for pet photo storage |

> 💡 CORS errors almost always mean `CORS_ORIGINS` doesn't match the frontend's port, or the server needs a restart after an `.env` change.

## ✨ Feature Status

**Implemented**
- User authentication (register/login with JWT)
- Pet profile creation & photo upload (Cloudflare R2, up to 5 photos)
- Public pet browsing (paginated, filterable by species/breed/gender)
- Swipe system with match detection and notifications
- Real-time chat, favorites, blocks, and reports

**Planned**
- Google OAuth login
- AI bio generation
- Push notifications (Firebase FCM)
- Premium features & Stripe subscriptions
- Playdate scheduler

## 🗄️ Database Migrations

```bash
cd backend
uv run alembic revision --autogenerate -m "describe your change"
uv run alembic upgrade head
```

## 🧪 Testing

```bash
cd backend
uv run pytest
```

## 📚 Documentation

- [Documentation Map](DOCUMENTATION_MAP.md) — index of everything below
- [Quick Start](docs/QUICK_START.md) · [Troubleshooting](docs/TROUBLESHOOTING.md) · [Port Configuration](docs/PORT_CONFIGURATION.md)
- [Architecture Overview](docs/ARCHITECTURE.md) · [Project Spec](project.md)
- [Backend API docs](backend/docs/README.md) — endpoints, chat API, matching system

## 📄 License

Private project — all rights reserved.
