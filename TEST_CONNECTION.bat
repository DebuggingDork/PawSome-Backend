@echo off
echo ========================================
echo  PawSome Connection Test
echo ========================================
echo.

echo Testing Backend Connection...
echo.

curl -s http://localhost:8000/health >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo ✅ Backend is RUNNING on http://localhost:8000
    echo.
    curl http://localhost:8000/health
    echo.
) else (
    echo ❌ Backend is NOT RUNNING on port 8000
    echo.
    echo Start the backend with:
    echo   cd backend
    echo   uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
    echo.
)

echo.
echo ========================================
echo.

echo Testing Frontend Connection...
echo.

curl -s http://localhost:5173 >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo ✅ Frontend is RUNNING on http://localhost:5173
    echo.
) else (
    echo ❌ Frontend is NOT RUNNING on port 5173
    echo.
    echo Start the frontend with:
    echo   cd frontend
    echo   npm run dev
    echo.
)

echo.
echo ========================================
echo  Test Complete
echo ========================================
echo.
echo If both services are running:
echo   • Frontend: http://localhost:5173
echo   • Backend API: http://localhost:8000/docs
echo.
pause
