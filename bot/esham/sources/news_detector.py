"""Makro ve sektör fiyat hareketlerinden otomatik haber tetikleyici.

Tasarım: Her tarama turunda GlobalMacroSource ve SectorSource'dan anlık veri çeker,
önceki değerlerle karşılaştırır. Eşiği aşan hareketler `MarketEvent` listesi olarak
döner — bunlar NewsStream kuyruğuna eklenir ve AI analiz raporu + tweet olarak yayınlanır.

Haber türleri:
- MAKRO_HAREKET : VIX sıçraması, faiz hareketi, dolar/TL değişimi, altın rallisi vb.
- SEKTÖR_HAREKET: BIST sektör endeksinde güçlü yükseliş veya sert düşüş
- BIST_HAREKET  : XU100 endeksinde ani sert hareket

Her enstrüman için eşikler ENV değişkeniyle ayarlanabilir; varsayılanlar gerçekçi
piyasa eşikleri (örn. VIX %5+, ABD 10Y 5 baz puan+, altın %0.8+).
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Literal

from ..config import get_logger
from .global_macro import GlobalMacroSource, MacroTicker
from .sector import SectorMove, SectorSource

log = get_logger(__name__)

# ---- eşikler (ENV override ile ayarlanabilir) ----------------------------------

def _env_float(key: str, default: float) -> float:
    try:
        return float(os.getenv(key, str(default)))
    except ValueError:
        return default


# Her sembol için "haber tetiklensin" minimum değişim eşikleri (%)
THRESHOLDS: dict[str, float] = {
    "ABD 10Y":  _env_float("ESHAM_THRESH_ABD10Y",   0.04),   # 4 baz puan (% cinsinden)
    "EUR/USD":  _env_float("ESHAM_THRESH_EURUSD",    0.30),   # %0.30
    "USD/TRY":  _env_float("ESHAM_THRESH_USDTRY",    0.50),   # %0.50 — Dolar/TL
    "ALTIN":    _env_float("ESHAM_THRESH_ALTIN",     0.80),   # %0.80
    "VIX":      _env_float("ESHAM_THRESH_VIX",       5.00),   # %5.00 (VIX oynak)
    "BRENT":    _env_float("ESHAM_THRESH_BRENT",     1.00),   # %1.00
    "Bitcoin":  _env_float("ESHAM_THRESH_BTC",       3.00),   # %3.00
    "Ethereum": _env_float("ESHAM_THRESH_ETH",       4.00),   # %4.00
}

# Sektör endeksi eşiği
SECTOR_THRESHOLD: float = _env_float("ESHAM_THRESH_SECTOR", 2.0)   # %2.0
# BIST XU100 endeks günlük hareket eşiği
BIST_THRESHOLD: float = _env_float("ESHAM_THRESH_BIST", 1.5)       # %1.5

EventKind = Literal["MAKRO_HAREKET", "SEKTÖR_HAREKET", "BIST_HAREKET", "SON_DAKIKA", "KRIPTO_HAREKET"]


@dataclass
class MarketEvent:
    """Otomatik tespit edilen tek bir piyasa gelişmesi.

    kind      — olayın türü (MAKRO_HAREKET / SEKTÖR_HAREKET / BIST_HAREKET)
    label     — insan okunur kısa ad (ör. "VIX", "Bankacılık", "XU100")
    change_pct— tespit anındaki % değişim (negatif = düşüş)
    value_str — enstrümanın güncel değer metni (ör. "2.340 $")
    change_str— biçimlendirilmiş değişim metni (ör. "+5,2%")
    headline  — AI prompt'una ve tweet başlığına hazır açıklama
    key       — tekrar tespiti engellemek için benzersiz anahtar
    """

    kind: EventKind
    label: str
    change_pct: float
    value_str: str
    change_str: str
    headline: str
    key: str
    tags: list[str] = field(default_factory=list)

    @property
    def emoji(self) -> str:
        if self.kind == "SON_DAKIKA":
            return "🚨"
        if self.kind == "KRIPTO_HAREKET":
            return "🪙"
        if self.kind == "MAKRO_HAREKET":
            return "🌍"
        if self.kind == "SEKTÖR_HAREKET":
            return "📊"
        return "📈" if self.change_pct >= 0 else "📉"

    @property
    def category(self) -> str:
        if self.kind == "SON_DAKIKA":
            return "gundem"
        if self.kind == "KRIPTO_HAREKET":
            return "kripto"
        if self.kind == "SEKTÖR_HAREKET":
            return "bist"
        if self.kind == "BIST_HAREKET":
            return "bist"
        return "global"


# ---- yardımcı formatlayıcılar ---------------------------------------------------

def _fmt_pct(pct: float) -> str:
    sign = "+" if pct >= 0 else ""
    return f"{sign}{pct:.2f}%"


def _direction(pct: float) -> str:
    return "yükseldi" if pct >= 0 else "geriledi"


# ---- olay oluşturucular ---------------------------------------------------------

def _macro_event(ticker: MacroTicker) -> MarketEvent:
    direction = _direction(ticker.change_pct)
    headline = (
        f"{ticker.label} {ticker.arrow} {ticker.change_str} {direction}; "
        f"küresel risk iştahına yansıması izleniyor."
    )
    # Enstrümana özgü daha açıklayıcı başlık
    if ticker.label == "VIX":
        headline = (
            f"VIX {ticker.change_str} {direction} — korku endeksi "
            f"{'yükseliyor, risk iştahı baskı altında' if ticker.change_pct > 0 else 'geriliyor, piyasalar rahatladı'}."
        )
    elif ticker.label == "ABD 10Y":
        headline = (
            f"ABD 10 yıllık tahvil faizi {ticker.change_str} {direction} ({ticker.value_str}). "
            f"Gelişmekte olan piyasalar üzerindeki baskı izleniyor."
        )
    elif ticker.label == "ALTIN":
        headline = (
            f"Altın {ticker.change_str} {direction} ({ticker.value_str}). "
            f"{'Güvenli liman talebi artıyor.' if ticker.change_pct > 0 else 'Risk iştahı altından uzaklaştırıyor.'}"
        )
    elif ticker.label == "BRENT":
        headline = (
            f"Brent petrol {ticker.change_str} {direction} ({ticker.value_str}). "
            f"Enerji fiyatlarındaki hareket enflasyon beklentilerini etkiliyor."
        )
    elif "USD" in ticker.label or "EUR" in ticker.label:
        headline = (
            f"{ticker.label} {ticker.change_str} {direction} ({ticker.value_str}). "
            f"Döviz hareketleri TL varlıkları üzerindeki etkisiyle takip ediliyor."
        )

    tags = ["Makro", ticker.label.replace("/", ""), "Küresel"]
    return MarketEvent(
        kind="MAKRO_HAREKET",
        label=ticker.label,
        change_pct=ticker.change_pct,
        value_str=ticker.value_str,
        change_str=ticker.change_str,
        headline=headline,
        key=f"macro:{ticker.label}:{ticker.change_pct:.2f}",
        tags=tags,
    )


def _sector_event(move: SectorMove) -> MarketEvent:
    direction = _direction(move.change_pct)
    strength = "güçlü" if move.change_pct >= 0 else "sert"
    headline = (
        f"BIST {move.name} sektörü {move.change_str} ile {strength} {direction}; "
        f"sektör rotasyonu ve para akışı takip ediliyor."
    )
    tags = ["Sektör", move.name, "BIST"]
    return MarketEvent(
        kind="SEKTÖR_HAREKET",
        label=move.name,
        change_pct=move.change_pct,
        value_str=move.change_str,
        change_str=move.change_str,
        headline=headline,
        key=f"sector:{move.code}:{move.change_pct:.2f}",
        tags=tags,
    )


# ---- ana dedektör sınıfı --------------------------------------------------------

class NewsDetector:
    """Her `scan()` çağrısında yeni tetikleyici olayları döner.

    `_seen_keys` ile aynı olay ikinci kez döndürülmez — set bellekte tutulur,
    süreç yeniden başlarsa sıfırlanır (restart'ta makro veriler de değişmiş
    olur, dolayısıyla yeniden tetikleme gereksiz alarm olmaz).
    """

    def __init__(self) -> None:
        self._seen_keys: set[str] = set()
        self._macro_src = GlobalMacroSource()
        self._sector_src = SectorSource()
        from .bist import BistSource  # noqa: PLC0415
        from .global_news import GlobalNewsSource
        from .crypto import CryptoSource
        from ..ai.analyzer import MarketAIAnalyzer
        self._bist_src = BistSource()
        self._global_news_src = GlobalNewsSource()
        self._crypto_src = CryptoSource()
        self._ai = MarketAIAnalyzer()

    def scan(self) -> list[MarketEvent]:
        """Tüm kaynakları tarar; yeni tetikleyici olayları listeler."""
        events: list[MarketEvent] = []
        events.extend(self._scan_macro())
        events.extend(self._scan_sectors())
        events.extend(self._scan_bist())
        events.extend(self._scan_global_news())
        events.extend(self._scan_crypto())
        return events

    # ---- makro tarama -----------------------------------------------------------

    def _scan_macro(self) -> list[MarketEvent]:
        events: list[MarketEvent] = []
        try:
            snap = self._macro_src.snapshot()
        except Exception as exc:
            log.warning("Makro tarama hatası: %s", exc)
            return events

        for ticker in snap.tickers:
            threshold = THRESHOLDS.get(ticker.label, 1.0)
            if abs(ticker.change_pct) < threshold:
                continue
            event = _macro_event(ticker)
            if event.key in self._seen_keys:
                continue
            self._seen_keys.add(event.key)
            events.append(event)
            log.info(
                "Makro olay tespit edildi: %s %s (eşik: ±%.2f%%)",
                ticker.label, ticker.change_str, threshold,
            )

        return events

    # ---- BIST endeks tarama -----------------------------------------------------

    def _scan_bist(self) -> list[MarketEvent]:
        """XU100 günlük %BIST_THRESHOLD+ hareket ettiğinde olay üretir."""
        events: list[MarketEvent] = []
        try:
            summary = self._bist_src.market_summary()
        except Exception as exc:
            log.warning("BIST endeks tarama hatası: %s", exc)
            return events

        change_str = summary.change  # ör. "+1,23%" veya "-0,87%"
        if not change_str:
            return events
        try:
            pct = float(
                change_str.replace("%", "").replace(",", ".").replace("+", "").strip()
            )
        except ValueError:
            return events

        if abs(pct) < BIST_THRESHOLD:
            return events

        direction = _direction(pct)
        strength = "güçlü" if pct >= 0 else "sert"
        headline = (
            f"BIST {summary.index} endeksi {_fmt_pct(pct)} ile {strength} {direction}. "
            f"Güncel seviye: {summary.price}"
            + (f", hacim: {summary.volume}" if summary.volume else "")
            + "."
        )
        key = f"bist:{summary.index}:{pct:.2f}"
        if key in self._seen_keys:
            return events
        self._seen_keys.add(key)

        event = MarketEvent(
            kind="BIST_HAREKET",
            label=summary.index,
            change_pct=pct,
            value_str=summary.price,
            change_str=_fmt_pct(pct),
            headline=headline,
            key=key,
            tags=["BIST", summary.index, "Borsa"],
        )
        events.append(event)
        log.info(
            "BIST endeks olayı tespit edildi: %s %s (eşik: ±%.2f%%)",
            summary.index, _fmt_pct(pct), BIST_THRESHOLD,
        )
        return events

    # ---- sektör tarama ----------------------------------------------------------

    def _scan_sectors(self) -> list[MarketEvent]:
        events: list[MarketEvent] = []
        try:
            moves = self._sector_src.snapshot()
        except Exception as exc:
            log.warning("Sektör tarama hatası: %s", exc)
            return events

        for move in moves:
            if abs(move.change_pct) < SECTOR_THRESHOLD:
                continue
            event = _sector_event(move)
            if event.key in self._seen_keys:
                continue
            self._seen_keys.add(event.key)
            events.append(event)
            log.info(
                "Sektör olayı tespit edildi: %s %s (eşik: ±%.2f%%)",
                move.name, move.change_str, SECTOR_THRESHOLD,
            )

        return events

    # ---- global haber tarama ----------------------------------------------------

    def _scan_global_news(self) -> list[MarketEvent]:
        events: list[MarketEvent] = []
        try:
            news_items = self._global_news_src.fetch_latest()
        except Exception as exc:
            log.warning("Global haber tarama hatası: %s", exc)
            return events

        for item in news_items:
            key = f"news:{item.link}"
            if key in self._seen_keys:
                continue
            self._seen_keys.add(key)
            
            # AI Analizi
            translated = self._ai.analyze_global_breaking_news(item.title)
            if not translated:
                continue
                
            headline = f"{translated}\n\nKaynak: {item.link}"
            event = MarketEvent(
                kind="SON_DAKIKA",
                label="Küresel Haber",
                change_pct=0.0,
                value_str="",
                change_str="",
                headline=headline,
                key=key,
                tags=["SonDakika", "Küresel"],
            )
            events.append(event)
            log.info("Son dakika haberi tespit edildi: %s", translated)

        return events

    # ---- kripto tarama ----------------------------------------------------------

    def _scan_crypto(self) -> list[MarketEvent]:
        events: list[MarketEvent] = []
        try:
            tickers = self._crypto_src.snapshot()
        except Exception as exc:
            log.warning("Kripto tarama hatası: %s", exc)
            return events

        for ticker in tickers:
            threshold = THRESHOLDS.get(ticker.label, 3.0)
            if abs(ticker.change_pct) < threshold:
                continue
                
            direction = _direction(ticker.change_pct)
            strength = "güçlü" if ticker.change_pct >= 0 else "sert"
            headline = (
                f"{ticker.label} {_fmt_pct(ticker.change_pct)} ile {strength} {direction}. "
                f"Güncel fiyat: ${ticker.price:,.0f}"
            )
            key = f"crypto:{ticker.symbol}:{ticker.change_pct:.2f}"
            if key in self._seen_keys:
                continue
            self._seen_keys.add(key)

            event = MarketEvent(
                kind="KRIPTO_HAREKET",
                label=ticker.label,
                change_pct=ticker.change_pct,
                value_str=f"${ticker.price:,.0f}",
                change_str=_fmt_pct(ticker.change_pct),
                headline=headline,
                key=key,
                tags=["Kripto", ticker.label],
            )
            events.append(event)
            log.info("Kripto olayı tespit edildi: %s %s (eşik: ±%.2f%%)", ticker.label, _fmt_pct(ticker.change_pct), threshold)

        return events

    def reset(self) -> None:
        """Görülmüş anahtarları sıfırlar — test veya günlük reset için."""
        self._seen_keys.clear()
