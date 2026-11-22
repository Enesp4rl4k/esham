"""TCMB EVDS (Elektronik Veri Dağıtım Sistemi) istemcisi — YALNIZCA ``EVDS_API_KEY`` ortam değişkeni varsa çalışır.

Anahtar yoksa hiçbir şey çekilmez ve hiçbir sayı üretilmez (bölüm sayfada görünmez). Anahtar değeri:
  - yalnızca ``key`` İSTEK BAŞLIĞINDA gönderilir (EVDS 'Required request header key' ile doğrular); URL'ye ASLA girmez,
  - hiçbir log satırında, hata iletisinde, önbellek/veri dosyasında yer almaz (hatalar anahtarsız, kısa nedenle yeniden fırlatılır).

Yanıt biçimi (EVDS dokümantasyonu): ``{"totalCount": N, "items": [{"Tarih": "01-09-2026", "TP_FG_J0": "2234.5",
"UNIXTIME": {...}}]}``; seri kodundaki noktalar alan adında altçizgi olur. Aylık serilerde ``Tarih`` "2026-9" biçiminde de
gelebilir; ikisi de desteklenir, tanınmayan biçim atlanır (tahmin yok).

Seri kodları ``INDICATORS`` içindedir ve anahtarla İLK çalıştırmada doğrulanmalıdır (EVDS seri listesi oturum ister):
yanlış kod hata/boş yanıt verir, bölüm gizli kalır; uydurma değer çıkmaz.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import date
from typing import Any, Callable

import requests

from ..config import default_headers, get_logger

log = get_logger(__name__)

ENV_KEY = "EVDS_API_KEY"
BASE_URL = "https://evds3.tcmb.gov.tr/igmevdsms-dis/"
SOURCE_URL = "https://evds3.tcmb.gov.tr/"
ATTRIBUTION = "Kaynak: T.C. Merkez Bankası, Elektronik Veri Dağıtım Sistemi (EVDS)"


class EvdsError(RuntimeError):
    """Anahtar içermeyen, kısa hata nedeni."""


@dataclass(frozen=True)
class EvdsIndicator:
    id: str
    label: str
    series: str
    unit: str
    kind: str  # "level" | "yoy" (aynı dönemin 12 ay öncesine göre % değişim)
    note: str


INDICATORS: tuple[EvdsIndicator, ...] = (
    EvdsIndicator("cpi_yoy", "TÜFE yıllık değişim", "TP.FG.J0", "%", "yoy",
                  "TÜFE genel endeksinin (TP.FG.J0) 12 ay öncesine göre değişimi; iki değer de EVDS'den, oran bot tarafından hesaplanır."),
    EvdsIndicator("reer", "Reel efektif döviz kuru (TÜFE bazlı)", "TP.RK.T1.Y", "endeks", "level",
                  "Endeksin yükselmesi TL'nin reel olarak değerlendiği, düşmesi değer kaybettiği anlamına gelir (TCMB tanımı)."),
)


def api_key() -> str | None:
    key = (os.getenv(ENV_KEY) or "").strip()
    return key or None


def build_url(series: str, start: date, end: date) -> str:
    """Anahtarsız URL (log'a yazılabilir)."""
    return f"{BASE_URL}series={series}&startDate={start.strftime('%d-%m-%Y')}&endDate={end.strftime('%d-%m-%Y')}&type=json"


def _parse_date(value: Any) -> date | None:
    s = str(value or "").strip()
    m = re.fullmatch(r"(\d{1,2})-(\d{1,2})-(\d{4})", s)
    if m:
        try:
            return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        except ValueError:
            return None
    m = re.fullmatch(r"(\d{4})-(\d{1,2})", s)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), 1)
        except ValueError:
            return None
    return None


def _parse_value(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value or "").strip()
    return float(s) if re.fullmatch(r"-?\d+(\.\d+)?", s) else None


def parse_series(doc: Any, series: str) -> tuple[list[tuple[date, float]], int]:
    """EVDS JSON → ([(tarih, değer)] eskiden yeniye, atlanan satır sayısı)."""
    if not isinstance(doc, dict) or not isinstance(doc.get("items"), list):
        raise EvdsError("EVDS yanıtı beklenen biçimde değil")
    field = series.replace(".", "_")
    out: list[tuple[date, float]] = []
    skipped = 0
    for it in doc["items"]:
        if not isinstance(it, dict) or field not in it:
            skipped += 1
            continue
        d, v = _parse_date(it.get("Tarih")), _parse_value(it.get(field))
        if d is None or v is None:
            skipped += 1
            continue
        out.append((d, v))
    out.sort()
    return out, skipped


def fetch_series(series: str, start: date, end: date, key: str,
                 get: Callable[..., requests.Response] = requests.get) -> tuple[list[tuple[date, float]], int]:
    """Anahtar yalnızca ``key`` başlığında; hata iletilerinde anahtar/başlık yok."""
    headers = {**default_headers(), "key": key}
    try:
        resp = get(build_url(series, start, end), headers=headers, timeout=40)
    except requests.RequestException as exc:
        raise EvdsError(f"EVDS isteği başarısız ({type(exc).__name__}): {series}") from None
    if resp.status_code != 200:
        raise EvdsError(f"EVDS HTTP {resp.status_code}: {series}")
    try:
        doc = resp.json()
    except ValueError:
        raise EvdsError(f"EVDS yanıtı JSON değil: {series}") from None
    return parse_series(doc, series)


def compute(ind: EvdsIndicator, points: list[tuple[date, float]]) -> dict[str, Any]:
    """Seriden gösterge değeri. ``yoy`` için TAM 12 ay önceki gözlem gerekir; yoksa EvdsError (tahmin/enterpolasyon yok)."""
    if not points:
        raise EvdsError(f"EVDS serisi boş: {ind.series}")
    last_d, last_v = points[-1]
    if ind.kind == "level":
        return {"value": round(last_v, 4), "asOf": last_d.isoformat()}
    prior = {(d.year, d.month): v for d, v in points}.get((last_d.year - 1, last_d.month))
    if prior is None or prior <= 0:
        raise EvdsError(f"12 ay önceki gözlem yok: {ind.series}")
    return {"value": round((last_v / prior - 1) * 100, 2), "asOf": last_d.isoformat()}
