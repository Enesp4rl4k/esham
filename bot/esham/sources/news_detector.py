"""Makro ve sektör fiyat hareketlerinden otomatik haber tetikleyici.

Tasarım: Her tarama turunda GlobalMacroSource ve SectorSource'dan anlık veri çeker,
önceki değerlerle karşılaştırır. Eşiği aşan hareketler `MarketEvent` listesi olarak
döner — bunlar NewsStream kuyruğuna eklenir ve AI analiz raporu + tweet olarak yayınlanır.

Haber türleri:
- MAKRO_HAREKET : VIX sıçraması, faiz hareketi, dolar/TL değişimi, altın rallisi vb.
- SEKTÖR_HAREKET: BIST sektör endeksinde güçlü yükseliş veya sert düşüş
- BIST_HAREKET  : XU100 endeksinde ani sert hareket
- HISSE_HAREKET : BIST-30 watchlist hisselerinde bireysel fiyat alarmı (±3%)

Her enstrüman için eşikler ENV değişkeniyle ayarlanabilir; varsayılanlar gerçekçi
piyasa eşikleri (örn. VIX %5+, ABD 10Y 5 baz puan+, altın %0.8+).
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
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
    "Bitcoin":  _env_float("ESHAM_THRESH_BTC",       1.50),   # %1.50
    "Ethereum": _env_float("ESHAM_THRESH_ETH",       2.00),   # %2.00
    "Solana":   _env_float("ESHAM_THRESH_SOL",       2.50),   # %2.50
    "Ripple":   _env_float("ESHAM_THRESH_XRP",       3.00),   # %3.00
}

# Sektör endeksi eşiği
SECTOR_THRESHOLD: float = _env_float("ESHAM_THRESH_SECTOR", 2.0)   # %2.0
# BIST XU100 endeks günlük hareket eşiği
BIST_THRESHOLD: float = _env_float("ESHAM_THRESH_BIST", 1.5)       # %1.5

EventKind = Literal["MAKRO_HAREKET", "SEKTÖR_HAREKET", "BIST_HAREKET", "SON_DAKIKA", "KRIPTO_HAREKET", "TEKNOLOJI_HAREKET"]


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
    details   — haberin tam açıklaması veya piyasa/teknik veri detayları
    source_url— haberin orijinal bağlantısı
    source_name— haber kaynağının adı
    """

    kind: EventKind
    label: str
    change_pct: float
    value_str: str
    change_str: str
    headline: str
    key: str
    tags: list[str] = field(default_factory=list)
    details: str = ""
    source_url: str = ""
    source_name: str = ""

    @property
    def emoji(self) -> str:
        if self.kind == "SON_DAKIKA":
            return "🚨"
        if self.kind == "TEKNOLOJI_HAREKET":
            return "⚡"
        if self.kind == "KRIPTO_HAREKET":
            return "🪙"
        if self.kind == "MAKRO_HAREKET":
            return "🌍"
        if self.kind == "SEKTÖR_HAREKET":
            return "📊"
        return "📈" if self.change_pct >= 0 else "📉"

    @property
    def category(self) -> str:
        if self.kind == "TEKNOLOJI_HAREKET":
            return "teknoloji"
        if self.kind == "KRIPTO_HAREKET":
            return "kripto"
        if self.kind in ("SEKTÖR_HAREKET", "BIST_HAREKET", "HISSE_HAREKET"):
            return "bist"
        if self.kind == "SON_DAKIKA":
            return "gundem"
        return "global"


# ---- yardımcı formatlayıcılar ---------------------------------------------------

def _fmt_pct(pct: float) -> str:
    sign = "+" if pct >= 0 else ""
    return f"{sign}{pct:.2f}%"


def _direction(pct: float) -> str:
    return "yükseldi" if pct >= 0 else "geriledi"


def _dedup_key(prefix: str, label: str, pct: float) -> str:
    """Aynı enstrüman için günde bir kez tetikleme anahtarı.

    Önceden anahtar `pct:.2f` içeriyordu; hareket her tarama turunda birkaç
    baz puan kayınca (ör. %2,91 -> %2,97) anahtar değişip aynı olay tekrar
    "yeni" sayılıyor, bu da 10 dakikada bir neredeyse aynı tweet'in
    atılmasına yol açıyordu. Gün + yön (artı/eksi) bazlı anahtar, aynı
    enstrüman aynı yönde hareket ettiği sürece günde bir kez tetiklenmesini
    sağlar; yön değişirse (ör. sektör düşüşe geçerse) yeniden tetiklenir.
    """
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    direction = "up" if pct >= 0 else "down"
    return f"{prefix}:{label}:{day}:{direction}"


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
        key=_dedup_key("macro", ticker.label, ticker.change_pct),
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
        key=_dedup_key("sector", move.code, move.change_pct),
        tags=tags,
    )


# ---- ana dedektör sınıfı --------------------------------------------------------

class NewsDetector:
    """Her `scan()` çağrısında yeni tetikleyici olayları döner.

    `_seen_keys` ile aynı olay ikinci kez döndürülmez.
    - Makro/sektör/BIST olayları: bellekte tutulur (restart'ta değerler değişmiş
      olduğundan yeniden tetikleme zararsız, hatta istenir).
    - SON_DAKIKA (global haber) olayları: state dosyasında kalıcı tutulur —
      restart'ta aynı haber tekrar tweetlenmez. 24 saatlik TTL uygulanır.
    """

    def __init__(self) -> None:
        from ..state import get_state
        self._state = get_state()
        # Makro/sektör/bist/hisse olayları — artık diske kalıcı (1 günlük TTL).
        # Bellekte tutulduğunda GitHub Actions her çalıştırmasında sıfırlanıyor ve
        # aynı sektör/makro olay günde onlarca kez paylaşılıyordu.
        self._seen_keys: set[str] = self._state.load_seen_market_events()
        # SON_DAKIKA haberleri için kalıcı seen set (24 saatlik TTL)
        self._seen_news_keys: set[str] = self._state.load_seen_news()

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
        # Kripto haber kaynağı ayrı instance (farklı RSS URL'leri)
        self._crypto_news_src = GlobalNewsSource.__new__(GlobalNewsSource)
        self._crypto_news_src.sources = __import__(
            "esham.sources.global_news", fromlist=["CRYPTO_NEWS_SOURCES"]
        ).CRYPTO_NEWS_SOURCES
        # Bireysel hisse watchlist
        from .watchlist import fetch_watchlist_moves, STOCK_ALERT_THRESHOLD
        self._fetch_watchlist = fetch_watchlist_moves
        self._watchlist_threshold = STOCK_ALERT_THRESHOLD

    def scan(self) -> list[MarketEvent]:
        """Tüm kaynakları tarar; yeni tetikleyici olayları listeler."""
        events: list[MarketEvent] = []
        events.extend(self._scan_macro())
        events.extend(self._scan_sectors())
        events.extend(self._scan_bist())
        events.extend(self._scan_watchlist())
        events.extend(self._scan_global_news())
        events.extend(self._scan_crypto())
        events.extend(self._scan_crypto_news())
        events.extend(self._scan_tech_news())
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
            self._state.save_seen_market_events(self._seen_keys)
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
        key = _dedup_key("bist", summary.index, pct)
        if key in self._seen_keys:
            return events
        self._seen_keys.add(key)
        self._state.save_seen_market_events(self._seen_keys)

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

    # ---- bireysel hisse watchlist tarama ----------------------------------------

    def _scan_watchlist(self) -> list[MarketEvent]:
        """BIST-30 watchlist hisselerini tarar; ±3%+ hareket edenleri olaya dönüştürür."""
        events: list[MarketEvent] = []
        try:
            moves = self._fetch_watchlist(self._watchlist_threshold)
        except Exception as exc:
            log.warning("Watchlist tarama hatası: %s", exc)
            return events

        for move in moves:
            direction = _direction(move.change_pct)
            strength = "güçlü" if move.change_pct >= 0 else "sert"
            headline = (
                f"{move.ticker} hissesi {move.change_str} ile {strength} {direction}. "
                f"Güncel fiyat: {move.price_str}"
                + (f", hacim: {move.volume}" if move.volume else "")
                + "."
            )
            key = _dedup_key("hisse", move.ticker, move.change_pct)
            if key in self._seen_keys:
                continue
            self._seen_keys.add(key)
            self._state.save_seen_market_events(self._seen_keys)

            event = MarketEvent(
                kind="HISSE_HAREKET",
                label=move.ticker,
                change_pct=move.change_pct,
                value_str=move.price_str,
                change_str=move.change_str,
                headline=headline,
                key=key,
                tags=["BIST", move.ticker, "Hisse"],
            )
            events.append(event)
            log.info(
                "Hisse alarmı: %s %s (eşik: ±%.1f%%)",
                move.ticker, move.change_str, self._watchlist_threshold,
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
            self._state.save_seen_market_events(self._seen_keys)
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
            # Link'ten normalize anahtar — query string'i at
            norm_link = item.link.split("?")[0].rstrip("/")
            key = f"news:{norm_link}"

            # Kalıcı seen set'te kontrol et (restart'tan sonra da tekrar göndermez)
            if key in self._seen_news_keys:
                continue

            # Bellekteki set'e de ekle (aynı seans içinde tekrarı önle)
            if key in self._seen_keys:
                continue

            # Önce seen'e ekle — AI çağrısından bağımsız (başarısız olsa da tekrar denemesin)
            self._seen_keys.add(key)
            self._seen_news_keys.add(key)
            self._state.save_seen_news(self._seen_news_keys)

            # AI Analizi — önemsizse None döner
            translated = self._ai.analyze_global_breaking_news(item.title)
            if not translated:
                continue

            headline = translated.removeprefix("SON DAKİKA: ").strip()
            event = MarketEvent(
                kind="SON_DAKIKA",
                label="Küresel Haber",
                change_pct=0.0,
                value_str="",
                change_str="",
                headline=headline,
                key=key,
                tags=["SonDakika", "Küresel"],
                details=item.description,
                source_url=item.link,
                source_name=item.source or "Küresel Ajanslar",
            )
            events.append(event)
            log.info(
                "Son dakika haberi tespit edildi [%s]: %s",
                item.source or "?",
                translated[:80],
            )

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
                f"{ticker.label} {_fmt_pct(ticker.change_pct)} ile {strength} {direction} (Güncel: ${ticker.price:,.0f})"
            )
            details = (
                f"{ticker.label} ({ticker.symbol}) son 24 saatlik seansta {_fmt_pct(ticker.change_pct)} "
                f"oranında hareket ederek ${ticker.price:,.2f} seviyesinde dengelendi. "
                f"Piyasada yön arayışı sürerken türev piyasalardaki likidite ve fonlama oranları yakından takip ediliyor."
            )
            key = _dedup_key("crypto", ticker.symbol, ticker.change_pct)
            if key in self._seen_keys:
                continue
            self._seen_keys.add(key)
            self._state.save_seen_market_events(self._seen_keys)

            event = MarketEvent(
                kind="KRIPTO_HAREKET",
                label=ticker.label,
                change_pct=ticker.change_pct,
                value_str=f"${ticker.price:,.0f}",
                change_str=_fmt_pct(ticker.change_pct),
                headline=headline,
                key=key,
                tags=["Kripto", ticker.label],
                details=details,
                source_url="https://finance.yahoo.com/crypto",
                source_name="Yahoo Finance / CoinMarketCap",
            )
            events.append(event)
            log.info("Kripto olayı tespit edildi: %s %s (eşik: ±%.2f%%)", ticker.label, _fmt_pct(ticker.change_pct), threshold)

        return events

    # ---- kripto haber tarama (CoinDesk, CoinTelegraph, Decrypt) ----------------

    def _scan_crypto_news(self) -> list[MarketEvent]:
        """Kripto haber kaynaklarını tarar; AI filtresiyle önemli olanları kuyruğa atar.

        Fiyat hareketi değil, haber bazlı: büyük exchange kararları, düzenleyici
        haberler, balina hareketi haberleri, protokol güncellemeleri vb.
        """
        events: list[MarketEvent] = []
        try:
            news_items = self._crypto_news_src.fetch_crypto_news()
        except Exception as exc:
            log.warning("Kripto haber tarama hatası: %s", exc)
            return events

        for item in news_items:
            norm_link = item.link.split("?")[0].rstrip("/")
            key = f"cryptonews:{norm_link}"

            if key in self._seen_news_keys or key in self._seen_keys:
                continue

            self._seen_keys.add(key)
            self._seen_news_keys.add(key)
            self._state.save_seen_news(self._seen_news_keys)

            # AI ile önem filtresi — sadece piyasayı etkileyen haberler geçer
            context_hint = f"{item.title} — {item.description[:200]}" if item.description else item.title
            translated = self._ai.analyze_global_breaking_news(context_hint)
            if not translated:
                t_lower = f"{item.title} {item.description}".lower()
                is_major = any(k in t_lower for k in (
                    "bitcoin", "btc", "ethereum", "eth", "solana", "sol", "crypto", "sec",
                    "etf", "binance", "coinbase", "tether", "stablecoin", "fed", "rate",
                    "rally", "crash", "ath", "record", "hack", "whale", "halving", "inflow",
                ))
                if is_major:
                    translated = f"SON DAKİKA: {item.title}"
                else:
                    continue

            headline = translated.removeprefix("SON DAKİKA: ").strip()
            event = MarketEvent(
                kind="KRIPTO_HAREKET",
                label="Kripto Haber",
                change_pct=0.0,
                value_str="",
                change_str="",
                headline=headline,
                key=key,
                tags=["Kripto", "DijitalVarlıklar"],
                details=item.description,
                source_url=item.link,
                source_name=item.source or "Kripto Basını",
            )
            events.append(event)
            log.info(
                "Kripto haber tespit edildi [%s]: %s",
                item.source or "?",
                translated[:80],
            )

        return events

    # ---- teknoloji haber tarama (TechCrunch, The Verge, Ars Technica, VentureBeat) --

    def _scan_tech_news(self) -> list[MarketEvent]:
        """Teknoloji/AI haber kaynaklarını tarar; ekonomik etkisi olan haberleri kuyruğa atar.

        Yalnızca piyasaları/ekonomiyi doğrudan etkileyen teknoloji haberleri geçer:
        büyük AI modeli lansmanları, donanım kıtlığı/fazlalığı, büyük şirket satın almaları,
        çip/yarı iletken haberleri, veri merkezi yatırımları vb.
        AI filtresi "NO" döndürürse (önemsiz) haber atlanır.
        """
        events: list[MarketEvent] = []

        try:
            from .global_news import TECH_NEWS_SOURCES
            tech_items = self._global_news_src._fetch_and_dedup(TECH_NEWS_SOURCES)
        except Exception as exc:
            log.warning("Teknoloji haber tarama hatası: %s", exc)
            return events

        for item in tech_items:
            norm_link = item.link.split("?")[0].rstrip("/")
            key = f"tech:{norm_link}"

            if key in self._seen_news_keys or key in self._seen_keys:
                continue

            self._seen_keys.add(key)
            self._seen_news_keys.add(key)
            self._state.save_seen_news(self._seen_news_keys)

            # AI filtresi: sadece ekonomi/piyasa etkisi olan teknoloji haberlerini geçir
            context_hint = f"{item.title} — {item.description[:200]}" if item.description else item.title
            translated = self._ai.analyze_global_breaking_news(context_hint)
            if not translated:
                t_lower = f"{item.title} {item.description}".lower()
                is_major_tech = any(k in t_lower for k in (
                    "ai", "artificial intelligence", "model", "openai", "chatgpt", "gemini",
                    "claude", "anthropic", "nvidia", "gpu", "chip", "semiconductor", "tsmc",
                    "intel", "amd", "apple", "microsoft", "google", "meta", "blackwell",
                    "acquisition", "buys", "deal", "billion", "data center", "robot",
                ))
                if is_major_tech:
                    translated = f"SON DAKİKA: {item.title}"
                else:
                    continue

            headline = translated.removeprefix("SON DAKİKA: ").strip()
            event = MarketEvent(
                kind="TEKNOLOJI_HAREKET",
                label="Teknoloji & AI",
                change_pct=0.0,
                value_str="",
                change_str="",
                headline=headline,
                key=key,
                tags=["Teknoloji", "YapayZeka", "AI"],
                details=item.description,
                source_url=item.link,
                source_name=item.source or "Teknoloji Basını",
            )
            events.append(event)
            log.info(
                "Teknoloji haberi tespit edildi [%s]: %s",
                item.source or "?",
                translated[:80],
            )

        return events

    def reset(self) -> None:
        """Görülmüş anahtarları sıfırlar — test veya günlük reset için."""
        self._seen_keys.clear()
        self._seen_news_keys.clear()
        self._state.save_seen_market_events(set())
        self._state.save_seen_news(set())
