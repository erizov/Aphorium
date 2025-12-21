"""
Translation utility for common words and phrases.

Uses database table for fast lookups. Falls back to dictionary for common words.
"""

from typing import Optional

# Fallback dictionary for common words (used if DB not available)
TRANSLATION_DICT = {
    # Common words
    'love': 'любовь',
    'любовь': 'love',
    'life': 'жизнь',
    'жизнь': 'life',
    'wisdom': 'мудрость',
    'мудрость': 'wisdom',
    'death': 'смерть',
    'смерть': 'death',
    'hope': 'надежда',
    'надежда': 'hope',
    'freedom': 'свобода',
    'свобода': 'freedom',
    'truth': 'истина',
    'истина': 'truth',
    'beauty': 'красота',
    'красота': 'beauty',
    'happiness': 'счастье',
    'счастье': 'happiness',
    'sorrow': 'печаль',
    'печаль': 'sorrow',
    'time': 'время',
    'время': 'time',
    'dream': 'мечта',
    'мечта': 'dream',
    'soul': 'душа',
    'душа': 'soul',
    'heart': 'сердце',
    'сердце': 'heart',
    'mind': 'ум',
    'ум': 'mind',
    'word': 'слово',
    'слово': 'word',
    'book': 'книга',
    'книга': 'book',
    'art': 'искусство',
    'искусство': 'art',
    'poetry': 'поэзия',
    'поэзия': 'poetry',
    'poet': 'поэт',
    'поэт': 'poet',
    'writer': 'писатель',
    'писатель': 'writer',
    'author': 'автор',
    'автор': 'author',
    'man': 'человек',
    'человек': 'man',
    'woman': 'женщина',
    'женщина': 'woman',
    'friend': 'друг',
    'друг': 'friend',
    'enemy': 'враг',
    'враг': 'enemy',
    'war': 'война',
    'война': 'war',
    'peace': 'мир',
    'мир': 'peace',
    'god': 'бог',
    'бог': 'god',
    'faith': 'вера',
    'вера': 'faith',
    'nature': 'природа',
    'природа': 'nature',
    'sea': 'море',
    'море': 'sea',
    'sky': 'небо',
    'небо': 'sky',
    'sun': 'солнце',
    'солнце': 'sun',
    'moon': 'луна',
    'луна': 'moon',
    'star': 'звезда',
    'звезда': 'star',
    'night': 'ночь',
    'ночь': 'night',
    'day': 'день',
    'день': 'day',
    'morning': 'утро',
    'утро': 'morning',
    'evening': 'вечер',
    'вечер': 'evening',
    'spring': 'весна',
    'весна': 'spring',
    'summer': 'лето',
    'лето': 'summer',
    'autumn': 'осень',
    'осень': 'autumn',
    'winter': 'зима',
    'зима': 'winter',
}


def translate_query(query: str, db_session=None) -> str:
    """
    Translate a search query to the other language.
    
    Uses database table for translations if available, falls back to dictionary.
    
    Args:
        query: Search query in English or Russian
        db_session: Optional database session for lookup
        
    Returns:
        Translated query, or original query if no translation found
    """
    if not query:
        return query
    
    query_lower = query.lower().strip()
    
    # Try database lookup first if session provided
    if db_session:
        try:
            from repositories.translation_word_repository import TranslationWordRepository
            repo = TranslationWordRepository(db_session)
            translation = repo.get_translation(query_lower)
            if translation:
                return translation
        except Exception:
            # Fall back to dictionary if DB lookup fails
            pass
    
    # Fallback to dictionary
    if query_lower in TRANSLATION_DICT:
        return TRANSLATION_DICT[query_lower]
    
    # Check for multi-word phrases
    words = query_lower.split()
    if len(words) > 1:
        translated_words = []
        for word in words:
            # Try DB lookup for each word
            if db_session:
                try:
                    from repositories.translation_word_repository import TranslationWordRepository
                    repo = TranslationWordRepository(db_session)
                    word_trans = repo.get_translation(word)
                    if word_trans:
                        translated_words.append(word_trans)
                        continue
                except Exception:
                    pass
            
            # Fallback to dictionary
            if word in TRANSLATION_DICT:
                translated_words.append(TRANSLATION_DICT[word])
            else:
                translated_words.append(word)
        
        # If we translated at least one word, return the translated phrase
        if any(word in TRANSLATION_DICT or (db_session and repo.get_translation(word)) 
               for word in words):
            return ' '.join(translated_words)
    
    # No translation found, return original
    return query


def get_bilingual_search_queries(query: str, db_session=None) -> tuple[str, str]:
    """
    Get both original and translated query for bilingual search.
    
    Args:
        query: Original search query
        db_session: Optional database session for translation lookup
        
    Returns:
        Tuple of (original_query, translated_query)
    """
    translated = translate_query(query, db_session)
    
    # If translation is the same as original, it means no translation was found
    # In that case, return original for both (search will still work)
    if translated.lower() == query.lower():
        return query, query
    
    return query, translated

