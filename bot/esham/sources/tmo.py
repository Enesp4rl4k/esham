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
    """Bir sezon ve ürün için TMO'nun resmen açıkladığı TABAN alım fiyatı (TL/kg; kaynaklarda TL/ton).

    `alim_fiyati_tl_kg=None` ve `dogrulandi=False`: birincil kaynakta bu sezon/ürün için açıklanmış fiyat
    BULUNAMADI; değer uydurulmaz, enterpole edilmez ve yayına girmez. Prim/destek taban fiyata
    eklenmez; kaynak ayrı veriyorsa `bakanlik_destegi_tl_kg` alanında tutulur.
    """
    yil: int
    kategori: str
    urun_adi: str                      # Resmî ürün tanımı (grup dahil)
    alim_fiyati_tl_kg: float | None    # TMO taban alım fiyatı (TL/kg); doğrulanamadıysa None
    bakanlik_destegi_tl_kg: float | None = None  # Kaynakta ayrı verilen destek/prim (TL/kg); taban fiyata dahil DEĞİL
    satis_fiyati_tl_kg: float | None = None      # Kaynakta açıklanmış TMO satış fiyatı (TL/kg)
    kaynak_url: str | None = None      # Birincil kaynak (tmo.gov.tr / tarimorman.gov.tr)
    duyuru_tarihi: str | None = None   # Duyuru tarihi (YYYY-MM-DD)
    dogrulandi: bool = False
    notlar: str = ""

    @property
    def toplam_uretici_fiyati_tl_kg(self) -> float | None:
        """Taban + kaynakta ayrı verilen destek (yalnızca ikisi de biliniyorsa)."""
        if self.alim_fiyati_tl_kg is None or self.bakanlik_destegi_tl_kg is None:
            return None
        return round(self.alim_fiyati_tl_kg + self.bakanlik_destegi_tl_kg, 3)


# Kaynak notu: her satır resmî duyuruya (URL + tarih) bağlıdır ve birim TL/ton -> TL/kg (÷1000) çevrilmiştir.
# Birincil kaynak bulunamayan hücreler `alim_fiyati_tl_kg=None, dogrulandi=False` taşır ("doğrulanamadı").
# Yeni değer eklerken resmî duyuru URL'si ve tarihi olmadan `dogrulandi=True` yapmayın; tahmin/enterpolasyon yok.
_K_2026 = "https://www.tarimorman.gov.tr/Haber/7092/2026-Yili-Hububat-Alim-Ve-Satis-Fiyatlari-Belirlendi"
_K_2025 = "https://www.tarimorman.gov.tr/Haber/6628/Tmo-2025-Yili-Hububat-Alim-Fiyatlarini-Acikladi"
_K_2025_MISIR = "https://www.tarimorman.gov.tr/Sayfalar/GormeEngellilerDetay.aspx?OgeId=6703&Liste=Haber"
_K_2024 = "https://www.tarimorman.gov.tr/Haber/6307/Toprak-Mahsulleri-Ofisi-2024-Hububat-Alim-Fiyatlari-Belirlendi"
_K_2023_HUB = "https://www.tmo.gov.tr/kurum-haber/716/2023-donemi-hububat-alim-fiyat-ve-politikalari"
_K_2023_MISIR = "https://www.tmo.gov.tr/kurum-haber/763/kamuoyu-aciklamasi"
_K_2022_GUNC = "https://www.tmo.gov.tr/kurum-haber/503/toprak-mahsulleri-ofisi-hububat-alim-fiyatlari-guncellenmistir"
_K_2022_MISIR = "https://siirt.tarimorman.gov.tr/Sayfalar/Detay.aspx?OgeId=345&Liste=Duyuru"
_K_2021 = "https://www.tmo.gov.tr/kamuoyu-duyurulari/324/2021-hububat-ve-bakliyat-alim-detaylari-belirlendi"

_YOK = "Birincil kaynakta bu sezon için açıklanmış TMO alım fiyatı bulunamadı (doğrulanamadı)."

TMO_FIYAT_VERITABANI: list[TmoFiyatKaydi] = [
    # 2026 Sezonu (duyuru 2 Haziran 2026). Destek: dekar başı 980 TL (ton başına ort. verimle 3.014 TL), ayrıca.
    TmoFiyatKaydi(2026, "Buğday", "Ekmeklik Buğday (2. Grup)", 16.50, 3.014, 18.50, _K_2026, "2026-06-02", True, "Satış 1 Ekim'den."),
    TmoFiyatKaydi(2026, "Buğday", "Makarnalık Buğday (2. Grup)", 16.50, 3.014, 18.50, _K_2026, "2026-06-02", True, "Satış 1 Ekim'den."),
    TmoFiyatKaydi(2026, "Arpa", "Arpa (2. Grup)", 12.75, 3.014, 14.00, _K_2026, "2026-06-02", True, "Satış 1 Ekim'den."),
    TmoFiyatKaydi(2026, "Mısır", "Mısır", None, notlar=_YOK),

    # 2025 Sezonu. Hububat duyurusu 3 Haziran 2025 (destek ton başına 2.520 TL); mısır 15 Ağustos 2025 (destek 668 TL/ton).
    TmoFiyatKaydi(2025, "Buğday", "Ekmeklik Buğday (2. Grup)", 13.50, 2.520, None, _K_2025, "2025-06-03", True),
    TmoFiyatKaydi(2025, "Buğday", "Makarnalık Buğday (2. Grup)", 13.50, 2.520, None, _K_2025, "2025-06-03", True),
    TmoFiyatKaydi(2025, "Arpa", "Arpa (2. Grup)", 11.00, 2.520, None, _K_2025, "2025-06-03", True),
    TmoFiyatKaydi(2025, "Mısır", "Mısır", 11.30, 0.668, None, _K_2025_MISIR, "2025-08-15", True),

    # 2024 Sezonu (duyuru 6 Haziran 2024; fark ödemesi "en fazla" buğdayda 1.750, arpada 750 TL/ton). Mısır için fiyat açıklanmadı.
    TmoFiyatKaydi(2024, "Buğday", "Ekmeklik Buğday (2. Grup)", 9.25, 1.75, None, _K_2024, "2024-06-06", True, "Destek: fark ödemesi, en fazla."),
    TmoFiyatKaydi(2024, "Buğday", "Makarnalık Buğday (2. Grup)", 10.00, 1.75, None, _K_2024, "2024-06-06", True, "Destek: fark ödemesi, en fazla."),
    TmoFiyatKaydi(2024, "Arpa", "Arpa (2. Grup)", 7.25, 0.75, None, _K_2024, "2024-06-06", True, "Destek: fark ödemesi, en fazla."),
    TmoFiyatKaydi(2024, "Mısır", "Mısır", None, notlar=_YOK),

    # 2023 Sezonu (hububat 6 Haziran 2023, prim buğdayda 1.000, arpada 500 TL/ton; mısır 22 Ağustos 2023, 2. sınıf).
    TmoFiyatKaydi(2023, "Buğday", "Ekmeklik Buğday (2. Grup)", 8.25, 1.00, None, _K_2023_HUB, "2023-06-06", True),
    TmoFiyatKaydi(2023, "Buğday", "Makarnalık Buğday (2. Grup)", 9.00, 1.00, None, _K_2023_HUB, "2023-06-06", True),
    TmoFiyatKaydi(2023, "Arpa", "Arpa (2. Grup)", 7.00, 0.50, None, _K_2023_HUB, "2023-06-06", True),
    TmoFiyatKaydi(2023, "Mısır", "Mısır (2. Sınıf, M2)", 6.00, None, None, _K_2023_MISIR, "2023-08-22", True),

    # 2022 Sezonu: 30 Haziran 2022 güncellemesiyle geçerli fiyatlar (ilk duyuru 5 Haziran: 6.050 / 6.500 / 5.500 TL/ton).
    # Prim (ayrı): buğday 1.000, arpa 500 TL/ton. Mısır: 23 Eylül 2022 tarihli bakanlık il müdürlüğü duyurusu (nem <= %14).
    TmoFiyatKaydi(2022, "Buğday", "Sert Ekmeklik Buğday (2. Grup)", 6.45, 1.00, None, _K_2022_GUNC, "2022-06-30", True, "İlk duyuru 5 Haziran 2022: 6.050 TL/ton."),
    TmoFiyatKaydi(2022, "Buğday", "Makarnalık Buğday (2. Grup)", 6.90, 1.00, None, _K_2022_GUNC, "2022-06-30", True, "İlk duyuru 5 Haziran 2022: 6.500 TL/ton."),
    TmoFiyatKaydi(2022, "Arpa", "Arpa (2. Grup)", 5.70, 0.50, None, _K_2022_GUNC, "2022-06-30", True, "İlk duyuru 5 Haziran 2022: 5.500 TL/ton."),
    TmoFiyatKaydi(2022, "Mısır", "Mısır (nem <= %14)", 5.70, None, None, _K_2022_MISIR, "2022-09-23", True, "Tarih: il müdürlüğü duyurusu."),

    # 2021 Sezonu (duyuru 17 Mayıs 2021). Mısır için fiyat açıklanmadı.
    TmoFiyatKaydi(2021, "Buğday", "Sert Ekmeklik Buğday (2. Grup)", 2.25, None, None, _K_2021, "2021-05-17", True),
    TmoFiyatKaydi(2021, "Buğday", "Makarnalık Buğday (2. Grup)", 2.45, None, None, _K_2021, "2021-05-17", True),
    TmoFiyatKaydi(2021, "Arpa", "Arpa", 1.75, None, None, _K_2021, "2021-05-17", True),
    TmoFiyatKaydi(2021, "Mısır", "Mısır", None, notlar=_YOK),
]


@dataclass
class TmoKarsilastirmaRaporu:
    urun_grubu: str
    serbest_piyasa_fiyati: float
    birim: str
    tarih: str
    tmo_yil: int
    tmo_urun_adi: str
    tmo_alim_fiyati: float | None
    bakanlik_destegi: float | None
    toplam_uretici_fiyati: float | None
    tmo_satis_fiyati: float | None
    alim_farki_tl: float | None
    alim_prim_yuzde: float | None
    toplam_fark_tl: float | None
    toplam_prim_yuzde: float | None
    satis_farki_tl: float | None
    piyasa_durumu: str  # TMO_USTUNDE_PRIMLI, TMO_ALIM_CIVARINDA, TMO_ALTINDA_ISKONTOLU, TMO_DOGRULANAMADI
    piyasa_yorumu: str
    tmo_kaynak_url: str | None = None
    tmo_duyuru_tarihi: str | None = None
    tmo_dogrulandi: bool = False


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

        if tmo_kaydi.alim_fiyati_tl_kg is None or not tmo_kaydi.dogrulandi:
            # Doğrulanamayan hücre: değer yayınlanmaz, kıyas yapılmaz.
            return TmoKarsilastirmaRaporu(
                urun_grubu=urun_grubu, serbest_piyasa_fiyati=serbest_fiyat, birim="TL/kg", tarih=tarih_str,
                tmo_yil=tmo_kaydi.yil, tmo_urun_adi=tmo_kaydi.urun_adi, tmo_alim_fiyati=None,
                bakanlik_destegi=None, toplam_uretici_fiyati=None, tmo_satis_fiyati=None,
                alim_farki_tl=None, alim_prim_yuzde=None, toplam_fark_tl=None, toplam_prim_yuzde=None,
                satis_farki_tl=None, piyasa_durumu="TMO_DOGRULANAMADI",
                piyasa_yorumu=f"{tmo_kaydi.yil} sezonu için resmî TMO alım fiyatı doğrulanamadı; kıyas yapılmadı.",
                tmo_kaynak_url=None, tmo_duyuru_tarihi=None, tmo_dogrulandi=False,
            )

        alim_farki = round(serbest_fiyat - tmo_kaydi.alim_fiyati_tl_kg, 2)
        alim_prim_pct = round(((serbest_fiyat - tmo_kaydi.alim_fiyati_tl_kg) / tmo_kaydi.alim_fiyati_tl_kg) * 100, 2)

        toplam = tmo_kaydi.toplam_uretici_fiyati_tl_kg
        toplam_fark = round(serbest_fiyat - toplam, 2) if toplam else None
        toplam_prim_pct = round(((serbest_fiyat - toplam) / toplam) * 100, 2) if toplam else None

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
            toplam_uretici_fiyati=toplam,
            tmo_satis_fiyati=tmo_kaydi.satis_fiyati_tl_kg,
            alim_farki_tl=alim_farki,
            alim_prim_yuzde=alim_prim_pct,
            toplam_fark_tl=toplam_fark,
            toplam_prim_yuzde=toplam_prim_pct,
            satis_farki_tl=satis_farki,
            piyasa_durumu=durum,
            piyasa_yorumu=yorum,
            tmo_kaynak_url=tmo_kaydi.kaynak_url,
            tmo_duyuru_tarihi=tmo_kaydi.duyuru_tarihi,
            tmo_dogrulandi=True,
        )
