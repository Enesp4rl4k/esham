"""Makro göstergeler: TCMB faiz sayfası ayrıştırma, USD/TRY değişimi, EVDS (anahtar yalnızca EVDS_API_KEY ile; sızıntı yok)."""
import json
import logging
import traceback
from datetime import date, datetime, timezone
from pathlib import Path

import pytest
import requests

from esham import freshness
from esham.jobs import publish_macro as pm
from esham.sources import tcmb_evds as EV
from esham.sources.real_returns import TcmbRate

FIX = Path(__file__).parent / "fixtures"
SECRET = "TEST-SECRET-KEY-0123456789abcdef"
TODAY = date(2026, 11, 23)


# ---- TCMB politika faizi ------------------------------------------------------------------

def test_policy_rate_parses_latest_change_from_recorded_page():
    p = pm.parse_policy_rate((FIX / "tcmb_1hafta_repo_20261123.html").read_bytes())
    assert p == {"asOf": "2026-10-23", "value": 36.0}  # sayfadaki son satır: 23.10.2026 / 36.00


def test_policy_rate_unknown_layout_is_rejected():
    with pytest.raises(pm.MacroParseError):
        pm.parse_policy_rate(b"<html><table id='midTable'><tr><td>x</td><td>y</td><td>z</td></tr></table></html>")
    with pytest.raises(pm.MacroParseError):
        pm.parse_policy_rate(b"<html>tablo yok</html>")


def test_policy_rate_bad_row_is_rejected_not_skipped():
    html = (FIX / "tcmb_1hafta_repo_20261123.html").read_text(encoding="utf-8").replace("36.00", "otuz altı")
    with pytest.raises(pm.MacroParseError):
        pm.parse_policy_rate(html.encode("utf-8"))


# ---- USD/TRY değişimi: yalnızca iki gerçek bülten --------------------------------------------

class _Fx:
    rates = {"2026-11-20": 50.0, "2026-10-21": 40.0, "2025-11-20": 25.0}

    def rate_on_or_before(self, day):
        if day in self.rates:
            return TcmbRate(day, self.rates[day], 55.0)
        raise pm.FxUnavailable(day)


def test_fx_pace_uses_two_real_bulletins_and_states_them():
    fx = _Fx()
    out = pm.fx_pace_indicators(fx, date(2026, 11, 20), "2026-11-23T10:00:00+00:00")
    by = {i["id"]: i for i in out}
    assert by["usdtry_30d"]["value"] == 25.0 and by["usdtry_365d"]["value"] == 100.0
    assert "2026-10-21 bülteni 40.0000" in by["usdtry_30d"]["note"]
    assert all(i["asOf"] == "2026-11-20" and i["sourceUrl"].startswith("https://www.tcmb.gov.tr") for i in out)


# ---- EVDS ----------------------------------------------------------------------------------

EVDS_DOC = {"totalCount": 3, "items": [
    {"Tarih": "2025-9", "TP_FG_J0": "2000.00", "UNIXTIME": {"$numberLong": "1"}},
    {"Tarih": "2026-8", "TP_FG_J0": "2900.00"},
    {"Tarih": "2026-9", "TP_FG_J0": "3000.00"},
    {"Tarih": "2026-10", "TP_FG_J0": ""},          # boş: atlanır
    {"Tarih": "bozuk", "TP_FG_J0": "1"},            # atlanır
]}


def test_evds_parse_and_yoy_from_documented_format():
    pts, skipped = EV.parse_series(EVDS_DOC, "TP.FG.J0")
    assert skipped == 2 and pts[-1] == (date(2026, 9, 1), 3000.0)
    assert EV.compute(EV.INDICATORS[0], pts) == {"value": 50.0, "asOf": "2026-09-01"}  # 3000/2000-1


def test_evds_yoy_requires_exact_year_ago_point():
    pts, _ = EV.parse_series({"items": [{"Tarih": "2026-9", "TP_FG_J0": "3000"}]}, "TP.FG.J0")
    with pytest.raises(EV.EvdsError):
        EV.compute(EV.INDICATORS[0], pts)


def test_evds_rejects_ambiguous_number_formats_and_bad_documents():
    pts, skipped = EV.parse_series({"items": [{"Tarih": "01-09-2026", "TP_FG_J0": "1.234,5"}]}, "TP.FG.J0")
    assert pts == [] and skipped == 1
    with pytest.raises(EV.EvdsError):
        EV.parse_series({"hata": 1}, "TP.FG.J0")


def test_no_key_means_no_evds_request_and_no_evds_indicator(monkeypatch, tmp_path):
    monkeypatch.delenv(EV.ENV_KEY, raising=False)
    called = []
    run = pm.run_macro(data_dir=tmp_path, today=TODAY, get=_policy_get, fx=_Fx_today(),
                       evds_fetch=lambda *a, **k: called.append(a))
    assert run == 1 and called == []
    doc = json.loads((tmp_path / pm.OUT_FILE).read_text(encoding="utf-8"))
    assert doc["evdsEnabled"] is False
    assert {i["id"] for i in doc["indicators"]} == {"policy_rate", "usdtry_30d", "usdtry_365d"}


class _Resp:
    def __init__(self, content=b"", status=200, payload=None):
        self.content, self.status_code, self._p = content, status, payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code}")

    def json(self):
        return self._p


def _policy_get(url, **k):
    return _Resp((FIX / "tcmb_1hafta_repo_20261123.html").read_bytes())


class _Fx_today(_Fx):
    rates = {"2026-11-23": 50.0, "2026-10-24": 40.0, "2025-11-23": 25.0}


def test_key_is_sent_only_as_header_never_in_url(monkeypatch):
    seen = {}

    def get(url, headers=None, timeout=None):
        seen.update(url=url, headers=headers)
        return _Resp(payload=EVDS_DOC)

    EV.fetch_series("TP.FG.J0", date(2025, 1, 1), TODAY, SECRET, get=get)
    assert seen["headers"]["key"] == SECRET
    assert SECRET not in seen["url"] and "key=" not in seen["url"].lower()


def test_evds_key_never_appears_in_logs_errors_tracebacks_or_files(monkeypatch, tmp_path, caplog):
    monkeypatch.setenv(EV.ENV_KEY, SECRET)
    caplog.set_level(logging.DEBUG)
    outputs = []

    def failing_get(url, headers=None, timeout=None):
        # istemci hataları isteği (başlıklar dahil) iletiye gömebilir: bizim sarmalayıcı bunu AKTARMAMALI
        raise requests.ConnectionError(f"bağlantı koptu url={url} headers={headers}")

    with pytest.raises(EV.EvdsError) as e1:
        EV.fetch_series("TP.FG.J0", date(2025, 1, 1), TODAY, SECRET, get=failing_get)
    outputs.append("".join(traceback.format_exception(e1.value)))

    with pytest.raises(EV.EvdsError) as e2:
        EV.fetch_series("TP.FG.J0", date(2025, 1, 1), TODAY, SECRET,
                        get=lambda *a, **k: _Resp(status=403, payload={"message": f"Required request header 'key' = {SECRET}"}))
    outputs.append("".join(traceback.format_exception(e2.value)))

    # tüm iş akışı: ağ hatalı EVDS + gerçek biçimli diğer kaynaklar
    run = pm.run_macro(data_dir=tmp_path, today=TODAY, get=_policy_get, fx=_Fx_today(), evds_fetch=lambda *a, **k: EV.fetch_series(*a, get=failing_get))
    assert run == 1
    outputs.append(caplog.text)
    outputs += [p.read_text(encoding="utf-8") for p in tmp_path.rglob("*") if p.is_file()]
    outputs += [str(e1.value), str(e2.value)]
    for text in outputs:
        assert SECRET not in text
    doc = json.loads((tmp_path / pm.OUT_FILE).read_text(encoding="utf-8"))
    assert doc["evdsEnabled"] is True
    assert {i["id"] for i in doc["indicators"]}.isdisjoint({"cpi_yoy", "reer"})  # alınamayan gösterge uydurulmaz


def test_evds_success_carries_series_source_and_date(monkeypatch, tmp_path):
    monkeypatch.setenv(EV.ENV_KEY, SECRET)

    def evds_fetch(series, start, end, key):
        assert key == SECRET
        doc = EVDS_DOC if series == "TP.FG.J0" else {"items": [{"Tarih": "2026-9", "TP_RK_T1_Y": "55.5"}]}
        return EV.parse_series(doc, series)

    pm.run_macro(data_dir=tmp_path, today=TODAY, get=_policy_get, fx=_Fx_today(), evds_fetch=evds_fetch)
    doc = json.loads((tmp_path / pm.OUT_FILE).read_text(encoding="utf-8"))
    by = {i["id"]: i for i in doc["indicators"]}
    assert by["cpi_yoy"]["value"] == 50.0 and by["cpi_yoy"]["asOf"] == "2026-09-01" and "TP.FG.J0" in by["cpi_yoy"]["source"]
    assert by["reer"]["value"] == 55.5
    assert all(i["fetchedAt"] and i["sourceUrl"] and i["asOf"] for i in doc["indicators"])
    assert SECRET not in (tmp_path / pm.OUT_FILE).read_text(encoding="utf-8")


def test_failed_indicator_keeps_last_good_value_with_original_date_marked_stale(tmp_path):
    prev = {"indicators": [{"id": "policy_rate", "value": 40.0, "asOf": "2026-06-01", "stale": False, "fetchedAt": "x"},
                           {"id": "cpi_yoy", "value": 33.0, "asOf": "2026-08-01", "stale": False, "fetchedAt": "y"}]}
    merged = pm.merge_with_previous([], prev, {"policy_rate"})
    assert merged == [{"id": "policy_rate", "value": 40.0, "asOf": "2026-06-01", "stale": True, "fetchedAt": "x"}]  # EVDS denenmedi → taşınmaz


def test_total_failure_writes_nothing(tmp_path):
    def boom(url, **k):
        raise requests.ConnectionError("x")

    class NoFx:
        def rate_on_or_before(self, d):
            raise pm.FxUnavailable(d)

    assert pm.run_macro(data_dir=tmp_path, today=TODAY, get=boom, fx=NoFx()) == 0
    assert not (tmp_path / pm.OUT_FILE).exists()


# ---- tazelik ölçümü ------------------------------------------------------------------------

def test_freshness_sections_missing_without_files_and_stale_when_old(tmp_path):
    now = datetime(2026, 11, 24, 12, 0, tzinfo=timezone.utc)
    secs = {s.id: s for s in freshness._kap_event_sections(now, tmp_path)}
    assert {k: v.status for k, v in secs.items()} == {"kap_dividends": "missing", "kap_buybacks": "missing", "macro_indicators": "missing"}
    old = "2026-11-01T10:00:00+00:00"
    scan = {"universeSize": 110, "tickersWithDisclosure": 3, "parsed": 3, "pending": 0}
    (tmp_path / "kap-dividends.json").write_text(json.dumps({"fetchedAt": old, "asOf": "2026-10-30", "scan": scan}), encoding="utf-8")
    (tmp_path / "macro-indicators.json").write_text(json.dumps({"fetchedAt": now.isoformat(), "evdsEnabled": False,
                                                                 "indicators": [{"id": "a", "stale": True}]}), encoding="utf-8")
    secs = {s.id: s for s in freshness._kap_event_sections(now, tmp_path)}
    assert secs["kap_dividends"].status == "stale" and "110 hisseden 3" in secs["kap_dividends"].detail
    assert secs["macro_indicators"].status == "stale" and "EVDS_API_KEY" in secs["macro_indicators"].detail
