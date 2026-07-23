# 🐾 PawSome - Pet Matching Platform

A Tinder-style matchmaking app for pets where pet owners can create profiles, swipe on nearby pets, match, and chat in real-time.

## 🚀 Quick Start

### Prerequisites
- **Backend**: Python 3.12, uv package manager
- **Frontend**: Node.js 18+, npm

### Start Both Services (Easiest)
```bash
# Double-click this file or run:
START_BOTH.bat
```

This opens two terminals:
- Backend → `http://localhost:8000`
- Frontend → `http://localhost:5174`

> ⚠️ **Important**: After pulling updates, always restart the backend to load new environment variables!

### Manual Start

#### Backend
```bash
cd backend
uv sync                      # Install dependencies
uv run alembic upgrade head  # Apply migrations
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

#### Frontend
```bash
cd frontend
npm install                  # Install dependencies
npm run dev                  # Start dev server
```

### Verify Everything Works
```bash
# Run connection test
TEST_CONNECTION.bat

# Or manually:
curl http://localhost:8000/health      # Backend
curl http://localhost:5174             # Frontend
```

## 📚 Documentation

> 📁 **Documentation is organized in two folders**: [See Documentation Map](DOCUMENTATION_MAP.md)  
> - `/docs` = Setup, troubleshooting, architecture  
> - `/backend/docs` = API specs and feature guides

### 🚀 Setup & Operations (Start Here!)
- **[Quick Start Guide](docs/QUICK_START.md)** - Setup & troubleshooting
- **[Troubleshooting Guide](docs/TROUBLESHOOTING.md)** - Detailed solutions for common issues
- **[Port Configuration](docs/PORT_CONFIGURATION.md)** - CORS and port setup reference

### 🏗️ System Design & Architecture
- **[Architecture Overview](docs/ARCHITECTURE.md)** - System design & data flow
- **[Project Spec](project.md)** - Complete feature specification
- **[Fixes Applied](docs/FIXES_APPLIED.md)** - Summary of all bug fixes

### 📡 API Documentation (Backend)
- **[API Endpoints](backend/docs/ENDPOINTS.md)** - Complete endpoint reference
- **[Chat API](backend/docs/CHAT_API.md)** - Real-time chat documentation
- **[Matching API](backend/docs/MATCHING_API.md)** - Swipe & match system
- **[Interactive API Docs](http://localhost:8000/docs)** - Swagger UI (when backend running)

> 💡 **Can't find what you need?** Check the [Documentation Map](DOCUMENTATION_MAP.md)

## 🏗️ Tech Stack

### Backend
- **Framework**: FastAPI (Python 3.12)
- **Database**: PostgreSQL (Neon - serverless)
- **Cache**: Redis (Upstash)
- **Storage**: Cloudflare R2 (S3-compatible)
- **Auth**: JWT (access + refresh tokens)
- **ORM**: SQLAlchemy 2.0 (async) + Alembic migrations

### Frontend
- **Framework**: React 18 + TypeScript
- **Build Tool**: Vite
- **State**: Zustand
- **Data Fetching**: TanStack Query
- **Styling**: Tailwind CSS + Framer Motion
- **Routing**: React Router

## 📦 Repository Structure

This is a mono-workspace with separate Git repositories:

```
PawSome/
├── backend/          → https://github.com/DebuggingDork/PawSome-Backend.git
├── frontend/         → https://github.com/DebuggingDork/PawSomeFrontend.git
├── START_BOTH.bat    → Start both services
├── QUICK_START.md    → Setup guide
├── ARCHITECTURE.md   → Technical docs
└── project.md        → Complete specification
```

## 🔑 Environment Variables

### Backend (.env)
```env
DATABASE_URL=postgresql://...
REDIS_URL=rediss://...
JWT_SECRET=your-secret-key
CORS_ORIGINS=http://localhost:5174    # Must match frontend port!
FRONTEND_URL=http://localhost:5174
R2_ACCOUNT_ID=...
R2_ACCESS_KEY_ID=...
R2_SECRET_ACCESS_KEY=...
R2_BUCKET_NAME=...
R2_PUBLIC_BASE_URL=...
```

### Frontend (.env)
```env
VITE_API_URL=http://localhost:8000
VITE_WS_URL=ws://localhost:8000
```

> 💡 **Tip**: If you get CORS errors, check that `CORS_ORIGINS` matches your frontend port! See [Port Configuration](docs/PORT_CONFIGURATION.md).

## ✨ Features

### Implemented ✅
- ✅ User authentication (register/login with JWT)
- ✅ Pet profile creation (name, species, breed, age, bio, location)
- ✅ Photo upload to Cloudflare R2 (max 5 photos, primary photo selection)
- ✅ Public pet browsing (paginated, filterable by species/breed/gender)
- ✅ Swipe system (like/skip with species validation)
- ✅ Match detection (mutual likes create matches)
- ✅ Match notifications for both users
- ✅ View matches, likes received, and swipe history

### In Progress 🚧
- 🚧 Explore feed with geo-filtering
- 🚧 Real-time chat via WebSocket
- 🚧 Online status tracking

### Planned 📋
- 📋 Google OAuth login
- 📋 AI bio generation (OpenAI)
- 📋 Push notifications (Firebase FCM)
- 📋 Block & report system
- 📋 Premium features (Super-Woof, Profile Boost)
- 📋 Playdate scheduler
- 📋 Stripe subscriptions

## 🧪 Testing

### Test Backend API
1. Start backend: `cd backend && uv run uvicorn app.main:app --reload`
2. Open Swagger UI: http://localhost:8000/docs
3. Test endpoints directly in the browser

### Test Frontend
1. Start both services: `START_BOTH.bat`
2. Open frontend: http://localhost:5173
3. Create test account and try features

## 🔄 Git Workflow

### Push Backend Changes
```bash
cd backend
git add .
git commit -m "Your message"
git push origin main
```
Or use: `backend/push-backend.bat`

### Push Frontend Changes
```bash
cd frontend
git add .
git commit -m "Your message"
git push origin main
```
Or use: `frontend/push-frontend.bat`

## 🐛 Common Issues

### "Backend not running" error
**Solution**: Start the backend server on port 8000
```bash
cd backend
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### CORS errors
**Solution**: 
1. Check backend `.env` has `CORS_ORIGINS=http://localhost:5174`
2. Verify frontend is on port 5174
3. **Restart the backend** (env changes require restart!)
4. Look for CORS log in backend terminal: `🔒 CORS enabled for origins: ['http://localhost:5174']`

See [Port Configuration Guide](docs/PORT_CONFIGURATION.md) for details.

### Port already in use
**Solution**: Find and kill the process
```bash
netstat -ano | findstr "8000"
taskkill /PID <PID> /F
```

## 📞 API Endpoints

### Authentication
- `POST /auth/register` - Create account
- `POST /auth/login` - Login & get tokens
- `POST /auth/refresh` - Refresh access token
- `POST /auth/logout` - Revoke token
- `GET /auth/me` - Get current user

### Pets
- `GET /pets` - Browse pets (public, paginated)
- `POST /pets` - Create pet profile
- `GET /pets/me` - Get my pets
- `GET /pets/{id}` - Get pet details
- `PATCH /pets/{id}` - Update pet
- `DELETE /pets/{id}` - Deactivate pet

### Matches
- `POST /matches/swipe` - Like or skip
- `GET /matches/my-matches` - List matches
- `GET /matches/likes-received` - See who liked you
- `GET /matches/notifications` - Get notifications
- `PATCH /matches/notifications/read` - Mark as read
- `GET /matches/swipe-history` - View swipe history

### Photos
- `POST /pets/{id}/photos/presign` - Get upload URL
- `POST /pets/{id}/photos` - Confirm upload
- `PATCH /pets/{id}/photos/{photo_id}/primary` - Set primary
- `DELETE /pets/{id}/photos/{photo_id}` - Delete photo

Full API docs: http://localhost:8000/docs

## 📄 License

Private project - All rights reserved

## 👥 Contributors

- DebuggingDork

---

**Need help?** Check [QUICK_START.md](docs/QUICK_START.md) for detailed setup instructions and troubleshooting.

📁 **All documentation is organized in the `/docs` folder** - See [docs/README.md](docs/README.md) for a complete index.
