"""Makro göstergeler → ``web/public/data/macro-indicators.json``.

Her gösterge: değer + birim + veri tarihi + kaynak + kaynak bağlantısı + çekiliş zamanı.
  - TCMB politika faizi (1 hafta repo): TCMB sayfası, anahtarsız. Veri tarihi = sayfadaki SON DEĞİŞİKLİK tarihi.
  - USD/TRY 30 gün / 365 gün değişimi: TCMB günlük döviz XML'i (anahtarsız). Tarih = kullanılan bülten tarihleri.
  - EVDS göstergeleri (TÜFE yıllık, REK): yalnızca ``EVDS_API_KEY`` varsa. Yoksa o göstergeler hiç yazılmaz.
Bir gösterge alınamazsa önceki dosyadaki son iyi değer KENDİ tarihiyle ``stale: true`` olarak taşınır; hiç yoksa yazılmaz.
EVDS hataları (anahtar yok, HTTP hatası, boş/eksik seri) ``evdsIssues`` alanına seri adı ve nedenle yazılır;
``data-status`` bunları gösterir. Tahmin/skor/olasılık YOK: yalnızca gözlenen değerler ve basit, açıklanmış oranlar.
"""
from __future__ import annotations

import json
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

import requests

from ..config import default_headers, get_logger, settings
from ..sources import tcmb_evds as EV
from ..sources.real_returns import FxUnavailable, TcmbFxSource

log = get_logger(__name__)
DATA_DIR = Path(__file__).resolve().parents[3] / "web" / "public" / "data"
OUT_FILE = "macro-indicators.json"
POLICY_URL = ("https://www.tcmb.gov.tr/wps/wcm/connect/TR/TCMB+TR/Main+Menu/Temel+Faaliyetler/Para+Politikasi/"
              "Merkez+Bankasi+Faiz+Oranlari/1+Hafta+Repo")
FX_URL = "https://www.tcmb.gov.tr/kurlar/kurlar_tr.html"
TCMB_ATTRIBUTION = "Kaynak: T.C. Merkez Bankası (tcmb.gov.tr)"


class MacroParseError(ValueError):
    pass


def parse_policy_rate(raw: bytes) -> dict[str, Any]:
    """TCMB '1 Hafta Repo' sayfası → son değişiklik (tarih + borç verme faizi). Biçim tanınmazsa MacroParseError."""
    from bs4 import BeautifulSoup

    try:
        html = raw.decode("utf-8")
    except UnicodeDecodeError:
        html = raw.decode("iso-8859-9")
    table = BeautifulSoup(html, "html.parser").select_one("table#midTable")
    if table is None:
        raise MacroParseError("faiz tablosu (#midTable) yok")
    rows = [[td.get_text(" ", strip=True) for td in tr.find_all(["td", "th"])] for tr in table.find_all("tr")]
    head = rows[0] if rows else []
    if len(head) != 3 or head[0] != "Tarih" or not head[1].endswith("Alma") or not head[2].endswith("Verme"):
        raise MacroParseError("faiz tablosu başlığı tanınmadı")
    parsed: list[tuple[str, float]] = []
    for r in rows[1:]:
        if len(r) != 3 or not re.fullmatch(r"\d{2}\.\d{2}\.\d{4}", r[0]) or not re.fullmatch(r"\d+(\.\d+)?", r[2]):
            raise MacroParseError("faiz tablosu satırı tanınmadı")
        dd, mm, yy = r[0].split(".")
        parsed.append((date(int(yy), int(mm), int(dd)).isoformat(), float(r[2])))
    if len(parsed) < 3:
        raise MacroParseError("faiz tablosu çok kısa")
    d, v = max(parsed)
    if not 0 < v < 200:
        raise MacroParseError("faiz değeri makul aralıkta değil")
    return {"asOf": d, "value": v}


def _stamp(id_: str, label: str, value: float, unit: str, as_of: str, source: str, url: str, fetched: str, note: str) -> dict[str, Any]:
    return {"id": id_, "label": label, "value": value, "unit": unit, "asOf": as_of, "source": source, "sourceUrl": url,
            "fetchedAt": fetched, "note": note, "stale": False}


def policy_rate_indicator(fetched: str, get: Callable[..., requests.Response] = requests.get) -> dict[str, Any]:
    resp = get(POLICY_URL, headers=default_headers(), timeout=settings.http_timeout)
    resp.raise_for_status()
    p = parse_policy_rate(resp.content)
    return _stamp("policy_rate", "TCMB politika faizi (1 hafta repo, borç verme)", p["value"], "%", p["asOf"],
                  "T.C. Merkez Bankası — 1 Hafta Repo faiz oranları", POLICY_URL, fetched,
                  "Veri tarihi, tablodaki son faiz değişikliğinin tarihidir; sayfa değişikliği olmayan günlerde de aynı değeri gösterir. "
                  + TCMB_ATTRIBUTION)


def fx_pace_indicators(fx: TcmbFxSource, today: date, fetched: str) -> list[dict[str, Any]]:
    """USD/TRY TCMB döviz alış kurunun 30 ve 365 gün önceki bültene göre % değişimi (yalnızca iki gerçek bülten)."""
    now = fx.rate_on_or_before(today.isoformat())
    out = []
    for days, id_, label in ((30, "usdtry_30d", "USD/TRY 30 günlük değişim"), (365, "usdtry_365d", "USD/TRY 12 aylık değişim")):
        base = fx.rate_on_or_before((date.fromisoformat(now.date) - timedelta(days=days)).isoformat())
        pct = round((now.usd / base.usd - 1) * 100, 2)
        out.append(_stamp(id_, label, pct, "%", now.date, "T.C. Merkez Bankası — günlük döviz kurları (döviz alış)", FX_URL, fetched,
                          f"{base.date} bülteni {base.usd:.4f} → {now.date} bülteni {now.usd:.4f} TL. " + TCMB_ATTRIBUTION))
    return out


def evds_indicators(key: str, today: date, fetched: str, fetch=EV.fetch_series) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    """(göstergeler, hatalar). Hata = {id, series, reason}; neden anahtarsız kısa metindir (EvdsError)."""
    out, failed = [], []
    for ind in EV.INDICATORS:
        try:
            pts, _skipped = fetch(ind.series, today - timedelta(days=500), today, key)
            c = EV.compute(ind, pts)
        except EV.EvdsError as exc:
            log.warning("EVDS göstergesi alınamadı (%s): %s", ind.id, exc)
            failed.append({"id": ind.id, "series": ind.series, "reason": str(exc)})
            continue
        out.append(_stamp(ind.id, ind.label, c["value"], ind.unit, c["asOf"], f"T.C. Merkez Bankası EVDS ({ind.series})",
                          EV.SOURCE_URL, fetched, ind.note + " " + EV.ATTRIBUTION))
    return out, failed


def merge_with_previous(new: list[dict[str, Any]], prev: dict[str, Any] | None, attempted: set[str]) -> list[dict[str, Any]]:
    """Alınamayan (ama denenen) gösterge: önceki iyi değer kendi tarihiyle ``stale`` taşınır. Denenmeyen (anahtarsız EVDS) taşınmaz."""
    have = {i["id"] for i in new}
    out = list(new)
    for old in (prev or {}).get("indicators", []):
        if isinstance(old, dict) and old.get("id") in attempted and old["id"] not in have:
            out.append({**old, "stale": True})
    return out


def run_macro(data_dir: Path | None = None, today: date | None = None, get: Callable[..., requests.Response] = requests.get,
              fx: TcmbFxSource | None = None, evds_fetch=EV.fetch_series) -> int:
    ddir = data_dir or DATA_DIR
    today = today or datetime.now(timezone(timedelta(hours=3))).date()
    fetched = datetime.now(timezone.utc).isoformat(timespec="seconds")
    try:
        prev = json.loads((ddir / OUT_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        prev = None
    new: list[dict[str, Any]] = []
    attempted: set[str] = {"policy_rate", "usdtry_30d", "usdtry_365d"}
    try:
        new.append(policy_rate_indicator(fetched, get))
    except (requests.RequestException, MacroParseError) as exc:
        log.warning("TCMB politika faizi alınamadı: %s", type(exc).__name__)
    try:
        new.extend(fx_pace_indicators(fx or TcmbFxSource(), today, fetched))
    except (FxUnavailable, requests.RequestException) as exc:
        log.warning("TCMB kur değişimi hesaplanamadı: %s", exc)
    key = EV.api_key()
    if key:
        attempted |= {i.id for i in EV.INDICATORS}
        got, evds_issues = evds_indicators(key, today, fetched, evds_fetch)
        new.extend(got)
    else:
        evds_issues = [{"id": i.id, "series": i.series, "reason": f"{EV.ENV_KEY} tanımlı değil; seri çekilmedi"} for i in EV.INDICATORS]
        print(f"{EV.ENV_KEY} tanımlı değil: EVDS göstergeleri (TÜFE yıllık, REK) çekilmedi ve sayfada gösterilmeyecek.")
    for i in evds_issues:
        print(f"EVDS sorunu: {i['series']} ({i['id']}): {i['reason']}")
    if not new:
        print("Hiçbir makro gösterge alınamadı; dosya değiştirilmedi.")
        return 0
    items = merge_with_previous(new, prev, attempted)
    doc = {"updatedAt": fetched, "fetchedAt": fetched, "indicators": items,
           "evdsEnabled": bool(key), "evdsIssues": evds_issues, "attribution": TCMB_ATTRIBUTION}
    (ddir / OUT_FILE).parent.mkdir(parents=True, exist_ok=True)
    (ddir / OUT_FILE).write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{OUT_FILE}: {len(items)} gösterge ({sum(1 for i in items if i['stale'])} eski).")
    return 1
