# Aphorium

A search engine for aphorisms and quotes from Russian and English literature,
designed to help users remember exact words and learn languages.

## Features

- Fast full-text search across Russian and English quotes
- Bilingual quote pairs (English-Russian)
- WikiQuote integration (RU and EN)
- Extensible architecture for future sources
- Simple, text-only interface

## Quick Start

### Prerequisites

- Python 3.10+
- PostgreSQL 12+

### Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd Aphorium
```

2. Create virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
# First, update build tools
python -m pip install --upgrade pip setuptools wheel

# Then install requirements
pip install -r requirements.txt
```

**Note:** If you encounter errors with `pydantic-core` on Python 3.13, see [research/INSTALL_TROUBLESHOOTING.md](research/INSTALL_TROUBLESHOOTING.md) for solutions.

4. Set up database:

**Option A: Use SQLite (Easiest for testing):**
```bash
python setup_database.py
# Choose 'y' when prompted to use SQLite
```

**Option B: Use PostgreSQL (Recommended for production):**
```bash
# Install PostgreSQL (see [research/POSTGRESQL_SETUP.md](research/POSTGRESQL_SETUP.md) for details)
# Then create database:
createdb aphorium

# Or use the setup helper:
python setup_database.py
```

5. Configure environment variables:

**Windows (PowerShell):**
```powershell
Copy-Item .env.example .env
# Edit .env with your database credentials
```

**Linux/Mac:**
```bash
cp .env.example .env
# Edit .env with your database credentials
```

**Note:** If `.env.example` doesn't exist, it will be created automatically. You can also create `.env` manually with the following variables:
- `DATABASE_URL` - PostgreSQL connection string
- `LOG_LEVEL` - Logging level (INFO, DEBUG, etc.)
- `API_PORT` - API server port (default: 8000)

6. Initialize database:
```bash
python init_database.py
```

7. Start the API server:

**Windows:**
```bash
.\start_app.ps1
```

**Linux/Mac:**
```bash
./start_app.sh
```

**Or manually:**
```bash
uvicorn api.main:app --reload
```

8. Start the application:

**Windows:**
```bash
.\start_app.ps1    # Starts both backend and frontend
```

**Linux/Mac:**
```bash
./start_app.sh     # Starts both backend and frontend
```

This will start:
- **Backend API** at http://localhost:8000
- **Frontend** at http://localhost:3000
- **API Docs** at http://localhost:8000/docs

### Managing the Application

**Windows:**
```bash
.\start_app.ps1    # Start both backend and frontend
.\stop_app.ps1     # Stop both servers
.\restart_app.ps1  # Restart both servers
```

**Linux/Mac:**
```bash
./start_app.sh     # Start both backend and frontend
./stop_app.sh      # Stop both servers
./restart_app.sh   # Restart both servers
```

**Note:** The start scripts automatically:
- Check and install dependencies (backend and frontend)
- Set up the database if needed
- Start both servers in separate processes
- Display server URLs and status

## Usage

### Ingesting WikiQuote Data

**Option 1: Single Author (Simple)**
```bash
# Ingest English author
python -m scrapers.ingest --lang en --author "William Shakespeare"

# Ingest Russian author
python -m scrapers.ingest --lang ru --author "Александр Пушкин"
```

**Option 2: Batch Loading (Recommended)**
```bash
# Load bilingual authors (authors that exist in both languages)
python -m scrapers.batch_loader --lang en --mode bilingual --workers 3
python -m scrapers.batch_loader --lang ru --mode bilingual --workers 3

# Or load from a file
python -m scrapers.batch_loader --lang en --authors-file authors.txt --workers 3
```

**Match Bilingual Pairs**
```bash
# After ingesting authors in both languages
python match_translations.py
```

See [research/WORKFLOW.md](research/WORKFLOW.md) for detailed workflow instructions.

### API Endpoints

- `GET /api/quotes/search?q=text&lang=en|ru|both` - Search quotes
- `GET /api/quotes/{id}` - Get quote by ID
- `GET /api/quotes/{id}/translations` - Get translations of a quote
- `GET /api/authors?name=...` - Search authors
- `GET /api/sources?title=...` - Search sources

### Frontend

Open `frontend/index.html` in your browser to use the search interface.

## Testing

```bash
# Run all tests
pytest

# Run e2e tests only
pytest tests/e2e/

# Run unit tests only
pytest tests/unit/
```

## Architecture

See [research/ARCHITECTURE.md](research/ARCHITECTURE.md) for detailed architecture documentation.

## Development

- Follow PEP 8 coding standards
- Use type hints for public functions
- Add logging for important operations
- Handle exceptions gracefully
- Write e2e tests for workflows
- Unit tests for critical modules only

## License

MIT

