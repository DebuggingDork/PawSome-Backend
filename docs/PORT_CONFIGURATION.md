# 🔌 PawSome Port Configuration

## Current Port Setup

| Service | Port | URL |
|---------|------|-----|
| **Frontend (Vite)** | 5174 | http://localhost:5174 |
| **Backend (FastAPI)** | 8000 | http://localhost:8000 |
| **API Docs (Swagger)** | 8000 | http://localhost:8000/docs |

## ⚠️ IMPORTANT: Port Mismatch Issue

If you see CORS errors like:
```
Access to fetch at 'http://localhost:8000/...' from origin 'http://localhost:5174' 
has been blocked by CORS policy
```

This means your **frontend port** and **CORS configuration** don't match!

## ✅ How to Fix

### Check Your Current Frontend Port
When you start the frontend, Vite shows:
```
VITE v5.x.x ready in xxx ms

➜  Local:   http://localhost:5174/
```

**That number (5174) is your frontend port.**

### Update Backend CORS Configuration

Edit `backend/.env`:
```env
# Change this line to match your frontend port:
CORS_ORIGINS=http://localhost:5174

# Also update:
FRONTEND_URL=http://localhost:5174
```

### Restart Backend
```bash
# Stop the backend (Ctrl+C)
# Then restart:
cd backend
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

You should see:
```
🔒 CORS enabled for origins: ['http://localhost:5174']
```

## 🔧 Why Port 5174 Instead of 5173?

Vite's default port is 5173, but it will use 5174 if:
- Port 5173 is already in use
- Another Vite dev server is running
- Windows reserved the port

We've now **locked the port to 5174** in `vite.config.ts`, so it's consistent.

## 🎯 Configuration Files

### Backend CORS (`backend/.env`)
```env
CORS_ORIGINS=http://localhost:5174  # ← Must match frontend port
FRONTEND_URL=http://localhost:5174  # ← Must match frontend port
```

### Frontend Vite Config (`frontend/vite.config.ts`)
```typescript
export default defineConfig({
  // ...
  server: {
    port: 5174,        // ← Frontend port
    strictPort: true,  // ← Fail if port unavailable
  },
})
```

### Frontend API URL (`frontend/.env`)
```env
VITE_API_URL=http://localhost:8000  # ← Backend port (correct)
VITE_WS_URL=ws://localhost:8000     # ← Backend WebSocket (correct)
```

## 🔍 Verify Configuration

After starting both services:

### 1. Check Backend Logs
Should show:
```
🔒 CORS enabled for origins: ['http://localhost:5174']
```

### 2. Check Frontend URL
Browser should be at:
```
http://localhost:5174
```

### 3. Test CORS
Open browser console (F12) and run:
```javascript
fetch('http://localhost:8000/health')
  .then(r => r.json())
  .then(console.log)
```

Should return:
```json
{"status":"healthy","env":"development"}
```

If you see CORS error → ports don't match!

## 🚨 Common Mistakes

### ❌ Wrong: CORS on 5173, Frontend on 5174
```env
# backend/.env
CORS_ORIGINS=http://localhost:5173  # ← Wrong!

# Frontend actually running on 5174
```
**Result:** CORS blocked!

### ✅ Correct: Both Match
```env
# backend/.env
CORS_ORIGINS=http://localhost:5174  # ← Correct!

# Frontend running on 5174
```
**Result:** Works perfectly!

## 📝 Quick Fix Checklist

If CORS is blocking:

1. ☑️ Check what port frontend is ACTUALLY running on
2. ☑️ Update `CORS_ORIGINS` in `backend/.env` to match
3. ☑️ Update `FRONTEND_URL` in `backend/.env` to match
4. ☑️ Restart the backend server
5. ☑️ Check backend logs for `🔒 CORS enabled for origins:`
6. ☑️ Refresh your browser
7. ☑️ Try login/register again

## 🎯 TL;DR

**The frontend port and CORS origins MUST match exactly!**

```
Frontend Port = 5174
         ↓
CORS_ORIGINS=http://localhost:5174
```

**Always check the backend logs on startup:**
```
🔒 CORS enabled for origins: ['http://localhost:5174']
                                          ↑↑↑↑
                                    Must match your frontend!
```
