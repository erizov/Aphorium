"""
Quick setup script to use SQLite for development.

Run this if PostgreSQL is not available.
"""

import os
from pathlib import Path
from sqlalchemy import create_engine
from database import Base, init_db
from logger_config import logger

# Set SQLite database URL
db_path = Path("aphorium.db")
sqlite_url = f"sqlite:///{db_path.absolute()}"

# Update environment
os.environ["DATABASE_URL"] = sqlite_url

# Update database engine
from database import engine
engine = create_engine(sqlite_url, pool_pre_ping=True, echo=False)

# Update .env file
env_file = Path(".env")
if env_file.exists():
    content = env_file.read_text(encoding="utf-8")
    lines = content.split("\n")
    new_lines = []
    updated = False
    for line in lines:
        if line.startswith("DATABASE_URL="):
            new_lines.append(f"DATABASE_URL={sqlite_url}")
            updated = True
        else:
            new_lines.append(line)
    if not updated:
        new_lines.append(f"DATABASE_URL={sqlite_url}")
    env_file.write_text("\n".join(new_lines), encoding="utf-8")
else:
    env_file.write_text(f"DATABASE_URL={sqlite_url}\n", encoding="utf-8")

print("Setting up SQLite database...")
print(f"Database file: {db_path.absolute()}")

# Create tables
Base.metadata.create_all(bind=engine)

print("[OK] SQLite database initialized successfully!")
print()
print("Note: SQLite doesn't support advanced full-text search.")
print("For production with better search performance, use PostgreSQL.")
print()
print("To switch to PostgreSQL later:")
print("1. Install and start PostgreSQL")
print("2. Update DATABASE_URL in .env")
print("3. Run: python init_database.py")

