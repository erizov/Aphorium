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

# Find and kill uvicorn processes using ps (works on both Linux and Windows with WSL/Git Bash)
if command -v ps >/dev/null 2>&1; then
    UVICORN_PIDS=$(ps aux 2>/dev/null | grep -E "[u]vicorn.*api.main" | awk '{print $2}' || ps -ef 2>/dev/null | grep -E "[u]vicorn.*api.main" | awk '{print $2}' || echo "")
    if [ -n "$UVICORN_PIDS" ]; then
        for pid in $UVICORN_PIDS; do
            echo "Stopping uvicorn process $pid..."
            kill $pid 2>/dev/null
        done
    fi
fi

# Find and kill node/vite processes (frontend)
if command -v ps >/dev/null 2>&1; then
    NODE_PIDS=$(ps aux 2>/dev/null | grep -E "[n]ode.*vite|[n]pm.*dev" | awk '{print $2}' || ps -ef 2>/dev/null | grep -E "[n]ode.*vite|[n]pm.*dev" | awk '{print $2}' || echo "")
    if [ -n "$NODE_PIDS" ]; then
        for pid in $NODE_PIDS; do
            echo "Stopping node process $pid..."
            kill $pid 2>/dev/null
        done
    fi
fi

# Kill tail and sed processes (from log monitoring)
pkill tail 2>/dev/null
pkill sed 2>/dev/null

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

# Fallback: kill by process name if pkill is available
if command -v pkill >/dev/null 2>&1; then
    pkill -f "uvicorn.*api.main:app" 2>/dev/null
    pkill -f "vite" 2>/dev/null
fi

echo "Servers stopped."
