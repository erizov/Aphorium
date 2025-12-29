"""
Translation service for quotes.

Reads quotes from the database, translates them between English and Russian using
Google Translate (via deep-translator), logs errors, and saves results to CSV.
"""

import csv
import time
from pathlib import Path
from typing import List, Tuple, Optional
from datetime import datetime

from sqlalchemy.orm import Session
from database import SessionLocal
from models import Quote
from logger_config import setup_logging

# Try to import deep-translator with multiple providers
try:
    from deep_translator import GoogleTranslator
    # Try to import optional providers (may not all be available)
    try:
        from deep_translator import DeepLTranslator
        HAS_DEEPL = True
    except ImportError:
        HAS_DEEPL = False
        DeepLTranslator = None
    
    try:
        from deep_translator import MicrosoftTranslator
        HAS_MICROSOFT = True
    except ImportError:
        HAS_MICROSOFT = False
        MicrosoftTranslator = None
    
    try:
        from deep_translator import MyMemoryTranslator
        HAS_MYMEMORY = True
    except ImportError:
        HAS_MYMEMORY = False
        MyMemoryTranslator = None
    
    try:
        from deep_translator import PonsTranslator
        HAS_PONS = True
    except ImportError:
        HAS_PONS = False
        PonsTranslator = None
    
    try:
        from deep_translator import LingueeTranslator
        HAS_LINGUEE = True
    except ImportError:
        HAS_LINGUEE = False
        LingueeTranslator = None
    
    TRANSLATION_AVAILABLE = True
except ImportError:
    TRANSLATION_AVAILABLE = False
    HAS_DEEPL = HAS_MICROSOFT = HAS_MYMEMORY = HAS_PONS = HAS_LINGUEE = False
    print("Warning: deep-translator not available. Install with: pip install deep-translator")

# Try to import langdetect for automatic language detection
try:
    from langdetect import detect, DetectorFactory
    # Ensure consistent results from langdetect
    DetectorFactory.seed = 0
    LANGDETECT_AVAILABLE = True
except ImportError:
    LANGDETECT_AVAILABLE = False
    print("Warning: langdetect not available. Install with: pip install langdetect")

# Setup logging
log_file = Path("logs") / f"translation_errors_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
logger = setup_logging(log_level="INFO", log_file=str(log_file))


class TranslationService:
    """
    Service for translating text between English and Russian.
    
    Supports multiple translation providers:
    - 'google' (default): Google Translate - free, no API key, good quality
    - 'deepl': DeepL - best quality, requires API key (free tier available)
    - 'microsoft': Microsoft Translator - good quality, requires API key
    - 'mymemory': MyMemory - free, no API key, good for short texts
    - 'pons': Pons - free, no API key, dictionary-based
    - 'linguee': Linguee - free, no API key, context-aware
    """
    
    # Provider configuration (dynamically built based on available imports)
    @classmethod
    def _get_providers(cls):
        """Get available providers based on what's imported."""
        providers = {
            'google': {
                'class': GoogleTranslator,
                'requires_key': False,
                'quality': 'good',
                'description': 'Google Translate - free, reliable, good quality',
                'available': True
            }
        }
        
        if HAS_DEEPL and DeepLTranslator:
            providers['deepl'] = {
                'class': DeepLTranslator,
                'requires_key': True,
                'quality': 'excellent',
                'description': 'DeepL - best quality, requires API key (free tier: 500k chars/month)',
                'available': True
            }
        
        if HAS_MICROSOFT and MicrosoftTranslator:
            providers['microsoft'] = {
                'class': MicrosoftTranslator,
                'requires_key': True,
                'quality': 'good',
                'description': 'Microsoft Translator - good quality, requires API key (free tier: 2M chars/month)',
                'available': True
            }
        
        if HAS_MYMEMORY and MyMemoryTranslator:
            providers['mymemory'] = {
                'class': MyMemoryTranslator,
                'requires_key': False,
                'quality': 'good',
                'description': 'MyMemory - free, no API key, good for short texts',
                'available': True
            }
        
        if HAS_PONS and PonsTranslator:
            providers['pons'] = {
                'class': PonsTranslator,
                'requires_key': False,
                'quality': 'fair',
                'description': 'Pons - free dictionary-based translation',
                'available': True
            }
        
        if HAS_LINGUEE and LingueeTranslator:
            providers['linguee'] = {
                'class': LingueeTranslator,
                'requires_key': False,
                'quality': 'good',
                'description': 'Linguee - free, context-aware translations',
                'available': True
            }
        
        return providers
    
    @property
    def PROVIDERS(self):
        """Get available providers."""
        return self._get_providers()
    
    def __init__(self, provider: str = 'google', delay: float = 0.5, api_key: Optional[str] = None):
        """
        Initialize translation service.
        
        Args:
            provider: Translation provider ('google', 'deepl', 'microsoft', 'mymemory', 'pons', 'linguee')
            delay: Delay between API requests in seconds (to avoid rate limiting)
            api_key: API key for providers that require it (DeepL, Microsoft)
        """
        if not TRANSLATION_AVAILABLE:
            raise ImportError(
                "deep-translator is not installed. "
                "Install it with: pip install deep-translator"
            )
        
        providers = self._get_providers()
        if provider not in providers:
            available = ', '.join(providers.keys())
            raise ValueError(
                f"Unknown provider: {provider}. "
                f"Available: {available}"
            )
        
        self.provider = provider
        self.provider_config = providers[provider]
        self.delay = delay
        self.api_key = api_key
        self.translator_en_ru = None
        self.translator_ru_en = None
        self._initialize_translators()
    
    def _initialize_translators(self, fallback_on_error: bool = True):
        """Initialize translator instances for both directions."""
        try:
            translator_class = self.provider_config['class']
            
            # Check if API key is required
            if self.provider_config['requires_key'] and not self.api_key:
                logger.warning(
                    f"Provider '{self.provider}' requires an API key. "
                    f"Some providers offer free tiers. Falling back to Google Translate."
                )
                translator_class = GoogleTranslator
                self.provider = 'google'
                self.provider_config = self._get_providers()['google']
            
            # Initialize translators based on provider
            if self.provider == 'deepl':
                if self.api_key:
                    try:
                        self.translator_en_ru = DeepLTranslator(
                            api_key=self.api_key, source='en', target='ru'
                        )
                        self.translator_ru_en = DeepLTranslator(
                            api_key=self.api_key, source='ru', target='en'
                        )
                        # Test DeepL availability with a simple translation
                        try:
                            test_result = self.translator_en_ru.translate("test")
                            logger.info("DeepL service is available and working")
                        except Exception as test_error:
                            error_msg = str(test_error).lower()
                            if 'region' in error_msg or 'unavailable' in error_msg or 'blocked' in error_msg:
                                raise ValueError(
                                    f"DeepL is unavailable in your region. Error: {test_error}. "
                                    f"Falling back to Google Translate."
                                )
                            else:
                                raise
                    except ValueError as ve:
                        # Region restriction or similar - fallback
                        if fallback_on_error:
                            logger.warning(str(ve))
                            logger.info("Falling back to Google Translate")
                            translator_class = GoogleTranslator
                            self.provider = 'google'
                            self.provider_config = self._get_providers()['google']
                            self.translator_en_ru = translator_class(source='en', target='ru')
                            self.translator_ru_en = translator_class(source='ru', target='en')
                        else:
                            raise
                    except Exception as e:
                        error_msg = str(e).lower()
                        if 'region' in error_msg or 'unavailable' in error_msg or 'blocked' in error_msg:
                            if fallback_on_error:
                                logger.warning(
                                    f"DeepL is unavailable in your region: {e}. "
                                    f"Falling back to Google Translate."
                                )
                                translator_class = GoogleTranslator
                                self.provider = 'google'
                                self.provider_config = self._get_providers()['google']
                                self.translator_en_ru = translator_class(source='en', target='ru')
                                self.translator_ru_en = translator_class(source='ru', target='en')
                            else:
                                raise
                        else:
                            raise
                else:
                    raise ValueError("DeepL requires an API key. Get one at https://www.deepl.com/pro-api")
            elif self.provider == 'microsoft':
                if self.api_key:
                    self.translator_en_ru = MicrosoftTranslator(
                        api_key=self.api_key, source='en', target='ru'
                    )
                    self.translator_ru_en = MicrosoftTranslator(
                        api_key=self.api_key, source='ru', target='en'
                    )
                else:
                    raise ValueError("Microsoft Translator requires an API key")
            else:
                # Google, MyMemory, Pons, Linguee don't require API keys
                self.translator_en_ru = translator_class(source='en', target='ru')
                self.translator_ru_en = translator_class(source='ru', target='en')
            
            logger.info(
                f"Translation service initialized with provider: {self.provider} "
                f"({self.provider_config['description']})"
            )
        except Exception as e:
            logger.error(f"Failed to initialize translators: {e}")
            # If fallback is enabled and we're not already on Google, try Google as fallback
            if fallback_on_error and self.provider != 'google':
                logger.info("Attempting fallback to Google Translate...")
                try:
                    self.provider = 'google'
                    self.provider_config = self._get_providers()['google']
                    self.translator_en_ru = GoogleTranslator(source='en', target='ru')
                    self.translator_ru_en = GoogleTranslator(source='ru', target='en')
                    logger.info("Successfully fell back to Google Translate")
                except Exception as fallback_error:
                    logger.error(f"Fallback to Google Translate also failed: {fallback_error}")
                    raise
            else:
                raise
    
    def translate(self, text: str, source_lang: str = 'en', target_lang: str = 'ru') -> Optional[str]:
        """
        Translate text from source language to target language.
        
        Args:
            text: Text to translate
            source_lang: Source language code ('en' or 'ru')
            target_lang: Target language code ('en' or 'ru')
            
        Returns:
            Translated text or None if error occurred
        """
        if not text or not text.strip():
            return None
        
        # Validate language codes
        if source_lang not in ['en', 'ru'] or target_lang not in ['en', 'ru']:
            logger.error(f"Invalid language codes: {source_lang} -> {target_lang}")
            return None
        
        # If same language, return original
        if source_lang == target_lang:
            return text
        
        try:
            # Select appropriate translator
            if source_lang == 'en' and target_lang == 'ru':
                translator = self.translator_en_ru
            elif source_lang == 'ru' and target_lang == 'en':
                translator = self.translator_ru_en
            else:
                logger.error(f"Unsupported translation direction: {source_lang} -> {target_lang}")
                return None
            
            # Translate text
            translated = translator.translate(text)
            
            # Add delay to avoid rate limiting
            time.sleep(self.delay)
            
            return translated.strip() if translated else None
            
        except Exception as e:
            error_msg = str(e).lower()
            # Check if it's a region/unavailability error for DeepL
            if self.provider == 'deepl' and ('region' in error_msg or 'unavailable' in error_msg or 'blocked' in error_msg):
                logger.warning(
                    f"DeepL translation failed (likely region restriction): {e}. "
                    f"Falling back to Google Translate for this request."
                )
                # Try fallback to Google for this specific request
                try:
                    fallback_translator = GoogleTranslator(source=source_lang, target=target_lang)
                    translated = fallback_translator.translate(text)
                    time.sleep(self.delay)
                    return translated.strip() if translated else None
                except Exception as fallback_error:
                    logger.error(f"Fallback translation also failed: {fallback_error}")
                    return None
            else:
                logger.error(f"Translation error for '{text[:50]}...' ({source_lang}->{target_lang}): {e}")
                return None
    
    def translate_en_to_ru(self, text: str) -> Optional[str]:
        """
        Translate English text to Russian.
        
        Args:
            text: English text to translate
            
        Returns:
            Translated Russian text or None if error occurred
        """
        return self.translate(text, source_lang='en', target_lang='ru')
    
    def translate_ru_to_en(self, text: str) -> Optional[str]:
        """
        Translate Russian text to English.
        
        Args:
            text: Russian text to translate
            
        Returns:
            Translated English text or None if error occurred
        """
        return self.translate(text, source_lang='ru', target_lang='en')
    
    def detect_language(self, text: str) -> Optional[str]:
        """
        Detect the language of the given text.
        
        Args:
            text: Text to detect language for
            
        Returns:
            Language code ('en' or 'ru') or None if detection failed
        """
        if not LANGDETECT_AVAILABLE:
            logger.warning("langdetect not available, cannot detect language")
            return None
        
        if not text or not text.strip():
            return None
        
        try:
            detected = detect(text)
            # Map langdetect codes to our language codes
            if detected == 'en':
                return 'en'
            elif detected == 'ru':
                return 'ru'
            else:
                logger.debug(f"Detected language '{detected}' is not en/ru for text: {text[:50]}...")
                return None
        except Exception as e:
            logger.error(f"Language detection error for '{text[:50]}...': {e}")
            return None
    
    def translate_with_auto_detect(self, text: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Automatically detect language and translate to the opposite language.
        
        Args:
            text: Text to translate
            
        Returns:
            Tuple of (detected_lang, translated_text, target_lang) or (None, None, None) on error
        """
        if not text or not text.strip():
            return None, None, None
        
        # Detect language
        detected_lang = self.detect_language(text)
        
        if not detected_lang:
            logger.warning(f"Could not detect language for: {text[:50]}...")
            return None, None, None
        
        # Determine target language (opposite of detected)
        target_lang = 'ru' if detected_lang == 'en' else 'en'
        
        # Translate
        translated = self.translate(text, source_lang=detected_lang, target_lang=target_lang)
        
        if translated:
            return detected_lang, translated, target_lang
        else:
            return detected_lang, None, target_lang


def get_quotes(db: Session, language: Optional[str] = None, limit: Optional[int] = None) -> List[Quote]:
    """
    Get quotes from the database, optionally filtered by language.
    
    Args:
        db: Database session
        language: Optional language code ('en' or 'ru'). If None, get all quotes.
        limit: Optional limit on number of quotes to process
        
    Returns:
        List of quotes
    """
    try:
        query = db.query(Quote)
        
        if language:
            query = query.filter(Quote.language == language)
        
        if limit:
            query = query.limit(limit)
        
        quotes = query.all()
        lang_str = f"{language.upper()} " if language else ""
        logger.info(f"Retrieved {len(quotes)} {lang_str}quotes from database")
        return quotes
    except Exception as e:
        logger.error(f"Error retrieving quotes from database: {e}")
        raise


def process_quotes(
    quotes: List[Quote],
    service: TranslationService,
    output_file: str,
    source_lang: Optional[str] = None,
    target_lang: Optional[str] = None,
    auto_detect: bool = False
) -> Tuple[int, int]:
    """
    Process quotes through translation service and save to CSV.
    
    Args:
        quotes: List of quotes to process
        service: Translation service instance
        output_file: Path to output CSV file
        source_lang: Source language ('en' or 'ru'). Required if auto_detect=False
        target_lang: Target language ('en' or 'ru'). Required if auto_detect=False
        auto_detect: If True, automatically detect language and translate to opposite
        
    Returns:
        Tuple of (successful_count, failed_count)
    """
    successful = 0
    failed = 0
    
    # Ensure output directory exists
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Open CSV file for writing
    with open(output_file, 'w', encoding='utf-8', newline='') as csvfile:
        if auto_detect:
            # Include language detection columns
            writer = csv.writer(csvfile)
            writer.writerow(['Original_Text', 'Detected_Lang', 'Translated_Text', 'Target_Lang'])
            
            total = len(quotes)
            logger.info(f"Processing {total} quotes with automatic language detection...")
            
            for idx, quote in enumerate(quotes, 1):
                source_text = quote.text.strip()
                
                if not source_text:
                    logger.warning(f"Quote ID {quote.id} has empty text, skipping")
                    failed += 1
                    continue
                
                # Auto-detect and translate
                detected_lang, translated_text, target_lang = service.translate_with_auto_detect(source_text)
                
                if translated_text and detected_lang:
                    writer.writerow([source_text, detected_lang, translated_text, target_lang])
                    successful += 1
                    if idx % 10 == 0:
                        logger.info(
                            f"Progress: {idx}/{total} quotes processed "
                            f"({successful} successful, {failed} failed)"
                        )
                else:
                    writer.writerow([source_text, detected_lang or 'unknown', '', ''])
                    failed += 1
                    logger.error(
                        f"Failed to translate quote ID {quote.id}: {source_text[:50]}..."
                    )
        else:
            # Manual language specification
            if not source_lang or not target_lang:
                raise ValueError("source_lang and target_lang are required when auto_detect=False")
            
            # Determine column names based on languages
            col1 = source_lang.upper()
            col2 = target_lang.upper()
            
            writer = csv.writer(csvfile)
            writer.writerow([col1, col2])  # Header
            
            total = len(quotes)
            logger.info(f"Processing {total} quotes ({source_lang} -> {target_lang})...")
            
            for idx, quote in enumerate(quotes, 1):
                source_text = quote.text.strip()
                
                if not source_text:
                    logger.warning(f"Quote ID {quote.id} has empty text, skipping")
                    failed += 1
                    continue
                
                # Translate
                target_text = service.translate(source_text, source_lang=source_lang, target_lang=target_lang)
                
                if target_text:
                    writer.writerow([source_text, target_text])
                    successful += 1
                    if idx % 10 == 0:
                        logger.info(
                            f"Progress: {idx}/{total} quotes processed "
                            f"({successful} successful, {failed} failed)"
                        )
                else:
                    writer.writerow([source_text, ''])  # Write empty target column on failure
                    failed += 1
                    logger.error(
                        f"Failed to translate quote ID {quote.id}: {source_text[:50]}..."
                    )
    
    return successful, failed


def main(
    limit: Optional[int] = None,
    output_file: Optional[str] = None,
    source_lang: Optional[str] = None,
    target_lang: Optional[str] = None,
    auto_detect: bool = False
):
    """
    Main function to run translation service.
    
    Args:
        limit: Optional limit on number of quotes to process
        output_file: Optional output CSV file path
        source_lang: Source language ('en' or 'ru'). Required if auto_detect=False
        target_lang: Target language ('en' or 'ru'). Required if auto_detect=False
        auto_detect: If True, automatically detect language for each quote and translate to opposite
    """
    if not TRANSLATION_AVAILABLE:
        logger.error("deep-translator is not installed. Install with: pip install deep-translator")
        return
    
    if auto_detect:
        if not LANGDETECT_AVAILABLE:
            logger.error("langdetect is not installed. Install with: pip install langdetect")
            logger.error("Cannot use auto-detect mode without langdetect")
            return
        logger.info("Using automatic language detection mode")
    else:
        # Validate language codes for manual mode
        if not source_lang or not target_lang:
            logger.error("source_lang and target_lang are required when auto_detect=False")
            return
        
        if source_lang not in ['en', 'ru'] or target_lang not in ['en', 'ru']:
            logger.error(f"Invalid language codes. Use 'en' or 'ru'")
            return
    
    if output_file is None:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        if auto_detect:
            output_file = f"data/translated_quotes_auto_{timestamp}.csv"
        else:
            lang_pair = f"{source_lang}_{target_lang}"
            output_file = f"data/translated_quotes_{lang_pair}_{timestamp}.csv"
    
    logger.info("Starting translation service...")
    if auto_detect:
        logger.info("Mode: Automatic language detection")
    else:
        logger.info(f"Translation direction: {source_lang.upper()} -> {target_lang.upper()}")
    logger.info(f"Output file: {output_file}")
    
    # Initialize service
    # Get provider from environment variable or use default
    import os
    provider = os.getenv('TRANSLATION_PROVIDER', 'google').lower()
    api_key = os.getenv('TRANSLATION_API_KEY', None)
    
    # If DeepL is selected but unavailable, warn and use Google
    if provider == 'deepl':
        logger.info("DeepL provider selected. Will automatically fallback to Google if unavailable in your region.")
    
    try:
        service = TranslationService(provider=provider, delay=0.5, api_key=api_key)
        # Log if provider was changed due to unavailability
        if provider == 'deepl' and service.provider == 'google':
            logger.warning(
                "DeepL was selected but is unavailable in your region. "
                "Using Google Translate instead. To avoid this warning, set TRANSLATION_PROVIDER=google"
            )
    except Exception as e:
        logger.error(f"Failed to initialize translation service: {e}")
        # Try Google as last resort
        if provider != 'google':
            logger.info("Attempting to use Google Translate as fallback...")
            try:
                service = TranslationService(provider='google', delay=0.5, api_key=None)
                logger.info("Successfully initialized Google Translate as fallback")
            except Exception as fallback_error:
                logger.error(f"Fallback to Google Translate also failed: {fallback_error}")
                return
        else:
            return
    
    # Get database session
    db = SessionLocal()
    
    try:
        # Get quotes (all quotes if auto_detect, filtered by language otherwise)
        quotes = get_quotes(db, language=source_lang if not auto_detect else None, limit=limit)
        
        if not quotes:
            lang_str = "quotes" if auto_detect else f"{source_lang.upper()} quotes"
            logger.warning(f"No {lang_str} found in database")
            return
        
        # Process quotes
        successful, failed = process_quotes(
            quotes, service, output_file,
            source_lang=source_lang, target_lang=target_lang,
            auto_detect=auto_detect
        )
        
        # Summary
        logger.info("=" * 60)
        logger.info("Translation completed!")
        if auto_detect:
            logger.info("Mode: Automatic language detection")
        else:
            logger.info(f"Translation direction: {source_lang.upper()} -> {target_lang.upper()}")
        logger.info(f"Total quotes processed: {len(quotes)}")
        logger.info(f"Successful: {successful}")
        logger.info(f"Failed: {failed}")
        logger.info(f"Output file: {output_file}")
        logger.info(f"Error log: {log_file}")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"Fatal error in main: {e}", exc_info=True)
        raise
    finally:
        db.close()


if __name__ == "__main__":
    import sys
    
    # Parse command line arguments
    # Usage: 
    #   python translit_service.py [limit] [output_file] [source_lang] [target_lang]
    #   python translit_service.py [limit] [output_file] auto
    # 
    # Examples:
    #   python translit_service.py 100 output.csv en ru          # Manual: EN->RU
    #   python translit_service.py 50 ru_en.csv ru en            # Manual: RU->EN
    #   python translit_service.py 100 auto_output.csv auto      # Auto-detect mode
    
    limit = None
    output_file = None
    source_lang = 'en'
    target_lang = 'ru'
    auto_detect = False
    
    if len(sys.argv) > 1:
        try:
            limit = int(sys.argv[1])
        except ValueError:
            logger.warning(f"Invalid limit argument: {sys.argv[1]}, processing all quotes")
    
    if len(sys.argv) > 2:
        output_file = sys.argv[2]
    
    if len(sys.argv) > 3:
        arg3 = sys.argv[3].lower()
        if arg3 == 'auto':
            auto_detect = True
            source_lang = None
            target_lang = None
        else:
            source_lang = arg3
            if source_lang not in ['en', 'ru']:
                logger.warning(f"Invalid source language: {source_lang}, using 'en'")
                source_lang = 'en'
    
    if len(sys.argv) > 4 and not auto_detect:
        target_lang = sys.argv[4].lower()
        if target_lang not in ['en', 'ru']:
            logger.warning(f"Invalid target language: {target_lang}, using 'ru'")
            target_lang = 'ru'
    
    main(
        limit=limit,
        output_file=output_file,
        source_lang=source_lang,
        target_lang=target_lang,
        auto_detect=auto_detect
    )

