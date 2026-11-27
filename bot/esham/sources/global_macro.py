"""Küresel makro veri kaynağı.

Yahoo Finance chart API'sini kullanır — bist.py ile aynı altyapı.
ABD 10Y tahvil faizi, EUR/USD, Altın, VIX ve Brent ham petrol verilerini
ticker board formatında döner: [(label, arrow, value), ...].

Her sembol ThreadPoolExecutor ile paralel çekilir — 5 sıralı istek yerine
tek bir tur (~timeout süresi). Hata durumunda o sembol atlanır; diğerleri
etkilenmez (graceful degradation).
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field

import requests

from ..config import default_headers, get_logger, sample_data_allowed, settings
from datetime import datetime

from ..formatting import from_epoch, tr_bp, tr_datetime, tr_pct
from ..formatting import tr_number as _tr_number
from ..http import retry_get

log = get_logger(__name__)

CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"

# Ticker board'da gösterilecek semboller.
MACRO_TICKERS: list[tuple[str, str, str, int]] = [
    ("^GSPC",   "S&P 500",  "",    2),  # ABD S&P 500
    ("^IXIC",   "NASDAQ",   "",    2),  # ABD Nasdaq
    ("^GDAXI",  "DAX",      "",    2),  # Almanya DAX
    ("000001.SS", "ŞANGHAY", "",   2),  # Çin Şanghay Borsası
    ("^TNX",    "ABD 10Y",  "%",   2),  # ABD 10 yıllık tahvil faizi
    ("EURUSD=X", "EUR/USD", "",    3),  # Euro/Dolar
    ("TRY=X",   "USD/TRY",  "₺",   2),  # Dolar/Türk Lirası
    ("GC=F",    "ALTIN",    "$",   0),  # COMEX altın vadeli ($/ons) — spot değil
    ("^VIX",    "VIX",      "",    1),  # Volatilite endeksi
    ("BZ=F",    "BRENT",    "$",   1),  # Brent ham petrol
]
_DECIMALS = {label: dec for _, label, _, dec in MACRO_TICKERS}


@dataclass
class MacroTicker:
    """Tek bir makro enstrümanın son verisi.

    price      — son fiyat (``regularMarketPrice``; piyasa kapalıysa son seansın kapanışı)
    change_pct — ``price``'ın önceki kapanışa göre yüzde değişimi
    prev       — karşılaştırılan önceki kapanış (biliniyorsa)
    as_of      — son fiyatın zamanı (``regularMarketTime``, Türkiye saati); bilinmiyorsa None
    """
    label: str
    price: float
    change_pct: float
    suffix: str = ""
    prev: float | None = None
    as_of: datetime | None = None

    @property
    def arrow(self) -> str:
        return "↑" if self.change_pct >= 0 else "↓"

    @property
    def is_rate(self) -> bool:
        """Değeri zaten yüzde olan büyüklük (tahvil faizi)."""
        return self.suffix == "%"

    @property
    def value_str(self) -> str:
        """Kart ticker board'da gösterilecek değer string'i."""
        if self.is_rate:
            return tr_pct(self.price, 2, signed=False)
        decimals = 0 if self.suffix == "$" and self.price > 100 else max(2, _DECIMALS.get(self.label, 2))
        num = _tr_number(self.price, decimals)
        return f"{self.suffix}{num}" if self.suffix else num

    @property
    def change_str(self) -> str:
        """Önceki kapanışa göre yüzde değişim (``+%1,16``)."""
        return tr_pct(self.change_pct)

    @property
    def change_points(self) -> float | None:
        """Faizde önceki kapanışa göre yüzde PUAN farkı (yalnız ``is_rate`` ve ``prev`` biliniyorsa)."""
        if self.is_rate and self.prev is not None:
            return self.price - self.prev
        return None

    @property
    def change_report(self) -> str:
        """Rapor metni için değişim: faizde baz puan (``+6 baz puan``), diğerlerinde yüzde."""
        pts = self.change_points
        if self.is_rate:
            return tr_bp(pts) if pts is not None else "—"
        return self.change_str

    @property
    def as_of_str(self) -> str:
        return tr_datetime(self.as_of) if self.as_of else "bilinmiyor"

    def to_board_row(self) -> tuple[str, str, str]:
        """(label, arrow, value) — CardSpec.ticker_board formatı."""
        return (self.label, self.arrow, self.value_str)


@dataclass
class GlobalMacroSnapshot:
    """Tüm makro enstrümanların birleşik görünümü."""
    tickers: list[MacroTicker] = field(default_factory=list)

    def ticker_board(self) -> list[tuple[str, str, str]]:
        """CardSpec.ticker_board için hazır liste."""
        return [t.to_board_row() for t in self.tickers]

    def summary_line(self) -> str:
        """Tweet/rapor için tek satır özet (değişimler önceki kapanışa göredir)."""
        if not self.tickers:
            return "Küresel makro veri alınamadı."
        parts = [f"{t.label} {t.change_report}" for t in self.tickers[:3]]
        return "Önceki kapanışa göre: " + " | ".join(parts)

    def to_markdown_table(self) -> str:
        """Web raporu için markdown tablosu (her satır kendi veri zamanını taşır)."""
        rows = "\n".join(
            f"| {t.label} | {t.value_str} | {t.change_report} | {t.as_of_str} |"
            for t in self.tickers
        )
        return (
            "| Enstrüman | Son değer | Önceki kapanışa göre | Veri zamanı |\n"
            f"| --- | --- | --- | --- |\n{rows}"
        )


class GlobalMacroSource:
    def __init__(self) -> None:
        self.headers = default_headers()

    def snapshot(self) -> GlobalMacroSnapshot:
        """Tüm makro sembolleri paralel çeker; başarısız olanları sessizce atlar.

        ThreadPoolExecutor ile aynı anda 5 istek açılır — max bekleme süresi
        sıralı 5×timeout yerine 1×timeout olur.
        """
        results: dict[str, MacroTicker | None] = {}

        with ThreadPoolExecutor(max_workers=len(MACRO_TICKERS)) as pool:
            future_to_key = {
                pool.submit(self._fetch_one, symbol, label, suffix): symbol
                for symbol, label, suffix, _ in MACRO_TICKERS
            }
            for future in as_completed(future_to_key):
                symbol = future_to_key[future]
                try:
                    results[symbol] = future.result()
                except Exception as exc:
                    log.warning("Paralel fetch hatası (%s): %s", symbol, exc)
                    results[symbol] = None

        # Orijinal sırayı koru (MACRO_TICKERS'daki sıra)
        tickers = [
            results[symbol]
            for symbol, _, _, _ in MACRO_TICKERS
            if results.get(symbol) is not None
        ]

        if not tickers:
            if sample_data_allowed():
                log.warning("ESHAM_ALLOW_SAMPLE_DATA açık: küresel makro için ÖRNEK veri (yalnızca geliştirme).")
                tickers = self._sample()
            else:
                log.warning("Küresel makro: hiçbir sembol alınamadı; örnek veri üretilmiyor (boş).")
        return GlobalMacroSnapshot(tickers=tickers)

    def _fetch_one(self, symbol: str, label: str, suffix: str) -> MacroTicker | None:
        try:
            url = CHART_URL.format(symbol=symbol)
            resp = retry_get(url, headers=self.headers, timeout=settings.http_timeout)
            resp.raise_for_status()
            meta = resp.json()["chart"]["result"][0]["meta"]
            price = meta.get("regularMarketPrice")
            prev = meta.get("chartPreviousClose") or meta.get("previousClose")
            if price is None:
                log.debug("Sembol %s için fiyat yok.", symbol)
                return None
            if not prev:
                # Önceki kapanış yoksa değişim BİLİNMİYOR: 0,00 diye yazılmaz, sembol atlanır.
                log.debug("Sembol %s için önceki kapanış yok; atlanıyor.", symbol)
                return None
            change_pct = (price - prev) / prev * 100
            return MacroTicker(
                label=label,
                price=float(price),
                change_pct=float(change_pct),
                suffix=suffix,
                prev=float(prev),
                as_of=from_epoch(meta.get("regularMarketTime")),
            )
        except (requests.RequestException, ValueError, KeyError, IndexError, TypeError) as exc:
            log.warning("Makro sembol alınamadı (%s): %s", symbol, exc)
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
            log.warning("Makro fiyat serisi alınamadı (%s).", exc)
            return None

    @staticmethod
    def _sample() -> list[MacroTicker]:
        """Ağ bağlantısı olmadığında kullanılan örnek veriler."""
        return [
            MacroTicker("ABD 10Y", 4.52, +0.03, "%"),
            MacroTicker("EUR/USD", 1.083, -0.21, ""),
            MacroTicker("USD/TRY", 32.85, +0.15, "₺"),
            MacroTicker("ALTIN",   2340.0, +0.45, "$"),
            MacroTicker("VIX",     18.4, -2.10, ""),
            MacroTicker("BRENT",   85.3, +0.80, "$"),
        ]
