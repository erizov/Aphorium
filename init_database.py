"""
Initialize database with tables and indexes.

Run this script to set up the database schema.
"""

from sqlalchemy import text
from database import engine, init_db
from logger_config import logger

# Import all models to ensure they're registered with Base.metadata
from models import (  # noqa: F401
    Author, Source, Quote, QuoteTranslation, WordTranslation
)


def create_search_indexes() -> None:
    """
    Create PostgreSQL full-text search indexes.

    This function creates the GIN index for full-text search
    and sets up triggers to update search vectors automatically.
    """
    try:
        with engine.connect() as conn:
            # Create GIN index for full-text search
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_quotes_search_vector
                ON quotes USING GIN(search_vector);
            """))

            # Create function to update search vector
            # Use 'simple' config for language-agnostic search
            conn.execute(text("""
                CREATE OR REPLACE FUNCTION update_quote_search_vector()
                RETURNS TRIGGER AS $$
                BEGIN
                    -- Use 'simple' config for language-agnostic search
                    -- This works for both English and Russian
                    NEW.search_vector := to_tsvector('simple', NEW.text);
                    RETURN NEW;
                END;
                $$ LANGUAGE plpgsql;
            """))

            # Create trigger to auto-update search vector
            conn.execute(text("""
                DROP TRIGGER IF EXISTS tsvector_update_quote ON quotes;
                CREATE TRIGGER tsvector_update_quote
                BEFORE INSERT OR UPDATE ON quotes
                FOR EACH ROW
                EXECUTE FUNCTION update_quote_search_vector();
            """))

            # Update existing quotes
            conn.execute(text("""
                UPDATE quotes
                SET search_vector = to_tsvector('simple', text)
                WHERE search_vector IS NULL;
            """))

            conn.commit()
            logger.info("Search indexes and triggers created successfully")
    except Exception as e:
        logger.error(f"Failed to create search indexes: {e}")
        raise


def main() -> None:
    """Main entry point."""
    logger.info("Initializing database...")

    try:
        # Test connection first
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
        except Exception as e:
            logger.error("=" * 60)
            logger.error("Database connection failed!")
            logger.error("=" * 60)
            logger.error(f"Error: {e}")
            logger.error("")
            logger.error("Possible solutions:")
            logger.error("1. Make sure PostgreSQL is installed and running")
            logger.error("2. Check your DATABASE_URL in .env file")
            logger.error("3. Run 'python setup_database.py' for guided setup")
            logger.error("4. Use SQLite for development: python setup_database.py")
            logger.error("")
            logger.error("See POSTGRESQL_SETUP.md for detailed instructions")
            raise

        # Create tables
        init_db()

        # Add bilingual_group_id column if it doesn't exist (migration helper)
        try:
            from sqlalchemy import inspect
            inspector = inspect(engine)
            columns = [col['name'] for col in inspector.get_columns('quotes')]
            
            if 'bilingual_group_id' not in columns:
                logger.info("Adding bilingual_group_id column to quotes table...")
                with engine.connect() as conn:
                    conn.execute(text(
                        "ALTER TABLE quotes ADD COLUMN bilingual_group_id INTEGER"
                    ))
                    conn.execute(text(
                        "CREATE INDEX IF NOT EXISTS idx_quotes_bilingual_group "
                        "ON quotes(bilingual_group_id)"
                    ))
                    conn.execute(text(
                        "CREATE INDEX IF NOT EXISTS idx_quotes_group_language "
                        "ON quotes(bilingual_group_id, language)"
                    ))
                    conn.commit()
                logger.info("✅ Added bilingual_group_id column and indexes")
        except Exception as e:
            logger.warning(
                f"Could not add bilingual_group_id column: {e}. "
                "This is OK if using Alembic migrations or column already exists."
            )

        # Create search indexes (PostgreSQL specific)
        # This will fail gracefully on SQLite (used in tests)
        try:
            create_search_indexes()
        except Exception as e:
            logger.warning(
                f"Could not create PostgreSQL-specific indexes: {e}. "
                "This is OK if using SQLite for testing."
            )

        logger.info("Database initialization complete")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        raise


if __name__ == "__main__":
    main()

