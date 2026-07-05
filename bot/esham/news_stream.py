"""Anlık haber akışı.

Tasarım: tarama (scan) ile yayın (publish) hızını AYIRIR. Aynı anda çok haber gelse
bile tarama hepsini kuyruğa atar; yayıncı her `publish_interval`'de kuyruktan TEK
haber servis eder. Böylece haberler aralıklı (drip) paylaşılır — spam ve rate-limit
önlenir. Öncelik: insider > ipo > diğer.

Maliyet notu: tweet metni yayın anında üretilir; kuyrukta bekleyip düşürülen haberler
için AI çağrısı yapılmaz.
"""
from __future__ import annotations

import re
import time

from .ai import TweetComposer
from .analysis import analyze_ipo_document
from .config import get_logger, settings
from .news_queue import NewsQueue
from .publishing.social import SocialPublisher
from .sources import Disclosure
from .sources.kap import KapSource

log = get_logger(__name__)

# Fiyat tespit / izahname bildirimlerini tam analize yönlendirmek için işaretler.
_IPO_DOC_MARKERS = ("fiyat tespit", "izahname", "halka arz")
# Şirket adından bildirim türü eklerini temizlemek için.
_TITLE_NOISE = re.compile(
    r"\s*(fiyat tespit raporu|izahname[si]*|halka arz.*|özel durum.*)\s*$",
    re.IGNORECASE,
)


def _classify(d: Disclosure) -> tuple[str, str]:
    """Bildirimden (kategori, emoji) çıkarır."""
    if d.is_insider:
        return "insider", "🚨"
    text = f"{d.disclosure_type} {d.title}".lower()
    if any(m in text for m in _IPO_DOC_MARKERS):
        return "ipo", "📄"
    return "bist", "📰"


def _is_analyzable_ipo(d: Disclosure) -> bool:
    """Fiyat tespit/izahname gibi belge içeren bir halka arz bildirimi mi?"""
    text = f"{d.disclosure_type} {d.title}".lower()
    return any(m in text for m in _IPO_DOC_MARKERS)


def _company_and_ticker(d: Disclosure) -> tuple[str, str]:
    company = _TITLE_NOISE.sub("", d.title).strip() or d.company
    return company, d.company


class NewsStream:
    def __init__(
        self,
        scan_interval: int | None = None,
        publish_interval: int | None = None,
        queue_max: int | None = None,
        analyze_ipo: bool = True,
    ) -> None:
        self.kap = KapSource()
        self.composer = TweetComposer()
        self.social = SocialPublisher()
        # Fiyat tespit/izahname bildirimlerini tam analize yönlendir.
        self.analyze_ipo = analyze_ipo

        self.scan_interval = scan_interval or settings.news_scan_interval
        self.publish_interval = publish_interval or settings.news_publish_interval
        self.queue: NewsQueue[Disclosure] = NewsQueue(queue_max or settings.news_queue_max)

        self._seen: set[str] = set()  # taranmış/kuyruğa alınmış anahtarlar

    def _key(self, d: Disclosure) -> str:
        return f"{d.company}:{d.title}:{d.date}"

    # ---- tarama ----------------------------------------------------------------

    def scan(self) -> int:
        """Yeni bildirimleri kuyruğa atar; kaç yeni haber eklendiğini döner."""
        added = 0
        for d in self.kap.latest_disclosures():
            key = self._key(d)
            if key in self._seen:
                continue
            self._seen.add(key)
            category, _ = _classify(d)
            self.queue.enqueue(d, category)
            added += 1
        if added:
            log.info("Tarama: %d yeni haber kuyruğa alındı (bekleyen: %d).", added, len(self.queue))
        return added

    # ---- yayın -----------------------------------------------------------------

    def publish_next(self) -> bool:
        """Kuyruktan tek haber servis eder; yayınlandıysa True."""
        item = self.queue.dequeue()
        if item is None:
            return False
        category, emoji = _classify(item)

        # Fiyat tespit/izahname → tam analiz üret, tweet analiz linkine bağlansın.
        if self.analyze_ipo and _is_analyzable_ipo(item):
            tweet = self._handle_ipo(item)
        else:
            news = item.raw_text or f"{item.title} ({item.disclosure_type})"
            tweet = self.composer.compose(news, category=category, emoji=emoji)

        self.social.broadcast(tweet)
        log.info("Yayınlandı (kalan kuyruk: %d).", len(self.queue))
        return True

    def _handle_ipo(self, item: Disclosure) -> str:
        """Halka arz belgesini indir + analiz et + yayınla; analiz linkli tweet döner."""
        company, ticker = _company_and_ticker(item)
        source = item.pdf_link or item.raw_text or item.title
        try:
            result = analyze_ipo_document(
                source, company=company, ticker=ticker, publish=True, make_pdf=True
            )
        except Exception as exc:
            log.error("Halka arz otomatik analizi başarısız (%s); kısa tweet'e düşülüyor.", exc)
            return self.composer.compose(
                item.raw_text or item.title, category="ipo", emoji="📄"
            )

        if result.slug:
            link = f"{settings.site_url}/rapor/{result.slug}"
            return f"📄 HALKA ARZ ANALİZİ: {company} ({ticker})\n{link}\n#HalkaArz #BIST"
        # Yayın yapılmadıysa yine de bir şey paylaş.
        return self.composer.compose(item.raw_text or item.title, category="ipo", emoji="📄")

    # ---- çalıştırma modları ----------------------------------------------------

    def check_once(self) -> int:
        """Tek tur: tara ve kuyruktakilerin TAMAMINI hemen yayınla (manuel test)."""
        self.scan()
        published = 0
        while self.publish_next():
            published += 1
        return published

    def run(self) -> None:
        """Sürekli: periyodik tara, sabit aralıkla tek tek yayınla (drip)."""
        log.info(
            "Anlık haber botu başladı (tarama: %ss, yayın aralığı: %ss).",
            self.scan_interval,
            self.publish_interval,
        )
        last_scan = 0.0
        while True:
            now = time.monotonic()
            if now - last_scan >= self.scan_interval:
                try:
                    self.scan()
                except Exception as exc:  # tarama hatası döngüyü durdurmasın
                    log.error("Tarama hatası: %s", exc)
                last_scan = now

            try:
                self.publish_next()
            except Exception as exc:
                log.error("Yayın hatası: %s", exc)

            time.sleep(self.publish_interval)
