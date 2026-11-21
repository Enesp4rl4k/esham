"""Ekonomik takvim kaynağı.

TradingView'in açık ekonomik takvim API'sini kullanır:
`economic-calendar.tradingview.com/events`. Türkiye ve seçili ülkelerin günlük
önemli veri açıklamalarını getirir. Hata durumunda örnek veriye düşülür.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import requests
from ..http import retry_get

from ..config import default_headers, get_logger, settings
from . import CalendarEvent

log = get_logger(__name__)

EVENTS_URL = "https://economic-calendar.tradingview.com/events"

# TradingView önem kodları -> Türkçe
_IMPORTANCE = {1: "Yüksek", 0: "Orta", -1: "Düşük"}

_COUNTRY = {
    "TR": "Türkiye",
    "US": "ABD",
    "EU": "Euro Bölgesi",
    "GB": "İngiltere",
    "DE": "Almanya",
    "CN": "Çin",
    "JP": "Japonya",
}

# Türkiye saati (UTC+3, sabit).
_TR_TZ = timezone(timedelta(hours=3))


class EconomicCalendarSource:
    def __init__(self, countries: str = "TR,US,EU") -> None:
        self.countries = countries
        self.headers = {**default_headers(), "Origin": "https://www.tradingview.com"}

    def daily_events(self, min_importance: int = 0) -> list[CalendarEvent]:
        """Bugünün olaylarını döner. `min_importance`: -1 hepsi, 0 orta+, 1 sadece yüksek."""
        now = datetime.now(timezone.utc)
        frm = now.replace(hour=0, minute=0, second=0, microsecond=0)
        to = frm + timedelta(days=1)
        try:
            resp = retry_get(
                EVENTS_URL,
                params={
                    "from": frm.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
                    "to": to.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
                    "countries": self.countries,
                },
                headers=self.headers,
                timeout=settings.http_timeout,
            )
            resp.raise_for_status()
            data = resp.json()
        except (requests.RequestException, ValueError) as exc:
            log.warning("Ekonomik takvim alınamadı (%s); boş liste (örnek veri üretilmiyor).", exc)
            return self._sample()

        if data.get("status") != "ok":
            log.warning("Takvim yanıtı beklenmedik; boş liste (örnek veri üretilmiyor).")
            return self._sample()

        events = self._parse(data.get("result", []), min_importance)
        if events:
            return events
        log.info("Takvimde eşleşen olay yok.")
        return self._sample()

    def _parse(self, rows: list[dict], min_importance: int) -> list[CalendarEvent]:
        out: list[CalendarEvent] = []
        for row in rows:
            imp = row.get("importance", -1)
            if not isinstance(imp, int) or imp < min_importance:
                continue
            out.append(
                CalendarEvent(
                    time=self._local_time(row.get("date", "")),
                    country=_COUNTRY.get(row.get("country", ""), row.get("country", "")),
                    event=row.get("title", "").strip(),
                    importance=_IMPORTANCE.get(imp, "Düşük"),
                    forecast=self._format_value(row.get("forecast")),
                )
            )
        out.sort(key=lambda e: e.time)
        return out

    @staticmethod
    def _local_time(iso: str) -> str:
        try:
            dt = datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(_TR_TZ)
            return dt.strftime("%H:%M")
        except (ValueError, AttributeError):
            return "--:--"

    @staticmethod
    def _format_value(value: object) -> str:
        if value is None:
            return ""
        return str(value)

    def _sample(self) -> list[CalendarEvent]:
        # Sahte / yapay ekonomik takvim yayını yapmamak için boş liste dön
        return []
