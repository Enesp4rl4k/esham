"""Piyasa raporu orkestrasyonu.

Akış: veri topla -> AI ile bülten üret -> marka kartı oluştur -> web'e yayınla
(içerik köprüsü, kart da /public/cards'a kopyalanır) -> sosyal medyada aynı
kartla paylaş. Her adım kendi hatasını yönetir; bir kaynak bozulsa da pipeline
mümkün olduğunca ilerler.

Görsel notu: `publishing/cards.py`'deki CardGenerator TEK görsel üretir; bu görsel
hem tweet'e hem web hero/OG'ye gider (tek üretim, tek kaynak, marka tutarlılığı).
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError as FuturesTimeout
from pathlib import Path

import requests

from .ai import MarketAIAnalyzer
from .ai.analyzer import NEUTRAL_RULES
from .config import get_logger, settings
from datetime import datetime

from . import market_text
from .formatting import TR_TZ, tr_date, tr_datetime, tr_number, tr_pct
from .neutral import strip_banned
from .sentences import safe_truncate
from .publishing import ContentStore, ReportDraft
from .publishing.content_store import slugify
from .publishing.cards import CardGenerator, CardSpec
from .publishing.social import SocialPublisher
from .publishing.pdf_report import generate_pdf
from .publishing.stock_data import write_stock_json
from .publishing.ticker_data import update_ticker_data
from .publishing.turib_data import update_turib_market_data
from .sources import Disclosure, MarketSnapshot
from .sources.unsplash import PexelsSource as _PhotoSource
from .sources.bist import BistSource
from .sources.calendar import EconomicCalendarSource
from .sources.global_macro import GlobalMacroSource
from .sources.kap import KapSource
from .sources.news_detector import MarketEvent
from .sources.peer import PeerSource
from .sources.sector import SectorSource, movers_lines
from .sources.turib import TuribSource
from .sources.viop import ViopSource, assess_margin_stress

log = get_logger(__name__)

_cards = CardGenerator()


def _now() -> datetime:
    """Rapor üretim anı (TSİ). Testler sabit zamana bağlar; tazelik kararları buna göre verilir."""
    return datetime.now(TR_TZ)


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


def gather_snapshot() -> MarketSnapshot:
    """Tüm veri kaynaklarından PARALEL olarak veri toplar (ThreadPoolExecutor).

    Her kaynak kendi try/except ile sarılır — bir kaynak bozulsa diğerleri
    etkilenmez (graceful degradation). Toplam bekleme süresi en yavaş kaynakla
    sınırlıdır (sıralı değil); GitHub Actions timeout riskini minimize eder.

    KAP bildirimleri kap_filter.is_significant() ile süzülür — devre kesici,
    genel kurul tutanağı, imza sirküleri gibi rutin bildirimler sabah
    bültenine ve tweet thread'ine girmez.
    """
    from .sources.kap_filter import is_significant as _kap_significant

    log.info("Piyasa verileri toplanıyor (BIST + KAP + Takvim + Makro + VİOP + Sektör) [paralel]...")

    snapshot = MarketSnapshot()

    def _filtered_disclosures() -> list:
        from .sources.kap_filter import score as _kap_score
        raw = KapSource().latest_disclosures()
        
        # 1. Filtre: Sadece önemli eşiği geçenleri al
        candidates = [d for d in raw if _kap_significant(d)]
        
        # 2. Şirket kotası: Aynı şirketten sadece en yüksek skorlu 1 bildirimi al
        by_company = {}
        for d in candidates:
            sc = _kap_score(d)
            comp_key = (d.ticker or d.company).strip().upper()
            if comp_key not in by_company or sc > by_company[comp_key][0]:
                by_company[comp_key] = (sc, d)
                
        # 3. Sıralama ve Tavan Kotası: En yüksek skorlu ilk 8 bildirimi seç
        sorted_pairs = sorted(by_company.values(), key=lambda x: x[0], reverse=True)
        filtered = [pair[1] for pair in sorted_pairs[:8]]
        
        log.info("KAP filtre: %d / %d bildirim filtrelendi, tekilleştirilmiş en önemli %d bildirim seçildi.", len(candidates), len(raw), len(filtered))
        return filtered

    # Her kaynak: (snapshot_alanı, callable)
    tasks: list[tuple[str, object]] = [
        ("bist",        lambda: BistSource().market_summary()),
        ("disclosures", _filtered_disclosures),
        ("calendar",    lambda: EconomicCalendarSource().daily_events()),
        ("macro",       lambda: GlobalMacroSource().snapshot()),
        ("viop_quote",  lambda: ViopSource().market_quote()),
        ("viop_margin", lambda: ViopSource().margin_snapshot()),
        ("sector",      lambda: SectorSource().snapshot()),
        ("turib",       lambda: TuribSource().snapshot()),
    ]

    # Her kaynak en fazla 30 saniye bekler; toplam paralel bekleme ~30s olur
    _FETCH_TIMEOUT = 30

    with ThreadPoolExecutor(max_workers=len(tasks)) as pool:
        future_to_field = {pool.submit(fn): field for field, fn in tasks}
        for future in as_completed(future_to_field, timeout=_FETCH_TIMEOUT + 5):
            field = future_to_field[future]
            try:
                result = future.result(timeout=_FETCH_TIMEOUT)
                setattr(snapshot, field, result)
            except FuturesTimeout:
                log.warning("%s kaynağı zaman aşımına uğradı; atlanıyor.", field)
            except Exception as exc:
                log.warning("%s kaynağı başarısız (%s); atlanıyor.", field, exc)

    log.info(
        "Snapshot hazır — KAP: %d bildirim, takvim: %d olay, sektör: %d, makro: %s",
        len(snapshot.disclosures),
        len(snapshot.calendar),
        len(snapshot.sector),
        "✓" if snapshot.macro else "✗",
    )
    return snapshot


def run_morning_report(publish_social: bool = True) -> str | None:
    """Sabah bültenini üretir, yayınlar ve rapor slug'ını döner."""
    log.info("=== Esham Sabah Raporu başlatılıyor ===")

    snapshot = gather_snapshot()

    analyzer = MarketAIAnalyzer()
    now = _now()
    if snapshot.macro is not None:
        _drop_stale_macro(snapshot.macro, now)
    # Rapor + tweet thread tek AI çağrısında üretilir (rate limit önlemi)
    body, ai_used, thread_tweets = analyzer.generate_morning_report_and_thread(snapshot, now=now)

    bist = snapshot.bist
    # Sabah raporu seans ÖNCESİ de koşabilir: endeks rakamı "güne başladı" diye değil, ne olduğu ve hangi
    # zamana ait olduğuyla yazılır. Zaman damgası yoksa/eskiyse BIST cümlesi hiç yazılmaz.
    bist_line = market_text.bist_last_short(bist, now)
    summary = " ".join(
        p for p in (bist_line, "Küresel makro gelişmeler ve KAP gündemi sabah bülteninde.") if p
    )
    bist_ok = bist_line is not None
    card_headline = (
        f"Son işlem {tr_datetime(bist.as_of)} — sabah bülteni" if bist_ok and bist and bist.as_of
        else "Küresel makro ve KAP gündemli sabah bülteni"
    )

    card_path = _render_card(
        CardSpec(
            category="bist",
            kicker=f"{bist.index} Endeksi" if bist else "BIST",
            headline=card_headline,
            stat_value=bist.price if bist_ok and bist else "",
            stat_change=bist.change if bist_ok and bist else "",
            sparkline=BistSource().fetch_closes("1d", "15m") if bist_ok else None,
            template="bist",
        )
    )

    draft = ReportDraft(
        title="BIST & Küresel Piyasalar Sabah Raporu",
        category="bist",
        summary=summary,
        body=body,
        sources=["KAP", "BIST", "Ekonomik Takvim"],
        tags=["BIST100", "Sabah Raporu", "Makro"],
        ai_generated=ai_used,
        image_path=card_path,
    )

    if ContentStore().publish(draft) is None:
        log.error("Sabah raporu guardrail'a takıldı; yayın ve paylaşım iptal.")
        _cleanup(card_path)
        return None
    slug = draft.resolved_slug()

    # PDF bülteni üret — web/public/reports/{slug}.pdf
    pdf_path: Path | None = None
    try:
        pdf_path = generate_pdf(
            body_md=draft.body,  # ContentStore'da süzülmüş gövde
            snapshot=snapshot,
            slug=slug,
            title="BIST & Küresel Piyasalar Sabah Raporu",
        )
        if pdf_path:
            log.info("Sabah bülteni PDF üretildi: %s", pdf_path)
    except Exception as exc:
        log.warning("PDF üretilemedi (devam ediliyor): %s", exc)

    if publish_social:
        # Thread hazır (rapor ile aynı AI çağrısında üretildi)
        if thread_tweets:
            # Son tweet'e rapor + PDF linkini ekle
            last = thread_tweets[-1]
            pdf_suffix = (
                f"\nPDF Bülten: {settings.site_url}/reports/{slug}.pdf"
                if pdf_path
                else ""
            )
            link_suffix = f"\n{settings.site_url}/rapor/{slug}{pdf_suffix}\n#BIST100 #Borsa"
            if len(last) + len(link_suffix) <= 280:
                thread_tweets[-1] = last + link_suffix
            else:
                extra = f"Tam rapor: {settings.site_url}/rapor/{slug}\n#BIST100 #Borsa"
                if pdf_path:
                    extra += f"\nPDF: {settings.site_url}/reports/{slug}.pdf"
                thread_tweets.append(extra)
            SocialPublisher().broadcast_thread(thread_tweets, image_path=card_path)
        else:
            # Fallback: tek tweet
            pdf_line = (
                f"\nPDF Bülten: {settings.site_url}/reports/{slug}.pdf"
                if pdf_path
                else ""
            )
            SocialPublisher().broadcast(
                f"Günün BIST & küresel piyasa sabah raporu yayında.\n"
                f"{settings.site_url}/rapor/{slug}{pdf_line}\n#BIST100 #Borsa",
                image_path=card_path,
            )
    _cleanup(card_path)

    # Ticker band JSON'unu güncelle — ana sayfadaki canlı bant bu dosyadan beslenir.
    try:
        update_ticker_data()
    except Exception as exc:
        log.warning("Ticker JSON güncellenemedi (sabah raporu): %s", exc)

    try:
        update_turib_market_data()
    except Exception as exc:
        log.warning("TÜRİB Piyasa JSON güncellenemedi: %s", exc)

    log.info("=== Süreç tamamlandı: %s ===", slug)
    return slug


def run_viop_report(
    prior_pct: float | None = None, publish: bool = True, publish_social: bool = True
) -> str | None:
    """VİOP piyasa + marketwide teminat stresi raporunu üretir ve yayınlar."""
    src = ViopSource()
    quote = src.market_quote()
    if quote is None:
        log.error("VİOP piyasa kotasyonu temin edilemedi; örnek veri yayınlanamaz.")
        return None
    snap = src.margin_snapshot()
    if snap is None or snap.required_margin_total_tl <= 0:
        log.error("Takasbank resmi teminat verisi temin edilemedi; yapay veri yayınlanamaz.")
        return None

    if prior_pct is None:
        from .state import get_state
        # Önceki kayıt yoksa bugünkü değerle "kıyaslanıp" Sabit denmez: karşılaştırma yok (None).
        prior_pct = get_state().get_margin_prev_pct()
    stress = assess_margin_stress(snap.margin_call_to_required_pct, prior_pct)
    margin_as_of = getattr(snap, "as_of", "") or ""
    from .state import get_state
    get_state().set_margin_prev_pct(snap.margin_call_to_required_pct)

    futures_line = (
        f"| Vadeli {quote.futures_symbol} | {quote.futures_price} | {quote.futures_change or '—'} |\n"
        if quote.has_futures
        else ""
    )
    fetched = f"\n\nTradingView verisi; alınma zamanı {tr_datetime(quote.fetched_at)}." if quote.fetched_at else ""
    body = f"""## VİOP Piyasa Görünümü

| Enstrüman | Son değer | Önceki kapanışa göre |
| --- | --- | --- |
| BIST 30 endeksi ({quote.index_symbol}, dayanak) | {quote.index_price} | {quote.index_change} |
{futures_line}{fetched}

## Piyasa Geneli Teminat (Takasbank)

Veri tarihi: {margin_as_of or 'belirtilmemiş'}

| Gösterge | Değer |
| --- | --- |
| Teminatlı hesap | {tr_number(snap.margined_account_count, 0)} |
| Margin-call toplam | {snap.margin_call_pretty()} |
| Gereken teminat | {snap.required_pretty()} |
| Margin-call / Gereken | {tr_pct(snap.margin_call_to_required_pct, 3, signed=False)} |

## Teminat Stresi: {stress.level}

{stress.note}

> **Margin-call/gereken teminat** oranı, teminat tamamlama çağrısı yapılan tutarın
> gereken toplam teminata oranıdır (Takasbank verisi)."""

    summary = (
        f"VİOP teminat stresi ({margin_as_of or 'veri tarihi belirtilmemiş'}): {stress.level}. "
        f"Margin-call toplam {snap.margin_call_pretty()}."
    )
    if not publish:
        return None

    card_path = _render_card(
        CardSpec(
            category="viop",
            kicker=f"{quote.index_symbol} VİOP Görünümü",
            headline=stress.note,
            # stat_value: margin_call_to_required_pct → stres bandı doluluk için
            stat_value=f"{snap.margin_call_to_required_pct:.3f}",
            stat_change=f"XU030: {quote.index_price} ({quote.index_change})",
            metrics=[
                ("Margin-Call", snap.margin_call_pretty()),
                ("Gereken Teminat", snap.required_pretty()),
            ],
            stress_level=stress.level,
            template="viop",
        )
    )

    draft = ReportDraft(
        title="VİOP Piyasa & Teminat Stresi Raporu",
        category="viop",
        summary=summary,
        body=body,
        sources=["TradingView", "Takasbank"],
        tags=["VİOP", "Teminat", "Margin Call"],
        ai_generated=False,
        image_path=card_path,
    )
    if ContentStore().publish(draft) is None:
        log.error("VİOP raporu guardrail'a takıldı; iptal.")
        _cleanup(card_path)
        return None
    slug = draft.resolved_slug()

    if publish_social:
        SocialPublisher().broadcast(
            f"VİOP piyasa görünümü: BIST 30 ({quote.index_symbol}) {quote.index_price}, "
            f"önceki kapanışa göre {quote.index_change}. Teminat stresi ({margin_as_of or 'tarih yok'}): "
            f"{stress.level}.\n"
            f"{settings.site_url}/rapor/{slug}\n#VİOP #BIST100",
            image_path=card_path,
        )
    _cleanup(card_path)
    return slug


def _opening_viop_line() -> str:
    """Açılış notu için VİOP vadeli satırı; gerçek vadeli kotasyon yoksa boş döner.

    Geçici ağ hataları uyarı olarak loglanıp atlanır (yayın akışı durmaz); programlama
    hataları (AttributeError vb.) ise ERROR + traceback ile loglanır, sessizce yutulmaz.
    """
    try:
        quote = ViopSource().market_quote()
    except (requests.RequestException, ValueError, OSError) as exc:
        log.warning("Açılış VİOP verisi alınamadı: %s", exc)
        return ""
    except (AttributeError, TypeError, KeyError, NameError):
        log.exception("Açılış VİOP satırı programlama hatası nedeniyle atlandı.")
        return ""
    if quote is None or not quote.has_futures or not quote.futures_change:
        return ""
    when = f" (veri alınma zamanı {tr_datetime(quote.fetched_at)})" if quote.fetched_at else ""
    return (
        f"\n\n**VİOP Görünümü:** Vadeli endeks kontratı ({quote.futures_symbol}) {quote.futures_price}; "
        f"önceki kapanışa göre {quote.futures_change}{when}."
    )


def run_opening_report(publish_social: bool = False) -> str | None:
    """BIST açılış notu — anlık endeks, sektörler ve canlı veri senkronizasyonu."""
    # 1. Canlı Ticker JSON'unu güncelle (header ve hisse terminali için)
    try:
        update_ticker_data()
    except Exception as exc:
        log.warning("Açılış bülteni ticker güncelleme hatası: %s", exc)

    bist = BistSource().market_summary()
    if not bist or not bist.price:
        log.error("BIST verisi temin edilemedi; yapay veri basılmaması için rapor iptal edildi.")
        return None
    now = _now()
    open_sentence = market_text.bist_open(bist, now)
    if open_sentence is None:
        # Açılış alanı yoksa son fiyat "açılış" diye YAZILMAZ; bugünün seansına ait değilse rapor yok.
        log.error("Bugünün açılış verisi yok/doğrulanamadı (as_of=%s); açılış raporu üretilmedi.", bist.as_of)
        return None

    # Sektörler (günlük, önceki kapanışa göre) ve VİOP kotasyonu
    sector_summary = ""
    try:
        from .sources.sector import SectorSource
        moves = SectorSource().snapshot()
        if moves:
            sector_summary = (
                f"\n\n**Sektör endeksleri — {market_text.sector_heading_note(moves)}:**\n\n"
                + market_text.sector_movers_md(moves)
            )
    except Exception as exc:
        log.debug("Açılış sektörel görünüm alınamadı: %s", exc)

    viop_line = _opening_viop_line()

    open_val = bist.open_price
    open_chg = bist.open_change

    # Son işlem açılıştan farklıysa ne olduğu ve ne zamana ait olduğuyla eklenir ("seans içi" yalnız seans açıksa).
    current_note = ""
    last = market_text.bist_last(bist, now)
    if last and bist.price != bist.open_price:
        current_note = f" {last}{market_text.session_note(bist)}"

    body = f"""## BIST Seans Açılışı

{open_sentence}{current_note}{viop_line}{sector_summary}"""

    draft = ReportDraft(
        title=f"BIST Seans Açılışı ({tr_date(bist.as_of)}): {bist.index} {open_chg}",
        category="bist",
        summary=f"{open_sentence}{current_note}",
        body=body,
        sources=["Borsa İstanbul", "TradingView", "VİOP"],
        tags=["BIST100", "Açılış", "Seans"],
        ai_generated=False,
    )

    card_path = _render_card(
        CardSpec(
            category="bist",
            kicker=f"{bist.index} Açılış",
            headline="BIST açılış ve seans seyri.",
            stat_value=open_val,
            stat_change=open_chg,
            sparkline=BistSource().fetch_closes("5d", "30m"),
            template="bist",
        )
    )
    draft.image_path = card_path

    if ContentStore().publish(draft) is None:
        log.error("Açılış raporu guardrail'a takıldı; iptal.")
        _cleanup(card_path)
        return None
    slug = draft.resolved_slug()
    if publish_social:
        SocialPublisher().broadcast(
            f"BIST açılış ({tr_date(bist.as_of)}): {bist.index} {open_val}, açılışın önceki kapanışa göre farkı {open_chg}\n"
            f"{settings.site_url}/rapor/{slug} #BIST100",
            image_path=card_path,
        )
    _cleanup(card_path)
    return slug


def run_closing_report(publish_social: bool = True) -> str | None:
    """Kapanış bülteni — BIST + VİOP kapanış özeti."""
    bist = BistSource().market_summary()
    if not bist or not bist.price:
        log.error("BIST verisi temin edilemedi; yapay veri basılmaması için rapor iptal edildi.")
        return None
    close_sentence = market_text.bist_close(bist, _now())
    if close_sentence is None:
        # "kapattı" yalnız bugünün seansı bitmişse doğrudur; seans açıkken ya da veri bugüne ait değilse yazılmaz.
        log.error("Bugünün kapanışı doğrulanamadı (as_of=%s, seans açık=%s); kapanış raporu üretilmedi.",
                  bist.as_of, bist.market_open)
        return None
    quote = ViopSource().market_quote()
    if quote is None:
        log.error("VİOP kotasyonu temin edilemedi; örnek veri basılmaması için kapanış raporu iptal edildi.")
        return None
    body = f"""## Kapanış Görünümü

{close_sentence}

| Piyasa | Son değer | Önceki kapanışa göre |
| --- | --- | --- |
| BIST {bist.index} | {bist.price} | {bist.change} |
| BIST 30 ({quote.index_symbol}, VİOP dayanağı) | {quote.index_price} | {quote.index_change} |"""
    draft = ReportDraft(
        title=f"Kapanış Bülteni ({tr_date(bist.as_of)}): BIST {bist.index} {bist.change}",
        category="bist",
        summary=close_sentence,
        body=body,
        sources=["BIST", "TradingView"],
        tags=["BIST", "Kapanış"],
        ai_generated=False,
    )

    card_path = _render_card(
        CardSpec(
            category="bist",
            kicker=f"{bist.index} Kapanış",
            headline=f"BIST 30 ({quote.index_symbol}) {quote.index_price}, önceki kapanışa göre {quote.index_change}.",
            stat_value=bist.price,
            stat_change=bist.change,
            sparkline=BistSource().fetch_closes("1d", "15m"),
            template="bist",
        )
    )
    draft.image_path = card_path

    if ContentStore().publish(draft) is None:
        log.error("Kapanış raporu guardrail'a takıldı; iptal.")
        _cleanup(card_path)
        return None
    slug = draft.resolved_slug()
    if publish_social:
        SocialPublisher().broadcast(
            f"{close_sentence}\n"
            f"BIST 30 ({quote.index_symbol}): {quote.index_price}, önceki kapanışa göre {quote.index_change}\n"
            f"{settings.site_url}/rapor/{slug} #BIST100 #Borsa",
            image_path=card_path,
        )
    _cleanup(card_path)

    # Kapanışta da ticker JSON'u güncelle — günün son canlı fiyatları.
    try:
        update_ticker_data()
    except Exception as exc:
        log.warning("Ticker JSON güncellenemedi (kapanış): %s", exc)

    try:
        update_turib_market_data()
    except Exception as exc:
        log.warning("TÜRİB Piyasa JSON güncellenemedi: %s", exc)

    return slug


def run_gundem_report(
    headline: str,
    body: str,
    summary: str,
    tags: list[str] | None = None,
    publish_social: bool = True,
) -> str | None:
    """Gündem haberi / anlık piyasa yorumu yayınlar.

    Parametreler
    ----------
    headline : str
        Kart ve tweet için kısa başlık (ör. "Fed faiz kararı açıklandı").
    body : str
        Markdown formatında rapor gövdesi.
    summary : str
        Tek cümlelik özet (OG description ve liste görünümü için).
    tags : list[str] | None
        İsteğe bağlı etiketler; verilmezse ["Gündem"] kullanılır.
    publish_social : bool
        False verilirse sosyal medya paylaşımı atlanır.
    """
    if not tags:
        tags = ["Gündem"]

    card_path = _render_card(
        CardSpec(
            category="gundem",
            kicker="Gündem",
            headline=headline,
            stat_value="",
            stat_change="",
            template="gundem",
        )
    )

    draft = ReportDraft(
        title=headline,
        category="gundem",
        summary=summary,
        body=body,
        sources=["Güncel Haberler"],
        tags=tags,
        ai_generated=False,
        image_path=card_path,
    )

    if ContentStore().publish(draft) is None:
        log.error("Gündem raporu guardrail'a takıldı; iptal.")
        _cleanup(card_path)
        return None
    slug = draft.resolved_slug()

    if publish_social:
        SocialPublisher().broadcast(
            f"{headline}\n{settings.site_url}/rapor/{slug}\n#Gündem #BIST",
            image_path=card_path,
        )
    _cleanup(card_path)
    log.info("Gündem raporu yayınlandı: %s", slug)
    return slug


def run_sector_report(publish_social: bool = True) -> str | None:
    """Haftalık sektör endeksi değişimleri — yalnız veri tablosu (yorum/yönlendirme yok)."""
    # Eskiden "haftalık" başlığıyla GÜNLÜK değişim (chartPreviousClose) yayınlanıyordu; artık gerçekten
    # haftalık: son kapanış / önceki haftanın son kapanışı (sources/bars.period_change).
    moves = SectorSource().snapshot(period="1w")
    if not moves:
        log.error("Haftalık sektör verisi temin edilemedi; rapor üretilmedi.")
        return None
    rows = "\n".join(f"| {m.name} | {m.change_str} |" for m in moves)
    ups, downs = movers_lines(moves, 3, with_values=True)
    note = market_text.sector_heading_note(moves)
    body = f"""## Haftalık Sektör Endeksi Değişimleri

Sektör endeksleri — {note}.

| Sektör | Haftalık değişim |
| --- | --- |
{rows}

{market_text.sector_movers_md(moves)}"""
    draft = ReportDraft(
        title="Haftalık Sektör Endeksi Değişimleri",
        category="bist",
        summary=f"Sektör endeksleri — {note}. Yükselenler: {ups}. Düşenler: {downs}.",
        body=body,
        sources=["TradingView"],
        tags=["Sektör", "BIST"],
        ai_generated=False,
    )

    card_path = _render_card(
        CardSpec(
            category="bist",
            kicker="Haftalık Sektör Değişimleri",
            headline=safe_truncate(f"Yükselenler: {ups}. Düşenler: {downs}.", 120),
            bars=[(m.name, m.change_pct) for m in moves[:6]],
            template="bist",
        )
    )
    draft.image_path = card_path

    if ContentStore().publish(draft) is None:
        log.error("Sektör raporu guardrail'a takıldı; iptal.")
        _cleanup(card_path)
        return None
    slug = draft.resolved_slug()
    if publish_social:
        SocialPublisher().broadcast(
            f"Sektör endeksleri — {note}. Yükselenler: {ups}.\n"
            f"{settings.site_url}/rapor/{slug} #BIST #Sektör",
            image_path=card_path,
        )
    _cleanup(card_path)
    return slug


def run_peer_report(sector_key: str = "bankacilik", publish_social: bool = True) -> str | None:
    """Sektör içi eş/değer kıyası raporu (peer multiples).

    `sources/peer.py` çarpanları (F/K, PD/DD, FD/FAVÖK) medyanıyla hangi hissenin
    sektör medyanına göre ucuz/pahalı olduğunu gösterir. Veri kaynağından bağımsız
    çalışır: crumb yoksa fiyat performansıyla devam eder; hiç veri yoksa rapor üretilmez.
    """
    snap = PeerSource().snapshot(sector_key)
    if not snap.peers:
        log.error("Peer verisi temin edilemedi (%s); örnek veri yayınlanamaz.", sector_key)
        return None

    rows = "\n".join(
        f"| {p.ticker} | {p.price_str} | {p.change_str} | "
        f"{_fmt_mult(p.pe)} | {_fmt_mult(p.pb)} | {_fmt_mult(p.ev_ebitda)} | "
        f"{_fmt_mult(p.dividend_yield, pct=True)} | {_fmt_mult(p.roe, pct=True)} |"
        for p in snap.peers
    )
    median_line = (
        f"| **Medyan** | — | — | **{_fmt_mult(snap.median_pe)}** | "
        f"**{_fmt_mult(snap.median_pb)}** | **{_fmt_mult(snap.median_ev_ebitda)}** | "
        f"**{_fmt_mult(snap.median_dividend_yield, pct=True)}** | — |"
    )

    # Yalnız tarafsız tablo: "en ucuz/pahalı", medyana göre "iskonto/prim" yorumu ve sıralama YOK.
    body = f"""## {snap.sector_name} — Çarpan Tablosu

| Hisse | Fiyat | Günlük | F/K | PD/DD | FD/FAVÖK | Temettü % | FÖK % |
| --- | --- | --- | --- | --- | --- | --- | --- |
{rows}
{median_line}

- Medyan, bu tablodaki hisselerden hesaplanır ve gün içi fiyatlarla değişir.

*Çarpanlar Yahoo Finance özet verisinden alınır.*"""

    summary = (
        f"{snap.sector_name} çarpan tablosu: medyan F/K {_fmt_mult(snap.median_pe)}, "
        f"medyan PD/DD {_fmt_mult(snap.median_pb)}."
    )

    card_path = _render_card(
        CardSpec(
            category="bist",
            kicker=f"{snap.sector_name} — Çarpan Tablosu",
            headline=f"Medyan F/K {_fmt_mult(snap.median_pe)} · PD/DD {_fmt_mult(snap.median_pb)}",
            metrics=[
                ("Medyan F/K", _fmt_mult(snap.median_pe)),
                ("Medyan PD/DD", _fmt_mult(snap.median_pb)),
                ("Temettü", _fmt_mult(snap.median_dividend_yield, pct=True)),
                ("Örneklem", str(len(snap.peers))),
            ],
            bars=[(p.ticker, p.change_pct) for p in snap.peers if p.change_pct is not None][:6],
            template="bist",
        )
    )

    draft = ReportDraft(
        title=f"{snap.sector_name} Sektörü Çarpan Tablosu",
        category="bist",
        summary=safe_truncate(summary, 200),
        body=body,
        sources=["Yahoo Finance"],
        tags=["Peer", "Çarpan", snap.sector_name, "BIST"],
        ai_generated=False,
        image_path=card_path,
    )
    if ContentStore().publish(draft) is None:
        log.error("Peer raporu guardrail'a takıldı; iptal.")
        _cleanup(card_path)
        return None
    slug = draft.resolved_slug()
    if publish_social:
        SocialPublisher().broadcast(
            f"{snap.sector_name} çarpan tablosu yayında: medyan F/K "
            f"{_fmt_mult(snap.median_pe)}.\n{settings.site_url}/rapor/{slug} #BIST #Çarpan",
            image_path=card_path,
        )
    _cleanup(card_path)
    return slug


def _fmt_mult(value: float | None, *, pct: bool = False) -> str:
    """Çarpan/çeyrek değeri kısa biçimde yazar (yoksa tire)."""
    if value is None:
        return "—"
    if pct:
        return tr_pct(value, 1, signed=False)  # eskiden "%3.0" (İngilizce ondalık nokta)
    return tr_number(value, 2)


def _drop_stale_macro(snap, now: datetime):
    """Tazelik koruması: veri zamanı sınırdan eski enstrüman tabloya hiç girmez (eski veri güncel sunulmaz)."""
    from .freshness import market_as_of_status

    kept = [t for t in snap.tickers if market_as_of_status(t.as_of, now) != "stale"]
    if len(kept) != len(snap.tickers):
        log.warning("Eski makro veri atlandı: %s",
                    [t.label for t in snap.tickers if t not in kept])
    snap.tickers = kept
    return snap


def run_global_report(publish_social: bool = True) -> str | None:
    """Küresel makro görünümü raporu.

    ABD 10Y, EUR/USD, Altın, VIX, Brent verilerini GlobalMacroSource'dan çeker.
    Kart: sol başlık + sağ ticker board (_render_global şablonu).
    Rapor: markdown tablosu.
    """
    log.info("=== Küresel Makro Raporu başlatılıyor ===")
    snap = _drop_stale_macro(GlobalMacroSource().snapshot(), _now())
    if not snap.tickers:
        log.error("Küresel makro verisi temin edilemedi; örnek veri yayınlanamaz.")
        return None
    board = snap.ticker_board()

    # Başlık: en büyük mutlak YÜZDE değişim (yalnız veri; "risk iştahı" yorumu yok). Faizler (baz puanla
    # ölçülür) yüzde değişimle kıyaslanamayacağı için bu sıralamaya girmez.
    headline_tickers = [t for t in snap.tickers if not t.is_rate and abs(t.change_pct) > 0.3]
    if headline_tickers:
        top = max(headline_tickers, key=lambda t: abs(t.change_pct))
        headline = f"Önceki kapanışa göre en büyük mutlak yüzde değişim: {top.label} {top.change_str}."
    else:
        headline = "İzlenen küresel göstergelerde önceki kapanışa göre %0,3'ü aşan değişim yok."

    summary = snap.summary_line()

    # AI ile detaylı rapor üret
    from .ai.analyzer import MarketAIAnalyzer
    ai_body, ai_tweet = MarketAIAnalyzer().generate_global_report(snap.to_markdown_table())

    if ai_body:
        body = f"## Küresel Makro Görünümü\n\n{snap.to_markdown_table()}\n\n{ai_body}"
    else:
        body = f"## Küresel Makro Görünümü\n\n{snap.to_markdown_table()}\n\n## Özet\n\n{headline}"

    card_path = _render_card(
        CardSpec(
            category="global",
            kicker="Küresel Makro",
            headline=headline,
            ticker_board=board,
            template="global",
        )
    )

    draft = ReportDraft(
        title="Küresel Makro Görünümü",
        category="global",
        summary=summary,
        body=body,
        sources=["Yahoo Finance"],
        tags=["Makro", "ABD", "Faiz", "Döviz", "Altın"],
        ai_generated=bool(ai_body),
        image_path=card_path,
    )

    if ContentStore().publish(draft) is None:
        log.error("Küresel makro raporu guardrail'a takıldı; iptal.")
        _cleanup(card_path)
        return None
    slug = draft.resolved_slug()

    if publish_social:
        final_tweet = ai_tweet if ai_tweet else f"Küresel makro görünümü. {summary}\n"
        final_tweet += f"\n{settings.site_url}/rapor/{slug}\n#Makro #Borsa #KüreselPiyasalar"
        SocialPublisher().broadcast(
            final_tweet,
            image_path=card_path,
        )
    _cleanup(card_path)
    log.info("=== Küresel Makro Raporu tamamlandı: %s ===", slug)
    return slug


_LAST_NEWS_STATUS = "none"


def last_news_status() -> str:
    """Son ``run_news_report`` çağrısının sonucu: published | duplicate | paused | blocked | error | none.

    news_stream bunu bildirimi "görüldü" işaretlemek için kullanır: yalnız kalıcı bir karardan sonra
    (published/duplicate) işaretlenir; diğer durumlarda bildirim sonraki taramada yeniden denenir.
    """
    return _LAST_NEWS_STATUS


def _set_status(status: str) -> None:
    global _LAST_NEWS_STATUS
    _LAST_NEWS_STATUS = status


def run_news_report(
    event: MarketEvent | None = None,
    disclosure: Disclosure | None = None,
    publish_social: bool = True,
) -> str | None:
    """KAP bildirimi veya makro/sektör olayı için kısa haber raporu.

    KAP modu: çıktı, bildirimde NE açıklandığının tarafsız özetidir. Rapor iki parçadan oluşur:
    (1) ÜRETİLMİŞ kısım (LLM/şablon özeti) — tarafsız dil süzgecinden geçer; (2) BİREBİR kısım —
    KAP başlığı AYNEN, şirket, tarih, KAP bildirim türü, bildirimde geçen tutarlar, KAP bağlantısı;
    süzülmez. Süzgeç/guardrail üretilmiş kısmı reddederse yalın rapor (yalnız birebir kısım) yayınlanır:
    bir bildirim hiçbir koşulda sessizce kaybolmaz.

    Eskiden burada eklenen "Mega İş Anlaşması" etiketi, teknik seviyeler (bist_quant.get_key_levels),
    Yahoo temel çarpanları ve karttaki hisse fiyatı/RSI/destek çipleri KALDIRILDI.
    """
    _set_status("none")
    if event is None and disclosure is None:
        log.error("run_news_report: event veya disclosure gerekli.")
        _set_status("error")
        return None

    from .neutral import NOTE_GENERIC, NOTE_KAP, REPORT_SCHEMA_VERSION, classify_filing, strip_banned
    from .turkish import tr_upper

    analyzer = MarketAIAnalyzer()
    facts = ""
    kap_meta: dict | None = None
    verbatim_summary = False
    fallback_summary = ""
    verbatim_parts: list[str] = []
    ticker = ""

    # ---- KAP bildirimi modu -------------------------------------------------------
    if disclosure is not None:
        from .ai.analyzer import filing_facts_markdown

        title = disclosure.title  # KAP başlığı AYNEN — süzülmez
        company = disclosure.company
        ticker = disclosure.ticker  # evren dışı çok pay gruplu şirkette "" olabilir (tahmin edilmez)
        disc_type = disclosure.disclosure_type
        raw = disclosure.raw_text or title
        if disclosure.disclosure_index:
            detail = KapSource().get_detail_text(disclosure.disclosure_index)
            if detail:
                raw = f"{raw}\n\nDetay:\n{detail}"

        body, summary, tweet_text = analyzer.generate_news_analysis(
            title=title,
            disclosure_type=disc_type,
            company=company,
            ticker=ticker,
            raw_text=raw,
            is_insider=disclosure.is_insider,
        )
        facts = filing_facts_markdown(
            company, ticker, title, disc_type, raw, disclosure.disclosure_index or "", date=disclosure.date,
        )
        fallback_summary = title
        verbatim_summary = summary.strip() == title.strip()
        category = "bist"
        label = classify_filing(title, disc_type)
        card_kicker = tr_upper(label)
        tags = [t for t in (ticker, "KAP", "BIST") if t]
        card_headline = safe_truncate(title, 120)
        card_ticker_val = ticker
        post_disclaimer = NOTE_KAP
        verbatim_parts = [title]
        kap_meta = {
            "company": company,
            "type": disc_type or "",
            "index": disclosure.disclosure_index or "",
            "url": (f"https://www.kap.org.tr/tr/Bildirim/{disclosure.disclosure_index}"
                    if disclosure.disclosure_index else ""),
        }
        sources = ["KAP", ticker] if ticker else ["KAP"]

    # ---- Makro/sektör olay modu --------------------------------------------------
    else:
        assert event is not None  # mypy
        from .translation import ensure_turkish, is_mostly_english

        macro_context = ""
        try:
            macro_context = GlobalMacroSource().snapshot().summary_line()
        except Exception as exc:
            log.debug("Makro bağlam alınamadı: %s", exc)

        post_disclaimer = NOTE_GENERIC
        title_line = event.headline.split('\n')[0]
        if is_mostly_english(title_line):
            title_line = ensure_turkish(title_line)
            if not title_line:
                log.error("Haber başlığı İngilizce ve Türkçeleştirilemedi; iptal: %s", event.headline[:60])
                _set_status("error")
                return None
        title = title_line
        summary = title_line
        fallback_summary = title_line
        category = event.category
        _KICKER_MAP = {
            "SON_DAKIKA": "Küresel Piyasalar",
            "HISSE_HAREKET": "Hisse Hareketi",
            "BIST_HAREKET": "BIST Endeksi",
            "SEKTÖR_HAREKET": "Sektör Hareketi",
            "MAKRO_HAREKET": "Makro Piyasalar",
            "KRIPTO_HAREKET": "Kripto Piyasası",
            "TEKNOLOJI_HAREKET": "Teknoloji & AI",
        }
        tags = event.tags or ["Makro", "Piyasa"]
        card_kicker = "SON DAKİKA" if event.kind == "SON_DAKIKA" else event.label
        card_headline = safe_truncate(title_line if event.kind == "SON_DAKIKA" else event.headline, 120)
        card_ticker_val = "" if event.kind == "SON_DAKIKA" else event.label

        if event.kind in ("SON_DAKIKA", "HISSE_HAREKET", "TEKNOLOJI_HAREKET", "KRIPTO_HAREKET", "MAKRO_HAREKET"):
            ai_body, ai_summary, tweet_text = analyzer.generate_event_analysis(event=event, macro_context=macro_context)
            if ai_summary and ai_summary.strip().lower() != title.strip().lower():
                summary = ai_summary.strip()
            src_label = getattr(event, "source_name", "") or {
                "TEKNOLOJI_HAREKET": "TechCrunch / The Verge / Ars Technica",
                "KRIPTO_HAREKET": "CoinDesk / CoinTelegraph / Yahoo Finance",
                "HISSE_HAREKET": "Yahoo Finance / BIST",
            }.get(event.kind, "Küresel Haber Ajansları")
            src_url = getattr(event, "source_url", "")
            facts = f"> **Kaynak:** [{src_label}]({src_url})" if src_url else f"> **Kaynak:** {src_label}"
            body = ai_body
        elif event.kind == "SEKTÖR_HAREKET":
            body, summary, tweet_text = analyzer.generate_sector_movement_analysis(
                sector_name=event.label, change_pct=event.change_pct, headline=event.headline,
            )
        else:
            body, summary, tweet_text = analyzer.generate_event_analysis(event=event, macro_context=macro_context)
        sources = ([event.source_name] if getattr(event, "source_name", "") else (
            ["TechCrunch"] if event.kind == "TEKNOLOJI_HAREKET"
            else ["CoinDesk"] if event.kind == "KRIPTO_HAREKET"
            else ["Yahoo Finance"]
        ))
        _ = _KICKER_MAP

    draft = ReportDraft(
        title=title,
        category=category,
        summary=summary,
        body=body,
        facts=facts,
        summary_verbatim=verbatim_summary,
        fallback_summary=fallback_summary,
        sources=sources,
        tags=tags,
        ai_generated=settings.ai_enabled,
        schema_version=REPORT_SCHEMA_VERSION,
        kap=kap_meta,
        # KAP: aynı gün aynı başlıklı iki ayrı bildirim çakışmasın diye slug bildirim numarasını taşır.
        slug=(f"{slugify(title)}-{kap_meta['index']}" if kap_meta and kap_meta.get("index") else None),
    )
    store = ContentStore()
    # Yayın kararı karttan ÖNCE verilir: engellenen/mükerrer bildirim için kart boşuna çizilmez.
    decision = store.prepare(draft)
    if decision != "ok":
        _set_status(decision)
        log.warning("Haber raporu yayınlanmadı (durum=%s): %s", decision, title[:80])
        return None

    # ---- kart --------------------------------------------------------------------
    # KAP kartlarında manşet rakamı YOK: bildirimden anlamı ve birimiyle güvenle çıkarılamayan sayı
    # gösterilmez — eksik bilgi eksik kalır, uydurulmaz.
    sparkline = None
    if event is not None:
        if event.kind == "MAKRO_HAREKET":
            from .sources.global_macro import MACRO_TICKERS
            symbol = next((s for s, l, _, _ in MACRO_TICKERS if l == event.label), None)
            if symbol:
                sparkline = GlobalMacroSource().fetch_closes(symbol)
        elif event.kind == "KRIPTO_HAREKET":
            from .sources.crypto import CryptoSource, CRYPTO_TICKERS
            symbol = next((s for s, l in CRYPTO_TICKERS if l.lower() in event.label.lower() or l.lower() in event.headline.lower()), "BTC-USD")
            sparkline = CryptoSource().fetch_closes(symbol)
        elif event.kind in ("BIST_HAREKET", "SEKTÖR_HAREKET"):
            symbol = "XU100.IS" if event.kind == "BIST_HAREKET" else f"{event.label}.IS"
            sparkline = BistSource(symbol).fetch_closes()
        elif event.kind == "HISSE_HAREKET":
            from .sources.watchlist import WATCHLIST
            yf_symbol = next((s for s, t in WATCHLIST if t == event.label), f"{event.label}.IS")
            sparkline = BistSource(yf_symbol).fetch_closes()

    photo_path = None
    if category in {"gundem", "global", "kripto", "teknoloji"} and not sparkline:
        try:
            photo_path = _PhotoSource().fetch_photo(title, category)
        except Exception as exc:
            log.debug("Fotoğraf çekilemedi (%s); görselsiz devam.", exc)

    card_path = _render_card(
        CardSpec(
            category=category,
            kicker=card_kicker,
            headline=card_headline,
            ticker=card_ticker_val,
            template=category,
            sparkline=sparkline,
            photo_path=photo_path,
        )
    )
    draft.image_path = card_path

    if store.publish(draft, prepared=True) is None:
        _set_status(store.last_status)
        log.error("Haber raporu yayınlanamadı (durum=%s): %s", store.last_status, title[:80])
        _cleanup(card_path)
        return None
    slug = draft.resolved_slug()
    _set_status("published")

    if publish_social:
        link = f"{settings.site_url}/rapor/{slug}"
        hashtags = " ".join(f"#{t.replace(' ', '')}" for t in tags[:3])
        tweet_text = strip_banned(tweet_text or "")
        if not tweet_text or len(tweet_text.strip()) < 30 or draft.summary_verbatim:
            # Üretilmiş tweet yok/zayıf/süzgece takıldı → KAP başlığı (birebir) kullanılır.
            tweet_text = draft.summary if not draft.summary_verbatim else fallback_summary
        link_suffix = f"\n\n{link}\n{hashtags}"
        max_body = 280 - len(link_suffix)
        tweet_body = tweet_text.strip()
        tweet_body = safe_truncate(tweet_body, max_body)  # yarım sayı / açık parantez bırakmaz
        verbatim = [p for p in verbatim_parts if p] + ([tweet_body] if tweet_text == fallback_summary else [])
        SocialPublisher().broadcast(
            f"{tweet_body}{link_suffix}", image_path=card_path, disclaimer=post_disclaimer, verbatim=verbatim,
        )

    _cleanup(card_path)
    log.info("Haber raporu yayınlandı: %s", slug)
    return slug


def run_weekly_summary(publish_social: bool = True) -> str | None:
    """Haftanın özet raporu — Cuma kapanışında çalışır.

    Haftanın tüm haberlerini, en çok hareket eden sektörleri, makro gelişmeleri
    ve öne çıkan KAP bildirimlerini AI ile özetler. Sabah bülteninden farkı:
    geriye dönük haftalık perspektif sunar, anlık değil özetleyici.
    """
    log.info("=== Haftalık Özet Raporu başlatılıyor ===")
    today = _now()
    # "%-d %B" Windows'ta geçersiz ve Linux'ta İngilizce ay adı veriyordu → Türkçe ay adları.
    _AYLAR = ("Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık")
    week_str = f"{today.day} {_AYLAR[today.month - 1]} {today.year} haftası"

    # Veri kaynakları. Eskiden "haftayı X ile kapattı" cümlesinde GÜNLÜK değişim ve "haftalık" sektör başlığı
    # altında günlük değişimler yayınlanıyordu; artık haftalık değişim iki kapanış tarihiyle hesaplanır.
    bist_src = BistSource()
    bist = bist_src.market_summary()
    if not bist or not bist.price:
        log.error("BIST verisi temin edilemedi; yapay veri basılmaması için rapor iptal edildi.")
        return None
    week = bist_src.weekly_change()
    week_sentence = market_text.bist_week(bist.index, week)
    if week_sentence is None:
        log.error("Haftalık BIST değişimi hesaplanamadı; haftalık özet üretilmedi (günlük değişim haftalık sunulmaz).")
        return None
    macro = _drop_stale_macro(GlobalMacroSource().snapshot(), _now())
    sector_moves = SectorSource().snapshot(period="1w")
    disclosures = KapSource().latest_disclosures(days=7)

    # Sektör tablosu (haftalık değişime göre sıralı; yükselen/düşen listeleri işarete göre süzülür)
    sector_rows = "\n".join(
        f"| {m.name} | {m.change_str} |" for m in sector_moves
    )
    ups, downs = movers_lines(sector_moves, 3)
    sector_note = market_text.sector_heading_note(sector_moves) if sector_moves else ""

    # KAP öne çıkanlar (insider + önemli)
    insider_disclosures = [d for d in disclosures if d.is_insider]
    notable_disclosures = [d for d in disclosures if not d.is_insider][:5]

    kap_section = ""
    if insider_disclosures:
        kap_section += "### Pay Alım Satım ve Geri Alım Bildirimleri\n\n"
        for d in insider_disclosures[:3]:
            kap_section += f"- {d.title}\n"
        kap_section += "\n"
    if notable_disclosures:
        kap_section += "### Öne Çıkan Bildirimler\n\n"
        for d in notable_disclosures:
            kap_section += f"- **{d.title}** — {d.company} [{d.disclosure_type}]\n"
        kap_section += "\n"

    # AI ile özet üret
    analyzer = MarketAIAnalyzer()
    macro_ctx = macro.summary_line()
    ai_prompt_context = (
        f"{week_sentence}\n"
        f"Makro ({macro_ctx})\n"
        f"Sektör endeksleri, {sector_note}: yükselenler {ups}; düşenler {downs}\n"
        f"Son 7 günde pay alım satım/geri alım bildirimi sayısı: {len(insider_disclosures)}\n"
        f"Son 7 günde toplam KAP bildirimi: {len(disclosures)}"
    )
    prompt = f"""
Tarafsız, Türkçe bir "haftalık piyasa veri özeti" yaz. Hafta: {week_str}.
Markdown kullan. ASLA yer tutucu yazma. Her rakamı verilerde yazdığı anlamla ve tarihiyle aktar.
{NEUTRAL_RULES}
Veriler:
{ai_prompt_context}

Bülten şu bölümleri içersin:
1. Haftanın Özeti (BIST performansı rakamlarıyla)
2. Sektörler (yükselen/düşen sektörler, rakamlarıyla)
3. Küresel Makro (faiz, döviz, emtia değişimleri, rakamlarıyla)
4. KAP & Şirket Haberleri (öne çıkan bildirimlerde ne açıklandığı)
5. Gelecek Hafta Takvimi (yalnızca açıklanmış veri/etkinlik tarihleri)
"""
    body = analyzer.client.generate(prompt, disable_thinking=True)
    body = strip_banned(body) if body else body

    if not body:
        # Şablon fallback
        sector_md = (
            f"## Sektör Endeksleri\n\nSektör endeksleri — {sector_note}.\n\n"
            f"| Sektör | Haftalık değişim |\n| --- | --- |\n{sector_rows}\n\n"
            f"{market_text.sector_movers_md(sector_moves)}\n\n"
            if sector_moves else ""
        )
        body = (
            f"## Haftanın Özeti\n\n{week_sentence}\n\n"
            + sector_md
            + (f"## Küresel Makro\n\n{macro.to_markdown_table()}\n\n" if macro.tickers else "")
            + (f"## KAP & Şirket Haberleri (son 7 gün)\n\n{kap_section}" if kap_section else "")
        )

    summary = f"{week_sentence} Yükselen sektörler (haftalık): {ups}."

    card_path = _render_card(
        CardSpec(
            category="bist",
            kicker="Haftalık Özet",
            headline=safe_truncate(f"Yükselenler: {ups}. Düşenler: {downs}.", 120),
            stat_value=tr_number(week.last_close) if week else bist.price,
            stat_change=tr_pct(week.pct) if week else "",
            bars=[(m.name, m.change_pct) for m in sector_moves[:6]],
            template="bist",
        )
    )

    draft = ReportDraft(
        title=f"Haftalık Piyasa Özeti — {week_str}",
        category="bist",
        summary=summary,
        body=body,
        sources=["BIST", "KAP", "Yahoo Finance"],
        tags=["Haftalık Özet", "BIST", "Sektör", "Makro"],
        ai_generated=settings.ai_enabled,
        image_path=card_path,
    )

    if ContentStore().publish(draft) is None:
        log.error("Haftalık özet guardrail'a takıldı; iptal.")
        _cleanup(card_path)
        return None
    slug = draft.resolved_slug()

    if publish_social:
        SocialPublisher().broadcast(
            f"Haftalık piyasa özeti yayında. {week_sentence}\n"
            f"{settings.site_url}/rapor/{slug}\n"
            f"#BIST100 #HaftalıkÖzet #Borsa",
            image_path=card_path,
        )
    _cleanup(card_path)
    log.info("=== Haftalık Özet Raporu tamamlandı: %s ===", slug)
    return slug
