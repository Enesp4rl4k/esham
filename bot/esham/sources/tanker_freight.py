"""Petrol (Brent) göstergesi — tanker navlun verisi için gerçek kaynak YOK.

Önceki sürüm; WTI (Brent - 3,60 ile türetilmiş), Urals iskontosu, crack spread, BDTI/BCTI endeksleri,
VLSFO bunker fiyatı, tanker kiralama günlük ücretleri (TD3C vb.) ve boğaz bekleme/demuraj rakamlarını
kod içine gömülü sabitlerle üretiyordu; Brent alınamazsa da 74,80 sabitini yazıyordu. Bunlar okura gerçek
piyasa verisi gibi sunulamaz. Artık yalnızca Yahoo'dan gelen GERÇEK Brent kotasyonu (BZ=F) yayınlanır;
alınamazsa `fetch_snapshot()` None döner. Navlun/TCE/boğaz alanları kaynak bağlanana kadar yoktur.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from ..config import get_logger

log = get_logger(__name__)


@dataclass
class TankerFreightSnapshot:
    """Yalnızca gerçek Brent kotasyonu."""

    updated_at: str
    date: str
    brent_price: float
    brent_str: str
    brent_change_pct: float
    brent_change_str: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "updatedAt": self.updated_at,
            "date": self.date,
            "oilBenchmarks": {
                "brent": {
                    "price": self.brent_price,
                    "priceStr": self.brent_str,
                    "changePct": self.brent_change_pct,
                    "changeStr": self.brent_change_str,
                },
            },
        }


class TankerFreightSource:
    def fetch_snapshot(self) -> TankerFreightSnapshot | None:
        """Canlı Brent kotasyonu; alınamazsa None (sabit fiyat yazılmaz)."""
        brent = None
        try:
            from .global_macro import GlobalMacroSource

            for t in GlobalMacroSource().snapshot().tickers:
                if t.label == "BRENT":
                    brent = t
                    break
        except Exception as exc:  # noqa: BLE001 - kaynak hatası yayını durdurmamalı
            log.warning("TankerFreightSource: Brent okunamadı: %s", exc)
        if brent is None or not brent.price or brent.price <= 0:
            log.warning("TankerFreightSource: canlı Brent yok; veri yayınlanmıyor.")
            return None

        now = datetime.now(timezone(timedelta(hours=3)))
        sign = "+" if brent.change_pct >= 0 else ""
        return TankerFreightSnapshot(
            updated_at=now.isoformat(timespec="seconds"),
            date=now.strftime("%Y-%m-%d"),
            brent_price=brent.price,
            brent_str=f"${brent.price:.2f}",
            brent_change_pct=brent.change_pct,
            brent_change_str=f"{sign}{brent.change_pct:.2f}%",
        )
