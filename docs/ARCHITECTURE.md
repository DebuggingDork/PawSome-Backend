# 🏗️ PawSome Architecture Overview

## System Architecture

```
┌─────────────────────────────────────────────────────────┐
│          Frontend (React + Vite)                        │
│          http://localhost:5173                          │
│  • TanStack Query for data fetching                     │
│  • Zustand for state management                         │
│  • Framer Motion for animations                         │
└──────────────────┬──────────────────────────────────────┘
                   │
                   │ HTTP/HTTPS (REST API)
                   │ CORS: http://localhost:5173
                   │
┌──────────────────▼──────────────────────────────────────┐
│          Backend (FastAPI + Python)                     │
│          http://localhost:8000                          │
│  • JWT Authentication (Access + Refresh tokens)         │
│  • RESTful API endpoints                                │
│  • WebSocket for real-time chat                         │
└──┬────────┬─────────┬─────────────┬─────────────────────┘
   │        │         │             │
   │        │         │             │
   ▼        ▼         ▼             ▼
┌─────┐ ┌───────┐ ┌────────┐ ┌──────────────┐
│Neon │ │Upstash│ │Cloudfl.│ │ OpenAI API   │
│PgSQL│ │Redis  │ │R2      │ │ (Future)     │
└─────┘ └───────┘ └────────┘ └──────────────┘
```

## Communication Flow

### 1. Authentication Flow
```
Frontend                    Backend                     Database
   │                          │                            │
   │─── POST /auth/register ──>│                            │
   │                          │─── Create User ───────────>│
   │                          │<── User Created ───────────│
   │<── {access, refresh} ────│                            │
   │                          │                            │
   │─── Store tokens ─────────>                            │
   │    (localStorage)         │                            │
```

### 2. API Request Flow with JWT
```
Frontend                    Backend                     Database
   │                          │                            │
   │─── GET /pets/me ─────────>│                            │
   │    Header: Authorization  │                            │
   │    Bearer <access_token>  │                            │
   │                          │─── Verify JWT ─────────────│
   │                          │─── Query Pets ─────────────>│
   │                          │<── Pet Data ────────────────│
   │<── Pet List ──────────────│                            │
```

### 3. Token Refresh Flow
```
Frontend                    Backend                     Redis
   │                          │                            │
   │─── POST /auth/refresh ───>│                            │
   │    {refresh_token}        │                            │
   │                          │─── Check revocation ───────>│
   │                          │<── Not revoked ─────────────│
   │                          │─── Generate new tokens ─────│
   │<── {access, refresh} ─────│                            │
```

## Directory Structure

### Backend Structure
```
backend/
├── app/
│   ├── api/
│   │   ├── routes/          # API endpoint handlers
│   │   │   ├── auth.py      # /auth/* endpoints
│   │   │   ├── pets.py      # /pets/* endpoints
│   │   │   ├── matches.py   # /matches/* endpoints
│   │   │   └── chat.py      # /chat/* + WebSocket
│   │   └── deps.py          # Dependency injection (get_current_user)
│   ├── core/
│   │   ├── config.py        # Settings from .env
│   │   ├── database.py      # SQLAlchemy setup
│   │   ├── security.py      # JWT + password hashing
│   │   ├── cors.py          # CORS middleware
│   │   └── redis.py         # Redis client
│   ├── models/              # SQLAlchemy models
│   ├── schemas/             # Pydantic schemas
│   ├── services/            # Business logic
│   └── main.py              # FastAPI app entry
├── alembic/                 # Database migrations
├── .env                     # Environment variables
└── pyproject.toml           # Dependencies (uv)
```

### Frontend Structure
```
frontend/
├── src/
│   ├── components/          # Reusable UI components
│   ├── pages/               # Page components
│   │   ├── Auth/            # Login/Register
│   │   ├── Discover/        # Swipe feed
│   │   ├── Matches/         # Matches list
│   │   └── Chat/            # Chat interface
│   ├── lib/
│   │   └── api/             # API client & functions
│   │       ├── client.ts    # Base API client (fetch wrapper)
│   │       ├── auth.ts      # Auth API calls
│   │       ├── pets.ts      # Pet API calls
│   │       └── tokens.ts    # Token storage
│   ├── store/               # Zustand state stores
│   │   └── useAuthStore.ts  # Auth state
│   └── App.tsx              # Router setup
├── .env                     # Environment variables
└── package.json             # Dependencies (npm)
```

## API Endpoints

### Authentication
| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| POST | `/auth/register` | Create new account | Public |
| POST | `/auth/login` | Login & get tokens | Public |
| POST | `/auth/refresh` | Refresh access token | Refresh token |
| POST | `/auth/logout` | Revoke refresh token | Public |
| GET | `/auth/me` | Get current user | Required |

### Pets
| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| GET | `/pets` | Browse pets (paginated) | Public |
| POST | `/pets` | Create pet profile | Required |
| GET | `/pets/me` | Get my pets | Required |
| GET | `/pets/{id}` | Get pet details | Public |
| PATCH | `/pets/{id}` | Update pet | Owner |
| DELETE | `/pets/{id}` | Deactivate pet | Owner |

### Matches
| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| POST | `/matches/swipe` | Like or skip a pet | Required |
| GET | `/matches/my-matches` | Get all matches | Required |
| GET | `/matches/likes-received` | See who liked you | Required |
| GET | `/matches/notifications` | Get notifications | Required |
| PATCH | `/matches/notifications/read` | Mark as read | Required |

### Photos
| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| POST | `/pets/{id}/photos/presign` | Get upload URL | Owner |
| POST | `/pets/{id}/photos` | Confirm upload | Owner |
| PATCH | `/pets/{id}/photos/{photo_id}/primary` | Set primary photo | Owner |
| DELETE | `/pets/{id}/photos/{photo_id}` | Delete photo | Owner |

## Environment Variables

### Backend (.env)
```env
# Database
DATABASE_URL=postgresql://...

# Redis
REDIS_URL=rediss://...

# JWT
JWT_SECRET=your-secret-key
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

# CORS
CORS_ORIGINS=http://localhost:5173
FRONTEND_URL=http://localhost:5173

# Cloudflare R2
R2_ACCOUNT_ID=...
R2_ACCESS_KEY_ID=...
R2_SECRET_ACCESS_KEY=...
R2_BUCKET_NAME=...
R2_PUBLIC_BASE_URL=...

# App
APP_ENV=development
```

### Frontend (.env)
```env
# Backend API
VITE_API_URL=http://localhost:8000

# WebSocket (for future chat)
VITE_WS_URL=ws://localhost:8000
```

## Security Features

### JWT Authentication
- **Access Token**: Short-lived (30 min), used for API requests
- **Refresh Token**: Long-lived (7 days), used to get new access tokens
- **Token Rotation**: Refresh tokens are single-use (revoked after refresh)
- **Revocation**: Logout adds refresh token `jti` to Redis denylist

### CORS
- Strict origin control: only `http://localhost:5173` allowed
- Credentials support enabled for cookies/auth headers
- Preflight requests cached for 1 hour

### Password Security
- bcrypt hashing with automatic salt
- Minimum 8 characters enforced
- Passwords never logged or returned in API responses

## Data Flow Examples

### Swipe → Match Flow
```
1. User swipes right (like) on a pet
   └─> POST /matches/swipe {action: "LIKE", target_pet_id: "..."}

2. Backend checks for mutual like
   └─> Query: Has target_pet liked my_pet?

3. If mutual:
   a. Create Match record
   b. Create Notification for both users
   c. Return match data to frontend

4. Frontend shows "It's a Match!" animation
```

### Photo Upload Flow
```
1. User selects image file
   └─> POST /pets/{id}/photos/presign
   
2. Backend generates presigned R2 URL
   └─> Returns {upload_url, object_key}
   
3. Frontend uploads directly to R2
   └─> PUT to upload_url with image data
   
4. Frontend confirms upload
   └─> POST /pets/{id}/photos {object_key}
   
5. Backend verifies object exists in R2
   └─> Saves pet_photo record with public URL
```

## Port Configuration

| Service | Port | URL |
|---------|------|-----|
| Frontend (Vite) | 5173 | http://localhost:5173 |
| Backend (FastAPI) | 8000 | http://localhost:8000 |
| Swagger UI | 8000 | http://localhost:8000/docs |
| PostgreSQL (Neon) | 5432 | Remote (serverless) |
| Redis (Upstash) | 6379 | Remote (serverless) |

## Development Workflow

1. **Start Services**: Run `START_BOTH.bat`
2. **Code Changes**:
   - Backend: Auto-reload with `--reload` flag
   - Frontend: Vite hot module replacement (HMR)
3. **Test API**: Use Swagger UI at http://localhost:8000/docs
4. **Test Frontend**: Open http://localhost:5173
5. **Database Changes**:
   ```bash
   cd backend
   uv run alembic revision --autogenerate -m "description"
   uv run alembic upgrade head
   ```
6. **Push Changes**:
   - Backend: Run `backend/push-backend.bat`
   - Frontend: Run `frontend/push-frontend.bat`
