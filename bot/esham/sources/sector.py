"""BIST sektör endeksleri kaynağı (sektör rotasyonu için).

Yahoo Finance chart API'sinden sektör endekslerinin günlük değişimini çeker
(TradingView turkey scanner sektör endekslerini vermediği için Yahoo kullanılır),
en güçlüden en zayıfa sıralar. Hata durumunda örnek veriye düşülür.
"""
from __future__ import annotations

from dataclasses import dataclass

import requests

from ..config import default_headers, get_logger, settings
from ..http import retry_get
from ..formatting import tr_number

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


@dataclass
class SectorMove:
    code: str
    name: str
    change_pct: float

    @property
    def change_str(self) -> str:
        return f"{'+' if self.change_pct >= 0 else ''}{tr_number(self.change_pct, 2)}%"


class SectorSource:
    def __init__(self) -> None:
        self.headers = default_headers()

    def snapshot(self) -> list[SectorMove]:
        moves: list[SectorMove] = []
        for code, name in SECTORS.items():
            change = self._fetch_change(code)
            if change is not None:
                moves.append(SectorMove(code, name, change))
        if not moves:
            log.warning("Sektör verisi alınamadı; boş liste (örnek veri üretilmiyor).")
            return self._sample()
        moves.sort(key=lambda m: m.change_pct, reverse=True)
        log.info("Sektör verisi alındı: %d sektör.", len(moves))
        return moves

    def _fetch_change(self, code: str) -> float | None:
        try:
            resp = retry_get(
                CHART_URL.format(symbol=code),
                headers=self.headers,
                timeout=settings.http_timeout,
            )
            resp.raise_for_status()
            meta = resp.json()["chart"]["result"][0]["meta"]
        except (requests.RequestException, ValueError, KeyError, IndexError, TypeError) as exc:
            log.debug("Sektör %s alınamadı: %s", code, exc)
            return None
        price = meta.get("regularMarketPrice")
        prev = meta.get("chartPreviousClose") or meta.get("previousClose")
        if not price or not prev:
            return None
        return (price - prev) / prev * 100

    def _sample(self) -> list[SectorMove]:
        # Sahte / yapay sektör yüzdesi yayını yapmamak için boş liste dön
        return []
