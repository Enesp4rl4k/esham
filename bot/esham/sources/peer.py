"""BIST eş/değer kıyası (peer comparison) kaynağı.

Aynı sektördeki birkaç büyük hissenin çarpanlarını (F/K, PD/DD, FD/FAVÖK,
temettü verimi, FAVÖK marjı, FÖK) yan yana koyar ve **medyan** üzerinden
göreli değerleme üretir: "X, sektör medyanından %x daha ucuz/pahalı".

Veri kaynakları (hepsi zarif bozulmalı):
- Fiyat/günlük değişim → Yahoo Finance **chart JSON API'si** (crumb'sız, repo'nun
  geri kalanıyla aynı uç nokta).
- Çarpanlar → Yahoo **quoteSummary** uç noktası. Bu uç nokta `Invalid Crumb`
  (401) döner; cookie + crumb akışı ile oturum açılır. Crumb alınamazsa çarpanlar
  boş kalır, kıyas fiyat performansıyla sürer. Hiçbir veri gelmezse boş snapshot (örnek veri yalnızca ESHAM_ALLOW_SAMPLE_DATA=1 ile).
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass, field

import requests

from ..config import default_headers, get_logger, sample_data_allowed, settings
from ..formatting import tr_money, tr_number, tr_pct
from .sector import SECTORS

log = get_logger(__name__)

#: Symbol zaten `.IS` ekiyle verilir — URL'e ekleme yapılmaz (aksi halde `.IS.IS`).
CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
QUOTE_SUMMARY_URL = "https://query1.finance.yahoo.com/v10/finance/quoteSummary/{symbol}"
CRUMB_URL = "https://query1.finance.yahoo.com/v1/test/getcrumb"
_YF_MODULES = "summaryDetail,defaultKeyStatistics,financialData"

#: Sektör anahtarı → {borsa kodu: şirket adı}. Anahtarlar `SECTORS` ile uyumlu
#: yazılır (kodlar Türkçe karakter içermemeli). Yanlış/eksik kod Yahoo'dan boş
#: döner ve atlanır — zarif bozulma.
PEER_GROUPS: dict[str, dict[str, str]] = {
    "bankacilik": {
        "AKBNK": "Akbank", "GARAN": "Garanti BBVA", "ISCTR": "İş Bankası (C)",
        "YKBNK": "Yapı Kredi", "VAKBN": "VakıfBank", "HALKB": "Halkbank",
    },
    "sanayi": {
        "EREGL": "Ereğli Demir Çelik", "SISE": "Şişecam", "ARCLK": "Arçelik",
        "PETKM": "Petkim", "KOZAL": "Koza Altın", "TUPRS": "Tüpraş",
    },
    "teknoloji": {
        "TCELL": "Türkcell", "TTKOM": "Türk Telekom", "ASELS": "Aselsan",
        "VESTL": "Vestel", "LOGO": "Logo Yazılım",
    },
    "otomotiv_ulasim": {
        "THYAO": "Türk Hava Yolları", "TOASO": "Tofaş Oto", "FROTO": "Ford Otosan",
        "TAVHL": "TAV Havalimanları",
    },
    "enerji": {
        "AKSEN": "Aksa Enerji", "ODAS": "Odaş Elektrik", "ZOREN": "Zorlu Enerji",
        "GUBRF": "Gübretaş",
    },
    "perakende_gida": {
        "BIMAS": "BİM Mağazalar", "MGROS": "Migros", "SOKM": "Şok Marketler",
        "ULKER": "Ülker Bisküvi",
    },
    "holding": {
        "KCHOL": "Koç Holding", "SAHOL": "Sabancı Holding",
        "OYAKC": "Oyak Çelik", "IHEVA": "İhlas Holding",
    },
}

# Örnek veri — YALNIZCA ESHAM_ALLOW_SAMPLE_DATA=1 ile (yerel geliştirme); üretimde asla kullanılmaz.
_SAMPLE: dict[str, list[tuple[str, str, float, float | None, float | None]]] = {
    # (kod, ad, fiyat, F/K, PD/DD)
    "bankacilik": [
        ("AKBNK", "Akbank", 62.50, 4.8, 1.1),
        ("GARAN", "Garanti BBVA", 128.40, 5.2, 1.3),
        ("ISCTR", "İş Bankası (C)", 14.85, 4.1, 0.9),
        ("YKBNK", "Yapı Kredi", 31.20, 4.5, 1.0),
    ],
}


@dataclass
class PeerMetric:
    ticker: str
    name: str
    price: float | None = None
    change_pct: float | None = None
    pe: float | None = None           # F/K (trailing)
    pb: float | None = None           # PD/DD
    ev_ebitda: float | None = None    # FD/FAVÖK
    dividend_yield: float | None = None  # % olarak
    ebitda_margin: float | None = None   # % olarak
    roe: float | None = None          # % olarak (FÖK)
    market_cap: float | None = None   # TL

    @property
    def price_str(self) -> str:
        return tr_number(self.price) if self.price else "—"

    @property
    def change_str(self) -> str:
        if self.change_pct is None:
            return "—"
        return tr_pct(self.change_pct)

    @property
    def has_fundamentals(self) -> bool:
        return any(v is not None for v in (self.pe, self.pb, self.ev_ebitda))

    @property
    def market_cap_str(self) -> str:
        return tr_money(self.market_cap) if self.market_cap else "—"


@dataclass
class PeerSnapshot:
    sector_key: str
    sector_name: str
    peers: list[PeerMetric] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)  # operasyonel notlar (ör. crumb yok)
    sample: bool = False

    # ---- medyanlar ---------------------------------------------------------
    def _median(self, attr: str) -> float | None:
        values = [getattr(p, attr) for p in self.peers if getattr(p, attr) is not None]
        return float(statistics.median(values)) if values else None

    @property
    def median_pe(self) -> float | None:
        return self._median("pe")

    @property
    def median_pb(self) -> float | None:
        return self._median("pb")

    @property
    def median_ev_ebitda(self) -> float | None:
        return self._median("ev_ebitda")

    @property
    def median_dividend_yield(self) -> float | None:
        return self._median("dividend_yield")

    def counted(self, attr: str) -> int:
        return sum(1 for p in self.peers if getattr(p, attr) is not None)

    def stance(self, attr: str, value: float | None) -> str:
        """`value` (ör. bir halka arzın F/K'sı) sektör medyanına göre konumlanır.

        Dönüş: "sektör medyanının %23 altında" / "medyanın %12 üzerinde" / "—".
        """
        med = self._median(attr)
        if med is None or value is None or value <= 0 or med <= 0:
            return "—"
        pct = (value - med) / med * 100
        if abs(pct) < 5:
            return "sektör medyanına yakın"
        direction = "üzerinde" if pct > 0 else "altında"
        return f"sektör medyanının {tr_pct(abs(pct), 0, signed=False)} {direction}"


class PeerSource:
    def __init__(self) -> None:
        self.headers = default_headers()
        self._session = requests.Session()
        self._session.headers.update(self.headers)
        self._crumb: str | None = None
        self._crumb_failed = False

    # ---- dışa açık ---------------------------------------------------------

    def snapshot(self, sector_key: str) -> PeerSnapshot:
        """Sektördeki tüm hisseleri toplar (fiyat + mümkünse çarpanlar)."""
        group = PEER_GROUPS.get(sector_key)
        if not group:
            raise ValueError(
                f"Bilinmeyen sektör: {sector_key!r}. Seçenekler: {sorted(PEER_GROUPS)}"
            )
        name = SECTORS.get(_SECTOR_CODE.get(sector_key, ""), sector_key.replace("_", " ").title())

        peers: list[PeerMetric] = []
        for ticker, company in group.items():
            metric = self._fetch(ticker, company)
            if metric:
                peers.append(metric)

        snapshot = PeerSnapshot(sector_key=sector_key, sector_name=name, peers=peers)
        if self._crumb_failed:
            snapshot.notes.append(
                "Yahoo çarpan (F/K, PD/DD) uç noktası crumb nedeniyle alınamadı; "
                "kıyas fiyat performansıyla sınırlı."
            )
        if not peers:
            if sample_data_allowed():
                log.warning(
                    "ESHAM_ALLOW_SAMPLE_DATA açık: peer için ÖRNEK veri (%s) — yalnızca geliştirme.",
                    sector_key,
                )
                return self._sample(sector_key, name)
            log.warning("Peer verisi alınamadı (%s); örnek veri üretilmiyor (boş).", sector_key)
            snapshot.notes.append("Peer verisi alınamadı.")
            return snapshot
        log.info("Peer kıyası: %s → %d hisse.", sector_key, len(peers))
        return snapshot

    def compare_ticker(self, sector_key: str, ticker: str) -> tuple[float | None, str]:
        """`ticker`'ın çarpanını sektör medyanıyla kıyaslar → (değer, cümle)."""
        snap = self.snapshot(sector_key)
        metric = next((p for p in snap.peers if p.ticker == ticker), None)
        if metric is None:
            return None, "—"
        for attr in ("pe", "pb", "ev_ebitda"):
            value = getattr(metric, attr)
            if value is not None:
                return value, snap.stance(attr, value)
        return None, "—"

    # ---- iç yardımcılar ----------------------------------------------------

    def _fetch(self, ticker: str, company: str) -> PeerMetric | None:
        symbol = f"{ticker}.IS"
        price, change = self._quote(symbol)
        fund = self._fundamentals(symbol) if self._ensure_crumb() else {}
        if price is None and not fund:
            log.debug("Peer hissesi alınamadı: %s", ticker)
            return None
        return PeerMetric(
            ticker=ticker,
            name=company,
            price=price,
            change_pct=change,
            pe=fund.get("pe"),
            pb=fund.get("pb"),
            ev_ebitda=fund.get("ev_ebitda"),
            dividend_yield=fund.get("dividend_yield"),
            ebitda_margin=fund.get("ebitda_margin"),
            roe=fund.get("roe"),
            market_cap=fund.get("market_cap"),
        )

    def _quote(self, symbol: str) -> tuple[float | None, float | None]:
        """Chart API'sinden fiyat + günlük değişim (crumb gerekmez)."""
        try:
            resp = self._session.get(
                CHART_URL.format(symbol=symbol), timeout=settings.http_timeout
            )
            resp.raise_for_status()
            meta = resp.json()["chart"]["result"][0]["meta"]
        except (requests.RequestException, ValueError, KeyError, IndexError, TypeError) as exc:
            log.debug("Chart verisi alınamadı (%s): %s", symbol, exc)
            return None, None
        price = meta.get("regularMarketPrice")
        prev = meta.get("chartPreviousClose") or meta.get("previousClose")
        change = None
        if price and prev:
            change = (price - prev) / prev * 100
        return (float(price) if price is not None else None), change

    def _ensure_crumb(self) -> bool:
        """Cookie + crumb akışı — bir kez denenir, başarısızsa tekrar denemez."""
        if self._crumb:
            return True
        if self._crumb_failed:
            return False
        try:
            # fc.yahoo.com çerezi set eder (yanıtın içeriği önemli değil)
            self._session.get("https://fc.yahoo.com", timeout=10)
            resp = self._session.get(CRUMB_URL, timeout=10)
            resp.raise_for_status()
            crumb = resp.text.strip()
            if not crumb or "<html" in crumb.lower():
                raise ValueError("crumb gövdesi geçersiz")
            self._crumb = crumb
            log.info("Yahoo crumb alındı — çarpanlar etkin.")
            return True
        except (requests.RequestException, ValueError) as exc:
            self._crumb_failed = True
            log.warning("Yahoo crumb alınamadı (%s); çarpanlar kapalı.", exc)
            return False

    def _fundamentals(self, symbol: str) -> dict[str, float]:
        """quoteSummary → çarpanlar. Hata/eksik veri → boş dict (kıyas devam eder)."""
        try:
            resp = self._session.get(
                QUOTE_SUMMARY_URL.format(symbol=symbol),
                params={"modules": _YF_MODULES, "crumb": self._crumb},
                timeout=settings.http_timeout,
            )
            if resp.status_code == 401:
                self._crumb_failed = True
                log.warning("Yahoo quoteSummary 401 (Invalid Crumb); çarpanlar kapalı.")
                return {}
            resp.raise_for_status()
            result = resp.json()["quoteSummary"]["result"][0]
        except (requests.RequestException, ValueError, KeyError, IndexError, TypeError) as exc:
            log.debug("Çarpan verisi alınamadı (%s): %s", symbol, exc)
            return {}

        out: dict[str, float] = {}
        detail = result.get("summaryDetail") or {}
        stats = result.get("defaultKeyStatistics") or {}
        fin = result.get("financialData") or {}

        pe = _raw(detail.get("trailingPE"))
        # Yahoo, zarar/aşırı volatil dönemlerde uç F/K üretir (ör. 512) — bunlar
        # medyanı bozar; makul üst sınır (200) dışında bırakılır.
        out["pe"] = pe if pe is not None and pe <= 200 else None
        out["pb"] = _raw(stats.get("priceToBook"))
        out["ev_ebitda"] = _raw(stats.get("enterpriseToEbitda"))
        out["market_cap"] = _raw(detail.get("marketCap"))
        # Yahoo bunları kesir olarak verir (0.045 = %4,5) — yüzdeye çevir.
        out["dividend_yield"] = _pct(detail.get("dividendYield"))
        out["ebitda_margin"] = _pct(fin.get("ebitdaMargins"))
        out["roe"] = _pct(fin.get("returnOnEquity"))
        return {k: v for k, v in out.items() if v is not None}

    def _sample(self, sector_key: str, name: str) -> PeerSnapshot:
        rows = _SAMPLE.get(sector_key)
        if not rows:
            rows = [
                (ticker, company, 100.0, 8.0, 1.2)
                for ticker, company in list(PEER_GROUPS[sector_key].items())[:4]
            ]
        peers = [
            PeerMetric(
                ticker=t, name=n, price=p, change_pct=None,
                pe=pe, pb=pb, ev_ebitda=None, dividend_yield=None,
            )
            for (t, n, p, pe, pb) in rows
        ]
        return PeerSnapshot(
            sector_key=sector_key, sector_name=name, peers=peers,
            sample=True,
            notes=["Hiçbir veri kaynağı dönmedi; ÖRNEK veri gösteriliyor."],
        )


# `snapshot()` içinde Türkçe ad için sektör anahtarını BIST koduna eşler.
_SECTOR_CODE: dict[str, str] = {
    "bankacilik": "XBANK",
    "teknoloji": "XUTEK",
    "sanayi": "XUSIN",
    "holding": "XHOLD",
    "perakende_gida": "XGIDA",
    "enerji": "XELKT",
    "otomotiv_ulasim": "XULAS",
}


def _raw(entry: object) -> float | None:
    """Yahoo `{raw, fmt}` sarımından ham sayıyı alır."""
    if isinstance(entry, dict):
        entry = entry.get("raw")
    if entry is None:
        return None
    try:
        value = float(entry)
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


def _pct(entry: object) -> float | None:
    """Kesir biçimindeki oranı yüzdeye çevirir (0.045 → 4.5)."""
    value = _raw(entry)
    if value is None:
        return None
    return value * 100 if value <= 1 else value


def available_groups() -> list[str]:
    return sorted(PEER_GROUPS)


def sector_for_today() -> str:
    """Bugünün peer sektörü — ISO haftasına göre döner.

    Haftalık işler aynı sektörü tekrarlamasın; örneklem zamanla zenginleşsin.
    `scheduler` (uzun süreç) ve GitHub Actions workflow'u bu fonksiyonu paylaşır.
    """
    from datetime import date

    keys = sorted(PEER_GROUPS)
    return keys[date.today().isocalendar().week % len(keys)]
