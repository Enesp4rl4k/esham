"""Tüm evren için hisse başına finansal+oran JSON'u üretir.

Çıktılar (web/public/data/):
  universe.json            — evren + tarayıcı için özet oranlar
  stocks/<TICKER>.json     — TTM oranlar, yıllık/çeyreklik tablolar, büyüme, geçmiş, sektör medyanı
  prices/<TICKER>.json     — 5 yıllık haftalık kapanış [[tarih, fiyat], ...]
"""
from __future__ import annotations

import json
import statistics
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from ..config import get_logger
from .. import ratios as R
from ..sources.financials import dividend_ttm, fetch_financials, fx_to_try
from ..universe import load_universe

log = get_logger(__name__)

DATA_DIR = Path(__file__).resolve().parents[3] / "web" / "public" / "data"
MEDIAN_KEYS = ("pe", "pb", "ev_ebitda", "roe", "net_margin", "dividend_yield")
SCREENER_KEYS = ("market_cap", "pe", "pb", "ev_ebitda", "roe", "net_margin", "dividend_yield", "net_debt_ebitda")


def _quality_flags(snap: dict, quarterly: list, annual: list, financial: bool) -> list[str]:
    flags: list[str] = []
    if not quarterly or len(quarterly) < 4:
        flags.append("ttm_yok_yillik_kullanildi")
    last = (quarterly or annual)[-1]["date"] if (quarterly or annual) else None
    if last and (date.today() - date.fromisoformat(last)).days > 200:
        flags.append("bilanco_eski")
    # TTM gelir, aralık sonu yıllık gelirle uyuşmalı (TMS 29 / çeyrek kümülatif hatası tespiti)
    if quarterly and annual and len(quarterly) >= 4:
        q4 = quarterly[-4:]
        match = next((a for a in annual if a["date"] == q4[-1]["date"]), None)
        qsum, a_rev = R.ttm(quarterly, "revenue"), match.get("revenue") if match else None
        if qsum and a_rev and abs(qsum / a_rev - 1) > 0.05:
            flags.append("ceyreklik_toplam_yillikle_uyusmuyor")
    if snap.get("_ebitda_approx") and not financial:
        flags.append("favok_yaklasik_ebit")
    flags.append("enflasyon_muhasebesi_tms29_karsilastirma_dikkat")
    return flags


def _fetch_prices(ticker: str) -> list[list[Any]]:
    import yfinance as yf

    try:
        h = yf.Ticker(f"{ticker}.IS").history(period="5y", interval="1wk", auto_adjust=False)
        return [[str(i.date()), round(float(c), 2)] for i, c in h["Close"].dropna().items()]
    except Exception as exc:
        log.warning("Fiyat geçmişi alınamadı %s: %s", ticker, exc)
        return []


def build_stock(meta: dict[str, Any]) -> dict[str, Any] | None:
    ticker, financial = meta["ticker"], bool(meta["financial"])
    raw = fetch_financials(ticker)
    if not raw:
        log.warning("Veri yok, atlandı: %s", ticker)
        return None
    q, a = raw["quarterly"], raw["annual"]
    snap = R.build_ttm_snapshot(q, a)
    as_of = (q or a)[-1]["date"]
    # Tablolar raporlama para biriminde (ör. THYAO USD); piyasa değeri TL.
    # Çarpanların tutarlı olması için piyasa değerini raporlama birimine çeviriyoruz.
    fx = fx_to_try(raw["currency"])
    mcap = raw["market_cap"]
    if raw["currency"] != "TRY":
        if not fx or not mcap:
            log.warning("Kur/piyasa değeri yok, çarpanlar hesaplanamadı: %s (%s)", ticker, raw["currency"])
            mcap = None
        else:
            mcap = mcap / fx
    rat = R.compute_ratios(
        snap,
        price=raw["price"],
        market_cap=mcap,
        # Yahoo'da hiç temettü kaydı yoksa "0" demek yanıltıcı → None (UI "—")
        dividend_per_share_ttm=dividend_ttm(raw["dividends"], date.today().isoformat()) if raw["dividends"] else None,
        financial=financial,
    )
    rat["market_cap"] = raw["market_cap"]  # gösterim/tarayıcı için her zaman TL
    quality = _quality_flags(snap, q, a, financial) + R.outlier_flags(rat, raw.get("yahoo_ref"), raw["currency"], financial)
    # Finansallar sekmesi tabloları için tüm normalize kalemler (eksik = null)
    keep = ("date",) + R.FLOW_KEYS + R.STOCK_KEYS
    return {
        "ticker": ticker,
        "name": meta["name"],
        "sector": meta["sector"],
        "financial": financial,
        "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "as_of": as_of,
        "basis": "TTM" if snap["_basis"] else "yillik",
        "currency": raw["currency"],  # tabloların para birimi
        "fx_to_try": fx,
        "price": raw["price"],  # her zaman TL
        "ratios": rat,
        "ttm": {k: v for k, v in snap.items() if not k.startswith("_")},
        "growth": {
            "annual_revenue": R.growth_series(a, "revenue", 1),
            "annual_net_income": R.growth_series(a, "net_income", 1),
            "quarterly_revenue_yoy": R.growth_series(q, "revenue", 4),
            "quarterly_net_income_yoy": R.growth_series(q, "net_income", 4),
            "revenue_cagr_3y": R.cagr(a[-4].get("revenue"), a[-1].get("revenue"), 3) if len(a) >= 4 else None,
        },
        "history": R.ratio_history(a),
        "quarterly_history": R.quarterly_history(q),
        "annual": [{k: p.get(k) for k in keep} for p in a],
        "quarterly": [{k: p.get(k) for k in keep} for p in q],
        "quality": quality,
        "suspect": any(f in R.SUSPECT_FLAGS for f in quality),
    }


def _medians(stocks: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
    by_sector: dict[str, dict[str, list[float]]] = {}
    for s in stocks:
        for k in MEDIAN_KEYS:
            v = s["ratios"].get(k)
            if v is not None:
                by_sector.setdefault(s["sector"], {}).setdefault(k, []).append(v)
    return {
        sec: {k: round(statistics.median(vs), 2) for k, vs in d.items() if len(vs) >= 3}
        for sec, d in by_sector.items()
    }


def _write(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def run_stocks(tickers: list[str] | None = None, workers: int = 4, with_prices: bool = True) -> int:
    universe = load_universe()
    if tickers:
        want = {t.upper() for t in tickers}
        universe = [u for u in universe if u["ticker"] in want]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(build_stock, universe))
    stocks = [s for s in results if s]

    medians = _medians(stocks)
    for s in stocks:
        s["sector_median"] = medians.get(s["sector"], {})
        _write(DATA_DIR / "stocks" / f"{s['ticker']}.json", s)
    if with_prices:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            for s, series in zip(stocks, pool.map(lambda x: _fetch_prices(x["ticker"]), stocks)):
                if series:
                    _write(DATA_DIR / "prices" / f"{s['ticker']}.json", series)

    # Kısmi çalıştırmada (tickers verilmiş) mevcut evreni bozma: birleştir
    uni_path = DATA_DIR / "universe.json"
    existing: dict[str, Any] = {}
    sector_median = medians
    if tickers and uni_path.exists():
        prev = json.loads(uni_path.read_text(encoding="utf-8"))
        existing = {r["ticker"]: r for r in prev["stocks"]}
        sector_median = prev.get("sector_median", medians)
    for s in stocks:
        existing[s["ticker"]] = {
            "ticker": s["ticker"], "name": s["name"], "sector": s["sector"], "financial": s["financial"],
            "price": s["price"], "as_of": s["as_of"], "suspect": s["suspect"],
            **{k: s["ratios"].get(k) for k in SCREENER_KEYS},
        }
    _write(uni_path, {
        "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "count": len(existing),
        "sector_median": sector_median,
        "stocks": sorted(existing.values(), key=lambda r: -(r.get("market_cap") or 0)),
    })
    log.info("Hisse verisi yazıldı: %d/%d", len(stocks), len(universe))
    return len(stocks)
