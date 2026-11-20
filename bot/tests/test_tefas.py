"""TEFAS kaynağı ve fon yayın işi: saf fonksiyonlar (ağ yok)."""
from datetime import date, timedelta

import pytest
import requests

from esham.jobs import publish_funds as P
from esham.sources import tefas as T


def series(n=400, start=1.0, daily=0.001, end=date(2026, 11, 20)):
    out, v = [], start
    for i in range(n):
        d = (end - timedelta(days=n - 1 - i)).isoformat()
        out.append((d, v))
        v *= 1 + daily
    return out


def test_normalize_return_row():
    r = T.normalize_return_row({"fonKodu": "aft", "fonUnvan": " X FONU ", "fonTurAciklama": "Hisse Senedi Şemsiye Fonu",
                                "tefasDurum": True, "getiri1a": -11.3, "getiri1y": "8,68", "getiri3y": None, "riskDegeri": "6"})
    assert r["code"] == "AFT" and r["name"] == "X FONU" and r["category"] == "Hisse Senedi"
    assert r["returns"]["1y"] == 8.68 and r["returns"]["3y"] is None and r["risk"] == 6


def test_parse_prices_drops_zero_and_dups():
    rows = [{"tarih": "2026-01-02", "fiyat": 1.1}, {"tarih": "2026-01-01", "fiyat": 0}, {"tarih": "2026-01-02", "fiyat": 1.2},
            {"tarih": "2026-01-03", "fiyat": "1,3"}, {"tarih": None, "fiyat": 5}]
    assert T.parse_prices(rows) == [("2026-01-02", 1.2), ("2026-01-03", 1.3)]


def test_period_return_and_insufficient_history():
    s = series(400, 1.0, 0.001)
    assert T.period_return(s, 365) == pytest.approx(((1.001) ** 365 - 1) * 100, rel=1e-3)
    assert T.period_return(series(20), 365) is None


def test_risk_metrics_constant_growth_has_low_vol_and_no_drawdown():
    m = T.risk_metrics(series(400, 1.0, 0.001), rf_annual_pct=10)
    assert m["max_drawdown"] == 0.0 and m["volatility"] == pytest.approx(0.0, abs=1e-6)
    assert m["sharpe"] is None  # oynaklık 0 → Sharpe tanımsız


def test_risk_metrics_drawdown_and_sharpe():
    s = series(100, 1.0, 0.0)
    prices = [(d, v * (1.5 if i < 50 else 1.0) * (1 + (0.01 if i % 2 else -0.01))) for i, (d, v) in enumerate(s)]
    m = T.risk_metrics(prices, rf_annual_pct=0)
    assert m["max_drawdown"] < -30 and m["volatility"] > 10 and m["sharpe"] is not None


def test_risk_metrics_short_series_is_empty():
    assert T.risk_metrics(series(10)) == {"volatility": None, "max_drawdown": None, "sharpe": None}


def test_real_return():
    assert T.real_return(40.54, 29.7659) == pytest.approx(8.3027, abs=1e-3)
    assert T.real_return(None, 10) is None and T.real_return(10, None) is None


def test_rank_in_categories():
    f = lambda c, cat, v: {"code": c, "category": cat, "returns": {"1y": v}}
    r = T.rank_in_categories([f("A", "X", 10), f("B", "X", 30), f("C", "X", 20), f("D", "Y", 5), f("E", "Y", None)])
    assert r["B"] == (1, 3) and r["A"] == (3, 3) and r["D"] == (1, 1) and "E" not in r


def test_thin_series_keeps_recent_fully():
    s = series(1000)
    out = T.thin_series(s, recent_days=366, step=5)
    assert out[-1][0] == s[-1][0]
    recent = [p for p in out if p[0] >= (date(2026, 11, 20) - timedelta(days=366)).isoformat()]
    assert len(recent) == 367 and len(out) < 700


def test_select_top_by_aum_and_limit():
    rows = [{"code": c} for c in "ABCD"]
    sizes = {"A": {"aum": 5}, "B": {"aum": 50}, "C": {"aum": None}, "D": {"aum": 20}}
    assert [r["code"] for r in P.select_top(rows, sizes, 2)] == ["B", "D"]
    assert [r["code"] for r in P.select_top(rows, sizes, 99)] == ["B", "D", "A"]  # büyüklüğü bilinmeyen elenir


def test_build_fund_fills_missing_returns_from_prices_and_summary():
    base = {"code": "ZZZ", "name": "Z", "category": "Hisse Senedi", "risk": 5,
            "returns": {"1m": None, "3m": None, "6m": None, "ytd": 3.0, "1y": None, "3y": None, "5y": None}}
    f = P.build_fund(base, series(400, 1.0, 0.001), {"price": 1.5, "investors": 10}, {"aum": 1e9}, 2.0,
                     {"deposit": 40.0, "cpi": 30.0, "usd": 20.0}, (2, 10), 11.0)
    assert f["returns"]["1y"] is not None and f["returns"]["5y"] is None
    assert f["real_1y"] is not None and f["allocation"] is None and f["source"].startswith("TEFAS")
    row = P.summary_row(f)
    assert row["rank"] == 2 and row["rank_of"] == 10 and row["r1y"] == f["returns"]["1y"]


class _Resp:
    def __init__(self, status=200, ctype="application/json", payload=None):
        self.status_code, self.headers, self._p = status, {"content-type": ctype}, payload or {}

    def json(self):
        return self._p


def test_parse_response_blocked_variants():
    with pytest.raises(T.TefasBlocked):
        T._parse_response(_Resp(429))
    with pytest.raises(T.TefasBlocked):
        T._parse_response(_Resp(200, "text/html"))  # "Erişim Engellendi" HTML sayfası
    with pytest.raises(T.TefasBlocked):
        T._parse_response(_Resp(200, payload={"faultCode": "ERR-224", "faultString": "Throttling"}))
    with pytest.raises(T.TefasError):
        T._parse_response(_Resp(200, payload={"errorMessage": "Sistem Hatası!!"}))
    assert T._parse_response(_Resp(200, payload={"resultList": [{"a": 1}]})) == [{"a": 1}]


def test_client_fails_over_to_backup_host(monkeypatch):
    calls = []

    def fake_post(self, url, json=None, timeout=None):
        calls.append(url)
        return _Resp(429) if "primary" in url else _Resp(200, payload={"resultList": [{"ok": 1}]})

    monkeypatch.setattr(requests.Session, "post", fake_post)
    monkeypatch.setattr(T.time, "sleep", lambda s: None)
    c = T.TefasClient(min_interval=0, bases=("https://primary/api", "https://backup/api"))
    assert c.post("x", {}) == [{"ok": 1}]
    assert calls[0].startswith("https://primary") and calls[-1].startswith("https://backup")
