"""Kripto para piyasası veri kaynağı.

Yahoo Finance chart API'sini kullanarak majör kripto paraların (BTC, ETH) anlık
durumunu ve grafik verilerini (sparkline) çeker.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field

import requests

from ..config import default_headers, get_logger, settings
from ..formatting import tr_pct
from ..http import retry_get

log = get_logger(__name__)

CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"

# (yahoo_symbol, etiket)
CRYPTO_TICKERS: list[tuple[str, str]] = [
    ("BTC-USD", "Bitcoin"),
    ("ETH-USD", "Ethereum"),
    ("SOL-USD", "Solana"),
    ("XRP-USD", "Ripple"),
]


@dataclass
class CryptoTicker:
    """Tek bir kripto paranın anlık durumu."""
    symbol: str
    label: str
    price: float
    change_pct: float

    @property
    def arrow(self) -> str:
        return "↑" if self.change_pct >= 0 else "↓"

    @property
    def change_str(self) -> str:
        return tr_pct(self.change_pct)


class CryptoSource:
    def __init__(self) -> None:
        self.headers = default_headers()

    def snapshot(self) -> list[CryptoTicker]:
        results: dict[str, CryptoTicker | None] = {}

        with ThreadPoolExecutor(max_workers=len(CRYPTO_TICKERS)) as pool:
            future_to_key = {
                pool.submit(self._fetch_one, symbol, label): symbol
                for symbol, label in CRYPTO_TICKERS
            }
            for future in as_completed(future_to_key):
                symbol = future_to_key[future]
                try:
                    results[symbol] = future.result()
                except Exception as exc:
                    log.warning("Kripto fetch hatası (%s): %s", symbol, exc)
                    results[symbol] = None

        tickers = [
            results[symbol]
            for symbol, _ in CRYPTO_TICKERS
            if results.get(symbol) is not None
        ]
        return tickers

    def _fetch_one(self, symbol: str, label: str) -> CryptoTicker | None:
        try:
            url = CHART_URL.format(symbol=symbol)
            resp = retry_get(url, headers=self.headers, timeout=settings.http_timeout)
            resp.raise_for_status()
            meta = resp.json()["chart"]["result"][0]["meta"]
            price = meta.get("regularMarketPrice")
            prev = meta.get("chartPreviousClose") or meta.get("previousClose")
            if price is None:
                return None
            change_pct = ((price - prev) / prev * 100) if prev else 0.0
            return CryptoTicker(
                symbol=symbol,
                label=label,
                price=float(price),
                change_pct=float(change_pct),
            )
        except (requests.RequestException, ValueError, KeyError, IndexError, TypeError) as exc:
            log.warning("Kripto sembol alınamadı (%s): %s", symbol, exc)
            return None

    def fetch_closes(self, symbol: str, range_str: str = "1d", interval: str = "15m") -> list[float] | None:
        """Sparkline için fiyat serisi döner."""
        try:
            url = f"{CHART_URL.format(symbol=symbol)}?range={range_str}&interval={interval}"
            resp = retry_get(url, headers=self.headers, timeout=settings.http_timeout)
            resp.raise_for_status()
            result = resp.json()["chart"]["result"][0]
            closes = result["indicators"]["quote"][0].get("close", [])
            valid = [c for c in closes if c is not None]
            return valid or None
        except (requests.RequestException, ValueError, KeyError, IndexError, TypeError) as exc:
            log.warning("Kripto fiyat serisi alınamadı (%s).", exc)
            return None
