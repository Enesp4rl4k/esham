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
from .pipeline import last_news_status, run_news_report
from .publish_gate import record_publication, reset_run_publications
from .publishing.cards import CardGenerator, CardSpec
from .publishing.outbox import outbox_context, send_outbox
from .publishing.social import SocialPublisher
from .publishing.ticker_data import update_ticker_data
from .sources import Disclosure
from .sources.kap import KapSource
from .sources.kap_filter import is_significant, score
from .sources.news_detector import MarketEvent, NewsDetector
from .state import get_state
from .turkish import tr_fold

#: Aynı KAP bildirimi için en fazla yayın denemesi (hata/engel durumlarında). Aşılınca ERROR loglanır,
#: durum dosyasına `failed_disclosures` olarak yazılır ve bildirim bir daha denenmez.
MAX_PUBLISH_ATTEMPTS = 3

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
# SADECE yeni/aktif halka arz sürecine ait belgeler — post-arz bildirimleri dahil DEĞİL.
_IPO_DOC_MARKERS = ("onaylı izahname", "taslak izahname", "halka arz fiyat tespit")

# Post-arz bildirimleri: artık tamamlanmış arzlara ait rutin açıklamalar.
# "fiyat tespit raporuna ilişkin analist raporu", "%5'inden fazlasını alanlar",
# "idari sorumluluğu olan kişiler", "arz edilen toplam payların" vb.
# Bu başlıklar _is_post_ipo() ile tespit edilir ve kuyruğa alınmaz.
_POST_IPO_MARKERS = (
    "fiyat tespit raporuna iliskin",  # analist raporu — eski arz
    "inden fazlasini alanlar",        # %5 bildirim — eski arz
    "arz edilen toplam paylarin",     # pay dağılımı — eski arz
    "pay alimi yapan idari",          # yönetici alımı — eski arz
    "paylarinin halka arzinda",       # genel post-arz ifadesi
    "halka arz isleminde",            # işlem tamamlandı bildirimi
    "halka arzi tamamlandi",          # tamamlanmış arz
    "talep toplama sonuclari",        # talep toplama bitti
    "kesin tahsisat",                 # kesin tahsisat bildirimi
)


def _is_post_ipo(d: "Disclosure") -> bool:  # type: ignore[name-defined]
    """Tamamlanmış bir halka arza ait post-bildirim mi? Bunları filtrele."""
    from .turkish import tr_fold
    text = tr_fold(f"{d.disclosure_type} {d.title}")
    return any(tr_fold(m) in text for m in _POST_IPO_MARKERS)


def _classify(d: Disclosure) -> tuple[str, str]:
    """Bildirimden (kategori, emoji) çıkarır."""
    if d.is_insider:
        return "bist", "🚨"
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
    return d.company, d.ticker


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
        # Kuyrukta bekleyen (henüz kalıcı karar verilmemiş) bildirimler — aynı süreçte tekrar kuyruğa girmesin.
        self._queued: set[str] = set()
        try:
            reset_run_publications(self._state)
        except Exception:  # noqa: BLE001 — test durum nesneleri get/set taşımayabilir
            pass

    def _key(self, d: Disclosure) -> str:
        return f"{d.company}:{d.title}:{d.date}"

    def _mark_seen(self, d: Disclosure) -> None:
        """Bildirimi kalıcı olarak "görüldü" işaretler — YALNIZ yayın veya kalıcı karar sonrası."""
        key = self._key(d)
        self._queued.discard(key)
        self._seen.add(key)
        self._state.save_seen(self._seen)

    # ---- KAP taraması ----------------------------------------------------------

    def scan(self) -> int:
        """Yeni KAP bildirimlerini kuyruğa atar; kaç yeni haber eklendiğini döner.

        Önem filtresi: insider/IPO her zaman kuyruğa girer (ayrı, öncelikli işlem
        görürler). Genel KAP akışındaki rutin/idari bildirimler (genel kurul
        çağrısı, imza sirküleri, yatırımcı sunumu vb.) filtrelenir.

        "Görüldü" işareti: filtrelenen bildirim (kalıcı karar) hemen işaretlenir; kuyruğa alınan bildirim
        ise ancak yayınlanınca veya kalıcı bir karar (mükerrer) verilince işaretlenir. Böylece tek turda
        servis edilemeyen ya da hata alan bildirim kaybolmaz, sonraki taramada yeniden kuyruğa girer.
        """
        added = 0
        skipped = 0
        for d in self.kap.latest_disclosures():
            key = self._key(d)
            if key in self._seen or key in self._queued:
                continue

            # Post-arz bildirimleri (tamamlanmış arzlara ait rutin açıklamalar)
            # hiçbir zaman paylaşılmaz — category kontrolünden önce elenir.
            if _is_post_ipo(d):
                skipped += 1
                self._seen.add(key)
                log.debug("Post-arz bildirimi filtrelendi: %s", d.title)
                continue

            category, _ = _classify(d)

            if category not in ("insider", "ipo") and not is_significant(
                d, settings.kap_min_importance
            ):
                skipped += 1
                self._seen.add(key)
                log.debug(
                    "Filtrelendi (skor=%d, eşik=%d): %s",
                    score(d), settings.kap_min_importance, d.title,
                )
                continue

            self.queue.enqueue(d, category)
            self._queued.add(key)
            added += 1
        if skipped:
            self._state.save_seen(self._seen)
        if added or skipped:
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
        """Kuyruktan tek öğe servis eder; bir öğe işlendiyse True (yayınlanmış olması gerekmez).

        Öğe türüne göre yönlendirme:
        - MarketEvent  → run_news_report(event=...) — makro/sektör özeti
        - Disclosure   → IPO ise tam analiz, değilse run_news_report(disclosure=...)

        "Yayınlandı" logu yalnız gerçekten yayınlanınca yazılır. KAP bildirimi yalnız yayın veya kalıcı
        karar (mükerrer) sonrası "görüldü" işaretlenir; hata/duraklatma/engel durumunda sonraki taramada
        yeniden denenir.
        """
        item = self.queue.dequeue()
        if item is None:
            return False

        # ---- makro/sektör olayı ------------------------------------------------
        if isinstance(item, MarketEvent):
            slug = None
            try:
                with outbox_context(kind="event"):
                    slug = run_news_report(event=item, publish_social=True)
            except Exception as exc:
                log.error("Makro olay yayın hatası (%s): %s", item.label, exc)
            if slug:
                log.info("Makro olay yayınlandı (kalan kuyruk: %d).", len(self.queue))
            return True

        # ---- KAP bildirimi (Disclosure) ----------------------------------------
        # Fiyat tespit/izahname → halka arz tam analiz (mevcut IPO pipeline'ı)
        if self.analyze_ipo and _is_analyzable_ipo(item):
            try:
                self._handle_ipo(item)
            except Exception as exc:
                log.error("IPO analiz hatası; sonraki taramada yeniden denenecek: %s", exc)
            return True

        self._publish_disclosure(item)
        return True

    def _publish_disclosure(self, item: Disclosure) -> str | None:
        """KAP bildirimini rapora dönüştürür; görüldü işaretini sonuca göre koyar."""
        slug = None
        status = "error"
        try:
            with outbox_context(kap_index=item.disclosure_index, source_key=self._key(item), kind="kap"):
                slug = run_news_report(disclosure=item, publish_social=True)
            status = last_news_status()
        except Exception as exc:
            log.error("KAP bildirim yayın hatası (%s): %s", item.title[:60], exc)
        if slug:
            log.info("KAP bildirimi yayınlandı: %s (kalan kuyruk: %d).", slug, len(self.queue))
        key = self._key(item)
        if status == "published" and slug:
            self._record_publication(item, slug)
        if status in ("published", "duplicate"):
            self._clear_attempts(key)
            self._mark_seen(item)
        elif status == "paused":
            # Acil durdurma: deneme sayılmaz, sonraki taramada yeniden denenir.
            self._queued.discard(key)
        else:
            attempts = self._bump_attempts(key)
            if attempts >= MAX_PUBLISH_ATTEMPTS:
                log.error(
                    "KAP bildirimi %d denemede yayınlanamadı (son durum=%s); deneme sınırı aşıldı, "
                    "bir daha denenmeyecek — elle kontrol gerekir: %s", attempts, status, item.title[:120],
                )
                self._record_failure(item, status)
                self._mark_seen(item)
            else:
                self._queued.discard(key)
                log.warning(
                    "KAP bildirimi yayınlanamadı (durum=%s, deneme %d/%d); görüldü işaretlenmedi, sonraki "
                    "taramada yeniden denenecek: %s", status, attempts, MAX_PUBLISH_ATTEMPTS, item.title[:80],
                )
        return slug

    # ---- yeniden deneme sayacı (kalıcı) ------------------------------------------

    def _attempts(self) -> dict:
        try:
            return dict(self._state.get("publish_attempts", {}) or {})
        except Exception:  # noqa: BLE001 — test durum nesneleri get() taşımayabilir
            return dict(getattr(self, "_mem_attempts", {}))

    def _save_attempts(self, data: dict) -> None:
        try:
            self._state.set("publish_attempts", data)
        except Exception:  # noqa: BLE001
            self._mem_attempts = data

    def _bump_attempts(self, key: str) -> int:
        data = self._attempts()
        data[key] = int(data.get(key, 0)) + 1
        self._save_attempts(data)
        return data[key]

    def _clear_attempts(self, key: str) -> None:
        data = self._attempts()
        if key in data:
            data.pop(key)
            self._save_attempts(data)

    def _record_publication(self, item: Disclosure, slug: str) -> None:
        """Bu koşuda rapora dönüşen bildirim: yayın kapısı kırılırsa `publish_gate` geri alır."""
        try:
            record_publication(self._state, key=self._key(item), title=item.title, date=item.date,
                               index=item.disclosure_index or "", slug=slug)
        except Exception:  # noqa: BLE001 — test durum nesneleri get/set taşımayabilir
            pass

    def _record_failure(self, item: Disclosure, status: str) -> None:
        try:
            failed = list(self._state.get("failed_disclosures", []) or [])
            failed.append({"title": item.title, "date": item.date, "index": item.disclosure_index, "status": status})
            self._state.set("failed_disclosures", failed[-200:])
        except Exception:  # noqa: BLE001
            pass

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
                source,
                company=company,
                ticker=ticker,
                publish=True,
                make_pdf=True,
                disclosure_date=item.date,
            )
        except Exception as exc:
            log.error("Halka arz otomatik analizi başarısız (%s); haber raporuna düşülüyor.", exc)
            self._publish_disclosure(item)
            return None

        if result.slug:
            self._record_publication(item, result.slug)
            self._mark_seen(item)
            log.info("IPO bildirimi yayınlandı: %s (kalan kuyruk: %d).", result.slug, len(self.queue))
            link = f"{settings.site_url}/rapor/{result.slug}"
            code = f" ({ticker})" if ticker and ticker != company else ""
            with outbox_context(kap_index=item.disclosure_index, source_key=self._key(item), kind="ipo"):
                self.social.broadcast(
                    f"HALKA ARZ BELGESİ ÖZETİ: {company}{code}\n{link}\n#HalkaArz #BIST",
                    image_path=result.image_path,
                    verbatim=[company],
                )
        else:
            # Analiz yayınlanamadıysa bildirim kaybolmasın: yalın KAP raporu.
            self._publish_disclosure(item)
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

    @staticmethod
    def _flush_outbox() -> None:
        """Uzun ömürlü (git'siz, kapısız) mod: giden kutusu hemen gönderilir. GitHub Actions bu yolu
        KULLANMAZ (``--once``); orada gönderim push sonrası ayrı adımdır."""
        try:
            send_outbox()
        except Exception:  # noqa: BLE001 — gönderim hatası döngüyü durdurmaz
            log.exception("Giden kutusu gönderilemedi")

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
            self._flush_outbox()

            time.sleep(self.publish_interval)
