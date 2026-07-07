"""Anlık haber akışı.

Tasarım: tarama (scan) ile yayın (publish) hızını AYIRIR. Aynı anda çok haber gelse
bile tarama hepsini kuyruğa atar; yayıncı her `publish_interval`'de kuyruktan TEK
haber servis eder. Böylece haberler aralıklı (drip) paylaşılır — spam ve rate-limit
önlenir. Öncelik: insider > ipo > diğer.

Haber kaynakları:
- KAP akışı        : şirket bildirimleri (insider, IPO, finansal sonuçlar vb.)
- Makro dedektör   : VIX sıçraması, ABD faiz hareketi, altın rallisi, sektör rotasyonu
  gibi eşiği aşan küresel/sektör gelişmeleri otomatik haber olarak kuyruğa girer.

Maliyet notu: tweet ve analiz metni yayın anında üretilir; kuyrukta bekleyip
düşürülen haberler için AI çağrısı yapılmaz.
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Union

from .analysis import analyze_ipo_document
from .config import get_logger, settings
from .news_queue import NewsQueue
from .pipeline import run_news_report
from .publishing.cards import CardGenerator, CardSpec
from .publishing.social import SocialPublisher
from .publishing.ticker_data import update_ticker_data
from .sources import Disclosure
from .sources.kap import KapSource
from .sources.kap_filter import is_significant, score
from .sources.news_detector import MarketEvent, NewsDetector
from .state import get_state
from .turkish import tr_fold

log = get_logger(__name__)

_cards = CardGenerator()

# KAP + makro olaylar aynı kuyrukta birleşir
QueueItem = Union[Disclosure, MarketEvent]


def _render_card(spec: CardSpec) -> Path | None:
    try:
        return _cards.render(spec)
    except Exception as exc:  # kart üretimi asla yayını durdurmasın
        log.warning("Kart görseli üretilemedi (%s); görselsiz devam ediliyor.", exc)
        return None


def _cleanup(path: Path | None) -> None:
    if path and path.exists():
        try:
            path.unlink()
        except OSError:
            pass

# Fiyat tespit / izahname bildirimlerini tam analize yönlendirmek için işaretler.
_IPO_DOC_MARKERS = ("fiyat tespit rapor", "onaylı izahname", "taslak izahname")


def _classify(d: Disclosure) -> tuple[str, str]:
    """Bildirimden (kategori, emoji) çıkarır."""
    if d.is_insider:
        return "insider", "🚨"
    text = tr_fold(f"{d.disclosure_type} {d.title}")
    if any(tr_fold(m) in text for m in _IPO_DOC_MARKERS):
        return "ipo", "📄"
    return "bist", "📰"


def _is_analyzable_ipo(d: Disclosure) -> bool:
    """Fiyat tespit/izahname gibi belge içeren bir halka arz bildirimi mi?"""
    text = tr_fold(f"{d.disclosure_type} {d.title}")
    return any(tr_fold(m) in text for m in _IPO_DOC_MARKERS)


def _company_and_ticker(d: Disclosure) -> tuple[str, str]:
    """KAP'ın yapılandırılmış alanlarından (kapTitle/stockCodes) doğrudan alır —
    artık başlık metnini regex'le ayrıştırmaya gerek yok."""
    return d.company, d.ticker or d.company


class NewsStream:
    def __init__(
        self,
        scan_interval: int | None = None,
        publish_interval: int | None = None,
        queue_max: int | None = None,
        analyze_ipo: bool = True,
    ) -> None:
        self.kap = KapSource()
        self.social = SocialPublisher()
        self.detector = NewsDetector()   # makro + sektör olay dedektörü
        # Fiyat tespit/izahname bildirimlerini tam analize yönlendir.
        self.analyze_ipo = analyze_ipo

        self.scan_interval = scan_interval or settings.news_scan_interval
        self.publish_interval = publish_interval or settings.news_publish_interval
        self.queue: NewsQueue[QueueItem] = NewsQueue(queue_max or settings.news_queue_max)

        # Süreç yeniden başlasa da (Render restart/deploy) aynı bildirim tekrar
        # tweetlenmesin diye diskte kalıcı — sadece bellekte olsaydı her restart
        # sıfırdan başlar ve yakın zamanda paylaşılmış haberler tekrar kuyruğa girerdi.
        self._state = get_state()
        self._seen: set[str] = self._state.load_seen()

    def _key(self, d: Disclosure) -> str:
        return f"{d.company}:{d.title}:{d.date}"

    # ---- KAP taraması ----------------------------------------------------------

    def scan(self) -> int:
        """Yeni KAP bildirimlerini kuyruğa atar; kaç yeni haber eklendiğini döner.

        Önem filtresi: insider/IPO her zaman kuyruğa girer (ayrı, öncelikli işlem
        görürler). Genel KAP akışındaki rutin/idari bildirimler (genel kurul
        çağrısı, imza sirküleri, yatırımcı sunumu vb.) filtrelenir — aksi halde
        her önemsiz KAP bildirimi paylaşılır ve akış gürültüye/veri yığılmasına
        döner.
        """
        added = 0
        skipped = 0
        for d in self.kap.latest_disclosures():
            key = self._key(d)
            if key in self._seen:
                continue
            self._seen.add(key)
            category, _ = _classify(d)

            if category not in ("insider", "ipo") and not is_significant(
                d, settings.kap_min_importance
            ):
                skipped += 1
                log.debug(
                    "Filtrelendi (skor=%d, eşik=%d): %s",
                    score(d), settings.kap_min_importance, d.title,
                )
                continue

            self.queue.enqueue(d, category)
            added += 1
        if added or skipped:
            self._state.save_seen(self._seen)  # süreç yeniden başlasa da kalıcı
            log.info(
                "KAP tarama: %d yeni haber kuyruğa alındı, %d önemsiz bildirim filtrelendi "
                "(bekleyen: %d).",
                added, skipped, len(self.queue),
            )
        return added

    # ---- makro/sektör taraması -------------------------------------------------

    def macro_scan(self) -> int:
        """Makro ve sektör fiyat hareketlerini tarar; tetikleyici olayları kuyruğa atar.

        NewsDetector eşiği aşan hareketleri döner (VIX sıçraması, faiz hareketi,
        altın rallisi, sektör rotasyonu vb.). Her olay daha önce görülmediyse
        kuyruğa "global" önceliğiyle eklenir.
        """
        added = 0
        try:
            events = self.detector.scan()
        except Exception as exc:
            log.warning("Makro tarama hatası: %s", exc)
            return 0

        for event in events:
            self.queue.enqueue(event, event.category)
            added += 1
            log.info("Makro olay kuyruğa alındı: %s", event.headline[:80])

        if added:
            log.info("Makro tarama: %d yeni olay kuyruğa alındı (bekleyen: %d).", added, len(self.queue))
        return added

    # ---- yayın -----------------------------------------------------------------

    def publish_next(self) -> bool:
        """Kuyruktan tek öğe servis eder; yayınlandıysa True.

        Öğe türüne göre yönlendirme:
        - MarketEvent  → run_news_report(event=...) — makro/sektör AI analizi
        - Disclosure   → IPO ise tam analiz, değilse run_news_report(disclosure=...)
        """
        item = self.queue.dequeue()
        if item is None:
            return False

        # ---- makro/sektör olayı ------------------------------------------------
        if isinstance(item, MarketEvent):
            try:
                run_news_report(event=item, publish_social=True)
            except Exception as exc:
                log.error("Makro olay yayın hatası (%s): %s", item.label, exc)
            log.info("Makro olay yayınlandı (kalan kuyruk: %d).", len(self.queue))
            return True

        # ---- KAP bildirimi (Disclosure) ----------------------------------------
        category, _ = _classify(item)

        # Fiyat tespit/izahname → halka arz tam analiz (mevcut IPO pipeline'ı)
        if self.analyze_ipo and _is_analyzable_ipo(item):
            try:
                img_path = self._handle_ipo(item)
            except Exception as exc:
                log.error("IPO analiz hatası: %s", exc)
            log.info("IPO bildirimi yayınlandı (kalan kuyruk: %d).", len(self.queue))
            return True

        # Diğer KAP bildirimleri → AI analiz raporu + tweet
        try:
            run_news_report(disclosure=item, publish_social=True)
        except Exception as exc:
            log.error("KAP bildirim yayın hatası (%s): %s", item.title[:60], exc)

        log.info("KAP bildirimi yayınlandı (kalan kuyruk: %d).", len(self.queue))
        return True

    def _handle_ipo(self, item: Disclosure) -> Path | None:
        """Halka arz belgesini indir + analiz et + yayınla."""
        company, ticker = _company_and_ticker(item)
        source = (
            self.kap.resolve_attachment_url(item.disclosure_index)
            or item.pdf_link
            or item.raw_text
            or item.title
        )
        try:
            result = analyze_ipo_document(
                source, company=company, ticker=ticker, publish=True, make_pdf=True
            )
        except Exception as exc:
            log.error("Halka arz otomatik analizi başarısız (%s); haber raporuna düşülüyor.", exc)
            run_news_report(disclosure=item, publish_social=True)
            return None

        if result.slug:
            link = f"{settings.site_url}/rapor/{result.slug}"
            self.social.broadcast(
                f"📄 HALKA ARZ ANALİZİ: {company} ({ticker})\n{link}\n#HalkaArz #BIST",
                image_path=result.image_path,
            )
        return result.image_path

    # ---- çalıştırma modları ----------------------------------------------------

    def check_once(self, max_publish: int = 5) -> int:
        """Tek tur: KAP + makro tara, ticker JSON güncelle, en fazla max_publish haber yayınla.

        max_publish ile yayın sayısı sınırlanır — GitHub Actions'ta her 15 dakikada
        bir çalıştırıldığında 258 KAP bildiriminin hepsini tek seferde boşaltmak
        yerine kademeli drip servis yapılır. Bu Twitter rate-limit ve Gemini 429'u önler.
        Varsayılan 5: günde ~20 seans dakikasında çalışırsa toplamda ~100 haber/gün —
        maksimum önem sıralamasıyla (insider > ipo > diğer) en kritikler önce gider.
        """
        self.scan()
        self.macro_scan()
        try:
            update_ticker_data()
        except Exception as exc:
            log.warning("Ticker JSON güncellenemedi: %s", exc)
        published = 0
        while published < max_publish and self.publish_next():
            published += 1
        if len(self.queue) > 0:
            log.info(
                "check_once: %d haber yayınlandı, %d haber kuyruкta kaldı (max_publish=%d).",
                published, len(self.queue), max_publish,
            )
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
                except Exception as exc:
                    log.error("KAP tarama hatası: %s", exc)
                try:
                    self.macro_scan()
                except Exception as exc:
                    log.error("Makro tarama hatası: %s", exc)
                try:
                    update_ticker_data()
                except Exception as exc:
                    log.warning("Ticker JSON güncellenemedi: %s", exc)
                last_scan = now

            try:
                self.publish_next()
            except Exception as exc:
                log.error("Yayın hatası: %s", exc)

            time.sleep(self.publish_interval)
