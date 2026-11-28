"""BIST sektör endeksleri kaynağı.

Yahoo Finance chart API'sinden sektör endekslerinin GÜNLÜK barlarını çeker (TradingView turkey scanner
sektör endekslerini vermediği için Yahoo kullanılır) ve değişimi açıkça tanımlı iki kapanış arasında
hesaplar:

- ``period="1d"``: son kapanış (seans açıksa son fiyat) / önceki işlem günü kapanışı,
- ``period="1w"``: son kapanış / son barın haftasından önceki son işlem günü kapanışı.

Her ``SectorMove`` veri tarihini (``as_of``) ve dönemini taşır; şablonlar "günlük"/"haftalık" ifadesini
buradan alır. Hata durumunda boş liste döner (örnek veri üretilmez).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import requests

from ..config import default_headers, get_logger, settings
from ..formatting import tr_pct
from ..http import retry_get
from .bars import daily_bars, period_change

log = get_logger(__name__)

CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}.IS"

# BIST sektör endeksleri: kod -> Türkçe ad
SECTORS: dict[str, str] = {
    "XBANK": "Bankacılık",
    "XUTEK": "Teknoloji",
    "XUSIN": "Sınai",
    "XHOLD": "Holding",
    "XGIDA": "Gıda & İçecek",
    "XKMYA": "Kimya & Petrol",
    "XUMAL": "Mali",
    "XILTM": "İletişim",
    "XELKT": "Elektrik",
    "XINSA": "İnşaat",
    "XULAS": "Ulaştırma",
    "XTRZM": "Turizm",
    "XGMYO": "GYO",
    "XSGRT": "Sigorta",
}

PERIOD_LABEL = {"1d": "günlük", "1w": "haftalık"}


@dataclass
class SectorMove:
    code: str
    name: str
    change_pct: float
    as_of: date | None = None  # son barın tarihi
    period: str = "1d"  # "1d" | "1w"

    @property
    def change_str(self) -> str:
        return tr_pct(self.change_pct)


def split_movers(moves: list[SectorMove], n: int = 3) -> tuple[list[SectorMove], list[SectorMove]]:
    """(yükselenler, düşenler): yükselenler YALNIZ pozitif değişimliler (büyükten küçüğe), düşenler YALNIZ
    negatifler (en düşükten). N'den az nitelikli varsa daha az döner; sıfır değişim iki listeye de girmez."""
    ups = sorted((m for m in moves if round(m.change_pct, 2) > 0), key=lambda m: m.change_pct, reverse=True)
    downs = sorted((m for m in moves if round(m.change_pct, 2) < 0), key=lambda m: m.change_pct)
    return ups[:n], downs[:n]


def movers_lines(moves: list[SectorMove], n: int = 3, *, with_values: bool = True) -> tuple[str, str]:
    """Tarafsız iki satır metni: ("Teknoloji (+%4,66), …" | "yükselen sektör yok", "…" | "düşen sektör yok")."""
    ups, downs = split_movers(moves, n)

    def fmt(items: list[SectorMove]) -> str:
        return ", ".join(f"{m.name} ({m.change_str})" if with_values else m.name for m in items)

    return (fmt(ups) or "yükselen sektör yok", fmt(downs) or "düşen sektör yok")


def as_of_of(moves: list[SectorMove]) -> date | None:
    """Listedeki EN ESKİ veri tarihi (karışık tazelikte taze görünmesin); tarihsizse None."""
    dates = [m.as_of for m in moves if m.as_of]
    return min(dates) if dates else None


class SectorSource:
    def __init__(self) -> None:
        self.headers = default_headers()

    def snapshot(self, period: str = "1d") -> list[SectorMove]:
        moves: list[SectorMove] = []
        for code, name in SECTORS.items():
            got = self._fetch_change(code, period)
            if got is not None:
                pct, as_of = got
                moves.append(SectorMove(code, name, pct, as_of=as_of, period=period))
        if not moves:
            log.warning("Sektör verisi alınamadı; boş liste (örnek veri üretilmiyor).")
            return self._sample()
        moves.sort(key=lambda m: m.change_pct, reverse=True)
        log.info("Sektör verisi alındı: %d sektör (%s).", len(moves), period)
        return moves

    def _fetch_change(self, code: str, period: str = "1d") -> tuple[float, date] | None:
        try:
            resp = retry_get(
                f"{CHART_URL.format(symbol=code)}?range=1mo&interval=1d",
                headers=self.headers,
                timeout=settings.http_timeout,
            )
            resp.raise_for_status()
            result = resp.json()["chart"]["result"][0]
        except (requests.RequestException, ValueError, KeyError, IndexError, TypeError) as exc:
            log.debug("Sektör %s alınamadı: %s", code, exc)
            return None
        change = period_change(daily_bars(result), period)
        if change is None:
            return None
        return change.pct, change.last_date

    def _sample(self) -> list[SectorMove]:
        # Sahte / yapay sektör yüzdesi yayını yapmamak için boş liste dön
        return []
