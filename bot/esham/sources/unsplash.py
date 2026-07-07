"""Pexels görsel kaynağı — haber kategorisine/başlığına göre otomatik fotoğraf çeker.

Pexels API:
  pexels.com/api → "Get Started" → email ile kayıt → anında key (onay yok)
  Ücretsiz: saatte 200 istek, aylık 20.000 istek — haber kartları için fazlasıyla yeterli.
  Ticari kullanım dahil serbesttir (attribution Pexels sayfasında gösterilmeli).

Tasarım:
- Haber başlığı + kategorisinden anahtar kelime çıkar
- Pexels API'sinden uygun fotoğraf çek (landscape, yüksek kalite)
- Fotoğraf 24 saat cache'lenir (aynı sorgu tekrar API çağrısı yapmaz)
- API key yoksa None döner (fallback: mevcut veri kartı kullanılır)
- KAP/analiz kartları KULLANMAZ — sadece genel haber/gündem kartları kullanır
"""
from __future__ import annotations

import hashlib
import time
from pathlib import Path

import requests

from ..config import get_logger, settings

log = get_logger(__name__)

PEXELS_API = "https://api.pexels.com/v1/search"

# Kategori → Pexels arama terimi
CATEGORY_QUERIES: dict[str, str] = {
    "bist":      "stock market trading finance",
    "global":    "world economy finance",
    "ipo":       "business corporation building",
    "viop":      "derivatives trading finance chart",
    "gundem":    "news economics city",
    "kripto":    "cryptocurrency bitcoin digital currency",
    "teknoloji": "technology artificial intelligence",
    "insider":   "business meeting corporate",
}

# Haber başlığından spesifik arama terimi çıkarımı
KEYWORD_MAP: dict[str, str] = {
    "bitcoin":     "bitcoin cryptocurrency digital",
    "btc":         "bitcoin digital currency",
    "ethereum":    "ethereum blockchain technology",
    "kripto":      "cryptocurrency digital finance",
    "faiz":        "interest rate central bank economy",
    "tcmb":        "central bank monetary policy",
    "enflasyon":   "inflation economy prices market",
    "altın":       "gold precious metal finance",
    "petrol":      "oil petroleum energy tanker",
    "dolar":       "dollar currency exchange rate",
    "euro":        "euro currency europe finance",
    "borsa":       "stock exchange market trading",
    "bist":        "stock market trading finance",
    "yapay zeka":  "artificial intelligence technology future",
    "ai":          "artificial intelligence technology",
    "nvidia":      "semiconductor chip technology",
    "çip":         "microchip semiconductor technology",
    "samsung":     "technology electronics innovation",
    "apple":       "apple technology innovation",
    "microsoft":   "technology office software",
    "tesla":       "electric vehicle technology",
    "hormuz":      "oil tanker ship ocean",
    "iran":        "middle east geopolitics",
    "japonya":     "japan tokyo city economy",
    "çin":         "china beijing skyline economy",
    "savaş":       "conflict war geopolitics",
    "banka":       "bank finance building architecture",
    "ihracat":     "global trade shipping port",
    "gsyh":        "economic growth gdp chart",
    "dow":         "wall street stock market nyse",
    "s&p":         "wall street stock exchange finance",
    "fed":         "federal reserve central bank",
    "hazine":      "government treasury finance",
    "solana":      "blockchain cryptocurrency technology",
    "strategy":    "bitcoin cryptocurrency investment",
    "stablecoin":  "cryptocurrency digital finance",
}

# Görsel cache dizini
_CACHE_DIR = Path(__file__).resolve().parents[3] / "bot" / "cache" / "images"
_CACHE_TTL = 24 * 3600  # 24 saat


def _cache_key(query: str) -> str:
    return hashlib.md5(query.lower().encode()).hexdigest()[:14]


def _find_query(title: str, category: str) -> str:
    """Başlık ve kategoriden en uygun Pexels arama sorgusunu döner."""
    title_lower = title.lower()
    for keyword, query in KEYWORD_MAP.items():
        if keyword in title_lower:
            return query
    return CATEGORY_QUERIES.get(category, "finance business economy")


class PexelsSource:
    """Pexels API'sinden haber görseli çeker — başvuru gerektirmez, anında key."""

    def __init__(self) -> None:
        self.api_key = settings.unsplash_access_key  # aynı config key'i kullanır
        self._cache_dir = _CACHE_DIR
        self._cache_dir.mkdir(parents=True, exist_ok=True)

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    def fetch_photo(self, title: str, category: str) -> Path | None:
        """Haber başlığı ve kategorisine göre fotoğraf indirir.

        Cache öncelikli: aynı sorgu için 24 saat içinde tekrar API çağrısı yapmaz.
        Başarısız olursa None döner — kart standart veri tasarımıyla devam eder.
        """
        if not self.enabled:
            return None

        query = _find_query(title, category)
        key = _cache_key(query)
        cache_path = self._cache_dir / f"{key}.jpg"

        # Cache hit — TTL kontrolü
        if cache_path.exists():
            age = time.time() - cache_path.stat().st_mtime
            if age < _CACHE_TTL and cache_path.stat().st_size > 10_000:
                log.debug("Pexels cache hit: '%s' → %s", query, key)
                return cache_path

        try:
            resp = requests.get(
                PEXELS_API,
                params={
                    "query": query,
                    "orientation": "landscape",
                    "size": "large",
                    "per_page": 5,
                },
                headers={"Authorization": self.api_key},
                timeout=10,
            )
            if resp.status_code == 401:
                log.warning("Pexels API: geçersiz key.")
                return None
            if resp.status_code == 429:
                log.warning("Pexels API: rate limit aşıldı.")
                return None
            resp.raise_for_status()

            photos = resp.json().get("photos", [])
            if not photos:
                log.debug("Pexels '%s' için sonuç bulunamadı.", query)
                return None

            # İlk fotoğrafı indir (landscape, large)
            photo_url = photos[0]["src"]["large2x"]
            photographer = photos[0].get("photographer", "?")

            img_resp = requests.get(photo_url, timeout=15)
            img_resp.raise_for_status()
            cache_path.write_bytes(img_resp.content)

            log.info(
                "Pexels fotoğraf indirildi: '%s' → %s (Foto: %s)",
                query, key, photographer,
            )
            return cache_path

        except requests.RequestException as exc:
            log.warning("Pexels fotoğraf indirilemedi ('%s'): %s", query, exc)
            return None
        except (KeyError, ValueError) as exc:
            log.warning("Pexels yanıtı ayrıştırılamadı: %s", exc)
            return None


# Geriye uyumluluk için Unsplash adıyla da erişilebilir
UnsplashSource = PexelsSource
