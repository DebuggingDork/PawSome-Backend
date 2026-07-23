# 🚀 PawSome Quick Start Guide

## The Problem You Were Having

Your backend APIs work perfectly when tested via `/docs` (Swagger UI), but the frontend application couldn't connect to the backend. This was because:

1. **Backend wasn't running** - The FastAPI server needs to be actively running on port 8000
2. Both services need to run simultaneously for the application to work

## ✅ Solution: Start Both Services

### Option 1: One-Click Start (Easiest)
Double-click `START_BOTH.bat` in the root folder. This will open two command windows:
- Backend running on `http://localhost:8000`
- Frontend running on `http://localhost:5173`

### Option 2: Manual Start

#### Terminal 1 - Start Backend
```bash
cd backend
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

#### Terminal 2 - Start Frontend
```bash
cd frontend
npm run dev
```

## 🔍 Verify Everything is Working

1. **Check Backend**: Open http://localhost:8000/health
   - Should return: `{"status":"healthy","env":"development"}`

2. **Check Frontend**: Open http://localhost:5173
   - You should see the PawSome landing page

3. **Test Registration/Login**: 
   - Try signing up with a test account
   - You should no longer see "backend not running" errors

## 🔒 CORS Configuration

The backend is configured to allow requests from:
- `http://localhost:5173` (Vite dev server)

When you start the backend, you'll see a log message showing enabled CORS origins.

## 📝 Environment Variables

### Backend (.env)
- ✅ `DATABASE_URL` - Neon PostgreSQL (configured)
- ✅ `REDIS_URL` - Upstash Redis (configured)
- ✅ `JWT_SECRET` - JWT signing key (configured)
- ✅ `CORS_ORIGINS` - `http://localhost:5173` (configured)
- ✅ `R2_*` - Cloudflare R2 storage (configured)

### Frontend (.env)
- ✅ `VITE_API_URL` - `http://localhost:8000` (configured)
- ✅ `VITE_WS_URL` - `ws://localhost:8000` (configured)

## 🐛 Common Issues

### "Network error" or "Backend not running"
**Solution**: Make sure the backend is running on port 8000
```bash
# Check if backend is running
netstat -ano | findstr "8000"
```

### CORS errors in browser console
**Solution**: Check that:
1. Backend `.env` has `CORS_ORIGINS=http://localhost:5173`
2. Frontend is running on port 5173 (default Vite port)
3. Backend logs show "🔒 CORS enabled for origins: ['http://localhost:5173']"

### Port already in use
**Solution**: 
```bash
# Find and kill process using port 8000
netstat -ano | findstr "8000"
taskkill /PID <PID> /F
```

### Database Connection Timeout
**Error**: `TimeoutError` when starting backend

**Causes**:
1. **Neon database is suspended** - Serverless databases auto-suspend after inactivity
2. Network/firewall blocking connection
3. Incorrect DATABASE_URL

**Solutions**:
1. **Wake up the database**: Visit your [Neon Dashboard](https://console.neon.tech/) and check if the database is active
2. **Test connection**: Run `cd backend && uv run python test_db_connection.py`
3. **Check credentials**: Verify `DATABASE_URL` in `backend/.env` matches your Neon connection string
4. **Wait for cold start**: First connection after suspension can take 10-30 seconds

The backend now has extended timeouts (30s connection, 60s query) to handle cold starts.

## 🔄 Git Push to Separate Repositories

### Backend Changes
```bash
cd backend
git add .
git commit -m "Your commit message"
git push origin main
```
Pushes to: https://github.com/DebuggingDork/PawSome.git

### Frontend Changes
```bash
cd frontend
git add .
git commit -m "Your commit message"
git push origin main
```
Pushes to: https://github.com/DebuggingDork/PawSomeFrontend.git

## 📚 API Documentation

Once backend is running, visit:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## ✨ Next Steps

1. Start both services using `START_BOTH.bat`
2. Open http://localhost:5173 in your browser
3. Create a test account
4. Add a pet profile
5. Start swiping!

---

**Need help?** Check the logs in the terminal windows for error messages.
