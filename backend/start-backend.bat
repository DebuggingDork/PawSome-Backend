@echo off
echo Starting PawSome Backend...
echo.
cd /d "%~dp0"

echo Testing database connection first...
uv run python test_db_connection.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ⚠️  Database connection test failed!
    echo Please check your DATABASE_URL in .env
    echo.
    pause
    exit /b 1
)

echo.
echo Database OK! Starting server...
echo.
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
