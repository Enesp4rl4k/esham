"""Veri tazeliği ve kaynak damgası: her bölüm için (kaynak, veri tarihi, çekiliş zamanı, durum).

Amaç: "ölçülmüş ve kaynaklı" kuralı. Bir bölümün verisi eskiyorsa ya da hiç yoksa bu görünür olur:
  - ``web/public/data/data-status.json`` her yayın turunda yeniden yazılır; site /yontem sayfasında gösterir.
  - ``python -m esham.main data-status`` hangi bölümün güncel / eski / eksik olduğunu ve nedenini yazar;
    GitHub Actions özetine (``GITHUB_STEP_SUMMARY``) ve ``::warning`` satırlarına da yansır.

Yalnızca standart kütüphane kullanır (ağ yok, ağır bağımlılık yok); saf fonksiyonlar test edilir.
"""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "web" / "public" / "data"
REPORTS = ROOT / "web" / "content" / "reports"
STATUS_FILE = DATA / "data-status.json"

TR_TZ = timezone(timedelta(hours=3))

#: TEK eşik: hisse/fon verisi bu kadar saatten eskiyse hem satır "bayat" işaretlenir hem data-status "eski" der.
#: (web/src/lib/stocks.ts içindeki STALE_ROW_HOURS ile aynı olmak zorunda; test denetler.)
STOCK_ROW_STALE_HOURS = 120


# --------------------------------------------------------------------------------------------
# TÜRİB / emtia sayfası bölümleri (turib_data bunu `sections` alanına yazar)
# --------------------------------------------------------------------------------------------

#: Bölüm -> (okunur ad, kaynak adı, kaynak URL'si)
SECTION_SOURCES: dict[str, tuple[str, str, str]] = {
    "indices": ("TÜRİB endeksleri", "TÜRİB ELÜS bülteni", "https://www.turib.com.tr"),
    "spotCommodities": ("TÜRİB spot ürünler", "TÜRİB ELÜS bülteni", "https://www.turib.com.tr"),
    "tmoComparison": ("TMO alım fiyatları", "Tarım ve Orman Bakanlığı / TMO duyuruları", "https://www.tmo.gov.tr"),
    "storageBacktest": ("Depolama geriye dönük testi", "TÜRİB tarihsel seri (varsayımlı maliyet modeli)", "https://www.turib.com.tr"),
    "regionalArbitrage": ("Bölgesel depo fiyat farkı", "TÜRİB ELÜS bülteni", "https://www.turib.com.tr"),
    "agriBist": ("Agri-BIST radarı", "Yahoo Finance (XGIDA/hisseler) + TÜRİB", "https://finance.yahoo.com"),
    "realReturns": ("Döviz cinsinden getiri", "TCMB döviz kurları + TÜRİB", "https://www.tcmb.gov.tr/kurlar/kurlar_tr.html"),
    "petrolTanker": ("Brent petrol", "Yahoo Finance (Brent vadeli)", "https://finance.yahoo.com"),
    "straits": ("İstanbul Boğazı geçişleri", "IMF PortWatch (BM Global Platform AIS)", "https://portwatch.imf.org/"),
}

#: Bölüm verisi bu kadar günden eskiyse "eski" sayılır (None: tarih sınırı yok, yıllık duyuru gibi).
SECTION_LIMIT_DAYS: dict[str, int | None] = {
    "indices": 4, "spotCommodities": 4, "regionalArbitrage": 4, "agriBist": 4,
    "realReturns": 5, "petrolTanker": 4, "straits": 21, "storageBacktest": 14, "tmoComparison": None,
}


def _first_date(value: Any) -> str | None:
    """Girdi/bölüm için veri tarihi (asOf > date > endDate > updatedAt); yoksa None."""
    if isinstance(value, dict):
        for k in ("asOf", "date", "endDate", "weekEnd"):
            if value.get(k):
                return str(value[k])[:10]
        if value.get("updatedAt"):
            return str(value["updatedAt"])[:10]
    return None


def _section_entries(data: dict[str, Any], key: str) -> list[dict[str, Any]]:
    if key == "straits":
        pt = data.get("petrolTanker")
        raw = pt.get("straits") if isinstance(pt, dict) else None
        return [e for e in (raw or []) if isinstance(e, dict)]
    value = data.get(key)
    if key == "petrolTanker" and isinstance(value, dict):
        value = {k: v for k, v in value.items() if k != "straits"} if value else {}
    entries = value if isinstance(value, list) else ([value] if isinstance(value, dict) and value else [])
    return [e for e in entries if isinstance(e, dict)]


def build_section_meta(data: dict[str, Any], fetched_at: str) -> dict[str, dict[str, Any]]:
    """Her bölüm için {label, source, sourceUrl, asOf, fetchedAt, stale, status}; veri yoksa status="missing".

    ``asOf`` bölümdeki EN ESKİ girdi tarihidir (karışık tazelikte taze görünmez); ``stale`` en az bir girdi
    taşınmışsa (`stale: true`) True olur. Tarihi bilinmeyen bölüm "missing" sayılır (tarihsiz veri taze sunulmaz).
    """
    meta: dict[str, dict[str, Any]] = {}
    for key, (label, source, url) in SECTION_SOURCES.items():
        entries = _section_entries(data, key)
        dates = [d for d in (_first_date(e) for e in entries) if d]
        base = {"label": label, "source": source, "sourceUrl": url}
        if not entries or not dates:
            meta[key] = {**base, "asOf": None, "fetchedAt": None, "stale": False, "status": "missing"}
            continue
        stale = any(bool(e.get("stale")) for e in entries)
        meta[key] = {**base, "asOf": min(dates), "fetchedAt": fetched_at, "stale": stale,
                     "status": "stale" if stale else "fresh"}
    return meta


# --------------------------------------------------------------------------------------------
# Genel durum (data-status.json)
# --------------------------------------------------------------------------------------------

@dataclass
class SectionStatus:
    id: str
    label: str
    source: str
    source_url: str
    as_of: str | None  # veri tarihi (YYYY-MM-DD) veya zaman damgası
    fetched_at: str | None
    status: str  # "fresh" | "stale" | "missing"
    detail: str


def _parse_ts(value: Any) -> datetime | None:
    try:
        d = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return d if d.tzinfo else d.replace(tzinfo=TR_TZ)


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _limit_hours(now: datetime, weekday_hours: float, weekend_hours: float) -> float:
    """Bot hafta içi çalışır: cumartesi-pazar-pazartesi sabahı boşluğu normal sayılır."""
    return weekend_hours if now.astimezone(TR_TZ).weekday() in (5, 6, 0) else weekday_hours


def _ts_status(now: datetime, sid: str, label: str, source: str, url: str, ts: Any, limit_h: float) -> SectionStatus:
    when = _parse_ts(ts)
    if when is None:
        return SectionStatus(sid, label, source, url, None, None, "missing", "zaman damgası yok/okunamadı")
    age_h = (now - when).total_seconds() / 3600
    ok = age_h <= limit_h
    return SectionStatus(sid, label, source, url, when.isoformat(timespec="seconds"), when.isoformat(timespec="seconds"),
                         "fresh" if ok else "stale", f"{age_h:.1f} saat önce (sınır {limit_h:.0f} saat)")


def newest_report_time(reports_dir: Path) -> datetime | None:
    best: datetime | None = None
    for f in sorted(reports_dir.glob("*.json"), reverse=True)[:12]:
        d = _read_json(f)
        t = _parse_ts(d.get("publishedAt")) if isinstance(d, dict) else None
        if t and (best is None or t > best):
            best = t
    return best


def kap_coverage(stocks_dir: Path) -> tuple[int, int]:
    """(KAP kaynaklı finansalı olan hisse sayısı, toplam hisse dosyası)."""
    total = kap = 0
    for f in stocks_dir.glob("*.json"):
        d = _read_json(f)
        if not isinstance(d, dict):
            continue
        total += 1
        if d.get("data_source") == "KAP":
            kap += 1
    return kap, total


def evaluate_sections(now: datetime, data_dir: Path = DATA, reports_dir: Path = REPORTS) -> list[SectionStatus]:
    now = now if now.tzinfo else now.replace(tzinfo=timezone.utc)
    out: list[SectionStatus] = []

    newest = newest_report_time(reports_dir)
    out.append(_ts_status(now, "reports", "Analiz raporları", "Esham otomatik analiz (Yahoo Finance, TradingView, KAP, haber RSS'leri)",
                          "https://esham.pages.dev/arsiv", newest.isoformat() if newest else None, _limit_hours(now, 26, 74)))

    ticker = _read_json(data_dir / "market-ticker.json")
    out.append(_ts_status(now, "market_ticker", "Piyasa bandı", "Yahoo Finance, TradingView, TÜRİB",
                          "https://finance.yahoo.com", (ticker or {}).get("updatedAt"), _limit_hours(now, 26, 74)))

    cal = _read_json(data_dir / "economic-calendar.json")
    out.append(_ts_status(now, "economic_calendar", "Ekonomik takvim", "TradingView ekonomik takvim",
                          "https://www.tradingview.com", (cal or {}).get("updated_at"), _limit_hours(now, 26, 74)))

    uni = _read_json(data_dir / "universe.json")
    s = _ts_status(now, "stocks", "Hisse oranları", "Fiyat/piyasa değeri: Yahoo Finance; finansal tablolar: KAP (birincil) / Yahoo (yedek)",
                   "https://www.kap.org.tr", (uni or {}).get("updated_at"), STOCK_ROW_STALE_HOURS)
    stale_rows = 0
    if isinstance(uni, dict):
        for r in uni.get("stocks", []):
            t = _parse_ts(r.get("updated_at")) if isinstance(r, dict) else None
            if t and (now - t) > timedelta(hours=STOCK_ROW_STALE_HOURS):
                stale_rows += 1
    if stale_rows:
        s.detail += f"; {stale_rows} hissenin satırı eski (son başarılı güncelleme)"
        if s.status == "fresh":
            s.status = "stale"
    out.append(s)

    kap, total = kap_coverage(data_dir / "stocks")
    out.append(SectionStatus("kap_coverage", "KAP finansal kapsamı", "KAP finansal rapor bildirimleri (IFRS/XBRL)",
                             "https://www.kap.org.tr", None, None, "fresh" if total and kap else "missing",
                             f"{kap}/{total} hissenin finansalı KAP kaynaklı (kalanlar Yahoo yedeği)"))

    funds_path = data_dir / "universe-funds.json"
    if funds_path.exists():
        funds = _read_json(funds_path)
        out.append(_ts_status(now, "funds", "TEFAS fonları", "TEFAS (tefas.gov.tr)", "https://www.tefas.gov.tr",
                              (funds or {}).get("updated_at") if isinstance(funds, dict) else None, STOCK_ROW_STALE_HOURS))

    turib = _read_json(data_dir / "turib-market.json")
    if isinstance(turib, dict):
        meta = turib.get("sections") or build_section_meta(turib, str(turib.get("updatedAt") or ""))
        today = now.astimezone(TR_TZ).date()
        for key, m in meta.items():
            limit = SECTION_LIMIT_DAYS.get(key)
            as_of, status, detail = m.get("asOf"), m.get("status", "missing"), ""
            if status == "missing":
                detail = "veri yok; sayfada gösterilmiyor"
            else:
                try:
                    age = (today - date.fromisoformat(str(as_of)[:10])).days
                except ValueError:
                    age, status = None, "missing"
                if age is not None:
                    detail = f"veri {age} gün önceki" + (" (son iyi değer taşındı)" if m.get("stale") else "")
                    if limit is not None and age > limit:
                        status, detail = "stale", detail + f"; sınır {limit} gün"
                    elif m.get("stale"):
                        status = "stale"
            out.append(SectionStatus(f"turib:{key}", m.get("label", key), m.get("source", ""), m.get("sourceUrl", ""),
                                     as_of, m.get("fetchedAt"), status, detail))
    else:
        out.append(SectionStatus("turib", "Emtia / TÜRİB sayfası", "TÜRİB", "https://www.turib.com.tr", None, None,
                                 "missing", "turib-market.json okunamadı"))
    return out


def summarize(sections: list[SectionStatus]) -> str:
    sym = {"fresh": "GUNCEL", "stale": "ESKI  ", "missing": "EKSIK "}
    lines = [f"{sym.get(s.status, s.status)} {s.id}: {s.label} — veri tarihi {s.as_of or 'yok'} — {s.detail}" for s in sections]
    n = {k: sum(1 for s in sections if s.status == k) for k in ("fresh", "stale", "missing")}
    lines.append(f"Özet: {n['fresh']} güncel, {n['stale']} eski, {n['missing']} eksik bölüm.")
    return "\n".join(lines)


def write_status(sections: list[SectionStatus], now: datetime, path: Path = STATUS_FILE) -> None:
    doc = {
        "generated_at": now.astimezone(TR_TZ).isoformat(timespec="seconds"),
        "sections": [asdict(s) for s in sections],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")


def run_data_status(strict: bool = False, now: datetime | None = None, data_dir: Path = DATA,
                    reports_dir: Path = REPORTS, status_path: Path = STATUS_FILE) -> int:
    """Durumu hesapla, dosyaya yaz, özeti yazdır. ``strict``: eski/eksik bölüm varsa 1 döner (varsayılan 0).

    Eksik/eski bölüm yayını DURDURMAZ (iyi veri yayınlanmaya devam eder); görünür kılınır: konsol,
    ``::warning`` satırları ve GitHub adım özeti.
    """
    now = now or datetime.now(timezone.utc)
    sections = evaluate_sections(now, data_dir, reports_dir)
    write_status(sections, now, status_path)
    text = summarize(sections)
    print(text)
    for s in sections:
        if s.status != "fresh":
            print(f"::warning title=Veri {('eski' if s.status == 'stale' else 'eksik')}: {s.label}::{s.detail}")
    summary_file = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_file:
        try:
            with open(summary_file, "a", encoding="utf-8") as fh:
                fh.write("### Veri durumu\n\n```\n" + text + "\n```\n")
        except OSError:
            pass
    bad = [s for s in sections if s.status != "fresh"]
    return 1 if (strict and bad) else 0
