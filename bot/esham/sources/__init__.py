"""Veri kaynakları.

Her kaynak dış dünyaya bağımlıdır (HTML/JSON scraping veya API). Kaynak kırıldığında
sessizce çökmemek için: her çağrı try/except ile sarılır, hata loglanır ve boş/örnek
veriyle zarifçe geri dönülür. Böylece bir kaynak bozulsa da pipeline devam eder.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Disclosure:
    title: str
    company: str
    date: str
    disclosure_type: str
    pdf_link: str = ""
    is_insider: bool = False
    raw_text: str = ""


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
    """Sabah raporunun beslendiği toplu veri paketi."""

    bist: MarketSummary | None = None
    disclosures: list[Disclosure] = field(default_factory=list)
    calendar: list[CalendarEvent] = field(default_factory=list)
