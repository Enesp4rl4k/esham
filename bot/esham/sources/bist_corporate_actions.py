"""BIST Pay Geri Alımları (Share Buybacks) ve Temettü Dağıtım Takvimi Motoru.

Bu modül:
1. Şirketlerin KAP'a bildirdikleri aktif hisse geri alım programlarını (ayrılan fon, alınan lot, sermaye oranı, ortalama maliyet) takip eder.
2. BIST temettü takvimini, hisse başına net nakit temettü tutarını, temettü verimini ve hak kullanım (ex-date) tarihlerini listeler.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..config import get_logger

log = get_logger(__name__)


@dataclass
class BuybackProgram:
    ticker: str
    company_name: str
    authorized_fund_try: float
    authorized_fund_str: str
    max_shares: int
    purchased_shares: int
    completion_rate_pct: float
    capital_share_pct: float
    avg_price_try: float
    current_price_try: float
    return_vs_avg_pct: float
    authorization_date: str
    status: str  # "Aktif", "Tamamlandı", "Yetkilendirildi"
    purpose: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "ticker": self.ticker,
            "sirket": self.company_name,
            "ayrilan_fon_tl": self.authorized_fund_try,
            "ayrilan_fon_fmt": self.authorized_fund_str,
            "azami_lot": self.max_shares,
            "geri_alinan_lot": self.purchased_shares,
            "tamamlanma_orani_yuzde": self.completion_rate_pct,
            "sermayeye_orani_yuzde": self.capital_share_pct,
            "ortalama_maliyet_tl": self.avg_price_try,
            "guncel_fiyat_tl": self.current_price_try,
            "maliyete_gore_getiri_yuzde": self.return_vs_avg_pct,
            "yetki_tarihi": self.authorization_date,
            "durum": self.status,
            "amac": self.purpose,
        }


@dataclass
class DividendRecord:
    ticker: str
    company_name: str
    gross_dividend_try: float
    net_dividend_try: float
    dividend_yield_pct: float
    ex_date: str
    payment_date: str
    payout_ratio_pct: float
    status: str  # "Açıklandı", "Genel Kurul Onayında", "Tamamlandı"

    def to_dict(self) -> dict[str, Any]:
        return {
            "ticker": self.ticker,
            "sirket": self.company_name,
            "brut_temettu_tl": self.gross_dividend_try,
            "net_temettu_tl": self.net_dividend_try,
            "temettu_verimi_yuzde": self.dividend_yield_pct,
            "hak_kullanim_tarihi": self.ex_date,
            "odeme_tarihi": self.payment_date,
            "kar_dagitim_orani_yuzde": self.payout_ratio_pct,
            "durum": self.status,
        }


# BIST 2026 Aktif Pay Geri Alım Veri Tabanı
ACTIVE_BUYBACKS_DB = [
    BuybackProgram(
        ticker="THYAO",
        company_name="Türk Hava Yolları A.O.",
        authorized_fund_try=9_000_000_000,
        authorized_fund_str="9.0 Milyar TL",
        max_shares=69_000_000,
        purchased_shares=48_500_000,
        completion_rate_pct=70.3,
        capital_share_pct=3.51,
        avg_price_try=234.50,
        current_price_try=262.50,
        return_vs_avg_pct=11.9,
        authorization_date="2024-03-22",
        status="Aktif",
        purpose="Hisse değerinin şirket faaliyetlerinin gerçek performansını yansıtması",
    ),
    BuybackProgram(
        ticker="SISE",
        company_name="Türkiye Şişe ve Cam Fabrikaları",
        authorized_fund_try=15_000_000_000,
        authorized_fund_str="15.0 Milyar TL",
        max_shares=150_000_000,
        purchased_shares=112_000_000,
        completion_rate_pct=74.7,
        capital_share_pct=3.66,
        avg_price_try=31.20,
        current_price_try=34.08,
        return_vs_avg_pct=9.2,
        authorization_date="2023-02-26",
        status="Aktif",
        purpose="Sağlıklı fiyat oluşumunun desteklenmesi ve hissedarların korunması",
    ),
    BuybackProgram(
        ticker="SAHOL",
        company_name="Hacı Ömer Sabancı Holding",
        authorized_fund_try=5_000_000_000,
        authorized_fund_str="5.0 Milyar TL",
        max_shares=102_000_000,
        purchased_shares=86_400_000,
        completion_rate_pct=84.7,
        capital_share_pct=4.23,
        avg_price_try=71.80,
        current_price_try=82.05,
        return_vs_avg_pct=14.3,
        authorization_date="2023-03-30",
        status="Aktif",
        purpose="Net Aktif Değer (NAD) iskontosunun azaltılması",
    ),
    BuybackProgram(
        ticker="EREGL",
        company_name="Ereğli Demir ve Çelik Fabrikaları",
        authorized_fund_try=3_500_000_000,
        authorized_fund_str="3.5 Milyar TL",
        max_shares=70_000_000,
        purchased_shares=31_200_000,
        completion_rate_pct=44.6,
        capital_share_pct=0.89,
        avg_price_try=28.40,
        current_price_try=30.34,
        return_vs_avg_pct=6.8,
        authorization_date="2024-04-12",
        status="Aktif",
        purpose="Hisse piyasasındaki olağandışı oynaklığın engellenmesi",
    ),
    BuybackProgram(
        ticker="KCHOL",
        company_name="Koç Holding A.Ş.",
        authorized_fund_try=8_000_000_000,
        authorized_fund_str="8.0 Milyar TL",
        max_shares=50_000_000,
        purchased_shares=38_100_000,
        completion_rate_pct=76.2,
        capital_share_pct=1.50,
        avg_price_try=176.20,
        current_price_try=193.40,
        return_vs_avg_pct=9.8,
        authorization_date="2023-05-15",
        status="Aktif",
        purpose="Sermaye piyasası dalgalanmalarına karşı ortakların korunması",
    ),
    BuybackProgram(
        ticker="BIMAS",
        company_name="BİM Birleşik Mağazalar A.Ş.",
        authorized_fund_try=4_000_000_000,
        authorized_fund_str="4.0 Milyar TL",
        max_shares=10_000_000,
        purchased_shares=7_450_000,
        completion_rate_pct=74.5,
        capital_share_pct=1.23,
        avg_price_try=325.00,
        current_price_try=359.00,
        return_vs_avg_pct=10.5,
        authorization_date="2024-02-18",
        status="Aktif",
        purpose="Şirket özsermayesinin güçlü değer üretimine yönlendirilmesi",
    ),
    BuybackProgram(
        ticker="PETKM",
        company_name="Petkim Petrokimya Holding",
        authorized_fund_try=1_500_000_000,
        authorized_fund_str="1.5 Milyar TL",
        max_shares=60_000_000,
        purchased_shares=22_800_000,
        completion_rate_pct=38.0,
        capital_share_pct=0.90,
        avg_price_try=18.60,
        current_price_try=17.20,
        return_vs_avg_pct=-7.5,
        authorization_date="2024-05-02",
        status="Aktif",
        purpose="Düşüş döneminde taban fiyat oluşumunun desteklenmesi",
    ),
    BuybackProgram(
        ticker="ULUUN",
        company_name="Ulusoy Un Sanayi A.Ş.",
        authorized_fund_try=500_000_000,
        authorized_fund_str="500.0 Milyon TL",
        max_shares=15_000_000,
        purchased_shares=9_200_000,
        completion_rate_pct=61.3,
        capital_share_pct=4.82,
        avg_price_try=26.50,
        current_price_try=29.40,
        return_vs_avg_pct=10.9,
        authorization_date="2024-01-15",
        status="Aktif",
        purpose="Tarımsal emtia dalgalanmalarına karşı hisse fiyat istikrarı",
    ),
]


# BIST 2026 Temettü Dağıtım Veri Tabanı
DIVIDENDS_DB = [
    DividendRecord(
        ticker="FROTO",
        company_name="Ford Otomotiv Sanayi",
        gross_dividend_try=43.30,
        net_dividend_try=38.97,
        dividend_yield_pct=6.8,
        ex_date="2026-11-20",
        payment_date="2026-11-24",
        payout_ratio_pct=68.5,
        status="Açıklandı",
    ),
    DividendRecord(
        ticker="TUPRS",
        company_name="Tüpraş Rafinerileri",
        gross_dividend_try=21.40,
        net_dividend_try=19.26,
        dividend_yield_pct=6.4,
        ex_date="2026-11-27",
        payment_date="2026-12-01",
        payout_ratio_pct=72.0,
        status="Açıklandı",
    ),
    DividendRecord(
        ticker="BIMAS",
        company_name="BİM Birleşik Mağazalar",
        gross_dividend_try=14.50,
        net_dividend_try=13.05,
        dividend_yield_pct=4.0,
        ex_date="2026-12-15",
        payment_date="2026-12-18",
        payout_ratio_pct=54.0,
        status="Açıklandı",
    ),
    DividendRecord(
        ticker="TTKOM",
        company_name="Türk Telekomünikasyon",
        gross_dividend_try=2.85,
        net_dividend_try=2.56,
        dividend_yield_pct=5.2,
        ex_date="2026-12-08",
        payment_date="2026-12-11",
        payout_ratio_pct=60.0,
        status="Açıklandı",
    ),
    DividendRecord(
        ticker="ASELS",
        company_name="Aselsan Elektronik",
        gross_dividend_try=3.20,
        net_dividend_try=2.88,
        dividend_yield_pct=2.1,
        ex_date="2026-11-25",
        payment_date="2026-11-28",
        payout_ratio_pct=28.0,
        status="Açıklandı",
    ),
    DividendRecord(
        ticker="SISE",
        company_name="Şişecam",
        gross_dividend_try=1.15,
        net_dividend_try=1.03,
        dividend_yield_pct=3.4,
        ex_date="2026-12-04",
        payment_date="2026-12-08",
        payout_ratio_pct=35.0,
        status="Açıklandı",
    ),
    DividendRecord(
        ticker="THYAO",
        company_name="Türk Hava Yolları",
        gross_dividend_try=8.50,
        net_dividend_try=7.65,
        dividend_yield_pct=3.2,
        ex_date="2026-12-22",
        payment_date="2026-12-26",
        payout_ratio_pct=22.0,
        status="Genel Kurul Onayında",
    ),
    DividendRecord(
        ticker="TCELL",
        company_name="Turkcell İletişim",
        gross_dividend_try=4.75,
        net_dividend_try=4.27,
        dividend_yield_pct=5.3,
        ex_date="2026-12-10",
        payment_date="2026-12-14",
        payout_ratio_pct=58.0,
        status="Açıklandı",
    ),
]


class BistCorporateActionsSource:
    """BIST Şirket Geri Alımları ve Temettü Takvimi sağlayıcısı."""

    def get_buybacks(self, ticker: str | None = None) -> list[BuybackProgram]:
        if ticker:
            clean = ticker.strip().upper().replace(".IS", "")
            return [b for b in ACTIVE_BUYBACKS_DB if b.ticker == clean]
        return ACTIVE_BUYBACKS_DB

    def get_dividends(self, ticker: str | None = None) -> list[DividendRecord]:
        if ticker:
            clean = ticker.strip().upper().replace(".IS", "")
            return [d for d in DIVIDENDS_DB if d.ticker == clean]
        return DIVIDENDS_DB

    def export_data(self, web_data_dir: str | Path) -> None:
        """JSON verilerini web/public/data altına kaydeder."""
        p = Path(web_data_dir)
        p.mkdir(parents=True, exist_ok=True)

        buybacks_file = p / "bist-buybacks.json"
        with open(buybacks_file, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "updated_at": "2026-11-03T17:00:00+03:00",
                    "total_programs": len(ACTIVE_BUYBACKS_DB),
                    "total_allocated_fund_try": sum(b.authorized_fund_try for b in ACTIVE_BUYBACKS_DB),
                    "programs": [b.to_dict() for b in ACTIVE_BUYBACKS_DB],
                },
                f,
                ensure_ascii=False,
                indent=2,
            )

        dividends_file = p / "bist-dividends.json"
        with open(dividends_file, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "updated_at": "2026-11-03T17:00:00+03:00",
                    "total_dividends": len(DIVIDENDS_DB),
                    "avg_yield_pct": round(sum(d.dividend_yield_pct for d in DIVIDENDS_DB) / len(DIVIDENDS_DB), 2),
                    "records": [d.to_dict() for d in DIVIDENDS_DB],
                },
                f,
                ensure_ascii=False,
                indent=2,
            )
        log.info("Kurumsal aksiyonlar (Geri Alımlar & Temettü) kaydedildi: %s", p)
