"""
Export all English quotes from database to a text file.

Reads all English quotes from the quotes table and writes them to a text file,
one quote per line.
"""

from pathlib import Path
from datetime import datetime
from sqlalchemy.orm import Session

from database import SessionLocal
from models import Quote
from logger_config import setup_logging

# Setup logging
log_file = Path("logs") / f"export_en_quotes_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
logger = setup_logging(log_level="INFO", log_file=str(log_file))


def export_english_quotes(output_file: str = None):
    """
    Export all English quotes to a text file.
    
    Args:
        output_file: Optional output file path. If None, uses timestamped filename.
    """
    if output_file is None:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_file = f"data/english_quotes_{timestamp}.txt"
    
    # Ensure output directory exists
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    logger.info("Starting export of English quotes...")
    logger.info(f"Output file: {output_file}")
    
    # Get database session
    db = SessionLocal()
    
    try:
        # Get all English quotes
        quotes = db.query(Quote).filter(Quote.language == 'en').order_by(Quote.id).all()
        
        logger.info(f"Found {len(quotes)} English quotes in database")
        
        if not quotes:
            logger.warning("No English quotes found in database")
            return
        
        # Write quotes to file
        with open(output_file, 'w', encoding='utf-8') as f:
            for idx, quote in enumerate(quotes, 1):
                # Write quote text, one per line
                f.write(quote.text.strip() + '\n')
                
                if idx % 100 == 0:
                    logger.info(f"Exported {idx}/{len(quotes)} quotes...")
        
        logger.info("=" * 60)
        logger.info("Export completed!")
        logger.info(f"Total quotes exported: {len(quotes)}")
        logger.info(f"Output file: {output_file}")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"Error exporting quotes: {e}", exc_info=True)
        raise
    finally:
        db.close()


if __name__ == "__main__":
    import sys
    
    output_file = None
    if len(sys.argv) > 1:
        output_file = sys.argv[1]
    
    export_english_quotes(output_file=output_file)


