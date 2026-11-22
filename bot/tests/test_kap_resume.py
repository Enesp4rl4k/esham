"""KAP kapsamı: devam edilebilir kuyruk (önbellek + ilerleme sırası), negatif önbellek, aracı kurum şablonu.

Fixture'lar GERÇEK KAP sayfalarından kaydedildi (23 Kas 2026): ISMEN 2026/9 (genel şablon, yalnızca ayrıştırıcının
kullandığı satırlar kırpıldı) ve DOCO (yabancı ihraççı: tablo yok, 'Finansal Rapor' ama ayrıştırılamaz)."""
from pathlib import Path

import pytest

from esham import kap_http
from esham.jobs import publish_kap
from esham.sources import kap_financials as kf_mod
from esham.sources.kap_financials import KapFinancials, parse_report, report_snapshot

FIX = Path(__file__).parent / "fixtures"
ISMEN = (FIX / "kap_ismen_2026_q3_trimmed.html").read_bytes()
DOCO = (FIX / "kap_doco_no_tables.html").read_bytes()


class _Resp:
    def __init__(self, content: bytes):
        self.content = content
        self.status_code = 200

    def raise_for_status(self):
        pass


@pytest.fixture
def kap(tmp_path, monkeypatch):
    monkeypatch.setattr(kf_mod, "CACHE_DIR", tmp_path / "cache")
    calls: list[str] = []
    pages = {"1": ISMEN, "2": DOCO}

    def fake_get(url, **kw):
        calls.append(url)
        return _Resp(pages[url.rsplit("/", 1)[1]])

    monkeypatch.setattr(kf_mod, "kap_get", fake_get)
    return KapFinancials(), calls


def test_recorded_broker_report_parses_with_general_template():
    snap = report_snapshot(parse_report(ISMEN.decode("utf-8")))
    assert snap is not None
    assert (snap["end"], snap["months"], snap["currency"], snap["consolidated"]) == ("2026-09-30", 9, "TRY", True)
    assert snap["ytd"]["net_income"] > 0 and snap["balance"]["equity"] > 0 and snap["balance"]["total_assets"] > 0


def test_recorded_foreign_filer_report_has_no_statements():
    assert report_snapshot(parse_report(DOCO.decode("utf-8"))) is None


def test_unparsable_report_is_downloaded_once(kap):
    kf, calls = kap
    assert kf.snapshot("2") is None
    assert kf.snapshot("2") is None
    assert calls == ["https://www.kap.org.tr/tr/Bildirim/2"]  # ikinci çağrı önbellekten (istek bütçesi harcanmaz)
    assert kf.is_cached("2")


def test_negative_cache_expires_with_new_parser_version(kap, monkeypatch):
    kf, calls = kap
    kf.snapshot("2")
    monkeypatch.setattr(kf_mod, "PARSER_VERSION", kf_mod.PARSER_VERSION + 1)
    assert not kf.is_cached("2")  # ayrıştırıcı geliştirildi → yeniden denenir
    kf.snapshot("2")
    assert len(calls) == 2


def test_successful_snapshot_cached_and_download_failure_not_cached(kap, monkeypatch):
    kf, calls = kap
    first = kf.snapshot("1")
    assert first and kf.snapshot("1") == first and len(calls) == 1

    def boom(url, **kw):
        raise kap_http.KapUnavailable("429")

    monkeypatch.setattr(kf_mod, "kap_get", boom)
    with pytest.raises(kap_http.KapUnavailable):
        kf.snapshot("3")
    assert not kf.is_cached("3")  # indirilemeyen rapor 'ayrıştırılamaz' diye işaretlenmez


def test_order_by_progress_puts_cached_and_nearly_done_first(kap):
    kf, _ = kap
    kf.snapshot("1")  # önbellekli
    by_t = {
        "AAA": [{"disclosureIndex": 11}, {"disclosureIndex": 12}],  # 2 eksik
        "BBB": [{"disclosureIndex": 1}],  # tamamen önbellekte
        "CCC": [{"disclosureIndex": 1}, {"disclosureIndex": 13}],  # 1 eksik
        "DDD": [{"disclosureIndex": 14}, {"disclosureIndex": 15}],  # 2 eksik
    }
    order = [(t, miss) for t, _rs, miss in publish_kap.order_by_progress(kf, by_t)]
    assert order == [("BBB", 0), ("CCC", 1), ("AAA", 2), ("DDD", 2)]


def test_kap_universe_includes_brokers_but_not_banks_or_insurers():
    tickers = {u["ticker"] for u in publish_kap.kap_universe()}
    assert {"ISMEN", "GLBMD", "THYAO"} <= tickers
    assert not tickers & {"AKBNK", "GARAN", "AKGRT", "ANHYT", "AGESA"}  # banks_role_/insurance_role_ taksonomisi desteklenmiyor
