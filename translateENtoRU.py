from wordfreq import top_n_list
import requests
import csv
import time

# 1) Get top 20k English word forms
words = top_n_list("en", 20000)

def get_russian_translation(word):
    # Example using Wikimedia / Wiktionary API for a first sense
    url = f"https://api.wiktionary.org/translate?lang=en&word={word}&target=ru"
    try:
        r = requests.get(url).json()
        return r["translation"][0]  # pick first dominant sense
    except:
        return ""

# 2) Build CSV
with open("20k_en_ru.csv", "w", encoding="utf-8", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["english","russian"])
    for w in words:
        ru = get_russian_translation(w)
        writer.writerow([w, ru])
        time.sleep(0.1)  # avoid rate limits
