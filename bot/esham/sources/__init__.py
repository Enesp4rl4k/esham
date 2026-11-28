"""Veri kaynakları.

Her kaynak dış dünyaya bağımlıdır (HTML/JSON scraping veya API). Kaynak kırıldığında
sessizce çökmemek için: her çağrı try/except ile sarılır, hata loglanır ve boş/örnek
veriyle zarifçe geri dönülür. Böylece bir kaynak bozulsa da pipeline devam eder.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
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
    """BIST endeks özeti. Alanların ANLAMI (şablon cümleleri buna göre yazılır):

    price        — son işlem fiyatı (seans açıksa gün içi son fiyat, kapalıysa son seansın kapanışı)
    change       — ``price``'ın ÖNCEKİ SEANS KAPANIŞINA göre yüzde değişimi (``+%2,18``)
    open_price   — ``as_of`` gününün seans açılış fiyatı
    open_change  — açılış fiyatının önceki seans kapanışına göre yüzde farkı
    as_of        — ``price``'ın ait olduğu son işlem zamanı (Türkiye saati); bilinmiyorsa None
    market_open  — veri çekildiği anda seans açık mı (True/False); bilinmiyorsa None
    volume       — kaynağın hacim alanı; birimi (TL mi lot mu) doğrulanamadığı için metinlerde KULLANILMAZ
    """

    index: str
    price: str
    change: str
    volume: str = ""
    open_price: str = ""
    open_change: str = ""
    high: str = ""
    low: str = ""
    price_value: float | None = None
    change_pct: float | None = None
    open_value: float | None = None
    open_change_pct: float | None = None
    as_of: "datetime | None" = None
    market_open: bool | None = None


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
        sector      — Sektör endekslerinin GÜNLÜK değişimi (önceki kapanışa göre; ``SectorMove.as_of``)
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
