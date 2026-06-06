🐾 PawSome
1. Technology Stack — Fixed Decisions
All choices below are final and production-validated. No ambiguity.

1.1 Frontend
Layer Choice Why
UI Framework React 18 + Vite Fastest DX, ecosystem, recruiter-ready
Routing React Router v6 Standard, nested routes for auth flows
Styling Tailwind CSS v3 Rapid modern UI, no CSS files
State (Server) TanStack Query v5 Caching, background sync, no Redux
State (UI) Zustand Lightweight, replaces Context for
globals
HTTP Client Axios Interceptors for JWT refresh
Maps Google Maps JS API Distance, nearby pets, explore map
Animations Framer Motion Swipe gestures, card stack
Push (Web) Firebase SDK (FCM) Browser push notifications
1.2 Backend
Layer Choice Why
Framework FastAPI (Python 3.12) Async, OpenAPI docs auto-generated
Real-time FastAPI WebSockets Native, no Socket.IO overhead for MVP
Auth JWT (Access + Refresh) Stateless, industry standard
Social Auth Google OAuth 2.0 Reduces friction at signup
Task Queue Celery + Redis Async: email, push, AI bio generation
Email Resend API Transactional email, great DX
API Docs Auto Swagger/OpenAPI Built into FastAPI, zero effort
1.3 Database & Storage
Layer Choice Why
Primary DB PostgreSQL 15 (Neon) Serverless, geo support, free tier
Geo Extension PostGIS Radius search, distance queries
ORM SQLAlchemy 2.0 + Alembic Async support, clean migrations
Cache / Sessions Redis (Upstash) Online status, chat cache, rate limits
File Storage AWS S3 + CloudFront Industry standard, cheap, scalable
Image Transform AWS Lambda + Sharp Auto-resize, WebP conversion on
upload
1.4 DevOps & Deployment
Layer Choice Why
Frontend Vercel Zero config, edge network, free tier
Backend Railway Docker support, easy scaling, logs
Database Neon PostgreSQL Serverless Postgres, branching for dev
Redis Upstash Serverless Redis, free tier
S3 Bucket AWS S3 (us-east-1) Standard, cheap ($0.023/GB)
CDN CloudFront Serve images globally fast
Containers Docker + docker-compose Local dev, production parity
CI/CD GitHub Actions Lint, test, deploy on push
Monitoring Sentry + Datadog Logs Error tracking + observability
1.5 Third-Party APIs (Required)
Google Maps JS API Nearby pets map, distance display, location picker
Google Places API Address autocomplete on profile setup
Firebase Cloud Messaging Push notifications (web + mobile PWA)
Resend Transactional email (verify, matches, chat alerts)
AWS S3 + CloudFront Photo storage and delivery
Stripe Premium subscriptions (Pawsome+ tier)
Twilio (optional) SMS OTP for phone-verified profiles
OpenAI API (gpt-4o-mini) AI-generated dog bios (< $0.01 per bio)
2. System Architecture
ARCHITECTURE OVERVIEW
┌─────────────────────────────────────────────────────────┐
│ React + Tailwind (Vercel) │
│ TanStack Query │ Zustand │ Framer Motion │ FCM SDK │
└──────────────────────┬──────────────────────────────────┘
│ HTTPS / WSS
┌──────────────────────▼──────────────────────────────────┐
│ FastAPI (Railway / Docker) │
│ REST API │ WebSocket Hub │ JWT Middleware │
│ Celery Workers (async tasks) │ OpenAPI Docs │
└──────┬──────────┬──────────────┬──────────────┬─────────┘
│ │ │ │
PostgreSQL Redis (Upstash) AWS S3 OpenAI API
+ PostGIS Cache/Sessions Photos Dog Bio Gen
(Neon) Online Status CloudFront
Chat Cache
Rate Limits
2.1 Request Flow
Auth Flow Login → FastAPI issues JWT pair → stored in httpOnly cookie +
memory
Image Upload Frontend → presigned S3 URL (via FastAPI) → direct upload →
Lambda resize
Swipe Action POST /swipe → DB write → check mutual match → emit WS event if
match
Real-time Chat WS connect with JWT → join room → messages via WS → persist to
Postgres
Nearby Search GET /explore?lat=x&lng=y&radius=50km → PostGIS ST_DWithin
query
Notifications Match/message → Celery task → FCM push + Resend email fallback
3. Database Schema (Key Tables)
Core Tables
Table Key Columns Notes
users id, email, password_hash, google_id,
is_verified, created_at
Owns dog profiles
dog_profiles id, user_id, name, breed, age_months,
gender, bio, lat, lng, is_active
PostGIS Point for location
dog_photos id, dog_id, s3_key, cdn_url, is_primary,
order
Max 6 photos
swipes id, swiper_dog_id, swiped_dog_id,
direction (like/pass), created_at
Unique constraint both IDs
matches id, dog1_id, dog2_id, matched_at,
is_active
Created when mutual like
messages id, match_id, sender_dog_id, content,
msg_type, read_at, created_at
Soft delete
dog_interests id, dog_id, interest (fetch/swim/hike
etc)
Tags for matching
blocks id, blocker_id, blocked_id Prevents showing in feed
reports id, reporter_id, reported_id, reason,
resolved
Moderation
subscriptions id, user_id, plan, status,
stripe_customer_id, expires_at
Premium tier
PostGIS Geo Query Example
SELECT dp.* FROM dog_profiles dp
WHERE ST_DWithin(dp.location::geography, ST_Point(:lng,:lat)::geography, :radius_m)
AND dp.id NOT IN (SELECT swiped_dog_id FROM swipes WHERE swiper_dog_id = :me)
ORDER BY ST_Distance(dp.location, ST_Point(:lng,:lat)) LIMIT 20
4. API Endpoints (Core)
Method + Path Description Auth
POST /auth/register Create user account Public
POST /auth/login Returns JWT pair Public
POST /auth/refresh Refresh access token Refresh JWT
GET /auth/google OAuth redirect Public
POST /dogs/ Create dog profile Required
GET /dogs/{id} Get dog profile Required
PATCH /dogs/{id} Update profile Owner
POST /dogs/{id}/photos Upload photo (presigned) Owner
GET /explore Swiping feed (geo-filtered) Required
POST /swipe Like or Pass a dog Required
GET /matches List all matches Required
WS /ws/chat/{match_id} Real-time chat JWT in header
GET
/matches/{id}/messages
Message history Required
POST /dogs/{id}/report Report a profile Required
POST /dogs/{id}/boost Boost visibility 30min Premium
GET /explore/map Nearby dogs map data Required
POST /ai/generate-bio AI bio generation Required
POST
/subscriptions/checkout
Stripe checkout session Required
5. Features — MVP vs Unique
5.1 MVP Features (Build First)
Core MVP — 2 Weeks
User registration + Google OAuth login
Dog profile creation (name, breed, age, bio, location, photos)
Photo upload to S3 (max 6, auto-resized via Lambda)
Swipe UI (like / pass / super-woof) — Framer Motion card stack
Mutual match detection + match notification
Real-time 1:1 chat via WebSockets
Explore feed filtered by distance, age, gender, breed
Push notifications via Firebase FCM
Email notifications via Resend
Block & Report system
Basic profile settings + account management
5.2 Unique Features — PawMeet Differentiators
These features don't exist in any pet app today. They're your competitive moat.

Find Compatible Playmates
Instead of simple filters :

embed dog personality
breed traits
interests
activity level
Use vector search (pgvector in PostgreSQL) to recommend highly compatible dogs.
Just like LIK movie thing (compatibility score)

🐾 Super-Woof
Like Bumble's SuperSwipe — a highlighted like that jumps to the top of the other dog's feed. 3 free/day, unlimited
with Pawsome+ subscription.

🗺️ Paw Map — Explore Nearby
An interactive map (Google Maps) showing anonymized dog locations nearby. Tap a dog pin to see their card. Swipe
directly from the map. No other pet app has this.

🤖 AI Dog Bio Generator
One-tap GPT-4o-mini bio generation. User fills breed, personality tags, interests → API call → returns witty, on-brand
bio. Users can regenerate up to 3 times free, then premium. Differentiator: feels magical, solves writer's block.

🏆 Doggo Personality Quiz
5 - question personality quiz on profile setup (energy level, play style, sociability). Results shown on profile as a badge
(e.g. 'Zoomie King', 'Cuddle Expert'). Better matches based on compatibility scores.

🎯 Compatibility Score
When viewing a dog's profile, show a % compatibility score based on: breed energy match, age gap, interests overlap,
personality quiz result. Makes swiping feel intentional, not random.

📅 Playdate Scheduler
After matching, users can propose a playdate directly in chat with a structured form: park name, date/time, duration.
The other user accepts/declines. Google Maps link auto-embedded. This is the killer feature — Bumble has Date Mode,
we have Playdate Mode.

🔥 Trending Breeds Near You
Home feed widget showing what breeds are most active in your area this week. Social proof + discovery. Drives re-
engagement.

👑 Pawsome+ Premium Tier (via Stripe)
Unlimited Super-Woofs 3/day free → unlimited premium
See Who Liked You Like Bumble Gold, visible swiper list
Profile Boost 30 min top-of-feed visibility
AI Bio Regenerations 3 free → unlimited
Read Receipts See when messages are read
Advanced Filters Vaccination status, size, temperament
🐕 Verified Vaccine Badge
Users upload proof of vaccination (image to S3). Manually reviewed or AI-checked. Verified badge shown on profile.
Differentiator: Safety-first trust signal — no other pet app does this. Parents trust it more.

🔔 Smart Notification Engine
Match alert Push + email immediately
Message alert Push if app is closed
Daily Digest Email: 'X dogs liked you today'
Playdate Reminder Push 1hr before scheduled playdate
Re-engagement '3 new dogs near you this week' (weekly)
6. Real-Time Architecture (WebSockets)
Events
Event Direction Payload
chat.message Server → Client match_id, sender_id, content,
timestamp
chat.typing Client → Server match_id, is_typing
chat.read Client → Server message_id, match_id
match.new Server → Client match object, dog profile
user.online Server → Client dog_id, status
boost.active Server → Client dog_id, expires_at
Redis for Real-Time State
HSET online_users {dog_id} {timestamp} // track online status
EXPIRE online_users:{dog_id} 300 // auto-expire after 5min
LPUSH chat_cache:{match_id} {message} // fast message reads
SET boost:{dog_id} 1 EX 1800 // 30min boost flag
7. Project Structure
Frontend (React + Vite)
src/
components/
SwipeCard.jsx # Framer Motion swipe card
MatchModal.jsx # Match celebration overlay
ChatWindow.jsx # Real-time chat UI
PawMap.jsx # Google Maps explore view
ProfileCard.jsx # Dog profile display
pages/
Onboarding.jsx # Signup + dog profile setup
Explore.jsx # Swiping feed
Matches.jsx # Match list
Chat.jsx # Chat page
Profile.jsx # Own profile management
Premium.jsx # Subscription page
hooks/
useSwipe.js # Swipe logic + TanStack Query
useChat.js # WebSocket hook
useLocation.js # Geolocation hook
store/
authStore.js # Zustand auth state
chatStore.js # Active chats state
Backend (FastAPI)
app/
api/routes/
auth.py # JWT + Google OAuth
dogs.py # Profile CRUD
swipe.py # Like/Pass + match detection
matches.py # Match list + details
chat.py # WS endpoint + history
explore.py # Geo-filtered feed
ai.py # Bio generation
subscriptions.py # Stripe webhooks + checkout
models/ # SQLAlchemy models
schemas/ # Pydantic v2 schemas
services/
s3.py # Presigned URL generation
notifications.py # FCM + Resend
matching.py # Compatibility score logic
ai_bio.py # OpenAI integration
tasks/ # Celery async tasks
core/
config.py # Settings (pydantic-settings)
security.py # JWT utils
database.py # Async SQLAlchemy engine
9. Environment Variables
Backend (.env)
DATABASE_URL postgresql+asyncpg://... (Neon connection string)
REDIS_URL redis://... (Upstash URL)
JWT_SECRET Random 32-byte hex string
GOOGLE_CLIENT_ID / SECRET From Google Cloud Console
AWS_ACCESS_KEY_ID IAM user with S3 + CloudFront access
AWS_SECRET_ACCESS_KEY IAM secret
S3_BUCKET_NAME e.g. pawmeet-photos-prod
CLOUDFRONT_DOMAIN e.g. d1abc.cloudfront.net
OPENAI_API_KEY For AI bio generation
RESEND_API_KEY For transactional email
FIREBASE_SERVICE_ACCOUNT JSON key for FCM
STRIPE_SECRET_KEY From Stripe dashboard
STRIPE_WEBHOOK_SECRET From Stripe CLI / dashboard
Frontend (.env)
VITE_API_URL https://api.pawmeet.app
VITE_WS_URL wss://api.pawmeet.app
VITE_GOOGLE_MAPS_KEY From Google Cloud Console
VITE_FIREBASE_CONFIG Firebase web config JSON
VITE_STRIPE_PUBLISHABLE_KEY From Stripe dashboard
ISSUE TO ADDRESS
Location Privacy
Never expose exact dog coordinates.
Instead:
store exact coordinates in PostGIS
return fuzzed coordinates to frontend
show approximate locations only
The review is absolutely right here.
Redis Pub/Sub for Chat
Don't wait until scaling problems appear.
Current:
User A -> Backend 1
User B -> Backend 2
Add:
Backend 1 <-> Redis Pub/Sub <-> Backend 2
This prevents messages from getting stuck on different instances.