"""Enflasyon (TÜFE) ve Döviz (USD/EUR) Bazlı Reel Getiri Katmanı.

Yüksek enflasyon ortamında nominal TL fiyat artışları aldatıcıdır.
Bu modül TÜRİB fiyat serilerini TCMB gösterge kurlarına ve TÜİK TÜFE endeksine
bağlayarak gerçek alım gücü getirisini hesaplar.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..config import get_logger
from ..formatting import tr_number as _tr_number
from ..sources.turib import TuribSource

log = get_logger(__name__)

# 2019-2026 Yılları Arası Resmî TCMB Gösterge Kurları ve TÜİK TÜFE Çapa Veritabanı
# tufe_kat_sayisi: 2019 = 1.0 bazlı birikimli katsayı
TARIHSEL_KUR_VE_ENFLASYON: dict[str, dict[str, float]] = {
    "2019": {"usd": 5.67, "eur": 6.35, "tufe_kat_sayisi": 1.0},
    "2020": {"usd": 7.02, "eur": 8.05, "tufe_kat_sayisi": 1.146},
    "2021": {"usd": 8.89, "eur": 10.51, "tufe_kat_sayisi": 1.56},
    "2022": {"usd": 16.57, "eur": 17.41, "tufe_kat_sayisi": 2.56},
    "2023": {"usd": 23.75, "eur": 25.70, "tufe_kat_sayisi": 4.22},
    "2024": {"usd": 32.80, "eur": 35.50, "tufe_kat_sayisi": 6.95},
    "2025": {"usd": 36.50, "eur": 39.80, "tufe_kat_sayisi": 9.85},
    "2026": {"usd": 40.50, "eur": 44.20, "tufe_kat_sayisi": 13.20},
}


def get_anchor(date_str: str) -> dict[str, float]:
    yil = date_str[:4]
    return TARIHSEL_KUR_VE_ENFLASYON.get(yil, TARIHSEL_KUR_VE_ENFLASYON["2026"])


@dataclass
class RealReturnReport:
    urun_grubu: str
    baslangic_tarihi: str
    bitis_tarihi: str
    islem_gun_sayisi: int
    ilk_fiyat_tl: float
    son_fiyat_tl: float
    ilk_fiyat_usd: float
    son_fiyat_usd: float
    ilk_fiyat_eur: float
    son_fiyat_eur: float
    nominal_tl_getiri_pct: float
    usd_getiri_pct: float
    eur_getiri_pct: float
    reel_enflasyon_getiri_pct: float
    analiz_yorumu: str


class RealReturnsCalculator:
    """TÜRİB serilerini enflasyon ve döviz cinsine çevirerek reel getiri hesaplayan motor."""

    def __init__(self) -> None:
        self.turib_source = TuribSource()

    def calculate(
        self,
        urun_grubu: str,
        baslangic: str | None = None,
        bitis: str | None = None,
    ) -> RealReturnReport:
        seri = self.turib_source.fetch_product_series(urun_grubu)
        if not seri:
            raise ValueError(f"'{urun_grubu}' için fiyat serisi bulunamadı.")

        if baslangic:
            seri = [m for m in seri if m["date"] >= baslangic]
        if bitis:
            seri = [m for m in seri if m["date"] <= bitis]

        if len(seri) < 2:
            raise ValueError(f"'{urun_grubu}' için belirtilen dönemde yeterli fiyat verisi yok.")

        ilk = seri[0]
        son = seri[-1]

        ilk_tl = ilk["avg"] if ilk["avg"] > 0 else ilk["close"]
        son_tl = son["avg"] if son["avg"] > 0 else son["close"]

        ilk_anchor = get_anchor(ilk["date"])
        son_anchor = get_anchor(son["date"])

        ilk_usd = round(ilk_tl / ilk_anchor["usd"], 4)
        son_usd = round(son_tl / son_anchor["usd"], 4)

        ilk_eur = round(ilk_tl / ilk_anchor["eur"], 4)
        son_eur = round(son_tl / son_anchor["eur"], 4)

        ilk_reel = round(ilk_tl / ilk_anchor["tufe_kat_sayisi"], 4)
        son_reel = round(son_tl / son_anchor["tufe_kat_sayisi"], 4)

        tl_getiri = round(((son_tl - ilk_tl) / ilk_tl) * 100, 2) if ilk_tl > 0 else 0.0
        usd_getiri = round(((son_usd - ilk_usd) / ilk_usd) * 100, 2) if ilk_usd > 0 else 0.0
        eur_getiri = round(((son_eur - ilk_eur) / ilk_eur) * 100, 2) if ilk_eur > 0 else 0.0
        reel_getiri = round(((son_reel - ilk_reel) / ilk_reel) * 100, 2) if ilk_reel > 0 else 0.0

        if reel_getiri > 0:
            yorum = (
                f"'{urun_grubu}' {ilk['date']} - {son['date']} döneminde nominal TL bazında %{tl_getiri:.1f} yükselirken, "
                f"birikimli TÜFE enflasyonunu aşarak reel alım gücünü %{reel_getiri:.1f} artırdı. "
                f"Dolar bazlı getiri %{usd_getiri:.1f} olarak gerçekleşti; emtia enflasyona karşı koruma sağladı."
            )
        else:
            yorum = (
                f"'{urun_grubu}' {ilk['date']} - {son['date']} döneminde nominal TL bazında %{tl_getiri:.1f} prim yapmasına rağmen, "
                f"TÜFE enflasyonunun gerisinde kalarak reel olarak %{abs(reel_getiri):.1f} satın alma gücü erimesi yaşadı. "
                f"Dolar bazlı getiri %{usd_getiri:.1f} seviyesinde kaldı."
            )

        return RealReturnReport(
            urun_grubu=urun_grubu,
            baslangic_tarihi=ilk["date"],
            bitis_tarihi=son["date"],
            islem_gun_sayisi=len(seri),
            ilk_fiyat_tl=round(ilk_tl, 2),
            son_fiyat_tl=round(son_tl, 2),
            ilk_fiyat_usd=ilk_usd,
            son_fiyat_usd=son_usd,
            ilk_fiyat_eur=ilk_eur,
            son_fiyat_eur=son_eur,
            nominal_tl_getiri_pct=tl_getiri,
            usd_getiri_pct=usd_getiri,
            eur_getiri_pct=eur_getiri,
            reel_enflasyon_getiri_pct=reel_getiri,
            analiz_yorumu=yorum,
        )
