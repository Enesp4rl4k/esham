"""Küresel finansal ve Türkiye ekonomi haberleri — çoklu RSS kaynağı.

Kaynaklar (öncelik sırasıyla):
  1. AA Ekonomi       — Türkiye'ye özgü, Türkçe, en yüksek öncelik
  2. Reuters Markets  — küresel piyasa haberleri (EN)
  3. Bloomberg Markets — küresel makro/piyasa (EN)
  4. Investing.com TR — Türkiye + küresel piyasa (TR/EN)
  5. ForexLive        — döviz/makro anlık akış (EN)

Tasarım:
- ThreadPoolExecutor ile tüm kaynaklar paralel çekilir — tek kaynak yavaş/çökmüş
  olsa diğerleri etkilenmez (graceful degradation).
- Her kaynağın son N haberi alınır; link bazlı deduplikasyon ile aynı haber iki
  kaynaktan geldiğinde sadece ilki döner.
- Haber AI filtresiyle "SON DAKİKA" kanalına girmeden önce news_detector.py
  içindeki `_scan_global_news` AI önem kontrolünden geçer.
"""
from __future__ import annotations

import html
import re
import xml.etree.ElementTree as ET
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field

from ..config import get_logger

log = get_logger(__name__)


def clean_html(text: str) -> str:
    """HTML etiketlerini, CDATA bloklarını ve XML kaçışlarını temizler."""
    if not text:
        return ""
    # script/style bloklarını sil
    text = re.sub(r"<(script|style).*?>.*?</>", "", text, flags=re.DOTALL | re.IGNORECASE)
    # Satır sonu oluşturan HTML etiketlerini yeni satıra çevir
    text = re.sub(r"<br\s*/?>|</p>|</div>|</li>", "\n", text, flags=re.IGNORECASE)
    # Kalan tüm HTML etiketlerini kaldır
    text = re.sub(r"<[^>]+>", "", text)
    # HTML karakter varlıklarını (&amp;, &#8217; vb.) dönüştür
    text = html.unescape(text)
    # Fazla boşlukları düzenle
    lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines()]
    clean_text = "\n".join(l for l in lines if l)
    return clean_text.strip()


@dataclass
class GlobalNewsItem:
    title: str
    link: str
    pub_date: str = ""
    source: str = ""
    description: str = ""


# ---- kaynak tanımları ----------------------------------------------------------

@dataclass
class RssSource:
    name: str
    url: str
    max_items: int = 10
    """Bu kaynaktan en fazla kaç haber alınacak."""


# Kaynaklar — erişilemez olanlar sessizce atlanır.
RSS_SOURCES: list[RssSource] = [
    # ── Türkiye ekonomi ────────────────────────────────────────────────────
    RssSource(
        name="AA Ekonomi",
        url="https://www.aa.com.tr/tr/rss/default?cat=ekonomi",
        max_items=15,
    ),
    RssSource(
        name="Sabah Ekonomi",
        url="https://www.sabah.com.tr/rss/ekonomi.xml",
        max_items=8,
    ),
    RssSource(
        name="Hürriyet Ekonomi",
        url="https://www.hurriyet.com.tr/rss/ekonomi",
        max_items=8,
    ),
    # ── Küresel piyasa & makro ─────────────────────────────────────────────
    RssSource(
        name="Reuters Business",
        url="https://feeds.reuters.com/reuters/businessNews",
        max_items=10,
    ),
    RssSource(
        name="Bloomberg Markets",
        url="https://feeds.bloomberg.com/markets/news.rss",
        max_items=10,
    ),
    RssSource(
        name="Investing.com TR",
        url="https://tr.investing.com/rss/news.rss",
        max_items=10,
    ),
    RssSource(
        name="ForexLive",
        url="https://www.forexlive.com/feed/news",
        max_items=10,
    ),
]

# ── Teknoloji & Yapay Zeka (Ayrı Kaynak Listesi) ──────────────────────
TECH_NEWS_SOURCES: list[RssSource] = [
    RssSource(
        name="TechCrunch",
        url="https://techcrunch.com/feed/",
        max_items=10,
    ),
    RssSource(
        name="The Verge",
        url="https://www.theverge.com/rss/index.xml",
        max_items=10,
    ),
    RssSource(
        name="Ars Technica",
        url="https://feeds.arstechnica.com/arstechnica/index",
        max_items=10,
    ),
    RssSource(
        name="VentureBeat AI",
        url="https://venturebeat.com/ai/feed/",
        max_items=10,
    ),
]

# Kripto balina/on-chain haberleri için ayrı kaynak listesi
CRYPTO_NEWS_SOURCES: list[RssSource] = [
    RssSource(
        name="CoinDesk",
        url="https://www.coindesk.com/arc/outboundfeeds/rss/",
        max_items=10,
    ),
    RssSource(
        name="CoinTelegraph",
        url="https://cointelegraph.com/rss",
        max_items=10,
    ),
    RssSource(
        name="Decrypt",
        url="https://decrypt.co/feed",
        max_items=8,
    ),
]

_TIMEOUT = 12  # saniye — tek kaynak için


# ---- yardımcı ----------------------------------------------------------------

def _fetch_rss(src: RssSource) -> list[GlobalNewsItem]:
    """Tek bir RSS veya Atom kaynağını çeker; hata durumunda boş liste döner."""
    items: list[GlobalNewsItem] = []
    try:
        req = urllib.request.Request(
            src.url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                "Accept": "application/rss+xml, application/xml, text/xml, */*",
            },
        )
        response = urllib.request.urlopen(req, timeout=_TIMEOUT).read()
        root = ET.fromstring(response)

        # RSS <item> veya Atom <entry>
        items_nodes = root.findall(".//item")
        is_atom = False
        if not items_nodes:
            items_nodes = root.findall(".//{http://www.w3.org/2005/Atom}entry")
            is_atom = bool(items_nodes)

        count = 0
        for item in items_nodes:
            if count >= src.max_items:
                break

            if is_atom:
                raw_title = item.findtext("{http://www.w3.org/2005/Atom}title") or ""
                link_node = item.find("{http://www.w3.org/2005/Atom}link")
                link = link_node.get("href") if link_node is not None else ""
                pub_date = (
                    item.findtext("{http://www.w3.org/2005/Atom}published")
                    or item.findtext("{http://www.w3.org/2005/Atom}updated")
                    or ""
                )
                desc = (
                    item.findtext("{http://www.w3.org/2005/Atom}summary")
                    or item.findtext("{http://www.w3.org/2005/Atom}content")
                    or ""
                )
            else:
                raw_title = item.findtext("title") or ""
                link = item.findtext("link") or item.findtext("guid") or ""
                pub_date = item.findtext("pubDate") or ""
                desc = (
                    item.findtext("description")
                    or item.findtext("{http://purl.org/rss/1.0/modules/content/}encoded")
                    or item.findtext("{http://www.w3.org/2005/Atom}summary")
                    or ""
                )

            title = html.unescape(raw_title).strip()
            cleaned_desc = clean_html(desc)

            if title and link:
                items.append(
                    GlobalNewsItem(
                        title=title,
                        link=link.strip(),
                        pub_date=pub_date.strip(),
                        source=src.name,
                        description=cleaned_desc,
                    )
                )
                count += 1

        log.debug("RSS %s: %d haber alındı.", src.name, len(items))
    except Exception as exc:
        log.debug("RSS kaynağı okunamadı (%s): %s", src.name, exc)

    return items


# ---- ana sınıf ---------------------------------------------------------------

class GlobalNewsSource:
    """Tüm RSS kaynaklarını paralel çeker, deduplike eder ve döner."""

    def __init__(self, sources: list[RssSource] | None = None) -> None:
        self.sources = sources or RSS_SOURCES

    def fetch_latest(self) -> list[GlobalNewsItem]:
        """Ekonomi + teknoloji kaynaklarını paralel çeker; link bazlı deduplikasyon uygular."""
        return self._fetch_and_dedup(self.sources)

    def fetch_crypto_news(self) -> list[GlobalNewsItem]:
        """Kripto haber kaynaklarını çeker (CoinDesk, CoinTelegraph, Decrypt)."""
        return self._fetch_and_dedup(CRYPTO_NEWS_SOURCES)

    def fetch_tech_news(self) -> list[GlobalNewsItem]:
        """Teknoloji & AI haber kaynaklarını çeker (TechCrunch, The Verge, Ars Technica, VentureBeat AI)."""
        return self._fetch_and_dedup(TECH_NEWS_SOURCES)

    def _fetch_and_dedup(self, sources: list[RssSource]) -> list[GlobalNewsItem]:
        """Verilen kaynak listesini paralel çeker, deduplike eder ve döner."""
        all_items: list[GlobalNewsItem] = []

        with ThreadPoolExecutor(max_workers=max(len(sources), 1)) as pool:
            future_to_src = {
                pool.submit(_fetch_rss, src): src for src in sources
            }
            # Kaynak sırasını koru (öncelik sırası) — as_completed sırasız döner,
            # bu yüzden sonuçları kaynak indeksine göre yeniden sıralarız.
            results: dict[str, list[GlobalNewsItem]] = {}
            for future in as_completed(future_to_src):
                src = future_to_src[future]
                try:
                    results[src.name] = future.result()
                except Exception as exc:
                    log.warning("RSS paralel fetch hatası (%s): %s", src.name, exc)
                    results[src.name] = []

        # Kaynak öncelik sırasına göre birleştir
        for src in sources:
            all_items.extend(results.get(src.name, []))

        # Link + title bazlı çift deduplikasyon
        # Aynı haber farklı URL'lerle (Reuters syndication, AP wire) gelebilir —
        # title'ı normalize edip hem link hem başlık bazlı süzüyoruz.
        seen_links: set[str] = set()
        seen_titles: set[str] = set()
        deduped: list[GlobalNewsItem] = []
        for item in all_items:
            norm_link = item.link.split("?")[0].rstrip("/")
            # Title normalize: küçük harf, noktalama/boşluk sil, ilk 80 karakter
            norm_title = "".join(
                c for c in item.title.lower() if c.isalnum() or c.isspace()
            ).split()
            norm_title_key = " ".join(norm_title[:12])  # ilk 12 kelime
            if norm_link in seen_links or norm_title_key in seen_titles:
                continue
            seen_links.add(norm_link)
            seen_titles.add(norm_title_key)
            deduped.append(item)

        log.info(
            "GlobalNewsSource (%d kaynak): %d toplam, %d deduplike.",
            len(sources),
            len(all_items),
            len(deduped),
        )
        return deduped
