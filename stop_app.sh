#!/bin/bash
# Bash script to stop Aphorium API server
# Usage: ./stop_app.sh

echo "Stopping Aphorium API server..."

# Find and kill uvicorn processes
PID=$(pgrep -f "uvicorn.*api.main:app" || pgrep -f "api.main:app")

if [ -n "$PID" ]; then
    echo "Stopping process $PID..."
    kill $PID
    echo "Server stopped."
else
    echo "No running server found."
fi

# Also try pkill as fallback
pkill -f "uvicorn.*api.main:app" 2>/dev/null

