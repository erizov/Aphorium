# Deployment Guide

## Quick Start

### Backend (FastAPI)

```bash
# Start API server
.\start_app.ps1  # Windows
./start_app.sh   # Linux/Mac
```

API runs on: http://localhost:8000

### Frontend (React)

```bash
cd frontend
npm install
npm run dev
```

Frontend runs on: http://localhost:3000

## Production Deployment

### Backend

1. Use production ASGI server:
```bash
gunicorn api.main:app -w 4 -k uvicorn.workers.UvicornWorker
```

2. Or with uvicorn:
```bash
uvicorn api.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### Frontend

1. Build for production:
```bash
cd frontend
npm run build
```

2. Serve static files:
```bash
# Using nginx or similar
# Or serve dist/ folder with any static file server
```

## Environment Variables

Set in `.env`:
- `DATABASE_URL` - Database connection string
- `LOG_LEVEL` - Logging level
- `API_PORT` - API server port

## Database

- Development: SQLite (automatic)
- Production: PostgreSQL (see research/POSTGRESQL_MIGRATION_PLAN.md)

