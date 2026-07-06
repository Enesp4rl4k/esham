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

    if not tickers:
        log.warning("Ticker JSON — hiç veri yok; dosya güncellenmedi.")
        return False

    data = {"updatedAt": now_str, "tickers": tickers}

    try:
        TICKER_JSON.parent.mkdir(parents=True, exist_ok=True)
        TICKER_JSON.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        log.info("Ticker JSON güncellendi: %d enstrüman → %s", len(tickers), TICKER_JSON)
        return True
    except OSError as exc:
        log.error("Ticker JSON yazılamadı: %s", exc)
        return False
