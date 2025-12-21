"""
Text utility functions for quote processing and normalization.
"""

import re


def normalize_text(text: str) -> str:
    """
    Normalize quote text for storage and search.

    Args:
        text: Raw text to normalize

    Returns:
        Normalized text
    """
    if not text:
        return ""

    # Remove extra whitespace
    text = re.sub(r"\s+", " ", text)
    # Remove leading/trailing whitespace
    text = text.strip()
    # Remove quotes if entire text is quoted
    if text.startswith('"') and text.endswith('"'):
        text = text[1:-1].strip()
    if text.startswith("'") and text.endswith("'"):
        text = text[1:-1].strip()

    return text


def detect_language(text: str) -> str:
    """
    Detect if text contains Cyrillic characters (Russian).

    Args:
        text: Text to analyze

    Returns:
        'ru' if Cyrillic detected, 'en' otherwise
    """
    has_cyrillic = any('\u0400' <= char <= '\u04FF' for char in text)
    return "ru" if has_cyrillic else "en"


def is_valid_quote(text: str, min_length: int = 10) -> bool:
    """
    Check if text is a valid quote.

    Args:
        text: Text to validate
        min_length: Minimum length for a valid quote

    Returns:
        True if text is a valid quote
    """
    if not text:
        return False
    
    normalized = normalize_text(text)
    return len(normalized) >= min_length


def sanitize_search_query(query: str, max_length: int = 500) -> str:
    """
    Sanitize search query to prevent SQL injection and handle special characters.
    
    Handles special characters that could cause issues with:
    - PostgreSQL full-text search (plainto_tsquery)
    - SQLite LIKE queries
    - SQL injection attempts
    
    Args:
        query: Raw search query
        max_length: Maximum allowed query length
        
    Returns:
        Sanitized query safe for database operations
    """
    if not query:
        return ""
    
    # Limit length
    query = query[:max_length]
    
    # Remove null bytes
    query = query.replace('\x00', '')
    
    # Remove control characters except newlines and tabs
    query = ''.join(char for char in query if char.isprintable() or char in '\n\t')
    
    # Normalize whitespace (but preserve hyphens for phrases like "Dual-language")
    # Replace multiple spaces with single space, but keep hyphens
    query = re.sub(r'[ \t]+', ' ', query)
    query = query.strip()
    
    # plainto_tsquery handles most special characters automatically
    # It treats them as word separators, which is fine for our use case
    # We just need to ensure the query is not empty after sanitization
    
    return query


def escape_like_pattern(text: str) -> str:
    """
    Escape special characters for SQL LIKE patterns.
    
    Escapes: %, _, [, ], ^, \
    
    Args:
        text: Text to escape
        
    Returns:
        Escaped text safe for LIKE queries
    """
    if not text:
        return ""
    
    # Escape special LIKE characters
    # SQLite and PostgreSQL use backslash for escaping in LIKE
    escape_chars = ['%', '_', '[', ']', '^', '\\']
    result = text
    for char in escape_chars:
        result = result.replace(char, f'\\{char}')
    
    return result

