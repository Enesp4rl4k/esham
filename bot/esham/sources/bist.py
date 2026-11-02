"""BIST endeks özeti kaynağı.

Yahoo Finance'in kırılgan HTML'i yerine dayanıklı JSON chart API'si kullanılır:
`query1.finance.yahoo.com/v8/finance/chart/XU100.IS`. Hata durumunda örnek veriyle
zarifçe geri dönülür.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import requests

from ..config import default_headers, get_logger, settings
from ..formatting import tr_money as _tr_volume
from ..formatting import tr_number as _tr_number
from ..http import retry_get
from . import MarketSummary

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
    closes: list[float] = field(default_factory=list)

    def format_line(self) -> str:
        sign = "+" if self.change_pct >= 0 else ""
        return (
            f"📊 **Teknik Görünüm (${self.ticker}):** "
            f"Fiyat: `{self.last_price:.2f} TL` (%{sign}{self.change_pct:.2f}) | "
            f"14G RSI: `{self.rsi_14:.1f}` ({self.rsi_zone}) | "
            f"20G HO: `{self.sma_20:.2f} TL` | "
            f"Destek: `{self.support:.2f} TL` | "
            f"Direnç: `{self.resistance:.2f} TL`"
        )

CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"


class BistSource:
    def __init__(self, symbol: str = "XU100.IS") -> None:
        self.symbol = symbol
        self.headers = default_headers()

    def market_summary(self) -> MarketSummary:
        try:
            resp = retry_get(
                CHART_URL.format(symbol=self.symbol),
                headers=self.headers,
                timeout=settings.http_timeout,
            )
            resp.raise_for_status()
            summary = self._parse(resp.json())
            if summary:
                return summary
            log.warning("BIST verisi ayrıştırılamadı; örnek veri kullanılıyor.")
        except (requests.RequestException, ValueError) as exc:
            log.warning("BIST verisi alınamadı (%s); örnek veri kullanılıyor.", exc)
        return self._sample()

    def _parse(self, payload: dict) -> MarketSummary | None:
        try:
            meta = payload["chart"]["result"][0]["meta"]
        except (KeyError, IndexError, TypeError):
            return None

        price = meta.get("regularMarketPrice")
        prev = meta.get("chartPreviousClose") or meta.get("previousClose")
        if price is None:
            return None

        change = ""
        if prev:
            pct = (price - prev) / prev * 100
            change = f"{'+' if pct >= 0 else ''}{_tr_number(pct, 2)}%"

        volume = (
            meta.get("regularMarketVolume")
            or meta.get("regularMarketDayVolume")
            or meta.get("averageDailyVolume10Day")
        )
        index = meta.get("symbol", self.symbol).replace(".IS", "")
        return MarketSummary(
            index=index,
            price=_tr_number(float(price)),
            change=change,
            volume=_tr_volume(float(volume)) if volume else "—",
        )

    def _sample(self) -> MarketSummary:
        return MarketSummary(
            index="XU100",
            price="10.450,23",
            change="+1,2%",
            volume="120 Milyar TL",
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
        closes = source.fetch_closes(range_str="3mo", interval="1d")
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
            closes=closes,
        )
