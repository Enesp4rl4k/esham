"""Veri kaynakları.

Her kaynak dış dünyaya bağımlıdır (HTML/JSON scraping veya API). Kaynak kırıldığında
sessizce çökmemek için: her çağrı try/except ile sarılır, hata loglanır ve boş/örnek
veriyle zarifçe geri dönülür. Böylece bir kaynak bozulsa da pipeline devam eder.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .global_macro import GlobalMacroSnapshot
    from .sector import SectorMove
    from .viop import ViopQuote, ViopMarginSnapshot
    from .turib import TuribSnapshot


@dataclass
class Disclosure:
    title: str
    company: str  # tam şirket adı (KAP kapTitle)
    date: str
    disclosure_type: str
    pdf_link: str = ""
    is_insider: bool = False
    raw_text: str = ""
    ticker: str = ""  # borsa kodu (KAP stockCodes'un ilki), company'den ayrı
    disclosure_index: str = ""  # KAP disclosureIndex — gerçek ek dosyayı çözmek için


@dataclass
class MarketSummary:
    index: str
    price: str
    change: str
    volume: str = ""


@dataclass
class CalendarEvent:
    time: str
    country: str
    event: str
    importance: str
    forecast: str = ""


@dataclass
class MarketSnapshot:
    """Sabah raporunun beslendiği toplu veri paketi.

    Alanlar:
        bist        — BIST endeks özeti (fiyat, değişim, hacim)
        disclosures — KAP bildirimleri (son N adet)
        calendar    — Ekonomik takvim olayları (bugün)
        macro       — Küresel makro: ABD 10Y, EUR/USD, Altın, VIX, Brent
        viop_quote  — VİOP endeks/vadeli fiyat ve değişimi
        viop_margin — Takasbank marketwide teminat snapshot'ı
        sector      — Sektör rotasyonu hareketleri (haftalık)
        turib       — TÜRİB ELÜS tarımsal emtia ve hububat endeks özeti
    """

    bist: MarketSummary | None = None
    disclosures: list[Disclosure] = field(default_factory=list)
    calendar: list[CalendarEvent] = field(default_factory=list)
    macro: "GlobalMacroSnapshot | None" = None
    viop_quote: "ViopQuote | None" = None
    viop_margin: "ViopMarginSnapshot | None" = None
    sector: "list[SectorMove]" = field(default_factory=list)
    turib: "TuribSnapshot | None" = None
