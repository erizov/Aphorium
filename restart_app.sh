#!/bin/bash
# Bash script to restart Aphorium API server and frontend
# Usage: ./restart_app.sh

echo "Restarting Aphorium..."

# Stop the servers
./stop_app.sh

# Wait a moment
sleep 2

# Activate virtual environment
source venv/bin/activate

# Create logs directory
mkdir -p logs

# Start backend server in background
echo "Starting backend API server..."
uvicorn api.main:app --host 0.0.0.0 --port 8000 > logs/backend.log 2>&1 &
BACKEND_PID=$!
echo $BACKEND_PID > .app_pids.txt

# Start frontend dev server in background
echo "Starting frontend dev server..."
cd frontend
npm run dev > ../logs/frontend.log 2>&1 &
FRONTEND_PID=$!
cd ..
echo $FRONTEND_PID >> .app_pids.txt

echo ""
echo "============================================================"
echo "Aphorium is running. Showing combined logs..."
echo "============================================================"
echo "Backend API: http://localhost:8000"
echo "Frontend:    http://localhost:3000"
echo ""
echo "Press Ctrl+C to stop both servers"
echo ""

# Function to cleanup on exit
cleanup() {
    echo ""
    echo "Stopping servers..."
    kill $BACKEND_PID $FRONTEND_PID 2>/dev/null
    ./stop_app.sh
    exit
}

trap cleanup INT TERM

# Tail both log files with prefixes using multitail or simple approach
if command -v multitail &> /dev/null; then
    multitail -s 2 -cT ansi logs/backend.log -cT ansi logs/frontend.log
else
    # Simple approach: use tail with process substitution
    tail -f logs/backend.log | sed 's/^/[BACKEND] /' &
    tail -f logs/frontend.log | sed 's/^/[FRONTEND] /' &
    wait
fi
