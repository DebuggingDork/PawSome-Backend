# 🐾 PawSome — Project Source of Truth

> **How to use this file (for AI agents & developers):**
> This is the single source of truth for the PawSome project. It contains:
> 1. The product idea, features, and workflows (Sections 1–7)
> 2. **What has actually been built so far** (Section 8 — Progress Tracker)
> 3. **What to build next** (Section 9 — Roadmap)
> 4. Known issues and deviations from the original spec (Section 10)
>
> Before starting any new feature, read Section 8 to understand the current state of the
> codebase, then check Section 9 for what comes next. **Update Section 8 after every
> completed feature** so this file always reflects reality.

**Last updated:** 2026-06-13
**Current phase:** Phase 4 — Swipe, Match & Notifications (DONE ✅) → Next: WebSocket Chat / Explore Feed

---

## 1. Project Idea

**PawSome** is a Tinder/Bumble-style matchmaking app **for pets** (dogs first, multi-species
supported in the data model). Pet owners create profiles for their pets, swipe on nearby pets,
match on mutual likes, chat in real time, and schedule in-person playdates.

**Core loop:** Sign up → create pet profile (photos, bio, location, interests) →
swipe on a geo-filtered feed → mutual like creates a match → real-time chat →
propose a playdate → meet at the park.

**Monetization:** "Pawsome+" premium subscription via Stripe (unlimited super-woofs,
see-who-liked-you, profile boost, advanced filters, unlimited AI bio regenerations).

---

## 2. Technology Stack — Fixed Decisions

All choices below are final and production-validated. No ambiguity.

### 2.2 Backend (in progress)

| Layer | Choice | Why |
|---|---|---|
| Framework | FastAPI (Python 3.12) | Async, OpenAPI docs auto-generated |
| Package Manager | **uv** (`pyproject.toml` + `uv.lock`) | Fast, modern, lockfile-based |
| Real-time | FastAPI WebSockets | Native, no Socket.IO overhead for MVP |
| Auth | JWT (Access + Refresh) | Stateless, industry standard |
| Social Auth | Google OAuth 2.0 | Reduces friction at signup |
| Task Queue | Celery + Redis | Async: email, push, AI bio generation |
| Email | Resend API | Transactional email, great DX |
| API Docs | Auto Swagger/OpenAPI | Built into FastAPI, zero effort |

### 2.3 Database & Storage

| Layer | Choice | Why |
|---|---|---|
| Primary DB | PostgreSQL 15 (**Neon**, serverless) | Geo support, branching, free tier |
| Geo Extension | PostGIS (planned — see Section 10) | Radius search, distance queries |
| ORM | SQLAlchemy 2.0 (async) + Alembic | Async support, clean migrations |
| Cache / Sessions | Redis (Upstash) | Online status, chat cache, rate limits |
| File Storage | **Cloudflare R2** (S3-compatible, via boto3) | Free egress (big win for image feed), S3 API |
| Image Transform | Cloudflare Images/Workers (later) | Resize/WebP at edge when needed |

### 2.4 DevOps & Deployment (not started yet)

| Layer | Choice |
|---|---|
| Frontend | Vercel |
| Backend | Railway (Docker) | or render
| Database | Neon PostgreSQL |
| Redis | Upstash |
| S3 Bucket | cloudfare R2 |
| CDN | CloudFront |
| Containers | Docker + docker-compose |
| CI/CD | GitHub Actions |
| Monitoring | Sentry + Datadog Logs |

### 2.5 Third-Party APIs (Required)

- **Google Maps JS API** — nearby pets map, distance display, location picker
- **Google Places API** — address autocomplete on profile setup
- **Firebase Cloud Messaging** — push notifications (web + mobile PWA)
- **Resend** — transactional email (verify, matches, chat alerts)
- **AWS S3 + CloudFront** — photo storage and delivery
- **Stripe** — premium subscriptions (Pawsome+ tier)
- **Twilio** (optional) — SMS OTP for phone-verified profiles
- **OpenAI API (gpt-4o-mini)** — AI-generated pet bios (< $0.01 per bio)

---

## 3. System Architecture

```
┌─────────────────────────────────────────────────────────┐
│              React + Tailwind (Vercel)                  │
│  TanStack Query │ Zustand │ Framer Motion │ FCM SDK     │
└──────────────────────┬──────────────────────────────────┘
                       │ HTTPS / WSS
┌──────────────────────▼──────────────────────────────────┐
│             FastAPI (Railway / Docker)                  │
│   REST API │ WebSocket Hub │ JWT Middleware             │
│   Celery Workers (async tasks) │ OpenAPI Docs           │
└──────┬──────────┬──────────────┬──────────────┬─────────┘
       │          │              │              │
  PostgreSQL   Redis (Upstash)  AWS S3      OpenAI API
  + PostGIS    Cache/Sessions   Photos      Pet Bio Gen
  (Neon)       Online Status    CloudFront
               Chat Cache
               Rate Limits
```

### 3.1 Request Flows

| Flow | How it works |
|---|---|
| Auth | Login → FastAPI issues JWT pair → stored in httpOnly cookie + memory |
| Image Upload | Frontend → presigned S3 URL (via FastAPI) → direct upload → Lambda resize |
| Swipe | `POST /swipe` → DB write → check mutual match → emit WS event if match |
| Real-time Chat | WS connect with JWT → join room → messages via WS → persist to Postgres |
| Nearby Search | `GET /explore?lat=x&lng=y&radius=50km` → PostGIS `ST_DWithin` query |
| Notifications | Match/message → Celery task → FCM push + Resend email fallback |

---

## 4. Database Schema

### 4.1 Implemented Tables ✅ (live in Neon via Alembic)

#### `users` (`backend/app/models/user.py`)

| Column | Type | Constraints |
|---|---|---|
| `id` | UUID | PK, default `uuid4` |
| `email` | String(255) | unique, indexed, NOT NULL |
| `password_hash` | String(255) | nullable (OAuth users have no password) |
| `google_id` | String(255) | unique, nullable |
| `is_verified` | Boolean | default `False` |
| `created_at` | DateTime(tz) | server default `now()` |
| `updated_at` | DateTime(tz) | server default + onupdate |

Relationship: `pet_profiles` → one-to-many `PetProfile` (cascade delete-orphan).

#### `pet_profiles` (`backend/app/models/pet_profile.py`)

> Note: spec originally said `dog_profiles`; we generalized to **`pet_profiles` with a
> `species` enum** so the app supports dogs, cats, rabbits, birds, etc.

| Column | Type | Constraints |
|---|---|---|
| `id` | UUID | PK |
| `user_id` | UUID | FK → `users.id` ON DELETE CASCADE, indexed |
| `name` | String(100) | NOT NULL |
| `species` | Enum `pet_species` (DOG/CAT/RABBIT/BIRD/OTHER) | indexed |
| `breed` | String(100) | NOT NULL |
| `age_months` | Integer | NOT NULL |
| `gender` | String(20) | NOT NULL (male/female) |
| `bio` | Text | nullable |
| `lat` | Float | NOT NULL (plain float for now, PostGIS later) |
| `lng` | Float | NOT NULL |
| `is_active` | Boolean | default `True` |
| `created_at` / `updated_at` | DateTime(tz) | server defaults |

#### `pet_photos` (`backend/app/models/pet_photo.py`) ✅

| Column | Type | Constraints |
|---|---|---|
| `id` | UUID | PK |
| `pet_id` | UUID | FK → `pet_profiles.id` ON DELETE CASCADE, indexed |
| `object_key` | String(512) | unique, NOT NULL (R2 key: `pets/{pet_id}/{uuid}.{ext}`) |
| `url` | String(1024) | NOT NULL (public R2/CDN URL) |
| `is_primary` | Boolean | default `False` (card image in browse) |
| `sort_order` | Integer | default 0 |
| `created_at` | DateTime(tz) | server default |

Max **5 photos per pet** (enforced in routes). Relationship `PetProfile.photos` uses
`lazy="selectin"` so photos are always eagerly loaded; `PetProfile.primary_photo_url`
property surfaces the card image. Storage is **Cloudflare R2** (S3-compatible, boto3),
not AWS S3 — decision changed for free egress.

### 4.2 Implemented Tables — Phase 4 ✅

#### `swipes` (`backend/app/models/swipe.py`)

| Column | Type | Constraints |
|---|---|---|
| `id` | UUID | PK |
| `swiper_pet_id` | UUID | FK → `pet_profiles.id` ON DELETE CASCADE, indexed |
| `target_pet_id` | UUID | FK → `pet_profiles.id` ON DELETE CASCADE, indexed |
| `action` | Enum `swipe_action` (LIKE/SKIP) | NOT NULL |
| `created_at` | DateTime(tz) | server default `now()` |

**Unique constraint**: (swiper_pet_id, target_pet_id) — prevents duplicate swipes.
**Index**: `ix_swipes_target_action` (target_pet_id, action) for mutual match detection.

#### `matches` (`backend/app/models/match.py`)

| Column | Type | Constraints |
|---|---|---|
| `id` | UUID | PK |
| `pet1_id` | UUID | FK → `pet_profiles.id` ON DELETE CASCADE (smaller UUID) |
| `pet2_id` | UUID | FK → `pet_profiles.id` ON DELETE CASCADE (larger UUID) |
| `created_at` | DateTime(tz) | server default `now()` |

**Unique constraint**: (pet1_id, pet2_id) — prevents duplicate matches.
Created automatically when two pets mutually like each other.

#### `notifications` (`backend/app/models/notification.py`)

| Column | Type | Constraints |
|---|---|---|
| `id` | UUID | PK |
| `user_id` | UUID | FK → `users.id` ON DELETE CASCADE, indexed |
| `notification_type` | Enum `notification_type` (NEW_MATCH/NEW_LIKE) | NOT NULL |
| `pet_id` | UUID | FK → `pet_profiles.id` (your pet) |
| `related_pet_id` | UUID | FK → `pet_profiles.id` (other pet) |
| `match_id` | UUID | FK → `matches.id` (nullable, for NEW_MATCH) |
| `message` | Text | Human-readable notification message |
| `is_read` | Boolean | default `False` |
| `created_at` | DateTime(tz) | server default `now()` |
| `read_at` | DateTime(tz) | nullable (set when marked read) |

### 4.3 Planned Tables ⬜ (not yet created)

| Table | Key Columns | Notes |
|---|---|---|
| `messages` | id, match_id, sender_pet_id, content, msg_type, read_at, created_at | Soft delete |
| `pet_interests` | id, pet_id, interest (fetch/swim/hike etc.) | Tags for matching |
| `blocks` | id, blocker_id, blocked_id | Prevents showing in feed |
| `reports` | id, reporter_id, reported_id, reason, resolved | Moderation |
| `subscriptions` | id, user_id, plan, status, stripe_customer_id, expires_at | Premium tier |

### 4.4 PostGIS Geo Query (target, once PostGIS is enabled)

```sql
SELECT pp.* FROM pet_profiles pp
WHERE ST_DWithin(pp.location::geography, ST_Point(:lng,:lat)::geography, :radius_m)
AND pp.id NOT IN (SELECT swiped_pet_id FROM swipes WHERE swiper_pet_id = :me)
ORDER BY ST_Distance(pp.location, ST_Point(:lng,:lat)) LIMIT 20
```

---

## 5. API Endpoints

| Status | Method + Path | Description | Auth |
|---|---|---|---|
| ✅ | `GET /` | API info + links to docs/health | Public |
| ✅ | `GET /health` | Health check (returns status + env) | Public |
| ✅ | `POST /auth/register` | Create user account | Public |
| ✅ | `POST /auth/login` | Returns JWT pair | Public |
| ✅ | `POST /auth/refresh` | Refresh access token (rotates: old token revoked) | Refresh JWT |
| ✅ | `POST /auth/logout` | Revoke refresh token (Redis denylist) | Public (token in body) |
| ✅ | `GET /auth/me` | Current user info | Required |
| ⬜ | `GET /auth/google` | OAuth redirect | Public |
| ✅ | `GET /pets` | Public catalog: paginated envelope `{items,total,limit,offset}` + filters (species/breed/gender); cards carry `primary_photo_url` | Public |
| ✅ | `POST /pets` | Create pet profile (max 5/user) | Required |
| ✅ | `GET /pets/me` | List my pets (`[]` = onboarding skipped) | Required |
| ✅ | `GET /pets/{id}` | Pet detail page incl. all photos (owner sees coords when logged in) | Public |
| ✅ | `PATCH /pets/{id}` | Update profile | Owner |
| ✅ | `DELETE /pets/{id}` | Soft-delete (deactivate) profile | Owner |
| ✅ | `POST /pets/{id}/photos/presign` | Get presigned R2 PUT URL (max 5 photos/pet) | Owner |
| ✅ | `POST /pets/{id}/photos` | Confirm upload → saves row, 1st photo = primary | Owner |
| ✅ | `PATCH /pets/{id}/photos/{photo_id}/primary` | Set the card/primary photo | Owner |
| ✅ | `DELETE /pets/{id}/photos/{photo_id}` | Delete photo (R2 + DB, promotes next primary) | Owner |
| ⬜ | `GET /explore` | Swiping feed (geo-filtered) | Required |
| ⬜ | `GET /explore/map` | Nearby pets map data | Required |
| ✅ | `POST /matches/swipe` | Like / Skip (validates species, creates match if mutual) | Required |
| ✅ | `GET /matches/my-matches` | List all matches for user's pets | Required |
| ✅ | `GET /matches/likes-received` | See who liked your pet (pending matches) | Required |
| ✅ | `GET /matches/notifications` | Get match/like notifications with pet details | Required |
| ✅ | `PATCH /matches/notifications/read` | Mark notifications as read | Required |
| ✅ | `GET /matches/swipe-history` | View your pet's swipe history (likes/skips) | Required |
| ⬜ | `GET /matches/{id}/messages` | Message history | Required |
| ⬜ | `WS /ws/chat/{match_id}` | Real-time chat | JWT in header |
| ⬜ | `POST /pets/{id}/report` | Report a profile | Required |
| ⬜ | `POST /pets/{id}/boost` | Boost visibility 30 min | Premium |
| ⬜ | `POST /ai/generate-bio` | AI bio generation | Required |
| ⬜ | `POST /subscriptions/checkout` | Stripe checkout session | Required |

---

## 6. Features

### 6.1 MVP Features (build first)

- [ ] User registration + Google OAuth login
- [ ] Pet profile creation (name, species, breed, age, bio, location, photos)
- [ ] Photo upload to S3 (max 6, auto-resized via Lambda)
- [ ] Swipe UI (like / pass / super-woof) — Framer Motion card stack
- [ ] Mutual match detection + match notification
- [ ] Real-time 1:1 chat via WebSockets
- [ ] Explore feed filtered by distance, age, gender, breed
- [ ] Push notifications via Firebase FCM
- [ ] Email notifications via Resend
- [ ] Block & Report system
- [ ] Basic profile settings + account management

### 6.2 Unique Differentiator Features (post-MVP)

- **Find Compatible Playmates** — embed pet personality, breed traits, interests, and
  activity level; use vector search (pgvector in PostgreSQL) to recommend highly
  compatible pets with a compatibility score.
- **🐾 Super-Woof** — like Bumble's SuperSwipe; a highlighted like that jumps to the top
  of the other pet's feed. 3 free/day, unlimited with Pawsome+.
- **🗺️ Paw Map — Explore Nearby** — interactive Google Map showing anonymized pet
  locations nearby. Tap a pin to see the card, swipe directly from the map.
- **🤖 AI Pet Bio Generator** — one-tap GPT-4o-mini bio from breed + personality tags +
  interests. 3 free regenerations, then premium.
- **🏆 Personality Quiz** — 5-question quiz on profile setup (energy, play style,
  sociability). Result shown as a profile badge (e.g. "Zoomie King", "Cuddle Expert").
- **🎯 Compatibility Score** — % score on every profile based on breed energy match,
  age gap, interests overlap, quiz result.
- **📅 Playdate Scheduler** — propose a structured playdate in chat (park, date/time,
  duration); other user accepts/declines; Google Maps link auto-embedded. **Killer feature.**
- **🔥 Trending Breeds Near You** — home feed widget of most active breeds in the area.
- **🐕 Verified Vaccine Badge** — upload vaccination proof to S3, reviewed, badge on profile.
- **👑 Pawsome+ Premium (Stripe)** — unlimited Super-Woofs, See Who Liked You, 30-min
  Profile Boost, unlimited AI bios, read receipts, advanced filters.
- **🔔 Smart Notification Engine** — match alert (push+email), message alert (push if app
  closed), daily digest email, playdate reminder (1 hr before), weekly re-engagement.

---

## 7. Real-Time Architecture (WebSockets)

### Events

| Event | Direction | Payload |
|---|---|---|
| `chat.message` | Server → Client | match_id, sender_id, content, timestamp |
| `chat.typing` | Client → Server | match_id, is_typing |
| `chat.read` | Client → Server | message_id, match_id |
| `match.new` | Server → Client | match object, pet profile |
| `user.online` | Server → Client | pet_id, status |
| `boost.active` | Server → Client | pet_id, expires_at |

### Redis for Real-Time State

```
HSET online_users {pet_id} {timestamp}      // track online status
EXPIRE online_users:{pet_id} 300            // auto-expire after 5 min
LPUSH chat_cache:{match_id} {message}       // fast message reads
SET boost:{pet_id} 1 EX 1800                // 30-min boost flag
```

> ⚠️ Use **Redis Pub/Sub** for chat fan-out from day one (Backend 1 ↔ Redis ↔ Backend 2),
> so messages never get stuck on a single instance when scaling horizontally.

---

## 8. ✅ PROGRESS TRACKER — What Has Been Completed

> **This section reflects the actual state of the codebase. Keep it updated.**

### 8.1 Repository layout (current, actual)

```
PawSome/
├── project.md                  ← this file (source of truth)
├── .gitignore                  ← Python, venv, .env, IDE ignores
└── backend/
    ├── pyproject.toml          ← uv-managed dependencies
    ├── uv.lock
    ├── .python-version         ← 3.12
    ├── .env.example            ← template for required env vars
    ├── alembic.ini
    ├── alembic/
    │   ├── env.py              ← async migrations, wired to app settings + Base
    │   └── versions/
    │       └── e49968edd5ac_create_users_and_pet_profiles.py
    └── app/
        ├── main.py             ← FastAPI app, CORS, auth + pets routers, GET / and /health
        ├── api/
        │   ├── deps.py         ← get_current_user, require_active_pet (pet gate)
        │   └── routes/
        │       ├── auth.py     ← register, login, refresh, logout, me
        │       ├── pets.py     ← pet CRUD + public paginated catalog
        │       └── pet_photos.py ← R2 presign/confirm/set-primary/delete (max 5)
        ├── core/
        │   ├── config.py       ← pydantic-settings Settings class
        │   ├── cors.py         ← setup_cors(app) middleware helper
        │   ├── database.py     ← async engine, session factory, get_db()
        │   ├── redis.py        ← async Redis client (Upstash) + get_redis()
        │   └── security.py     ← bcrypt + JWT utilities (tokens carry jti)
        ├── models/
        │   ├── __init__.py     ← exports User, PetProfile, PetPhoto
        │   ├── user.py         ← users table
        │   ├── pet_profile.py  ← pet_profiles table + PetSpecies enum
        │   └── pet_photo.py    ← pet_photos table (R2 keys + URLs)
        ├── services/
        │   └── r2.py           ← Cloudflare R2: presign PUT, head, delete
        └── schemas/
            ├── auth.py         ← Pydantic auth schemas
            └── pet.py          ← pet + photo + pagination schemas
```

`frontend/` does **not exist yet**. No Docker, no CI, no tests yet.

### 8.2 Done in detail

| # | Item | File(s) | Details |
|---|---|---|---|
| 1 | **Project bootstrapped** | `backend/pyproject.toml`, `uv.lock` | uv package manager, Python 3.12. Deps: `fastapi[standard]`, `sqlalchemy>=2.0`, `asyncpg`, `alembic`, `pydantic-settings`, `python-jose[cryptography]`, `passlib[bcrypt]`, `bcrypt<4`, `email-validator`, `redis`, `python-dotenv`. FastAPI CLI entry: `app.main:app`. |
| 2 | **FastAPI app shell** | `app/main.py` | App created with title/description. `GET /` (API info) and `GET /health` (status + env). **No routers registered yet, no CORS middleware yet.** |
| 3 | **Settings management** | `app/core/config.py` | `Settings` (pydantic-settings) loads from `.env`: `app_env`, `database_url`, `redis_url`, `jwt_secret`, `jwt_algorithm` (HS256), `access_token_expire_minutes` (30), `refresh_token_expire_days` (7), `cors_origins`. Includes `_normalize_database_url()` which converts `postgresql://` → `postgresql+asyncpg://` and strips `sslmode` into `connect_args["ssl"]=True` — **required for the Neon connection string, do not remove**. |
| 4 | **Async database layer** | `app/core/database.py` | `Base` (DeclarativeBase), async engine (`echo=True` in dev), `AsyncSessionLocal` session factory, `get_db()` async dependency ready for route injection. Connected to **Neon Postgres** (serverless). |
| 5 | **Security utilities** | `app/core/security.py` | `hash_password()` / `verify_password()` (passlib bcrypt); `create_access_token()` / `create_refresh_token()` (python-jose JWT with `type` claim "access"/"refresh"); `decode_token()`; `verify_token(token, expected_type) -> UUID`. **Fully written, not yet consumed by any route.** |
| 6 | **User model** | `app/models/user.py` | `users` table — see Section 4.1. Password nullable to support Google-OAuth-only users. |
| 7 | **PetProfile model** | `app/models/pet_profile.py` | `pet_profiles` table with `PetSpecies` enum — see Section 4.1. Generalized from spec's dog-only design. |
| 8 | **Alembic migrations** | `alembic/`, `alembic.ini` | Async migration setup; `env.py` imports `app.models` and uses `settings.database_url`. One applied migration `e49968edd5ac` creates `users` + `pet_profiles` with indexes. (A duplicate migration was created earlier and removed — see git history.) |
| 9 | **Auth schemas** | `app/schemas/auth.py` | `RegisterRequest`, `LoginRequest`, `RefreshRequest`, `TokenResponse`, `UserResponse` (with `from_attributes`). Schema bugs from Section 10.3 are fixed. |
| 10 | **Env template** | `backend/.env.example` | `DATABASE_URL`, `REDIS_URL`, `JWT_SECRET`, `JWT_ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES`, `REFRESH_TOKEN_EXPIRE_DAYS`, `APP_ENV`, `CORS_ORIGINS`. (More vars to add as integrations land — see Section 11.) |
| 11 | **CORS middleware** | `app/core/cors.py`, `app/main.py` | `setup_cors(app)` registers `CORSMiddleware` with `settings.cors_origins`. |
| 12 | **Auth API routes** | `app/api/routes/auth.py` | `POST /auth/register` (409 on dup email), `POST /auth/login`, `POST /auth/refresh`, `GET /auth/me`. Router registered in `main.py`. |
| 13 | **Auth dependency** | `app/api/deps.py` | `get_current_user`: HTTPBearer → `verify_token` (access) → loads `User` or 401. |
| 14 | **Pet schemas** | `app/schemas/pet.py` | `PetCreate` (validated: age > 0, gender literal, lat/lng ranges), `PetUpdate` (all optional), `PetResponse` (owner view, incl. coords), `PetPublicResponse` (browse view, **no lat/lng** per Section 10.1). |
| 15 | **Pets API routes** | `app/api/routes/pets.py` | `POST /pets` (max 5 active pets/user), `GET /pets/me` (empty list = onboarding skipped), `GET /pets/{id}` (owner gets full view, others get public view), `PATCH /pets/{id}` + `DELETE /pets/{id}` (owner-only; delete is soft → `is_active=False`). Router registered in `main.py`. |
| 16 | **Pet gate dependency** | `app/api/deps.py` | `require_active_pet`: loads user's first active pet or raises **403 `PET_PROFILE_REQUIRED`**. Not used by pets routes; for Phase 4/5 (swipe, chat) so pet-less users can browse but get a clean error the frontend turns into a "register a pet" prompt. |
| 17 | **Public pet catalog** | `app/api/routes/pets.py` | `GET /pets` — fully public (no auth), paginated (`limit`≤100/`offset`), filters: `species`, `gender`, `breed` (case-insensitive substring). Returns `PetPublicResponse` (no coords). `GET /pets/{id}` is also public via `get_current_user_optional` (owner logged in → full view). |
| 18 | **Logout + token revocation** | `app/api/routes/auth.py`, `app/core/redis.py`, `app/core/security.py` | JWTs now carry a `jti` claim. `POST /auth/logout` denylists the refresh token's jti in Redis (TTL = remaining token life). `POST /auth/refresh` rejects revoked tokens **and rotates** (old refresh token revoked on use — single-use). Tokens without `jti` (pre-change) are rejected on refresh; users just re-login. |
| 19 | **PetPhoto model + migration** | `app/models/pet_photo.py`, `alembic/versions/b5e938cdcb09_*` | `pet_photos` table (Section 4.1). Separate table (not a column on pets) so the photo limit is just a config change. Applied to Neon. |
| 20 | **Cloudflare R2 storage service** | `app/services/r2.py`, `app/core/config.py` | boto3 S3 client pointed at `https://{account}.r2.cloudflarestorage.com`. Presigned PUT (10-min expiry, content type pinned to jpeg/png/webp), head (size check, 10 MB max), delete, public URL builder. R2 env vars optional — photo endpoints return **503** until configured. Blocking boto3 calls wrapped in `run_in_threadpool`. |
| 21 | **Photo upload routes** | `app/api/routes/pet_photos.py` | Presign → client PUTs directly to R2 → confirm (verifies object exists, key ownership `pets/{pet_id}/` prefix, size, 5-photo cap; first photo auto-primary). Set-primary + delete (R2 object removed, next photo promoted if primary deleted). All owner-only via shared `get_owned_pet` dependency (moved to `app/api/deps.py`). |
| 22 | **Paginated browse** | `app/api/routes/pets.py` | `GET /pets` now returns `{items, total, limit, offset}`; items include `primary_photo_url` + `photos`. |
| 23 | **Swipe, Match & Notification models** | `app/models/swipe.py`, `app/models/match.py`, `app/models/notification.py` | Three new models for matching system. Swipe records every like/skip with species validation. Match created on mutual like. Notifications sent to both users on match. Migration `08edcca036c1` creates all three tables with proper indexes and constraints. |
| 24 | **Matching API routes** | `app/api/routes/matches.py` | `POST /matches/swipe` (validates species match, detects mutual likes, creates match + notifications), `GET /matches/my-matches` (list user's matches), `GET /matches/likes-received` (see who liked your pet), `GET /matches/notifications` (get notifications with pet details), `PATCH /matches/notifications/read` (mark as read), `GET /matches/swipe-history` (view your swipe history). All routes enforce species matching (dog-to-dog only, etc.). Router registered in `main.py`. |
| 25 | **Match schemas** | `app/schemas/match.py` | Request/response schemas for swipe actions, matches, and notifications. Includes detailed notification responses with pet info for UI display. |

### 8.3 How to run the backend (current)

```bash
cd backend
uv sync                      # install deps
cp .env.example .env         # then fill in Neon DATABASE_URL, JWT_SECRET, etc.
uv run alembic upgrade head  # apply migrations to Neon
uv run fastapi dev           # start dev server → http://localhost:8000/docs
```

---

## 9. 🗺️ ROADMAP — What To Build Next (in order)

### Phase 1 — Backend Foundation (current, ~80% done)
- [x] uv project + dependencies
- [x] FastAPI shell + health endpoint
- [x] Settings (pydantic-settings) + Neon DB connection
- [x] Async SQLAlchemy + Alembic
- [x] User & PetProfile models + first migration
- [x] JWT + password security utilities
- [x] Auth Pydantic schemas
- [x] Fix auth schema bugs (Section 10.3)
- [x] Register CORS middleware in `main.py` (`app/core/cors.py`)

### Phase 2 — Auth API (done except Google OAuth)
- [x] `app/api/routes/auth.py`: `POST /auth/register`, `POST /auth/login`, `POST /auth/refresh`, `GET /auth/me`
- [x] `POST /auth/logout` with Redis jti denylist + refresh-token rotation
- [x] `get_current_user` dependency (reads Bearer token → `verify_token` → loads `User` via `get_db`)
- [x] `get_current_user_optional` dependency (public endpoints with owner-aware responses)
- [x] Register the auth router in `main.py`
- [ ] Google OAuth (`GET /auth/google` + callback) — needs `GOOGLE_CLIENT_ID/SECRET`

### Phase 3 — Pet Profiles API (CRUD done)
- [x] `app/schemas/pet.py` (create/update/response schemas; public response hides coords)
- [x] `app/api/routes/pets.py`: `POST /pets`, `GET /pets/me`, `GET /pets/{id}`, `PATCH /pets/{id}`, `DELETE /pets/{id}` (owner-only, soft delete)
- [x] `GET /pets` public catalog (no auth) with paginated envelope (`{items,total,limit,offset}`) + species/breed/gender filters
- [x] `require_active_pet` gate dependency in `app/api/deps.py` (403 `PET_PROFILE_REQUIRED` — apply to swipe/chat routes in Phases 4–5)
- [x] `pet_photos` model + migration; **Cloudflare R2** presigned upload service (`app/services/r2.py`) + photo routes (presign/confirm/set-primary/delete, max 5)
- [ ] Fill in R2 env vars (`R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET_NAME`, `R2_PUBLIC_BASE_URL`) — photo endpoints 503 until then

### Phase 4 — Swipe, Match & Explore (Matching done ✅, Explore feed pending)
- [x] `swipes` + `matches` + `notifications` models + migration `08edcca036c1`
- [x] `POST /matches/swipe` with mutual-match detection + species validation (inter-species only)
- [x] `GET /matches/my-matches` — list all matches for user's pets
- [x] `GET /matches/likes-received` — see who liked your pet (potential matches)
- [x] `GET /matches/notifications` — get match notifications with pet details
- [x] `PATCH /matches/notifications/read` — mark notifications as read
- [x] `GET /matches/swipe-history` — view swipe history (likes/skips with pet details)
- [x] Notification system: both users get notified on match with message and pet info
- [ ] `GET /explore` geo-filtered feed (start with lat/lng haversine; upgrade to PostGIS)
- [ ] Enable PostGIS on Neon + migrate `lat`/`lng` → geography `location` column

### Phase 5 — Real-time Chat
- [ ] `messages` model + migration
- [ ] `WS /ws/chat/{match_id}` with JWT auth, Redis Pub/Sub fan-out
- [ ] `GET /matches/{id}/messages` history
- [ ] Online status in Redis

### Phase 6 — Frontend (React + Vite)
- [ ] Scaffold `frontend/` per structure in Section 12
- [ ] Auth pages + Axios JWT-refresh interceptor + Zustand auth store
- [ ] Onboarding (pet profile setup), Explore (swipe cards), Matches, Chat, Profile pages

### Phase 7 — Differentiators & Premium
- [ ] AI bio generation (OpenAI), Block/Report, notifications (FCM + Resend via Celery),
      Super-Woof, Boost, Compatibility score, Playdate scheduler, Stripe subscriptions

### Phase 8 — DevOps & Hardening
- [ ] Dockerfile + docker-compose, GitHub Actions CI, tests (pytest), Sentry,
      deploy backend to Railway + frontend to Vercel

---

## 10. ⚠️ Known Issues & Decisions To Address

### 10.1 Location Privacy (design decision — must implement)
Never expose exact pet coordinates. Store exact coordinates in the DB, but **return fuzzed
coordinates to the frontend** and show approximate locations only.

### 10.2 Redis Pub/Sub for Chat (design decision — must implement)
Don't wait for scaling problems. Route all WS chat messages through Redis Pub/Sub so
users connected to different backend instances still receive messages.

### 10.3 Current code bugs
All previously listed auth-schema bugs are fixed (`min_length=8, max_length=128`, unused
import removed, `app/schemas/__init__.py` added). No known open bugs at the moment.

### 10.4 Deviations from original spec (intentional, keep)
- Tables are `pet_profiles` (multi-species via `PetSpecies` enum), not `dog_profiles`.
  All future tables should follow the `pet_` naming (e.g. `pet_photos`, `swiper_pet_id`).
- Location is plain `lat`/`lng` floats for now; PostGIS upgrade is scheduled in Phase 4.

---

## 11. Environment Variables

### Backend `.env` — current ✅
```
DATABASE_URL                  postgresql://... (Neon — auto-normalized to asyncpg)
REDIS_URL                     redis://... (Upstash)
JWT_SECRET                    random 32-byte hex string
JWT_ALGORITHM                 HS256
ACCESS_TOKEN_EXPIRE_MINUTES   30
REFRESH_TOKEN_EXPIRE_DAYS     7
APP_ENV                       development | production
CORS_ORIGINS                  http://localhost:5173
```

### Backend `.env` — to add later ⬜ (when each integration lands)
```
GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET   Google Cloud Console (Phase 2)
R2_ACCOUNT_ID                             Cloudflare dashboard (Phase 3 — needed NOW for photos)
R2_ACCESS_KEY_ID / R2_SECRET_ACCESS_KEY   R2 API token (Phase 3 — needed NOW for photos)
R2_BUCKET_NAME                            e.g. pawsome-photos (Phase 3 — needed NOW for photos)
R2_PUBLIC_BASE_URL                        r2.dev public URL or custom domain (Phase 3)
OPENAI_API_KEY                            AI bio generation (Phase 7)
RESEND_API_KEY                            transactional email (Phase 7)
FIREBASE_SERVICE_ACCOUNT                  JSON key for FCM (Phase 7)
STRIPE_SECRET_KEY / STRIPE_WEBHOOK_SECRET Stripe dashboard (Phase 7)
```

### Frontend `.env` ⬜ (Phase 6)
```
VITE_API_URL                  http://localhost:8000 (dev)
VITE_WS_URL                   ws://localhost:8000 (dev)
VITE_GOOGLE_MAPS_KEY          Google Cloud Console
VITE_FIREBASE_CONFIG          Firebase web config JSON
VITE_STRIPE_PUBLISHABLE_KEY   Stripe dashboard
```

---

## 12. Target Project Structure (planned)

### Backend (FastAPI) — items marked ✅ exist today

```
backend/app/
├── main.py                ✅ (CORS + auth/pets routers registered)
├── api/routes/
│   ├── auth.py            ✅ JWT done (Google OAuth ⬜)
│   ├── pets.py            ✅ Profile CRUD + photos ✅
│   ├── pet_photos.py      ✅ R2 presign/confirm/set-primary/delete
│   ├── matches.py         ✅ Swipe + match detection + notifications
│   ├── chat.py            ⬜ WS endpoint + history
│   ├── explore.py         ⬜ Geo-filtered feed
│   ├── ai.py              ⬜ Bio generation
│   └── subscriptions.py   ⬜ Stripe webhooks + checkout
├── models/
│   ├── user.py            ✅
│   ├── pet_profile.py     ✅
│   ├── pet_photo.py       ✅
│   ├── swipe.py           ✅
│   ├── match.py           ✅
│   ├── notification.py    ✅
│   └── (message, pet_interest, block, report, ...) ⬜
├── schemas/
│   ├── auth.py            ✅
│   ├── pet.py             ✅
│   ├── match.py           ✅
│   └── (chat, explore, ...) ⬜
├── services/
│   ├── r2.py              ✅ Cloudflare R2 presigned URLs + delete
│   ├── notifications.py   ⬜ FCM + Resend
│   ├── matching.py        ⬜ Compatibility score logic
│   └── ai_bio.py          ⬜ OpenAI integration
├── tasks/                 ⬜ Celery async tasks
└── core/
    ├── config.py          ✅
    ├── security.py        ✅
    └── database.py        ✅
```

### Frontend (React + Vite) — all ⬜

```
frontend/src/
├── components/   SwipeCard, MatchModal, ChatWindow, PawMap, ProfileCard
├── pages/        Onboarding, Explore, Matches, Chat, Profile, Premium
├── hooks/        useSwipe, useChat, useLocation
└── store/        authStore, chatStore
```
