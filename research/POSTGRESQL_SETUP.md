# PostgreSQL Setup Guide

## Quick Setup Options

### Option 1: Use SQLite for Development (Easiest)

If you just want to test the application, use SQLite:

```bash
python setup_database.py
# Choose 'y' when prompted to use SQLite
```

**Note:** SQLite works for testing but doesn't support advanced full-text search features. Use PostgreSQL for production.

### Option 2: Install PostgreSQL

## Windows Installation

### Method 1: Installer (Recommended)

1. **Download PostgreSQL:**
   - Visit: https://www.postgresql.org/download/windows/
   - Download the installer from EnterpriseDB
   - Run the installer

2. **Installation Steps:**
   - Choose installation directory (default is fine)
   - Select components: PostgreSQL Server, pgAdmin 4, Command Line Tools
   - Set password for `postgres` user (remember this!)
   - Port: 5432 (default)
   - Locale: Default

3. **Start PostgreSQL Service:**
   ```powershell
   # Open Services
   services.msc
   
   # Find "postgresql-x64-XX" service
   # Right-click -> Start
   ```

   Or use PowerShell:
   ```powershell
   Start-Service postgresql-x64-16  # Adjust version number
   ```

4. **Create Database:**
   ```powershell
   # Open psql (in PostgreSQL bin directory)
   psql -U postgres
   
   # Create database
   CREATE DATABASE aphorium;
   \q
   ```

### Method 2: Using Chocolatey

```powershell
choco install postgresql
```

## Linux Installation

### Ubuntu/Debian

```bash
# Install PostgreSQL
sudo apt-get update
sudo apt-get install postgresql postgresql-contrib

# Start service
sudo systemctl start postgresql
sudo systemctl enable postgresql

# Create database
sudo -u postgres psql
CREATE DATABASE aphorium;
\q
```

### Fedora/RHEL

```bash
sudo dnf install postgresql postgresql-server
sudo postgresql-setup --initdb
sudo systemctl start postgresql
sudo systemctl enable postgresql
```

## Mac Installation

### Using Homebrew

```bash
# Install PostgreSQL
brew install postgresql@16

# Start service
brew services start postgresql@16

# Create database
createdb aphorium
```

## Verify Installation

Test PostgreSQL connection:

```bash
# Windows
psql -U postgres -d aphorium

# Linux/Mac
psql -U postgres -d aphorium
```

If you can connect, PostgreSQL is working!

## Configure .env File

After PostgreSQL is running, update your `.env` file:

```env
DATABASE_URL=postgresql://postgres:YOUR_PASSWORD@localhost:5432/aphorium
```

Replace `YOUR_PASSWORD` with the password you set during installation.

## Common Issues

### "Connection refused"

**Cause:** PostgreSQL service is not running.

**Fix:**
- Windows: Start the PostgreSQL service in Services
- Linux: `sudo systemctl start postgresql`
- Mac: `brew services start postgresql@16`

### "Authentication failed"

**Cause:** Wrong password in `.env` file.

**Fix:** Update `DATABASE_URL` in `.env` with correct password.

### "Database does not exist"

**Cause:** Database `aphorium` hasn't been created.

**Fix:**
```sql
psql -U postgres
CREATE DATABASE aphorium;
\q
```

### "Role does not exist"

**Cause:** User doesn't exist or wrong username.

**Fix:**
```sql
psql -U postgres
CREATE USER your_username WITH PASSWORD 'your_password';
ALTER USER your_username CREATEDB;
\q
```

## Quick Test

After setup, test the connection:

```bash
python setup_database.py
```

This will check your PostgreSQL connection and guide you through setup.

