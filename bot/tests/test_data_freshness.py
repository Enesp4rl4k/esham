"""Tazelik dürüstlüğü: bölüm damgaları, eski veri eşiği, evren birleştirme, takvim üzerine yazmama (ağ yok)."""
import json
from datetime import date, datetime, timedelta, timezone

import pytest

from esham import freshness
from esham.freshness import SECTION_SOURCES, build_section_meta, evaluate_sections, run_data_status
from esham.jobs.publish_stocks import HIDE_ROW_DAYS, STALE_ROW_HOURS, merge_universe_rows
from esham.publishing import turib_data

NOW = datetime(2026, 11, 24, 12, 0, tzinfo=timezone.utc)  # Salı


def _w(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj), encoding="utf-8")


# ---- bölüm damgaları ---------------------------------------------------------------------

def test_section_meta_uses_oldest_entry_date_and_marks_stale():
    data = {
        "indices": [{"code": "A", "asOf": "2026-11-20"}, {"code": "B", "asOf": "2026-11-10", "stale": True}],
        "spotCommodities": [],
        "storageBacktest": {"asOf": "2026-11-21", "productGroup": "X"},
        "petrolTanker": {"date": "2026-11-21", "straits": [{"strait": "Bosporus", "asOf": "2026-11-08", "weekEnd": "2026-11-08"}]},
    }
    meta = build_section_meta(data, "2026-11-21T10:00:00+03:00")
    assert meta["indices"]["asOf"] == "2026-11-10" and meta["indices"]["stale"] and meta["indices"]["status"] == "stale"
    assert meta["spotCommodities"]["status"] == "missing" and meta["spotCommodities"]["asOf"] is None
    assert meta["storageBacktest"]["status"] == "fresh"
    # Boğaz tarihi Brent bölümünü eskitmez: ayrı bölüm
    assert meta["petrolTanker"]["asOf"] == "2026-11-21"
    assert meta["straits"]["asOf"] == "2026-11-08"
    assert set(meta) == set(SECTION_SOURCES)
    assert all(m["source"] and m["sourceUrl"].startswith("https://") for m in meta.values())


def test_section_without_date_is_missing_not_fresh():
    meta = build_section_meta({"agriBist": {"xgidaPrice": "1,0", "companies": []}}, "x")
    assert meta["agriBist"]["status"] == "missing"


# ---- eski veri eşiği ---------------------------------------------------------------------

def test_carried_value_older_than_threshold_is_dropped(monkeypatch):
    monkeypatch.setattr(turib_data, "_today", lambda: date(2026, 11, 24))
    fresh = {"code": "T", "asOf": "2026-11-20"}
    old = {"code": "T", "asOf": "2026-10-01"}
    assert turib_data._carry_over(["T"], {"date": "2026-11-20", "indices": [fresh]}, "indices", "code", ())[0]["stale"] is True
    assert turib_data._carry_over(["T"], {"date": "2026-10-01", "indices": [old]}, "indices", "code", ()) == []
    data = {"agriBist": {}}
    turib_data._carry_section(data, {"date": "2026-10-01", "agriBist": {"date": "2026-10-01", "companies": [1]}}, "agriBist")
    assert data["agriBist"] == {}  # 14 günden eski bölüm tazeymiş gibi taşınmaz
    assert not turib_data._too_old("2026-10-01", None)  # TMO gibi yıllık duyurular için sınırsız


# ---- evren birleştirme (evren sessizce küçülmez) ------------------------------------------

def test_failed_ticker_keeps_last_good_row_with_its_own_date_then_goes_stale_then_hidden():
    prev_ts = (NOW - timedelta(hours=2)).isoformat()
    old_ts = (NOW - timedelta(hours=STALE_ROW_HOURS + 5)).isoformat()
    ancient = (NOW - timedelta(days=HIDE_ROW_DAYS + 1)).isoformat()
    prev = {
        "OK": {"ticker": "OK", "pe": 1.0, "updated_at": prev_ts},
        "OLD": {"ticker": "OLD", "pe": 2.0, "updated_at": old_ts},
        "GONE": {"ticker": "GONE", "pe": 3.0, "updated_at": ancient},
        "NODATE": {"ticker": "NODATE", "pe": 4.0},  # satırda tarih yok -> dosya damgası
        "NEW": {"ticker": "NEW", "pe": 5.0, "updated_at": prev_ts},
    }
    new = {"NEW": {"ticker": "NEW", "pe": 6.0, "updated_at": NOW.isoformat()}}
    universe = ["OK", "OLD", "GONE", "NODATE", "NEW", "NEVER"]
    merged, failed, hidden = merge_universe_rows(prev, new, universe, prev_ts, NOW)
    assert merged["NEW"]["pe"] == 6.0
    assert merged["OK"]["updated_at"] == prev_ts and "stale" not in merged["OK"]
    assert merged["OLD"]["stale"] is True and merged["OLD"]["updated_at"] == old_ts
    assert merged["NODATE"]["updated_at"] == prev_ts
    assert "GONE" not in merged and hidden == ["GONE"]
    assert sorted(failed) == ["GONE", "NEVER", "NODATE", "OK", "OLD"]  # bu turda alınamayan hepsi raporlanır (GONE: gizlenen de)


def test_partial_run_does_not_report_untouched_tickers_as_failed():
    ts = NOW.isoformat()
    prev = {"A": {"ticker": "A", "updated_at": ts}, "B": {"ticker": "B", "updated_at": ts}}
    merged, failed, _ = merge_universe_rows(prev, {"A": {"ticker": "A", "updated_at": ts}}, ["A"], ts, NOW, partial=True)
    assert set(merged) == {"A", "B"} and failed == []


# ---- data-status.json ---------------------------------------------------------------------

@pytest.fixture
def datadir(tmp_path):
    d, r = tmp_path / "data", tmp_path / "reports"
    r.mkdir()
    _w(r / "2026-11-24-x.json", {"publishedAt": (NOW - timedelta(hours=3)).isoformat()})
    _w(d / "market-ticker.json", {"updatedAt": (NOW - timedelta(hours=1)).isoformat()})
    _w(d / "economic-calendar.json", {"updated_at": (NOW - timedelta(hours=90)).isoformat()})
    _w(d / "universe.json", {"updated_at": (NOW - timedelta(hours=5)).isoformat(),
                             "stocks": [{"ticker": "A", "updated_at": (NOW - timedelta(days=9)).isoformat()}]})
    _w(d / "stocks" / "A.json", {"data_source": "KAP"})
    _w(d / "stocks" / "B.json", {"data_source": "Yahoo"})
    _w(d / "turib-market.json", {"updatedAt": NOW.isoformat(), "date": "2026-11-24",
                                 "indices": [{"code": "TRBHUB", "asOf": "2026-11-23"}], "agriBist": {}})
    return d, r


def test_evaluate_sections_marks_stale_and_missing_and_reports_kap_coverage(datadir):
    d, r = datadir
    by = {s.id: s for s in evaluate_sections(NOW, d, r)}
    assert by["reports"].status == "fresh"
    assert by["market_ticker"].status == "fresh"
    assert by["economic_calendar"].status == "stale"  # 90 saat > 26 saat (Salı)
    assert by["stocks"].status == "stale" and "1 hissenin satırı eski" in by["stocks"].detail
    assert by["kap_coverage"].detail.startswith("1/2 hissenin finansalı KAP kaynaklı")
    assert by["turib:indices"].status == "fresh" and by["turib:indices"].as_of == "2026-11-23"
    assert by["turib:agriBist"].status == "missing" and "gösterilmiyor" in by["turib:agriBist"].detail
    assert "funds" not in by  # fon verisi hiç üretilmediyse alarm yok


def test_run_data_status_writes_manifest_and_strict_exit_code(datadir, tmp_path, capsys):
    d, r = datadir
    out = tmp_path / "data-status.json"
    assert run_data_status(strict=False, now=NOW, data_dir=d, reports_dir=r, status_path=out) == 0
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert doc["generated_at"] and any(s["id"] == "economic_calendar" and s["status"] == "stale" for s in doc["sections"])
    assert "::warning title=Veri eski" in capsys.readouterr().out
    assert run_data_status(strict=True, now=NOW, data_dir=d, reports_dir=r, status_path=out) == 1


def test_economic_calendar_not_overwritten_with_empty_events(monkeypatch, tmp_path):
    """Kaynak hatası 'bugün olay yok' gibi taze damgayla yazılmaz: eski dosya kendi tarihiyle kalır."""
    from esham.publishing import ticker_data
    from esham.sources import calendar as cal

    path = tmp_path / "market-ticker.json"
    monkeypatch.setattr(ticker_data, "TICKER_JSON", path)
    cal_path = tmp_path / "economic-calendar.json"
    cal_path.write_text(json.dumps({"updated_at": "2026-11-20T01:00:00+03:00", "events": [{"event": "x"}]}), encoding="utf-8")

    class _Bist:
        def market_summary(self):
            return type("M", (), {"index": "XU100", "price": "1", "change": "+1%"})()

    monkeypatch.setattr(ticker_data, "BistSource", _Bist)
    monkeypatch.setattr(ticker_data, "GlobalMacroSource", lambda: type("G", (), {"snapshot": lambda self: type("S", (), {"tickers": []})()})())
    monkeypatch.setattr(ticker_data, "WATCHLIST", [])
    monkeypatch.setattr(cal.EconomicCalendarSource, "daily_events", lambda self, min_importance=0: [])
    import esham.sources.turib as turib_mod

    class _T:
        def snapshot(self):
            raise RuntimeError("down")

    monkeypatch.setattr(turib_mod, "TuribSource", _T)
    assert ticker_data.update_ticker_data() is True
    assert json.loads(cal_path.read_text(encoding="utf-8"))["updated_at"] == "2026-11-20T01:00:00+03:00"


def test_one_stale_threshold_shared_by_rows_status_health_and_web():
    """Satır bayatlığı, data-status, health ve web aynı eşiği kullanır (tek sabit)."""
    import re
    from pathlib import Path

    from esham.freshness import STOCK_ROW_STALE_HOURS
    from esham.jobs import health, publish_stocks

    assert publish_stocks.STALE_ROW_HOURS == STOCK_ROW_STALE_HOURS == 120
    assert health.STOCK_ROW_STALE_HOURS == STOCK_ROW_STALE_HOURS
    ts = (Path(__file__).resolve().parents[2] / "web" / "src" / "lib" / "programmatic.ts").read_text(encoding="utf-8")
    assert int(re.search(r"STALE_ROW_HOURS = (\d+);", ts).group(1)) == STOCK_ROW_STALE_HOURS


def test_fund_rows_carry_own_timestamp_and_blocked_rows_are_marked_stale(monkeypatch, tmp_path):
    from esham.jobs import publish_funds

    monkeypatch.setattr(publish_funds, "DATA_DIR", tmp_path)
    (tmp_path / "funds").mkdir()
    (tmp_path / "funds" / "OLD.json").write_text("{}", encoding="utf-8")
    (tmp_path / "universe-funds.json").write_text(json.dumps({"funds": [{"code": "OLD", "aum": 1, "updated_at": "2026-11-01T00:00:00+03:00"}]}), encoding="utf-8")
    fund = {"code": "NEW", "name": "n", "category": "c", "risk": 1, "price": 1.0, "daily": 0.0, "aum": 5, "investors": 1, "fee": None,
            "as_of": "2026-11-20", "returns": {}, "real_1y": None, "metrics": {"volatility": None, "max_drawdown": None, "sharpe": None},
            "category_rank": None, "updated_at": "2026-11-23T10:00:00+03:00"}
    publish_funds._merge_universe([fund], {}, partial=False, chosen={"OLD", "NEW"})
    rows = {r["code"]: r for r in json.loads((tmp_path / "universe-funds.json").read_text(encoding="utf-8"))["funds"]}
    assert rows["NEW"]["updated_at"] == "2026-11-23T10:00:00+03:00" and not rows["NEW"].get("stale")
    assert rows["OLD"]["stale"] is True and rows["OLD"]["updated_at"] == "2026-11-01T00:00:00+03:00"
