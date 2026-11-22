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
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from ..config import get_logger
from ..freshness import STOCK_ROW_STALE_HOURS
from .. import ratios as R
from ..kap_merge import choose_source, merge_statements
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


def _load_kap(ticker: str) -> dict[str, Any] | None:
    path = DATA_DIR / "kap" / f"{ticker}.json"
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
    except (OSError, ValueError) as exc:
        log.warning("KAP dosyası okunamadı %s: %s", ticker, exc)
        return None


def build_stock(meta: dict[str, Any]) -> dict[str, Any] | None:
    ticker, financial = meta["ticker"], bool(meta["financial"])
    raw = fetch_financials(ticker)
    if not raw:
        log.warning("Veri yok, atlandı: %s", ticker)
        return None
    q, a = raw["quarterly"], raw["annual"]
    # Birincil kaynak: KAP (resmî IFRS/XBRL); koşullar sağlanmazsa Yahoo (bkz. kap_merge)
    fx_yahoo = fx_to_try(raw["currency"])
    kap_doc = _load_kap(ticker)
    source, source_note = choose_source(kap_doc, q, fx_yahoo)
    currency = raw["currency"]
    if source == "KAP" and kap_doc:
        q, a = merge_statements(kap_doc, q, a, raw["currency"])
        currency = kap_doc.get("currency") or "TRY"
    snap = R.build_ttm_snapshot(q, a)
    as_of = (q or a)[-1]["date"]
    # Tablolar raporlama para biriminde (ör. THYAO USD); piyasa değeri TL.
    # Çarpanların tutarlı olması için piyasa değerini raporlama birimine çeviriyoruz.
    fx = fx_to_try(currency)
    mcap = raw["market_cap"]
    if currency != "TRY":
        if not fx or not mcap:
            log.warning("Kur/piyasa değeri yok, çarpanlar hesaplanamadı: %s (%s)", ticker, currency)
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
    quality = _quality_flags(snap, q, a, financial) + R.outlier_flags(rat, None if source == "KAP" else raw.get("yahoo_ref"), currency, financial)
    if source_note:
        quality.append(source_note)
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
        "data_source": source,  # "KAP" | "Yahoo" — finansal tabloların kaynağı (fiyat/piyasa değeri/temettü her zaman Yahoo)
        "currency": currency,  # tabloların para birimi
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


#: Son başarılı güncellemesi bu kadar saatten eski satır `stale: true` işaretlenir; bu kadar günden eskiyse gizlenir.
STALE_ROW_HOURS = STOCK_ROW_STALE_HOURS
HIDE_ROW_DAYS = 30


def merge_universe_rows(
    prev_rows: dict[str, Any],
    new_rows: dict[str, Any],
    universe_tickers: list[str],
    prev_stamp: str | None,
    now: datetime,
    partial: bool = False,
) -> tuple[dict[str, Any], list[str], list[str]]:
    """(birleşik satırlar, bu turda alınamayanlar, gizlenenler).

    Alınamayan hissenin son iyi satırı kendi ``updated_at``'ıyla korunur (satırda yoksa önceki dosya damgası);
    tarihi bilinmiyorsa satır taşınmaz. ``partial``: yalnızca bir alt küme istendiyse kalan hisseler "alınamadı"
    sayılmaz, olduğu gibi kalır.
    """
    merged: dict[str, Any] = {}
    failed: list[str] = []
    hidden: list[str] = []
    for t, row in prev_rows.items():
        if t in new_rows:
            continue
        stamp = row.get("updated_at") or prev_stamp
        try:
            age = now - datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
        except (TypeError, ValueError):
            hidden.append(t)  # tarihsiz eski satır taze gibi sunulmaz
            continue
        if age > timedelta(days=HIDE_ROW_DAYS):
            hidden.append(t)
            continue
        carried = {**row, "updated_at": stamp}
        if age > timedelta(hours=STALE_ROW_HOURS):
            carried["stale"] = True
        merged[t] = carried
        if not partial and t in universe_tickers:
            failed.append(t)
    merged.update(new_rows)
    if not partial:  # evrende olup hiç satırı olmayan (ilk kez alınamayan) hisseler de raporlanır
        failed.extend(t for t in universe_tickers if t not in merged and t not in failed)
    return merged, failed, hidden


def run_stocks(tickers: list[str] | None = None, workers: int = 4, with_prices: bool = True) -> int:
    universe = load_universe()
    if tickers:
        want = {t.upper() for t in tickers}
        universe = [u for u in universe if u["ticker"] in want]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(build_stock, universe))
    stocks = [s for s in results if s]
    if not stocks:
        # Hiçbir hisse alınamadı: dosyalara dokunma (aksi halde evren dosyası taze damgayla eski veriyi örter).
        log.error("Hiçbir hisse için veri alınamadı; mevcut dosyalar değiştirilmedi.")
        return 0

    medians = _medians(stocks)
    for s in stocks:
        s["sector_median"] = medians.get(s["sector"], {})
        _write(DATA_DIR / "stocks" / f"{s['ticker']}.json", s)
    if with_prices:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            for s, series in zip(stocks, pool.map(lambda x: _fetch_prices(x["ticker"]), stocks)):
                if series:
                    _write(DATA_DIR / "prices" / f"{s['ticker']}.json", series)

    # Evreni HER ZAMAN önceki yayınla birleştir: bu turda verisi alınamayan hisse sessizce listeden düşmez; son iyi
    # satırı KENDİ tarihiyle kalır, eşik aşılırsa "stale" işaretlenir, çok eskiyse gizlenir.
    uni_path = DATA_DIR / "universe.json"
    prev_rows: dict[str, Any] = {}
    prev_stamp: str | None = None
    prev_medians: dict[str, Any] = {}
    if uni_path.exists():
        try:
            prev = json.loads(uni_path.read_text(encoding="utf-8"))
            prev_stamp = prev.get("updated_at")
            prev_rows = {r["ticker"]: r for r in prev.get("stocks", [])}
            prev_medians = prev.get("sector_median", {})
        except (OSError, ValueError, KeyError) as exc:
            log.warning("Önceki universe.json okunamadı, birleştirme yapılmadı: %s", exc)
    now = datetime.now(timezone.utc)
    new_rows: dict[str, Any] = {}
    for s in stocks:
        new_rows[s["ticker"]] = {
            "ticker": s["ticker"], "name": s["name"], "sector": s["sector"], "financial": s["financial"],
            "price": s["price"], "as_of": s["as_of"], "suspect": s["suspect"], "updated_at": s["updated_at"],
            **{k: s["ratios"].get(k) for k in SCREENER_KEYS},
        }
    merged, failed, hidden = merge_universe_rows(prev_rows, new_rows, [str(u["ticker"]) for u in universe],
                                                 prev_stamp, now, partial=bool(tickers))
    _write(uni_path, {
        "updated_at": now.isoformat(timespec="seconds"),
        "count": len(merged),
        "sector_median": medians if not tickers else (prev_medians or medians),
        "stocks": sorted(merged.values(), key=lambda r: -(r.get("market_cap") or 0)),
    })
    if failed:
        log.warning("Hisse verisi alınamadı (%d): %s — önceki satırlar kendi tarihleriyle korundu.", len(failed), ", ".join(sorted(failed)))
    if hidden:
        log.warning("Çok eski olduğu için evrenden gizlendi (%d): %s", len(hidden), ", ".join(sorted(hidden)))
    print(f"Hisse özeti: {len(stocks)}/{len(universe)} güncellendi; {len(failed)} alınamadı (son iyi değer korundu); "
          f"{sum(1 for r in merged.values() if r.get('stale'))} satır eski işaretli; {len(hidden)} gizlendi.")
    log.info("Hisse verisi yazıldı: %d/%d", len(stocks), len(universe))
    return len(stocks)
