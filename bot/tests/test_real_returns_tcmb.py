"""TCMB döviz kuru kaynağı: kayıtlı gerçek bülten fixture'ı (ağ yok) ve 'kur yoksa uydurma yok' kuralı."""
import ast
import inspect
from pathlib import Path

import pytest

from esham.sources import real_returns
from esham.sources.real_returns import (
    FxUnavailable,
    RealReturnsCalculator,
    TcmbFxSource,
    TcmbRate,
    compute_report,
    parse_tcmb_xml,
)

FIX = Path(__file__).parent / "fixtures"


def test_parse_recorded_tcmb_bulletin_2026_11_20():
    rate = parse_tcmb_xml((FIX / "tcmb_20261120.xml").read_bytes())
    assert rate is not None
    assert (rate.date, rate.usd) == ("2026-11-20", 50.4028)
    assert rate.eur > rate.usd  # EUR/TRY > USD/TRY (fixture'dan okunur)


def test_parse_recorded_tcmb_bulletin_2022_01_03():
    rate = parse_tcmb_xml((FIX / "tcmb_20220103.xml").read_text(encoding="utf-8"))
    assert rate is not None
    assert rate.date == "2022-01-03"
    assert rate.usd == 13.4221


@pytest.mark.parametrize("bad", [b"", b"<html>404</html>", b"<Tarih_Date Date='bozuk'></Tarih_Date>",
                                 b"<Tarih_Date Date='11/20/2026'><Currency CurrencyCode='USD'><Unit>1</Unit>"
                                 b"<ForexBuying></ForexBuying></Currency></Tarih_Date>"])
def test_parse_rejects_missing_or_broken_bulletins(bad):
    assert parse_tcmb_xml(bad) is None


class _Resp:
    def __init__(self, status, content=b""):
        self.status_code = status
        self.content = content


def test_rate_walks_back_over_weekend_and_reports_bulletin_date(monkeypatch):
    xml = (FIX / "tcmb_20261120.xml").read_bytes()  # Cuma bülteni
    seen = []

    def fake_get(url, **kw):
        seen.append(url)
        return _Resp(200, xml) if url.endswith("20112026.xml") else _Resp(404)

    monkeypatch.setattr(real_returns, "retry_get", fake_get)
    rate = TcmbFxSource().rate_on_or_before("2026-11-22")  # Pazar
    assert rate.date == "2026-11-20"
    assert len(seen) == 3  # 22, 21, 20


def test_rate_never_invented_when_bulletins_are_missing(monkeypatch):
    monkeypatch.setattr(real_returns, "retry_get", lambda url, **kw: _Resp(404))
    with pytest.raises(FxUnavailable):
        TcmbFxSource().rate_on_or_before("2026-11-20")


def test_compute_report_uses_only_given_prices_and_rates():
    seri = [{"date": "2025-11-20", "avg": 10.0, "close": 9.0}, {"date": "2026-11-20", "avg": 15.0, "close": 14.0}]
    r0, r1 = TcmbRate("2025-11-20", 40.0, 50.0), TcmbRate("2026-11-20", 50.0, 60.0)
    rep = compute_report("BUĞDAY EKMEKLİK", seri, r0, r1, "2026-11-21T00:00:00+00:00")
    assert rep.nominal_tl_getiri_pct == 50.0
    assert rep.usd_getiri_pct == 20.0  # 10/40=0.25 -> 15/50=0.30
    assert rep.eur_getiri_pct == 25.0  # 10/50=0.20 -> 15/60=0.25
    assert (rep.kur_tarihi_baslangic, rep.kur_tarihi_bitis) == ("2025-11-20", "2026-11-20")
    assert "tcmb.gov.tr" in rep.kaynak and rep.cekilis_zamani


def test_calculator_fails_loudly_without_fx(monkeypatch):
    class _Turib:
        def fetch_product_series(self, g):
            return [{"date": "2026-01-02", "avg": 1.0, "close": 1.0}, {"date": "2026-11-20", "avg": 2.0, "close": 2.0}]

    monkeypatch.setattr(real_returns, "retry_get", lambda url, **kw: _Resp(404))
    with pytest.raises(FxUnavailable):
        RealReturnsCalculator(turib_source=_Turib()).calculate("BUĞDAY EKMEKLİK")


def test_no_hardcoded_fx_or_cpi_table_left():
    tree = ast.parse(inspect.getsource(real_returns))
    floats = {n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, float)}
    assert floats == set()  # kur/TÜFE katsayısı kodda yok
    assert not hasattr(real_returns, "TARIHSEL_KUR_VE_ENFLASYON")
    assert not hasattr(real_returns, "get_anchor")
