"""BIST & TÜRİB Çapraz Piyasa Analizi (Agri-BIST Cross-Market Intelligence).

Borsa İstanbul'daki gıda/tarım sanayi şirketleri (ULUUN, PETUN, BANVT, TATGD, TUKAS vb.)
ve BIST Gıda Endeksi (XGIDA) ile TÜRİB ELÜS tarımsal emtia fiyatları (Buğday, Mısır, Arpa)
arasındaki maliyet baskısı, kârlılık korelasyonu ve girdi marjlarını analiz eder.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..config import get_logger
from ..formatting import tr_number as _tr_number
from ..sources.bist import BistSource
from ..sources.turib import TuribSource, TuribSnapshot, TuribProductPrice

log = get_logger(__name__)

# BIST'teki tarım/gıda hisseleri ve doğrudan bağımlı oldukları TÜRİB ELÜS emtiaları
AGRI_BIST_RELATIONS: dict[str, dict[str, Any]] = {
    "ULUUN": {
        "name": "Ulusoy Un Sanayi",
        "primary_commodity": "BUĞDAY EKMEKLİK",
        "impact_type": "input_cost",  # Buğday artışı hammadde maliyetini artırır, stok değerini yükseltir
        "description": "Un üretiminde ana hammadde ekmeklik buğdaydır.",
    },
    "PETUN": {
        "name": "Pınar Et ve Un",
        "primary_commodity": "BUĞDAY EKMEKLİK",
        "impact_type": "input_cost",
        "description": "Un ve yem sanayii girdi maliyeti.",
    },
    "BANVT": {
        "name": "Banvit",
        "primary_commodity": "MISIR",
        "secondary_commodity": "ARPA",
        "impact_type": "feed_cost",  # Kanatlı et üretim maliyetinin ~%65'i yemdir (mısır/soya)
        "description": "Kanatlı yem rasyonunda mısır ve arpa kritik girdi maliyetidir.",
    },
    "TATGD": {
        "name": "Tat Gıda",
        "primary_commodity": "BUĞDAY MAKARNALIK",
        "impact_type": "input_cost",
        "description": "Makarnalık buğday ve tarımsal hammadde fiyat duyarlılığı.",
    },
    "TUKAS": {
        "name": "Tukaş Gıda",
        "primary_commodity": "BUĞDAY EKMEKLİK",
        "impact_type": "input_cost",
        "description": "Tarımsal mamul ve konserve girdisi.",
    },
}


@dataclass
class AgriCompanyImpact:
    ticker: str
    company_name: str
    stock_price: str
    stock_change: str
    commodity: str
    commodity_price: float
    commodity_change: float
    margin_pressure: str  # "Pozitif (Stok Kârı)", "Negatif (Maliyet Baskısı)", "Nötr"
    commentary: str


@dataclass
class AgriBistCorrelationReport:
    date: str
    xgida_price: str
    xgida_change: str
    turib_hububat_index: str
    turib_hububat_change: str
    company_impacts: list[AgriCompanyImpact] = field(default_factory=list)
    macro_takeaway: str = ""


class AgriBistAnalyzer:
    """BIST ve TÜRİB verilerini çaprazlayarak gıda enflasyonu ve şirket kârlılık sinyalleri üretir."""

    def __init__(self) -> None:
        self.turib_source = TuribSource()

    def analyze(self, turib_snap: TuribSnapshot | None = None) -> AgriBistCorrelationReport:
        if turib_snap is None:
            turib_snap = self.turib_source.snapshot()

        # 1. BIST Gıda Endeksi (XGIDA.IS)
        xgida = BistSource(symbol="XGIDA.IS").market_summary()

        # TÜRİB Hububat Endeksi
        hububat_val = _tr_number(turib_snap.hububat_index.price) if turib_snap.hububat_index else "—"
        hububat_chg = f"{'+' if turib_snap.hububat_index.change_pct >= 0 else ''}{_tr_number(turib_snap.hububat_index.change_pct)}%" if turib_snap.hububat_index else "—"

        # TÜRİB ürün fiyat haritası
        prod_map: dict[str, TuribProductPrice] = {p.product: p for p in turib_snap.products}

        company_impacts: list[AgriCompanyImpact] = []

        for ticker, meta in AGRI_BIST_RELATIONS.items():
            comm_name = meta["primary_commodity"]
            comm = prod_map.get(comm_name)
            if comm is None:
                # Canlı TÜRİB fiyatı yok: 0,0 TL/kg gibi sahte bir değer yayınlama, şirketi atla.
                log.warning("AgriBist: %s için TÜRİB %s fiyatı yok; şirket atlandı.", ticker, comm_name)
                continue
            stock = BistSource(symbol=f"{ticker}.IS").market_summary()

            comm_price = comm.avg_price_tl_kg
            comm_chg = comm.change_pct

            # Basit deterministik marj duyarlılığı:
            # Emtia fiyatı hızla artıyorsa (>+%3) ve hisse fiyatı ayak uyduramadıysa -> maliyet baskısı
            # Emtia fiyatı düşüyorsa (<-%2) -> kâr marjında rahatlama
            pressure = "Nötr"
            commentary = ""

            if comm_chg > 3.0:
                if meta["impact_type"] == "feed_cost":
                    pressure = "Yüksek Maliyet Baskısı"
                    commentary = f"TÜRİB {comm_name} fiyatındaki %{_tr_number(comm_chg)} artış, {ticker} yem maliyetlerini yukarı yönlü zorluyor."
                else:
                    pressure = "Maliyet & Stok Artışı"
                    commentary = f"TÜRİB {comm_name} fiyatındaki %{_tr_number(comm_chg)} yükseliş, hammadde maliyetini artırırken mevcut silo stoklarına kâr yazabilir."
            elif comm_chg < -2.0:
                pressure = "Maliyet Rahatlaması"
                commentary = f"TÜRİB {comm_name} fiyatındaki %{_tr_number(comm_chg)} gerileme, {ticker} girdi marjlarını pozitif destekler."
            else:
                commentary = f"TÜRİB {comm_name} fiyatı yatay ({comm_price} TL/kg). Operasyonel marjlar olağan seyrinde."

            company_impacts.append(
                AgriCompanyImpact(
                    ticker=ticker,
                    company_name=meta["name"],
                    stock_price=stock.price,
                    stock_change=stock.change,
                    commodity=comm_name,
                    commodity_price=comm_price,
                    commodity_change=comm_chg,
                    margin_pressure=pressure,
                    commentary=commentary,
                )
            )

        # Makro çıkarım
        macro_takeaway = (
            f"BIST Gıda Endeksi (XGIDA) {xgida.change} hareket ederken, "
            f"TÜRİB Hububat Endeksi {hububat_chg} seviyesinde. "
            f"Tarımsal emtia fiyatlarındaki yön, BIST gıda şirketlerinin 1-2 çeyrek sonraki FAVÖK marjlarına doğrudan yansıyacaktır."
        )

        return AgriBistCorrelationReport(
            date=turib_snap.date,
            xgida_price=xgida.price,
            xgida_change=xgida.change,
            turib_hububat_index=hububat_val,
            turib_hububat_change=hububat_chg,
            company_impacts=company_impacts,
            macro_takeaway=macro_takeaway,
        )
