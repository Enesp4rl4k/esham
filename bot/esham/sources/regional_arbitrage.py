"""Bölgesel ve Depolar Arası TÜRİB Arbitraj Motoru.

Farklı illerdeki lisanslı depolarda (LİDAŞ) aynı ürün için oluşan fiyat makaslarını (spread)
tarar, ortalama nakliye ve lojistik maliyetini düşerek net arbitraj imkanlarını hesaplar.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from ..config import get_logger
from ..formatting import tr_number as _tr_number
from ..sources.turib import TuribSource
from ..turkish import tr_fold

log = get_logger(__name__)

# Standart ortalama yurt içi dökme tahıl nakliye maliyeti göstergesi (~0.50 TL/kg)
VARSAYILAN_NAKLIYE_TL_KG = 0.50


@dataclass
class RegionalPriceGroup:
    il: str
    lidas_adi: str
    agirlikli_ortalama_fiyat: float
    toplam_miktar_kg: float
    toplam_hacim_tl: float
    islem_adedi: int


@dataclass
class ArbitrageSpread:
    urun: str
    ucuz_il: str
    ucuz_lidas: str
    ucuz_fiyat: float
    pahali_il: str
    pahali_lidas: str
    pahali_fiyat: float
    brut_makas_tl_kg: float
    tahmini_nakliye_tl_kg: float
    net_arbitraj_tl_kg: float
    net_arbitraj_pct: float
    firsat_seviyesi: str  # YUKSEK_FIRSAT, SINIRLI_FIRSAT, ARBITRAJ_YOK
    aciklama: str


@dataclass
class RegionalArbitrageReport:
    tarih: str
    urun_filtresi: str
    taranan_islem_sayisi: int
    bolgesel_fiyatlar: list[RegionalPriceGroup] = field(default_factory=list)
    en_iyi_firsatlar: list[ArbitrageSpread] = field(default_factory=list)
    genel_degerlendirme: str = ""


class RegionalArbitrageScanner:
    """TÜRİB günlük bültenlerinden lisanslı depolar ve iller arası arbitraj fırsatlarını süzen motor."""

    def __init__(self) -> None:
        self.turib_source = TuribSource()

    def scan(
        self,
        urun: str = "BUĞDAY",
        tarih_str: str | None = None,
        nakliye_maliyeti_tl_kg: float = VARSAYILAN_NAKLIYE_TL_KG,
    ) -> RegionalArbitrageReport:
        if not tarih_str:
            tarih_str = datetime.now().strftime("%Y-%m-%d")

        # Önce bülteni çek
        raw_trades = self.turib_source.fetch_bulletin_table(tarih_str)
        # Eğer bugün hafta sonu veya seans açılmadıysa geriye doğru 3 gün ara
        if not raw_trades:
            dt = datetime.strptime(tarih_str, "%Y-%m-%d")
            for geri in range(1, 4):
                onceki = (dt - timedelta(days=geri)).strftime("%Y-%m-%d")
                raw_trades = self.turib_source.fetch_bulletin_table(onceki)
                if raw_trades:
                    tarih_str = onceki
                    break

        norm_urun = tr_fold(urun)

        # Ham satırları ayrıştır
        # Beklenen satır formatı: [isin, enstrumanSinifi, oncekiKapanis, enDusuk, enYuksek, agirlikliOrt, kapanis, islemAdedi, miktarKg, hacimTl, lidasAdi, il, ilce, ...]
        kovalar: dict[str, list[dict[str, Any]]] = {}

        for t in raw_trades:
            cols = t.get("raw_cols", [])
            if len(cols) < 13:
                continue

            sinif = cols[2] if len(cols) > 2 else ""
            if norm_urun not in tr_fold(sinif):
                continue

            try:
                # 6: Ağırlıklı Ortalama, 7: Kapanış, 9: Miktar, 10: Hacim, 11: LİDAŞ, 12: İl
                f_str = cols[6] if cols[6] else cols[7]
                fiyat_val = float(f_str.replace(".", "").replace(",", "."))
                m_str = cols[9]
                miktar_val = float(m_str.replace(".", "").replace(",", "."))
                h_str = cols[10]
                hacim_val = float(h_str.replace(".", "").replace(",", ".")) if h_str else (fiyat_val * miktar_val)
                lidas = cols[11] if len(cols) > 11 and cols[11] else "Genel LİDAŞ"
                il = cols[12] if len(cols) > 12 and cols[12] else "Merkez"
            except (ValueError, IndexError):
                continue

            if fiyat_val <= 0 or miktar_val <= 0:
                continue

            key = f"{il}::{lidas}"
            if key not in kovalar:
                kovalar[key] = []
            kovalar[key].append({
                "fiyat": fiyat_val,
                "miktar": miktar_val,
                "hacim": hacim_val,
                "il": il,
                "lidas": lidas,
            })

        bolgesel_list: list[RegionalPriceGroup] = []
        for key, items in kovalar.items():
            toplam_miktar = sum(x["miktar"] for x in items)
            toplam_hacim = sum(x["hacim"] for x in items)
            ort_fiyat = (toplam_hacim / toplam_miktar) if toplam_miktar > 0 else 0.0
            il = items[0]["il"]
            lidas = items[0]["lidas"]

            bolgesel_list.append(
                RegionalPriceGroup(
                    il=il,
                    lidas_adi=lidas,
                    agirlikli_ortalama_fiyat=round(ort_fiyat, 2),
                    toplam_miktar_kg=round(toplam_miktar, 1),
                    toplam_hacim_tl=round(toplam_hacim, 2),
                    islem_adedi=len(items),
                )
            )

        # Sadece pozitif fiyatı olan geçerli işlemleri al ve fiyata göre sırala
        bolgesel_list = [b for b in bolgesel_list if b.agirlikli_ortalama_fiyat > 0]
        bolgesel_list.sort(key=lambda x: x.agirlikli_ortalama_fiyat)

        firsatlar: list[ArbitrageSpread] = []

        # En ucuz ile en pahalı bölgeler arasındaki spread'leri çıkar
        if len(bolgesel_list) >= 2:
            ucuzlar = bolgesel_list[:3]
            pahalilar = bolgesel_list[-3:]
            pahalilar.reverse()

            for u in ucuzlar:
                for p in pahalilar:
                    if u.il == p.il and u.lidas_adi == p.lidas_adi:
                        continue
                    if u.agirlikli_ortalama_fiyat <= 0:
                        continue
                    brut = round(p.agirlikli_ortalama_fiyat - u.agirlikli_ortalama_fiyat, 2)
                    if brut <= 0:
                        continue

                    net = round(brut - nakliye_maliyeti_tl_kg, 2)
                    net_pct = round((net / u.agirlikli_ortalama_fiyat) * 100, 2) if u.agirlikli_ortalama_fiyat > 0 else 0.0

                    if net > 0.50:
                        seviye = "YUKSEK_FIRSAT"
                        aciklama = f"{u.il} ({u.lidas_adi}) deposundan {u.agirlikli_ortalama_fiyat:.2f} TL'ye alınıp, {p.il} ({p.lidas_adi}) deposunda {p.agirlikli_ortalama_fiyat:.2f} TL'ye satıldığında nakliye sonrası net {net:.2f} TL/kg kâr kalır."
                    elif net > 0.0:
                        seviye = "SINIRLI_FIRSAT"
                        aciklama = f"Bölgeler arası {brut:.2f} TL brüt makas var; nakliye sonrası net marj {net:.2f} TL/kg seviyesinde kısıtlıdır."
                    else:
                        seviye = "ARBITRAJ_YOK"
                        aciklama = f"Brüt makas ({brut:.2f} TL), nakliye maliyetini ({nakliye_maliyeti_tl_kg:.2f} TL) karşılamamaktadır."

                    firsatlar.append(
                        ArbitrageSpread(
                            urun=urun,
                            ucuz_il=u.il,
                            ucuz_lidas=u.lidas_adi,
                            ucuz_fiyat=u.agirlikli_ortalama_fiyat,
                            pahali_il=p.il,
                            pahali_lidas=p.lidas_adi,
                            pahali_fiyat=p.agirlikli_ortalama_fiyat,
                            brut_makas_tl_kg=brut,
                            tahmini_nakliye_tl_kg=nakliye_maliyeti_tl_kg,
                            net_arbitraj_tl_kg=net,
                            net_arbitraj_pct=net_pct,
                            firsat_seviyesi=seviye,
                            aciklama=aciklama,
                        )
                    )

        # En yüksek net kâra göre sırala
        firsatlar.sort(key=lambda x: x.net_arbitraj_tl_kg, reverse=True)

        if firsatlar and firsatlar[0].net_arbitraj_tl_kg > 0:
            top = firsatlar[0]
            genel_degerlendirme = (
                f"TÜRİB bülteninde {top.ucuz_il} ile {top.pahali_il} lisanslı depoları arasında "
                f"{top.brut_makas_tl_kg:.2f} TL/kg brüt fiyat farkı tespit edildi. "
                f"Tahmini {nakliye_maliyeti_tl_kg:.2f} TL nakliye düşüldükten sonra net %{top.net_arbitraj_pct:.1f} ({top.net_arbitraj_tl_kg:.2f} TL/kg) arbitraj marjı bulunmaktadır."
            )
        else:
            genel_degerlendirme = (
                f"Taranan {len(bolgesel_list)} farklı lisanslı depoda fiyatlar bölgesel lojistik dengede seyretmektedir; "
                f"nakliye maliyetini aşan belirgin bir net arbitraj boşluğu bulunmamaktadır."
            )

        return RegionalArbitrageReport(
            tarih=tarih_str,
            urun_filtresi=urun,
            taranan_islem_sayisi=len(raw_trades),
            bolgesel_fiyatlar=bolgesel_list[:15],
            en_iyi_firsatlar=firsatlar[:5],
            genel_degerlendirme=genel_degerlendirme,
        )
