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

