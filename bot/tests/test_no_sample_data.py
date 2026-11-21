"""Üretimde örnek/sahte veri yayınlanmaz; yalnızca ESHAM_ALLOW_SAMPLE_DATA=1 ile (ağ yok)."""
import pytest
import requests

from esham import pipeline
from esham.config import sample_data_allowed, settings
from esham.publishing import turib_data
from esham.sources import global_macro, peer, viop
from esham.sources.calendar import EconomicCalendarSource
from esham.sources.kap import KapSource
from esham.sources.sector import SectorSource


def _down(*_a, **_k):
    raise requests.ConnectionError("upstream down")


@pytest.fixture(autouse=True)
def _flag_off(monkeypatch):
    monkeypatch.delenv("ESHAM_ALLOW_SAMPLE_DATA", raising=False)


def test_flag_default_off_and_parsing(monkeypatch):
    assert sample_data_allowed() is False
    monkeypatch.setenv("ESHAM_ALLOW_SAMPLE_DATA", "1")
    assert sample_data_allowed() is True
    monkeypatch.setenv("ESHAM_ALLOW_SAMPLE_DATA", "0")
    assert sample_data_allowed() is False


# ---- bayrak KAPALI ---------------------------------------------------------

def test_viop_quote_none_when_down(monkeypatch):
    monkeypatch.setattr(viop, "retry_post", _down)
    assert viop.ViopSource().market_quote() is None


def test_global_macro_empty_when_down(monkeypatch):
    monkeypatch.setattr(global_macro, "retry_get", _down)
    assert global_macro.GlobalMacroSource().snapshot().tickers == []


def test_peer_empty_when_down(monkeypatch):
    monkeypatch.setattr(peer.PeerSource, "_fetch", lambda *_a, **_k: None)
    key = next(iter(peer.PEER_GROUPS))
    snap = peer.PeerSource().snapshot(key)
    assert snap.peers == [] and snap.sample is False


def test_already_clean_sources_empty_when_down(monkeypatch):
    from esham import kap_http
    from esham.sources import calendar, kap, sector

    monkeypatch.setattr(calendar, "retry_get", _down)
    monkeypatch.setattr(sector, "retry_get", _down)
    monkeypatch.setattr(kap, "kap_post", _down)
    assert EconomicCalendarSource().daily_events() == []
    assert SectorSource().snapshot() == []
    assert KapSource().latest_disclosures() == []
    assert kap_http  # import kullanımı


def test_reports_abort_and_write_nothing(monkeypatch):
    monkeypatch.setattr(viop, "retry_post", _down)
    monkeypatch.setattr(viop.requests, "get", _down)
    monkeypatch.setattr(global_macro, "retry_get", _down)
    monkeypatch.setattr(peer.PeerSource, "_fetch", lambda *_a, **_k: None)

    def _boom(*_a, **_k):
        raise AssertionError("yayın/kart üretilmemeli")

    monkeypatch.setattr(pipeline, "_render_card", _boom)
    before = sorted(p.name for p in settings.content_dir.glob("*")) if settings.content_dir.exists() else []

    assert pipeline.run_global_report(publish_social=False) is None
    assert pipeline.run_peer_report(next(iter(peer.PEER_GROUPS)), publish_social=False) is None
    assert pipeline.run_viop_report(publish=False, publish_social=False) is None

    after = sorted(p.name for p in settings.content_dir.glob("*")) if settings.content_dir.exists() else []
    assert before == after


def test_turib_does_not_hardcode_free_market_prices():
    import inspect
    import re

    src = inspect.getsource(turib_data.generate_turib_market_data)
    # TMO kıyası serbest piyasa fiyatını canlı TÜRİB'den almalı; elle sabit fiyat yok.
    assert not re.search(r'\("(MISIR|ARPA)",\s*[\d.]+\)', src)


# ---- bayrak AÇIK (yalnızca yerel geliştirme) ------------------------------

def test_sample_paths_work_when_opted_in(monkeypatch):
    monkeypatch.setenv("ESHAM_ALLOW_SAMPLE_DATA", "1")
    monkeypatch.setattr(viop, "retry_post", _down)
    monkeypatch.setattr(global_macro, "retry_get", _down)
    monkeypatch.setattr(peer.PeerSource, "_fetch", lambda *_a, **_k: None)

    q = viop.ViopSource().market_quote()
    assert q is not None and q.index_symbol == "XU030"
    assert len(global_macro.GlobalMacroSource().snapshot().tickers) > 0
    snap = peer.PeerSource().snapshot(next(iter(peer.PEER_GROUPS)))
    assert snap.sample is True and snap.peers
