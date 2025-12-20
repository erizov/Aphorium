"""
Database setup helper script.

Checks PostgreSQL connection and provides helpful error messages.
Supports SQLite fallback for development.
"""

import sys
import os
from pathlib import Path

from config import settings
from logger_config import logger


def check_postgresql_connection() -> bool:
    """Check if PostgreSQL is accessible."""
    try:
        import psycopg2
        from urllib.parse import urlparse

        parsed = urlparse(settings.database_url)
        
        try:
            conn = psycopg2.connect(
                host=parsed.hostname or "localhost",
                port=parsed.port or 5432,
                user=parsed.username or "postgres",
                password=parsed.password or "postgres",
                connect_timeout=3
            )
            conn.close()
            logger.info("PostgreSQL connection successful!")
            return True
        except psycopg2.OperationalError as e:
            logger.error(f"PostgreSQL connection failed: {e}")
            return False
    except ImportError:
        logger.error("psycopg2 not installed")
        return False


def setup_sqlite() -> str:
    """
    Set up SQLite database for development.

    Returns:
        SQLite database URL
    """
    db_path = Path("aphorium.db")
    sqlite_url = f"sqlite:///{db_path.absolute()}"
    
    logger.info(f"Setting up SQLite database at: {db_path}")
    
    # Update .env file
    env_file = Path(".env")
    if env_file.exists():
        content = env_file.read_text(encoding="utf-8")
        # Update DATABASE_URL if it exists, otherwise add it
        if "DATABASE_URL=" in content:
            lines = content.split("\n")
            new_lines = []
            for line in lines:
                if line.startswith("DATABASE_URL="):
                    new_lines.append(f"DATABASE_URL={sqlite_url}")
                else:
                    new_lines.append(line)
            env_file.write_text("\n".join(new_lines), encoding="utf-8")
        else:
            env_file.write_text(
                content + f"\nDATABASE_URL={sqlite_url}\n",
                encoding="utf-8"
            )
    else:
        env_file.write_text(f"DATABASE_URL={sqlite_url}\n", encoding="utf-8")
    
    logger.info("SQLite database URL configured in .env")
    return sqlite_url


def main() -> None:
    """Main entry point."""
    print("=" * 60)
    print("Aphorium Database Setup")
    print("=" * 60)
    print()

    # Check PostgreSQL connection
    print("Checking PostgreSQL connection...")
    if check_postgresql_connection():
        print("[OK] PostgreSQL is running and accessible")
        print()
        print("Proceeding with PostgreSQL setup...")
        from init_database import main as init_main
        init_main()
        return

    # PostgreSQL not available
    print()
    print("[X] PostgreSQL is not running or not accessible")
    print()
    print("Options:")
    print("1. Install and start PostgreSQL")
    print("2. Use SQLite for development (recommended for testing)")
    print()

    choice = input("Use SQLite for development? (y/n): ").strip().lower()

    if choice in ['y', 'yes']:
        print()
        sqlite_url = setup_sqlite()
        
        # Reload config with new database URL
        os.environ["DATABASE_URL"] = sqlite_url
        from config import settings
        settings.database_url = sqlite_url
        
        # Update database.py to use new URL
        from database import engine
        from sqlalchemy import create_engine
        engine = create_engine(sqlite_url, pool_pre_ping=True)
        
        print("Initializing SQLite database...")
        from database import init_db, Base
        Base.metadata.create_all(bind=engine)
        print("✓ SQLite database initialized successfully!")
        print()
        print("Note: SQLite doesn't support full-text search indexes.")
        print("For production, use PostgreSQL for better search performance.")
    else:
        print()
        print("Please install and start PostgreSQL:")
        print()
        print("Windows:")
        print("  1. Download from: https://www.postgresql.org/download/windows/")
        print("  2. Install PostgreSQL")
        print("  3. Start PostgreSQL service:")
        print("     - Open Services (services.msc)")
        print("     - Find 'postgresql-x64-XX' service")
        print("     - Right-click -> Start")
        print()
        print("Linux:")
        print("  sudo apt-get install postgresql postgresql-contrib")
        print("  sudo systemctl start postgresql")
        print()
        print("Mac:")
        print("  brew install postgresql")
        print("  brew services start postgresql")
        print()
        print("After starting PostgreSQL, run this script again.")
        sys.exit(1)


if __name__ == "__main__":
    main()

