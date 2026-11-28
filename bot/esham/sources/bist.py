"""BIST endeks özeti kaynağı.

Yahoo Finance'in kırılgan HTML'i yerine dayanıklı JSON chart API'si kullanılır:
`query1.finance.yahoo.com/v8/finance/chart/XU100.IS`. Hata durumunda örnek veriyle
zarifçe geri dönülür.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

import math

import requests

from ..config import default_headers, get_logger, settings
from ..formatting import tr_number as _tr_number
from ..formatting import tr_pct
from ..http import retry_get, retry_post
from . import MarketSummary
from .bars import PeriodChange, daily_bars, period_change, session_info

log = get_logger(__name__)


@dataclass
class TechnicalSnapshot:
    ticker: str
    last_price: float
    change_pct: float
    rsi_14: float
    rsi_zone: str  # "Aşırı Alım (>70)", "Aşırı Satım (<30)", "Nötr"
    sma_20: float
    sma_50: float
    trend: str     # "20G HO Üzerinde", "20G HO Altında"
    support: float
    resistance: float
    year_high: float = 0.0
    year_low: float = 0.0
    closes: list[float] = field(default_factory=list)

    @property
    def dist_to_high(self) -> float:
        if self.year_high > 0:
            return round((self.last_price - self.year_high) / self.year_high * 100, 2)
        return 0.0

    def format_line(self) -> str:
        sign = "+" if self.change_pct >= 0 else ""
        return (
            f"**Teknik Görünüm (${self.ticker}):** "
            f"Fiyat: `{self.last_price:.2f} TL` (%{sign}{self.change_pct:.2f}) | "
            f"14G RSI: `{self.rsi_14:.1f}` ({self.rsi_zone}) | "
            f"20G HO: `{self.sma_20:.2f} TL` | "
            f"Destek: `{self.support:.2f} TL` | "
            f"Direnç: `{self.resistance:.2f} TL`"
        )

    def format_table(self) -> str:
        sign = "+" if self.change_pct >= 0 else ""
        dist_str = f"%{self.dist_to_high:+.1f}" if self.year_high > 0 else "—"
        high_low_str = f"Zirve: {self.year_high:.2f} TL / Dip: {self.year_low:.2f} TL" if self.year_high > 0 else "—"
        return (
            f"### Kurumsal Teknik İstihbarat (${self.ticker})\n"
            f"| Gösterge | Değer | Sinyal / Yorum |\n"
            f"| :--- | :--- | :--- |\n"
            f"| **Son Fiyat** | **{self.last_price:.2f} TL** | Günlük Değişim: %{sign}{self.change_pct:.2f} |\n"
            f"| **14G Göreceli Güç (RSI)** | **{self.rsi_14:.1f}** | {self.rsi_zone} Bölgesi |\n"
            f"| **20 Günlük HO** | {self.sma_20:.2f} TL | {self.trend} |\n"
            f"| **50 Günlük HO** | {self.sma_50:.2f} TL | Orta Vadeli Trend Desteği |\n"
            f"| **Kısa Vadeli Destek** | {self.support:.2f} TL | 20 Günlük Dip Tabanı |\n"
            f"| **Kısa Vadeli Direnç** | {self.resistance:.2f} TL | 20 Günlük Zirve Tavanı |\n"
            f"| **52H Zirveye Uzaklık** | {dist_str} | {high_low_str} |"
        )

CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
TV_SCAN_URL = "https://scanner.tradingview.com/turkey/scan"


def _finite(x: object) -> bool:
    """Sayı ve sonlu mu (None, NaN, inf, metin → False)."""
    try:
        return x is not None and math.isfinite(float(x))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return False


class BistSource:
    def __init__(self, symbol: str = "XU100.IS") -> None:
        self.symbol = symbol
        self.headers = default_headers()

    def _tv_ticker(self, symbol: str) -> str:
        clean = symbol.replace(".IS", "").strip().upper()
        if not clean.startswith("BIST:"):
            return f"BIST:{clean}"
        return clean

    def market_summary(self) -> MarketSummary | None:
        """Endeks özeti. Fiyat ve zaman damgası AYNI kaynaktan gelir (kaynak karışımı yok):

        1. Yahoo chart (5 gün/günlük): değer, açılış, önceki kapanış (``closes[-2]``), son işlem zamanı
           (``regularMarketTime``) ve seans durumu aynı yanıttan. Ücretsiz BIST verisi ~15 dk gecikmelidir;
           şablonlar bunu yazar (``market_text.DELAY_NOTE``).
        2. Yahoo yoksa TradingView taraması: değerler var ama yanıt işlem zamanı VERMEZ → ``as_of=None``;
           tarih gerektiren cümleler yazılmaz (tahminle "bugün" denmez).
        """
        yahoo_payload = self._yahoo_chart("5d", "1d")
        if yahoo_payload is not None:
            summary = self._parse_yahoo(yahoo_payload)
            if summary:
                summary = self._with_session(summary, yahoo_payload)
                if summary.as_of is not None:
                    return summary
                log.warning("Yahoo BIST yanıtında işlem zamanı yok; TradingView deneniyor.")
            else:
                log.warning("BIST Yahoo verisi ayrıştırılamadı; TradingView deneniyor.")

        try:
            tv_sym = self._tv_ticker(self.symbol)
            resp = retry_post(
                TV_SCAN_URL,
                json={
                    "symbols": {"tickers": [tv_sym]},
                    "columns": ["name", "close", "change", "open", "high", "low", "volume"],
                },
                headers=self.headers,
                timeout=settings.http_timeout,
            )
            resp.raise_for_status()
            summary = self._parse_tv(resp.json(), tv_sym)
            if summary:
                return summary  # as_of=None: zaman damgası başka kaynaktan EKLENMEZ
            log.warning("TradingView BIST verisi ayrıştırılamadı.")
        except Exception as exc:
            log.warning("TradingView BIST verisi alınamadı (%s).", exc)
        log.error("BIST verisi hiçbir resmi kaynaktan alınamadı; yapay veri üretilmiyor.")
        return None

    def _yahoo_chart(self, range_str: str, interval: str) -> dict | None:
        try:
            resp = retry_get(
                f"{CHART_URL.format(symbol=self.symbol)}?range={range_str}&interval={interval}",
                headers=self.headers,
                timeout=settings.http_timeout,
            )
            resp.raise_for_status()
            return resp.json()
        except (requests.RequestException, ValueError) as exc:
            log.warning("Yahoo chart verisi alınamadı (%s, %s): %s", self.symbol, range_str, exc)
            return None

    @staticmethod
    def _with_session(summary: MarketSummary, payload: dict | None, now: datetime | None = None) -> MarketSummary:
        """Son işlem zamanını ve seans durumunu Yahoo meta'sından ekler (yoksa None bırakır)."""
        try:
            meta = payload["chart"]["result"][0]["meta"] if payload else None
        except (KeyError, IndexError, TypeError):
            meta = None
        if isinstance(meta, dict):
            summary.as_of, summary.market_open = session_info(meta, now)
        return summary

    def weekly_change(self) -> PeriodChange | None:
        """Son kapanışın, son barın haftasından önceki son işlem günü kapanışına göre değişimi."""
        payload = self._yahoo_chart("1mo", "1d")
        try:
            result = payload["chart"]["result"][0] if payload else None
        except (KeyError, IndexError, TypeError):
            result = None
        return period_change(daily_bars(result), "1w") if result else None

    def _parse_tv(self, payload: dict, tv_sym: str) -> MarketSummary | None:
        rows = {r["s"]: r["d"] for r in payload.get("data", []) if "s" in r and "d" in r}
        row = rows.get(tv_sym)
        if not row or len(row) < 3:
            return None
        name, close, change_pct = row[0], row[1], row[2]
        open_val = row[3] if len(row) > 3 else None
        high_val = row[4] if len(row) > 4 else None
        low_val = row[5] if len(row) > 5 else None
        volume = row[6] if len(row) > 6 else None

        if not _finite(close):
            return None

        chg = float(change_pct) if _finite(change_pct) else None  # NaN/None → değişim bilinmiyor
        open_pct: float | None = None
        if open_val is not None and chg is not None:
            try:
                prev_close = float(close) / (1.0 + (chg / 100.0))
                if prev_close > 0:
                    open_pct = (float(open_val) - prev_close) / prev_close * 100.0
            except ZeroDivisionError:
                pass

        return MarketSummary(
            index=name or self.symbol.replace(".IS", ""),
            price=_tr_number(float(close)),
            change=tr_pct(chg) if chg is not None else "",
            volume=_tr_number(float(volume) / 1e9, 1) + " milyar" if volume else "",
            open_price=_tr_number(float(open_val)) if open_val is not None else "",
            open_change=tr_pct(open_pct) if open_pct is not None else "",
            high=_tr_number(float(high_val)) if high_val is not None else "",
            low=_tr_number(float(low_val)) if low_val is not None else "",
            price_value=float(close),
            change_pct=chg,
            open_value=float(open_val) if open_val is not None else None,
            open_change_pct=open_pct,
        )

    def _parse_yahoo(self, payload: dict) -> MarketSummary | None:
        try:
            res = payload["chart"]["result"][0]
            meta = res["meta"]
            quotes = res.get("indicators", {}).get("quote", [{}])[0]
        except (KeyError, IndexError, TypeError):
            return None

        price = meta.get("regularMarketPrice")
        if not _finite(price):
            return None

        # Yahoo'nun bayat 'previousClose' meta alanı yerine 5 günlük mumların sondan bir öncekini (closes[-2]) kullan
        raw_closes = quotes.get("close", [])
        valid_closes = [float(c) for c in raw_closes if _finite(c)]
        prev = None
        if len(valid_closes) >= 2:
            prev = valid_closes[-2]
        if prev is None or prev <= 0:
            prev = meta.get("chartPreviousClose") or meta.get("previousClose")

        pct: float | None = None
        if prev and prev > 0:
            pct = (float(price) - float(prev)) / float(prev) * 100

        raw_opens = quotes.get("open", [])
        valid_opens = [float(o) for o in raw_opens if _finite(o)]
        open_val = valid_opens[-1] if valid_opens else meta.get("regularMarketOpen")
        open_pct: float | None = None
        if open_val is not None and prev and prev > 0:
            open_pct = (float(open_val) - float(prev)) / float(prev) * 100

        volume = meta.get("regularMarketVolume") or meta.get("regularMarketDayVolume")
        index = meta.get("symbol", self.symbol).replace(".IS", "")
        return MarketSummary(
            index=index,
            price=_tr_number(float(price)),
            change=tr_pct(pct) if pct is not None else "",
            volume=_tr_number(float(volume) / 1e9, 1) + " milyar" if volume else "",
            open_price=_tr_number(float(open_val)) if open_val is not None else "",
            open_change=tr_pct(open_pct) if open_pct is not None else "",
            price_value=float(price),
            change_pct=pct,
            open_value=float(open_val) if open_val is not None else None,
            open_change_pct=open_pct,
        )

    def fetch_closes(self, range_str: str = "1d", interval: str = "15m") -> list[float] | None:
        """Ham kapanış fiyat serisini döner (kart sparkline'ı gibi hafif kullanımlar için).

        `generate_chart_image` ile aynı veri kaynağını paylaşır; None değerler filtrelenir.
        """
        try:
            url = f"{CHART_URL.format(symbol=self.symbol)}?range={range_str}&interval={interval}"
            resp = retry_get(url, headers=self.headers, timeout=settings.http_timeout)
            resp.raise_for_status()
            result = resp.json()["chart"]["result"][0]
            closes = result["indicators"]["quote"][0].get("close", [])
            valid = [c for c in closes if c is not None]
            return valid or None
        except (requests.RequestException, ValueError, KeyError, IndexError, TypeError) as exc:
            log.warning("Fiyat serisi alınamadı (%s).", exc)
            return None

    @classmethod
    def fetch_technical_snapshot(cls, ticker: str) -> TechnicalSnapshot | None:
        """Belirtilen hisse senedi veya endeks için teknik analiz verilerini çeker ve hesaplar."""
        clean_ticker = ticker.strip().upper()
        if not clean_ticker:
            return None
        
        symbol = clean_ticker if (clean_ticker.endswith(".IS") or clean_ticker.startswith("^") or "=" in clean_ticker) else f"{clean_ticker}.IS"
        source = cls(symbol=symbol)
        
        # Meta verisini ve kapanışları tek çağrıda al
        year_high = 0.0
        year_low = 0.0
        closes: list[float] = []
        try:
            url = f"{CHART_URL.format(symbol=source.symbol)}?range=3mo&interval=1d"
            resp = retry_get(url, headers=source.headers, timeout=settings.http_timeout)
            resp.raise_for_status()
            res = resp.json()["chart"]["result"][0]
            meta = res.get("meta", {})
            year_high = float(meta.get("fiftyTwoWeekHigh", 0.0) or 0.0)
            year_low = float(meta.get("fiftyTwoWeekLow", 0.0) or 0.0)
            raw_closes = res["indicators"]["quote"][0].get("close", [])
            closes = [float(c) for c in raw_closes if c is not None]
        except Exception as exc:
            log.warning("Teknik snapshot verisi çekilemedi (%s): %s", symbol, exc)
            return None

        if not closes or len(closes) < 15:
            return None
        
        last_price = closes[-1]
        prev_close = closes[-2] if len(closes) >= 2 else last_price
        change_pct = ((last_price - prev_close) / prev_close * 100) if prev_close else 0.0

        n_20 = min(20, len(closes))
        sma_20 = sum(closes[-n_20:]) / n_20
        n_50 = min(50, len(closes))
        sma_50 = sum(closes[-n_50:]) / n_50
        trend = "20G HO Üzerinde (Pozitif)" if last_price >= sma_20 else "20G HO Altında (Düzeltme)"

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
            rsi_zone = "Aşırı Alım"
        elif rsi <= 30:
            rsi_zone = "Aşırı Satım"
        else:
            rsi_zone = "Nötr"

        support = min(closes[-n_20:])
        resistance = max(closes[-n_20:])

        return TechnicalSnapshot(
            ticker=clean_ticker.replace(".IS", ""),
            last_price=round(last_price, 2),
            change_pct=round(change_pct, 2),
            rsi_14=round(rsi, 1),
            rsi_zone=rsi_zone,
            sma_20=round(sma_20, 2),
            sma_50=round(sma_50, 2),
            trend=trend,
            support=round(support, 2),
            resistance=round(resistance, 2),
            year_high=round(year_high, 2),
            year_low=round(year_low, 2),
            closes=closes,
        )
