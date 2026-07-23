# 🔧 PawSome Troubleshooting Guide

## Database Connection Issues

### ❌ Error: TimeoutError / Connection Timeout

**Full error message:**
```
asyncpg.connection: TimeoutError
Could not connect to database
```

**Root Cause:**
Neon (your PostgreSQL provider) is a **serverless database** that automatically suspends after inactivity to save resources. When suspended, the first connection attempt takes longer as the database "wakes up."

### ✅ Solutions (in order):

#### 1. **Wait for Cold Start** (Most Common)
The first connection after suspension can take **10-30 seconds**. Just wait and the connection should succeed.

#### 2. **Test Connection Manually**
```bash
cd backend
uv run python test_db_connection.py
```

This will:
- Test the database connection
- Show if the database is reachable
- Display helpful error messages
- Wake up the database for subsequent connections

#### 3. **Check Neon Dashboard**
1. Visit https://console.neon.tech/
2. Log in to your account
3. Find your `neondb` database
4. Check if it shows as "Active" or "Suspended"
5. If suspended, click to wake it up

#### 4. **Verify DATABASE_URL**
Open `backend/.env` and verify:
```env
DATABASE_URL=postgresql://neondb_owner:npg_xgY3G4KPJpud@ep-delicate-cloud-aoffo7k7-pooler.c-2.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require
```

Make sure:
- No extra spaces
- Correct password
- URL matches your Neon project

#### 5. **Check Network/Firewall**
```bash
# Test if you can reach Neon's endpoint
ping ep-delicate-cloud-aoffo7k7-pooler.c-2.ap-southeast-1.aws.neon.tech
```

If ping fails:
- Check your firewall settings
- Check antivirus software
- Try from a different network

### 🔧 What We Fixed

The backend now has improved connection settings:

```python
connect_args = {
    "timeout": 30,           # 30 second connection timeout (handles cold starts)
    "command_timeout": 60,   # 60 second query timeout
    "ssl": True,             # SSL enabled for Neon
}

# Connection pool settings
pool_size=5                  # Keep 5 connections ready
pool_pre_ping=True          # Verify connections before using
pool_recycle=3600           # Recycle old connections
```

These settings handle:
- Serverless cold starts
- Network latency
- Connection validation
- Automatic recovery from stale connections

---

## Frontend Connection Issues

### ❌ Error: "Could not reach the server. Is the backend running?"

**Cause:** Backend is not running on port 8000

**Solution:**
```bash
# Check if backend is running
netstat -ano | findstr "8000"

# If not, start it
cd backend
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Or just run: `START_BOTH.bat`

---

## CORS Errors

### ❌ Error: "Access to fetch at 'http://localhost:8000/...' from origin 'http://localhost:5173' has been blocked by CORS policy"

**Cause:** CORS not configured correctly

**Check:**
1. Backend `.env` has: `CORS_ORIGINS=http://localhost:5173`
2. Frontend is running on port 5173 (default Vite port)
3. Backend logs show: `🔒 CORS enabled for origins: ['http://localhost:5173']`

**Solution:**
```bash
# Stop both services
# Edit backend/.env and add:
CORS_ORIGINS=http://localhost:5173

# Restart backend
cd backend
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

---

## Port Already in Use

### ❌ Error: "Address already in use" on port 8000 or 5173

**Solution:**

**For Port 8000 (Backend):**
```bash
# Find process using port 8000
netstat -ano | findstr "8000"

# Kill the process (replace <PID> with actual number)
taskkill /PID <PID> /F
```

**For Port 5173 (Frontend):**
```bash
# Find process using port 5173
netstat -ano | findstr "5173"

# Kill the process
taskkill /PID <PID> /F
```

---

## Authentication Issues

### ❌ Error: 401 Unauthorized

**Causes:**
1. Access token expired (30 min lifetime)
2. Invalid token
3. Token not being sent in requests

**Solution:**
1. Log out and log back in
2. Check browser console for token errors
3. Clear browser localStorage: 
   ```javascript
   // In browser console
   localStorage.clear()
   ```

### ❌ Error: "Email already exists" during registration

**Cause:** You've already registered with that email

**Solution:** 
- Use login instead of register
- Or use a different email

---

## Photo Upload Issues

### ❌ Error: 503 Service Unavailable (photo endpoints)

**Cause:** Cloudflare R2 credentials not configured

**Solution:**
Check `backend/.env` has all R2 variables:
```env
R2_ACCOUNT_ID=your-account-id
R2_ACCESS_KEY_ID=your-access-key
R2_SECRET_ACCESS_KEY=your-secret-key
R2_BUCKET_NAME=your-bucket-name
R2_PUBLIC_BASE_URL=https://your-bucket.r2.dev
```

### ❌ Error: "Maximum 5 photos per pet"

**Cause:** Pet already has 5 photos (this is the limit)

**Solution:** Delete an existing photo before uploading a new one

---

## Migration Issues

### ❌ Error: "Table already exists" or migration errors

**Solution:**
```bash
cd backend

# Check current migration state
uv run alembic current

# Check pending migrations
uv run alembic history

# Apply all migrations
uv run alembic upgrade head

# If corrupted, downgrade and reapply
uv run alembic downgrade -1
uv run alembic upgrade head
```

---

## General Debugging

### Enable Debug Logging

**Backend:**
```bash
# Already enabled in development
# Check app.main:app logs in terminal
```

**Frontend:**
```bash
# Open browser DevTools (F12)
# Check Console tab for errors
# Check Network tab for API calls
```

### Test Everything is Working

```bash
# Test backend directly
curl http://localhost:8000/health

# Should return:
# {"status":"healthy","env":"development"}

# Test database connection
cd backend
uv run python test_db_connection.py

# Test frontend API calls
# Open http://localhost:5173
# Try to register/login
# Check browser console for errors
```

### Full Reset

If everything is broken, start fresh:

```bash
# 1. Stop all services (Ctrl+C in terminals)

# 2. Test database connection
cd backend
uv run python test_db_connection.py

# 3. Apply migrations
uv run alembic upgrade head

# 4. Start both services
cd ..
START_BOTH.bat

# 5. Test in browser
# Open http://localhost:5173
# Register a new account
```

---

## Getting Help

### Before Asking for Help:

1. ✅ Run `TEST_CONNECTION.bat` to check service status
2. ✅ Run `backend/test_db_connection.py` to verify database
3. ✅ Check backend terminal for error messages
4. ✅ Check browser console (F12) for frontend errors
5. ✅ Verify all environment variables in `.env` files

### Provide This Information:

- Error message (full stack trace)
- Backend terminal output
- Browser console errors
- Output of `test_db_connection.py`
- Which endpoint/feature is failing
- Steps to reproduce the issue

---

## Quick Reference

| Issue | Quick Fix |
|-------|-----------|
| Backend won't start | `cd backend && uv run python test_db_connection.py` |
| Frontend can't connect | Run `START_BOTH.bat` |
| CORS errors | Check `CORS_ORIGINS=http://localhost:5173` in backend/.env |
| 401 errors | Log out and log back in |
| Photo upload fails | Check R2 credentials in backend/.env |
| Port in use | `netstat -ano \| findstr "8000"` then `taskkill /PID <PID> /F` |
| Database timeout | Wait 30 seconds for cold start, or check Neon dashboard |

---

**Still stuck?** Check the error message carefully - it usually tells you exactly what's wrong! 🔍
