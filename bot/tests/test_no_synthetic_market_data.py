"""Sentetik/sessizce düşen piyasa verisi yok: VİOP vadeli, TÜRİB taşıma, açılış VİOP satırı (ağ yok)."""
import inspect
import json
import logging
from types import SimpleNamespace

import pytest
import requests

from esham import pipeline
from esham.publishing import turib_data
from esham.sources import viop
from esham.sources.viop import ViopSource

IDX = ["BIST:XU030", 16000.0, 1.5, 1_000_000.0]
FUT = ["BIST:XU030D", 16200.0, 1.2, 500_000.0]


def _payload(*rows):
    return {"data": [{"s": r[0], "d": r} for r in rows]}


# ---- (1) VİOP vadeli kotasyon -------------------------------------------------

def test_missing_futures_row_gives_no_futures_quote():
    q = ViopSource()._parse_quote(_payload(IDX))
    assert q is not None and q.index_price
    assert q.futures_symbol is None and q.futures_price is None
    assert q.futures_change is None and q.futures_volume is None
    assert q.has_futures is False
    # sentetik spot*1.0125 (= 16.200,00) hiçbir yerde görünmez
    assert "16.200" not in repr(q)


def test_futures_row_without_price_is_not_a_quote():
    q = ViopSource()._parse_quote(_payload(IDX, ["BIST:XU030D", None, None, None]))
    assert q is not None and q.has_futures is False and q.futures_price is None


def test_real_futures_row_is_parsed():
    q = ViopSource()._parse_quote(_payload(IDX, FUT))
    assert q.has_futures and q.futures_symbol == "XU030D"
    assert q.futures_price == "16.200,00" and q.futures_change == "+1,20%"


def test_no_index_row_gives_none():
    assert ViopSource()._parse_quote(_payload(FUT)) is None


def test_no_synthetic_derivation_left_in_source():
    assert "1.0125" not in inspect.getsource(viop)


def _fake_source(quote):
    class _Src:
        def market_quote(self):
            return quote

        def margin_snapshot(self):
            return SimpleNamespace(
                required_margin_total_tl=1.0, margin_call_total_tl=0.1, margined_account_count=1,
                margin_call_to_required_pct=10.0,
                margin_call_pretty=lambda: "0,1", required_pretty=lambda: "1",
            )
    return _Src


def test_viop_report_skips_futures_row_when_missing(monkeypatch):
    captured = {}

    class _Store:
        def publish(self, draft):
            captured["body"] = draft.body
            return None  # guardrail yolunu simüle et: yayın yok

    q = ViopSource()._parse_quote(_payload(IDX))
    monkeypatch.setattr(pipeline, "ViopSource", _fake_source(q))
    monkeypatch.setattr(pipeline, "ContentStore", _Store)
    monkeypatch.setattr(pipeline, "_render_card", lambda *_a, **_k: None)
    monkeypatch.setattr(pipeline, "_cleanup", lambda *_a, **_k: None)
    import esham.state as state
    monkeypatch.setattr(state, "get_state", lambda: SimpleNamespace(
        get_margin_prev_pct=lambda: None, set_margin_prev_pct=lambda *_: None))
    assert pipeline.run_viop_report(prior_pct=10.0, publish=True, publish_social=False) is None
    assert "Vadeli" not in captured["body"] and "Endeks XU030" in captured["body"]


def test_viop_report_none_quote_aborts(monkeypatch):
    monkeypatch.setattr(pipeline, "ViopSource", _fake_source(None))
    assert pipeline.run_viop_report(publish=False) is None


# ---- (3) pipeline açılış VİOP satırı ---------------------------------------------

def _patch_quote(monkeypatch, quote=None, exc=None):
    class _Src:
        def market_quote(self):
            if exc:
                raise exc
            return quote
    monkeypatch.setattr(pipeline, "ViopSource", _Src)


def test_opening_line_uses_real_futures_quote(monkeypatch):
    _patch_quote(monkeypatch, ViopSource()._parse_quote(_payload(IDX, FUT)))
    line = pipeline._opening_viop_line()
    assert "XU030D" in line and "+1,20%" in line


def test_opening_line_empty_without_futures(monkeypatch):
    _patch_quote(monkeypatch, ViopSource()._parse_quote(_payload(IDX)))
    assert pipeline._opening_viop_line() == ""
    _patch_quote(monkeypatch, None)
    assert pipeline._opening_viop_line() == ""


def test_opening_line_network_failure_is_warning_not_crash(monkeypatch, caplog):
    _patch_quote(monkeypatch, exc=requests.ConnectionError("down"))
    with caplog.at_level(logging.WARNING):
        assert pipeline._opening_viop_line() == ""
    assert not [r for r in caplog.records if r.levelno >= logging.ERROR]


def test_opening_line_programming_error_logged_as_error(monkeypatch, caplog):
    _patch_quote(monkeypatch, exc=AttributeError("no such method"))
    with caplog.at_level(logging.WARNING):
        assert pipeline._opening_viop_line() == ""
    assert any(r.levelno >= logging.ERROR for r in caplog.records)


def test_dead_snapshot_call_removed():
    assert not hasattr(ViopSource, "snapshot")
    assert "ViopSource().snapshot" not in open(pipeline.__file__, encoding="utf-8").read()


# ---- (2) TÜRİB taşıma ------------------------------------------------------------

class _Boom:
    def __init__(self, *a, **k):
        raise RuntimeError("source down")


def _tmo_report(name):
    return SimpleNamespace(
        urun_grubu=name, tarih="2026-11-21", tmo_urun_adi=name, tmo_yil=2026, tmo_alim_fiyati=10.0,
        bakanlik_destegi=1.0, toplam_uretici_fiyati=11.0, tmo_satis_fiyati=None,
        serbest_piyasa_fiyati=12.0, alim_farki_tl=2.0, alim_prim_yuzde=20.0, toplam_prim_yuzde=9.0,
        piyasa_durumu="TMO_USTUNDE_PRIMLI", piyasa_yorumu="x",
        tmo_kaynak_url="https://www.tarimorman.gov.tr/x", tmo_duyuru_tarihi="2026-06-02", tmo_dogrulandi=True,
    )


@pytest.fixture
def offline_turib(monkeypatch):
    for n in ("TuribSource", "MeatFeedIndexAnalyzer", "RealReturnsCalculator",
              "StorageStrategyBacktester", "RegionalArbitrageScanner", "AgriBistAnalyzer"):
        monkeypatch.setattr(turib_data, n, _Boom)

    class _Tmo:
        def compare(self, urun_grubu, manuel_fiyat=None):
            if urun_grubu in ("MISIR", "ARPA"):
                raise ValueError("canlı fiyat yok")
            return _tmo_report(urun_grubu)
    monkeypatch.setattr(turib_data, "TmoSource", _Tmo)
    import esham.sources.tanker_freight as tf
    monkeypatch.setattr(tf, "TankerFreightSource", _Boom)


def _old(commodity, as_of=None, price=9.99):
    e = {"commodity": commodity, "turibFreePrice": price, "spreadTl": 1.0,
         "tmoVerified": True, "tmoSource": "https://www.tarimorman.gov.tr/x"}
    if as_of:
        e["asOf"] = as_of
    return e


def test_turib_carry_over_keeps_last_good_value_and_original_date(offline_turib):
    prev = {"date": "2026-11-18", "tmoComparison": [_old("MISIR", "2026-11-17"), _old("ARPA")]}
    data = turib_data.generate_turib_market_data(previous=prev)
    by = {e["commodity"]: e for e in data["tmoComparison"]}
    assert set(by) == {"BUĞDAY EKMEKLİK", "BUĞDAY MAKARNALIK", "MISIR", "ARPA"}
    assert by["MISIR"]["turibFreePrice"] == 9.99 and by["MISIR"]["asOf"] == "2026-11-17"
    assert by["MISIR"]["stale"] is True
    assert by["ARPA"]["asOf"] == "2026-11-18"  # tarihsiz eski girdi: önceki yayının tarihi
    assert by["BUĞDAY EKMEKLİK"]["asOf"] == "2026-11-21" and "stale" not in by["BUĞDAY EKMEKLİK"]


def test_turib_no_previous_value_is_omitted(offline_turib):
    for prev in (None, {"date": "2026-11-18", "tmoComparison": []}, {"tmoComparison": [_old("MISIR")]}):
        data = turib_data.generate_turib_market_data(previous=prev)
        names = {e["commodity"] for e in data["tmoComparison"]}
        assert "MISIR" not in names and "ARPA" not in names


def test_turib_update_roundtrip_keeps_original_date(offline_turib, monkeypatch, tmp_path):
    path = tmp_path / "turib-market.json"
    path.write_text(json.dumps({"date": "2026-11-18", "tmoComparison": [_old("MISIR", "2026-11-17")]}),
                    encoding="utf-8")
    monkeypatch.setattr(turib_data, "TURIB_JSON", path)
    assert turib_data.update_turib_market_data() is True
    out = json.loads(path.read_text(encoding="utf-8"))
    misir = [e for e in out["tmoComparison"] if e["commodity"] == "MISIR"][0]
    assert misir["asOf"] == "2026-11-17" and misir["stale"] is True
    # ikinci tur: tarih yeniden damgalanmaz
    assert turib_data.update_turib_market_data() is True
    out2 = json.loads(path.read_text(encoding="utf-8"))
    assert [e for e in out2["tmoComparison"] if e["commodity"] == "MISIR"][0]["asOf"] == "2026-11-17"


def test_turib_corrupt_previous_file_is_ignored(tmp_path):
    p = tmp_path / "x.json"
    p.write_text("{bad", encoding="utf-8")
    assert turib_data.load_previous_market_data(p) is None
    assert turib_data.load_previous_market_data(tmp_path / "missing.json") is None


def test_tmo_entries_carry_explicit_source_and_season(offline_turib):
    data = turib_data.generate_turib_market_data(previous=None)
    live = [e for e in data["tmoComparison"] if not e.get("stale")]
    assert live
    for e in live:
        assert e["tmoSeason"] == str(e["year"])
        assert e["tmoSource"] and e["tmoAsOf"]
        assert e["tmoVerified"] is True


def test_tmo_carry_over_drops_unverified_old_entries(offline_turib):
    old = {"commodity": "MISIR", "turibFreePrice": 9.99, "asOf": "2026-11-17", "tmoPurchasePrice": 12.0}
    data = turib_data.generate_turib_market_data(previous={"date": "2026-11-18", "tmoComparison": [old]})
    assert "MISIR" not in {e["commodity"] for e in data["tmoComparison"]}
