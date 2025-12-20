# Database Setup Guide

## Quick Start

### Option 1: SQLite (Recommended for Testing)

**Easiest option - no PostgreSQL installation needed:**

```bash
python setup_database_sqlite.py
```

This will:
- Create a SQLite database file (`aphorium.db`)
- Update your `.env` file automatically
- Initialize all tables

**Pros:**
- No installation required
- Works immediately
- Good for development and testing

**Cons:**
- Limited full-text search capabilities
- Not recommended for production with large datasets

### Option 2: PostgreSQL (Recommended for Production)

**Better performance and full-text search:**

1. **Install PostgreSQL** (see [POSTGRESQL_SETUP.md](POSTGRESQL_SETUP.md) in this folder)

2. **Create database:**
   ```bash
   createdb aphorium
   ```

3. **Update `.env` file:**
   ```env
   DATABASE_URL=postgresql://postgres:your_password@localhost:5432/aphorium
   ```

4. **Initialize:**
   ```bash
   python init_database.py
   ```

**Pros:**
- Advanced full-text search
- Better performance
- Production-ready

**Cons:**
- Requires installation
- More setup steps

## Switching Between Databases

### From SQLite to PostgreSQL

1. Install and start PostgreSQL
2. Create database: `createdb aphorium`
3. Update `.env`: Change `DATABASE_URL` to PostgreSQL connection string
4. Run: `python init_database.py`
5. (Optional) Migrate data from SQLite if needed

### From PostgreSQL to SQLite

1. Update `.env`: Change `DATABASE_URL` to `sqlite:///aphorium.db`
2. Run: `python setup_database_sqlite.py`
3. (Optional) Export data from PostgreSQL first

## Troubleshooting

### "Connection refused"

**PostgreSQL is not running.**

**Solutions:**
- Start PostgreSQL service
- Use SQLite instead: `python setup_database_sqlite.py`
- Check `DATABASE_URL` in `.env`

### "Database does not exist"

**PostgreSQL database hasn't been created.**

**Solution:**
```bash
createdb aphorium
```

### "Authentication failed"

**Wrong password in `.env`.**

**Solution:**
Update `DATABASE_URL` in `.env` with correct password.

## Current Setup

Check your current database setup:

```bash
# Check .env file
cat .env | grep DATABASE_URL

# Check if SQLite file exists
ls aphorium.db

# Test connection
python -c "from database import engine; engine.connect(); print('OK')"
```

## Recommendations

- **Development/Testing:** Use SQLite (`setup_database_sqlite.py`)
- **Production:** Use PostgreSQL (better search performance)
- **Learning:** Start with SQLite, switch to PostgreSQL later

