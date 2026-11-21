"""Uydurma (kod içine gömülü) piyasa sayısı yayınlanmaz: VİOP basis, makro barometre, kur radarı,
tanker/Brent, sabit kurlu sözleşme tutarı, TÜRİB bölüm taşıma (ağ yok)."""
import ast
import inspect
import json

import pytest
import requests

from esham.publishing import turib_data
from esham.sources import bist_quant, devaluation_radar, macro_radar, tanker_freight, viop
from esham.sources.devaluation_radar import DevaluationRadarAnalyzer
from esham.sources.macro_radar import MacroRadarAnalyzer
from esham.sources.viop import ViopQuote, ViopSource

FABRICATED = (11840.5, 12180.0, 35.82, 34.3, 32.7, 339.5, 254.0, 158.4)


class _Src:
    def __init__(self, quote):
        self._q = quote

    def market_quote(self):
        return self._q


def _all_numbers(obj):
    if isinstance(obj, dict):
        for v in obj.values():
            yield from _all_numbers(v)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            yield from _all_numbers(v)
    elif isinstance(obj, (int, float)) and not isinstance(obj, bool):
        yield obj


# ---- get_viop_basis: gerçek upstream olmadan çıktı üretilemez ------------------------------

def test_viop_basis_none_without_quote():
    assert MacroRadarAnalyzer(_Src(None)).get_viop_basis() is None


def test_viop_basis_none_without_futures_row():
    q = ViopSource()._parse_quote({"data": [{"s": "BIST:XU030", "d": ["XU030", 16000.0, 1.0, 1.0]}]})
    assert q is not None
    assert not q.has_futures
    assert MacroRadarAnalyzer(_Src(q)).get_viop_basis() is None


def test_viop_basis_none_when_upstream_request_fails(monkeypatch):
    def boom(*a, **k):
        raise requests.ConnectionError("down")

    monkeypatch.delenv("ESHAM_ALLOW_SAMPLE_DATA", raising=False)
    monkeypatch.setattr(viop, "retry_post", boom)
    assert MacroRadarAnalyzer().get_viop_basis() is None


def test_viop_basis_values_come_only_from_the_quote():
    payload = {"data": [
        {"s": "BIST:XU030", "d": ["XU030", 15000.0, 0.5, 1.0]},
        {"s": "BIST:XU030D", "d": ["XU030D", 15300.0, 0.4, 1.0]},
    ]}
    res = MacroRadarAnalyzer(_Src(ViopSource()._parse_quote(payload))).get_viop_basis()
    assert res is not None
    assert (res.spot_xu030, res.futures_f_xu030_near, res.basis_points, res.basis_pct) == (15000.0, 15300.0, 300.0, 2.0)
    assert not set(FABRICATED) & set(_all_numbers(res.to_dict()))
    assert res.to_dict()["veri_tarihi"]


def test_viop_basis_export_writes_nothing_without_data(tmp_path):
    MacroRadarAnalyzer(_Src(None)).export_data(tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_viop_basis_export_with_real_quote(tmp_path):
    q = ViopQuote("XU030", "15.000,00", "+0,5%", "XU030D", "15.300,00", "+0,4%", None, 15000.0, 15300.0)
    MacroRadarAnalyzer(_Src(q)).export_data(tmp_path)
    out = json.loads((tmp_path / "viop-basis.json").read_text(encoding="utf-8"))
    assert out["spot_xu030"] == 15000.0
    assert out["basis_puan"] == 300.0


# ---- makro barometre / devalüasyon radarı: kaynak yok -> None ---------------------------------

def test_macro_barometer_has_no_source():
    assert MacroRadarAnalyzer(_Src(None)).get_macro_barometer() is None


def test_devaluation_radar_never_produces_output_without_upstream():
    assert DevaluationRadarAnalyzer().analyze() is None
    assert not hasattr(devaluation_radar, "export_devaluation_radar_json")


@pytest.mark.parametrize("module", [macro_radar, devaluation_radar])
def test_radar_modules_contain_no_market_literals(module):
    """Bu modüllerde piyasa sayısı gibi float sabiti kalmamalı (yalnızca 100.0 / 365.0 gibi birim sabitleri)."""
    tree = ast.parse(inspect.getsource(module))
    floats = {n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, float)}
    assert floats <= {100.0, 365.0}, floats
    assert not floats & set(FABRICATED)


# ---- MCP: bist_viop_durum gerçek niteliklere erişir ------------------------------------------

def test_mcp_viop_durum_uses_real_attributes(monkeypatch):
    from esham.mcp import server

    q = ViopQuote("XU030", "15.000,00", "+0,5%", "XU030D", "15.300,00", "+0,4%", None, 15000.0, 15300.0)

    class _V:
        def market_quote(self):
            return q

        def margin_snapshot(self):
            return viop.ViopMarginSnapshot("2026-11-20", 10, 1.0, 2.0, 50.0)

    monkeypatch.setattr(server, "ViopSource", _V)
    out = server.bist_viop_durum()
    assert out["endeks_fiyat"] == "15.000,00"
    assert out["vadeli_fiyat"] == "15.300,00"
    assert out["takasbank_teminat"]["teminat_tamamlama_orani_yuzde"] == 50.0

    class _None(_V):
        def market_quote(self):
            return None

        def margin_snapshot(self):
            return None

    monkeypatch.setattr(server, "ViopSource", _None)
    out = server.bist_viop_durum()
    assert out["endeks_fiyat"] is None
    assert out["vadeli_fiyat"] is None
    assert out["takasbank_teminat"] is None


# ---- tanker / Brent: yalnızca gerçek Brent --------------------------------------------------

def test_tanker_snapshot_none_without_live_brent(monkeypatch):
    from esham.sources import global_macro

    monkeypatch.setattr(global_macro.GlobalMacroSource, "snapshot",
                        lambda self: global_macro.GlobalMacroSnapshot(tickers=[]))
    assert tanker_freight.TankerFreightSource().fetch_snapshot() is None


def test_tanker_snapshot_only_real_brent(monkeypatch):
    from esham.sources import global_macro

    snap = global_macro.GlobalMacroSnapshot(tickers=[global_macro.MacroTicker("BRENT", 91.25, -1.5, "$")])
    monkeypatch.setattr(global_macro.GlobalMacroSource, "snapshot", lambda self: snap)
    d = tanker_freight.TankerFreightSource().fetch_snapshot().to_dict()
    assert d["oilBenchmarks"]["brent"]["price"] == 91.25
    assert set(d["oilBenchmarks"]) == {"brent"}
    assert "freightIndices" not in d
    assert "rates" not in d


# ---- sabit kurla TL çevrimi yok -------------------------------------------------------------

def test_contract_amount_needs_live_fx_for_foreign_currency(monkeypatch):
    monkeypatch.setattr(bist_quant, "live_fx_rate", lambda symbol: None)
    assert bist_quant.extract_contract_amount("10 milyon USD bedelli anlaşma") is None
    assert bist_quant.extract_contract_amount("5 milyon euro sipariş") is None
    assert bist_quant.extract_contract_amount("750 milyon TL ihale") == 750_000_000.0
    monkeypatch.setattr(bist_quant, "live_fx_rate", lambda symbol: 50.0 if symbol == "TRY=X" else 60.0)
    assert bist_quant.extract_contract_amount("10 milyon USD bedelli anlaşma") == 500_000_000.0
    assert bist_quant.extract_contract_amount("1 milyon euro sipariş") == 60_000_000.0


# ---- TÜRİB: bölüm düzeyinde son iyi değer (boş yayın yok) ----------------------------------

class _Boom:
    def __init__(self, *a, **k):
        raise RuntimeError("source down")


@pytest.fixture
def offline(monkeypatch):
    for n in ("TuribSource", "MeatFeedIndexAnalyzer", "RealReturnsCalculator", "TmoSource",
              "StorageStrategyBacktester", "RegionalArbitrageScanner", "AgriBistAnalyzer"):
        monkeypatch.setattr(turib_data, n, _Boom)
    monkeypatch.setattr(tanker_freight, "TankerFreightSource", _Boom)


def test_turib_section_failure_keeps_last_good_with_original_date(offline):
    prev = {
        "date": "2026-11-18",
        "indices": [{"code": "TRBHUB", "value": 7000.0, "asOf": "2026-11-17"}, {"code": "TRBBGD", "value": 8000.0}],
        "agriBist": {"date": "2026-11-16", "xgidaPrice": "1,0", "companies": []},
    }
    data = turib_data.generate_turib_market_data(previous=prev)
    by = {e["code"]: e for e in data["indices"]}
    assert by["TRBHUB"]["asOf"] == "2026-11-17"
    assert by["TRBHUB"]["stale"] is True
    assert by["TRBBGD"]["asOf"] == "2026-11-18"
    assert by["TRBBGD"]["stale"] is True
    assert data["agriBist"]["asOf"] == "2026-11-16"
    assert data["agriBist"]["stale"] is True


def test_turib_section_without_previous_stays_empty(offline):
    data = turib_data.generate_turib_market_data(previous=None)
    assert data["indices"] == []
    assert data["meatFeed"] == {}
    assert data["petrolTanker"] == {}
    data = turib_data.generate_turib_market_data(previous={"indices": [{"code": "X"}]})  # tarihsiz
    assert data["indices"] == []
