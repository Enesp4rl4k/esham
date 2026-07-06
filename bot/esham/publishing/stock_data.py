"""Hisse bazlı veri sayfaları için JSON üretici.

Bot her `run_stock_report(ticker)` çağrısında bu modülü kullanarak
`web/public/data/stocks/{TICKER}.json` dosyasını günceller.

Web sitesi `/hisse/[ticker]` sayfasında bu JSON'ı okur — statik export
uyumlu (API route yok, dosya sistemi üzerinden).

JSON formatı:
{
  "ticker": "THYAO",
  "company": "Türk Hava Yolları A.O.",
  "updatedAt": "2026-07-06T15:00:00+03:00",
  "price": "280,50",
  "change": "+2,3%",
  "volume": "1,2 Milyar TL",
  "summary": "AI tarafından üretilmiş kısa özet...",
  "disclosures": [
    {"date": "2026-07-06", "title": "...", "type": "...", "is_insider": false}
  ]
}
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ..config import PROJECT_ROOT, get_logger
from ..sources.bist import BistSource

log = get_logger(__name__)

STOCKS_DIR = PROJECT_ROOT / "web" / "public" / "data" / "stocks"


def write_stock_json(
    ticker: str,
    company: str,
    summary: str,
    disclosures: list[dict],
    price: str = "",
    change: str = "",
    volume: str = "",
) -> Path | None:
    """Hisse JSON dosyasını yazar/günceller; yazılan dosya yolunu döner."""
    TR_TZ = timezone(timedelta(hours=3))
    now_str = datetime.now(TR_TZ).isoformat(timespec="seconds")

    data = {
        "ticker": ticker.upper(),
        "company": company,
        "updatedAt": now_str,
        "price": price,
        "change": change,
        "volume": volume,
        "summary": summary,
        "disclosures": disclosures,
    }

    try:
        STOCKS_DIR.mkdir(parents=True, exist_ok=True)
        out = STOCKS_DIR / f"{ticker.upper()}.json"
        out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        log.info("Hisse JSON güncellendi: %s → %s", ticker, out)
        return out
    except OSError as exc:
        log.error("Hisse JSON yazılamadı (%s): %s", ticker, exc)
        return None


def read_stock_json(ticker: str) -> dict | None:
    """Var olan hisse JSON'ını okur; yoksa None."""
    try:
        p = STOCKS_DIR / f"{ticker.upper()}.json"
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def list_stock_tickers() -> list[str]:
    """Mevcut tüm hisse ticker'larını döner (JSON dosya adlarından)."""
    try:
        return [p.stem for p in sorted(STOCKS_DIR.glob("*.json"))]
    except OSError:
        return []
