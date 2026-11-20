"""TEFAS (Takasbank Fon Bilgilendirme Platformu) kaynağı: fon listesi, günlük fiyat, getiri, büyüklük.

Erişim notları (Kas 2026'da elle test edildi):
- Eski ``/api/DB/BindHistoryInfo`` uç noktası KAPALI ("Method not found or disabled"). Yeni site (Next.js) JSON
  uç noktalarını ``https://www.tefas.gov.tr/api/funds/<yöntem>`` altında POST ile sunar; çerez/CSRF gerekmez.
- HTML sayfaları F5 JS-challenge arkasında; ``/api/*`` yolları düz ``requests`` ile açılıyor.
- Hız sınırı sert: ardışık ~10 hızlı istekten sonra 429 (``ERR-224``) ve ardından HTML "Erişim Engellendi"
  sayfası dönüyor. Bu yüzden istemci istekler arası bekler (``min_interval``) ve engeli ``TefasBlocked`` ile bildirir.
- Kullanım şartı: TEFAS SSS'si "API paylaşımı yapılmamaktadır" diyor; veri okur-yazarlık amaçlı yayımlanıyor.
  Bu modül belgelenmemiş uç noktaları kullanır → nazik hız, önbellek, kaynak atfı ("Kaynak: TEFAS") ve
  hata toleransı (job eski veriyi korur) zorunludur. Kamuya açık veri; yine de hukuki görüş önerilir.
- Portföy dağılımı (varlık türü %) yalnızca fon sayfasının sunucu tarafı render'ında geliyor (JS-challenge
  arkasında); JSON ucu bulunamadı → v1'de ``allocation`` boştur (bkz. publish_funds.py).
- Yedek kaynak: ``fundturkey.com.tr`` (TEFAS'ın İngilizce alan adı, aynı arka uç) ana alan engellenirse denenir.
  Üçüncü taraf siteler (fintables: Cloudflare 403; fonbul: yalnızca HTML) kazıma gerektirdiği için eklenmedi.
"""
from __future__ import annotations

import math
import statistics
import time
from datetime import date, datetime, timedelta
from typing import Any

import requests

from ..config import get_logger

log = get_logger(__name__)

BASES = (
    "https://www.tefas.gov.tr/api/funds",
    "https://www.fundturkey.com.tr/api/funds",  # yedek alan adı (aynı arka uç)
)
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; EshamBot/1.0; +https://esham.pages.dev/yontem)",
    "Content-Type": "application/json",
    "Accept": "application/json",
}
TRADING_DAYS = 252


class TefasError(RuntimeError):
    """TEFAS yanıtı alınamadı ya da beklenmedik biçimde."""


class TefasBlocked(TefasError):
    """Hız sınırı / WAF engeli (429 ya da HTML 'Erişim Engellendi')."""


class TefasClient:
    def __init__(self, min_interval: float = 0.4, timeout: float = 60.0, bases: tuple[str, ...] = BASES) -> None:
        self.min_interval = min_interval
        self.timeout = timeout
        self.bases = bases
        self._last = 0.0
        self._session = requests.Session()
        self._session.headers.update(HEADERS)
        self._base_idx = 0

    def _wait(self) -> None:
        gap = self.min_interval - (time.monotonic() - self._last)
        if gap > 0:
            time.sleep(gap)
        self._last = time.monotonic()

    def post(self, method: str, body: dict[str, Any], retries: int = 3) -> list[dict[str, Any]]:
        """``resultList`` döndürür. Engelde yedek alan adına, sonra bekleyerek yeniden dener."""
        last_err: Exception | None = None
        for attempt in range(retries):
            base = self.bases[self._base_idx % len(self.bases)]
            self._wait()
            try:
                resp = self._session.post(f"{base}/{method}", json=body, timeout=self.timeout)
                data = _parse_response(resp)
                return data
            except TefasBlocked as exc:
                last_err = exc
                self._base_idx += 1  # yedek alan adına geç
                wait = 5.0 * (attempt + 1)
                log.warning("TEFAS engeli (%s) → %s; %.0f sn sonra yeniden (%d/%d)", method, exc, wait, attempt + 1, retries)
                time.sleep(wait)
            except (requests.RequestException, ValueError) as exc:
                last_err = exc
                time.sleep(2.0 * (attempt + 1))
        if isinstance(last_err, TefasBlocked):
            raise last_err
        raise TefasError(f"{method}: {last_err}")


def _parse_response(resp: requests.Response) -> list[dict[str, Any]]:
    if resp.status_code == 429:
        raise TefasBlocked("HTTP 429 (hız sınırı)")
    ctype = resp.headers.get("content-type", "")
    if "json" not in ctype:
        raise TefasBlocked(f"JSON değil ({resp.status_code}, {ctype or 'içerik türü yok'})")
    payload = resp.json()
    if payload.get("faultCode"):
        raise TefasBlocked(f"{payload.get('faultCode')}: {payload.get('faultString')}")
    if payload.get("errorMessage"):
        raise TefasError(str(payload["errorMessage"]))
    return payload.get("resultList") or []


# ---------------------------------------------------------------- saf yardımcılar (test edilir)
def _num(v: Any) -> float | None:
    try:
        if v is None or v == "":
            return None
        f = float(str(v).replace(",", ".")) if isinstance(v, str) else float(v)
        return f if math.isfinite(f) else None
    except (TypeError, ValueError):
        return None


def normalize_return_row(row: dict[str, Any]) -> dict[str, Any]:
    """``fonGetiriBazliBilgiGetir`` satırı → sade fon kaydı (getiriler % olarak)."""
    return {
        "code": str(row["fonKodu"]).upper(),
        "name": str(row.get("fonUnvan") or "").strip(),
        "category": str(row.get("fonTurAciklama") or "").replace(" Şemsiye Fonu", "").strip() or "Diğer",
        "tradable": bool(row.get("tefasDurum", True)),
        "risk": int(r) if (r := _num(row.get("riskDegeri"))) else None,
        "returns": {
            "1m": _num(row.get("getiri1a")), "3m": _num(row.get("getiri3a")), "6m": _num(row.get("getiri6a")),
            "ytd": _num(row.get("getiriyb")), "1y": _num(row.get("getiri1y")),
            "3y": _num(row.get("getiri3y")), "5y": _num(row.get("getiri5y")),
        },
    }


def parse_prices(rows: list[dict[str, Any]]) -> list[tuple[str, float]]:
    """``fonFiyatBilgiGetir`` → [(tarih, fiyat)] eskiden yeniye; sıfır/boş fiyatlar atılır, tarih tekilleştirilir."""
    seen: dict[str, float] = {}
    for r in rows:
        d, p = r.get("tarih"), _num(r.get("fiyat"))
        if d and p and p > 0:
            seen[str(d)[:10]] = p
    return sorted(seen.items())


def thin_series(prices: list[tuple[str, float]], recent_days: int = 366, step: int = 5) -> list[list[Any]]:
    """Son ``recent_days`` günün tamamı + eski dönemden her ``step``. noktada bir örnek (dosya boyutu için)."""
    if not prices:
        return []
    cutoff = (date.fromisoformat(prices[-1][0]) - timedelta(days=recent_days)).isoformat()
    old = [p for p in prices if p[0] < cutoff]
    keep = old[::step] + [p for p in prices if p[0] >= cutoff]
    return [[d, round(v, 6)] for d, v in keep]


def period_return(prices: list[tuple[str, float]], days: int) -> float | None:
    """Son fiyata göre ``days`` takvim günü önceki (ya da en yakın önceki) fiyatla yüzde getiri."""
    if len(prices) < 2:
        return None
    last_d = date.fromisoformat(prices[-1][0])
    target = (last_d - timedelta(days=days)).isoformat()
    if prices[0][0] > target:
        return None  # yeterli geçmiş yok
    base = next((p for d, p in reversed(prices) if d <= target), None)
    return round((prices[-1][1] / base - 1) * 100, 4) if base else None


def risk_metrics(prices: list[tuple[str, float]], rf_annual_pct: float | None = None, days: int = 365) -> dict[str, float | None]:
    """Son ``days`` günde yıllıklandırılmış oynaklık (%), maks. düşüş (%) ve Sharpe.

    Sharpe = (yıllık getiri − risksiz) / oynaklık; risksiz = TCMB ağırlıklı ortalama mevduat faizi (TEFAS'ın verdiği
    1Y değeri). Gözlem sayısı < 30 ise hesaplanmaz (None).
    """
    empty: dict[str, float | None] = {"volatility": None, "max_drawdown": None, "sharpe": None}
    if len(prices) < 31:
        return empty
    cutoff = (date.fromisoformat(prices[-1][0]) - timedelta(days=days)).isoformat()
    win = [p for p in prices if p[0] >= cutoff]
    if len(win) < 31:
        return empty
    rets = [win[i][1] / win[i - 1][1] - 1 for i in range(1, len(win))]
    vol = statistics.pstdev(rets) * math.sqrt(TRADING_DAYS) * 100
    peak, mdd = win[0][1], 0.0
    for _, v in win:
        peak = max(peak, v)
        mdd = min(mdd, v / peak - 1)
    span_days = (date.fromisoformat(win[-1][0]) - date.fromisoformat(win[0][0])).days or 1
    ann = ((win[-1][1] / win[0][1]) ** (365 / span_days) - 1) * 100
    sharpe = (ann - rf_annual_pct) / vol if (rf_annual_pct is not None and vol > 0) else None
    return {"volatility": round(vol, 2), "max_drawdown": round(mdd * 100, 2), "sharpe": round(sharpe, 2) if sharpe is not None else None}


def real_return(nominal_pct: float | None, inflation_pct: float | None) -> float | None:
    """Reel getiri = (1+nominal)/(1+enflasyon) − 1 (yüzde). Başka bir varlığa (USD) karşı getiride de aynı formül."""
    if nominal_pct is None or inflation_pct is None:
        return None
    return round(((1 + nominal_pct / 100) / (1 + inflation_pct / 100) - 1) * 100, 4)


def rank_in_categories(funds: list[dict[str, Any]], key: str = "1y") -> dict[str, tuple[int, int]]:
    """Kategori içi sıra (1 = en yüksek ``key`` getirisi). Getirisi olmayan fonlar sıralanmaz."""
    by_cat: dict[str, list[tuple[float, str]]] = {}
    for f in funds:
        v = f["returns"].get(key)
        if v is not None:
            by_cat.setdefault(f["category"], []).append((v, f["code"]))
    out: dict[str, tuple[int, int]] = {}
    for rows in by_cat.values():
        rows.sort(key=lambda x: -x[0])
        for i, (_, code) in enumerate(rows, 1):
            out[code] = (i, len(rows))
    return out


# ---------------------------------------------------------------- ağ çağrıları
def _d(dt: date) -> str:
    return dt.strftime("%Y%m%d")


def fetch_return_table(client: TefasClient, fund_type: str = "YAT") -> list[dict[str, Any]]:
    """Tüm fonların getiri tablosu (tek çağrı, ~1.000+ satır). ``fund_type``: YAT (menkul), EMK (emeklilik), BYF."""
    body = {
        "dil": "TR", "fonTipi": fund_type, "kurucuKodu": None, "sfonTurKod": None, "fonTurAciklama": None, "islem": 1,
        "fonTurKod": None, "fonGrubu": None, "donemGetiri1a": "1", "donemGetiri3a": "1", "donemGetiri6a": "1",
        "donemGetiri1y": "1", "donemGetiriyb": "1", "donemGetiri3y": "1", "donemGetiri5y": "1", "basTarih": None,
        "bitTarih": None, "calismaTipi": 2, "getiriOrani": "1",
    }
    rows = [normalize_return_row(r) for r in client.post("fonGetiriBazliBilgiGetir", body) if r.get("fonKodu")]
    return [r for r in rows if r["tradable"]]


def fetch_sizes(client: TefasClient, fund_type: str = "YAT", lookback_days: int = 7) -> dict[str, dict[str, float | None]]:
    """Fon başına son portföy büyüklüğü (TL) ve pay adedi — tek çağrı."""
    today = date.today()
    body = {
        "dil": "TR", "fonTipi": fund_type, "kurucuKodu": None, "sfonTurKod": None, "fonTurAciklama": None, "islem": 1,
        "fonTurKod": None, "fonGrubu": None, "basTarih": _d(today - timedelta(days=lookback_days)), "bitTarih": _d(today),
        "calismaTipi": 2, "fonKodu": None,
    }
    return {
        str(r["fonKodu"]).upper(): {"aum": _num(r.get("sonPortfoyDegeri")), "units": _num(r.get("sonPayAdedi"))}
        for r in client.post("fonBuyuklukBazliBilgiGetir", body) if r.get("fonKodu")
    }


def fetch_fees(client: TefasClient, fund_type: str = "YAT") -> dict[str, float | None]:
    """Fon başına uygulanan yıllık yönetim ücreti (%) — tek çağrı. Bulunamazsa boş sözlük (zorunlu değil)."""
    body = {
        "dil": "TR", "fonTipi": fund_type, "kurucuKodu": None, "sfonTurKod": None, "fonTurAciklama": None, "islem": 1,
        "fonTurKod": None, "fonGrubu": None, "basTarih": None, "bitTarih": None, "calismaTipi": 2,
    }
    return {str(r["fonKodu"]).upper(): _num(r.get("uygulananYu1Y")) for r in client.post("fonYonetimBazliBilgiGetir", body) if r.get("fonKodu")}


def fetch_fund_info(client: TefasClient, code: str) -> dict[str, Any] | None:
    """Son fiyat, günlük getiri, yatırımcı sayısı, pazar payı (fon başına 1 çağrı)."""
    rows = client.post("fonBilgiGetir", {"fonKodu": code})
    if not rows:
        return None
    r = rows[0]
    return {
        "price": _num(r.get("sonFiyat")), "daily": _num(r.get("gunlukGetiri")), "aum": _num(r.get("portBuyukluk")),
        "units": _num(r.get("payAdet")), "investors": int(v) if (v := _num(r.get("yatirimciSayi"))) is not None else None,
        "market_share": _num(r.get("pazarPayi")), "category_name": r.get("fonKategori"),
    }


def fetch_prices(client: TefasClient, code: str, months: int = 60) -> list[tuple[str, float]]:
    """Günlük fiyat geçmişi (``periyod`` ay)."""
    return parse_prices(client.post("fonFiyatBilgiGetir", {"fonKodu": code, "dil": "TR", "periyod": months}))


def fetch_benchmarks(client: TefasClient, code: str) -> dict[str, float]:
    """1Y kıyas getirileri (yüzde): mevduat, TÜFE, USD, EUR, altın, BIST100/30. Fon başına değil genel; tek fon üzerinden alınır."""
    names = {"MEVDUAT FAIZI": "deposit", "TUFE": "cpi", "USD": "usd", "EUR": "eur", "ALTIN": "gold", "BIST100": "bist100", "BIST30": "bist30"}
    out: dict[str, float] = {}
    for r in client.post("fonProfilDtyGetir", {"dil": "TR", "fonKodu": code, "periyod": "12"}):
        key, v = names.get(str(r.get("fonKodu"))), _num(r.get("fonTurGetiri"))
        if key and v is not None:
            out[key] = round(v * 100, 4)  # API kesir döndürür (0,4054 = %40,54)
    return out


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")
