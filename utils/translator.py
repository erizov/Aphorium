"""
Simple translation utility for common words and phrases.

For MVP, uses a basic dictionary. Can be extended with translation APIs later.
"""

# Common English-Russian translations for search
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


def translate_query(query: str) -> str:
    """
    Translate a search query to the other language.
    
    For MVP, uses a simple dictionary. Can be extended with translation APIs.
    
    Args:
        query: Search query in English or Russian
        
    Returns:
        Translated query, or original query if no translation found
    """
    if not query:
        return query
    
    query_lower = query.lower().strip()
    
    # Check for exact match
    if query_lower in TRANSLATION_DICT:
        return TRANSLATION_DICT[query_lower]
    
    # Check for multi-word phrases (simple approach)
    words = query_lower.split()
    if len(words) > 1:
        # Try to translate each word
        translated_words = []
        for word in words:
            if word in TRANSLATION_DICT:
                translated_words.append(TRANSLATION_DICT[word])
            else:
                # Keep original word if no translation found
                translated_words.append(word)
        
        # If we translated at least one word, return the translated phrase
        if any(word in TRANSLATION_DICT for word in words):
            return ' '.join(translated_words)
    
    # No translation found, return original
    return query


def get_bilingual_search_queries(query: str) -> tuple[str, str]:
    """
    Get both original and translated query for bilingual search.
    
    Args:
        query: Original search query
        
    Returns:
        Tuple of (original_query, translated_query)
    """
    translated = translate_query(query)
    
    # If translation is the same as original, it means no translation was found
    # In that case, return original for both (search will still work)
    if translated.lower() == query.lower():
        return query, query
    
    return query, translated

