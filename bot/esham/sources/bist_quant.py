"""BIST Kantitatif İstihbarat, Key Level (Destek/Direnç/Pivot/Fibonacci) ve Temel Analiz Motoru.

Bu modül:
1. Günlük OHLCV verilerinden Pivot (Classic & Fibonacci), RSI 14, 20G/50G/200G HO ve
   kısa/orta vadeli kritik destek-direnç eşiklerini (Key Levels) hesaplar.
2. Şirketin temel analiz çarpanlarını (Piyasa Değeri, F/K, PD/DD, FD/FAVÖK, Ciro, Kâr Marjı)
   ve KAP sözleşme tutarlarının yıllık ciroya göreli oranını hesaplar.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
import re
import requests

from ..config import default_headers, get_logger, settings
from ..http import retry_get

log = get_logger(__name__)

CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"


@dataclass
class KeyLevelsResult:
    ticker: str
    last_price: float
    change_pct: float
    pivot: float
    r1: float
    r2: float
    s1: float
    s2: float
    fib_382: float
    fib_500: float
    fib_618: float
    rsi_14: float
    rsi_zone: str
    sma_20: float
    sma_50: float
    support_20d: float
    resistance_20d: float
    year_high: float
    year_low: float

    @property
    def dist_to_high_pct(self) -> float:
        if self.year_high > 0:
            return round((self.last_price - self.year_high) / self.year_high * 100, 2)
        return 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "ticker": self.ticker,
            "son_fiyat": self.last_price,
            "gunluk_degisim_yuzde": self.change_pct,
            "pivot_noktasi": self.pivot,
            "direncler": {
                "r1": self.r1,
                "r2": self.r2,
                "direnc_20g": self.resistance_20d,
                "fib_618": self.fib_618,
            },
            "destekler": {
                "s1": self.s1,
                "s2": self.s2,
                "destek_20g": self.support_20d,
                "fib_382": self.fib_382,
            },
            "hareketli_ortalamalar": {
                "sma_20": self.sma_20,
                "sma_50": self.sma_50,
            },
            "rsi_14": self.rsi_14,
            "rsi_bolgesi": self.rsi_zone,
            "52h_zirve": self.year_high,
            "52h_dip": self.year_low,
            "zirveye_uzaklik_yuzde": self.dist_to_high_pct,
        }

    def format_table(self) -> str:
        sign = "+" if self.change_pct >= 0 else ""
        dist_sign = "+" if self.dist_to_high_pct >= 0 else ""
        return (
            f"### 🎯 Kurumsal Key Level & Teknik Eşikler (${self.ticker})\n"
            f"| Metrik | Seviye | Teknik Anlam / Sinyal |\n"
            f"| :--- | :--- | :--- |\n"
            f"| **Son Fiyat** | **{self.last_price:.2f} TL** | Seans Değişimi: %{sign}{self.change_pct:.2f} |\n"
            f"| **Günlük Pivot Eşiği** | **{self.pivot:.2f} TL** | Pivot Üstü: Boğa / Altı: Ayı |\n"
            f"| **Kritik Direnç (R1 / 20G)** | {self.r1:.2f} TL / {self.resistance_20d:.2f} TL | İlk Kar Satışı Bölgesi |\n"
            f"| **Kritik Destek (S1 / 20G)** | {self.s1:.2f} TL / {self.support_20d:.2f} TL | Olası Tepki Alım Tabanı |\n"
            f"| **Fibonacci %50 / %61.8** | {self.fib_500:.2f} TL / {self.fib_618:.2f} TL | Orta Vadeli Düzeltme Seviyeleri |\n"
            f"| **14G RSI** | {self.rsi_14:.1f} ({self.rsi_zone}) | Trend Gücü Göstergesi |\n"
            f"| **20G / 50G Ortalama** | {self.sma_20:.2f} TL / {self.sma_50:.2f} TL | Kısa / Orta Vade Trend Filtresi |\n"
            f"| **52H Zirve / Uzaklık** | {self.year_high:.2f} TL (%{dist_sign}{self.dist_to_high_pct:.1f}) | Dip: {self.year_low:.2f} TL |"
        )


@dataclass
class FundamentalResult:
    ticker: str
    company_name: str
    sector: str
    industry: str
    market_cap_try: float
    market_cap_str: str
    trailing_pe: float | None
    price_to_book: float | None
    ev_to_ebitda: float | None
    total_revenue_try: float | None
    revenue_str: str
    profit_margin_pct: float | None
    roe_pct: float | None
    contract_analysis: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "ticker": self.ticker,
            "sirket": self.company_name,
            "sektor": self.sector,
            "alt_sektor": self.industry,
            "piyasa_degeri_tl": self.market_cap_try,
            "piyasa_degeri_fmt": self.market_cap_str,
            "fiyat_kazanc_fk": self.trailing_pe,
            "piyasa_defter_pddd": self.price_to_book,
            "fd_favok": self.ev_to_ebitda,
            "yillik_hasilat_tl": self.total_revenue_try,
            "hasilat_fmt": self.revenue_str,
            "net_kar_marji_yuzde": self.profit_margin_pct,
            "ozsermaye_karliligi_roe": self.roe_pct,
            "sozlesme_ciro_analizi": self.contract_analysis,
        }

    def format_table(self) -> str:
        fk_str = f"{self.trailing_pe:.2f}" if self.trailing_pe else "—"
        pddd_str = f"{self.price_to_book:.2f}" if self.price_to_book else "—"
        fdfavok_str = f"{self.ev_to_ebitda:.2f}" if self.ev_to_ebitda else "—"
        margin_str = f"%{self.profit_margin_pct:.1f}" if self.profit_margin_pct else "—"
        roe_str = f"%{self.roe_pct:.1f}" if self.roe_pct else "—"

        contract_section = ""
        if self.contract_analysis:
            ca = self.contract_analysis
            contract_section = (
                f"\n\n#### 📑 Sözleşme Büyüklüğü & Ciro Etki Çarpanı\n"
                f"- **Sözleşme Tutarı:** {ca.get('sozlesme_tutari_str', '—')}\n"
                f"- **Son 12 Aylık Hasılat:** {self.revenue_str}\n"
                f"- **Ciroya Göreli Oranı:** **%{ca.get('ciro_orani_yuzde', 0.0):.1f}**\n"
                f"- **Stratejik Sınıf:** `{ca.get('tier', 'STANDART')}` ({ca.get('degerlendirme', '')})"
            )

        return (
            f"### 🏢 Temel Finansal Çarpanlar (${self.ticker})\n"
            f"| Temel Gösterge | Değer | Sektör / Açıklama |\n"
            f"| :--- | :--- | :--- |\n"
            f"| **Piyasa Değeri** | **{self.market_cap_str}** | Sektör: {self.sector or 'BIST'} |\n"
            f"| **Fiyat / Kazanç (F/K)** | {fk_str} | Piyasa Değerleme Çarpanı |\n"
            f"| **Piyasa / Defter (PD/DD)** | {pddd_str} | Özkaynak Çarpanı |\n"
            f"| **Firma Değeri / FAVÖK** | {fdfavok_str} | Operasyonel Çarpan |\n"
            f"| **Yıllık Ciro (Hasılat)** | {self.revenue_str} | Son 12 Aylık Konsolide |\n"
            f"| **Net Kâr Marjı** | {margin_str} | Kârlılık Göstergesi |\n"
            f"| **Özsermaye Kârlılığı (ROE)** | {roe_str} | Sermaye Verimliliği |"
            f"{contract_section}"
        )


def _fmt_try_money(amount: float) -> str:
    if amount >= 1_000_000_000:
        return f"{amount / 1_000_000_000:.1f} Milyar TL"
    if amount >= 1_000_000:
        return f"{amount / 1_000_000:.1f} Milyon TL"
    return f"{amount:,.0f} TL"


class BistQuantAnalyzer:
    """BIST kantitatif seviyeler ve temel analiz motoru."""

    def __init__(self) -> None:
        self.headers = default_headers()

    def get_key_levels(self, ticker: str) -> KeyLevelsResult | None:
        """Belirtilen hisse senedi için tam Key Levels (Pivot, R1-S2, Fib, RSI, HO) hesaplar."""
        clean = ticker.strip().upper().replace(".IS", "")
        symbol = f"{clean}.IS"

        try:
            url = f"{CHART_URL.format(symbol=symbol)}?range=6mo&interval=1d"
            resp = retry_get(url, headers=self.headers, timeout=settings.http_timeout)
            resp.raise_for_status()
            res = resp.json()["chart"]["result"][0]
            quotes = res["indicators"]["quote"][0]
            meta = res.get("meta", {})

            highs = [float(h) for h in quotes.get("high", []) if h is not None]
            lows = [float(l) for l in quotes.get("low", []) if l is not None]
            closes = [float(c) for c in quotes.get("close", []) if c is not None]

            if not closes or len(closes) < 15:
                return None

            last = closes[-1]
            prev = closes[-2] if len(closes) >= 2 else last
            change_pct = ((last - prev) / prev * 100) if prev else 0.0

            # 20 günlük uçlar
            n_20 = min(20, len(closes))
            support_20d = min(lows[-n_20:])
            resistance_20d = max(highs[-n_20:])
            sma_20 = sum(closes[-n_20:]) / n_20

            # 50 günlük HO
            n_50 = min(50, len(closes))
            sma_50 = sum(closes[-n_50:]) / n_50

            # Klasik Pivot Hesabı (önceki günün verileriyle)
            prev_high = highs[-2] if len(highs) >= 2 else highs[-1]
            prev_low = lows[-2] if len(lows) >= 2 else lows[-1]
            pivot = (prev_high + prev_low + prev) / 3.0
            r1 = (2.0 * pivot) - prev_low
            s1 = (2.0 * pivot) - prev_high
            r2 = pivot + (prev_high - prev_low)
            s2 = pivot - (prev_high - prev_low)

            # Fibonacci Düzeltme Seviyeleri (6 aylık aralık)
            h_max = max(highs)
            l_min = min(lows)
            diff = h_max - l_min
            fib_382 = l_min + 0.382 * diff
            fib_500 = l_min + 0.500 * diff
            fib_618 = l_min + 0.618 * diff

            # RSI 14
            deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
            gains = [max(0.0, d) for d in deltas]
            losses = [max(0.0, -d) for d in deltas]
            n_rsi = min(14, len(deltas))
            avg_gain = sum(gains[-n_rsi:]) / n_rsi if n_rsi else 0.0
            avg_loss = sum(losses[-n_rsi:]) / n_rsi if n_rsi else 0.0
            if avg_loss == 0.0:
                rsi = 100.0
            else:
                rs = avg_gain / avg_loss
                rsi = 100.0 - (100.0 / (1.0 + rs))

            if rsi >= 70:
                rsi_zone = "Aşırı Alım (>70)"
            elif rsi <= 30:
                rsi_zone = "Aşırı Satım (<30)"
            else:
                rsi_zone = "Nötr (Dengeli)"

            year_high = float(meta.get("fiftyTwoWeekHigh", 0.0) or h_max)
            year_low = float(meta.get("fiftyTwoWeekLow", 0.0) or l_min)

            return KeyLevelsResult(
                ticker=clean,
                last_price=round(last, 2),
                change_pct=round(change_pct, 2),
                pivot=round(pivot, 2),
                r1=round(r1, 2),
                r2=round(r2, 2),
                s1=round(s1, 2),
                s2=round(s2, 2),
                fib_382=round(fib_382, 2),
                fib_500=round(fib_500, 2),
                fib_618=round(fib_618, 2),
                rsi_14=round(rsi, 1),
                rsi_zone=rsi_zone,
                sma_20=round(sma_20, 2),
                sma_50=round(sma_50, 2),
                support_20d=round(support_20d, 2),
                resistance_20d=round(resistance_20d, 2),
                year_high=round(year_high, 2),
                year_low=round(year_low, 2),
            )
        except Exception as exc:
            log.warning("Key levels hesaplama hatası (%s): %s", ticker, exc)
            return None

    def get_fundamental_metrics(
        self, ticker: str, contract_amount_try: float | None = None
    ) -> FundamentalResult | None:
        """Şirketin piyasa çarpanlarını çeker ve varsa sözleşme/ciro etki çarpanını hesaplar."""
        clean = ticker.strip().upper().replace(".IS", "")
        symbol = f"{clean}.IS"

        try:
            import yfinance as yf
            t = yf.Ticker(symbol)
            info = t.info

            mcap = float(info.get("marketCap") or 0.0)
            revenue = float(info.get("totalRevenue") or 0.0)
            pe = float(info.get("forwardPE") or info.get("trailingPE") or 0.0) or None
            pb = float(info.get("priceToBook") or 0.0) or None
            ev_ebitda = float(info.get("enterpriseToEbitda") or 0.0) or None
            margin = float(info.get("profitMargins") or 0.0)
            roe = float(info.get("returnOnEquity") or 0.0)

            contract_analysis = None
            if contract_amount_try and contract_amount_try > 0:
                rev_ratio = (contract_amount_try / revenue * 100.0) if revenue > 0 else 0.0
                mcap_ratio = (contract_amount_try / mcap * 100.0) if mcap > 0 else 0.0
                is_mega = rev_ratio >= 10.0 or contract_amount_try >= 1_000_000_000

                tier = "TIER-1 (MEGA İŞ ANLAŞMASI)" if is_mega else "TIER-2 (STANDART SÖZLEŞME)"
                degerlendirme = (
                    "Hasılatın %10'undan fazlasına tekabül eden, finansalları dönüştürücü sözleşme."
                    if is_mega
                    else "Rutin operasyonel iş akışı kapsamında standart sözleşme."
                )

                contract_analysis = {
                    "sozlesme_tutari_tl": contract_amount_try,
                    "sozlesme_tutari_str": _fmt_try_money(contract_amount_try),
                    "ciro_orani_yuzde": round(rev_ratio, 2),
                    "piyasa_degeri_orani_yuzde": round(mcap_ratio, 2),
                    "tier": tier,
                    "degerlendirme": degerlendirme,
                    "is_mega": is_mega,
                }

            return FundamentalResult(
                ticker=clean,
                company_name=info.get("shortName") or info.get("longName") or clean,
                sector=info.get("sector") or "BIST",
                industry=info.get("industry") or "Hisse",
                market_cap_try=mcap,
                market_cap_str=_fmt_try_money(mcap) if mcap > 0 else "—",
                trailing_pe=round(pe, 2) if pe else None,
                price_to_book=round(pb, 2) if pb else None,
                ev_to_ebitda=round(ev_ebitda, 2) if ev_ebitda else None,
                total_revenue_try=revenue if revenue > 0 else None,
                revenue_str=_fmt_try_money(revenue) if revenue > 0 else "—",
                profit_margin_pct=round(margin * 100, 1) if margin else None,
                roe_pct=round(roe * 100, 1) if roe else None,
                contract_analysis=contract_analysis,
            )
        except Exception as exc:
            log.warning("Temel analiz verisi çekilemedi (%s): %s", ticker, exc)
            return None


def extract_contract_amount(text: str, usd_try: float = 34.2, eur_try: float = 37.1) -> float | None:
    """Metin içinden sözleşme, sipariş veya ihale tutarını (TL cinsinden) ayrıştırır."""
    if not text:
        return None

    clean_text = text.lower()

    # 1. Milyar / Milyon kalıpları: "1,5 milyar TL", "450 milyon TL", "25 milyon USD", "100 Milyon Euro"
    m = re.search(r'(\d+(?:[.,]\d+)?)\s*(milyar|milyon)\s*(tl|try|usd|dolar|\$|eur|euro|€)?', clean_text)
    if m:
        val_str = m.group(1).replace(',', '.')
        try:
            val = float(val_str)
        except ValueError:
            return None
        unit = m.group(2)
        curr = (m.group(3) or 'tl').strip()

        mult = 1_000_000_000 if 'milyar' in unit else 1_000_000
        amount = val * mult

        if curr in ('usd', 'dolar', '$'):
            amount *= usd_try
        elif curr in ('eur', 'euro', '€'):
            amount *= eur_try
        return amount

    # 2. Tam sayılar: "500.000.000 TL", "25,000,000 USD"
    m2 = re.search(r'(\d{1,3}(?:[.,]\d{3})+)\s*(tl|try|usd|dolar|\$|eur|euro|€)', clean_text)
    if m2:
        val_str = m2.group(1).replace('.', '').replace(',', '')
        try:
            val = float(val_str)
        except ValueError:
            return None
        curr = m2.group(2).strip()
        if curr in ('usd', 'dolar', '$'):
            val *= usd_try
        elif curr in ('eur', 'euro', '€'):
            val *= eur_try
        return val

    return None
