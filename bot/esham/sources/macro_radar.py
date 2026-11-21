"""Türkiye Makro Barometresi & VİOP Basis / Likidite İstihbarat Motoru.

Bu modül:
1. VİOP BIST 30 vadeli kontratı ile spot arasındaki prim/iskontoyu (basis) CANLI TradingView
   kotasyonlarından hesaplar. Gerçek kotasyon yoksa hiçbir değer üretilmez (None).
2. Makro barometre (CDS, TCMB rezervleri, politika faizi vb.) için gerçek bir veri kaynağı YOKTUR;
   `get_macro_barometer` bu yüzden None döner. Sabit/uydurma sayı asla yayınlanmaz.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from ..config import get_logger
from .viop import ViopSource

log = get_logger(__name__)


MACRO_BAROMETER_UNAVAILABLE = (
    "Makro barometre (CDS, TCMB rezervleri, politika faizi, tahvil faizi) için gerçek bir veri kaynağı "
    "bağlı değil; sabit/uydurma değer yayınlanmaz."
)
VIOP_BASIS_UNAVAILABLE = (
    "VİOP spot/vadeli kotasyonu temin edilemedi; basis hesaplanmadı (sabit/uydurma değer yayınlanmaz)."
)


@dataclass
class ViopBasisResult:
    """Yalnızca gerçek kotasyondan türetilen basis. Vade, açık pozisyon vb. kaynaksız alanlar yoktur."""

    spot_xu030: float
    futures_f_xu030_near: float
    basis_points: float
    basis_pct: float
    as_of: str
    evaluation: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "spot_xu030": self.spot_xu030,
            "vadeli_f_xu030": self.futures_f_xu030_near,
            "basis_puan": self.basis_points,
            "basis_yuzde": self.basis_pct,
            "veri_tarihi": self.as_of,
            "degerlendirme": self.evaluation,
        }


class MacroRadarAnalyzer:
    """Makroekonomik veriler ve VİOP Basis analiz motoru (yalnızca gerçek veriyle)."""

    def __init__(self, viop_source: ViopSource | None = None) -> None:
        self._viop = viop_source

    def get_macro_barometer(self) -> None:
        log.warning("Makro barometre: %s", MACRO_BAROMETER_UNAVAILABLE)
        return None

    def get_viop_basis(self) -> ViopBasisResult | None:
        """Canlı XU030 / XU030D kotasyonundan basis; gerçek yanıt yoksa None."""
        quote = (self._viop or ViopSource()).market_quote()
        if quote is None or not quote.has_futures:
            log.warning("VİOP basis: %s", VIOP_BASIS_UNAVAILABLE)
            return None
        spot, fut = quote.index_value, quote.futures_value
        if not spot or not fut or spot <= 0 or fut <= 0:
            log.warning("VİOP basis: kotasyonda sayısal değer yok.")
            return None
        basis = fut - spot
        basis_pct = round(basis / spot * 100.0, 2)
        side = "primli (Contango)" if basis >= 0 else "iskontolu (Backwardation)"
        evaluation = (
            f"VİOP XU030 vadeli kontratı spot endekse göre {basis:+.2f} puan ({basis_pct:+.2f}%) {side} işlem görüyor."
        )
        as_of = datetime.now(timezone(timedelta(hours=3))).isoformat(timespec="seconds")
        return ViopBasisResult(
            spot_xu030=spot,
            futures_f_xu030_near=fut,
            basis_points=round(basis, 2),
            basis_pct=basis_pct,
            as_of=as_of,
            evaluation=evaluation,
        )

    def export_data(self, web_data_dir: str | Path) -> None:
        """Yalnızca GERÇEK veri varsa yazar. Veri yoksa dosyaya dokunmaz (son iyi dosya kalır)."""
        p = Path(web_data_dir)
        p.mkdir(parents=True, exist_ok=True)

        vb = self.get_viop_basis()
        if vb is None:
            log.warning("VİOP basis JSON yazılmadı (gerçek veri yok).")
            return
        with open(p / "viop-basis.json", "w", encoding="utf-8") as f:
            json.dump({"updated_at": vb.as_of, **vb.to_dict()}, f, ensure_ascii=False, indent=2)
        log.info("VİOP Basis verisi kaydedildi: %s", p)
