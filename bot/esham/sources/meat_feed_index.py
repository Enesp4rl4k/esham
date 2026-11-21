"""Et-Yem Paritesi (Meat-to-Feed Ratio) ve Et TÜFE Endeksi Katmanı.

Türkiye hayvancılık, et sanayii ve perakende gıda sektörü için en kritik kârlılık
ve enflasyon göstergeleri:
  1. Dana Karkas / Besi Yemi Paritesi:
     - Formül: Dana Karkas (TL/kg) / Besi Yemi (TL/kg)
     - Başabaş eşiği: ~18-20 kg yem/kg et. 20'nin üzeri kârlı besi, 18'in altı üretici zararı
       ve 6-9 ay sonra arz krizine yol açan erken dişi kesimi alarmıdır.
  2. Tavuk Karkas / Kanatlı Karma Yemi Paritesi (TÜRİB Mısır/Arpa girdili - BANVT marjı).
  3. TÜİK Et ve Et Ürünleri TÜFE Endeksi:
     - Manşet TÜFE ile Et TÜFE ayrışması (Et Enflasyon Primi).
     - TÜRİB yem hammaddelerinden (Arpa, Mısır) et tüketici fiyatlarına 2-3 ay gecikmeli geçişkenlik.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ..config import get_logger
from ..sources.turib import TuribSource

log = get_logger(__name__)

ET_YEM_UNAVAILABLE = (
    "Et-yem paritesi / Et TÜFE için gerçek veri kaynağı (UKON karkas fiyatı, TÜİK Et ve Et Ürünleri TÜFE) "
    "bağlı değil; sabit/uydurma değer yayınlanmaz."
)


@dataclass
class MeatFeedParity:
    kategori: str                     # "Dana Besi", "Kuzu", "Tavuk / Beyaz Et"
    karkas_fiyati_tl_kg: float        # Karkas et fiyatı
    yem_fiyati_tl_kg: float           # İlgili karma yem veya TÜRİB hammadde maliyeti
    parite_orani: float               # karkas / yem (kg yem / kg et)
    esik_basabasi: float              # 20.0 (Besi için ideal eşik)
    kar_marji_durumu: str             # "KÂRLI BESI ALANI", "NORMAL BAŞABAŞ", "KRİTİK ZARAR ALANI"
    sinyal_yorumu: str


@dataclass
class MeatCpiReport:
    tarih: str
    et_tufe_endeks: float
    manset_tufe_endeks: float
    et_enflasyonu_yillik_pct: float
    manset_enflasyon_yillik_pct: float
    et_enflasyon_primi_pct: float     # Et TÜFE - Manşet TÜFE (Et enflasyonunun manşete göre farkı)
    pariteler: list[MeatFeedParity] = field(default_factory=list)
    bist_etkisi_ozeti: str = ""
    makro_degerlendirme: str = ""


class MeatFeedIndexAnalyzer:
    """Et-Yem Paritesi ve Et TÜFE analizi.

    Önceki sürüm karkas fiyatlarını ve Et/Manşet TÜFE endekslerini kod içindeki kaynaksız bir tablodan,
    TÜRİB arpa/mısır alınamazsa da 11,50 / 12,00 TL sabitlerinden üretip bugünün tarihiyle yayınlıyordu.
    Karkas fiyatı ve TÜFE için gerçek bir kaynak bağlı olmadığından `analyze()` None döner.
    """

    def __init__(self) -> None:
        self.turib_source = TuribSource()

    def analyze(self) -> MeatCpiReport | None:
        log.warning("Et-yem endeksi: %s", ET_YEM_UNAVAILABLE)
        return None
