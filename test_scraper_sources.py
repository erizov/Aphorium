"""Test if scraper extracts sources."""

from scrapers.wikiquote_en import WikiQuoteEnScraper

scraper = WikiQuoteEnScraper()
data = scraper.scrape_author_page("William Shakespeare")

print(f"Total quotes: {len(data['quotes'])}")
print(f"Sources found: {len(data['sources'])}")
if data['sources']:
    print(f"First 5 source titles: {list(data['sources'].keys())[:5]}")
    for title, quotes in list(data['sources'].items())[:3]:
        print(f"  - {title}: {len(quotes)} quotes")
else:
    print("No sources extracted - all quotes are in general list")

