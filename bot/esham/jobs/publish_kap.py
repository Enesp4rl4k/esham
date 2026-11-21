"""KAP finansal raporlarından hisse başına IFRS tabloları üretir (``web/public/data/kap/<T>.json``).

Yahoo ile aynı normalize ``Period`` şemasını kullanır (``ratios.py`` ile doğrudan uyumlu).
Şimdilik YAN VERİ: site hâlâ Yahoo'yu kullanır; bu iş KAP'ı doğrulama referansı olarak üretir ve
Yahoo ile TTM hasılat/net kâr farklarını raporlar. Banka/sigorta (farklı XBRL taksonomisi) desteklenmez.
"""
from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..config import get_logger
from .. import ratios as R
from ..kap_http import KapUnavailable, gate
from ..sources.financials import fx_to_try
from ..sources.kap_financials import KapFinancials, build_periods
from ..universe import load_universe

log = get_logger(__name__)
DATA_DIR = Path(__file__).resolve().parents[3] / "web" / "public" / "data"


def crosscheck(kap_q: list[dict[str, Any]], yahoo: dict[str, Any]) -> dict[str, float | None]:
    """KAP ve Yahoo TTM hasılat/net kâr oranı (KAP/Yahoo − 1). Para birimi farklıysa güncel kurla TL'ye çevrilir."""
    k_rev, k_ni = R.ttm(kap_q, "revenue"), R.ttm(kap_q, "net_income")
    y = yahoo.get("ttm", {})
    fx = fx_to_try(yahoo.get("currency", "TRY")) or 1.0
    y_rev = None if y.get("revenue") is None else y["revenue"] * fx
    y_ni = None if y.get("net_income") is None else y["net_income"] * fx
    return {
        "revenue_diff_pct": None if not (k_rev and y_rev) else round((k_rev / y_rev - 1) * 100, 1),
        "net_income_diff_pct": None if not (k_ni and y_ni) else round((k_ni / y_ni - 1) * 100, 1),
    }


def build_ticker(kf: KapFinancials, ticker: str, reports: list[dict[str, Any]]) -> dict[str, Any] | None:
    try:
        snaps = [kf.snapshot(str(r["disclosureIndex"])) for r in reports]
    except KapUnavailable as exc:
        # Eksik rapor setiyle yazmak son iyi dosyayı bozar → atla, mevcut web/public/data/kap/<T>.json kalır.
        log.warning("KAP: %s atlandı, önceki veri korunuyor (%s)", ticker, exc)
        return None
    ok = [s for s in snaps if s]
    if not ok:
        log.warning("KAP: %s için işlenebilir rapor yok (banka/sigorta taksonomisi olabilir)", ticker)
        return None
    quarterly, annual = build_periods(ok)
    return {
        "source": "KAP",
        "ticker": ticker,
        "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "currency": ok[-1]["currency"],
        "consolidated": ok[-1]["consolidated"],
        "reports": [
            {"index": r["disclosureIndex"], "year": r.get("year"), "period": r.get("period"), "consolidated": r["_consolidated"]}
            for r in reports
        ],
        "quarterly": quarterly,
        "annual": annual,
    }


def run_kap(tickers: list[str] | None = None, months: int = 18, workers: int = 3) -> int:
    universe = [u for u in load_universe() if not u["financial"]]
    want = {t.upper() for t in tickers} if tickers else {str(u["ticker"]) for u in universe}
    kf = KapFinancials()
    gate.begin_stage()
    try:
        reports = kf.list_reports(want, months=months)
    except KapUnavailable as exc:
        log.warning("KAP rapor listesi alınamadı, hiçbir dosya değiştirilmedi: %s | %s", exc, gate.summary())
        return 0
    if gate.failed or gate.stopped:
        # Pencerelerden biri eksik → rapor seti eksik olabilir; eksik veriyle üzerine yazmayız.
        log.warning("KAP rapor listesi eksik, hiçbir dosya değiştirilmedi. %s", gate.summary())
        return 0
    by_t: dict[str, list[dict[str, Any]]] = {}
    for r in reports:
        by_t.setdefault(r["_ticker"], []).append(r)
    log.info("KAP: %d hisse için %d finansal rapor bulundu", len(by_t), len(reports))

    def work(item: tuple[str, list[dict[str, Any]]]) -> tuple[str, dict[str, Any] | None]:
        if gate.stopped:
            return item[0], None  # KAP'a başvurmadan atla (önbellekteki raporlar da eksikse build_ticker yine None döner)
        return item[0], build_ticker(kf, item[0], item[1])

    written = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for ticker, doc in pool.map(work, sorted(by_t.items())):
            if not doc:
                continue
            y_path = DATA_DIR / "stocks" / f"{ticker}.json"
            if y_path.exists():
                doc["crosscheck_vs_yahoo"] = crosscheck(doc["quarterly"], json.loads(y_path.read_text(encoding="utf-8")))
            out = DATA_DIR / "kap" / f"{ticker}.json"
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
            written += 1
            print(f"{ticker:<6} {len(doc['quarterly'])}Ç {len(doc['annual'])}Y {doc['currency']}  vs Yahoo: {doc.get('crosscheck_vs_yahoo')}")
    skipped = len(by_t) - written
    log.info("KAP: %d hisse yazıldı, %d hisse atlandı (önceki veri korundu). %s", written, skipped, gate.summary())
    return written
