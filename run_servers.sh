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

# Ensure Node.js version is >= 20.9.0 (load NVM if available, or prepend v22.22.0 to PATH)
if [ -s "$HOME/.nvm/nvm.sh" ]; then
    . "$HOME/.nvm/nvm.sh"
    nvm use 22.22.0 >/dev/null 2>&1 || nvm use default >/dev/null 2>&1
elif [ -d "$HOME/.nvm/versions/node/v22.22.0/bin" ]; then
    export PATH="$HOME/.nvm/versions/node/v22.22.0/bin:$PATH"
fi

echo "========================================="
echo "      Outreach App Server Launcher       "
echo "========================================="
echo "Using Node.js version: $(node -v 2>/dev/null || echo 'Unknown')"
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
