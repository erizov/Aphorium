# PostgreSQL Migration Plan

## Overview

This document provides a step-by-step plan to migrate Aphorium from SQLite to PostgreSQL for better performance, scalability, and advanced full-text search capabilities.

## Prerequisites

- Current database: SQLite with ~17,000+ quotes
- Target: PostgreSQL with full-text search
- Estimated migration time: 30-60 minutes

## Step 1: PostgreSQL Installation and Account Setup

### 1.1 Install PostgreSQL

**Windows:**
1. Download PostgreSQL installer from: https://www.postgresql.org/download/windows/
2. Run installer (recommended version: 14+)
3. During installation:
   - Set password for `postgres` superuser (remember this!)
   - Port: 5432 (default)
   - Locale: Default
   - Install pgAdmin 4 (optional but helpful)

**Linux (Ubuntu/Debian):**
```bash
sudo apt-get update
sudo apt-get install postgresql postgresql-contrib
sudo systemctl start postgresql
sudo systemctl enable postgresql
```

**Mac:**
```bash
brew install postgresql@14
brew services start postgresql@14
```

### 1.2 Verify Installation

```bash
# Windows (in PostgreSQL bin directory or add to PATH)
psql --version

# Linux/Mac
psql --version
```

### 1.3 Create Database and User

```bash
# Connect as postgres user
psql -U postgres

# In psql prompt:
CREATE DATABASE aphorium;
CREATE USER aphorium_user WITH PASSWORD 'your_secure_password';
GRANT ALL PRIVILEGES ON DATABASE aphorium TO aphorium_user;
\q
```

### 1.4 Test Connection

```bash
psql -U aphorium_user -d aphorium -h localhost
# Enter password when prompted
# Type \q to exit
```

## Step 2: Update Configuration

### 2.1 Update .env File

Edit `.env` file:

```env
# Change from SQLite:
# DATABASE_URL=sqlite:///aphorium.db

# To PostgreSQL:
DATABASE_URL=postgresql://aphorium_user:your_secure_password@localhost:5432/aphorium
```

### 2.2 Verify Connection

```bash
python -c "from database import engine; engine.connect(); print('Connection successful!')"
```

## Step 3: Data Migration

### 3.1 Export Data from SQLite

Create export script `export_sqlite_data.py`:

```python
"""Export data from SQLite for migration."""
import json
from database import SessionLocal
from models import Quote, Author, Source, QuoteTranslation

db = SessionLocal()

# Export authors
authors = db.query(Author).all()
authors_data = [{
    'name': a.name,
    'language': a.language,
    'bio': a.bio,
    'wikiquote_url': a.wikiquote_url
} for a in authors]

# Export sources
sources = db.query(Source).all()
sources_data = [{
    'title': s.title,
    'language': s.language,
    'author_id': s.author_id,
    'source_type': s.source_type,
    'wikiquote_url': s.wikiquote_url
} for s in sources]

# Export quotes
quotes = db.query(Quote).all()
quotes_data = [{
    'text': q.text,
    'author_id': q.author_id,
    'source_id': q.source_id,
    'language': q.language
} for q in quotes]

# Export translations
translations = db.query(QuoteTranslation).all()
translations_data = [{
    'quote_id': t.quote_id,
    'translated_quote_id': t.translated_quote_id,
    'confidence': t.confidence
} for t in translations]

# Save to JSON
with open('migration_data.json', 'w', encoding='utf-8') as f:
    json.dump({
        'authors': authors_data,
        'sources': sources_data,
        'quotes': quotes_data,
        'translations': translations_data
    }, f, ensure_ascii=False, indent=2)

print(f"Exported: {len(authors_data)} authors, {len(sources_data)} sources, "
      f"{len(quotes_data)} quotes, {len(translations_data)} translations")
db.close()
```

### 3.2 Initialize PostgreSQL Database

```bash
python init_database.py
```

This will create all tables with PostgreSQL-specific features (tsvector, etc.).

### 3.3 Import Data to PostgreSQL

Create import script `import_postgresql_data.py`:

```python
"""Import data to PostgreSQL."""
import json
from database import SessionLocal
from repositories.author_repository import AuthorRepository
from repositories.source_repository import SourceRepository
from repositories.quote_repository import QuoteRepository
from repositories.translation_repository import TranslationRepository

db = SessionLocal()

# Load data
with open('migration_data.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

# Import authors (create mapping)
author_repo = AuthorRepository(db)
author_map = {}  # old_id -> new_id

for author_data in data['authors']:
    author = author_repo.get_or_create(
        name=author_data['name'],
        language=author_data['language'],
        bio=author_data.get('bio'),
        wikiquote_url=author_data.get('wikiquote_url')
    )
    # Note: We can't map old IDs, so we'll match by name+language
    author_map[author_data['name'] + '|' + author_data['language']] = author.id

db.commit()

# Import sources
source_repo = SourceRepository(db)
source_map = {}

for source_data in data['sources']:
    author_id = None
    if source_data.get('author_id'):
        # Find author by name (from original data)
        # This is simplified - you may need better mapping
        pass
    
    source = source_repo.get_or_create(
        title=source_data['title'],
        language=source_data['language'],
        author_id=author_id,
        source_type=source_data.get('source_type'),
        wikiquote_url=source_data.get('wikiquote_url')
    )
    source_map[source_data['title'] + '|' + source_data['language']] = source.id

db.commit()

# Import quotes
quote_repo = QuoteRepository(db)
quote_map = {}  # old_id -> new_id

for idx, quote_data in enumerate(data['quotes']):
    quote = quote_repo.create(
        text=quote_data['text'],
        author_id=quote_data.get('author_id'),
        source_id=quote_data.get('source_id'),
        language=quote_data['language']
    )
    quote_map[idx] = quote.id  # Using index as old ID
    
    if (idx + 1) % 1000 == 0:
        db.commit()
        print(f"Imported {idx + 1} quotes...")

db.commit()

# Import translations
translation_repo = TranslationRepository(db)
for trans_data in data['translations']:
    old_q1 = trans_data['quote_id']
    old_q2 = trans_data['translated_quote_id']
    
    # Map old IDs to new IDs (simplified - may need better mapping)
    # This is complex - you may need to export with better ID tracking
    
print("Migration complete!")
db.close()
```

**Note:** The ID mapping is simplified. For production, use a more robust mapping strategy.

### 3.4 Alternative: Direct SQL Migration

For simpler migration, use SQL dump:

```bash
# Export from SQLite
sqlite3 aphorium.db .dump > sqlite_dump.sql

# Convert and import to PostgreSQL
# (Requires manual editing or conversion tool)
```

## Step 4: Update Start/Stop Scripts

### 4.1 Update start_app.ps1

Add PostgreSQL check:

```powershell
# Check PostgreSQL connection
Write-Host "Checking PostgreSQL..." -ForegroundColor Cyan
$dbUrl = (Get-Content .env | Select-String "DATABASE_URL").ToString()
if ($dbUrl -like "*postgresql*") {
    Write-Host "Using PostgreSQL database" -ForegroundColor Green
    # Optional: Check if PostgreSQL service is running
    $pgService = Get-Service -Name "postgresql*" -ErrorAction SilentlyContinue
    if (-not $pgService -or $pgService.Status -ne "Running") {
        Write-Host "Warning: PostgreSQL service may not be running" -ForegroundColor Yellow
    }
} else {
    Write-Host "Using SQLite database" -ForegroundColor Cyan
}
```

### 4.2 Update start_app.sh

Add similar PostgreSQL check for Linux/Mac.

### 4.3 Update stop_app.ps1

No changes needed (stops API server, not database).

## Step 5: Verify Migration

### 5.1 Check Data Counts

```python
from database import SessionLocal
from models import Quote, Author, Source

db = SessionLocal()
print(f"Authors: {db.query(Author).count()}")
print(f"Sources: {db.query(Source).count()}")
print(f"Quotes: {db.query(Quote).count()}")
db.close()
```

### 5.2 Test Search

```bash
# Start server
.\start_app.ps1

# Test search endpoint
curl "http://localhost:8000/api/quotes/search?q=love&limit=10"
```

### 5.3 Verify Full-Text Search

```sql
-- Connect to PostgreSQL
psql -U aphorium_user -d aphorium

-- Test full-text search
SELECT text, ts_rank(search_vector, plainto_tsquery('simple', 'love')) as rank
FROM quotes
WHERE search_vector @@ plainto_tsquery('simple', 'love')
ORDER BY rank DESC
LIMIT 10;
```

## Step 6: Performance Optimization

### 6.1 Create Indexes

```sql
-- Already created by init_database.py, but verify:
\di quotes*

-- Should see:
-- idx_quotes_search_vector (GIN)
-- idx_quotes_language
-- idx_quotes_author
```

### 6.2 Tune PostgreSQL

Edit `postgresql.conf` (usually in data directory):

```conf
# Memory settings
shared_buffers = 256MB
effective_cache_size = 1GB
work_mem = 16MB
maintenance_work_mem = 128MB

# Full-text search
default_text_search_config = 'simple'
```

Restart PostgreSQL after changes.

## Step 7: Backup Strategy

### 7.1 Create Backup Script

Create `backup_database.ps1`:

```powershell
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$backupFile = "backups/aphorium_backup_$timestamp.sql"

New-Item -ItemType Directory -Path "backups" -Force | Out-Null

pg_dump -U aphorium_user -d aphorium -F c -f $backupFile

Write-Host "Backup created: $backupFile"
```

### 7.2 Restore Script

Create `restore_database.ps1`:

```powershell
param([string]$backupFile)

if (-not $backupFile) {
    Write-Host "Usage: .\restore_database.ps1 <backup_file>"
    exit
}

pg_restore -U aphorium_user -d aphorium -c $backupFile
Write-Host "Database restored from $backupFile"
```

## Troubleshooting

### Connection Issues

**Error: "Connection refused"**
- Check PostgreSQL service is running
- Verify port 5432 is open
- Check firewall settings

**Error: "Authentication failed"**
- Verify username/password in .env
- Check pg_hba.conf for authentication method

### Performance Issues

**Slow searches:**
- Verify GIN index exists: `\di quotes*`
- Run ANALYZE: `ANALYZE quotes;`
- Check query plans: `EXPLAIN ANALYZE SELECT ...`

### Data Issues

**Missing data:**
- Check migration logs
- Verify import script completed
- Compare counts between SQLite and PostgreSQL

## Rollback Plan

If migration fails:

1. Keep SQLite database file (`aphorium.db`)
2. Revert `.env` to SQLite URL
3. Restart application
4. Fix issues and retry migration

## Post-Migration Checklist

- [ ] PostgreSQL installed and running
- [ ] Database and user created
- [ ] .env updated with PostgreSQL URL
- [ ] Data migrated successfully
- [ ] Search functionality working
- [ ] Full-text search indexes created
- [ ] Performance acceptable
- [ ] Backup strategy in place
- [ ] Start/stop scripts updated
- [ ] Documentation updated

## Next Steps

After successful migration:

1. Monitor performance
2. Optimize queries as needed
3. Set up automated backups
4. Consider read replicas for scaling
5. Implement connection pooling if needed

## Resources

- PostgreSQL Documentation: https://www.postgresql.org/docs/
- Full-Text Search: https://www.postgresql.org/docs/current/textsearch.html
- Performance Tuning: https://www.postgresql.org/docs/current/performance-tips.html

