"""Quick script to check for duplicate wikiquote_urls."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from database import SessionLocal
from models import Author
from collections import Counter

db = SessionLocal()
authors = db.query(Author).filter(Author.wikiquote_url.isnot(None)).all()
urls = [a.wikiquote_url for a in authors]
url_counts = Counter(urls)
duplicates = {url: count for url, count in url_counts.items() if count > 1}

print(f'Total authors with wikiquote_url: {len(authors)}')
print(f'Unique URLs: {len(url_counts)}')
print(f'Duplicate URLs: {len(duplicates)}')
if duplicates:
    print('\nDuplicate URLs:')
    for url, count in list(duplicates.items())[:10]:
        print(f'  {url}: {count} authors')
        # Show author IDs
        dup_authors = [a for a in authors if a.wikiquote_url == url]
        ids = [a.id for a in dup_authors]
        print(f'    Author IDs: {ids}')

db.close()

