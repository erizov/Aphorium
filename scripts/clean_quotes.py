"""
Script to clean up quotes by removing references, citations, and non-quote entries.

Removes:
- Citations like "Can Socialists Be Happy?", Tribune (20 December 1943)
- References like "The English People" (written Spring 1944, published 1947)[2]
- Publication info like "Letter to Thomas Beard (11 January 1835), in..."
- Short entries that are just titles or metadata
"""

import re
import sys
from pathlib import Path
from typing import List, Tuple

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from database import SessionLocal
from models import Quote, Author
from logger_config import logger


# Patterns that indicate references/citations (not actual quotes)
# Based on research of common citation patterns in English and Russian
REFERENCE_PATTERNS = [
    # Records starting with ↑ (upward arrow - footnote references)
    r'^↑',
    r'^\u2191',  # Unicode upward arrow
    
    # Records starting with "см." (Russian "see" - reference marker) - ALL of them
    r'^.*см\.',
    r'^.*См\.',
    
    # Records starting with "Категория:" (Russian "Category:")
    r'^Категория:',
    r'^категория:',
    
    # Records with "Famous Quotations" or "Quotations"
    r'^.*Famous\s+Quotations.*$',
    r'^.*Quotations.*$',
    
    # HTTP/HTTPS links (URLs)
    r'^https?://',
    r'^www\.',
    
    # Play references: Act III, scene ii, Act 1, Scene 2 (standalone or at end)
    r'^.*\bAct\s+[IVX]+,\s+scene\s+[ivx]+\s*$',  # Ends with Act III, scene ii
    r'^.*\bAct\s+\d+,\s+Scene\s+\d+\s*$',  # Ends with Act 1, Scene 2
    r'^.*\bAct\s+[IVX]+\s*$',  # Just "Act III" at end
    r'^.*,\s+Act\s+[IVX]+,\s+scene\s+[ivx]+\s*$',  # Title, Act III, scene ii
    r'^.*,\s+Act\s+\d+,\s+Scene\s+\d+\s*$',  # Title, Act 1, Scene 2
    
    # All entries starting with "Scenes,"
    r'^Scenes?,',
    r'^Scene\s*,',
    
    # All entries containing "Ch." (chapter references)
    r'.*\bCh\.\s*\d+.*',
    r'.*\bCh\s+\d+.*',
    
    # Part references (English): Part I, Part 1, Part One, Part A
    r'^Part\s+[IVX]+(?:\s*[:\-]|\s*$)',  # Part I, Part I:, Part I-
    r'^Part\s+\d+(?:\s*[:\-]|\s*$)',  # Part 1, Part 1:, Part 1-
    r'^Part\s+[A-Z](?:\s*[:\-]|\s*$)',  # Part A, Part A:, Part A-
    r'^Part\s+One(?:\s*[:\-]|\s*$)',  # Part One, Part One:
    r'^Part\s+Two(?:\s*[:\-]|\s*$)',  # Part Two
    r'^Part\s+Three(?:\s*[:\-]|\s*$)',  # Part Three
    r'^Part\s+Four(?:\s*[:\-]|\s*$)',  # Part Four
    r'^Part\s+Five(?:\s*[:\-]|\s*$)',  # Part Five
    r'.*,\s+Part\s+[IVX]+\s*$',  # Title, Part I (at end)
    r'.*,\s+Part\s+\d+\s*$',  # Title, Part 1 (at end)
    
    # Part references (Russian): Часть I, Часть 1, Часть первая
    r'^Часть\s+[IVX]+(?:\s*[:\-]|\s*$)',  # Часть I, Часть I:
    r'^Часть\s+\d+(?:\s*[:\-]|\s*$)',  # Часть 1, Часть 1:
    r'^Часть\s+[А-ЯЁ]+(?:\s*[:\-]|\s*$)',  # Часть первая, Часть вторая
    r'.*,\s+Часть\s+[IVX]+\s*$',  # Title, Часть I (at end)
    r'.*,\s+Часть\s+\d+\s*$',  # Title, Часть 1 (at end)
    
    # Chapter references (more comprehensive)
    r'^Chapter\s+[IVX]+(?:\s*[:\-]|\s*$)',  # Chapter I, Chapter I:
    r'^Chapter\s+\d+(?:\s*[:\-]|\s*$)',  # Chapter 1, Chapter 1:
    r'^Chapter\s+[A-Z](?:\s*[:\-]|\s*$)',  # Chapter A, Chapter A:
    r'.*,\s+Chapter\s+[IVX]+\s*$',  # Title, Chapter I (at end)
    r'.*,\s+Chapter\s+\d+\s*$',  # Title, Chapter 1 (at end)
    
    # Section references (English): Section 1, Section A
    r'^Section\s+[IVX]+(?:\s*[:\-]|\s*$)',  # Section I, Section I:
    r'^Section\s+\d+(?:\s*[:\-]|\s*$)',  # Section 1, Section 1:
    r'^Section\s+[A-Z](?:\s*[:\-]|\s*$)',  # Section A, Section A:
    r'.*,\s+Section\s+[IVX]+\s*$',  # Title, Section I (at end)
    r'.*,\s+Section\s+\d+\s*$',  # Title, Section 1 (at end)
    
    # Section references (Russian): Раздел 1, Секция 1
    r'^Раздел\s+\d+(?:\s*[:\-]|\s*$)',  # Раздел 1, Раздел 1:
    r'^Секция\s+\d+(?:\s*[:\-]|\s*$)',  # Секция 1, Секция 1:
    r'.*,\s+Раздел\s+\d+\s*$',  # Title, Раздел 1 (at end)
    r'.*,\s+Секция\s+\d+\s*$',  # Title, Секция 1 (at end)
    
    # Article references (English): Article 1, Article I
    r'^Article\s+[IVX]+(?:\s*[:\-]|\s*$)',  # Article I, Article I:
    r'^Article\s+\d+(?:\s*[:\-]|\s*$)',  # Article 1, Article 1:
    r'.*,\s+Article\s+[IVX]+\s*$',  # Title, Article I (at end)
    r'.*,\s+Article\s+\d+\s*$',  # Title, Article 1 (at end)
    
    # Article references (Russian): Статья 1
    r'^Статья\s+\d+(?:\s*[:\-]|\s*$)',  # Статья 1, Статья 1:
    r'.*,\s+Статья\s+\d+\s*$',  # Title, Статья 1 (at end)
    
    # Book title patterns (standalone titles without quotes, no sentence ending)
    r'^[A-ZА-ЯЁ][^.!?]{10,150}\s*\([^)]*\d{4}[^)]*\)\s*$',  # Title (Year) - no sentence
    r'^[A-ZА-ЯЁ][^.!?]{10,150},\s*[A-ZА-ЯЁ][^.!?]{5,50}\s*$',  # Title, Subtitle - no sentence
    r'^[A-ZА-ЯЁ][^.!?]{10,150}:\s*[A-ZА-ЯЁ][^.!?]{5,50}\s*$',  # Title: Subtitle - no sentence
    
    # Published as/by patterns
    r'^.*\bpublished\s+as\b.*$',
    r'^.*\bpublished\s+by\b.*$',
    r'^.*\bPublished\s+as\b.*$',
    r'^.*\bPublished\s+by\b.*$',
    
    # Volume references (English and Russian)
    r'^.*\bVol(?:ume)?\.?\s*\d+\b.*$',  # English: Vol. 3, Volume 2
    r'^.*\bТом\.?\s*\d+\b.*$',  # Russian: Том 3, Том. 2
    
    # Author with book title patterns
    r'^.*\bby\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b.*$',  # English: by Author Name Book Title
    r'^.*\bавтор[а-яё]*:\s*[А-ЯЁ][а-яё]+(?:\s+[А-ЯЁ][а-яё]+)*\b.*$',  # Russian: автор: Имя Фамилия
    
    # Publishing house names (English)
    r'^.*\b(?:Published\s+by|Publisher):?\s*[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*(?:\s+(?:Press|Publishing|House|Books?|Editions?))?\b.*$',
    r'^.*\b(?:Penguin|Random House|HarperCollins|Simon & Schuster|Macmillan|Hachette|Scholastic|Oxford University Press|Cambridge University Press|Harvard University Press|MIT Press|Princeton University Press|Yale University Press|University Press|Press,|Publishers?|Publishing|Editions?|Books?)\b.*$',
    
    # Publishing house names (Russian)
    r'^.*\b(?:Издательство|Издатель):?\s*[А-ЯЁ][а-яё]+(?:\s+[А-ЯЁ][а-яё]+)*\b.*$',  # Издательство: Название
    r'^.*\b(?:Издательство|Издатель)\s+[А-ЯЁ][а-яё]+(?:\s+[А-ЯЁ][а-яё]+)*\b.*$',
    
    # Publication citations: "Title", Publication (Date)
    r'^"[^"]+",\s+[A-Z][^,]+(?:,\s*\d{1,2}\s+\w+\s+\d{4})?\)?$',
    # References with dates: "Title" (written Date, published Date)[number]
    r'^"[^"]+"\s*\([^)]*(?:written|published|written|published)[^)]*\)\s*\[\d+\]$',
    # Letter citations: "Letter to ... (Date), in ..."
    r'^Letter\s+to\s+[^,]+,\s*\([^)]+\),\s*(?:in|as|as quoted in)',
    # Comment citations: "Comment while ... (Date), as quoted in ..."
    r'^Comment\s+(?:while|on)[^,]+,\s*\([^)]+\),\s*as quoted in',
    # Publication info: "Title" (Date), in ...
    r'^"[^"]+"\s*\([^)]+\),\s*(?:in|as|as cited|as quoted)',
    # Just publication info without quotes
    r'^[A-Z][^,]+,\s*\([^)]+\),\s*(?:in|as|as cited|as quoted)',
    # Chapter references: "Title" (Date), Ch. X or Chapter X (standalone, not part of quote)
    r'^[A-Z][^.!?]{0,80},\s*\([^)]+\),\s*Ch\.?\s*\d+\s*$',  # Must be end of string
    r'^[A-Z][^.!?]{0,80},\s*\([^)]+\),\s*Chapter\s+\d+\s*$',  # Must be end of string
    # Chapter references without quotes: Title, Ch. X
    r'^[A-Z][^.!?]{0,80},\s*Ch\.?\s*\d+\s*$',
    r'^[A-Z][^.!?]{0,80},\s*Chapter\s+\d+\s*$',
    # Russian chapter references: Гл. X, Глава X
    r'^[А-ЯЁ][^.!?]{0,80},\s*\([^)]+\),\s*Гл\.?\s*\d+\s*$',
    r'^[А-ЯЁ][^.!?]{0,80},\s*\([^)]+\),\s*Глава\s+\d+\s*$',
    r'^[А-ЯЁ][^.!?]{0,80},\s*Гл\.?\s*\d+\s*$',
    r'^[А-ЯЁ][^.!?]{0,80},\s*Глава\s+\d+\s*$',
    # Short entries that are just titles with dates
    r'^[A-ZА-ЯЁ][^.!?]{0,80}\s*\([^)]*\d{4}[^)]*\)\s*$',  # Title (Date) - no sentence ending
]

# Patterns that indicate actual quotes (keep these)
QUOTE_INDICATORS = [
    r'[.!?]',  # Has sentence ending
    r'\b(?:said|wrote|quoted|remarked|declared|stated)\b',  # Quote verbs
    r'"[^"]{20,}"',  # Long quoted text
]


def is_reference(text: str) -> bool:
    """
    Check if text is a reference/citation rather than a quote.
    
    Args:
        text: Text to check
        
    Returns:
        True if it's a reference, False if it's a quote
    """
    text = text.strip()
    
    # Too short to be a quote
    if len(text) < 20:
        return True
    
    # Check against reference patterns
    for pattern in REFERENCE_PATTERNS:
        if re.match(pattern, text, re.IGNORECASE):
            return True
    
    # Check for citation markers (English and Russian)
    citation_markers = [
        r'https?://',  # HTTP/HTTPS links
        r'www\.',  # WWW links
        r'см\.',  # Russian "see" - anywhere (ALL of them)
        r'См\.',  # Russian "See" - anywhere (ALL of them)
        
        # Category markers
        r'^Категория:',
        r'^категория:',
        
        # Quotation markers
        r'\bFamous\s+Quotations\b',
        r'\bQuotations\b',
        r'↑',  # Upward arrow (footnote reference)
        r'\u2191',  # Unicode upward arrow
        
        # Play references
        r'\bAct\s+[IVX]+,\s+scene\s+[ivx]+\b',  # Act III, scene ii
        r'\bAct\s+\d+,\s+Scene\s+\d+\b',  # Act 1, Scene 2
        r'\bAct\s+[IVX]+\b',  # Just "Act III"
        
        # Chapter references with "Scenes"
        r'^Scenes?,\s*Ch\.?\s*\d+',  # Scenes, Ch. 22
        r'^Scenes?,\s*Chapter\s+\d+',  # Scenes, Chapter 22
        
        # Published as/by
        r'\bpublished\s+as\b',
        r'\bpublished\s+by\b',
        r'\bPublished\s+as\b',
        r'\bPublished\s+by\b',
        
        # Volume references
        r'\bVol(?:ume)?\.?\s*\d+\b',  # English: Vol. 3, Volume 2
        r'\bТом\.?\s*\d+\b',  # Russian: Том 3
        
        # Author patterns
        r'\bby\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b',  # English: by Author Name
        r'\bавтор[а-яё]*:\s*[А-ЯЁ][а-яё]+(?:\s+[А-ЯЁ][а-яё]+)+\b',  # Russian: автор: Имя
        
        # Publishing houses (English)
        r'\b(?:Published\s+by|Publisher):?\s*[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*(?:\s+(?:Press|Publishing|House))?\b',
        r'\b(?:Penguin|Random House|HarperCollins|Simon & Schuster|Macmillan|Hachette|Scholastic|Oxford University Press|Cambridge University Press|Harvard University Press|MIT Press|Princeton University Press|Yale University Press|University Press|Press,|Publishers?|Publishing|Editions?|Books?)\b',
        
        # Publishing houses (Russian)
        r'\b(?:Издательство|Издатель):?\s*[А-ЯЁ][а-яё]+(?:\s+[А-ЯЁ][а-яё]+)*\b',
        r'\b(?:Издательство|Издатель)\s+[А-ЯЁ][а-яё]+(?:\s+[А-ЯЁ][а-яё]+)*\b',
        
        # Dates in parentheses
        r'\(\d{1,2}\s+\w+\s+\d{4}\)',  # English: (20 December 1943)
        r'\(\d{1,2}\s+(?:января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря)\s+\d{4}\)',  # Russian: (20 декабря 1943)
        r'\(\d{4}\)',  # Year: (1943)
        
        # Reference numbers
        r'\[\d+\]',  # [1], [2]
        
        # Citation phrases
        r',\s+in\s+',  # "in [publication]"
        r',\s+as\s+(?:quoted|cited)',  # "as quoted in"
        r'\(written\s+',  # "(written..."
        r'\(published\s+',  # "(published..."
        
        # All entries starting with "Scenes,"
        r'^Scenes?,',
        r'^Scene\s*,',
        
        # All entries containing "Ch." (chapter references)
        r'\bCh\.\s*\d+',
        r'\bCh\s+\d+',
        
        # Chapter references at end
        r',\s+Ch\.?\s*\d+\s*$',  # English: ", Ch. 3"
        r',\s+Chapter\s+\d+\s*$',  # English: ", Chapter 3"
        r',\s+Гл\.?\s*\d+\s*$',  # Russian: ", Гл. 3"
        r',\s+Глава\s+\d+\s*$',  # Russian: ", Глава 3"
        
        # Part references (English)
        r'^Part\s+[IVX]+(?:\s*[:\-]|\s*$)',
        r'^Part\s+\d+(?:\s*[:\-]|\s*$)',
        r'^Part\s+[A-Z](?:\s*[:\-]|\s*$)',
        r'^Part\s+(?:One|Two|Three|Four|Five)(?:\s*[:\-]|\s*$)',
        r',\s+Part\s+[IVX]+\s*$',
        r',\s+Part\s+\d+\s*$',
        
        # Part references (Russian)
        r'^Часть\s+[IVX]+(?:\s*[:\-]|\s*$)',
        r'^Часть\s+\d+(?:\s*[:\-]|\s*$)',
        r'^Часть\s+[А-ЯЁ]+(?:\s*[:\-]|\s*$)',
        r',\s+Часть\s+[IVX]+\s*$',
        r',\s+Часть\s+\d+\s*$',
        
        # Section references (English)
        r'^Section\s+[IVX]+(?:\s*[:\-]|\s*$)',
        r'^Section\s+\d+(?:\s*[:\-]|\s*$)',
        r'^Section\s+[A-Z](?:\s*[:\-]|\s*$)',
        r',\s+Section\s+[IVX]+\s*$',
        r',\s+Section\s+\d+\s*$',
        
        # Section references (Russian)
        r'^Раздел\s+\d+(?:\s*[:\-]|\s*$)',
        r'^Секция\s+\d+(?:\s*[:\-]|\s*$)',
        r',\s+Раздел\s+\d+\s*$',
        r',\s+Секция\s+\d+\s*$',
        
        # Article references (English)
        r'^Article\s+[IVX]+(?:\s*[:\-]|\s*$)',
        r'^Article\s+\d+(?:\s*[:\-]|\s*$)',
        r',\s+Article\s+[IVX]+\s*$',
        r',\s+Article\s+\d+\s*$',
        
        # Article references (Russian)
        r'^Статья\s+\d+(?:\s*[:\-]|\s*$)',
        r',\s+Статья\s+\d+\s*$',
    ]
    
    for marker in citation_markers:
        if re.search(marker, text, re.IGNORECASE):
            # For HTTP links, upward arrows, "см." anywhere, categories, and quotations, always consider as reference
            if marker in [r'https?://', r'www\.', r'см\.', r'См\.', r'↑', r'\u2191',
                         r'^Категория:', r'^категория:',
                         r'\bFamous\s+Quotations\b', r'\bQuotations\b']:
                return True
            
            # For play references (Act, scene), always flag
            if marker in [r'\bAct\s+[IVX]+,\s+scene\s+[ivx]+\b', 
                         r'\bAct\s+\d+,\s+Scene\s+\d+\b',
                         r'\bAct\s+[IVX]+\b']:
                return True
            
            # For "Scenes," at start, always flag
            if marker in [r'^Scenes?,', r'^Scene\s*,']:
                return True
            
            # For "Ch." anywhere in text, always flag
            if marker in [r'\bCh\.\s*\d+', r'\bCh\s+\d+']:
                return True
            
            # For Part references, always flag
            if marker.startswith(r'^Part\s+') or marker.startswith(r',\s+Part\s+'):
                return True
            if marker.startswith(r'^Часть\s+') or marker.startswith(r',\s+Часть\s+'):
                return True
            
            # For Section references, always flag
            if marker.startswith(r'^Section\s+') or marker.startswith(r',\s+Section\s+'):
                return True
            if marker.startswith(r'^Раздел\s+') or marker.startswith(r'^Секция\s+') or \
               marker.startswith(r',\s+Раздел\s+') or marker.startswith(r',\s+Секция\s+'):
                return True
            
            # For Article references, always flag
            if marker.startswith(r'^Article\s+') or marker.startswith(r',\s+Article\s+'):
                return True
            if marker.startswith(r'^Статья\s+') or marker.startswith(r',\s+Статья\s+'):
                return True
            
            # For "published as/by", always flag
            if marker in [r'\bpublished\s+as\b', r'\bpublished\s+by\b',
                         r'\bPublished\s+as\b', r'\bPublished\s+by\b']:
                return True
            
            # STRICT: Reject ANY volume references
            if marker in [r'\bVol(?:ume)?\.?\s*\d+\b', r'\bТом\.?\s*\d+\b']:
                return True
            
            # STRICT: Reject ANY author patterns (likely citations)
            if marker in [r'\bby\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b', 
                         r'\bавтор[а-яё]*:\s*[А-ЯЁ][а-яё]+(?:\s+[А-ЯЁ][а-яё]+)+\b']:
                return True
            
            # STRICT: Reject ANY publishing houses
            if marker.startswith(r'\b(?:Published\s+by|Publisher)') or \
               marker.startswith(r'\b(?:Penguin|Random') or \
               marker.startswith(r'\b(?:Издательство|Издатель)'):
                return True
            
            # STRICT: Reject ANY dates in parentheses (anywhere in text)
            if marker in [r'\(\d{1,2}\s+\w+\s+\d{4}\)', 
                         r'\(\d{1,2}\s+(?:января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря)\s+\d{4}\)',
                         r'\(\d{4}\)']:
                # Reject if date appears anywhere - strict mode
                return True
            
            # For other markers, check if it's actually a quote with citation
            # If it has sentence ending before the citation, it's a quote
            elif not re.search(r'[.!?][^.!?]*' + marker, text):
                return True
    
    # Check if it looks like a quote
    for indicator in QUOTE_INDICATORS:
        if re.search(indicator, text):
            return False  # Has quote indicators, likely a real quote
    
    # If it's very short and doesn't have sentence ending, likely a reference
    if len(text) < 50 and not re.search(r'[.!?]', text):
        return True
    
    return False


def clean_quote_text(text: str) -> str:
    """
    Clean quote text by removing citation suffixes, dates, links, etc.
    
    Args:
        text: Raw quote text
        
    Returns:
        Cleaned quote text
    """
    # Remove upward arrow and everything after it (footnote references)
    text = re.sub(r'↑.*$', '', text)
    text = re.sub(r'\u2191.*$', '', text)  # Unicode upward arrow
    
    # Remove "см." anywhere (Russian "see" reference) - remove everything after it
    if re.search(r'см\.', text) or re.search(r'См\.', text):
        text = re.sub(r'см\..*$', '', text)
        text = re.sub(r'См\..*$', '', text)
    
    # Remove "Категория:" at start
    text = re.sub(r'^Категория:.*$', '', text)
    text = re.sub(r'^категория:.*$', '', text)
    
    # Remove "Famous Quotations" and "Quotations"
    text = re.sub(r'\bFamous\s+Quotations\b', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\bQuotations\b', '', text, flags=re.IGNORECASE)
    
    # Remove HTTP/HTTPS links
    text = re.sub(r'https?://[^\s]+', '', text)
    text = re.sub(r'www\.[^\s]+', '', text)
    
    # Remove play references: Act III, scene ii
    text = re.sub(r'\bAct\s+[IVX]+,\s+scene\s+[ivx]+\b', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\bAct\s+\d+,\s+Scene\s+\d+\b', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\bAct\s+[IVX]+\b', '', text, flags=re.IGNORECASE)
    
    # Remove "Scenes," at start
    text = re.sub(r'^Scenes?,\s*.*$', '', text, flags=re.IGNORECASE)
    text = re.sub(r'^Scene\s*,.*$', '', text, flags=re.IGNORECASE)
    
    # Remove "Ch." patterns anywhere in text
    text = re.sub(r'\bCh\.\s*\d+[^.!?]*', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\bCh\s+\d+[^.!?]*', '', text, flags=re.IGNORECASE)
    
    # Remove "published as/by" patterns
    text = re.sub(r'\bpublished\s+as\s+[^.!?]+', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\bpublished\s+by\s+[^.!?]+', '', text, flags=re.IGNORECASE)
    
    # Remove volume references: Vol. 3, Volume 2, Том 3
    text = re.sub(r'\bVol(?:ume)?\.?\s*\d+\b', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\bТом\.?\s*\d+\b', '', text)
    
    # Remove author patterns: by Author Name, автор: Имя
    text = re.sub(r'\bby\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\bавтор[а-яё]*:\s*[А-ЯЁ][а-яё]+(?:\s+[А-ЯЁ][а-яё]+)+\b', '', text)
    
    # Remove publishing house names (English)
    text = re.sub(r'\b(?:Published\s+by|Publisher):?\s*[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*(?:\s+(?:Press|Publishing|House|Books?|Editions?))?\b', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\b(?:Penguin|Random House|HarperCollins|Simon & Schuster|Macmillan|Hachette|Scholastic|Oxford University Press|Cambridge University Press|Harvard University Press|MIT Press|Princeton University Press|Yale University Press|University Press|Press,|Publishers?|Publishing|Editions?|Books?)\b', '', text, flags=re.IGNORECASE)
    
    # Remove publishing house names (Russian)
    text = re.sub(r'\b(?:Издательство|Издатель):?\s*[А-ЯЁ][а-яё]+(?:\s+[А-ЯЁ][а-яё]+)*\b', '', text)
    text = re.sub(r'\b(?:Издательство|Издатель)\s+[А-ЯЁ][а-яё]+(?:\s+[А-ЯЁ][а-яё]+)*\b', '', text)
    
    # Remove citation patterns at the end (more aggressive)
    # Pattern: "quote text", Publication (Date), in ...
    text = re.sub(r',\s+[A-Z][^,]+,\s*\([^)]+\),\s*(?:in|as|as cited|as quoted).*$', '', text)
    
    # Pattern: "quote text" (Date), in ...
    text = re.sub(r'\s*\([^)]+\),\s*(?:in|as|as cited|as quoted).*$', '', text)
    
    # Pattern: "quote text"; as quoted in ...
    text = re.sub(r';\s*as\s+(?:quoted|cited)\s+in\s+.*$', '', text, flags=re.IGNORECASE)
    
    # Pattern: "quote text", as quoted in ...
    text = re.sub(r',\s+as\s+(?:quoted|cited)\s+in\s+.*$', '', text, flags=re.IGNORECASE)
    
    # Pattern: "quote text" (Date), source, page
    text = re.sub(r',\s*\([^)]+\),\s*[A-Z][^,]+,\s*\d+.*$', '', text)
    
    # Pattern: "quote text", source (Date), page
    text = re.sub(r',\s+[A-Z][^,]+,\s*\([^)]+\),\s*\d+.*$', '', text)
    
    # Pattern: "quote text", source, page
    text = re.sub(r',\s+[A-Z][^,]+,\s+\d+:\s*\d+.*$', '', text)  # e.g., "source, 83: 696"
    text = re.sub(r',\s+[A-Z][^,]+,\s+p\.?\s*\d+.*$', '', text, flags=re.IGNORECASE)  # e.g., "source, p. 123"
    
    # Remove dates in parentheses at the end: (1943), (20 December 1943), (20 декабря 1943)
    # But be careful - only remove if it looks like a citation, not part of quote
    # Pattern: text ending with (Date) and no sentence ending before it
    text = re.sub(r'([^.!?])\s*\(\d{1,2}\s+\w+\s+\d{4}\)\s*$', r'\1', text)  # English dates
    text = re.sub(r'([^.!?])\s*\(\d{1,2}\s+(?:января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря)\s+\d{4}\)\s*$', r'\1', text)  # Russian dates
    text = re.sub(r'([^.!?])\s*\(\d{4}\)\s*$', r'\1', text)  # Year only
    
    # Remove chapter references at the end: ", Ch. 3" or ", Chapter 3" (English)
    text = re.sub(r',\s+Ch\.?\s*\d+\s*$', '', text, flags=re.IGNORECASE)
    text = re.sub(r',\s+Chapter\s+\d+\s*$', '', text, flags=re.IGNORECASE)
    
    # Remove chapter references (Russian): ", Гл. 3" or ", Глава 3"
    text = re.sub(r',\s+Гл\.?\s*\d+\s*$', '', text)
    text = re.sub(r',\s+Глава\s+\d+\s*$', '', text)
    
    # Remove Part references (English): Part I, Part 1, Part One, Part A
    text = re.sub(r'^Part\s+[IVX]+(?:\s*[:\-]|\s*$)', '', text, flags=re.IGNORECASE)
    text = re.sub(r'^Part\s+\d+(?:\s*[:\-]|\s*$)', '', text, flags=re.IGNORECASE)
    text = re.sub(r'^Part\s+[A-Z](?:\s*[:\-]|\s*$)', '', text, flags=re.IGNORECASE)
    text = re.sub(r'^Part\s+(?:One|Two|Three|Four|Five)(?:\s*[:\-]|\s*$)', '', text, flags=re.IGNORECASE)
    text = re.sub(r',\s+Part\s+[IVX]+\s*$', '', text, flags=re.IGNORECASE)
    text = re.sub(r',\s+Part\s+\d+\s*$', '', text, flags=re.IGNORECASE)
    
    # Remove Part references (Russian): Часть I, Часть 1, Часть первая
    text = re.sub(r'^Часть\s+[IVX]+(?:\s*[:\-]|\s*$)', '', text)
    text = re.sub(r'^Часть\s+\d+(?:\s*[:\-]|\s*$)', '', text)
    text = re.sub(r'^Часть\s+[А-ЯЁ]+(?:\s*[:\-]|\s*$)', '', text)
    text = re.sub(r',\s+Часть\s+[IVX]+\s*$', '', text)
    text = re.sub(r',\s+Часть\s+\d+\s*$', '', text)
    
    # Remove Section references (English): Section I, Section 1, Section A
    text = re.sub(r'^Section\s+[IVX]+(?:\s*[:\-]|\s*$)', '', text, flags=re.IGNORECASE)
    text = re.sub(r'^Section\s+\d+(?:\s*[:\-]|\s*$)', '', text, flags=re.IGNORECASE)
    text = re.sub(r'^Section\s+[A-Z](?:\s*[:\-]|\s*$)', '', text, flags=re.IGNORECASE)
    text = re.sub(r',\s+Section\s+[IVX]+\s*$', '', text, flags=re.IGNORECASE)
    text = re.sub(r',\s+Section\s+\d+\s*$', '', text, flags=re.IGNORECASE)
    
    # Remove Section references (Russian): Раздел 1, Секция 1
    text = re.sub(r'^Раздел\s+\d+(?:\s*[:\-]|\s*$)', '', text)
    text = re.sub(r'^Секция\s+\d+(?:\s*[:\-]|\s*$)', '', text)
    text = re.sub(r',\s+Раздел\s+\d+\s*$', '', text)
    text = re.sub(r',\s+Секция\s+\d+\s*$', '', text)
    
    # Remove Article references (English): Article I, Article 1
    text = re.sub(r'^Article\s+[IVX]+(?:\s*[:\-]|\s*$)', '', text, flags=re.IGNORECASE)
    text = re.sub(r'^Article\s+\d+(?:\s*[:\-]|\s*$)', '', text, flags=re.IGNORECASE)
    text = re.sub(r',\s+Article\s+[IVX]+\s*$', '', text, flags=re.IGNORECASE)
    text = re.sub(r',\s+Article\s+\d+\s*$', '', text, flags=re.IGNORECASE)
    
    # Remove Article references (Russian): Статья 1
    text = re.sub(r'^Статья\s+\d+(?:\s*[:\-]|\s*$)', '', text)
    text = re.sub(r',\s+Статья\s+\d+\s*$', '', text)
    
    # Pattern: Title (Date), Ch. X (at end) - English
    text = re.sub(r',\s*\([^)]+\),\s*Ch\.?\s*\d+\s*$', '', text, flags=re.IGNORECASE)
    text = re.sub(r',\s*\([^)]+\),\s*Chapter\s+\d+\s*$', '', text, flags=re.IGNORECASE)
    
    # Pattern: Title (Date), Гл. X (at end) - Russian
    text = re.sub(r',\s*\([^)]+\),\s*Гл\.?\s*\d+\s*$', '', text)
    text = re.sub(r',\s*\([^)]+\),\s*Глава\s+\d+\s*$', '', text)
    
    # Remove reference numbers at the end: [1], [2], etc.
    text = re.sub(r'\s*\[\d+\]\s*$', '', text)
    
    # Remove trailing citation info: , as quoted in ...
    text = re.sub(r',\s+as\s+(?:quoted|cited)\s+in\s+.*$', '', text, flags=re.IGNORECASE)
    
    # Remove publishing house names at the end (already handled above, but keep for safety)
    # Additional cleanup for any remaining publishing info
    text = re.sub(r',\s+(?:Press|Publishers?|Publishing|Editions?|Books?)\s*$', '', text, flags=re.IGNORECASE)
    
    # Clean up whitespace
    text = ' '.join(text.split())
    
    return text.strip()


def identify_bad_quotes(db) -> List[Tuple[int, str, str]]:
    """
    Identify quotes that are references/citations.
    
    Args:
        db: Database session
        
    Returns:
        List of (quote_id, text, reason) tuples
    """
    bad_quotes = []
    quotes = db.query(Quote).all()
    
    # Load all author names from database for pattern 3
    all_authors = db.query(Author.name).all()
    author_names = {author[0].lower() for author in all_authors}
    logger.info(f"Loaded {len(author_names)} author names for matching")
    
    # English month names
    english_months = [
        r'January', r'February', r'March', r'April', r'May', r'June',
        r'July', r'August', r'September', r'October', r'November', r'December',
        r'Jan', r'Feb', r'Mar', r'Apr', r'Jun', r'Jul', r'Aug',
        r'Sep', r'Sept', r'Oct', r'Nov', r'Dec'
    ]
    
    # Russian month names
    russian_months = [
        r'января', r'февраля', r'марта', r'апреля', r'мая', r'июня',
        r'июля', r'августа', r'сентября', r'октября', r'ноября', r'декабря',
        r'янв', r'фев', r'мар', r'апр', r'май', r'июн', r'июл',
        r'авг', r'сен', r'окт', r'ноя', r'дек'
    ]
    
    for quote in quotes:
        text = quote.text.strip()
        reason = None
        
        # Pattern 1: 4-digit numbers in parentheses (1817—1875) or (1817-1875)
        # Matches: (1817—1875), (1817-1875), (1817–1875), (1817 - 1875), (1817 – 1875)
        if re.search(r'\(\d{4}[\s]*[—–-][\s]*\d{4}\)', text):
            reason = "Contains 4-digit year range in parentheses"
        
        # Pattern 2: Dates in English or Russian format
        # English: (May 7, 2007), (May 7 2007), (7 May 2007), (May 2007)
        # Russian: (7 мая 2007), (7 мая 2007 г.), (май 2007)
        elif re.search(r'\([^)]*(?:' + '|'.join(english_months) + r')[^)]*\d{4}[^)]*\)', text, re.IGNORECASE):
            reason = "Contains date in English format"
        elif re.search(r'\([^)]*(?:' + '|'.join(russian_months) + r')[^)]*\d{4}[^)]*\)', text, re.IGNORECASE):
            reason = "Contains date in Russian format"
        # Also match patterns like (7 May 2007) or (7 мая 2007)
        elif re.search(r'\(\d{1,2}\s+(?:' + '|'.join(english_months) + r')\s+\d{4}\)', text, re.IGNORECASE):
            reason = "Contains date in English format"
        elif re.search(r'\(\d{1,2}\s+(?:' + '|'.join(russian_months) + r')\s+\d{4}\)', text, re.IGNORECASE):
            reason = "Contains date in Russian format"
        
        # Pattern 3: Contains author name (check if any word matches author name)
        elif _contains_author_name(text, author_names):
            reason = "Contains author name"
        
        # Existing patterns
        elif is_reference(text):
            reason = "Reference/citation pattern"
        elif len(text) < 20:
            reason = "Too short"
        elif not re.search(r'[.!?]', text) and len(text) < 100:
            reason = "No sentence ending, likely title"
        
        if reason:
            bad_quotes.append((quote.id, text, reason))
    
    return bad_quotes


def _contains_author_name(text: str, author_names: set) -> bool:
    """
    Check if text contains any author name.
    
    Args:
        text: Quote text to check
        author_names: Set of author names (lowercase)
        
    Returns:
        True if text contains an author name
    """
    text_lower = text.lower()
    
    # Split text into words (handle punctuation)
    words = re.findall(r'\b\w+\b', text_lower)
    
    # Check if any word matches an author name
    for word in words:
        if word in author_names:
            return True
    
    # Also check for multi-word author names (2-4 words)
    # Check all possible word combinations
    for i in range(len(words)):
        for j in range(i + 1, min(i + 5, len(words) + 1)):
            phrase = ' '.join(words[i:j])
            if phrase in author_names:
                return True
    
    return False


def clean_quotes(dry_run: bool = True) -> dict:
    """
    Clean quotes by removing references and citations.
    
    Args:
        dry_run: If True, only report what would be done
        
    Returns:
        Dictionary with statistics
    """
    db = SessionLocal()
    stats = {
        "total_quotes": 0,
        "bad_quotes_found": 0,
        "quotes_cleaned": 0,
        "quotes_deleted": 0,
        "quotes_updated": 0
    }
    
    try:
        # Get all quotes
        quotes = db.query(Quote).all()
        stats["total_quotes"] = len(quotes)
        
        logger.info(f"Analyzing {stats['total_quotes']} quotes...")
        
        # Identify bad quotes
        bad_quotes = identify_bad_quotes(db)
        stats["bad_quotes_found"] = len(bad_quotes)
        
        logger.info(f"Found {stats['bad_quotes_found']} references/citations to remove")
        
        if dry_run:
            logger.info("DRY RUN - No changes will be made")
            for quote_id, text, reason in bad_quotes[:10]:  # Show first 10
                logger.info(f"  Would delete: [{quote_id}] {text[:80]}... ({reason})")
            if len(bad_quotes) > 10:
                logger.info(f"  ... and {len(bad_quotes) - 10} more")
        else:
            # Delete bad quotes
            for quote_id, text, reason in bad_quotes:
                try:
                    quote = db.query(Quote).filter(Quote.id == quote_id).first()
                    if quote:
                        db.delete(quote)
                        stats["quotes_deleted"] += 1
                except Exception as e:
                    logger.warning(f"Failed to delete quote {quote_id}: {e}")
            
            # Clean remaining quotes (remove citation suffixes)
            cleaned_count = 0
            for quote in quotes:
                original_text = quote.text
                cleaned_text = clean_quote_text(original_text)
                
                if cleaned_text != original_text and len(cleaned_text) > 20:
                    quote.text = cleaned_text
                    stats["quotes_updated"] += 1
                    cleaned_count += 1
            
            db.commit()
            stats["quotes_cleaned"] = cleaned_count
            logger.info(f"Deleted {stats['quotes_deleted']} bad quotes")
            logger.info(f"Cleaned {stats['quotes_updated']} quotes")
        
        return stats
        
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to clean quotes: {e}")
        raise
    finally:
        db.close()


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Clean quotes by removing references and citations"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only report what would be done (default: True)"
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually perform the cleanup (default: dry-run)"
    )
    
    args = parser.parse_args()
    
    dry_run = not args.execute
    
    logger.info("=" * 60)
    logger.info("Quote Cleanup Script")
    logger.info("=" * 60)
    
    stats = clean_quotes(dry_run=dry_run)
    
    logger.info("=" * 60)
    logger.info("Summary:")
    logger.info(f"  Total quotes: {stats['total_quotes']}")
    logger.info(f"  Bad quotes found: {stats['bad_quotes_found']}")
    if not dry_run:
        logger.info(f"  Quotes deleted: {stats['quotes_deleted']}")
        logger.info(f"  Quotes cleaned: {stats['quotes_updated']}")
    logger.info("=" * 60)
    
    if dry_run:
        logger.info("\nTo actually perform cleanup, run with --execute flag")


if __name__ == "__main__":
    main()

