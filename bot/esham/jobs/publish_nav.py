"""Holding/çok iş kollu şirketler için KAP iştirak pay tablosu → ``web/public/data/nav/<T>.json``.

Web, bu paylar × iştirakin piyasa değeri (universe.json) ile NAV hesaplar. Yalnızca DOĞRUDAN paylar
gelir (bkz. sources/kap_holdings.py sınırı).
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from ..config import get_logger
from ..kap_http import KapUnavailable, gate
from ..sources.kap_financials import KapFinancials, iter_fr_rows
from ..sources.kap_holdings import KapHoldings, fold_title, match_listed
from ..universe import load_universe

log = get_logger(__name__)
DATA_DIR = Path(__file__).resolve().parents[3] / "web" / "public" / "data"

# Holding sektörü + çok iş kollu gruplar (NAV iskontosu bakılan şirketler)
EXTRA_NAV_TICKERS = ["ALARK", "TKFEN"]


def nav_tickers() -> list[str]:
    base = [str(u["ticker"]) for u in load_universe() if u["sector"] == "Holding"]
    return sorted(set(base + EXTRA_NAV_TICKERS))


def title_to_ticker(prefer: set[str], days: int = 150, step: int = 10) -> dict[str, str]:
    """Son ``days`` günün FR bildirimlerinden {katlanmış ünvan: ticker} (borsada işlem gören şirketler).

    Bir şirketin birden çok kodu olabilir (ör. "YKBNK, YKB"): evrendeki (``prefer``) kod önceliklidir."""
    kf = KapFinancials()
    out: dict[str, str] = {}
    end = date.today()
    w = end - timedelta(days=days)
    while w < end:
        w_end = min(w + timedelta(days=step), end)
        for r in iter_fr_rows(kf.headers, w, w_end):
            codes = [c.strip() for c in str(r.get("stockCodes") or "").split(",") if c.strip()]
            title = str(r.get("kapTitle") or "")
            if codes and title:
                code = next((c for c in codes if c in prefer), codes[0])
                if fold_title(title) not in out or code in prefer:
                    out[fold_title(title)] = code
        w = w_end + timedelta(days=1)
    return out


def run_nav(tickers: list[str] | None = None) -> int:
    tickers = [t.upper() for t in tickers] if tickers else nav_tickers()
    names = {str(u["ticker"]): str(u["name"]) for u in load_universe()}
    universe = set(names)
    gate.begin_stage()
    try:
        tmap = title_to_ticker(universe)
    except KapUnavailable as exc:
        log.warning("KAP ünvan→ticker eşlemesi alınamadı, NAV dosyaları değiştirilmedi: %s | %s", exc, gate.summary())
        return 0
    if gate.failed or gate.stopped:
        log.warning("KAP ünvan eşlemesi eksik, NAV dosyaları değiştirilmedi. %s", gate.summary())
        return 0
    log.info("KAP ünvan→ticker eşlemesi: %d şirket", len(tmap))
    kh = KapHoldings()
    written = 0
    for t in tickers:
        stakes = kh.stakes(t, names.get(t))
        if stakes is None:
            continue
        # Şirketin kendi koduna eşleşme geçersiz (ör. ALARK ↔ "Alser Alarko Sermaye" ünvan benzerliği)
        matched = [{**s, "ticker": None if s["ticker"] == t else s["ticker"]} for s in match_listed(stakes, tmap)]
        doc: dict[str, Any] = {
            "source": "KAP Genel Bilgi Formu (doğrudan paylar)",
            "ticker": t,
            "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "stakes": sorted(matched, key=lambda s: -s["pct"]),
        }
        out = DATA_DIR / "nav" / f"{t}.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        listed = [s for s in matched if s["ticker"]]
        missing = sorted({s["ticker"] for s in listed} - universe)
        print(f"{t:<6} {len(matched)} iştirak, {len(listed)} borsada işlem gören; evrende olmayan: {missing or '-'}")
        written += 1
    log.info("KAP NAV: %d/%d şirket yazıldı, kalanında önceki veri korundu. %s", written, len(tickers), gate.summary())
    return written
