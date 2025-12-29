# Translation Service Providers Guide

This document explains the available translation providers and how to use them with the translation service.

## Available Providers

### 1. **Google Translate** (Default) ✅ Recommended for Free Use
- **Quality**: Good
- **API Key Required**: No
- **Free Tier**: Unlimited (with rate limiting)
- **Best For**: General use, free projects, high volume
- **Pros**: Free, reliable, supports many languages
- **Cons**: Quality not as good as DeepL for some language pairs

### 2. **DeepL** ⭐ Best Quality
- **Quality**: Excellent (often better than Google)
- **API Key Required**: Yes (free tier available)
- **Free Tier**: 500,000 characters/month
- **Best For**: When quality is critical, professional translations
- **Pros**: Best translation quality, natural-sounding results
- **Cons**: Requires API key, free tier has limits, **may be unavailable in some regions**
- **Get API Key**: https://www.deepl.com/pro-api
- **⚠️ Region Restriction**: If DeepL is unavailable in your region, the service will automatically fallback to Google Translate

### 3. **Microsoft Translator**
- **Quality**: Good
- **API Key Required**: Yes (free tier available)
- **Free Tier**: 2,000,000 characters/month
- **Best For**: High volume, Microsoft ecosystem integration
- **Pros**: Very generous free tier, good quality
- **Cons**: Requires API key and Azure account
- **Get API Key**: https://azure.microsoft.com/en-us/services/cognitive-services/translator/

### 4. **MyMemory**
- **Quality**: Good (especially for short texts)
- **API Key Required**: No
- **Free Tier**: Unlimited (with rate limiting)
- **Best For**: Short texts, quick translations
- **Pros**: Free, no API key needed
- **Cons**: Better for shorter texts

### 5. **Pons**
- **Quality**: Fair (dictionary-based)
- **API Key Required**: No
- **Free Tier**: Unlimited
- **Best For**: Word/phrase translations, dictionary lookups
- **Pros**: Free, dictionary-based
- **Cons**: Less natural for full sentences

### 6. **Linguee**
- **Quality**: Good (context-aware)
- **API Key Required**: No
- **Free Tier**: Unlimited
- **Best For**: Context-aware translations
- **Pros**: Free, provides context
- **Cons**: May be slower

## Quality Comparison (EN ↔ RU)

1. **DeepL** - ⭐⭐⭐⭐⭐ Best quality, most natural
2. **Google Translate** - ⭐⭐⭐⭐ Good quality, reliable
3. **Microsoft Translator** - ⭐⭐⭐⭐ Good quality
4. **Linguee** - ⭐⭐⭐ Good with context
5. **MyMemory** - ⭐⭐⭐ Good for short texts
6. **Pons** - ⭐⭐ Dictionary-based, less natural

## How to Use Different Providers

### Method 1: Environment Variables (Recommended)

Set environment variables before running:

```bash
# Use Google Translate (default)
python translit_service.py 100 output.csv auto

# Use DeepL (requires API key)
export TRANSLATION_PROVIDER=deepl
export TRANSLATION_API_KEY=your_deepl_api_key
python translit_service.py 100 output.csv auto

# Use Microsoft Translator
export TRANSLATION_PROVIDER=microsoft
export TRANSLATION_API_KEY=your_microsoft_api_key
python translit_service.py 100 output.csv auto

# Use MyMemory (free, no API key)
export TRANSLATION_PROVIDER=mymemory
python translit_service.py 100 output.csv auto

# Use Linguee (free, no API key)
export TRANSLATION_PROVIDER=linguee
python translit_service.py 100 output.csv auto
```

### Method 2: Modify Code Directly

Edit `translit_service.py` and change the provider in the `main()` function:

```python
# In main() function, change:
provider = os.getenv('TRANSLATION_PROVIDER', 'google').lower()
# To:
provider = os.getenv('TRANSLATION_PROVIDER', 'deepl').lower()  # or 'microsoft', 'mymemory', etc.
```

## Getting API Keys

### DeepL API Key
1. Go to https://www.deepl.com/pro-api
2. Sign up for free account
3. Get your API key from dashboard
4. Free tier: 500,000 characters/month

### Microsoft Translator API Key
1. Go to https://azure.microsoft.com/en-us/services/cognitive-services/translator/
2. Create Azure account (free)
3. Create Translator resource
4. Get API key from Azure portal
5. Free tier: 2,000,000 characters/month

## Recommendations

### For Free Use (No API Key)
- **Best Choice**: Google Translate (default)
- **Alternative**: MyMemory or Linguee

### For Best Quality
- **Best Choice**: DeepL (requires API key, but free tier available)
- **Alternative**: Microsoft Translator (larger free tier)

### For High Volume
- **Best Choice**: Microsoft Translator (2M chars/month free)
- **Alternative**: Google Translate (unlimited with rate limiting)

### For Quotes/Aphorisms
- **Best Choice**: DeepL (best natural translations)
- **Second Choice**: Google Translate (good balance)

## Example Usage

```bash
# Default (Google Translate)
python translit_service.py 100 output.csv auto

# DeepL with API key
export TRANSLATION_PROVIDER=deepl
export TRANSLATION_API_KEY=your_key_here
python translit_service.py 100 output.csv auto

# MyMemory (free, no key needed)
export TRANSLATION_PROVIDER=mymemory
python translit_service.py 100 output.csv auto
```

## Notes

- All providers support both EN→RU and RU→EN translation
- Auto-detect mode works with all providers
- Rate limiting delay (0.5s) is applied to all providers
- Errors are logged to timestamped log files
- CSV output format is the same for all providers
- **DeepL Region Restriction**: If DeepL is unavailable in your region, the service automatically falls back to Google Translate. You'll see a warning in the logs, but translation will continue seamlessly.

