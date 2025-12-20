#!/bin/bash
# Bash script to start Aphorium API server and frontend
# Usage: ./start_app.sh

echo "Starting Aphorium..."

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Virtual environment not found. Creating..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Check if dependencies are installed
echo "Checking backend dependencies..."
if ! pip show fastapi &> /dev/null; then
    echo "Installing backend dependencies..."
    pip install -r requirements.txt
fi

# Check frontend dependencies
echo "Checking frontend dependencies..."
if [ ! -d "frontend/node_modules" ]; then
    echo "Installing frontend dependencies..."
    cd frontend
    npm install
    cd ..
fi

# Check if .env file exists
echo "Checking configuration..."
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        echo "Creating .env from .env.example..."
        cp .env.example .env
        echo "Please edit .env with your database credentials!"
    else
        echo "Creating .env file with defaults..."
        cat > .env << EOF
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/aphorium
LOG_LEVEL=INFO
LOG_FILE=logs/aphorium.log
API_HOST=0.0.0.0
API_PORT=8000
WIKIQUOTE_RU_BASE_URL=https://ru.wikiquote.org
WIKIQUOTE_EN_BASE_URL=https://en.wikiquote.org
SCRAPE_DELAY=1.0
EOF
        echo "Please edit .env with your database credentials!"
    fi
fi

# Check database configuration
echo "Checking database..."
if [ -f ".env" ]; then
    DB_URL=$(grep "DATABASE_URL" .env | cut -d '=' -f2)
    if [[ $DB_URL == *"postgresql"* ]]; then
        echo "Using PostgreSQL database"
        if command -v pg_isready &> /dev/null; then
            if pg_isready -q; then
                echo "  PostgreSQL is ready"
            else
                echo "  Warning: PostgreSQL may not be running"
            fi
        fi
    elif [[ $DB_URL == *"sqlite"* ]]; then
        echo "Using SQLite database"
    fi
fi

# Check if database is initialized
if [ ! -f ".db_initialized" ]; then
    echo "Database not initialized. Setting up..."
    if [[ $DB_URL == *"sqlite"* ]]; then
        python setup_database_sqlite.py
    else
        python init_database.py
    fi
    touch .db_initialized
fi

# Create logs directory
mkdir -p logs

# PID file
PID_FILE=".app_pids.txt"

# Start backend server
echo ""
echo "Starting backend API server..."
uvicorn api.main:app --host 0.0.0.0 --port 8000 > logs/backend.log 2>&1 &
BACKEND_PID=$!
echo $BACKEND_PID > $PID_FILE

# Start frontend dev server
echo "Starting frontend dev server..."
cd frontend
npm run dev > ../logs/frontend.log 2>&1 &
FRONTEND_PID=$!
cd ..
echo $FRONTEND_PID >> $PID_FILE

echo ""
echo "============================================================"
echo "Aphorium is starting..."
echo "============================================================"
echo "Backend API: http://localhost:8000"
echo "API Docs:    http://localhost:8000/docs"
echo "Frontend:    http://localhost:3000"
echo ""
echo "To stop both servers, run: ./stop_app.sh"
echo ""

# Wait a moment for servers to start
sleep 3

# Check if servers are running
if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo "[OK] Backend server is running"
else
    echo "[...] Backend server starting..."
fi

echo "[...] Frontend server starting..."
echo ""
echo "Servers are running in background."
echo "Backend PID: $BACKEND_PID"
echo "Frontend PID: $FRONTEND_PID"
echo ""
echo "Logs:"
echo "  Backend:  logs/backend.log"
echo "  Frontend: logs/frontend.log"
echo ""

# Wait for interrupt
trap 'echo ""; echo "Stopping servers..."; ./stop_app.sh; exit' INT TERM

# Keep script running
wait
