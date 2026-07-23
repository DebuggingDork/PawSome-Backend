@echo off
echo ========================================
echo  Starting PawSome Application
echo ========================================
echo.
echo Starting Backend on http://localhost:8000
echo Starting Frontend on http://localhost:5173
echo.
echo Press Ctrl+C to stop both services
echo.

start "PawSome Backend" cmd /k "cd /d backend && uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"
timeout /t 3 /nobreak >nul
start "PawSome Frontend" cmd /k "cd /d frontend && npm run dev"

echo.
echo Both services are starting in separate windows...
echo Close this window when you're done.
pause
