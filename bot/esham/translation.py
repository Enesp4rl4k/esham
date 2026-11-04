"""Merkezi Türkçe Çeviri ve Dil Denetim Modülü.

Esham kurumsal bir Türk finansal istihbarat platformudur.
İngilizce başlık veya metinlerin ham halde sitede veya sosyal medyada yayınlanması kesinlikle yasaktır.
Bu modül:
1. Metnin İngilizce olup olmadığını tespit eder (is_mostly_english).
2. İngilizce metinleri akıcı, kurumsal Türkçe finans diline çevirir (translate_to_turkish).
3. Çevrilemeyen veya İngilizce kalan içerikleri filtreler / engeller.
"""
from __future__ import annotations

import re
from typing import Optional

import requests

from .config import get_logger

log = get_logger(__name__)

ENGLISH_COMMON_WORDS = {
    "the", "be", "to", "of", "and", "a", "in", "that", "have", "i",
    "it", "for", "not", "on", "with", "he", "as", "you", "do", "at",
    "this", "but", "his", "by", "from", "they", "we", "say", "her",
    "she", "or", "an", "will", "my", "one", "all", "would", "there",
    "their", "what", "so", "up", "out", "if", "about", "who", "get",
    "which", "go", "me", "when", "make", "can", "like", "time", "no",
    "just", "him", "know", "take", "people", "into", "year", "your",
    "good", "some", "could", "them", "see", "other", "than", "then",
    "now", "look", "only", "come", "its", "over", "think", "also",
    "back", "after", "use", "two", "how", "our", "work", "first",
    "well", "way", "even", "new", "want", "because", "any", "these",
    "give", "day", "most", "us", "is", "are", "was", "were", "been",
    "has", "had", "faces", "backlash", "schools", "plan", "restrict",
    "hits", "rewind", "undoing", "years", "expansion", "tried", "recaps",
    "theyre", "useful", "unsettling", "crypto", "market", "stocks",
    "jump", "drops", "warns", "amid", "says", "deal", "buys", "sec",
}

TURKISH_SPECIFIC_CHARS = set("çğıöşüÇĞİÖŞÜ")


def is_mostly_english(text: str) -> bool:
    """Verilen metnin İngilizce olup olmadığını tespit eder."""
    if not text or not text.strip():
        return False

    clean_text = re.sub(r"[^a-zA-ZçğıöşüÇĞİÖŞÜ\s]", " ", text)
    words = [w.lower() for w in clean_text.split() if len(w) > 1]
    if not words:
        return False

    has_tr_char = any(c in TURKISH_SPECIFIC_CHARS for c in text)
    eng_matches = sum(1 for w in words if w in ENGLISH_COMMON_WORDS)
    eng_ratio = eng_matches / len(words)

    # 1. 3 veya daha fazla İngilizce stop-word varsa kesin İngilizcedir
    if eng_matches >= 3:
        return True
    # 2. 2 eşleşme ve kelimelerin en az %25'i İngilizce ise
    if eng_matches >= 2 and eng_ratio >= 0.25:
        return True
    # 3. Türkçe karakter yoksa ve kısa bir başlıkta İngilizce stop-word varsa
    if not has_tr_char and eng_matches >= 1 and len(words) <= 5:
        return True

    return False


def translate_to_turkish(text: str, timeout: int = 6) -> str:
    """İngilizce metni kurumsal ve akıcı Türkçeye çevirir.

    Google Translate public API endpoint'ini kullanır (ücretsiz, anahtarsız, hızlı).
    Başarısız olursa boş string döner.
    """
    if not text or not text.strip():
        return ""

    if not is_mostly_english(text):
        return text.strip()

    try:
        url = "https://translate.googleapis.com/translate_a/single"
        params = {
            "client": "gtx",
            "sl": "auto",
            "tl": "tr",
            "dt": "t",
            "q": text,
        }
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        resp = requests.get(url, params=params, headers=headers, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        translated = "".join([item[0] for item in data[0] if item and item[0]])
        translated = translated.strip()

        if translated and not is_mostly_english(translated):
            log.info("İngilizce metin Türkçeye çevrildi: '%s' -> '%s'", text[:50], translated[:50])
            return translated
    except Exception as exc:
        log.warning("Çeviri servisi hatası (%s): %s", text[:40], exc)

    return ""


def ensure_turkish(headline: str, fallback_prompt: str = "") -> str:
    """Başlığın mutlaka Türkçe olmasını garanti eder.

    İngilizce ise çevirir; çevrilemezse boş döner (asla İngilizce bırakmaz).
    """
    if not headline or not headline.strip():
        return ""

    if not is_mostly_english(headline):
        return headline.strip()

    translated = translate_to_turkish(headline)
    if translated and not is_mostly_english(translated):
        return translated

    log.warning("Başlık Türkçeleştirilemedi; yayınlanması engellendi: '%s'", headline[:60])
    return ""
