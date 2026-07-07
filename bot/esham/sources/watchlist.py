"""Bireysel hisse fiyat alarmları — BIST watchlist takibi.

WATCHLIST'teki her hisse için Yahoo Finance'dan günlük değişim çekilir.
Eşik aşılırsa NewsDetector'a HISSE_HAREKET olayı döner.

Eşik: ±3% (bireysel hisseler endeksten daha volatil olduğu için daha yüksek)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor, as_completed

log = logging.getLogger(__name__)

# BIST-30'un önemli hisseleri — Yahoo Finance formatı (.IS suffix)
WATCHLIST: list[tuple[str, str]] = [
    ("THYAO.IS", "THYAO"),   # Türk Hava Yolları
    ("GARAN.IS", "GARAN"),   # Garanti BBVA
    ("AKBNK.IS", "AKBNK"),   # Akbank
    ("ASELS.IS", "ASELS"),   # Aselsan
    ("KCHOL.IS", "KCHOL"),   # Koç Holding
    ("EREGL.IS", "EREGL"),   # Ereğli Demir Çelik
    ("SAHOL.IS", "SAHOL"),   # Sabancı Holding
    ("BIMAS.IS", "BIMAS"),   # BİM Mağazalar
    ("SISE.IS",  "SISE"),    # Şişe Cam
    ("TUPRS.IS", "TUPRS"),   # Tüpraş
    ("YKBNK.IS", "YKBNK"),   # Yapı Kredi
    ("TCELL.IS", "TCELL"),   # Turkcell
    ("FROTO.IS", "FROTO"),   # Ford Otosan
    ("TOASO.IS", "TOASO"),   # Tofaş
    ("PGSUS.IS", "PGSUS"),   # Pegasus
]

# Alarm eşiği — bireysel hisseler için daha yüksek (endeks eşiği 1.5%)
STOCK_ALERT_THRESHOLD: float = 3.0


@dataclass
class StockMove:
    """Tek bir hissenin günlük hareket özeti."""
    symbol: str       # Yahoo Finance sembolü (örn. THYAO.IS)
    ticker: str       # Kısa kod (örn. THYAO)
    price: float      # Güncel fiyat (TRY)
    change_pct: float # Günlük değişim yüzdesi
    volume: str = ""  # Hacim (formatlanmış)

    @property
    def change_str(self) -> str:
        sign = "+" if self.change_pct >= 0 else ""
        return f"{sign}{self.change_pct:.2f}%"

    @property
    def price_str(self) -> str:
        return f"₺{self.price:,.2f}"


def _fetch_one(symbol: str, ticker: str) -> StockMove | None:
    """Tek bir hisse için Yahoo Finance'dan veri çeker."""
    try:
        import yfinance as yf
        data = yf.Ticker(symbol).fast_info
        price = float(getattr(data, "last_price", 0) or 0)
        prev_close = float(getattr(data, "previous_close", 0) or 0)
        if not price or not prev_close:
            return None
        change_pct = (price - prev_close) / prev_close * 100

        # Hacim
        volume_raw = getattr(data, "three_month_average_volume", None)
        volume_str = ""
        if volume_raw:
            try:
                v = float(volume_raw)
                if v >= 1_000_000:
                    volume_str = f"{v/1_000_000:.1f}M"
                elif v >= 1_000:
                    volume_str = f"{v/1_000:.0f}K"
                else:
                    volume_str = str(int(v))
            except (ValueError, TypeError):
                pass

        return StockMove(
            symbol=symbol,
            ticker=ticker,
            price=price,
            change_pct=change_pct,
            volume=volume_str,
        )
    except Exception as exc:
        log.debug("Hisse verisi çekilemedi [%s]: %s", ticker, exc)
        return None


def fetch_stock_price(symbol: str, ticker: str) -> StockMove | None:
    """Tek bir hisse için fiyat çeker — threshold kontrolü yok.

    ticker_data.py gibi modüller tarafından kullanılır.
    """
    return _fetch_one(symbol, ticker)


def fetch_watchlist_moves(threshold: float = STOCK_ALERT_THRESHOLD) -> list[StockMove]:
    """WATCHLIST'teki hisselerden eşiği aşanları paralel çeker ve döner.

    Sadece abs(change_pct) >= threshold olan hisseler döner.
    Hata veren hisseler sessizce atlanır.
    """
    results: list[StockMove] = []
    with ThreadPoolExecutor(max_workers=min(len(WATCHLIST), 8)) as pool:
        future_to_ticker = {
            pool.submit(_fetch_one, symbol, ticker): ticker
            for symbol, ticker in WATCHLIST
        }
        for future in as_completed(future_to_ticker):
            move = future.result()
            if move and abs(move.change_pct) >= threshold:
                results.append(move)

    results.sort(key=lambda m: abs(m.change_pct), reverse=True)
    return results
