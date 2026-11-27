"""Piyasa rakamı içeren şablon cümleleri — TEK yer, her cümle neyi ve NE ZAMANKİ değeri söylediğini yazar.

Kurallar (inceleme 2026-11-27 bulguları):
- Her cümle sayının ne olduğunu açıkça adlandırır: "son işlem", "açılış", "önceki kapanışa göre değişim",
  "haftalık değişim (X kapanışına göre)". Bir alanın yerine başka alan KONMAZ (ör. açılış yokken son fiyat
  "açılış" diye yazılmaz).
- Her cümle veri zamanını taşır (``as_of``); zaman damgası yoksa ya da veri ``freshness.MARKET_DATA_MAX_AGE_DAYS``
  sınırından eskiyse cümle YAZILMAZ (None döner) — "bugün", "güne başladı" gibi ifadeler tahminle kurulmaz.
- Sayılar yalnız ``formatting`` üzerinden biçimlenir.

``SENTENCE_CATALOG``: her şablonun dayandığı veri alanı ve zaman kuralı (``tests/test_semantic_honesty.py``
bu tabloyu üreticilerin gerçek çıktısıyla karşılaştırır).
"""
from __future__ import annotations

from datetime import datetime

from .formatting import tr_date, tr_datetime, tr_number, tr_pct
from .freshness import market_as_of_status
from .sources import MarketSummary
from .sources.bars import PeriodChange
from .sources.sector import PERIOD_LABEL, SectorMove, as_of_of, movers_lines

#: şablon adı -> (kullandığı alanlar, zaman kuralı)
SENTENCE_CATALOG: dict[str, tuple[str, str]] = {
    "bist_last": (
        "MarketSummary.price (son işlem), .change_pct (önceki kapanışa göre), .as_of, .market_open",
        "as_of zorunlu ve en çok MARKET_DATA_MAX_AGE_DAYS gün eski; tarih+saat cümlede yazılır",
    ),
    "bist_open": (
        "MarketSummary.open_price (açılış), .open_change_pct (açılışın önceki kapanışa göre farkı), .as_of",
        "as_of bugünün (TSİ) tarihi olmalı; yoksa açılış cümlesi yazılmaz",
    ),
    "bist_close": (
        "MarketSummary.price (kapanış), .change_pct, .as_of, .market_open=False",
        "as_of bugünün tarihi VE seans kapalı olmalı; yoksa 'kapattı' denmez",
    ),
    "bist_week": (
        "PeriodChange(period='1w').last_close, .pct, .base_date, .last_date",
        "iki kapanış tarihi de cümlede yazılır",
    ),
    "sector_movers": (
        "SectorMove.change_pct (period: günlük/haftalık), .as_of",
        "yükselen listesi yalnız >0, düşen listesi yalnız <0; veri tarihi başlıkta",
    ),
    "viop_index": (
        "ViopQuote.index_price, .index_change (önceki kapanışa göre), .fetched_at",
        "TradingView işlem zamanı vermez: 'veri alınma zamanı' olarak etiketlenir",
    ),
}


def _usable(b: MarketSummary | None, now: datetime) -> bool:
    return bool(b and b.price and b.change_pct is not None
                and market_as_of_status(b.as_of, now) in ("today", "previous"))


def session_note(b: MarketSummary) -> str:
    if b.market_open is True:
        return " Seans açık; rakamlar gün içi."
    if b.market_open is False:
        return " Seans şu an kapalı."
    return ""


def bist_last(b: MarketSummary | None, now: datetime) -> str | None:
    """'BIST XU100 endeksinde son işlem: 10.977,01 (27.11.2026 18:10 TSİ); önceki kapanışa göre değişim +%2,18.'"""
    if not _usable(b, now):
        return None
    assert b is not None and b.as_of is not None
    return (
        f"BIST {b.index} endeksinde son işlem: {b.price} ({tr_datetime(b.as_of)}); "
        f"önceki kapanışa göre değişim {b.change}."
    )


def bist_last_short(b: MarketSummary | None, now: datetime) -> str | None:
    """Özet/Telegram için kısa biçim: 'XU100 son işlem 10.977,01 (27.11.2026 18:10 TSİ), önceki kapanışa göre +%2,18.'"""
    if not _usable(b, now):
        return None
    assert b is not None and b.as_of is not None
    return f"{b.index} son işlem {b.price} ({tr_datetime(b.as_of)}), önceki kapanışa göre {b.change}."


def bist_open(b: MarketSummary | None, now: datetime) -> str | None:
    """'Borsa İstanbul XU100 endeksi 27.11.2026 seansını 10.737,18 puandan açtı; açılışın önceki kapanışa göre
    farkı -%0,06.' — yalnız bugünün açılışı ve açılış alanları varsa."""
    if not (b and b.open_price and b.open_change_pct is not None
            and market_as_of_status(b.as_of, now) == "today"):
        return None
    assert b.as_of is not None
    return (
        f"Borsa İstanbul {b.index} endeksi {tr_date(b.as_of)} seansını {b.open_price} puandan açtı; "
        f"açılışın önceki kapanışa göre farkı {b.open_change}."
    )


def bist_close(b: MarketSummary | None, now: datetime) -> str | None:
    """'BIST XU100 endeksi 27.11.2026 seansını 10.977,01 puandan kapattı; önceki kapanışa göre değişim +%2,18.'"""
    if not (_usable(b, now) and b is not None and b.market_open is False
            and market_as_of_status(b.as_of, now) == "today"):
        return None
    assert b.as_of is not None
    return (
        f"BIST {b.index} endeksi {tr_date(b.as_of)} seansını {b.price} puandan kapattı; "
        f"önceki kapanışa göre değişim {b.change}."
    )


def bist_week(index: str, wk: PeriodChange | None) -> str | None:
    """'BIST XU100 endeksi 27.11.2026 kapanışında 10.977,01; 21.11.2026 kapanışına göre haftalık değişim -%1,39.'"""
    if wk is None:
        return None
    return (
        f"BIST {index} endeksi {tr_date(wk.last_date)} kapanışında {tr_number(wk.last_close)}; "
        f"{tr_date(wk.base_date)} kapanışına göre haftalık değişim {tr_pct(wk.pct)}."
    )


def sector_heading_note(moves: list[SectorMove]) -> str:
    """'günlük değişim (önceki kapanışa göre; veri tarihi 27.11.2026)' — tarihsizse tarih yazılmaz."""
    period = PERIOD_LABEL.get(moves[0].period, "günlük") if moves else "günlük"
    basis = "önceki kapanışa göre" if period == "günlük" else "önceki haftanın son kapanışına göre"
    d = as_of_of(moves)
    return f"{period} değişim ({basis}" + (f"; veri tarihi {tr_date(d)})" if d else ")")


def sector_movers_md(moves: list[SectorMove], n: int = 3) -> str:
    """İki madde: yalnız pozitifler / yalnız negatifler; yoksa 'yükselen/düşen sektör yok'."""
    ups, downs = movers_lines(moves, n)
    period = PERIOD_LABEL.get(moves[0].period, "günlük") if moves else "günlük"
    return (
        f"- **Yükselen sektörler (en yüksek {period} değişim):** {ups}\n"
        f"- **Düşen sektörler (en düşük {period} değişim):** {downs}"
    )


def viop_index_line(q) -> str:
    """'BIST 30 endeksi (XU030; VİOP endeks kontratlarının dayanağı): 13.763,83, önceki kapanışa göre +%2,31.'"""
    when = f" Veri alınma zamanı: {tr_datetime(q.fetched_at)}." if getattr(q, "fetched_at", None) else ""
    line = (
        f"BIST 30 endeksi ({q.index_symbol}; VİOP endeks kontratlarının dayanağı): {q.index_price}, "
        f"önceki kapanışa göre {q.index_change}."
    )
    if q.has_futures:
        line += f" Vadeli {q.futures_symbol}: {q.futures_price}"
        line += f", önceki kapanışa göre {q.futures_change}." if q.futures_change else "."
    return line + when
