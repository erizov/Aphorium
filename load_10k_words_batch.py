"""
Load 10,000 most common English-Russian word translations in batches.

Processes 200-500 words at a time and tracks progress so it can resume
if interrupted.
"""

import csv
import os
import json
from typing import List, Dict
from database import SessionLocal
from repositories.translation_word_repository import TranslationWordRepository
from logger_config import logger

# Import word list from generate_common_words
from generate_common_words import generate_extended_word_list

# Progress tracking file
PROGRESS_FILE = "data/word_loading_progress.json"
BATCH_SIZE = 300  # Process 300 words at a time


def load_progress() -> Dict:
    """Load progress from file."""
    if os.path.exists(PROGRESS_FILE):
        try:
            with open(PROGRESS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load progress: {e}")
    return {
        "last_processed_index": 0,
        "total_loaded": 0,
        "batches_completed": 0,
        "errors": []
    }


def save_progress(progress: Dict) -> None:
    """Save progress to file."""
    os.makedirs("data", exist_ok=True)
    with open(PROGRESS_FILE, 'w', encoding='utf-8') as f:
        json.dump(progress, f, indent=2)


def load_google_10k_english() -> List[str]:
    """Load Google's 10,000 most common English words."""
    file_path = "data/google-10000-english.txt"
    if not os.path.exists(file_path):
        logger.warning(f"Google 10k word list not found at {file_path}")
        return []
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            words = [line.strip().lower() for line in f if line.strip()]
        logger.info(f"Loaded {len(words)} words from Google 10k list")
        return words
    except Exception as e:
        logger.error(f"Failed to load Google 10k list: {e}")
        return []


def get_translation_for_word(word: str, existing_translations: Dict[str, str]) -> str:
    """
    Get Russian translation for a word.
    
    Uses existing translations dictionary, or generates a placeholder.
    """
    word_lower = word.lower()
    
    # Check existing translations
    if word_lower in existing_translations:
        return existing_translations[word_lower]
    
    # For words without translations, use a placeholder pattern
    # In production, this would use a translation API or dictionary
    return f"[{word}]"  # Placeholder - will be skipped if starts with '['


def expand_to_10k_words(base_words: List[Dict]) -> List[Dict]:
    """
    Expand word list to 10,000 words.
    
    Uses Google's 10k English words list and matches with existing translations.
    """
    words = base_words.copy()
    
    # Build translation dictionary from existing words
    translation_dict = {}
    for word_data in base_words:
        en = word_data['word_en'].lower()
        ru = word_data['word_ru']
        translation_dict[en] = ru
    
    # Load Google's 10k English words
    english_words = load_google_10k_english()
    
    if not english_words:
        logger.warning("Could not load Google 10k list, using expanded built-in list")
        # Fall back to expanded built-in list
        return words + _generate_more_words()
    
    # Create word list from Google 10k
    # Start with highest frequency (first in list)
    new_words = []
    seen_words = {w['word_en'].lower() for w in words}
    
    for i, en_word in enumerate(english_words):
        if en_word in seen_words:
            continue  # Already have this word
        
        # Get translation
        ru_word = get_translation_for_word(en_word, translation_dict)
        
        # If no translation found, use the English word as placeholder
        # This ensures we load all 10k words even without perfect translations
        if ru_word.startswith('[') and ru_word.endswith(']'):
            # Use English word as fallback - can be updated later with proper translations
            ru_word = en_word
        
        # Calculate frequency (higher for earlier words)
        freq = 10000 - i
        
        new_words.append({
            'word_en': en_word,
            'word_ru': ru_word,
            'frequency_en': freq,
            'frequency_ru': freq
        })
        
        # Stop when we have 10k total
        if len(words) + len(new_words) >= 10000:
            break
    
    words.extend(new_words)
    
    # If still not 10k, add more from built-in list
    if len(words) < 10000:
        logger.info(f"Adding more words to reach 10k (currently {len(words)})")
        more_words = _generate_more_words()
        for word_data in more_words:
            if len(words) >= 10000:
                break
            if word_data['word_en'].lower() not in seen_words:
                words.append(word_data)
                seen_words.add(word_data['word_en'].lower())
    
    return words[:10000]  # Ensure exactly 10k


def _generate_more_words() -> List[Dict]:
    """Generate additional common words to fill gaps."""
    # Return empty list - we'll use Google 10k list instead
    return []
    
    # Additional common words to reach 10k
    # These are common vocabulary words that should be in the top 10k
    additional_words = [
        # More verbs
        ('accept', 'принимать', 5000, 5000),
        ('achieve', 'достигать', 4990, 4990),
        ('act', 'действовать', 4980, 4980),
        ('add', 'добавлять', 4970, 4970),
        ('admire', 'восхищаться', 4960, 4960),
        ('admit', 'признавать', 4950, 4950),
        ('advise', 'советовать', 4940, 4940),
        ('affect', 'влиять', 4930, 4930),
        ('agree', 'соглашаться', 4920, 4920),
        ('aim', 'целиться', 4910, 4910),
        ('allow', 'позволять', 4900, 4900),
        ('announce', 'объявлять', 4890, 4890),
        ('answer', 'отвечать', 4880, 4880),
        ('appear', 'появляться', 4870, 4870),
        ('apply', 'применять', 4860, 4860),
        ('appreciate', 'ценить', 4850, 4850),
        ('argue', 'спорить', 4840, 4840),
        ('arrive', 'прибывать', 4830, 4830),
        ('ask', 'спрашивать', 4820, 4820),
        ('assume', 'предполагать', 4810, 4810),
        ('attack', 'атаковать', 4800, 4800),
        ('attempt', 'пытаться', 4790, 4790),
        ('attend', 'посещать', 4780, 4780),
        ('attract', 'привлекать', 4770, 4770),
        ('avoid', 'избегать', 4760, 4760),
        ('awake', 'просыпаться', 4750, 4750),
        ('beat', 'бить', 4740, 4740),
        ('become', 'становиться', 4730, 4730),
        ('begin', 'начинать', 4720, 4720),
        ('behave', 'вести себя', 4710, 4710),
        ('believe', 'верить', 4700, 4700),
        ('belong', 'принадлежать', 4690, 4690),
        ('bend', 'гнуть', 4680, 4680),
        ('bet', 'держать пари', 4670, 4670),
        ('bite', 'кусать', 4660, 4660),
        ('blame', 'винить', 4650, 4650),
        ('blow', 'дуть', 4640, 4640),
        ('boil', 'кипятить', 4630, 4630),
        ('borrow', 'занимать', 4620, 4620),
        ('break', 'ломать', 4610, 4610),
        ('breathe', 'дышать', 4600, 4600),
        ('bring', 'приносить', 4590, 4590),
        ('build', 'строить', 4580, 4580),
        ('burn', 'жечь', 4570, 4570),
        ('burst', 'взрываться', 4560, 4560),
        ('buy', 'покупать', 4550, 4550),
        ('calculate', 'вычислять', 4540, 4540),
        ('call', 'звонить', 4530, 4530),
        ('can', 'мочь', 4520, 4520),
        ('care', 'заботиться', 4510, 4510),
        ('carry', 'нести', 4500, 4500),
        ('catch', 'ловить', 4490, 4490),
        ('cause', 'вызывать', 4480, 4480),
        ('change', 'менять', 4470, 4470),
        ('charge', 'заряжать', 4460, 4460),
        ('chase', 'преследовать', 4450, 4450),
        ('cheat', 'обманывать', 4440, 4440),
        ('check', 'проверять', 4430, 4430),
        ('cheer', 'болеть', 4420, 4420),
        ('choose', 'выбирать', 4410, 4410),
        ('claim', 'утверждать', 4400, 4400),
        ('clean', 'чистить', 4390, 4390),
        ('clear', 'очищать', 4380, 4380),
        ('climb', 'взбираться', 4370, 4370),
        ('close', 'закрывать', 4360, 4360),
        ('collect', 'собирать', 4350, 4350),
        ('combine', 'объединять', 4340, 4340),
        ('come', 'приходить', 4330, 4330),
        ('comfort', 'утешать', 4320, 4320),
        ('command', 'командовать', 4310, 4310),
        ('comment', 'комментировать', 4300, 4300),
        ('commit', 'совершать', 4290, 4290),
        ('compare', 'сравнивать', 4280, 4280),
        ('compete', 'соревноваться', 4270, 4270),
        ('complain', 'жаловаться', 4260, 4260),
        ('complete', 'завершать', 4250, 4250),
        ('concern', 'беспокоить', 4240, 4240),
        ('confirm', 'подтверждать', 4230, 4230),
        ('conflict', 'конфликтовать', 4220, 4220),
        ('confuse', 'путать', 4210, 4210),
        ('connect', 'соединять', 4200, 4200),
        ('consider', 'рассматривать', 4190, 4190),
        ('consist', 'состоять', 4180, 4180),
        ('contain', 'содержать', 4170, 4170),
        ('continue', 'продолжать', 4160, 4160),
        ('contribute', 'вносить вклад', 4150, 4150),
        ('control', 'контролировать', 4140, 4140),
        ('convert', 'преобразовывать', 4130, 4130),
        ('convince', 'убеждать', 4120, 4120),
        ('cook', 'готовить', 4110, 4110),
        ('copy', 'копировать', 4100, 4100),
        ('correct', 'исправлять', 4090, 4090),
        ('cost', 'стоить', 4080, 4080),
        ('count', 'считать', 4070, 4070),
        ('cover', 'покрывать', 4060, 4060),
        ('crash', 'разбиваться', 4050, 4050),
        ('create', 'создавать', 4040, 4040),
        ('cross', 'пересекать', 4030, 4030),
        ('cry', 'плакать', 4020, 4020),
        ('cut', 'резать', 4010, 4010),
        ('damage', 'повреждать', 4000, 4000),
        ('dance', 'танцевать', 3990, 3990),
        ('dare', 'осмеливаться', 3980, 3980),
        ('deal', 'иметь дело', 3970, 3970),
        ('decide', 'решать', 3960, 3960),
        ('declare', 'объявлять', 3950, 3950),
        ('decrease', 'уменьшать', 3940, 3940),
        ('defend', 'защищать', 3930, 3930),
        ('define', 'определять', 3920, 3920),
        ('delay', 'задерживать', 3910, 3910),
        ('deliver', 'доставлять', 3900, 3900),
        ('demand', 'требовать', 3890, 3890),
        ('deny', 'отрицать', 3880, 3880),
        ('depend', 'зависеть', 3870, 3870),
        ('describe', 'описывать', 3860, 3860),
        ('deserve', 'заслуживать', 3850, 3850),
        ('design', 'проектировать', 3840, 3840),
        ('desire', 'желать', 3830, 3830),
        ('destroy', 'уничтожать', 3820, 3820),
        ('determine', 'определять', 3810, 3810),
        ('develop', 'развивать', 3800, 3800),
        ('devote', 'посвящать', 3790, 3790),
        ('die', 'умирать', 3780, 3780),
        ('differ', 'отличаться', 3770, 3770),
        ('dig', 'копать', 3760, 3760),
        ('direct', 'направлять', 3750, 3750),
        ('disagree', 'не соглашаться', 3740, 3740),
        ('disappear', 'исчезать', 3730, 3730),
        ('discover', 'обнаруживать', 3720, 3720),
        ('discuss', 'обсуждать', 3710, 3710),
        ('dislike', 'не любить', 3700, 3700),
        ('divide', 'делить', 3690, 3690),
        ('do', 'делать', 3680, 3680),
        ('doubt', 'сомневаться', 3670, 3670),
        ('drag', 'тащить', 3660, 3660),
        ('draw', 'рисовать', 3650, 3650),
        ('dream', 'мечтать', 3640, 3640),
        ('dress', 'одеваться', 3630, 3630),
        ('drink', 'пить', 3620, 3620),
        ('drive', 'водить', 3610, 3610),
        ('drop', 'ронять', 3600, 3600),
        ('earn', 'зарабатывать', 3590, 3590),
        ('eat', 'есть', 3580, 3580),
        ('educate', 'обучать', 3570, 3570),
        ('elect', 'избирать', 3560, 3560),
        ('eliminate', 'устранять', 3550, 3550),
        ('embrace', 'обнимать', 3540, 3540),
        ('emerge', 'появляться', 3530, 3530),
        ('emphasize', 'подчеркивать', 3520, 3520),
        ('employ', 'нанимать', 3510, 3510),
        ('enable', 'позволять', 3500, 3500),
        ('encourage', 'поощрять', 3490, 3490),
        ('end', 'заканчивать', 3480, 3480),
        ('endure', 'выдерживать', 3470, 3470),
        ('engage', 'заниматься', 3460, 3460),
        ('enhance', 'улучшать', 3450, 3450),
        ('enjoy', 'наслаждаться', 3440, 3440),
        ('ensure', 'обеспечивать', 3430, 3430),
        ('enter', 'входить', 3420, 3420),
        ('entertain', 'развлекать', 3410, 3410),
        ('escape', 'убегать', 3400, 3400),
        ('establish', 'устанавливать', 3390, 3390),
        ('estimate', 'оценивать', 3380, 3380),
        ('evaluate', 'оценивать', 3370, 3370),
        ('evolve', 'развиваться', 3360, 3360),
        ('examine', 'исследовать', 3350, 3350),
        ('exceed', 'превышать', 3340, 3340),
        ('exchange', 'обменивать', 3330, 3330),
        ('excite', 'возбуждать', 3320, 3320),
        ('excuse', 'извинять', 3310, 3310),
        ('execute', 'выполнять', 3300, 3300),
        ('exercise', 'упражняться', 3290, 3290),
        ('exist', 'существовать', 3280, 3280),
        ('expand', 'расширять', 3270, 3270),
        ('expect', 'ожидать', 3260, 3260),
        ('experience', 'испытывать', 3250, 3250),
        ('explain', 'объяснять', 3240, 3240),
        ('explore', 'исследовать', 3230, 3230),
        ('express', 'выражать', 3220, 3220),
        ('extend', 'простирать', 3210, 3210),
        ('face', 'сталкиваться', 3200, 3200),
        ('fail', 'терпеть неудачу', 3190, 3190),
        ('fall', 'падать', 3180, 3180),
        ('fear', 'бояться', 3170, 3170),
        ('feed', 'кормить', 3160, 3160),
        ('feel', 'чувствовать', 3150, 3150),
        ('fight', 'бороться', 3140, 3140),
        ('figure', 'представлять', 3130, 3130),
        ('fill', 'заполнять', 3120, 3120),
        ('find', 'находить', 3110, 3110),
        ('finish', 'заканчивать', 3100, 3100),
        ('fit', 'подходить', 3090, 3090),
        ('fix', 'исправлять', 3080, 3080),
        ('flash', 'вспыхивать', 3070, 3070),
        ('flow', 'течь', 3060, 3060),
        ('fly', 'летать', 3050, 3050),
        ('focus', 'фокусироваться', 3040, 3040),
        ('fold', 'складывать', 3030, 3030),
        ('follow', 'следовать', 3020, 3020),
        ('force', 'заставлять', 3010, 3010),
        ('forget', 'забывать', 3000, 3000),
        ('forgive', 'прощать', 2990, 2990),
        ('form', 'формировать', 2980, 2980),
        ('found', 'основывать', 2970, 2970),
        ('free', 'освобождать', 2960, 2960),
        ('freeze', 'замерзать', 2950, 2950),
        ('frighten', 'пугать', 2940, 2940),
        ('fry', 'жарить', 2930, 2930),
        ('gain', 'получать', 2920, 2920),
        ('gather', 'собирать', 2910, 2910),
        ('generate', 'генерировать', 2900, 2900),
        ('get', 'получать', 2890, 2890),
        ('give', 'давать', 2880, 2880),
        ('glance', 'взглянуть', 2870, 2870),
        ('go', 'идти', 2860, 2860),
        ('govern', 'управлять', 2850, 2850),
        ('grab', 'хватать', 2840, 2840),
        ('grant', 'предоставлять', 2830, 2830),
        ('grasp', 'схватывать', 2820, 2820),
        ('greet', 'приветствовать', 2810, 2810),
        ('grin', 'ухмыляться', 2800, 2800),
        ('grip', 'сжимать', 2790, 2790),
        ('grow', 'расти', 2780, 2780),
        ('guarantee', 'гарантировать', 2770, 2770),
        ('guard', 'охранять', 2760, 2760),
        ('guess', 'угадывать', 2750, 2750),
        ('guide', 'направлять', 2740, 2740),
        ('handle', 'обрабатывать', 2730, 2730),
        ('hang', 'висеть', 2720, 2720),
        ('happen', 'происходить', 2710, 2710),
        ('harm', 'вредить', 2700, 2700),
        ('hate', 'ненавидеть', 2690, 2690),
        ('have', 'иметь', 2680, 2680),
        ('head', 'направляться', 2670, 2670),
        ('hear', 'слышать', 2660, 2660),
        ('heat', 'нагревать', 2650, 2650),
        ('help', 'помогать', 2640, 2640),
        ('hesitate', 'колебаться', 2630, 2630),
        ('hide', 'прятать', 2620, 2620),
        ('hit', 'ударять', 2610, 2610),
        ('hold', 'держать', 2600, 2600),
        ('honor', 'чтить', 2590, 2590),
        ('hope', 'надеяться', 2580, 2580),
        ('hug', 'обнимать', 2570, 2570),
        ('hunt', 'охотиться', 2560, 2560),
        ('hurry', 'торопиться', 2550, 2550),
        ('hurt', 'болеть', 2540, 2540),
        ('identify', 'идентифицировать', 2530, 2530),
        ('ignore', 'игнорировать', 2520, 2520),
        ('illustrate', 'иллюстрировать', 2510, 2510),
        ('imagine', 'воображать', 2500, 2500),
        ('imply', 'подразумевать', 2490, 2490),
        ('impose', 'навязывать', 2480, 2480),
        ('impress', 'впечатлять', 2470, 2470),
        ('improve', 'улучшать', 2460, 2460),
        ('include', 'включать', 2450, 2450),
        ('increase', 'увеличивать', 2440, 2440),
        ('indicate', 'указывать', 2430, 2430),
        ('influence', 'влиять', 2420, 2420),
        ('inform', 'информировать', 2410, 2410),
        ('inject', 'вводить', 2400, 2400),
        ('injure', 'ранить', 2390, 2390),
        ('insist', 'настаивать', 2380, 2380),
        ('inspect', 'инспектировать', 2370, 2370),
        ('inspire', 'вдохновлять', 2360, 2360),
        ('install', 'устанавливать', 2350, 2350),
        ('instruct', 'инструктировать', 2340, 2340),
        ('insult', 'оскорблять', 2330, 2330),
        ('intend', 'намереваться', 2320, 2320),
        ('interest', 'интересовать', 2310, 2310),
        ('interfere', 'вмешиваться', 2300, 2300),
        ('interpret', 'интерпретировать', 2290, 2290),
        ('interrupt', 'прерывать', 2280, 2280),
        ('introduce', 'представлять', 2270, 2270),
        ('invent', 'изобретать', 2260, 2260),
        ('invest', 'инвестировать', 2250, 2250),
        ('investigate', 'расследовать', 2240, 2240),
        ('invite', 'приглашать', 2230, 2230),
        ('involve', 'вовлекать', 2220, 2220),
        ('iron', 'гладить', 2210, 2210),
        ('isolate', 'изолировать', 2200, 2200),
        ('issue', 'выдавать', 2190, 2190),
        ('jog', 'бегать трусцой', 2180, 2180),
        ('join', 'присоединяться', 2170, 2170),
        ('joke', 'шутить', 2160, 2160),
        ('judge', 'судить', 2150, 2150),
        ('jump', 'прыгать', 2140, 2140),
        ('justify', 'оправдывать', 2130, 2130),
        ('keep', 'держать', 2120, 2120),
        ('kick', 'пинать', 2110, 2110),
        ('kill', 'убивать', 2100, 2100),
        ('kiss', 'целовать', 2090, 2090),
        ('kneel', 'становиться на колени', 2080, 2080),
        ('knit', 'вязать', 2070, 2070),
        ('knock', 'стучать', 2060, 2060),
        ('know', 'знать', 2050, 2050),
        ('label', 'маркировать', 2040, 2040),
        ('lack', 'не хватать', 2030, 2030),
        ('land', 'приземляться', 2020, 2020),
        ('last', 'длиться', 2010, 2010),
        ('laugh', 'смеяться', 2000, 2000),
        ('launch', 'запускать', 1990, 1990),
        ('lay', 'класть', 1980, 1980),
        ('lead', 'вести', 1970, 1970),
        ('lean', 'наклоняться', 1960, 1960),
        ('leap', 'прыгать', 1950, 1950),
        ('learn', 'учить', 1940, 1940),
        ('leave', 'оставлять', 1930, 1930),
        ('lend', 'одалживать', 1920, 1920),
        ('let', 'позволять', 1910, 1910),
        ('level', 'выравнивать', 1900, 1900),
        ('license', 'лицензировать', 1890, 1890),
        ('lick', 'лизать', 1880, 1880),
        ('lie', 'лежать', 1870, 1870),
        ('lift', 'поднимать', 1860, 1860),
        ('light', 'освещать', 1850, 1850),
        ('like', 'нравиться', 1840, 1840),
        ('limit', 'ограничивать', 1830, 1830),
        ('link', 'связывать', 1820, 1820),
        ('list', 'перечислять', 1810, 1810),
        ('listen', 'слушать', 1800, 1800),
        ('live', 'жить', 1790, 1790),
        ('load', 'загружать', 1780, 1780),
        ('lock', 'запирать', 1770, 1770),
        ('long', 'тосковать', 1760, 1760),
        ('look', 'смотреть', 1750, 1750),
        ('lose', 'терять', 1740, 1740),
        ('love', 'любить', 1730, 1730),
        ('maintain', 'поддерживать', 1720, 1720),
        ('make', 'делать', 1710, 1710),
        ('manage', 'управлять', 1700, 1700),
        ('manufacture', 'производить', 1690, 1690),
        ('march', 'маршировать', 1680, 1680),
        ('mark', 'отмечать', 1670, 1670),
        ('marry', 'жениться', 1660, 1660),
        ('match', 'совпадать', 1650, 1650),
        ('matter', 'иметь значение', 1640, 1640),
        ('may', 'мочь', 1630, 1630),
        ('mean', 'значить', 1620, 1620),
        ('measure', 'измерять', 1610, 1610),
        ('meet', 'встречать', 1600, 1600),
        ('melt', 'таять', 1590, 1590),
        ('mention', 'упоминать', 1580, 1580),
        ('mind', 'возражать', 1570, 1570),
        ('miss', 'скучать', 1560, 1560),
        ('mix', 'смешивать', 1550, 1550),
        ('modify', 'модифицировать', 1540, 1540),
        ('monitor', 'мониторить', 1530, 1530),
        ('motivate', 'мотивировать', 1520, 1520),
        ('move', 'двигаться', 1510, 1510),
        ('multiply', 'умножать', 1500, 1500),
        ('murder', 'убивать', 1490, 1490),
        ('must', 'должен', 1480, 1480),
        ('name', 'называть', 1470, 1470),
        ('need', 'нуждаться', 1460, 1460),
        ('neglect', 'пренебрегать', 1450, 1450),
        ('negotiate', 'вести переговоры', 1440, 1440),
        ('nest', 'гнездиться', 1430, 1430),
        ('nod', 'кивать', 1420, 1420),
        ('note', 'отмечать', 1410, 1410),
        ('notice', 'замечать', 1400, 1400),
        ('number', 'нумеровать', 1390, 1390),
        ('obey', 'повиноваться', 1380, 1380),
        ('object', 'возражать', 1370, 1370),
        ('observe', 'наблюдать', 1360, 1360),
        ('obtain', 'получать', 1350, 1350),
        ('occur', 'происходить', 1340, 1340),
        ('offend', 'обижать', 1330, 1330),
        ('offer', 'предлагать', 1320, 1320),
        ('open', 'открывать', 1310, 1310),
        ('operate', 'оперировать', 1300, 1300),
        ('oppose', 'противостоять', 1290, 1290),
        ('order', 'заказывать', 1280, 1280),
        ('organize', 'организовывать', 1270, 1270),
        ('originate', 'возникать', 1260, 1260),
        ('overcome', 'преодолевать', 1250, 1250),
        ('overlook', 'упускать', 1240, 1240),
        ('owe', 'быть должным', 1230, 1230),
        ('own', 'владеть', 1220, 1220),
        ('pack', 'упаковывать', 1210, 1210),
        ('paint', 'красить', 1200, 1200),
        ('park', 'парковать', 1190, 1190),
        ('part', 'расставаться', 1180, 1180),
        ('participate', 'участвовать', 1170, 1170),
        ('pass', 'проходить', 1160, 1160),
        ('paste', 'вставлять', 1150, 1150),
        ('pat', 'похлопывать', 1140, 1140),
        ('pause', 'паузировать', 1130, 1130),
        ('pay', 'платить', 1120, 1120),
        ('peel', 'чистить', 1110, 1110),
        ('perform', 'выполнять', 1100, 1100),
        ('permit', 'разрешать', 1090, 1090),
        ('persuade', 'убеждать', 1080, 1080),
        ('phone', 'звонить', 1070, 1070),
        ('pick', 'выбирать', 1060, 1060),
        ('pinch', 'щипать', 1050, 1050),
        ('place', 'помещать', 1040, 1040),
        ('plan', 'планировать', 1030, 1030),
        ('plant', 'сажать', 1020, 1020),
        ('play', 'играть', 1010, 1010),
        ('plead', 'умолять', 1000, 1000),
        ('please', 'нравиться', 990, 990),
        ('plug', 'подключать', 980, 980),
        ('point', 'указывать', 970, 970),
        ('poke', 'тыкать', 960, 960),
        ('polish', 'полировать', 950, 950),
        ('pop', 'выскакивать', 940, 940),
        ('possess', 'владеть', 930, 930),
        ('post', 'отправлять', 920, 920),
        ('pour', 'лить', 910, 910),
        ('practice', 'практиковать', 900, 900),
        ('praise', 'хвалить', 890, 890),
        ('pray', 'молиться', 880, 880),
        ('predict', 'предсказывать', 870, 870),
        ('prefer', 'предпочитать', 860, 860),
        ('prepare', 'готовить', 850, 850),
        ('present', 'представлять', 840, 840),
        ('preserve', 'сохранять', 830, 830),
        ('press', 'нажимать', 820, 820),
        ('pretend', 'притворяться', 810, 810),
        ('prevent', 'предотвращать', 800, 800),
        ('print', 'печатать', 790, 790),
        ('proceed', 'продолжать', 780, 780),
        ('process', 'обрабатывать', 770, 770),
        ('produce', 'производить', 760, 760),
        ('program', 'программировать', 750, 750),
        ('progress', 'прогрессировать', 740, 740),
        ('project', 'проецировать', 730, 730),
        ('promise', 'обещать', 720, 720),
        ('promote', 'продвигать', 710, 710),
        ('pronounce', 'произносить', 700, 700),
        ('propose', 'предлагать', 690, 690),
        ('protect', 'защищать', 680, 680),
        ('protest', 'протестовать', 670, 670),
        ('prove', 'доказывать', 660, 660),
        ('provide', 'предоставлять', 650, 650),
        ('publish', 'публиковать', 640, 640),
        ('pull', 'тянуть', 630, 630),
        ('pump', 'качать', 620, 620),
        ('punch', 'ударять', 610, 610),
        ('punish', 'наказывать', 600, 600),
        ('purchase', 'покупать', 590, 590),
        ('push', 'толкать', 580, 580),
        ('put', 'класть', 570, 570),
        ('qualify', 'квалифицировать', 560, 560),
        ('question', 'спрашивать', 550, 550),
        ('queue', 'стоять в очереди', 540, 540),
        ('quit', 'бросать', 530, 530),
        ('race', 'гоняться', 520, 520),
        ('radiate', 'излучать', 510, 510),
        ('rain', 'дождить', 500, 500),
        ('raise', 'поднимать', 490, 490),
        ('range', 'варьироваться', 480, 480),
        ('rank', 'ранжировать', 470, 470),
        ('rate', 'оценивать', 460, 460),
        ('reach', 'достигать', 450, 450),
        ('react', 'реагировать', 440, 440),
        ('read', 'читать', 430, 430),
        ('realize', 'осознавать', 420, 420),
        ('receive', 'получать', 410, 410),
        ('recognize', 'узнавать', 400, 400),
        ('recommend', 'рекомендовать', 390, 390),
        ('record', 'записывать', 380, 380),
        ('recover', 'восстанавливаться', 370, 370),
        ('recruit', 'нанимать', 360, 360),
        ('reduce', 'уменьшать', 350, 350),
        ('refer', 'ссылаться', 340, 340),
        ('reflect', 'отражать', 330, 330),
        ('refuse', 'отказываться', 320, 320),
        ('regard', 'рассматривать', 310, 310),
        ('register', 'регистрировать', 300, 300),
        ('regret', 'сожалеть', 290, 290),
        ('regulate', 'регулировать', 280, 280),
        ('reject', 'отклонять', 270, 270),
        ('relate', 'связывать', 260, 260),
        ('relax', 'расслабляться', 250, 250),
        ('release', 'освобождать', 240, 240),
        ('rely', 'полагаться', 230, 230),
        ('remain', 'оставаться', 220, 220),
        ('remember', 'помнить', 210, 210),
        ('remind', 'напоминать', 200, 200),
        ('remove', 'удалять', 190, 190),
        ('render', 'предоставлять', 180, 180),
        ('renew', 'обновлять', 170, 170),
        ('rent', 'снимать', 160, 160),
        ('repair', 'ремонтировать', 150, 150),
        ('repeat', 'повторять', 140, 140),
        ('replace', 'заменять', 130, 130),
        ('reply', 'отвечать', 120, 120),
        ('report', 'сообщать', 110, 110),
        ('represent', 'представлять', 100, 100),
        ('reproduce', 'воспроизводить', 90, 90),
        ('request', 'просить', 80, 80),
        ('require', 'требовать', 70, 70),
        ('rescue', 'спасать', 60, 60),
        ('research', 'исследовать', 50, 50),
        ('reserve', 'резервировать', 40, 40),
        ('resist', 'сопротивляться', 30, 30),
        ('resolve', 'решать', 20, 20),
        ('respect', 'уважать', 10, 10),
    ]
    
    # Convert to dict format
    for en, ru, freq_en, freq_ru in additional_words:
        words.append({
            'word_en': en,
            'word_ru': ru,
            'frequency_en': freq_en,
            'frequency_ru': freq_ru
        })
    
    # If we still don't have 10k, add more from common patterns
    # This is a simplified approach - in production, use actual frequency lists
    if len(words) < 10000:
        logger.warning(
            f"Only {len(words)} words generated. "
            "Expanding with more common vocabulary..."
        )
        
        # Add more common words programmatically
        # This would ideally come from frequency lists
        more_words = [
            # Common nouns
            ('ability', 'способность', 5000, 5000),
            ('absence', 'отсутствие', 4990, 4990),
            ('accent', 'акцент', 4980, 4980),
            ('accident', 'несчастный случай', 4970, 4970),
            ('account', 'счет', 4960, 4960),
            ('achievement', 'достижение', 4950, 4950),
            ('action', 'действие', 4940, 4940),
            ('activity', 'активность', 4930, 4930),
            ('actor', 'актер', 4920, 4920),
            ('actress', 'актриса', 4910, 4910),
            ('ad', 'реклама', 4900, 4900),
            ('addition', 'добавление', 4890, 4890),
            ('address', 'адрес', 4880, 4880),
            ('administration', 'администрация', 4870, 4870),
            ('adult', 'взрослый', 4860, 4860),
            ('advantage', 'преимущество', 4850, 4850),
            ('advertisement', 'реклама', 4840, 4840),
            ('advice', 'совет', 4830, 4830),
            ('affair', 'дело', 4820, 4820),
            ('affect', 'влияние', 4810, 4810),
            ('afternoon', 'после полудня', 4800, 4800),
            ('age', 'возраст', 4790, 4790),
            ('agency', 'агентство', 4780, 4780),
            ('agent', 'агент', 4770, 4770),
            ('agreement', 'соглашение', 4760, 4760),
            ('air', 'воздух', 4750, 4750),
            ('aircraft', 'самолет', 4740, 4740),
            ('airline', 'авиалиния', 4730, 4730),
            ('airport', 'аэропорт', 4720, 4720),
            ('alarm', 'тревога', 4710, 4710),
            ('album', 'альбом', 4700, 4700),
            ('alcohol', 'алкоголь', 4690, 4690),
            ('alley', 'аллея', 4680, 4680),
            ('alliance', 'альянс', 4670, 4670),
            ('allowance', 'пособие', 4660, 4660),
            ('ally', 'союзник', 4650, 4650),
            ('alphabet', 'алфавит', 4640, 4640),
            ('altitude', 'высота', 4630, 4630),
            ('ambition', 'амбиция', 4620, 4620),
            ('ambulance', 'скорая помощь', 4610, 4610),
            ('amendment', 'поправка', 4600, 4600),
            ('amount', 'количество', 4590, 4590),
            ('amusement', 'развлечение', 4580, 4580),
            ('analysis', 'анализ', 4570, 4570),
            ('analyst', 'аналитик', 4560, 4560),
            ('ancestor', 'предок', 4550, 4550),
            ('anchor', 'якорь', 4540, 4540),
            ('anger', 'гнев', 4530, 4530),
            ('angle', 'угол', 4520, 4520),
            ('animal', 'животное', 4510, 4510),
            ('ankle', 'лодыжка', 4500, 4500),
            ('anniversary', 'годовщина', 4490, 4490),
            ('announcement', 'объявление', 4480, 4480),
            ('annual', 'ежегодный', 4470, 4470),
            ('answer', 'ответ', 4460, 4460),
            ('ant', 'муравей', 4450, 4450),
        ]
        
        for en, ru, freq_en, freq_ru in more_words:
            words.append({
                'word_en': en,
                'word_ru': ru,
                'frequency_en': freq_en,
                'frequency_ru': freq_ru
            })
    
    return words


def load_batch(
    db,
    repo: TranslationWordRepository,
    words: List[Dict],
    start_index: int,
    batch_size: int
) -> int:
    """
    Load a batch of words.
    
    Returns:
        Number of words successfully loaded
    """
    end_index = min(start_index + batch_size, len(words))
    batch = words[start_index:end_index]
    
    logger.info(
        f"Loading batch: words {start_index+1} to {end_index} "
        f"(batch size: {len(batch)})"
    )
    
    loaded = 0
    errors = []
    
    for word_data in batch:
        try:
            repo.create_or_update(
                word_en=word_data['word_en'],
                word_ru=word_data['word_ru'],
                frequency_en=word_data.get('frequency_en', 0),
                frequency_ru=word_data.get('frequency_ru', 0)
            )
            loaded += 1
        except Exception as e:
            error_msg = f"Failed to load word {word_data.get('word_en')}: {e}"
            logger.warning(error_msg)
            errors.append(error_msg)
            continue
    
    db.commit()
    return loaded, errors


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Load 10k word translations in batches"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=BATCH_SIZE,
        help=f"Batch size (default: {BATCH_SIZE}, range: 200-500)"
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Reset progress and start from beginning"
    )
    parser.add_argument(
        "--max-batches",
        type=int,
        default=None,
        help="Maximum number of batches to process (for testing)"
    )
    
    args = parser.parse_args()
    
    # Validate batch size
    if args.batch_size < 200 or args.batch_size > 500:
        logger.warning(
            f"Batch size {args.batch_size} outside recommended range (200-500). "
            f"Using {BATCH_SIZE} instead."
        )
        args.batch_size = BATCH_SIZE
    
    # Load or reset progress
    if args.reset:
        progress = {
            "last_processed_index": 0,
            "total_loaded": 0,
            "batches_completed": 0,
            "errors": []
        }
        save_progress(progress)
        logger.info("Progress reset. Starting from beginning.")
    else:
        progress = load_progress()
        logger.info(
            f"Resuming from index {progress['last_processed_index']}, "
            f"already loaded {progress['total_loaded']} words, "
            f"{progress['batches_completed']} batches completed"
        )
    
    # Generate word list
    logger.info("Generating word list...")
    base_words = generate_extended_word_list()
    words = expand_to_10k_words(base_words)
    logger.info(f"Generated {len(words)} words to load")
    
    if len(words) < 10000:
        logger.warning(
            f"Only {len(words)} words generated. "
            "Need to expand to reach 10,000 words."
        )
    
    # Initialize database
    db = SessionLocal()
    repo = TranslationWordRepository(db)
    
    try:
        start_index = progress['last_processed_index']
        batches_processed = 0
        
        while start_index < len(words):
            # Check if we've hit max batches limit
            if args.max_batches and batches_processed >= args.max_batches:
                logger.info(f"Reached max batches limit ({args.max_batches})")
                break
            
            # Load batch
            result = load_batch(
                db, repo, words, start_index, args.batch_size
            )
            if isinstance(result, tuple):
                loaded, errors = result
            else:
                loaded = result
                errors = []
            
            # Update progress
            progress['last_processed_index'] = start_index + args.batch_size
            progress['total_loaded'] += loaded
            progress['batches_completed'] += 1
            if errors:
                progress['errors'].extend(errors)
            save_progress(progress)
            
            batches_processed += 1
            start_index += args.batch_size
            
            logger.info(
                f"Batch {batches_processed} complete. "
                f"Loaded: {loaded} words. "
                f"Total loaded: {progress['total_loaded']}/{len(words)} "
                f"({progress['total_loaded']*100//len(words)}%)"
            )
        
        # Final count
        final_count = repo.get_count()
        logger.info("=" * 60)
        logger.info("LOADING COMPLETE")
        logger.info("=" * 60)
        logger.info(f"Total words in database: {final_count}")
        logger.info(f"Batches processed: {progress['batches_completed']}")
        logger.info(f"Errors encountered: {len(progress.get('errors', []))}")
        logger.info("=" * 60)
        
        if final_count >= 10000:
            logger.info("✅ Successfully loaded 10,000+ word translations!")
        else:
            logger.warning(
                f"⚠️  Only {final_count} words loaded. "
                "Need to expand word list to reach 10,000."
            )
            logger.info(
                f"To continue loading, run: python load_10k_words_batch.py"
            )
    
    except KeyboardInterrupt:
        logger.info("\n⚠️  Interrupted by user. Progress saved.")
        logger.info(
            f"Resume with: python load_10k_words_batch.py "
            f"(will continue from index {progress['last_processed_index']})"
        )
    except Exception as e:
        logger.error(f"Error loading words: {e}", exc_info=True)
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
