#!/bin/bash
# Bash script to restart Aphorium API server and frontend
# Usage: ./restart_app.sh

echo "Restarting Aphorium..."

# Stop the servers and kill all related processes
echo "Stopping previous instances..."

# Kill processes on ports 8000 and 3000
PORT8000_PID=$(lsof -ti:8000 2>/dev/null)
PORT3000_PID=$(lsof -ti:3000 2>/dev/null)

if [ ! -z "$PORT8000_PID" ]; then
    echo "Killing process on port 8000 (PID: $PORT8000_PID)..."
    kill -9 $PORT8000_PID 2>/dev/null
fi

if [ ! -z "$PORT3000_PID" ]; then
    echo "Killing process on port 3000 (PID: $PORT3000_PID)..."
    kill -9 $PORT3000_PID 2>/dev/null
fi

# Also kill any processes from PID file
if [ -f ".app_pids.txt" ]; then
    while read pid; do
        if [ ! -z "$pid" ] && kill -0 $pid 2>/dev/null; then
            echo "Killing process PID: $pid..."
            kill -9 $pid 2>/dev/null
        fi
    done < .app_pids.txt
fi

# Kill any uvicorn or node processes related to this app
pkill -f "uvicorn.*aphorium" 2>/dev/null
pkill -f "node.*aphorium" 2>/dev/null

# Wait for ports to be released
echo "Waiting for ports to be released..."
MAX_WAIT=10
WAITED=0
while [ $WAITED -lt $MAX_WAIT ]; do
    PORT8000_IN_USE=$(lsof -ti:8000 2>/dev/null)
    PORT3000_IN_USE=$(lsof -ti:3000 2>/dev/null)
    
    if [ -z "$PORT8000_IN_USE" ] && [ -z "$PORT3000_IN_USE" ]; then
        break
    fi
    
    sleep 1
    WAITED=$((WAITED + 1))
    echo "  Waiting... ($WAITED/$MAX_WAIT)"
done

if [ $WAITED -ge $MAX_WAIT ]; then
    echo "Warning: Ports may still be in use. Continuing anyway..."
fi

# Wait a bit more
sleep 2

# Activate virtual environment
source venv/bin/activate

# Create logs directory
mkdir -p logs

# Start backend server in background
echo ""
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

# Tail both log files with prefixes
tail -f logs/backend.log | sed 's/^/[BACKEND] /' &
TAIL_BACKEND_PID=$!
tail -f logs/frontend.log | sed 's/^/[FRONTEND] /' &
TAIL_FRONTEND_PID=$!

# Wait for both tail processes
wait $TAIL_BACKEND_PID $TAIL_FRONTEND_PID
