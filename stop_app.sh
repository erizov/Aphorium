#!/bin/bash
# Bash script to stop Aphorium API server and frontend
# Usage: ./stop_app.sh

echo "Stopping Aphorium servers..."

# Read PIDs from file
PID_FILE=".app_pids.txt"
if [ -f "$PID_FILE" ]; then
    while read pid; do
        if [ -n "$pid" ] && kill -0 $pid 2>/dev/null; then
            echo "Stopping process $pid..."
            kill $pid 2>/dev/null
        fi
    done < $PID_FILE
    rm -f $PID_FILE
fi

# Find and kill uvicorn processes
UVICORN_PID=$(pgrep -f "uvicorn.*api.main:app" || pgrep -f "api.main:app")
if [ -n "$UVICORN_PID" ]; then
    echo "Stopping uvicorn process $UVICORN_PID..."
    kill $UVICORN_PID 2>/dev/null
fi

# Find and kill node/vite processes (frontend)
NODE_PID=$(pgrep -f "vite" || pgrep -f "npm.*dev")
if [ -n "$NODE_PID" ]; then
    echo "Stopping node process $NODE_PID..."
    kill $NODE_PID 2>/dev/null
fi

# Kill processes by port
BACKEND_PORT=8000
FRONTEND_PORT=3000

# Backend port
BACKEND_PID=$(lsof -ti:$BACKEND_PORT 2>/dev/null)
if [ -n "$BACKEND_PID" ]; then
    echo "Stopping process on port $BACKEND_PORT (PID: $BACKEND_PID)..."
    kill $BACKEND_PID 2>/dev/null
fi

# Frontend port
FRONTEND_PID=$(lsof -ti:$FRONTEND_PORT 2>/dev/null)
if [ -n "$FRONTEND_PID" ]; then
    echo "Stopping process on port $FRONTEND_PORT (PID: $FRONTEND_PID)..."
    kill $FRONTEND_PID 2>/dev/null
fi

# Fallback: pkill
pkill -f "uvicorn.*api.main:app" 2>/dev/null
pkill -f "vite" 2>/dev/null

echo "Servers stopped."
