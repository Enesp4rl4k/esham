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
from .config import get_logger, settings
from .publishing import ContentStore, ReportDraft
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
from .sources.sector import SectorSource
from .sources.turib import TuribSource
from .sources.viop import ViopSource, assess_margin_stress

log = get_logger(__name__)

_cards = CardGenerator()


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
    # Rapor + tweet thread tek AI çağrısında üretilir (rate limit önlemi)
    body, ai_used, thread_tweets = analyzer.generate_morning_report_and_thread(snapshot)

    bist = snapshot.bist
    change = bist.change if bist else ""
    price = bist.price if bist else ""
    index = bist.index if bist else "XU100"
    summary = (
        f"{index} endeksi {price} seviyesinde, {change} değişimle güne başladı. "
        "Küresel makro gelişmeler ve KAP gündemi sabah bülteninde."
    )
    # Kart görseli için kısa başlık — sparkline + büyük stat olduğunda sol kolona
    # fazla alan kalmaz, bu yüzden sadece kısa ve çarpıcı bir ifade kullan.
    card_headline = (
        f"Küresel makro ve KAP gündemli sabah bülteni"
        if not change else
        f"{change} değişimle {'yükseliş' if change.startswith('+') else 'düşüş'} — sabah bülteni"
    )

    card_path = _render_card(
        CardSpec(
            category="bist",
            kicker=f"{bist.index} Endeksi" if bist else "BIST",
            headline=card_headline,
            stat_value=bist.price if bist else "",
            stat_change=bist.change if bist else "",
            sparkline=BistSource().fetch_closes("1d", "15m") if bist else None,
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
            body_md=body,
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
        prior_pct = get_state().get_margin_prev_pct() or snap.margin_call_to_required_pct
    stress = assess_margin_stress(snap.margin_call_to_required_pct, prior_pct)
    from .state import get_state
    get_state().set_margin_prev_pct(snap.margin_call_to_required_pct)

    futures_line = (
        f"| Vadeli {quote.futures_symbol} | {quote.futures_price} | {quote.futures_change or '—'} |\n"
        if quote.has_futures
        else ""
    )
    body = f"""## VİOP Piyasa Görünümü

| Enstrüman | Değer | Değişim |
| --- | --- | --- |
| Endeks {quote.index_symbol} | {quote.index_price} | {quote.index_change} |
{futures_line}

## Marketwide Teminat (Takasbank)

| Gösterge | Değer |
| --- | --- |
| Teminatlı hesap | {snap.margined_account_count:,} |
| Margin-call toplam | {snap.margin_call_pretty()} |
| Gereken teminat | {snap.required_pretty()} |
| Margin-call / Gereken | %{snap.margin_call_to_required_pct:.3f} |

## Teminat Stresi: {stress.level}

{stress.note}

> **Margin-call/gereken teminat** oranı marketwide stres sinyalidir. Yükselmesi,
> takas kurumunun teminatı sıkılaştırdığını ve brokerların margin-call çıkaracağını
> gösterir."""

    summary = (
        f"VİOP teminat stresi: {stress.level}. Margin-call toplam "
        f"{snap.margin_call_pretty()}."
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
            f"VİOP piyasa görünümü: {quote.index_symbol} {quote.index_price} "
            f"({quote.index_change}). Teminat stresi: {stress.level}.\n"
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
    return (
        f"\n\n**VİOP Görünümü:** Vadeli endeks kontratı ({quote.futures_symbol}) "
        f"seansa {quote.futures_change} değişimle başladı."
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

    # Sektör rotasyonu ve VİOP kotasyonu
    sector_summary = ""
    try:
        from .sources.sector import SectorSource
        moves = SectorSource().snapshot()
        top_gainers = [m for m in moves if m.change_pct > 0][:3]
        top_losers = [m for m in moves if m.change_pct < 0][:3]
        sec_lines = []
        if top_gainers:
            sec_lines.append("**Pozitif Ayrışan Sektörler:** " + ", ".join(f"{m.name} (%{m.change_pct:+.2f})" for m in top_gainers))
        if top_losers:
            sec_lines.append("**Baskı Altındaki Sektörler:** " + ", ".join(f"{m.name} (%{m.change_pct:+.2f})" for m in top_losers))
        if sec_lines:
            sector_summary = "\n\n" + "\n\n".join(sec_lines)
    except Exception as exc:
        log.debug("Açılış sektörel görünüm alınamadı: %s", exc)

    viop_line = _opening_viop_line()

    open_val = bist.open_price or bist.price
    open_chg = bist.open_change or bist.change

    current_note = ""
    if bist.open_price and bist.price and bist.open_price != bist.price:
        current_note = f" (Seans içi güncel seviye: **{bist.price}** / **{bist.change}**)"

    body = f"""## BIST Seans Açılışı

Borsa İstanbul {bist.index} endeksi seansa **{open_val}** puan seviyesinde, **{open_chg}** açılış değişimi ile başladı.{current_note}{viop_line}{sector_summary}

### Seans İçi Takip Edilecekler
- **Likidite ve Para Girişi:** Bankacılık ve Sınai sektörlerindeki kurumsal hacimler.
- **Teknik Seviyeler:** Endeksin destek ve direnç bölgelerindeki tutunma gücü.
- **Küresel Piyasalar:** ABD vadeli endeksleri ve Avrupa açılışlarındaki risk algısı."""

    draft = ReportDraft(
        title=f"BIST Seans Açılışı: {bist.index} {open_chg}",
        category="bist",
        summary=f"{bist.index} endeksi {open_val} ({open_chg}) ile yeni seansa başladı.{current_note}",
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
            f"BIST açılış: {bist.index} {open_val} ({open_chg})\n"
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
    quote = ViopSource().market_quote()
    if quote is None:
        log.error("VİOP kotasyonu temin edilemedi; örnek veri basılmaması için kapanış raporu iptal edildi.")
        return None
    body = f"""## Kapanış Görünümü

| Piyasa | Değer | Değişim |
| --- | --- | --- |
| BIST {bist.index} | {bist.price} | {bist.change} |
| VİOP {quote.index_symbol} | {quote.index_price} | {quote.index_change} |

Hacim: {bist.volume or '—'}. Gün içi öne çıkan hisse ve sektör hareketleri
yarınki açılış beklentilerini şekillendirecek."""
    draft = ReportDraft(
        title=f"Kapanış Bülteni: BIST {bist.change}",
        category="bist",
        summary=f"BIST {bist.index} günü {bist.change} ile {bist.price} seviyesinde kapattı.",
        body=body,
        sources=["BIST", "TradingView"],
        tags=["BIST", "Kapanış"],
        ai_generated=False,
    )

    card_path = _render_card(
        CardSpec(
            category="bist",
            kicker=f"{bist.index} Kapanış",
            headline=f"VİOP {quote.index_symbol} {quote.index_price} ({quote.index_change}) ile eşlik etti.",
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
            f"Kapanış: BIST {bist.index} {bist.price} ({bist.change})\n"
            f"Hacim: {bist.volume} | VİOP {quote.index_symbol}: {quote.index_price} ({quote.index_change})\n"
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
    """Haftalık sektör rotasyonu raporu."""
    moves = SectorSource().snapshot()
    rows = "\n".join(f"| {m.name} | {m.change_str} |" for m in moves)
    leaders = ", ".join(m.name for m in moves[:3])
    laggards = ", ".join(m.name for m in moves[-3:])
    body = f"""## Sektör Rotasyonu

| Sektör | Değişim |
| --- | --- |
{rows}

## Öne Çıkanlar

- **Güçlü:** {leaders}
- **Zayıf:** {laggards}

Sektör rotasyonu, paranın hangi temalara aktığını gösterir; güçlü sektörlerdeki
liderler orta vadeli momentum açısından izlenmeye değer."""
    draft = ReportDraft(
        title="Haftalık Sektör Rotasyonu",
        category="bist",
        summary=f"Bu hafta öne çıkan sektörler: {leaders}.",
        body=body,
        sources=["TradingView"],
        tags=["Sektör", "Rotasyon", "BIST"],
        ai_generated=False,
    )

    card_path = _render_card(
        CardSpec(
            category="bist",
            kicker="Haftalık Sektör Rotasyonu",
            headline=f"Güçlü: {leaders}. Zayıf: {laggards}.",
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
            f"Haftalık sektör rotasyonu yayında. Güçlü: {leaders}.\n"
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

    # F/K medyanına göre en ucuz / en pahalı iki hisse (varsa)
    ranked = sorted(
        (p for p in snap.peers if p.pe is not None), key=lambda p: p.pe
    )
    cheapest = ranked[0] if ranked else None
    priciest = ranked[-1] if ranked and len(ranked) > 1 else None

    cheap_line = (
        f"- **En düşük F/K:** {cheapest.ticker} ({cheapest.name}) — "
        f"{_fmt_mult(cheapest.pe)} · {snap.stance('pe', cheapest.pe)}"
        if cheapest else "- F/K verisi alınamadı; kıyas fiyat performansına dayanıyor."
    )
    pricy_line = (
        f"- **En yüksek F/K:** {priciest.ticker} ({priciest.name}) — "
        f"{_fmt_mult(priciest.pe)} · {snap.stance('pe', priciest.pe)}"
        if priciest else ""
    )
    notes = "\n".join(f"- {n}" for n in snap.notes)
    caveat = (
        "\n> **Not:** Veriler örnek amaçlıdır; gerçek kaynaklara erişilemedi."
        if snap.sample
        else ""
    )

    body = f"""## {snap.sector_name} — Eş Kıyası

| Hisse | Fiyat | Günlük | F/K | PD/DD | FD/FAVÖK | Temettü % | FÖK % |
| --- | --- | --- | --- | --- | --- | --- | --- |
{rows}
{median_line}

## Medyana Göre Konumlanma

{cheap_line}
{pricy_line}

## Değerlendirme

- Sektör medyanı, bu örneklemden hesaplanır ve gün içi fiyatlarla değişir.
- F/K medyanına **yakın** hisseler iskonto primi olmadan işlem görür; medyanın
  belirgin **altında** kalanlar için temel/neden, **üstünde** kalanlar için prim
  gerekçesi aranır (bilanço kalitesi, büyüme, temettü politikası).
{notes}{caveat}

*Çarpanlar Yahoo Finance özet verisinden alınır; yatırıma yönlendirici değildir.*"""

    cheapest_p = cheapest.ticker if cheapest else "—"
    summary = (
        f"{snap.sector_name} eş kıyası: medyan F/K {_fmt_mult(snap.median_pe)}, "
        f"medyan PD/DD {_fmt_mult(snap.median_pb)}. En ucuz: {cheapest_p}."
    )

    card_path = _render_card(
        CardSpec(
            category="bist",
            kicker=f"{snap.sector_name} — Eş Kıyası",
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
        title=f"{snap.sector_name} Sektöründe Eş Kıyası (Peer)",
        category="bist",
        summary=summary[:200],
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
            f"{snap.sector_name} eş kıyası yayında: medyan F/K "
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
        return f"%{value:.1f}"
    return f"{value:.2f}".replace(".", ",")


def run_global_report(publish_social: bool = True) -> str | None:
    """Küresel makro görünümü raporu.

    ABD 10Y, EUR/USD, Altın, VIX, Brent verilerini GlobalMacroSource'dan çeker.
    Kart: sol başlık + sağ ticker board (_render_global şablonu).
    Rapor: markdown tablosu.
    """
    log.info("=== Küresel Makro Raporu başlatılıyor ===")
    snap = GlobalMacroSource().snapshot()
    if not snap.tickers:
        log.error("Küresel makro verisi temin edilemedi; örnek veri yayınlanamaz.")
        return None
    board = snap.ticker_board()

    # Başlık: en güçlü değişim sinyali
    headline_tickers = [t for t in snap.tickers if abs(t.change_pct) > 0.3]
    if headline_tickers:
        top = max(headline_tickers, key=lambda t: abs(t.change_pct))
        headline = (
            f"{top.label} {top.arrow} {top.change_str} öne çıktı; "
            f"küresel risk iştahı {('artıyor' if top.change_pct > 0 else 'azalıyor')}."
        )
    else:
        headline = "Küresel piyasalarda sınırlı hareketlilik; risk iştahı nötr."

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
        final_tweet = ai_tweet if ai_tweet else f"Küresel makro: {summary}\n"
        final_tweet += f"\n{settings.site_url}/rapor/{slug}\n#Makro #Borsa #KüreselPiyasalar"
        SocialPublisher().broadcast(
            final_tweet,
            image_path=card_path,
        )
    _cleanup(card_path)
    log.info("=== Küresel Makro Raporu tamamlandı: %s ===", slug)
    return slug


def run_news_report(
    event: MarketEvent | None = None,
    disclosure: Disclosure | None = None,
    publish_social: bool = True,
) -> str | None:
    """KAP bildirimi veya makro/sektör olayı için AI destekli kısa haber raporu.

    İki kullanım modu:
    - `disclosure` verilirse: KAP bildirimi analizi (şirket haberi)
    - `event` verilirse: makro/sektör fiyat hareketi analizi

    Her iki durumda da:
    1. AI ile kısa analiz + tweet metni üretilir
    2. Web'e rapor yayınlanır (ContentStore)
    3. Sosyal medyada paylaşılır (kart görseli ile)
    """
    if event is None and disclosure is None:
        log.error("run_news_report: event veya disclosure gerekli.")
        return None

    analyzer = MarketAIAnalyzer()

    # Bağlam için anlık makro ve sektör verisi (hafif — sadece gerekirse)
    macro_context = ""
    sector_context = ""
    try:
        snap = GlobalMacroSource().snapshot()
        macro_context = snap.summary_line()
    except Exception as exc:
        log.debug("Makro bağlam alınamadı: %s", exc)

    # ---- KAP bildirimi modu -------------------------------------------------------
    if disclosure is not None:
        title = disclosure.title
        company = disclosure.company
        ticker = disclosure.ticker or disclosure.company
        disc_type = disclosure.disclosure_type
        raw = disclosure.raw_text or title
        
        # Sadece başlık yerine bildirimin tam metnini (detayını) çek ki AI analiz edebilsin.
        if disclosure.disclosure_index:
            detail = KapSource().get_detail_text(disclosure.disclosure_index)
            if detail:
                # Başlık/özet ve detayı birleştir
                raw = f"{raw}\n\nDetay:\n{detail}"
        is_insider = disclosure.is_insider

        # Tier-1 / Mega İş Anlaşması tespiti
        from .turkish import tr_fold
        norm_disc = tr_fold(f"{title} {raw}")
        is_order = any(k in norm_disc for k in ("yeni is iliskisi", "siparis", "sozlesme", "ihale", "proje"))
        has_mega_amount = any(k in norm_disc for k in ("milyar", "500 milyon", "600 milyon", "700 milyon", "800 milyon", "900 milyon"))
        is_mega_deal = is_order and has_mega_amount

        body, summary, tweet_text = analyzer.generate_news_analysis(
            title=title,
            disclosure_type=disc_type,
            company=company,
            ticker=ticker,
            raw_text=raw,
            is_insider=is_insider,
            macro_context=macro_context,
        )
        category = "bist"
        emoji = "🔥" if is_mega_deal else ("🚨" if is_insider else "📰")
        
        if is_mega_deal:
            kicker = "Mega İş Anlaşması"
            card_kicker = "MEGA İŞ ANLAŞMASI"
        elif is_insider:
            kicker = "İçsel İşlem"
            card_kicker = "İÇSEL İŞLEM"
        else:
            kicker = disc_type or "KAP Bildirimi"
            card_kicker = kicker

        tags = [ticker, "KAP", "BIST"]
        if is_mega_deal:
            tags.insert(0, "Mega Sözleşme")
        if is_insider:
            tags.insert(0, "İçsel İşlem")

        card_headline = title[:120]
        card_ticker_val = ticker

        # Teknik analiz snapshot'ı (Fiyat, RSI, 20G HO, Destek/Direnç)
        from .sources.bist import BistSource
        tech_snapshot = BistSource.fetch_technical_snapshot(ticker)

        # BIST Quant & Temel Analiz & Key Levels motoru
        try:
            from .sources.bist_quant import BistQuantAnalyzer, extract_contract_amount
            quant = BistQuantAnalyzer()
            contract_val = extract_contract_amount(f"{title} {raw}")
            fund_data = quant.get_fundamental_metrics(ticker, contract_amount_try=contract_val)
            if fund_data:
                body = f"{body}\n\n{fund_data.format_table()}"
                if fund_data.contract_analysis and fund_data.contract_analysis.get("is_mega"):
                    is_mega_deal = True

            key_data = quant.get_key_levels(ticker)
            if key_data:
                body = f"{body}\n\n{key_data.format_table()}"
            elif tech_snapshot:
                body = f"{body}\n\n{tech_snapshot.format_table()}"
        except Exception as exc:
            log.warning("Kantitatif analiz eklenemedi (%s): %s", ticker, exc)
            if tech_snapshot:
                body = f"{body}\n\n{tech_snapshot.format_table()}"

        if is_mega_deal and not summary.startswith("MEGA SÖZLEŞME"):
            summary = f"MEGA SÖZLEŞME | {summary}"

    # ---- Makro/sektör olay modu --------------------------------------------------
    else:
        assert event is not None  # mypy
        from .translation import ensure_turkish, is_mostly_english
        title_line = event.headline.split('\n')[0]
        if is_mostly_english(title_line):
            title_line = ensure_turkish(title_line)
            if not title_line:
                log.error("Haber başlığı İngilizce ve Türkçeleştirilemedi; iptal: %s", event.headline[:60])
                return None
        title = title_line
        summary = title_line
        category = event.category
        emoji = event.emoji
        _KICKER_MAP = {
            "SON_DAKIKA": "Küresel Piyasalar",
            "HISSE_HAREKET": "Hisse Alarmı",
            "BIST_HAREKET": "BIST Endeksi",
            "SEKTÖR_HAREKET": "Sektör Hareketi",
            "MAKRO_HAREKET": "Makro Piyasalar",
            "KRIPTO_HAREKET": "Kripto Piyasası",
            "TEKNOLOJI_HAREKET": "Teknoloji & AI",
        }
        kicker = _KICKER_MAP.get(event.kind, event.kind.replace("_", " ").title())
        tags = event.tags or ["Makro", "Piyasa"]
        card_kicker = "SON DAKİKA" if event.kind == "SON_DAKIKA" else event.label
        card_headline = title_line[:120] if event.kind == "SON_DAKIKA" else event.headline[:120]
        card_ticker_val = "" if event.kind == "SON_DAKIKA" else event.label

        if event.kind in ("SON_DAKIKA", "HISSE_HAREKET", "TEKNOLOJI_HAREKET", "KRIPTO_HAREKET", "MAKRO_HAREKET"):
            ai_body, ai_summary, tweet_text = analyzer.generate_event_analysis(
                event=event,
                macro_context=macro_context,
            )
            if ai_summary and ai_summary.strip().lower() != title.strip().lower():
                summary = ai_summary.strip()

            src_label = getattr(event, "source_name", "")
            if not src_label:
                if event.kind == "TEKNOLOJI_HAREKET":
                    src_label = "TechCrunch / The Verge / Ars Technica"
                elif event.kind == "KRIPTO_HAREKET":
                    src_label = "CoinDesk / CoinTelegraph / Yahoo Finance"
                elif event.kind == "HISSE_HAREKET":
                    src_label = "Yahoo Finance / BIST"
                else:
                    src_label = "Küresel Haber Ajansları"

            src_url = getattr(event, "source_url", "")
            if src_url:
                source_block = f"\n\n> **Kaynak:** [{src_label}]({src_url})"
            else:
                source_block = f"\n\n> **Kaynak:** {src_label}"

            body = f"{ai_body}{source_block}"
        elif event.kind == "SEKTÖR_HAREKET":
            body, summary, tweet_text = analyzer.generate_sector_movement_analysis(
                sector_name=event.label,
                change_pct=event.change_pct,
                headline=event.headline,
                macro_context=macro_context,
            )
        else:
            body, summary, tweet_text = analyzer.generate_news_analysis(
                title=event.headline,
                disclosure_type=event.kind,
                company=event.label,
                ticker=event.label,
                raw_text=event.headline,
                macro_context=macro_context,
                sector_context=sector_context,
            )

    # ---- kart ve rapor -----------------------------------------------------------
    sparkline = None
    card_metrics = []
    card_stat_value = ""
    card_stat_change = ""

    if disclosure is not None and tech_snapshot:
        sparkline = tech_snapshot.closes
        card_stat_value = f"{tech_snapshot.last_price:.2f} TL"
        sign = "+" if tech_snapshot.change_pct >= 0 else ""
        card_stat_change = f"{sign}{tech_snapshot.change_pct:.2f}%"
        card_metrics = [
            ("RSI", f"{tech_snapshot.rsi_14:.0f}"),
            ("20G HO", f"{tech_snapshot.sma_20:.1f}"),
            ("Destek", f"{tech_snapshot.support:.1f}"),
        ]

    if event is not None:
        if event.kind == "MAKRO_HAREKET":
            from .sources.global_macro import GlobalMacroSource, MACRO_TICKERS
            symbol = next((s for s, l, _, _ in MACRO_TICKERS if l == event.label), None)
            if symbol:
                sparkline = GlobalMacroSource().fetch_closes(symbol)
        elif event.kind == "KRIPTO_HAREKET":
            from .sources.crypto import CryptoSource, CRYPTO_TICKERS
            symbol = next((s for s, l in CRYPTO_TICKERS if l.lower() in event.label.lower() or l.lower() in event.headline.lower()), "BTC-USD")
            sparkline = CryptoSource().fetch_closes(symbol)
        elif event.kind in ("BIST_HAREKET", "SEKTÖR_HAREKET"):
            from .sources.bist import BistSource
            symbol = "XU100.IS" if event.kind == "BIST_HAREKET" else f"{event.label}.IS"
            sparkline = BistSource(symbol).fetch_closes()
        elif event.kind == "HISSE_HAREKET":
            from .sources.bist import BistSource
            from .sources.watchlist import WATCHLIST
            yf_symbol = next((s for s, t in WATCHLIST if t == event.label), f"{event.label}.IS")
            sparkline = BistSource(yf_symbol).fetch_closes()

    # Genel haber/gündem/kripto/teknoloji kartları için Pexels fotoğrafı çek.
    # KAP bildirimleri için fotoğraf kullanılmaz (veri kartı kalır).
    # BIST/VİOP fiyat hareketleri için de fotoğraf gerekmez (sparkline var).
    _USE_PHOTO_CATEGORIES = {"gundem", "global", "kripto", "teknoloji"}
    photo_path = None
    if category in _USE_PHOTO_CATEGORIES and not sparkline:
        try:
            photo_path = _PhotoSource().fetch_photo(title, category)
        except Exception as exc:
            log.debug("Fotoğraf çekilemedi (%s); görselsiz devam.", exc)

    card_path = _render_card(
        CardSpec(
            category=category,
            kicker=card_kicker,
            headline=card_headline,
            stat_value=card_stat_value,
            stat_change=card_stat_change,
            metrics=card_metrics,
            ticker=card_ticker_val,
            template="bist" if (disclosure and tech_snapshot) else category,
            sparkline=sparkline,
            photo_path=photo_path,
        )
    )

    draft = ReportDraft(
        title=title,
        category=category,
        summary=summary,
        body=body,
        sources=(
            (["KAP", ticker] if ticker else ["KAP"])
            if disclosure
            else ([event.source_name] if getattr(event, "source_name", "") else (
                ["TechCrunch"] if event.kind == "TEKNOLOJI_HAREKET"
                else ["CoinDesk"] if event.kind == "KRIPTO_HAREKET"
                else ["Yahoo Finance"]
            ))
        ),
        tags=tags,
        ai_generated=settings.ai_enabled,
        image_path=card_path,
    )

    if ContentStore().publish(draft) is None:
        log.error("Haber raporu guardrail'a takıldı; iptal: %s", title[:80])
        _cleanup(card_path)
        return None
    slug = draft.resolved_slug()

    if publish_social:
        link = f"{settings.site_url}/rapor/{slug}"
        hashtags = " ".join(f"#{t.replace(' ', '')}" for t in tags[:3])

        # Tweet kalite kontrolü: sadece gerçekten boş veya çok kısa olanları yakala.
        # Önceki "emoji + başlık" kontrolü AI'nın ürettiği iyi tweetleri de yanlışlıkla
        # "zayıf" sayıp TweetComposer'a gönderiyordu — bu kaldırıldı.
        def _is_weak_tweet(t: str) -> bool:
            return not t or len(t.strip()) < 30

        if _is_weak_tweet(tweet_text):
            # AI tweet üretemedi — summary'den direkt oluştur, yorum cümlesi ekle.
            base = summary or title
            tweet_text = base if len(base) <= 240 else base[:240].rsplit(" ", 1)[0].rstrip(" ,.;:") + "…"
            log.info("Boş/kısa tweet; summary'den oluşturuldu.")

        # Link suffix için yer ayır: ~45 karakter link + ~30 karakter hashtag
        link_suffix = f"\n\n{link}\n{hashtags}"
        max_body = 280 - len(link_suffix)
        tweet_body = tweet_text.strip()
        if len(tweet_body) > max_body:
            tweet_body = tweet_body[:max_body].rsplit(" ", 1)[0].rstrip(" ,.;:") + "…"

        SocialPublisher().broadcast(
            f"{tweet_body}{link_suffix}",
            image_path=card_path,
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
    from datetime import datetime, timedelta, timezone

    log.info("=== Haftalık Özet Raporu başlatılıyor ===")
    TR_TZ = timezone(timedelta(hours=3))
    today = datetime.now(TR_TZ)
    week_str = today.strftime("%-d %B %Y haftası")

    # Anlık veri kaynakları
    bist = BistSource().market_summary()
    if not bist or not bist.price:
        log.error("BIST verisi temin edilemedi; yapay veri basılmaması için rapor iptal edildi.")
        return None
    macro = GlobalMacroSource().snapshot()
    sector_moves = SectorSource().snapshot()
    disclosures = KapSource().latest_disclosures()

    # Sektör tablosu
    sector_rows = "\n".join(
        f"| {m.name} | {m.change_str} |" for m in sector_moves[:8]
    )
    leaders = ", ".join(m.name for m in sector_moves[:3])
    laggards = ", ".join(m.name for m in sector_moves[-3:])

    # KAP öne çıkanlar (insider + önemli)
    insider_disclosures = [d for d in disclosures if d.is_insider]
    notable_disclosures = [d for d in disclosures if not d.is_insider][:5]

    kap_section = ""
    if insider_disclosures:
        kap_section += "### İçsel İşlemler\n\n"
        for d in insider_disclosures[:3]:
            kap_section += f"- **{d.company}** ({d.ticker}): {d.title}\n"
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
        f"BIST {bist.index}: {bist.price} ({bist.change}), hacim: {bist.volume}\n"
        f"Makro: {macro_ctx}\n"
        f"Güçlü sektörler: {leaders}\n"
        f"Zayıf sektörler: {laggards}\n"
        f"İçsel bildirim sayısı: {len(insider_disclosures)}\n"
        f"Toplam KAP bildirimi: {len(disclosures)}"
    )
    prompt = f"""
Aracı kurum kalitesinde, Türkçe bir "haftalık piyasa özeti" yaz. Hafta: {week_str}.
Markdown kullan. Yatırım tavsiyesi verme. ASLA yer tutucu yazma.

Veriler:
{ai_prompt_context}

Bülten şu bölümleri içersin:
1. Haftanın Özeti (BIST performansı, genel atmosfer)
2. Sektör Rotasyonu (güçlü/zayıf sektörler, para akışı yorumu)
3. Küresel Makro (faiz, döviz, emtia hareketlerinin BIST'e etkisi)
4. KAP & Şirket Haberleri (öne çıkan bildirimler, içsel işlemler)
5. Gelecek Haftaya Bakış (izlenecek başlıklar ve riskler)
"""
    body = analyzer.client.generate(prompt, disable_thinking=True)

    if not body:
        # Şablon fallback
        body = (
            f"## Haftanın Özeti\n\n"
            f"BIST {bist.index} haftayı **{bist.price}** ({bist.change}) seviyesinde kapattı.\n\n"
            f"## Sektör Rotasyonu\n\n"
            f"| Sektör | Değişim |\n| --- | --- |\n{sector_rows}\n\n"
            f"- **Güçlü:** {leaders}\n- **Zayıf:** {laggards}\n\n"
            f"## Küresel Makro\n\n{macro.to_markdown_table()}\n\n"
            + (f"## KAP & Şirket Haberleri\n\n{kap_section}" if kap_section else "")
            + "## Gelecek Haftaya Bakış\n\nPiyasa koşulları ve veri akışı takip edilmeye devam edilecek."
        )

    summary = f"BIST {bist.index} haftayı {bist.change} ile kapattı. Güçlü sektörler: {leaders}."

    card_path = _render_card(
        CardSpec(
            category="bist",
            kicker="Haftalık Özet",
            headline=f"Haftanın kazananları: {leaders}. Zayıflar: {laggards}.",
            stat_value=bist.price,
            stat_change=bist.change,
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
            f"Haftalık piyasa özeti yayında. "
            f"BIST {bist.change} | Güçlü: {leaders}\n"
            f"{settings.site_url}/rapor/{slug}\n"
            f"#BIST100 #HaftalıkÖzet #Borsa",
            image_path=card_path,
        )
    _cleanup(card_path)
    log.info("=== Haftalık Özet Raporu tamamlandı: %s ===", slug)
    return slug
