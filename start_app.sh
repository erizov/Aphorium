#!/bin/bash
# Bash script to start Aphorium API server
# Usage: ./start_app.sh

echo "Starting Aphorium API server..."

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Virtual environment not found. Creating..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Check if dependencies are installed
echo "Checking dependencies..."
if ! pip show fastapi &> /dev/null; then
    echo "Installing dependencies..."
    pip install -r requirements.txt
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
        # Check if PostgreSQL is running (Linux/Mac)
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

# Start the server
echo "Starting API server on http://localhost:8000"
echo "API docs available at http://localhost:8000/docs"
echo "Press Ctrl+C to stop the server"
echo ""

uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload

