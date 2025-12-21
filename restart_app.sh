#!/bin/bash
# Bash script to restart Aphorium API server and frontend
# Usage: ./restart_app.sh

echo "Restarting Aphorium..."

# Stop the servers and kill all related processes
echo "Stopping previous instances..."

# First, run stop script to clean up
./stop_app.sh

# Kill ALL processes that might be related:
# 1. Processes on ports 8000, 3000, 3001, 3002, etc. (in case frontend tried different ports)
echo "Killing processes on ports..."
if command -v lsof >/dev/null 2>&1; then
    # Check ports 8000 and 3000-3010
    for port in 8000 $(seq 3000 3010); do
        PID=$(lsof -ti:$port 2>/dev/null || echo "")
        if [ ! -z "$PID" ]; then
            echo "  Killing process on port $port (PID: $PID)..."
            kill -9 $PID 2>/dev/null
        fi
    done
else
    echo "  lsof not available, skipping port-based process killing"
fi

# 2. Kill all node processes (frontend)
echo "Killing all node processes..."
if command -v pkill >/dev/null 2>&1; then
    pkill -9 node 2>/dev/null
else
    # Fallback: use ps and kill
    if command -v ps >/dev/null 2>&1; then
        NODE_PIDS=$(ps aux 2>/dev/null | grep -E "[n]ode" | awk '{print $2}' || ps -ef 2>/dev/null | grep -E "[n]ode" | awk '{print $2}' || echo "")
        for pid in $NODE_PIDS; do
            kill -9 $pid 2>/dev/null
        done
    fi
fi

# 3. Kill all uvicorn/python processes
echo "Killing uvicorn/python processes..."
if command -v pkill >/dev/null 2>&1; then
    pkill -9 -f "uvicorn.*api.main" 2>/dev/null
    pkill -9 -f "uvicorn.*aphorium" 2>/dev/null
    pkill -9 -f "python.*uvicorn" 2>/dev/null
else
    # Fallback: use ps and kill
    if command -v ps >/dev/null 2>&1; then
        PYTHON_PIDS=$(ps aux 2>/dev/null | grep -E "[p]ython.*uvicorn|[u]vicorn" | awk '{print $2}' || ps -ef 2>/dev/null | grep -E "[p]ython.*uvicorn|[u]vicorn" | awk '{print $2}' || echo "")
        for pid in $PYTHON_PIDS; do
            kill -9 $pid 2>/dev/null
        done
    fi
fi

# 4. Kill tail and sed processes (from log monitoring)
echo "Killing tail/sed processes..."
if command -v pkill >/dev/null 2>&1; then
    pkill -9 tail 2>/dev/null
    pkill -9 sed 2>/dev/null
else
    # Fallback: use ps and kill
    if command -v ps >/dev/null 2>&1; then
        TAIL_PIDS=$(ps aux 2>/dev/null | grep -E "[t]ail" | awk '{print $2}' || ps -ef 2>/dev/null | grep -E "[t]ail" | awk '{print $2}' || echo "")
        SED_PIDS=$(ps aux 2>/dev/null | grep -E "[s]ed" | awk '{print $2}' || ps -ef 2>/dev/null | grep -E "[s]ed" | awk '{print $2}' || echo "")
        for pid in $TAIL_PIDS $SED_PIDS; do
            kill -9 $pid 2>/dev/null
        done
    fi
fi

# 5. Kill any processes from PID file
if [ -f ".app_pids.txt" ]; then
    echo "Killing processes from PID file..."
    while read pid; do
        if [ ! -z "$pid" ] && kill -0 $pid 2>/dev/null; then
            echo "  Killing process PID: $pid..."
            kill -9 $pid 2>/dev/null
        fi
    done < .app_pids.txt
    rm -f .app_pids.txt
fi

# Check if ports 8000 and 3000 are in use - only wait if they are
echo "Checking if ports 8000 and 3000 are in use..."
if command -v lsof >/dev/null 2>&1; then
    PORT8000_IN_USE=$(lsof -ti:8000 2>/dev/null || echo "")
    PORT3000_IN_USE=$(lsof -ti:3000 2>/dev/null || echo "")
else
    # lsof not available, assume ports are free
    PORT8000_IN_USE=""
    PORT3000_IN_USE=""
    echo "  lsof not available, assuming ports are free"
fi

# Only wait if ports are actually in use
if [ ! -z "$PORT8000_IN_USE" ] || [ ! -z "$PORT3000_IN_USE" ]; then
    echo "Ports are in use. Waiting for release..."
    echo "IMPORTANT: Will wait until ports are free - will NOT use different ports!"
    MAX_WAIT=30
    WAITED=0
    
    while [ $WAITED -lt $MAX_WAIT ]; do
        if command -v lsof >/dev/null 2>&1; then
            PORT8000_IN_USE=$(lsof -ti:8000 2>/dev/null || echo "")
            PORT3000_IN_USE=$(lsof -ti:3000 2>/dev/null || echo "")
        else
            # lsof not available, assume ports are free and exit loop
            PORT8000_IN_USE=""
            PORT3000_IN_USE=""
        fi
        
        if [ -z "$PORT8000_IN_USE" ] && [ -z "$PORT3000_IN_USE" ]; then
            echo "All ports are free!"
            break
        fi
        
        # If ports still in use, try to kill processes again
        if [ ! -z "$PORT8000_IN_USE" ]; then
            echo "  Port 8000 still in use, killing PID: $PORT8000_IN_USE..."
            kill -9 $PORT8000_IN_USE 2>/dev/null
        fi
        
        if [ ! -z "$PORT3000_IN_USE" ]; then
            echo "  Port 3000 still in use, killing PID: $PORT3000_IN_USE..."
            kill -9 $PORT3000_IN_USE 2>/dev/null
        fi
        
        # Also kill any remaining node/python processes using our ports
        if command -v lsof >/dev/null 2>&1; then
            # Kill processes on our ports
            for port in 8000 3000; do
                PID=$(lsof -ti:$port 2>/dev/null || echo "")
                if [ ! -z "$PID" ]; then
                    kill -9 $PID 2>/dev/null
                fi
            done
        fi
        
        sleep 1
        WAITED=$((WAITED + 1))
        echo "  Waiting for ports 8000 and 3000... ($WAITED/$MAX_WAIT)"
    done
    
    # Final check - fail if ports still in use
    if command -v lsof >/dev/null 2>&1; then
        PORT8000_IN_USE=$(lsof -ti:8000 2>/dev/null || echo "")
        PORT3000_IN_USE=$(lsof -ti:3000 2>/dev/null || echo "")
    else
        PORT8000_IN_USE=""
        PORT3000_IN_USE=""
    fi
    
    if [ ! -z "$PORT8000_IN_USE" ] || [ ! -z "$PORT3000_IN_USE" ]; then
        echo ""
        echo "ERROR: Ports 8000 and/or 3000 are still in use after $MAX_WAIT seconds!"
        echo "Port 8000 in use: $([ ! -z "$PORT8000_IN_USE" ] && echo "YES (PID: $PORT8000_IN_USE)" || echo "NO")"
        echo "Port 3000 in use: $([ ! -z "$PORT3000_IN_USE" ] && echo "YES (PID: $PORT3000_IN_USE)" || echo "NO")"
        echo "Please manually kill processes and try again."
        echo "You can use: lsof -ti:8000,3000 | xargs kill -9"
        exit 1
    fi
else
    echo "Ports 8000 and 3000 are already free!"
fi

# Wait a bit more to ensure ports are fully released
echo "Waiting 2 seconds to ensure ports are fully released..."
sleep 2

# Final aggressive cleanup - kill any remaining processes on our ports
echo "Final cleanup: killing any remaining processes on ports 8000 and 3000..."
if command -v lsof >/dev/null 2>&1; then
    for port in 8000 3000; do
        PID=$(lsof -ti:$port 2>/dev/null || echo "")
        if [ ! -z "$PID" ]; then
            echo "  Killing process on port $port (PID: $PID)..."
            kill -9 $PID 2>/dev/null
            sleep 0.5
        fi
    done
fi

# Kill all node processes one more time (in case something started)
echo "Killing all node processes one final time..."
if command -v pkill >/dev/null 2>&1; then
    pkill -9 node 2>/dev/null
else
    if command -v ps >/dev/null 2>&1; then
        NODE_PIDS=$(ps aux 2>/dev/null | grep -E "[n]ode" | awk '{print $2}' || ps -ef 2>/dev/null | grep -E "[n]ode" | awk '{print $2}' || echo "")
        for pid in $NODE_PIDS; do
            kill -9 $pid 2>/dev/null
        done
    fi
fi

# Wait one more second
sleep 1

# Final verification - ports must be free
echo "Verifying ports 8000 and 3000 are free..."
if command -v lsof >/dev/null 2>&1; then
    PORT8000_FINAL=$(lsof -ti:8000 2>/dev/null || echo "")
    PORT3000_FINAL=$(lsof -ti:3000 2>/dev/null || echo "")
    
    if [ ! -z "$PORT8000_FINAL" ] || [ ! -z "$PORT3000_FINAL" ]; then
        echo ""
        echo "WARNING: Ports still in use after cleanup!"
        echo "Port 8000: $([ ! -z "$PORT8000_FINAL" ] && echo "IN USE (PID: $PORT8000_FINAL)" || echo "FREE")"
        echo "Port 3000: $([ ! -z "$PORT3000_FINAL" ] && echo "IN USE (PID: $PORT3000_FINAL)" || echo "FREE")"
        echo "Attempting to kill again..."
        [ ! -z "$PORT8000_FINAL" ] && kill -9 $PORT8000_FINAL 2>/dev/null
        [ ! -z "$PORT3000_FINAL" ] && kill -9 $PORT3000_FINAL 2>/dev/null
        sleep 1
    else
        echo "  Ports 8000 and 3000 are confirmed free!"
    fi
else
    echo "  lsof not available, proceeding anyway..."
fi

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

# Final check: make absolutely sure port 3000 is free
if command -v lsof >/dev/null 2>&1; then
    PORT3000_CHECK=$(lsof -ti:3000 2>/dev/null || echo "")
    if [ ! -z "$PORT3000_CHECK" ]; then
        echo "  WARNING: Port 3000 still in use (PID: $PORT3000_CHECK), killing..."
        kill -9 $PORT3000_CHECK 2>/dev/null
        sleep 1
        PORT3000_CHECK=$(lsof -ti:3000 2>/dev/null || echo "")
        if [ ! -z "$PORT3000_CHECK" ]; then
            echo "  ERROR: Port 3000 still in use after kill attempt!"
            echo "  Please manually kill process $PORT3000_CHECK and try again"
            exit 1
        fi
    fi
fi

cd frontend
# Use strict port - will fail if 3000 is not available
npm run dev -- --port 3000 --strictPort > ../logs/frontend.log 2>&1 &
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
