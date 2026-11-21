"""IMF PortWatch — İstanbul Boğazı haftalık gemi geçiş SAYIMLARI (gözlem katmanı).

Kaynak: IMF PortWatch `Daily_Chokepoints_Data` (ArcGIS FeatureServer). Günlük "transit call" sayıları
gemi türüne göre (tanker, dökme yük, konteyner, genel kargo, ro-ro); BM Global Platform AIS verisine dayanır.
Veri kümesinde yalnızca "Bosporus Strait" vardır; Çanakkale (Dardanelles) kümede YOKTUR ve burada üretilmez.

Kurallar: yalnızca TAMAMLANMIŞ ISO haftaları (Pzt-Paz, 7 günün tamamı var) yayınlanır; eksik hafta tam
haftaymış gibi sunulmaz. Yanıt boş/hatalıysa `None` döner — varsayılan sayı yazılmaz. Sayılar tahmindir
(AIS yayını kapatan gemiler sayılmaz) ve resmî istatistik değildir.

Atıf (sağlayıcının önerisi): "Sources: UN Global Platform; IMF PortWatch (portwatch.imf.org)."
Lisans: https://www.imf.org/external/terms.htm (Data - Special Terms: atıfla kopyalama/türev/yayın serbest).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any

from ..config import get_logger, settings
from ..http import retry_get

log = get_logger(__name__)

SERVICE_URL = (
    "https://services9.arcgis.com/weJ1QsnbMYJlCHdG/ArcGIS/rest/services/"
    "Daily_Chokepoints_Data/FeatureServer/0"
)
CITATION = "Sources: UN Global Platform; IMF PortWatch (portwatch.imf.org)."
SOURCE_URL = "https://portwatch.imf.org/"

#: Veri kümesindeki ad -> yayın anahtarı ve Türkçe ad. Çanakkale kümede yok.
STRAITS = {"Bosporus Strait": ("Bosporus", "İstanbul Boğazı")}

#: Sorguya alınan geriye dönük gün (yaklaşık 5 hafta + yayın gecikmesi payı).
LOOKBACK_DAYS = 42

_FIELDS = ("n_tanker", "n_dry_bulk", "n_container", "n_general_cargo", "n_roro", "n_total")


@dataclass(frozen=True)
class WeekCounts:
    week_start: str  # Pazartesi
    week_end: str  # Pazar
    tanker: int
    dry_bulk: int
    container: int
    general_cargo: int
    roro: int
    total: int

    def counts_dict(self) -> dict[str, int]:
        return {
            "tanker": self.tanker,
            "dryBulk": self.dry_bulk,
            "container": self.container,
            "generalCargo": self.general_cargo,
            "roro": self.roro,
            "total": self.total,
        }


@dataclass(frozen=True)
class StraitObservation:
    strait: str
    name: str
    current: WeekCounts
    previous: WeekCounts | None
    data_updated: str | None  # veri kümesinin kendi son güncelleme tarihi (UTC, YYYY-MM-DD)

    def to_dict(self) -> dict[str, Any]:
        prev = None
        if self.previous is not None:
            prev = {
                "weekStart": self.previous.week_start,
                "weekEnd": self.previous.week_end,
                "counts": self.previous.counts_dict(),
            }
        return {
            "strait": self.strait,
            "name": self.name,
            "weekStart": self.current.week_start,
            "weekEnd": self.current.week_end,
            "asOf": self.current.week_end,
            "stale": False,
            "counts": self.current.counts_dict(),
            "previousWeek": prev,
            "dataUpdatedAt": self.data_updated,
            "source": CITATION,
            "sourceUrl": SOURCE_URL,
        }


def _to_date(value: Any) -> date | None:
    """ArcGIS DateOnly alanı: 'YYYY-MM-DD' metni (ya da epoch ms) -> date."""
    try:
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(value / 1000, tz=timezone.utc).date()
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError, OSError, OverflowError):
        return None


def aggregate_weeks(rows: list[dict[str, Any]]) -> dict[date, WeekCounts]:
    """Günlük satırları ISO haftalarına toplar; yalnızca 7 günü de tam olan haftaları döndürür.

    Anahtar: haftanın Pazartesi tarihi. Bir günde eksik/negatif/sayı olmayan alan varsa o hafta atılır.
    """
    by_week: dict[date, dict[date, dict[str, int]]] = {}
    broken: set[date] = set()
    for row in rows:
        d = _to_date(row.get("date"))
        if d is None:
            continue
        monday = d - timedelta(days=d.weekday())
        vals: dict[str, int] = {}
        for f in _FIELDS:
            v = row.get(f)
            if isinstance(v, bool) or not isinstance(v, (int, float)) or v < 0 or int(v) != v:
                broken.add(monday)
                break
            vals[f] = int(v)
        else:
            by_week.setdefault(monday, {})[d] = vals

    out: dict[date, WeekCounts] = {}
    for monday, days in by_week.items():
        if monday in broken or len(days) != 7:
            continue
        sums = {f: sum(v[f] for v in days.values()) for f in _FIELDS}
        out[monday] = WeekCounts(
            week_start=monday.isoformat(),
            week_end=(monday + timedelta(days=6)).isoformat(),
            tanker=sums["n_tanker"],
            dry_bulk=sums["n_dry_bulk"],
            container=sums["n_container"],
            general_cargo=sums["n_general_cargo"],
            roro=sums["n_roro"],
            total=sums["n_total"],
        )
    return out


def build_observation(
    portname: str, rows: list[dict[str, Any]], data_updated: str | None
) -> StraitObservation | None:
    """Son tamamlanmış hafta + (ardışıksa) önceki hafta; tamamlanmış hafta yoksa None."""
    weeks = aggregate_weeks(rows)
    if not weeks or portname not in STRAITS:
        return None
    latest = max(weeks)
    key, name = STRAITS[portname]
    return StraitObservation(
        strait=key,
        name=name,
        current=weeks[latest],
        previous=weeks.get(latest - timedelta(days=7)),
        data_updated=data_updated,
    )


class PortWatchSource:
    def __init__(self, today: date | None = None) -> None:
        self._today = today

    def _get_json(self, path: str, params: dict[str, str]) -> dict[str, Any] | None:
        try:
            resp = retry_get(
                SERVICE_URL + path,
                params=params,
                headers={"User-Agent": "esham-bot (+https://esham.pages.dev)"},
                timeout=settings.http_timeout,
            )
            resp.raise_for_status()
            body = resp.json()
        except Exception as exc:  # noqa: BLE001 - kaynak hatası yayını durdurmamalı
            log.warning("PortWatch: istek başarısız: %s", exc)
            return None
        if not isinstance(body, dict) or "error" in body:
            log.warning("PortWatch: hatalı yanıt gövdesi.")
            return None
        return body

    def _data_updated(self) -> str | None:
        meta = self._get_json("", {"f": "json"})
        try:
            ms = meta["editingInfo"]["dataLastEditDate"] if meta else None
            d = _to_date(ms) if ms else None
        except (KeyError, TypeError):
            d = None
        return d.isoformat() if d else None

    def fetch_straits(self) -> list[StraitObservation] | None:
        """Boğaz gözlemleri; yanıt boş/hatalıysa None (sayı uydurulmaz)."""
        today = self._today or datetime.now(timezone.utc).date()
        since = (today - timedelta(days=LOOKBACK_DAYS)).isoformat()
        results: list[StraitObservation] = []
        updated: str | None = None
        for portname in STRAITS:
            body = self._get_json("/query", {
                "where": f"portname='{portname}' AND date >= timestamp '{since}'",
                "outFields": "date,portname," + ",".join(_FIELDS),
                "orderByFields": "date",
                "returnGeometry": "false",
                "resultRecordCount": "200",
                "f": "json",
            })
            feats = body.get("features") if body else None
            if not isinstance(feats, list) or not feats:
                log.warning("PortWatch: %s için satır yok.", portname)
                continue
            rows = [
                f["attributes"] for f in feats
                if isinstance(f, dict) and isinstance(f.get("attributes"), dict)
                and f["attributes"].get("portname") == portname
            ]
            if updated is None:
                updated = self._data_updated()
            obs = build_observation(portname, rows, updated)
            if obs is not None:
                results.append(obs)
        return results or None
