"""BIST endeks özeti kaynağı.

Yahoo Finance'in kırılgan HTML'i yerine dayanıklı JSON chart API'si kullanılır:
`query1.finance.yahoo.com/v8/finance/chart/XU100.IS`. Hata durumunda örnek veriyle
zarifçe geri dönülür.
"""
from __future__ import annotations

import requests

from ..config import default_headers, get_logger, settings
from ..formatting import tr_money as _tr_volume
from ..formatting import tr_number as _tr_number
from ..http import retry_get
from . import MarketSummary

log = get_logger(__name__)

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

