"""Canlı fiyat verilerini web/public/data/market-ticker.json'a yazar.

Statik export (Cloudflare Pages) ortamında Next.js API route çalışmaz.
Bunun yerine bot her tarama turunda bu modülü çağırır; üretilen JSON dosyası
GitHub commit'i ile web'e iletilir ve ticker bant onu okur.

JSON formatı:
{
  "updatedAt": "2026-07-06T15:00:00+03:00",
  "tickers": [
    {"label": "BIST100", "value": "10.450", "change": "+1,2%", "up": true},
    {"label": "USD/TRY", "value": "32,85", "change": "+0,3%", "up": true},
    ...
  ]
}
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ..config import PROJECT_ROOT, get_logger
from ..sources.bist import BistSource
from ..sources.global_macro import GlobalMacroSource
from ..sources.watchlist import WATCHLIST, fetch_stock_price

log = get_logger(__name__)

TICKER_JSON = PROJECT_ROOT / "web" / "public" / "data" / "market-ticker.json"


def update_ticker_data() -> bool:
    """Anlık fiyatları çekip JSON'a yazar; başarıysa True döner."""
    TR_TZ = timezone(timedelta(hours=3))
    now_str = datetime.now(TR_TZ).isoformat(timespec="seconds")

    tickers: list[dict] = []

    # BIST100
    try:
        bist = BistSource().market_summary()
        tickers.append({
            "label": bist.index,
            "value": bist.price,
            "change": bist.change,
            "up": not bist.change.startswith("-"),
        })
    except Exception as exc:
        log.warning("Ticker JSON — BIST alınamadı: %s", exc)

    # Makro enstrümanlar
    try:
        snap = GlobalMacroSource().snapshot()
        for t in snap.tickers:
            tickers.append({
                "label": t.label,
                "value": t.value_str,
                "change": t.change_str,
                "up": t.change_pct >= 0,
            })
    except Exception as exc:
        log.warning("Ticker JSON — makro alınamadı: %s", exc)

    # TÜRİB ELÜS & Et-Yem Endeksleri
    try:
        from ..sources.turib import TuribSource
        tsnap = TuribSource().snapshot()
        for idx in tsnap.indices:
            if idx.code in ("TRBHUB", "TRBBGD"):
                tickers.append({
                    "label": idx.code,
                    "value": f"{idx.price:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
                    "change": f"{idx.change_pct:+.2f}%".replace(".", ","),
                    "up": idx.change_pct >= 0,
                })
        for prod in tsnap.products:
            if "EKMEKLIK" in prod.product.upper():
                tickers.append({
                    "label": "ELÜS BUĞDAY",
                    "value": f"{prod.avg_price_tl_kg:.2f} ₺",
                    "change": f"{prod.change_pct:+.2f}%".replace(".", ","),
                    "up": prod.change_pct >= 0,
                })
    except Exception as exc:
        log.warning("Ticker JSON — TÜRİB alınamadı: %s", exc)

    try:
        from ..sources.meat_feed_index import MeatFeedIndexAnalyzer
        mrep = MeatFeedIndexAnalyzer().analyze()
        for p in mrep.pariteler:
            if "Dana" in p.kategori:
                tickers.append({
                    "label": "DANA/YEM",
                    "value": f"{p.parite_orani:.1f}x",
                    "change": f"Eşik:{p.esik_basabasi:.0f}",
                    "up": p.parite_orani >= p.esik_basabasi,
                })
    except Exception as exc:
        log.warning("Ticker JSON — Et/Yem alınamadı: %s", exc)

    # BIST-30 watchlist hisseleri
    try:
        from concurrent.futures import ThreadPoolExecutor, as_completed as _as_completed
        with ThreadPoolExecutor(max_workers=8) as pool:
            futures = {pool.submit(fetch_stock_price, sym, tick): tick for sym, tick in WATCHLIST}
            for fut in _as_completed(futures):
                move = fut.result()
                if move:
                    tickers.append({
                        "label": move.ticker,
                        "value": move.price_str,
                        "change": move.change_str,
                        "up": move.change_pct >= 0,
                    })
    except Exception as exc:
        log.warning("Ticker JSON — watchlist alınamadı: %s", exc)

    if not tickers:
        log.warning("Ticker JSON — hiç veri yok; dosya güncellenmedi.")
        return False

    data = {"updatedAt": now_str, "tickers": tickers}

    try:
        TICKER_JSON.parent.mkdir(parents=True, exist_ok=True)
        TICKER_JSON.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        log.info("Ticker JSON güncellendi: %d enstrüman → %s", len(tickers), TICKER_JSON)

        # Ekonomik Takvim verisi
        try:
            from ..sources.calendar import EconomicCalendarSource
            events = EconomicCalendarSource().daily_events(min_importance=0)
            cal_path = TICKER_JSON.parent / "economic-calendar.json"
            cal_data = {"updated_at": now_str, "events": [vars(e) for e in events]}
            cal_path.write_text(json.dumps(cal_data, ensure_ascii=False, indent=2), encoding="utf-8")
            log.info("Ekonomik Takvim JSON güncellendi: %d olay → %s", len(events), cal_path)
        except Exception as exc:
            log.warning("Ekonomik Takvim JSON yazılamadı: %s", exc)

        return True
    except OSError as exc:
        log.error("Ticker JSON yazılamadı: %s", exc)
        return False
