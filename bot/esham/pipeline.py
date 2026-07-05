"""Sabah raporu orkestrasyonu.

Akış: veri topla -> AI ile bülten üret -> web'e yayınla (içerik köprüsü) ->
sosyal medyada paylaş. Her adım kendi hatasını yönetir; bir kaynak bozulsa da
pipeline mümkün olduğunca ilerler.
"""
from __future__ import annotations

from .ai import MarketAIAnalyzer
from .config import get_logger, settings
from .publishing import ContentStore, ReportDraft
from .publishing.social import SocialPublisher
from .sources import MarketSnapshot
from .sources.bist import BistSource
from .sources.calendar import EconomicCalendarSource
from .sources.kap import KapSource
from .sources.sector import SectorSource
from .sources.viop import ViopSource, assess_margin_stress

import tempfile
import urllib.parse
from pathlib import Path
import requests

log = get_logger(__name__)

_CATEGORY_PROMPTS = {
    "insider": (
        "Abstract 3D render of elegant financial curves, dark navy blue background, "
        "minimalist design, gold accents, smooth light reflections, octane render, "
        "premium financial visualization, clean and high-end"
    ),
    "ipo": (
        "Abstract 3D render of ascending geometric bars and rings, dark blue and platinum theme, "
        "clean minimal design, volumetric lighting, premium corporate graphic"
    ),
    "bist": (
        "Minimalist abstract 3D render of smooth financial trend lines, dark midnight blue background, "
        "ice blue and white glowing curves, clean design, premium market visualization, 8k"
    ),
    "viop": (
        "Abstract 3D render of digital grid and trading waves, dark theme, sharp lines, "
        "glowing blue and red accents, minimalist composition, octane render"
    ),
    "global": (
        "Abstract 3D render of interconnected globe network lines, dark blue background, "
        "minimalist tech design, glowing nodes, elegant, high-end"
    ),
    "sector": (
        "Abstract 3D geometric composition of rotating rings and trend indicators, "
        "dark theme, gold and platinum accents, minimal design, premium finance look"
    ),
}

_DEFAULT_PROMPT = (
    "Abstract 3D render of elegant financial waves, dark midnight blue background, "
    "minimal design, glowing curves, octane render, clean, premium market visualization"
)


def fetch_report_image(
    title: str, slug: str, category: str = "bist"
) -> Path | None:
    """Haberin başlığına ve kategorisine uygun, bağlamsal görsel üretir."""
    try:
        seed = 0
        for char in slug:
            seed = ((seed << 5) - seed) + ord(char)
            seed &= 0xFFFFFFFF
            if seed >= 0x80000000:
                seed -= 0x100000000
        seed = abs(seed) % 10000

        # Kategori bazlı temel sahne + başlıktan bağlamsal detay
        base_scene = _CATEGORY_PROMPTS.get(category, _DEFAULT_PROMPT)
        prompt = urllib.parse.quote(
            f"{base_scene}. Context: {title}"
        )
        url = (
            f"https://image.pollinations.ai/prompt/{prompt}"
            f"?width=800&height=400&nologo=true&seed={seed}"
        )

        resp = requests.get(url, timeout=30)
        resp.raise_for_status()

        tmp = Path(tempfile.gettempdir()) / f"esham_{slug}.jpg"
        tmp.write_bytes(resp.content)
        return tmp
    except Exception as exc:
        log.warning("Kapak görseli indirilemedi: %s", exc)
        return None

def gather_snapshot() -> MarketSnapshot:
    log.info("Piyasa verileri toplanıyor...")
    return MarketSnapshot(
        bist=BistSource().market_summary(),
        disclosures=KapSource().latest_disclosures(),
        calendar=EconomicCalendarSource().daily_events(),
    )


def run_morning_report(publish_social: bool = True) -> str | None:
    """Sabah bültenini üretir, yayınlar ve rapor slug'ını döner."""
    log.info("=== Esham Sabah Raporu başlatılıyor ===")

    snapshot = gather_snapshot()

    analyzer = MarketAIAnalyzer()
    body = analyzer.generate_morning_report(snapshot)

    change = snapshot.bist.change if snapshot.bist else ""
    draft = ReportDraft(
        title="BIST & Küresel Piyasalar Sabah Raporu",
        category="bist",
        summary=(
            f"Endeks {change} ile güne başlarken küresel makro veriler ve KAP "
            "gündemi bültende."
        ),
        body=body,
        sources=["KAP", "BIST", "Ekonomik Takvim"],
        tags=["BIST100", "Sabah Raporu", "Makro"],
        ai_generated=settings.ai_enabled,
    )

    if ContentStore().publish(draft) is None:
        log.error("Sabah raporu guardrail'a takıldı; yayın ve paylaşım iptal.")
        return None
    slug = draft.resolved_slug()

    if publish_social:
        img_path = fetch_report_image(draft.title, slug, category="bist")
        SocialPublisher().broadcast(
            f"📊 Günün BIST & küresel piyasa sabah raporu yayında.\n"
            f"{settings.site_url}/rapor/{slug}\n#BIST100 #Borsa",
            image_path=img_path
        )
        if img_path and img_path.exists():
            img_path.unlink()

    log.info("=== Süreç tamamlandı: %s ===", slug)
    return slug


def run_viop_report(prior_pct: float | None = None, publish: bool = True) -> str | None:
    """VİOP piyasa + marketwide teminat stresi raporunu üretir ve yayınlar."""
    src = ViopSource()
    quote = src.market_quote()
    snap = src.margin_snapshot()
    stress = assess_margin_stress(snap.margin_call_to_required_pct, prior_pct)

    futures_line = (
        f"| Vadeli {quote.futures_symbol} | {quote.futures_price} | {quote.futures_change} |\n"
        if quote.futures_symbol
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

    draft = ReportDraft(
        title="VİOP Piyasa & Teminat Stresi Raporu",
        category="viop",
        summary=summary,
        body=body,
        sources=["TradingView", "Takasbank"],
        tags=["VİOP", "Teminat", "Margin Call"],
        ai_generated=False,
    )
    if ContentStore().publish(draft) is None:
        log.error("VİOP raporu guardrail'a takıldı; iptal.")
        return None
    return draft.resolved_slug()


def run_opening_report(publish_social: bool = False) -> str | None:
    """BIST açılış notu — kısa endeks görünümü."""
    bist = BistSource().market_summary()
    body = f"""## BIST Güne Başlıyor

{bist.index} endeksi **{bist.price}** seviyesinde ({bist.change}) açılışa hazırlanıyor.

Gün içi endeks yönü için küresel risk iştahı ve yabancı takas hareketleri izlenecek."""
    draft = ReportDraft(
        title=f"BIST Açılış: {bist.index} {bist.change}",
        category="bist",
        summary=f"{bist.index} {bist.price} ({bist.change}) ile güne başlıyor.",
        body=body,
        sources=["BIST", "Yahoo Finance"],
        tags=["BIST", "Açılış"],
        ai_generated=False,
    )
    if ContentStore().publish(draft) is None:
        log.error("Açılış raporu guardrail'a takıldı; iptal.")
        return None
    slug = draft.resolved_slug()
    if publish_social:
        img_path = fetch_report_image(draft.title, slug, category="bist")
        SocialPublisher().broadcast(
            f"🔔 BIST açılış: {bist.index} {bist.price} ({bist.change})\n"
            f"{settings.site_url}/rapor/{slug} #BIST100",
            image_path=img_path
        )
        if img_path and img_path.exists():
            img_path.unlink()
    return slug


def run_closing_report(publish_social: bool = True) -> str | None:
    """Kapanış bülteni — BIST + VİOP kapanış özeti."""
    bist = BistSource().market_summary()
    quote = ViopSource().market_quote()
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
    if ContentStore().publish(draft) is None:
        log.error("Kapanış raporu guardrail'a takıldı; iptal.")
        return None
    slug = draft.resolved_slug()
    if publish_social:
        img_path = fetch_report_image(draft.title, slug, category="bist")
        SocialPublisher().broadcast(
            f"🔚 Kapanış: BIST {bist.index} {bist.price} ({bist.change})\n"
            f"{settings.site_url}/rapor/{slug} #BIST100",
            image_path=img_path
        )
        if img_path and img_path.exists():
            img_path.unlink()
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
    if ContentStore().publish(draft) is None:
        log.error("Sektör raporu guardrail'a takıldı; iptal.")
        return None
    slug = draft.resolved_slug()
    if publish_social:
        img_path = fetch_report_image(draft.title, slug, category="sector")
        SocialPublisher().broadcast(
            f"📊 Haftalık sektör rotasyonu yayında. Güçlü: {leaders}.\n"
            f"{settings.site_url}/rapor/{slug} #BIST #Sektör",
            image_path=img_path
        )
        if img_path and img_path.exists():
            img_path.unlink()
    return slug
