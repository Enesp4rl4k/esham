"""Tarımsal Emtia Ticaret & Depolama Stratejisi Backtest Motoru.

2020-2026 yılları arasındaki gerçek TÜRİB serileri üzerinde;
"Hasatta Spot Sat" vs "3 Ay Depola" vs "6 Ay Depola" vs "9 Ay Depola"
stratejilerini resmî depolama tarifesi, fire kaybı ve finansman faiziyle geriye dönük test eder.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..config import get_logger
from ..formatting import tr_number as _tr_number
from ..sources.turib import TuribSource
from ..turkish import tr_fold

log = get_logger(__name__)

# Resmî lisanslı depo kira tarifesi yaklaşık günlük TL/kg (0.005 TL/kg/gün = 5 TL/Ton/Gün)
VARSAYILAN_KIRA_GUNLUK_TL_KG = 0.005

# Yasal LİDAŞ fire oranları (süreye göre ürün kaybı kesri)
FIRE_ORANLARI = {
    3: 0.0035,  # 3 ay: %0.35 fire
    6: 0.0075,  # 6 ay: %0.75 fire
    9: 0.0115,  # 9 ay: %1.15 fire
}


@dataclass
class StrategyResult:
    strateji_adi: str
    vade_ay: int
    satis_ayi: int
    satis_fiyati: float
    brut_fark_tl_kg: float
    depolama_maliyeti: float
    finansman_maliyeti: float
    fire_maliyeti: float
    toplam_maliyet_tl_kg: float
    net_kar_zarar_tl_kg: float
    net_getiri_pct: float
    spotu_gecti_mi: bool


@dataclass
class SeasonResult:
    sezon_yili: int
    hasat_ayi: int
    hasat_spot_fiyati: float
    stratejiler: list[StrategyResult] = field(default_factory=list)
    kazanan_strateji: str = ""


@dataclass
class StorageBacktestReport:
    urun_grubu: str
    test_edilen_sezon_sayisi: int
    yillik_faiz_pct: float
    sezon_sonuclari: list[SeasonResult] = field(default_factory=list)
    strateji_3ay_kazanma_orani_pct: float = 0.0
    strateji_6ay_kazanma_orani_pct: float = 0.0
    strateji_9ay_kazanma_orani_pct: float = 0.0
    ortalama_6ay_net_getiri_pct: float = 0.0
    en_basarili_strateji: str = ""
    stratejik_tavsiye: str = ""


class StorageStrategyBacktester:
    """TÜRİB tarihsel serilerinde depolama arbitrajını geriye dönük test eden simülatör."""

    def __init__(self) -> None:
        self.turib_source = TuribSource()

    def run_backtest(
        self,
        urun_grubu: str = "BUĞDAY EKMEKLİK",
        yillik_faiz_pct: float = 50.0,
        kira_gunluk_tl_kg: float = VARSAYILAN_KIRA_GUNLUK_TL_KG,
    ) -> StorageBacktestReport:
        seri = self.turib_source.fetch_product_series(urun_grubu)
        if not seri:
            raise ValueError(f"'{urun_grubu}' için geriye dönük test verisi bulunamadı.")

        norm = tr_fold(urun_grubu)
        is_misir = "misir" in norm
        hasat_ayi = 10 if is_misir else 7  # Mısır: Ekim (10), Buğday/Arpa: Temmuz (07)

        # Aylık ortalama fiyatları hesapla: Map["YYYY-MM", ortalamaFiyat]
        aylik_toplam: dict[str, float] = {}
        aylik_adet: dict[str, int] = {}

        for m in seri:
            key = m["date"][:7]
            f = m["avg"] if m["avg"] > 0 else m["close"]
            aylik_toplam[key] = aylik_toplam.get(key, 0.0) + f
            aylik_adet[key] = aylik_adet.get(key, 0) + 1

        def ay_fiyati(yil: int, ay: int) -> float | None:
            key = f"{yil:04d}-{ay:02d}"
            if key in aylik_toplam and aylik_adet[key] > 0:
                return round(aylik_toplam[key] / aylik_adet[key], 4)
            return None

        yillar = [2020, 2021, 2022, 2023, 2024, 2025]
        sezon_sonuclari: list[SeasonResult] = []

        vadeler = [
            ("3 Ay Depolama Sonrası Satış", 3),
            ("6 Ay Depolama Sonrası Satış", 6),
            ("9 Ay Depolama Sonrası Satış", 9),
        ]

        for yil in yillar:
            spot_fiyat = ay_fiyati(yil, hasat_ayi)
            if spot_fiyat is None:
                continue

            strat_sonuclar: list[StrategyResult] = []

            for ad, ay_fark in vadeler:
                hedef_yil = yil
                hedef_ay = hasat_ayi + ay_fark
                if hedef_ay > 12:
                    hedef_ay -= 12
                    hedef_yil += 1

                satis_fiyati = ay_fiyati(hedef_yil, hedef_ay)
                if satis_fiyati is None:
                    continue

                gun_sayisi = ay_fark * 30
                fire_orani = FIRE_ORANLARI.get(ay_fark, 0.0075)

                depolama_maliyeti = kira_gunluk_tl_kg * gun_sayisi
                finansman_maliyeti = spot_fiyat * (yillik_faiz_pct / 100.0) * (gun_sayisi / 365.0)
                fire_maliyeti = spot_fiyat * fire_orani
                toplam_maliyet = depolama_maliyeti + finansman_maliyeti + fire_maliyeti

                brut_fark = satis_fiyati - spot_fiyat
                net_kar = brut_fark - toplam_maliyet
                net_getiri = (net_kar / spot_fiyat) * 100.0

                strat_sonuclar.append(
                    StrategyResult(
                        strateji_adi=ad,
                        vade_ay=ay_fark,
                        satis_ayi=hedef_ay,
                        satis_fiyati=round(satis_fiyati, 2),
                        brut_fark_tl_kg=round(brut_fark, 2),
                        depolama_maliyeti=round(depolama_maliyeti, 2),
                        finansman_maliyeti=round(finansman_maliyeti, 2),
                        fire_maliyeti=round(fire_maliyeti, 2),
                        toplam_maliyet_tl_kg=round(toplam_maliyet, 2),
                        net_kar_zarar_tl_kg=round(net_kar, 2),
                        net_getiri_pct=round(net_getiri, 2),
                        spotu_gecti_mi=net_kar > 0,
                    )
                )

            if strat_sonuclar:
                en_iyi = max(strat_sonuclar, key=lambda s: s.net_kar_zarar_tl_kg)
                kazanan = en_iyi.strateji_adi if en_iyi.net_kar_zarar_tl_kg > 0 else "Hasatta Spot Satış (Maliyetleri Karşılamadı)"

                sezon_sonuclari.append(
                    SeasonResult(
                        sezon_yili=yil,
                        hasat_ayi=hasat_ayi,
                        hasat_spot_fiyati=round(spot_fiyat, 2),
                        stratejiler=strat_sonuclar,
                        kazanan_strateji=kazanan,
                    )
                )

        n = len(sezon_sonuclari)
        if n == 0:
            raise ValueError(f"'{urun_grubu}' için test edilebilecek yeterli hasat sezonu bulunamadı.")

        s3_win = sum(1 for s in sezon_sonuclari if any(x.vade_ay == 3 and x.spotu_gecti_mi for x in s.stratejiler))
        s6_win = sum(1 for s in sezon_sonuclari if any(x.vade_ay == 6 and x.spotu_gecti_mi for x in s.stratejiler))
        s9_win = sum(1 for s in sezon_sonuclari if any(x.vade_ay == 9 and x.spotu_gecti_mi for x in s.stratejiler))

        s6_getiriler = [
            next((x.net_getiri_pct for x in s.stratejiler if x.vade_ay == 6), 0.0)
            for s in sezon_sonuclari
        ]
        ort_6ay = sum(s6_getiriler) / n if s6_getiriler else 0.0

        if s6_win >= s3_win and s6_win >= s9_win and s6_win > n / 2:
            en_basarili = "6 Ay Depolama Sonrası Satış (Kış/Ocak Çıkışı)"
        elif s3_win > s6_win and s3_win > n / 2:
            en_basarili = "3 Ay Depolama Sonrası Satış (Sonbahar/Ekim Çıkışı)"
        elif s9_win > s6_win and s9_win > n / 2:
            en_basarili = "9 Ay Depolama Sonrası Satış (İlkbahar/Nisan Çıkışı)"
        else:
            en_basarili = "Hasatta Spot Satış (Yüksek faiz ortamında depolama riskli)"

        tavsiye = (
            f"Tarihsel {n} hasat sezonunda, yıllık %{yillik_faiz_pct:.0f} alternatif finansman faizi ve resmî LİDAŞ kirası/fire düşüldüğünde; "
            f"en yüksek kârlılık '{en_basarili}' stratejisinde elde edildi. "
            f"6 aylık depolama stratejisinin hasat spot satışını geçme başarı oranı %{(s6_win / n) * 100:.0f} ve ortalama net getirisi %{ort_6ay:.1f} oldu."
        )

        return StorageBacktestReport(
            urun_grubu=urun_grubu,
            test_edilen_sezon_sayisi=n,
            yillik_faiz_pct=yillik_faiz_pct,
            sezon_sonuclari=sezon_sonuclari,
            strateji_3ay_kazanma_orani_pct=round((s3_win / n) * 100, 1),
            strateji_6ay_kazanma_orani_pct=round((s6_win / n) * 100, 1),
            strateji_9ay_kazanma_orani_pct=round((s9_win / n) * 100, 1),
            ortalama_6ay_net_getiri_pct=round(ort_6ay, 2),
            en_basarili_strateji=en_basarili,
            stratejik_tavsiye=tavsiye,
        )
