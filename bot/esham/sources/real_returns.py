"""TÜRİB fiyat serilerinin USD / EUR cinsinden getirisi (TCMB resmî döviz kurları).

Yüksek enflasyon ortamında nominal TL fiyat artışları aldatıcıdır; döviz cinsinden getiri bunun için
kaynaklı, doğrulanabilir bir göstergedir.

Kaynak: TCMB günlük döviz kurları XML'i (``https://www.tcmb.gov.tr/kurlar/YYYYMM/DDMMYYYY.xml``,
anahtarsız, herkese açık). Döviz alış (``ForexBuying``) kuru kullanılır; resmî tatil/hafta sonu için
bir önceki iş gününün bülteni alınır ve kullanılan bülten tarihi çıktıda yazılır.
Atıf: "Kaynak: T.C. Merkez Bankası (tcmb.gov.tr)".

Eski sürümdeki kodun içine gömülü yıllık kur / TÜFE katsayısı tablosu (kaynaksız sayılar) KALDIRILDI.
TÜFE ile arındırılmış reel getiri için anahtarsız, kararlı bir kaynak doğrulanamadığından (TCMB EVDS anahtar
ister; TÜİK tabloları programatik değil) bu sürümde üretilmez ve yayınlanmaz.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any

import requests

from ..config import get_logger, settings
from ..http import retry_get
from ..sources.turib import TuribSource

log = get_logger(__name__)

TCMB_URL = "https://www.tcmb.gov.tr/kurlar/{ym}/{dmy}.xml"
TCMB_SOURCE_URL = "https://www.tcmb.gov.tr/kurlar/kurlar_tr.html"
CITATION = "Kaynak: T.C. Merkez Bankası (tcmb.gov.tr) döviz kurları; TÜRİB (turib.com.tr) fiyatları."
RATE_BASIS = "ForexBuying"
MAX_LOOKBACK_DAYS = 7  # hafta sonu + uzun tatil payı


@dataclass(frozen=True)
class TcmbRate:
    date: str  # bültenin tarihi (YYYY-MM-DD)
    usd: float
    eur: float


class FxUnavailable(RuntimeError):
    """İstenen tarih için TCMB bülteni alınamadı; kur uydurulmaz."""


def parse_tcmb_xml(content: bytes | str) -> TcmbRate | None:
    """TCMB günlük XML'i -> USD/EUR döviz alış kuru. Eksik/bozuk bültende None."""
    try:
        root = ET.fromstring(content)
    except ET.ParseError:
        return None
    raw_date = root.get("Date") or ""  # "MM/DD/YYYY"
    try:
        bulletin = datetime.strptime(raw_date, "%m/%d/%Y").date()
    except ValueError:
        return None
    rates: dict[str, float] = {}
    for cur in root.iter("Currency"):
        code = cur.get("CurrencyCode")
        if code not in ("USD", "EUR"):
            continue
        unit = (cur.findtext("Unit") or "1").strip() or "1"
        raw = (cur.findtext(RATE_BASIS) or "").strip()
        try:
            rates[code] = float(raw) / float(unit)
        except ValueError:
            return None
    if "USD" not in rates or "EUR" not in rates or rates["USD"] <= 0 or rates["EUR"] <= 0:
        return None
    return TcmbRate(bulletin.isoformat(), rates["USD"], rates["EUR"])


class TcmbFxSource:
    """İstenen güne en yakın (önceki) TCMB bülteni; süreç içinde önbellekli."""

    def __init__(self) -> None:
        self._cache: dict[str, TcmbRate | None] = {}

    def _fetch_day(self, day: date) -> TcmbRate | None:
        key = day.isoformat()
        if key in self._cache:
            return self._cache[key]
        url = TCMB_URL.format(ym=day.strftime("%Y%m"), dmy=day.strftime("%d%m%Y"))
        rate: TcmbRate | None = None
        try:
            resp = retry_get(url, timeout=settings.http_timeout)
            if resp.status_code == 200:
                rate = parse_tcmb_xml(resp.content)
        except requests.RequestException as exc:
            log.warning("TCMB kur bülteni alınamadı %s: %s", key, exc)
        self._cache[key] = rate
        return rate

    def rate_on_or_before(self, date_str: str) -> TcmbRate:
        day = date.fromisoformat(date_str[:10])
        for back in range(MAX_LOOKBACK_DAYS + 1):
            rate = self._fetch_day(day - timedelta(days=back))
            if rate:
                return rate
        raise FxUnavailable(f"{date_str} için TCMB kuru bulunamadı (son {MAX_LOOKBACK_DAYS} gün denendi).")


@dataclass
class RealReturnReport:
    urun_grubu: str
    baslangic_tarihi: str
    bitis_tarihi: str
    islem_gun_sayisi: int
    ilk_fiyat_tl: float
    son_fiyat_tl: float
    ilk_fiyat_usd: float
    son_fiyat_usd: float
    ilk_fiyat_eur: float
    son_fiyat_eur: float
    nominal_tl_getiri_pct: float
    usd_getiri_pct: float
    eur_getiri_pct: float
    kur_tarihi_baslangic: str
    kur_tarihi_bitis: str
    usd_try_baslangic: float
    usd_try_bitis: float
    eur_try_baslangic: float
    eur_try_bitis: float
    analiz_yorumu: str
    kaynak: str = CITATION
    kaynak_url: str = TCMB_SOURCE_URL
    cekilis_zamani: str = ""


def compute_report(urun_grubu: str, seri: list[dict[str, Any]], r0: TcmbRate, r1: TcmbRate, fetched_at: str) -> RealReturnReport:
    """Saf hesap: TÜRİB serisinin ilk/son fiyatı ve iki TCMB bülteninden getiriler."""
    ilk, son = seri[0], seri[-1]
    ilk_tl = ilk["avg"] if ilk["avg"] > 0 else ilk["close"]
    son_tl = son["avg"] if son["avg"] > 0 else son["close"]
    if ilk_tl <= 0 or son_tl <= 0:
        raise ValueError(f"'{urun_grubu}' için geçerli fiyat yok.")
    ilk_usd, son_usd = ilk_tl / r0.usd, son_tl / r1.usd
    ilk_eur, son_eur = ilk_tl / r0.eur, son_tl / r1.eur
    pct = lambda a, b: round((b - a) / a * 100, 2)  # noqa: E731
    tl, usd, eur = pct(ilk_tl, son_tl), pct(ilk_usd, son_usd), pct(ilk_eur, son_eur)
    yorum = (
        f"'{urun_grubu}' {ilk['date']} - {son['date']} döneminde TL bazında %{tl:.1f}, "
        f"USD bazında %{usd:.1f}, EUR bazında %{eur:.1f} değişti (TCMB döviz alış kuru; "
        f"{r0.date} ve {r1.date} bültenleri). TÜFE ile arındırılmış getiri bu veri setinde yoktur."
    )
    return RealReturnReport(
        urun_grubu=urun_grubu,
        baslangic_tarihi=ilk["date"],
        bitis_tarihi=son["date"],
        islem_gun_sayisi=len(seri),
        ilk_fiyat_tl=round(ilk_tl, 2),
        son_fiyat_tl=round(son_tl, 2),
        ilk_fiyat_usd=round(ilk_usd, 4),
        son_fiyat_usd=round(son_usd, 4),
        ilk_fiyat_eur=round(ilk_eur, 4),
        son_fiyat_eur=round(son_eur, 4),
        nominal_tl_getiri_pct=tl,
        usd_getiri_pct=usd,
        eur_getiri_pct=eur,
        kur_tarihi_baslangic=r0.date,
        kur_tarihi_bitis=r1.date,
        usd_try_baslangic=r0.usd,
        usd_try_bitis=r1.usd,
        eur_try_baslangic=r0.eur,
        eur_try_bitis=r1.eur,
        analiz_yorumu=yorum,
        cekilis_zamani=fetched_at,
    )


class RealReturnsCalculator:
    """TÜRİB serilerini TCMB kurlarıyla USD/EUR cinsine çeviren motor (kur yoksa hata verir, uydurmaz)."""

    def __init__(self, turib_source: TuribSource | None = None, fx: TcmbFxSource | None = None) -> None:
        self.turib_source = turib_source or TuribSource()
        self.fx = fx or TcmbFxSource()

    def calculate(
        self,
        urun_grubu: str,
        baslangic: str | None = None,
        bitis: str | None = None,
    ) -> RealReturnReport:
        seri = self.turib_source.fetch_product_series(urun_grubu)
        if not seri:
            raise ValueError(f"'{urun_grubu}' için fiyat serisi bulunamadı.")
        if baslangic:
            seri = [m for m in seri if m["date"] >= baslangic]
        if bitis:
            seri = [m for m in seri if m["date"] <= bitis]
        if len(seri) < 2:
            raise ValueError(f"'{urun_grubu}' için belirtilen dönemde yeterli fiyat verisi yok.")
        r0 = self.fx.rate_on_or_before(seri[0]["date"])
        r1 = self.fx.rate_on_or_before(seri[-1]["date"])
        return compute_report(urun_grubu, seri, r0, r1, datetime.now(timezone.utc).isoformat(timespec="seconds"))
