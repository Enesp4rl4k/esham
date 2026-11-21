"""BIST Pay Geri Alımları (Share Buybacks) ve Temettü Dağıtım Takvimi Motoru.

Bu modül:
1. Şirketlerin KAP'a bildirdikleri aktif hisse geri alım programlarını (ayrılan fon, alınan lot, sermaye oranı, ortalama maliyet) takip eder.
2. BIST temettü takvimini, hisse başına net nakit temettü tutarını, temettü verimini ve hak kullanım (ex-date) tarihlerini listeler.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
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


# Geri alım ve temettü kayıtları için gerçek bir kaynak (KAP/Takasbank akışı) bağlı DEĞİL.
# Önceki sürüm elle girilmiş, kaynaksız ve "güncel fiyat" taşıyan kayıtlar içeriyordu; bunlar okura
# gerçek piyasa verisi gibi sunulamaz. Kaynak bağlanana kadar listeler boştur.
ACTIVE_BUYBACKS_DB: list[BuybackProgram] = []

DIVIDENDS_DB: list[DividendRecord] = []





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
        """JSON verilerini web/public/data altına kaydeder; kayıt yoksa dosya yazılmaz."""
        p = Path(web_data_dir)
        p.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone(timedelta(hours=3))).isoformat(timespec="seconds")

        if ACTIVE_BUYBACKS_DB:
            with open(p / "bist-buybacks.json", "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "updated_at": stamp,
                        "total_programs": len(ACTIVE_BUYBACKS_DB),
                        "total_allocated_fund_try": sum(b.authorized_fund_try for b in ACTIVE_BUYBACKS_DB),
                        "programs": [b.to_dict() for b in ACTIVE_BUYBACKS_DB],
                    },
                    f,
                    ensure_ascii=False,
                    indent=2,
                )
        else:
            log.warning("Geri alım kaydı yok (gerçek kaynak bağlı değil); bist-buybacks.json yazılmadı.")

        if DIVIDENDS_DB:
            with open(p / "bist-dividends.json", "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "updated_at": stamp,
                        "total_dividends": len(DIVIDENDS_DB),
                        "avg_yield_pct": round(sum(d.dividend_yield_pct for d in DIVIDENDS_DB) / len(DIVIDENDS_DB), 2),
                        "records": [d.to_dict() for d in DIVIDENDS_DB],
                    },
                    f,
                    ensure_ascii=False,
                    indent=2,
                )
        else:
            log.warning("Temettü kaydı yok (gerçek kaynak bağlı değil); bist-dividends.json yazılmadı.")
