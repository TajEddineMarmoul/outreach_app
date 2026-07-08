#!/bin/bash

# Function to clean up background processes on exit
cleanup() {
    echo ""
    echo "Stopping servers..."
    # Kill the background jobs started by this script
    kill $(jobs -p) 2>/dev/null
    exit 0
}

# Run cleanup on script interruption or exit
trap cleanup SIGINT SIGTERM EXIT

echo "========================================="
echo "      Outreach App Server Launcher       "
echo "========================================="
echo ""

echo "[1/2] Launching FastAPI Backend on Port 8000..."
./.venv/bin/python -m uvicorn api.main:app --port 8000 --reload &

echo "[2/2] Launching Next.js Frontend on Port 3000..."
(cd outreach_web && npm run dev) &

echo ""
echo "========================================="
echo "Both servers are launching!"
echo ""
echo " - Backend API:  http://127.0.0.1:8000"
echo " - Frontend Web: http://localhost:3000"
echo "========================================="
echo ""
echo "Press Ctrl+C to stop both servers."

# Keep script running to maintain the background processes
wait
