"""Yahoo chart yanıtından tarihli günlük barlar, dönem değişimi ve seans durumu (saf fonksiyonlar).

Neden: ``meta.chartPreviousClose`` isteğin ARALIĞINA bağlıdır (range=1mo ise bir ay önceki kapanış). Sektör
ve endeks değişimini "günlük" ya da "haftalık" diye yazabilmek için hangi iki kapanışın karşılaştırıldığı
ve son barın TARİHİ bilinmelidir; bu modül ikisini de açıkça döndürür.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

from ..formatting import from_epoch, is_number


@dataclass(frozen=True)
class PeriodChange:
    pct: float
    base_date: date  # karşılaştırılan önceki kapanışın tarihi
    last_date: date  # son barın tarihi (veri tarihi)
    last_close: float


def daily_bars(result: dict) -> list[tuple[date, float]]:
    """chart.result[0] → [(borsa yerel tarihi, kapanış)], tarih başına SON değer, sıralı."""
    try:
        ts = result.get("timestamp") or []
        closes = result["indicators"]["quote"][0].get("close") or []
    except (KeyError, IndexError, TypeError, AttributeError):
        return []
    offset = int((result.get("meta") or {}).get("gmtoffset") or 0)
    tz = timezone(timedelta(seconds=offset))
    by_day: dict[date, float] = {}
    for t, c in zip(ts, closes):
        if t is None or not is_number(c):  # NaN/None bar atlanır
            continue
        try:
            d = datetime.fromtimestamp(int(t), tz=tz).date()
        except (TypeError, ValueError, OverflowError, OSError):
            continue
        by_day[d] = float(c)
    return sorted(by_day.items())


def period_change(bars: list[tuple[date, float]], period: str = "1d") -> PeriodChange | None:
    """``1d``: son kapanış / bir önceki işlem günü kapanışı. ``1w``: son kapanış / son barın haftasından
    ÖNCEKİ son işlem gününün kapanışı (hafta pazartesi başlar). Yeterli bar yoksa None."""
    if len(bars) < 2:
        return None
    last_d, last_c = bars[-1]
    if period == "1d":
        base_d, base_c = bars[-2]
    elif period == "1w":
        monday = last_d - timedelta(days=last_d.weekday())
        prior = [b for b in bars if b[0] < monday]
        if not prior:
            return None
        base_d, base_c = prior[-1]
    else:
        raise ValueError(f"bilinmeyen dönem: {period}")
    if not base_c:
        return None
    return PeriodChange((last_c - base_c) / base_c * 100.0, base_d, last_d, last_c)


def session_info(meta: dict, now: datetime | None = None) -> tuple[datetime | None, bool | None]:
    """(son işlem zamanı TR, seans şu an açık mı). Alan yoksa ilgili değer None."""
    as_of = from_epoch(meta.get("regularMarketTime")) if isinstance(meta, dict) else None
    regular = ((meta or {}).get("currentTradingPeriod") or {}).get("regular") or {}
    start, end = regular.get("start"), regular.get("end")
    is_open: bool | None = None
    if isinstance(start, (int, float)) and isinstance(end, (int, float)):
        now_ts = (now or datetime.now(timezone.utc)).timestamp()
        is_open = start <= now_ts < end
    return as_of, is_open
