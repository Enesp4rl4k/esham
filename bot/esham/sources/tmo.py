"""Toprak Mahsulleri Ofisi (TMO) Müdahale Alım, Satış ve Prim Fiyatları Katmanı.

TMO fiyatları Türkiye tarımsal emtia piyasasının resmî taban ve tavan çıpasıdır.
Serbest piyasa (ELÜS) fiyatlarının TMO müdahale fiyatlarına göre durumu,
regülasyon baskısını ve üretici/sanayici ticaret dinamiklerini belirler.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from ..config import get_logger
from ..formatting import tr_number as _tr_number
from ..turkish import tr_fold

log = get_logger(__name__)


@dataclass
class TmoFiyatKaydi:
    yil: int
    kategori: str
    urun_adi: str
    alim_fiyati_tl_kg: float          # TMO Resmî Alım Fiyatı (TL/kg)
    bakanlik_destegi_tl_kg: float     # Bakanlık ÇKS Üretici Prim Desteği (TL/kg)
    toplam_uretici_fiyati_tl_kg: float # Çiftçinin eline geçen toplam bedel
    satis_fiyati_tl_kg: float | None  # TMO Regülasyon Satış Fiyatı (varsa)
    notlar: str = ""


# 2021-2026 Resmî TMO Müdahale Alım ve Satış Fiyatları Arşivi (TL/kg)
TMO_FIYAT_VERITABANI: list[TmoFiyatKaydi] = [
    # 2026 Sezonu (Güncel)
    TmoFiyatKaydi(2026, "Buğday", "Ekmeklik Buğday (2. Grup)", 13.50, 1.75, 15.25, 16.00, "2026 dönemi müdahale alım fiyatı ve prim desteği."),
    TmoFiyatKaydi(2026, "Buğday", "Makarnalık Buğday (2. Grup)", 14.50, 1.75, 16.25, 17.20, "Durum makarnalık buğday alım fiyatı."),
    TmoFiyatKaydi(2026, "Arpa", "Arpa", 10.75, 1.00, 11.75, 12.50, "Yemlik arpa alım fiyatı."),
    TmoFiyatKaydi(2026, "Mısır", "Mısır", 12.00, 1.00, 13.00, 13.80, "Yerli mısır müdahale alım fiyatı."),

    # 2025 Sezonu
    TmoFiyatKaydi(2025, "Buğday", "Ekmeklik Buğday (2. Grup)", 9.25, 1.75, 11.00, 11.50, "2025 hasat dönemi fiyatı."),
    TmoFiyatKaydi(2025, "Buğday", "Makarnalık Buğday (2. Grup)", 10.00, 1.75, 11.75, 12.25),
    TmoFiyatKaydi(2025, "Arpa", "Arpa", 7.25, 0.75, 8.00, 8.75),
    TmoFiyatKaydi(2025, "Mısır", "Mısır", 8.50, 0.75, 9.25, 10.00),

    # 2024 Sezonu
    TmoFiyatKaydi(2024, "Buğday", "Ekmeklik Buğday (2. Grup)", 8.25, 1.00, 9.25, 9.75),
    TmoFiyatKaydi(2024, "Buğday", "Makarnalık Buğday (2. Grup)", 9.00, 1.00, 10.00, 10.50),
    TmoFiyatKaydi(2024, "Arpa", "Arpa", 7.00, 0.50, 7.50, 8.00),
    TmoFiyatKaydi(2024, "Mısır", "Mısır", 6.00, 0.50, 6.50, 7.20),

    # 2023 Sezonu
    TmoFiyatKaydi(2023, "Buğday", "Ekmeklik Buğday (2. Grup)", 8.25, 1.00, 9.25, 9.50),
    TmoFiyatKaydi(2023, "Buğday", "Makarnalık Buğday (2. Grup)", 9.00, 1.00, 10.00, 10.20),
    TmoFiyatKaydi(2023, "Arpa", "Arpa", 7.00, 0.50, 7.50, 7.80),
    TmoFiyatKaydi(2023, "Mısır", "Mısır", 6.00, 0.50, 6.50, 6.80),

    # 2022 Sezonu
    TmoFiyatKaydi(2022, "Buğday", "Ekmeklik Buğday (2. Grup)", 6.05, 1.00, 7.05, 7.25),
    TmoFiyatKaydi(2022, "Buğday", "Makarnalık Buğday (2. Grup)", 6.90, 1.00, 7.90, 8.10),
    TmoFiyatKaydi(2022, "Arpa", "Arpa", 5.50, 0.50, 6.00, 6.25),
    TmoFiyatKaydi(2022, "Mısır", "Mısır", 5.70, 0.50, 6.20, 6.50),

    # 2021 Sezonu
    TmoFiyatKaydi(2021, "Buğday", "Ekmeklik Buğday (2. Grup)", 2.25, 0.20, 2.45, 2.70),
    TmoFiyatKaydi(2021, "Buğday", "Makarnalık Buğday (2. Grup)", 2.45, 0.20, 2.65, 2.90),
    TmoFiyatKaydi(2021, "Arpa", "Arpa", 1.75, 0.15, 1.90, 2.10),
    TmoFiyatKaydi(2021, "Mısır", "Mısır", 1.95, 0.15, 2.10, 2.30),
]


@dataclass
class TmoKarsilastirmaRaporu:
    urun_grubu: str
    serbest_piyasa_fiyati: float
    birim: str
    tarih: str
    tmo_yil: int
    tmo_urun_adi: str
    tmo_alim_fiyati: float
    bakanlik_destegi: float
    toplam_uretici_fiyati: float
    tmo_satis_fiyati: float | None
    alim_farki_tl: float
    alim_prim_yuzde: float
    toplam_fark_tl: float
    toplam_prim_yuzde: float
    satis_farki_tl: float | None
    piyasa_durumu: str  # TMO_USTUNDE_PRIMLI, TMO_ALIM_CIVARINDA, TMO_ALTINDA_ISKONTOLU
    piyasa_yorumu: str


class TmoSource:
    """TMO referans fiyatlarını sorgulayan ve serbest piyasayla karşılaştıran motor."""

    def list_records(self, yil: int | None = None, kategori: str | None = None) -> list[TmoFiyatKaydi]:
        liste = list(TMO_FIYAT_VERITABANI)
        if yil is not None:
            liste = [k for k in liste if k.yil == yil]
        if kategori:
            aranan = tr_fold(kategori)
            liste = [k for k in liste if aranan in tr_fold(k.kategori) or aranan in tr_fold(k.urun_adi)]
        return sorted(liste, key=lambda x: (-x.yil, x.urun_adi))

    def match_product(self, urun_adi: str, yil: int = 2026) -> TmoFiyatKaydi | None:
        norm = tr_fold(urun_adi)
        yil_kayitlari = [k for k in TMO_FIYAT_VERITABANI if k.yil == yil]

        if "makarnalik" in norm:
            for k in yil_kayitlari:
                if "makarnalik" in tr_fold(k.urun_adi):
                    return k
        if "bugday" in norm or "ekmeklik" in norm:
            for k in yil_kayitlari:
                if "ekmeklik" in tr_fold(k.urun_adi):
                    return k
        if "arpa" in norm:
            for k in yil_kayitlari:
                if "arpa" in tr_fold(k.urun_adi):
                    return k
        if "misir" in norm:
            for k in yil_kayitlari:
                if "misir" in tr_fold(k.urun_adi):
                    return k

        for k in yil_kayitlari:
            if tr_fold(k.kategori) in norm:
                return k
        return None

    def compare(
        self,
        urun_grubu: str,
        manuel_fiyat: float | None = None,
        referans_yili: int = 2026,
    ) -> TmoKarsilastirmaRaporu:
        from .turib import TuribSource

        tmo_kaydi = self.match_product(urun_grubu, referans_yili)
        if not tmo_kaydi:
            raise ValueError(f"'{urun_grubu}' için {referans_yili} yılına ait TMO referans kaydı bulunamadı.")

        serbest_fiyat = manuel_fiyat
        tarih_str = datetime.now().strftime("%Y-%m-%d")

        if serbest_fiyat is None:
            ts = TuribSource()
            p = ts.fetch_latest_product_price(urun_grubu)
            if not p:
                raise ValueError(f"'{urun_grubu}' için güncel TÜRİB piyasa fiyatı alınamadı.")
            serbest_fiyat = p.avg_price_tl_kg
            tarih_str = p.date

        alim_farki = round(serbest_fiyat - tmo_kaydi.alim_fiyati_tl_kg, 2)
        alim_prim_pct = round(((serbest_fiyat - tmo_kaydi.alim_fiyati_tl_kg) / tmo_kaydi.alim_fiyati_tl_kg) * 100, 2)

        toplam_fark = round(serbest_fiyat - tmo_kaydi.toplam_uretici_fiyati_tl_kg, 2)
        toplam_prim_pct = round(((serbest_fiyat - tmo_kaydi.toplam_uretici_fiyati_tl_kg) / tmo_kaydi.toplam_uretici_fiyati_tl_kg) * 100, 2)

        satis_farki = round(serbest_fiyat - tmo_kaydi.satis_fiyati_tl_kg, 2) if tmo_kaydi.satis_fiyati_tl_kg is not None else None

        if alim_prim_pct >= 5.0:
            durum = "TMO_USTUNDE_PRIMLI"
            yorum = (
                f"Serbest piyasa fiyatı ({serbest_fiyat:.2f} TL/kg), TMO alım tabanının ({tmo_kaydi.alim_fiyati_tl_kg:.2f} TL/kg) "
                f"%{alim_prim_pct:.1f} üzerinde primli seyrediyor. Özel sektör talebi canlı, üretici ürününü TMO yerine ELÜS borsasında satmayı tercih ediyor."
            )
        elif alim_prim_pct <= -3.0:
            durum = "TMO_ALTINDA_ISKONTOLU"
            yorum = (
                f"Serbest piyasa fiyatı ({serbest_fiyat:.2f} TL/kg), TMO alım tabanının ({tmo_kaydi.alim_fiyati_tl_kg:.2f} TL/kg) "
                f"%{abs(alim_prim_pct):.1f} altında iskontolu işlem görüyor. Piyasada arz fazlası veya talep durgunluğu var; üreticiler için TMO'ya teslimat daha avantajlı hale gelebilir."
            )
        else:
            durum = "TMO_ALIM_CIVARINDA"
            yorum = (
                f"Serbest piyasa fiyatı ({serbest_fiyat:.2f} TL/kg), TMO müdahale alım fiyatı ({tmo_kaydi.alim_fiyati_tl_kg:.2f} TL/kg) ile dengede. "
                "Piyasada TMO taban çıpası etkin olarak çalışıyor."
            )

        return TmoKarsilastirmaRaporu(
            urun_grubu=urun_grubu,
            serbest_piyasa_fiyati=serbest_fiyat,
            birim="TL/kg",
            tarih=tarih_str,
            tmo_yil=tmo_kaydi.yil,
            tmo_urun_adi=tmo_kaydi.urun_adi,
            tmo_alim_fiyati=tmo_kaydi.alim_fiyati_tl_kg,
            bakanlik_destegi=tmo_kaydi.bakanlik_destegi_tl_kg,
            toplam_uretici_fiyati=tmo_kaydi.toplam_uretici_fiyati_tl_kg,
            tmo_satis_fiyati=tmo_kaydi.satis_fiyati_tl_kg,
            alim_farki_tl=alim_farki,
            alim_prim_yuzde=alim_prim_pct,
            toplam_fark_tl=toplam_fark,
            toplam_prim_yuzde=toplam_prim_pct,
            satis_farki_tl=satis_farki,
            piyasa_durumu=durum,
            piyasa_yorumu=yorum,
        )
