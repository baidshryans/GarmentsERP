@echo off
setlocal enabledelayedexpansion

title Jewel India ERP — Dev Setup

echo ============================================================
echo   Jewel India ERP — Development Environment Setup
echo ============================================================
echo.

:: ── Locate the script's own directory ───────────────────────────────────────
set "ROOT=%~dp0"
set "ROOT=%ROOT:~0,-1%"
set "BACKEND=%ROOT%\backend"
set "FRONTEND=%ROOT%\frontend"
set "VENV=%BACKEND%\env"

:: ── Check prerequisites ──────────────────────────────────────────────────────
echo [1/7] Checking prerequisites...

where python >nul 2>&1
if errorlevel 1 (
    echo   ERROR: Python is not installed or not in PATH.
    echo   Download from https://www.python.org/downloads/
    pause & exit /b 1
)
for /f "tokens=*" %%v in ('python --version 2^>^&1') do echo   Found %%v

where node >nul 2>&1
if errorlevel 1 (
    echo   ERROR: Node.js is not installed or not in PATH.
    echo   Download from https://nodejs.org/
    pause & exit /b 1
)
for /f "tokens=*" %%v in ('node --version 2^>^&1') do echo   Found Node.js %%v

where npm >nul 2>&1
if errorlevel 1 (
    echo   ERROR: npm is not found. Re-install Node.js.
    pause & exit /b 1
)
for /f "tokens=*" %%v in ('npm --version 2^>^&1') do echo   Found npm %%v
echo.

:: ── Backend: create virtual environment ─────────────────────────────────────
echo [2/7] Setting up Python virtual environment...
if exist "%VENV%\Scripts\activate.bat" (
    echo   Virtual environment already exists — skipping creation.
) else (
    python -m venv "%VENV%"
    if errorlevel 1 (
        echo   ERROR: Failed to create virtual environment.
        pause & exit /b 1
    )
    echo   Virtual environment created at: %VENV%
)
echo.

:: ── Activate venv ────────────────────────────────────────────────────────────
call "%VENV%\Scripts\activate.bat"
echo   Virtual environment activated.
echo.

:: ── Install Python dependencies ──────────────────────────────────────────────
echo [3/7] Installing Python dependencies (pip install -r requirements.txt)...
choice /C YN /M "   Do you want to run pip install? (Y/N): "
if errorlevel 2 (
    echo   Skipping pip install.
) else if errorlevel 1 (
    cd /d "%BACKEND%"
    pip install -r requirements.txt --quiet
    if errorlevel 1 (
        echo   ERROR: pip install failed.
        pause & exit /b 1
    )
    echo   Done.
)
echo.

:: ── Check .env file ──────────────────────────────────────────────────────────
if not exist "%BACKEND%\.env" (
    echo   WARNING: No .env file found at backend\.env
    echo   Copy .env.example to .env and fill in your settings before continuing.
    echo   Then re-run this script from step [5/7] onwards manually.
    pause
)

:: ── Django: makemigrations + migrate ─────────────────────────────────────────
echo [4/7] Running database migrations...
cd /d "%BACKEND%"
python manage.py makemigrations
if errorlevel 1 (
    echo   ERROR: makemigrations failed.
    pause & exit /b 1
)
python manage.py migrate
if errorlevel 1 (
    echo   ERROR: migrate failed.
    pause & exit /b 1
)
echo   Done.
echo.

:: ── Django: create superuser ─────────────────────────────────────────────────
echo [5/7] Create a Django superuser account.
cd /d "%BACKEND%"
python manage.py shell -c "from django.contrib.auth import get_user_model; U=get_user_model(); u,created=U.objects.get_or_create(username='admin', defaults={'email':'admin@example.com','is_staff':True,'is_superuser':True}); u.is_staff=True; u.is_superuser=True; u.is_active=True; u.set_password('admin123'); u.save(); print('Superuser admin created' if created else 'Superuser admin already existed (password reset to admin123)')"
echo.

:: ── Launch servers in separate windows ──────────────────────────────────────
echo [6/7] Starting development servers...
echo.
echo   Django backend  →  http://127.0.0.1:8000
echo   Vite frontend   →  http://localhost:5173
echo.

:: Django in a new window (venv already activated in that shell via /k)
start "Django Dev Server" cmd /k "cd /d "%BACKEND%" && call "%VENV%\Scripts\activate.bat" && python manage.py runserver"

:: Small delay so Django starts before frontend (avoids CORS noise in console)
timeout /t 2 /nobreak >nul

:: Vite in a new window
start "Vite Dev Server" cmd /k "cd /d "%FRONTEND%" && npm run dev"

:: Small delay to ensure React server starts
timeout /t 4 /nobreak >nul

:: Open Chrome with the React server
start "" "C:\Program Files\Google\Chrome\Application\chrome.exe" "http://localhost:5173"

echo ============================================================
echo   Setup complete!  Both servers are running in new windows.
echo   Chrome should open automatically at http://localhost:5173
echo   Close the server windows to stop them.
echo ============================================================
echo.
pause
