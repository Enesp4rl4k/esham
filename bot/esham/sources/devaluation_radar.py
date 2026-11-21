"""TRY Devalüasyon / Kur Şoku Basınç Radarı.

DURUM: Radar beş girdiye dayanıyordu (VİOP USD/TRY vadeli, TCMB swap hariç net rezerv, Kapalıçarşı
makası, 5Y CDS, REER). Bu girdilerin hiçbiri için gerçek bir veri kaynağı bağlı DEĞİL; önceki sürüm
bunları kod içine gömülü sabitlerle (spot 34,30, vadeli 35,82, CDS 264, rezerv 31,5 mrd $ ...) üretip
yayınlıyordu. Uydurma piyasa sayısı okura gerçek gibi sunulamayacağı için analizör artık yalnızca
GERÇEK bir kaynak yanıtı varsa sonuç üretir; kaynak bağlanana kadar `analyze()` her zaman None döner
ve hiçbir JSON yazılmaz.

Gerçek kaynak bağlandığında `analyze()` içinde, kaynak yanıtı olmadan sonuç üretilemeyecek şekilde
(tests/test_no_fabricated_market_numbers.py korumasına bakın) uygulanmalıdır.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from ..config import get_logger

log = get_logger(__name__)

DEVALUATION_RADAR_UNAVAILABLE = (
    "Kur basınç radarı için gerçek veri kaynağı (VİOP USD/TRY vadeli, TCMB rezervleri, Kapalıçarşı, CDS, REER) "
    "bağlı değil; sabit/uydurma değer yayınlanmaz."
)


class DevaluationRadarAnalyzer:
    """Gerçek kaynak yanıtı yoksa None döndüren radar (şu an kaynak bağlı değil)."""

    def analyze(self) -> dict[str, Any] | None:
        log.warning("Devalüasyon radarı: %s", DEVALUATION_RADAR_UNAVAILABLE)
        return None


def export_devaluation_radar_json(target_path: Path | str | None = None) -> Path | None:
    """Radar sonucu varsa yazar; yoksa (şu an daima) hiçbir dosya yazmadan None döner."""
    res = DevaluationRadarAnalyzer().analyze()
    if res is None:
        log.warning("Devalüasyon radarı JSON yazılmadı (gerçek veri yok).")
        return None
    raise NotImplementedError("Gerçek kaynak bağlandığında JSON serileştirmesi burada eklenmeli.")
