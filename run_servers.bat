@echo off
title Outreach App Launcher
echo =========================================
echo       Outreach App Server Launcher       
echo =========================================
echo.

echo [1/2] Launching FastAPI Backend on Port 8000...
start "Outreach Backend (Port 8000)" cmd /k ".\.venv\Scripts\python -m uvicorn api.main:app --port 8000 --reload"

echo [2/2] Launching Next.js Frontend on Port 3000...
start "Outreach Frontend (Port 3000)" cmd /k "cd outreach_web && npm run dev"

echo.
echo =========================================
echo Both servers are launching!
echo.
echo  - Backend API:  http://127.0.0.1:8000
echo  - Frontend Web: http://localhost:3000
echo =========================================
echo.
echo Press any key to exit this launcher window. (The servers will keep running).
pause > nul
