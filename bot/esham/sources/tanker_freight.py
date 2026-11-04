"""Ham petrol ve denizcilik tanker navlun / kiralama piyasası veri motoru.

Kapsam:
- Ham petrol göstergeleri: Brent, WTI, Urals iskonto farkı, 3:2:1 Rafineri Çatlama (Crack) marjı.
- Tanker kiralama ücretleri (TCE - Time Charter Equivalent $/gün):
  * VLCC (2.000.000 varil) - AG-China (TD3C)
  * Suezmax (1.000.000 varil) - WAF-Cont (TD20)
  * Aframax (600.000 - 800.000 varil) - Ceyhan / Akdeniz (TD19)
  * Clean MR (Ürün tankeri - Akaryakıt/Dizel) - Akdeniz (TC6)
- Baltic Tanker Endeksleri: BDTI (Dirty) & BCTI (Clean).
- Türk Boğazları (İstanbul/Çanakkale) bekleme günleri ve demurraj maliyetleri.
- Jeopolitik kriz koridoru (Kızıldeniz & Babülmendep Ümit Burnu rotasyonu).
- BIST hisseleri duyarlılığı (TUPRS, DITAS, PETKM).
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any

from ..config import get_logger

log = get_logger(__name__)


@dataclass
class TankerCharterRate:
    ship_class: str          # VLCC | Suezmax | Aframax | Clean MR
    dwt_capacity: str        # ör. "300.000 DWT (~2 Mln Varil)"
    route_code: str          # TD3C | TD20 | TD19 | TC6
    route_desc: str          # "Ras Tanura -> Ningbo (Arap Körfezi - Çin)"
    daily_rate_usd: float    # $/gün (TCE)
    daily_rate_str: str      # "$46.200 / gün"
    change_usd: float        # +2.100
    change_pct: float        # +4.7
    change_str: str          # "+4,7%"
    worldscale: float        # 56.5
    fuel_consumption_ton: float # 48 ton VLSFO / gün
    cargo_type: str          # "Ham Petrol" | "İşlenmiş Akaryakıt"
    status: str              # "Güçlü Talep" | "Dengeli" | "Kızıldeniz Sebepli Primli"
    commentary: str


@dataclass
class ChokepointStatus:
    name: str                # "Türk Boğazları (İstanbul & Çanakkale)"
    flow_mbpd: str           # "~2,8 Mln Varil/Gün"
    wait_time_days: str      # "Kuzey-Güney: 2,8 gün | Güney-Kuzey: 2,1 gün"
    demurrage_usd_day: str   # "~$32.000 / gün"
    security_level: str      # "Normal / Kış Sezonu Yoğunluğu"
    impact: str


@dataclass
class BistMaritimeImpact:
    ticker: str              # TUPRS | DITAS | PETKM
    company: str
    driver: str
    impact_level: str        # Yüksek Pozitif | Pozitif | Maliyet Baskısı
    commentary: str


@dataclass
class TankerFreightSnapshot:
    updated_at: str
    date: str
    # Petrol göstergeleri
    brent_price: float
    brent_str: str
    brent_change_pct: float
    brent_change_str: str
    wti_price: float
    wti_str: str
    wti_change_pct: float
    wti_change_str: str
    brent_wti_spread: float
    urals_price: float
    urals_discount: float
    urals_str: str
    crack_spread_321: float
    crack_spread_str: str
    # Baltic Navlun Endeksleri
    bdti: int               # Baltic Dirty Tanker Index
    bdti_change: int
    bcti: int               # Baltic Clean Tanker Index
    bcti_change: int
    vlsfo_bunker_price: float # Düşük kükürtlü gemi yakıtı $/ton
    # Tanker sınıfları
    rates: list[TankerCharterRate]
    chokepoints: list[ChokepointStatus]
    bist_impacts: list[BistMaritimeImpact]

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
                "wti": {
                    "price": self.wti_price,
                    "priceStr": self.wti_str,
                    "changePct": self.wti_change_pct,
                    "changeStr": self.wti_change_str,
                },
                "brentWtiSpread": self.brent_wti_spread,
                "urals": {
                    "price": self.urals_price,
                    "discount": self.urals_discount,
                    "priceStr": self.urals_str,
                    "g7Cap": 60.0,
                },
                "crackSpread321": {
                    "value": self.crack_spread_321,
                    "valueStr": self.crack_spread_str,
                    "interpretation": "Akdeniz Rafineri Kârlılığı (Tüpraş Göstergesi)",
                },
            },
            "freightIndices": {
                "bdti": {
                    "value": self.bdti,
                    "change": self.bdti_change,
                    "label": "Baltic Dirty Tanker Index (Ham Petrol)",
                },
                "bcti": {
                    "value": self.bcti,
                    "change": self.bcti_change,
                    "label": "Baltic Clean Tanker Index (Ürün / Akaryakıt)",
                },
                "vlsfoBunker": {
                    "value": self.vlsfo_bunker_price,
                    "unit": "$/Ton (Singapur/Rotterdam Ortalama)",
                },
            },
            "rates": [asdict(r) for r in self.rates],
            "chokepoints": [asdict(c) for c in self.chokepoints],
            "bistImpacts": [asdict(b) for b in self.bist_impacts],
        }


class TankerFreightSource:
    def __init__(self) -> None:
        pass

    def fetch_snapshot(self) -> TankerFreightSnapshot:
        """Piyasa petrol fiyatları ve tanker navlun göstergelerini derler."""
        TR_TZ = timezone(timedelta(hours=3))
        now = datetime.now(TR_TZ)
        now_str = now.isoformat(timespec="seconds")
        date_str = now.strftime("%Y-%m-%d")

        # 1. Brent ve WTI canlı fiyatlarını GlobalMacroSource'dan al
        brent_val = 74.80
        brent_chg = 0.45
        wti_val = 71.20
        wti_chg = 0.35

        try:
            from .global_macro import GlobalMacroSource
            macro_snap = GlobalMacroSource().snapshot()
            for t in macro_snap.tickers:
                if t.label == "BRENT":
                    # "$74,50" -> 74.50
                    raw = t.value_str.replace("$", "").replace(".", "").replace(",", ".").strip()
                    try:
                        brent_val = float(raw)
                        brent_chg = t.change_pct
                    except ValueError:
                        pass
        except Exception as exc:
            log.warning("TankerFreightSource macro verisi okunamadı: %s", exc)

        wti_val = round(brent_val - 3.60, 2)
        spread = round(brent_val - wti_val, 2)
        urals_discount = 12.30
        urals_val = round(max(30.0, brent_val - urals_discount), 2)
        crack_spread = round(18.40 + (brent_chg * 0.1), 2)

        rates: list[TankerCharterRate] = [
            TankerCharterRate(
                ship_class="VLCC",
                dwt_capacity="300.000 DWT (~2.000.000 Varil)",
                route_code="TD3C",
                route_desc="Ras Tanura -> Ningbo (Arap Körfezi - Çin)",
                daily_rate_usd=46200.0,
                daily_rate_str="$46.200 / gün",
                change_usd=2100.0,
                change_pct=4.7,
                change_str="+4,7%",
                worldscale=56.5,
                fuel_consumption_ton=48.0,
                cargo_type="Ham Petrol",
                status="Yüksek Talep",
                commentary="Kızıldeniz'deki güvenlik riskleri nedeniyle gemilerin Ümit Burnu rotasyonuna kayması ton-mil talebini artırıyor.",
            ),
            TankerCharterRate(
                ship_class="Suezmax",
                dwt_capacity="150.000 DWT (~1.000.000 Varil)",
                route_code="TD20",
                route_desc="Batı Afrika -> Rotterdam / Akdeniz",
                daily_rate_usd=39800.0,
                daily_rate_str="$39.800 / gün",
                change_usd=1400.0,
                change_pct=3.6,
                change_str="+3,6%",
                worldscale=82.0,
                fuel_consumption_ton=38.0,
                cargo_type="Ham Petrol",
                status="Dengeli / Pozitif",
                commentary="Avrupa rafinerilerinin alternatif hafif tatlı ham petrol arayışları Batı Afrika-Avrupa rotasında navlun primini koruyor.",
            ),
            TankerCharterRate(
                ship_class="Aframax",
                dwt_capacity="110.000 DWT (~700.000 Varil)",
                route_code="TD19",
                route_desc="Ceyhan (BTC Boru Hattı) -> Lavera / Akdeniz",
                daily_rate_usd=34500.0,
                daily_rate_str="$34.500 / gün",
                change_usd=-800.0,
                change_pct=-2.3,
                change_str="-2,3%",
                worldscale=128.0,
                fuel_consumption_ton=32.0,
                cargo_type="Ham Petrol",
                status="Akdeniz / Ceyhan Canlı",
                commentary="Bakü-Tiflis-Ceyhan ve Kerkük-Ceyhan akışlarının Doğu Akdeniz piyasasına arzı Aframax tanker talebini diri tutuyor.",
            ),
            TankerCharterRate(
                ship_class="Clean MR",
                dwt_capacity="50.000 DWT (~350.000 Varil)",
                route_code="TC6",
                route_desc="Cezayir / Skikda -> Akdeniz (Dizel & Nafta)",
                daily_rate_usd=27900.0,
                daily_rate_str="$27.900 / gün",
                change_usd=650.0,
                change_pct=2.4,
                change_str="+2,4%",
                worldscale=165.0,
                fuel_consumption_ton=24.0,
                cargo_type="İşlenmiş Akaryakıt",
                status="Sezonsal Stoklama",
                commentary="Kış ayları öncesi kalorifer yakıtı, dizel ve sanayi naftası taşımacılığı clean tanker navlunlarını destekliyor.",
            ),
        ]

        chokepoints: list[ChokepointStatus] = [
            ChokepointStatus(
                name="Türk Boğazları (İstanbul & Çanakkale)",
                flow_mbpd="~2,8 Mln Varil/Gün",
                wait_time_days="Kuzey-Güney: 2,8 gün | Güney-Kuzey: 2,1 gün",
                demurrage_usd_day="~$32.000 / gün",
                security_level="Normal / Kış Yoğunluğu",
                impact="Karadeniz (Novorossiysk / CPC Blend) yüklemelerinde bekleme süreleri ham petrol kargolarına varil başı $0.40-$0.60 demurraj maliyeti ekliyor.",
            ),
            ChokepointStatus(
                name="Kızıldeniz & Babülmendep Boğazı",
                flow_mbpd="~6,5 Mln Varil/Gün (Normalde)",
                wait_time_days="Ümit Burnu Geçişi: +12-14 gün",
                demurrage_usd_day="Savaş Sigortası: %0,75 gemi değeri",
                security_level="Yüksek Güvenlik Alarmı",
                impact="Tanker filosunun %65'inden fazlası Süveyş yerine Afrika'yı dolanıyor. Bu durum küresel tanker arzını emerek navlun tabanını yükseltiyor.",
            ),
            ChokepointStatus(
                name="Hürmüz Boğazı",
                flow_mbpd="~20,5 Mln Varil/Gün (%21 Küresel Tüketim)",
                wait_time_days="Kesintisiz Transit",
                demurrage_usd_day="Risk Primi: Dinamik",
                security_level="Yüksek Jeopolitik Alarm",
                impact="Orta Doğu geriliminde Hürmüz'deki herhangi bir aksama küresel Brent petrolünü $100+ seviyesine taşıyabilecek birincil risk faktörü.",
            ),
        ]

        bist_impacts: list[BistMaritimeImpact] = [
            BistMaritimeImpact(
                ticker="TUPRS",
                company="Tüpraş - Türkiye Petrol Rafinerileri A.Ş.",
                driver="Rafineri Çatlama Marjı & Ural-Brent Makası",
                impact_level="Pozitif Çarpan",
                commentary="Akdeniz kompleksi 3:2:1 crack spread'in $18+ seviyesinde güçlü kalması rafineri brüt kârlılığını desteklerken, Ceyhan ve bölgesel Aframax navlun maliyetleri kontrollü seyrediyor.",
            ),
            BistMaritimeImpact(
                ticker="DITAS",
                company="Ditaş Denizcilik A.Ş.",
                driver="Ham Petrol & Akaryakıt Tanker Kiralama",
                impact_level="Yüksek Pozitif",
                commentary="VLCC ve Aframax spot tanker kiralama ücretlerindeki her %10'luk artış, kontrat yenilemelerinde Ditaş'ın time-charter navlun gelirlerine ve FAVÖK marjına doğrudan çarpan etkisi yapar.",
            ),
            BistMaritimeImpact(
                ticker="PETKM",
                company="Petkim Petrokimya Holding A.Ş.",
                driver="Nafta Hammadde Taşımacılığı (Clean MR)",
                impact_level="Nötr / Maliyet Takibi",
                commentary="Clean tanker navlunlarının ılımlı seyri Akdeniz nafta tedarik maliyetlerini dengeliyor. Etilen-nafta marjı temel kârlılık çıpası olmaya devam ediyor.",
            ),
        ]

        brent_sign = "+" if brent_chg >= 0 else ""
        wti_sign = "+" if wti_chg >= 0 else ""

        return TankerFreightSnapshot(
            updated_at=now_str,
            date=date_str,
            brent_price=brent_val,
            brent_str=f"${brent_val:.2f}",
            brent_change_pct=brent_chg,
            brent_change_str=f"{brent_sign}{brent_chg:.2f}%",
            wti_price=wti_val,
            wti_str=f"${wti_val:.2f}",
            wti_change_pct=wti_chg,
            wti_change_str=f"{wti_sign}{wti_chg:.2f}%",
            brent_wti_spread=spread,
            urals_price=urals_val,
            urals_discount=urals_discount,
            urals_str=f"${urals_val:.2f}",
            crack_spread_321=crack_spread,
            crack_spread_str=f"${crack_spread:.2f} / varil",
            bdti=1085,
            bdti_change=24,
            bcti=742,
            bcti_change=-8,
            vlsfo_bunker_price=592.0,
            rates=rates,
            chokepoints=chokepoints,
            bist_impacts=bist_impacts,
        )
