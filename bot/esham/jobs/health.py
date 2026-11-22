"""Boru hattı sağlık denetimi: veri tazeliği + canlı sitenin güncel olup olmadığı.

Neden: dağıtım adımı eskiden hataları yutuyordu (`continue-on-error`), bot veri üretmeye devam ederken site
sessizce eskiyebilirdi. Bu denetim dışarıdan bakar: "en son rapor canlıda açılıyor mu?"

``evaluate`` saf fonksiyondur (test edilir); ``run_health`` dosyaları okur ve siteyi sorgular.
Başarısızlıkta çıkış kodu 1 → GitHub Actions başarısız olur → depo sahibine e-posta gider.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import requests

from ..config import get_logger
from ..freshness import STOCK_ROW_STALE_HOURS

log = get_logger(__name__)
ROOT = Path(__file__).resolve().parents[3]
REPORTS = ROOT / "web" / "content" / "reports"
DATA = ROOT / "web" / "public" / "data"

DEPLOY_GRACE = timedelta(hours=6)  # en yeni rapor bu kadar eskiyse canlıda da olmalı


@dataclass
class Check:
    name: str
    ok: bool
    detail: str


def _limit_hours(now: datetime, weekday_hours: float, weekend_hours: float) -> float:
    """Bot hafta içi çalışır: cumartesi-pazar-pazartesi sabahı boşluğu normal sayılır."""
    return weekend_hours if now.weekday() in (5, 6, 0) else weekday_hours


def _age(now: datetime, then: datetime | None) -> timedelta | None:
    return None if then is None else now - then


def evaluate(
    now: datetime,
    newest_report: datetime | None,
    universe_updated: datetime | None,
    ticker_updated: datetime | None,
    site_status: int | None,
    prod_has_report: bool | None,
    offline: bool = False,
    funds_updated: datetime | None = None,
    check_funds: bool = False,
) -> list[Check]:
    checks: list[Check] = []

    def fresh(name: str, then: datetime | None, limit_h: float) -> None:
        age = _age(now, then)
        if age is None:
            checks.append(Check(name, False, "zaman damgası okunamadı"))
            return
        h = age.total_seconds() / 3600
        checks.append(Check(name, h <= limit_h, f"{h:.1f} saat önce (sınır {limit_h:.0f} saat)"))

    fresh("Son rapor tazeliği", newest_report, _limit_hours(now, 26, 74))
    fresh("Piyasa bandı (market-ticker.json) tazeliği", ticker_updated, _limit_hours(now, 26, 74))
    fresh("Hisse verisi (universe.json) tazeliği", universe_updated, STOCK_ROW_STALE_HOURS)
    if check_funds:  # fon verisi henüz hiç üretilmediyse (eski depo/ilk kurulum) alarm verme
        fresh("Fon verisi (universe-funds.json) tazeliği", funds_updated, STOCK_ROW_STALE_HOURS)

    if offline:
        checks.append(Check("Canlı site erişimi", True, "atlandı (--offline)"))
    elif site_status is None:
        checks.append(Check("Canlı site erişimi", False, "istek başarısız (ağ/zaman aşımı)"))
    else:
        checks.append(Check("Canlı site erişimi", site_status == 200, f"HTTP {site_status}"))

    if prod_has_report is None:
        checks.append(Check("Dağıtım güncel mi", True, "atlandı (sorgulanamadı)"))
    else:
        checks.append(Check("Dağıtım güncel mi", prod_has_report, "en son rapor canlıda açılıyor" if prod_has_report else "en son rapor canlıda 404: dağıtım duruyor olabilir"))
    return checks


def _parse(ts: Any) -> datetime | None:
    try:
        d = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def newest_reports(limit: int = 12) -> list[dict[str, Any]]:
    """Dosya adındaki tarihe göre en yeni raporlar (slug + publishedAt)."""
    files = sorted(REPORTS.glob("*.json"), reverse=True)[:limit]
    out = []
    for f in files:
        try:
            d = _read_json(f)
        except (OSError, ValueError):
            continue
        out.append({"slug": d.get("slug"), "published": _parse(d.get("publishedAt"))})
    return [r for r in out if r["slug"] and r["published"]]


def run_health(site: str, offline: bool = False, now: datetime | None = None) -> list[Check]:
    now = now or datetime.now(timezone.utc)
    reports = newest_reports()
    newest = max((r["published"] for r in reports), default=None)
    try:
        universe = _parse(_read_json(DATA / "universe.json").get("updated_at"))
    except (OSError, ValueError):
        universe = None
    funds_path = DATA / "universe-funds.json"
    try:
        funds = _parse(_read_json(funds_path).get("updated_at")) if funds_path.exists() else None
    except (OSError, ValueError):
        funds = None
    try:
        ticker = _parse(_read_json(DATA / "market-ticker.json").get("updatedAt"))
    except (OSError, ValueError):
        ticker = None

    status: int | None = None
    prod_has: bool | None = None
    if not offline:
        try:
            status = requests.get(site, timeout=20, headers={"User-Agent": "esham-health/1.0"}).status_code
        except requests.RequestException as exc:
            log.warning("Canlı site sorgulanamadı: %s", exc)
        # grace süresini geçmiş en yeni rapor canlıda olmalı
        due = [r for r in reports if now - r["published"] >= DEPLOY_GRACE]
        if due and status == 200:
            slug = max(due, key=lambda r: r["published"])["slug"]
            try:
                prod_has = requests.get(f"{site.rstrip('/')}/rapor/{slug}", timeout=20, headers={"User-Agent": "esham-health/1.0"}).status_code == 200
            except requests.RequestException:
                prod_has = None
    return evaluate(now, newest, universe, ticker, status, prod_has, offline=offline, funds_updated=funds, check_funds=funds_path.exists())


def report(checks: list[Check]) -> int:
    """Sonuçları yazdır; başarısız kontrol varsa 1 (CI başarısız olsun)."""
    for c in checks:
        print(f"{'OK  ' if c.ok else 'FAIL'} {c.name}: {c.detail}")
    failed = [c for c in checks if not c.ok]
    print()
    print(f"{len(failed)} kontrol başarısız." if failed else "Tüm kontroller geçti.")
    return 1 if failed else 0


def main(argv: list[str] | None = None) -> int:
    """`python -m esham.jobs.health`: yalnızca requests + python-dotenv gerekir (tam bağımlılık kurulumu yok)."""
    import argparse
    import os
    import sys

    ap = argparse.ArgumentParser(prog="esham.jobs.health")
    ap.add_argument("--site", default=os.environ.get("ESHAM_SITE_URL", "https://esham.pages.dev"))
    ap.add_argument("--offline", action="store_true")
    args = ap.parse_args(argv)
    if sys.stdout.encoding != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")
    return report(run_health(args.site, offline=args.offline))


if __name__ == "__main__":
    raise SystemExit(main())
