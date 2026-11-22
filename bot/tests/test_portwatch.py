"""IMF PortWatch boğaz sayıları: fixture tabanlı (ağ yok)."""
from datetime import date, timedelta

import pytest
import requests

from esham.publishing import turib_data
from esham.sources import portwatch
from esham.sources.portwatch import PortWatchSource, aggregate_weeks, build_observation

BOS = "Bosporus Strait"


def _row(d, tanker=10, dry=5, cont=3, gen=7, roro=1):
    return {
        "date": d.isoformat(), "portname": BOS, "n_tanker": tanker, "n_dry_bulk": dry,
        "n_container": cont, "n_general_cargo": gen, "n_roro": roro,
        "n_total": tanker + dry + cont + gen + roro,
    }


def _days(start, n, **kw):
    return [_row(start + timedelta(days=i), **kw) for i in range(n)]


MON1 = date(2026, 11, 2)   # önceki hafta (Pzt)
MON2 = date(2026, 11, 9)   # son hafta (Pzt)
MON3 = date(2026, 11, 16)  # eksik hafta


class _Resp:
    def __init__(self, body, status=200):
        self._b, self.status_code = body, status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(str(self.status_code))

    def json(self):
        return self._b


def _patch_http(monkeypatch, query_body, meta_body=None):
    def fake(url, **kw):
        if url.endswith("/query"):
            return _Resp(query_body)
        return _Resp(meta_body if meta_body is not None else {"editingInfo": {"dataLastEditDate": 1794910506451}})

    monkeypatch.setattr(portwatch, "retry_get", fake)


def _feats(rows):
    return {"features": [{"attributes": r} for r in rows]}


def test_complete_weeks_are_summed():
    weeks = aggregate_weeks(_days(MON1, 7) + _days(MON2, 7, tanker=20))
    assert set(weeks) == {MON1, MON2}
    w = weeks[MON2]
    assert (w.week_start, w.week_end) == ("2026-11-09", "2026-11-15")
    assert w.tanker == 140
    assert w.total == 7 * (20 + 5 + 3 + 7 + 1)
    assert weeks[MON1].tanker == 70


def test_partial_week_is_excluded():
    weeks = aggregate_weeks(_days(MON1, 7) + _days(MON2, 7) + _days(MON3, 3))
    assert MON3 not in weeks
    assert set(weeks) == {MON1, MON2}


def test_week_with_missing_day_or_bad_field_is_excluded():
    rows = _days(MON2, 7)
    del rows[3]
    assert aggregate_weeks(rows) == {}
    rows = _days(MON2, 7)
    rows[2]["n_tanker"] = None
    assert aggregate_weeks(rows) == {}
    rows = _days(MON2, 7)
    rows[2]["n_total"] = -1
    assert aggregate_weeks(rows) == {}


def test_observation_uses_latest_complete_week_and_previous():
    obs = build_observation(BOS, _days(MON1, 7, tanker=10) + _days(MON2, 7, tanker=20) + _days(MON3, 2), "2026-11-17")
    assert obs.current.week_end == "2026-11-15" and obs.current.tanker == 140
    assert obs.previous.week_end == "2026-11-08" and obs.previous.tanker == 70
    d = obs.to_dict()
    assert d["asOf"] == "2026-11-15" and d["stale"] is False
    assert d["dataUpdatedAt"] == "2026-11-17"
    assert d["counts"]["tanker"] == 140 and d["previousWeek"]["counts"]["tanker"] == 70
    assert d["source"].startswith("Sources: UN Global Platform; IMF PortWatch")


def test_previous_week_none_when_not_consecutive_or_incomplete():
    obs = build_observation(BOS, _days(MON2, 7), None)
    assert obs.previous is None
    assert obs.to_dict()["previousWeek"] is None
    obs = build_observation(BOS, _days(MON1, 7) + _days(MON2, 7)[:5], None)
    assert obs.current.week_end == "2026-11-08" and obs.previous is None


def test_no_complete_week_gives_none():
    assert build_observation(BOS, _days(MON3, 4), None) is None
    assert build_observation(BOS, [], None) is None
    assert build_observation("Unknown Strait", _days(MON2, 7), None) is None


def test_fetch_returns_observation(monkeypatch):
    _patch_http(monkeypatch, _feats(_days(MON1, 7) + _days(MON2, 7)))
    out = PortWatchSource(today=date(2026, 11, 21)).fetch_straits()
    assert len(out) == 1
    assert out[0].strait == "Bosporus" and out[0].data_updated == "2026-11-17"


@pytest.mark.parametrize("body", [{"features": []}, {"error": {"code": 400}}, {}, [], {"features": "x"}])
def test_fetch_none_on_empty_or_bad_upstream(monkeypatch, body):
    _patch_http(monkeypatch, body)
    assert PortWatchSource(today=date(2026, 11, 21)).fetch_straits() is None


def test_fetch_none_when_request_fails(monkeypatch):
    def boom(*a, **k):
        raise requests.ConnectionError("down")

    monkeypatch.setattr(portwatch, "retry_get", boom)
    assert PortWatchSource().fetch_straits() is None


def test_fetch_ignores_rows_of_other_chokepoints(monkeypatch):
    rows = [dict(r, portname="Suez Canal") for r in _days(MON2, 7)]
    _patch_http(monkeypatch, _feats(rows))
    assert PortWatchSource(today=date(2026, 11, 21)).fetch_straits() is None


# ---- yayın: son iyi değer, özgün asOf ile ---------------------------------------------------

class _NoSource:
    def __init__(self, *a, **k):
        raise RuntimeError("down")


def test_collect_straits_carries_last_good_with_original_asof(monkeypatch):
    monkeypatch.setattr(turib_data, "_today", lambda: date(2026, 11, 20))
    monkeypatch.setattr(portwatch, "PortWatchSource", _NoSource)
    prev = {
        "date": "2026-11-18",
        "petrolTanker": {"straits": [{"strait": "Bosporus", "weekEnd": "2026-11-08", "asOf": "2026-11-08",
                                      "stale": False, "counts": {"tanker": 70}}]},
    }
    out = turib_data._collect_straits(prev)
    assert len(out) == 1
    assert out[0]["asOf"] == "2026-11-08" and out[0]["stale"] is True
    assert out[0]["counts"] == {"tanker": 70}


def test_collect_straits_nothing_without_previous_or_date(monkeypatch):
    monkeypatch.setattr(portwatch, "PortWatchSource", _NoSource)
    assert turib_data._collect_straits(None) == []
    assert turib_data._collect_straits({"petrolTanker": {"straits": [{"strait": "Bosporus"}]}}) == []


def test_collect_straits_fresh_replaces_old(monkeypatch):
    _patch_http(monkeypatch, _feats(_days(MON1, 7) + _days(MON2, 7)))
    prev = {"petrolTanker": {"straits": [{"strait": "Bosporus", "asOf": "2026-10-01"}]}}
    out = turib_data._collect_straits(prev)
    assert len(out) == 1 and out[0]["stale"] is False and out[0]["asOf"] == "2026-11-15"
