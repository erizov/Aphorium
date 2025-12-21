#!/bin/bash
# Bash script to restart Aphorium API server and frontend
# Usage: ./restart_app.sh

echo "Restarting Aphorium..."

# Stop the servers and kill all related processes
echo "Stopping previous instances..."

# First, run stop script to clean up
./stop_app.sh

# Kill processes on ports 8000, 3000, 3001, 3002 (in case frontend tried different ports)
PORTS=(8000 3000 3001 3002)
for port in "${PORTS[@]}"; do
    PID=$(lsof -ti:$port 2>/dev/null)
    if [ ! -z "$PID" ]; then
        echo "Killing process on port $port (PID: $PID)..."
        kill -9 $PID 2>/dev/null
    fi
done

# Kill all node processes (frontend)
pkill -9 node 2>/dev/null

# Kill all uvicorn/python processes
pkill -9 -f "uvicorn.*api.main" 2>/dev/null
pkill -9 -f "uvicorn.*aphorium" 2>/dev/null

# Wait for ports to be released with more aggressive checking
echo "Waiting for ports to be released..."
MAX_WAIT=15
WAITED=0
while [ $WAITED -lt $MAX_WAIT ]; do
    PORT8000_IN_USE=$(lsof -ti:8000 2>/dev/null)
    PORT3000_IN_USE=$(lsof -ti:3000 2>/dev/null)
    
    if [ -z "$PORT8000_IN_USE" ] && [ -z "$PORT3000_IN_USE" ]; then
        echo "All ports are free!"
        break
    fi
    
    # Try to kill again if still in use
    if [ ! -z "$PORT8000_IN_USE" ]; then
        kill -9 $PORT8000_IN_USE 2>/dev/null
    fi
    if [ ! -z "$PORT3000_IN_USE" ]; then
        kill -9 $PORT3000_IN_USE 2>/dev/null
    fi
    
    sleep 1
    WAITED=$((WAITED + 1))
    echo "  Waiting for ports... ($WAITED/$MAX_WAIT)"
done

# Final check - fail if ports still in use
PORT8000_IN_USE=$(lsof -ti:8000 2>/dev/null)
PORT3000_IN_USE=$(lsof -ti:3000 2>/dev/null)

if [ ! -z "$PORT8000_IN_USE" ] || [ ! -z "$PORT3000_IN_USE" ]; then
    echo "ERROR: Ports are still in use after $MAX_WAIT seconds!"
    echo "Please manually kill processes and try again."
    exit 1
fi

# Wait a bit more to ensure ports are fully released
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
