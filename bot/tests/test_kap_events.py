"""KAP kâr payı ve geri alım ayrıştırıcıları, iş akışı ve sayfa korumaları (kayıtlı gerçek bildirimlerle; ağ yok)."""
import json
from datetime import date
from pathlib import Path

import pytest

from esham.jobs import publish_kap_events as job
from esham.sources import kap_events as KE
from esham.sources.kap_events import Unparsable, parse_buyback, parse_dividend

FIX = Path(__file__).parent / "fixtures"


def _b(name: str) -> bytes:
    return (FIX / name).read_bytes()


# ---- kâr payı: gerçek bildirimlerle -------------------------------------------------------

def test_dividend_proposal_aygaz_real_disclosure():
    """AYGAZ 1700009 (18.11.2026, 'Kar Dağıtımı Önerisi'): teklif edilen hak kullanım tarihi, kesinleşen boş."""
    d = parse_dividend(_b("kap_div_aygaz_teklif_1700009.html"), "AYGAZ")
    assert d["status"] == "teklif" and d["decision_date"] == "2026-11-18" and d["currency"] == "TRY"
    (i,) = d["installments"]
    assert (i["gross"], i["net"], i["withholding_pct"]) == (4.65, 3.9525, 15.0)
    assert i["ex_date"] == "2026-12-23" and not i["ex_date_final"]
    assert i["payment_date"] == "2026-12-25" and i["record_date"] == "2026-12-24"


def test_dividend_final_yigit_picks_only_the_traded_share_group():
    """YIGIT 1700660: A grubu 'İşlem Görmüyor', B grubu YIGIT; kesinleşen tarih dolu → 'kesinlesti'."""
    d = parse_dividend(_b("kap_div_yigit_kesinlesen_1700660.html"), "YIGIT")
    assert d["status"] == "kesinlesti" and d["agm_date"] == "2026-07-17"
    (i,) = d["installments"]
    assert "YIGIT" in i["pay_group"] and "Görmüyor" not in i["pay_group"]
    assert i["gross"] == 0.1946589 and i["net"] == 0.16546
    assert i["ex_date"] == "2026-12-15" and i["ex_date_final"] and i["payment_date"] == "2026-12-17"


@pytest.mark.parametrize("name,ticker", [("kap_div_avod_dagitim_yok_1700335.html", "AVOD"), ("kap_div_cante_dagitim_yok_1700270.html", "CANTE")])
def test_dividend_zero_is_reported_as_no_distribution_not_as_a_row(name, ticker):
    d = parse_dividend(_b(name), ticker)
    assert d["status"] == "dagitim_yok" and d["installments"] == []


def test_dividend_wrong_ticker_is_skipped_with_reason():
    with pytest.raises(Unparsable, match="eşleşmedi"):
        parse_dividend(_b("kap_div_aygaz_teklif_1700009.html"), "THYAO")


def test_dividend_net_inconsistent_with_gross_and_withholding_is_rejected():
    html = _b("kap_div_aygaz_teklif_1700009.html").decode("utf-8").replace("3,9525000", "3,5000000")
    with pytest.raises(Unparsable, match="tutarsız"):
        parse_dividend(html, "AYGAZ")


def test_dividend_missing_date_table_is_rejected_not_guessed():
    html = _b("kap_div_aygaz_teklif_1700009.html").decode("utf-8").replace("SHARE_DIVIDEND_FLEX_TABLE_3", "X")
    with pytest.raises(Unparsable, match="tarih"):
        parse_dividend(html, "AYGAZ")


def test_dividend_payment_before_ex_date_is_rejected():
    html = _b("kap_div_aygaz_teklif_1700009.html").decode("utf-8").replace("25.12.2026", "01.12.2026")
    with pytest.raises(Unparsable):
        parse_dividend(html, "AYGAZ")


def test_dividend_unknown_page_is_unparsable():
    with pytest.raises(Unparsable):
        parse_dividend("<html><body>boş</body></html>", "AYGAZ")


# ---- geri alım ----------------------------------------------------------------------------

def test_buyback_kzgyo_real_disclosure_and_arithmetic():
    """KZGYO 1700896: 18 işlem satırı; KAP'ın kendi 'daha önce alınan' sütunuyla program toplamı tutarlı olmalı."""
    b = parse_buyback(_b("kap_buyback_kzgyo_1700896.html"), "KZGYO")
    assert len(b["trades"]) == 18 and b["board_decision_date"] == "2026-10-01"
    assert b["max_nominal"] == 7_000_000 and b["fund_total_try"] == 150_000_000
    last = max(b["trades"], key=lambda t: t["date"])
    assert (last["date"], last["nominal"], last["price"]) == ("2026-11-20", 200000.0, 15.87)  # bildirim metni: ağırlıklı ort. 15,87 TL, 200.000 adet
    assert b["program_cumulative_nominal"] == 2_986_247 + 200_000
    assert b["total_nominal"] == sum(t["nominal"] for t in b["trades"])
    assert b["amount_try"] == pytest.approx(sum(t["nominal"] * t["price"] for t in b["trades"]), abs=0.01)
    assert b["first_trade_date"] == "2026-10-02" and b["last_trade_date"] == "2026-11-20"


def test_buyback_bank_template_has_no_prior_column_and_other_limit_labels():
    """GARAN 1700856: banka şablonunda 'Daha önce geri alınan' sütunu yok, limit etiketleri farklı; sütun kayması olmamalı."""
    b = parse_buyback(_b("kap_buyback_garan_1700856.html"), "GARAN")
    assert b["nature"] == "Diğer" and b["max_nominal"] == 85_000_000 and b["fund_total_try"] == 11_000_000_000
    assert b["program_cumulative_nominal"] is None  # KAP vermiyor: tahmin edilmez
    first = min(b["trades"], key=lambda t: t["date"])
    assert (first["date"], first["nominal"], first["price"]) == ("2026-11-04", 2474579.0, 137.385)
    assert all(t["prior_nominal"] is None for t in b["trades"])


def test_buyback_program_start_notice_is_skipped_with_specific_reason():
    """PGSUS 1698617 (16.11.2026): program başlatma bildirimi, işlem satırı yok."""
    with pytest.raises(Unparsable, match="program başlangıç"):
        parse_buyback(_b("kap_buyback_pgsus_program_baslangic_1698617.html"), "PGSUS")


def test_buyback_row_for_other_ticker_is_not_mixed_in():
    with pytest.raises(Unparsable, match="eşleşmedi"):
        parse_buyback(_b("kap_buyback_kzgyo_1700896.html"), "AKBNK")


def test_buyback_without_trade_table_is_unparsable():
    with pytest.raises(Unparsable, match="tablosu yok"):
        parse_buyback("<html><table><tr><td>x</td></tr></table></html>", "KZGYO")


def test_buyback_bad_number_is_rejected():
    html = _b("kap_buyback_kzgyo_1700896.html").decode("utf-8").replace("15,98", "x,y")
    with pytest.raises(Unparsable, match="okunamadı"):
        parse_buyback(html, "KZGYO")


# ---- liste süzgeci ------------------------------------------------------------------------

def test_list_disclosures_filters_subject_and_universe(monkeypatch):
    rows = [
        {"subject": KE.SUBJECT_BUYBACK, "stockCodes": "KZGYO", "publishDate": "20.11.2026 23:51:04", "disclosureIndex": 2, "summary": "a"},
        {"subject": KE.SUBJECT_BUYBACK, "stockCodes": "XXXXX", "publishDate": "20.11.2026 10:00:00", "disclosureIndex": 3},
        {"subject": "Başka Konu", "stockCodes": "KZGYO", "publishDate": "20.11.2026 10:00:00", "disclosureIndex": 4},
        {"subject": KE.SUBJECT_BUYBACK, "stockCodes": "KZGYO", "publishDate": "bozuk", "disclosureIndex": 5},
    ]
    monkeypatch.setattr(KE, "iter_fr_rows", lambda *a, **k: rows)
    out = KE.list_disclosures(KE.SUBJECT_BUYBACK_OID, KE.SUBJECT_BUYBACK, {"KZGYO"}, date(2026, 11, 1), date(2026, 11, 23))
    assert [d.index for d in out] == ["2"]
    assert out[0].published == "2026-11-20T23:51:04+03:00"


# ---- iş akışı: damgalar, kapsam, devam edilebilirlik, son iyi veri --------------------------

def _disc(idx, ticker, pub):
    return KE.Disclosure(str(idx), ticker, pub, "", KE.SUBJECT_DIVIDEND)


@pytest.fixture
def fake_kap(monkeypatch, tmp_path):
    """KAP'ı kayıtlı sayfalarla taklit eder; kaç istek yapıldığını sayar."""
    pages = {"1700009": "kap_div_aygaz_teklif_1700009.html", "1700660": "kap_div_yigit_kesinlesen_1700660.html",
             "1700896": "kap_buyback_kzgyo_1700896.html"}
    calls = []

    class R:
        def __init__(self, content):
            self.content, self.status_code = content, 200

        def raise_for_status(self):
            pass

    def get(url, **k):
        idx = url.rsplit("/", 1)[1]
        calls.append(idx)
        return R(_b(pages[idx]))

    monkeypatch.setattr(KE, "kap_get", get)
    job.gate.begin_stage()
    return calls, tmp_path


def test_dividend_document_carries_source_dates_scan_and_uses_newest_per_ticker(fake_kap):
    calls, tmp = fake_kap
    listed = [_disc(1700009, "AYGAZ", "2026-11-18T18:46:48+03:00"), _disc(1700660, "YIGIT", "2026-11-20T14:41:34+03:00"),
              _disc(1699999, "AYGAZ", "2026-06-01T10:00:00+03:00")]  # eski AYGAZ bildirimi: indirilmez
    doc = job.build_dividends(listed, {"AYGAZ": "Aygaz", "YIGIT": "Yiğit Akü"}, None, 40, "2026-11-23T10:00:00+00:00", 110,
                              (date(2026, 6, 26), date(2026, 11, 23)), tmp / "c")
    assert sorted(calls) == ["1700009", "1700660"]
    assert doc["scan"]["universeSize"] == 110 and doc["scan"]["tickersWithDisclosure"] == 2 and doc["scan"]["pending"] == 0
    assert doc["scan"]["complete"] and doc["scan"]["lastCompleteScanAt"] == "2026-11-23T10:00:00+00:00"
    for it in doc["items"]:
        assert it["sourceUrl"].startswith("https://www.kap.org.tr/tr/Bildirim/") and it["asOf"] and it["fetchedAt"] and it["publishedAt"]
    assert [i["ticker"] for i in doc["items"]] == ["YIGIT", "AYGAZ"]  # hak kullanım tarihine göre


def test_second_run_is_served_from_cache_with_zero_requests(fake_kap):
    calls, tmp = fake_kap
    listed = [_disc(1700009, "AYGAZ", "2026-11-18T18:46:48+03:00")]
    args = ({"AYGAZ": "Aygaz"}, None, 40, "2026-11-23T10:00:00+00:00", 110, (date(2026, 6, 26), date(2026, 11, 23)), tmp / "c")
    job.build_dividends(listed, *args)
    n = len(calls)
    job.build_dividends(listed, *args)
    assert len(calls) == n


def test_budget_exhaustion_counts_pending_and_resumes_next_run(fake_kap):
    calls, tmp = fake_kap
    listed = [_disc(1700009, "AYGAZ", "2026-11-18T18:46:48+03:00"), _disc(1700660, "YIGIT", "2026-11-20T14:41:34+03:00")]
    common = ({"AYGAZ": "A", "YIGIT": "Y"},)
    first = job.build_dividends(listed, *common, None, 1, "2026-11-23T10:00:00+00:00", 110, (date(2026, 6, 26), date(2026, 11, 23)), tmp / "c")
    assert first["scan"]["pending"] == 1 and not first["scan"]["complete"] and first["scan"]["lastCompleteScanAt"] is None
    second = job.build_dividends(listed, *common, first, 1, "2026-11-24T10:00:00+00:00", 110, (date(2026, 6, 26), date(2026, 11, 24)), tmp / "c")
    assert second["scan"]["pending"] == 0 and second["scan"]["complete"] and len(second["items"]) == 2


def test_unparsable_disclosure_is_counted_with_reason_and_link(fake_kap, monkeypatch):
    calls, tmp = fake_kap
    listed = [_disc(1700009, "THYAO", "2026-11-18T18:46:48+03:00")]  # sayfa AYGAZ'ın: THYAO ile eşleşmez
    doc = job.build_dividends(listed, {"THYAO": "THY"}, None, 40, "2026-11-23T10:00:00+00:00", 110, (date(2026, 6, 26), date(2026, 11, 23)), tmp / "c")
    assert doc["items"] == [] and doc["scan"]["skipped"] == {"pay grubu hisse koduyla eşleşmedi": 1}
    assert doc["scan"]["skippedItems"][0]["sourceUrl"].endswith("/1700009")


WIN = (date(2026, 6, 26), date(2026, 12, 20))


def _both(fake_kap, fetched_at):
    calls, tmp = fake_kap
    listed = [_disc(1700009, "AYGAZ", "2026-11-18T18:46:48+03:00"), _disc(1700660, "YIGIT", "2026-11-20T14:41:34+03:00")]
    return job.build_dividends(listed, {"AYGAZ": "A", "YIGIT": "Y"}, None, 40, fetched_at, 110, WIN, tmp / "c")


def _past(doc):
    return {i["ticker"]: i["installments"][0]["exDatePast"] for i in doc["items"]}


def test_past_ex_dates_are_marked_relative_to_generation_day_in_istanbul(fake_kap):
    """YIGIT hak kullanım 15.12.2026, AYGAZ 23.12.2026. Üretim günü 20.12 → YIGIT geçti, AYGAZ değil."""
    assert _past(_both(fake_kap, "2026-12-20T10:00:00+00:00")) == {"YIGIT": True, "AYGAZ": False}


def test_ex_date_day_itself_is_not_past_and_day_uses_istanbul_not_utc(fake_kap):
    # 14.12 22:00 UTC = 15.12 01:00 İstanbul → hak kullanım günü bugün: geçmedi.
    assert _past(_both(fake_kap, "2026-12-14T22:00:00+00:00"))["YIGIT"] is False
    # 15.12 22:00 UTC = 16.12 01:00 İstanbul → geçti.
    assert _past(_both(fake_kap, "2026-12-15T22:00:00+00:00"))["YIGIT"] is True


def test_past_flag_is_recomputed_for_rows_carried_over_from_previous_file(fake_kap):
    calls, tmp = fake_kap
    listed = [_disc(1700660, "YIGIT", "2026-11-20T14:41:34+03:00")]
    first = job.build_dividends(listed, {"YIGIT": "Y"}, None, 40, "2026-12-10T10:00:00+00:00", 110, WIN, tmp / "c")
    assert _past(first)["YIGIT"] is False
    # Bütçe 0 + boş önbellek: satır önceki dosyadan taşınır, bayrak yeni üretim gününe göre güncellenir.
    second = job.build_dividends(listed, {"YIGIT": "Y"}, first, 0, "2026-12-20T10:00:00+00:00", 110, WIN, tmp / "empty")
    assert _past(second)["YIGIT"] is True


def test_pending_tickers_are_listed_so_not_scanned_differs_from_scanned_none(fake_kap):
    calls, tmp = fake_kap
    listed = [_disc(1700009, "AYGAZ", "2026-11-18T18:46:48+03:00"), _disc(1700660, "YIGIT", "2026-11-20T14:41:34+03:00")]
    names = {"AYGAZ": "A", "YIGIT": "Y"}
    first = job.build_dividends(listed, names, None, 1, "2026-12-01T10:00:00+00:00", 110, WIN, tmp / "c")
    sc = first["scan"]
    (p,) = sc["pendingItems"]
    assert sc["pending"] == 1 and p["ticker"] == "YIGIT" and p["sourceUrl"].endswith("/1700660")
    assert [i["ticker"] for i in first["items"]] == ["AYGAZ"]  # taranmış; YIGIT'in satırı yok ama "bekleyen" olarak adlı
    second = job.build_dividends(listed, names, first, 1, "2026-12-02T10:00:00+00:00", 110, WIN, tmp / "c")
    assert second["scan"]["pendingItems"] == [] and second["scan"]["complete"]


def test_unparsable_stays_distinct_from_pending(fake_kap):
    calls, tmp = fake_kap
    listed = [_disc(1700009, "THYAO", "2026-11-18T18:46:48+03:00")]
    doc = job.build_dividends(listed, {"THYAO": "T"}, None, 40, "2026-12-01T10:00:00+00:00", 110, WIN, tmp / "c")
    assert doc["scan"]["pendingItems"] == [] and doc["scan"]["skippedItems"][0]["ticker"] == "THYAO"


def test_buyback_pending_items_are_listed(fake_kap):
    calls, tmp = fake_kap
    listed = [KE.Disclosure("1700896", "KZGYO", "2026-11-20T23:51:04+03:00", "", KE.SUBJECT_BUYBACK)]
    doc = job.build_buybacks(listed, {"KZGYO": "K"}, None, 0, "2026-11-23T10:00:00+00:00", 110, (date(2026, 10, 9), date(2026, 11, 23)), tmp / "empty")
    assert doc["items"] == [] and [p["ticker"] for p in doc["scan"]["pendingItems"]] == ["KZGYO"]


def test_amount_note_states_source_figures_and_never_derives_net():
    d = parse_dividend(_b("kap_div_aygaz_teklif_1700009.html"), "AYGAZ")
    note = job.amount_note(d["installments"][0])
    assert "%15" in note and "bildirimdeki" in note and "farklı" in note
    equal = job.amount_note({"gross": 2.0, "net": 2.0, "withholding_pct": 0.0})
    assert "aynı" in equal and "hesaplamadı" in equal


def test_dividend_item_carries_amount_note(fake_kap):
    doc = _both(fake_kap, "2026-12-01T10:00:00+00:00")
    assert all(i["installments"][0]["amountNote"] for i in doc["items"])


def test_missing_net_is_rejected_not_derived_from_gross_and_default_withholding():
    html = _b("kap_div_aygaz_teklif_1700009.html").decode("utf-8").replace("3,9525000", "")
    with pytest.raises(Unparsable, match="okunamadı"):
        parse_dividend(html, "AYGAZ")


def test_cli_help_defaults_match_real_defaults():
    import argparse

    from esham import main as M

    sub = next(a for a in M.build_parser()._actions if isinstance(a, argparse._SubParsersAction)).choices["kap-events"]
    text = " ".join(sub.format_help().split())
    assert f"varsayılan {job.DEFAULT_DIVIDEND_DAYS};" in text
    assert f"varsayılan {job.DEFAULT_BUYBACK_DAYS};" in text
    assert f"varsayılan {job.DEFAULT_MAX_DETAILS};" in text


def test_buyback_document_fields(fake_kap):
    calls, tmp = fake_kap
    listed = [KE.Disclosure("1700896", "KZGYO", "2026-11-20T23:51:04+03:00", "", KE.SUBJECT_BUYBACK)]
    doc = job.build_buybacks(listed, {"KZGYO": "Kuzugrup GYO"}, None, 40, "2026-11-23T10:00:00+00:00", 110, (date(2026, 10, 9), date(2026, 11, 23)), tmp / "c")
    (it,) = doc["items"]
    assert it["asOf"] == "2026-11-20" and it["lastTradeDate"] == "2026-11-20" and it["maxNominal"] == 7_000_000
    assert it["sourceUrl"].endswith("/1700896") and it["programCumulativeNominal"] == 3_186_247


def test_list_failure_leaves_files_untouched(monkeypatch, tmp_path):
    (tmp_path / job.DIVIDEND_FILE).write_text('{"fetchedAt": "2026-11-20T10:00:00+00:00"}', encoding="utf-8")

    def boom(*a, **k):
        raise job.KapUnavailable("429")

    monkeypatch.setattr(job.KE, "list_disclosures", boom)
    assert job.run_kap_events(data_dir=tmp_path) == 0
    assert json.loads((tmp_path / job.DIVIDEND_FILE).read_text(encoding="utf-8")) == {"fetchedAt": "2026-11-20T10:00:00+00:00"}
    assert not (tmp_path / job.BUYBACK_FILE).exists()


# ---- yayınlanmış dosya koruması (repodaki veri) ---------------------------------------------

DATA = Path(__file__).resolve().parents[2] / "web" / "public" / "data"
ITEM_REQUIRED = ("ticker", "disclosureIndex", "sourceUrl", "publishedAt", "asOf", "fetchedAt")


@pytest.mark.parametrize("fname", ["kap-dividends.json", "kap-buybacks.json"])
def test_committed_kap_event_files_carry_source_dates_and_coverage(fname):
    p = DATA / fname
    if not p.exists():
        pytest.skip("henüz üretilmedi: sayfa veri yoksa çizilmez")
    doc = json.loads(p.read_text(encoding="utf-8"))
    assert doc["source"] and doc["sourceUrl"].startswith("https://") and doc["fetchedAt"] and doc["updatedAt"]
    for k in ("universeSize", "tickersWithDisclosure", "disclosuresListed", "parsed", "pending", "windowFrom", "windowTo", "skipped"):
        assert k in doc["scan"], k
    rows = list(doc["items"]) + list(doc.get("noDividend", []))
    for it in rows:
        for k in ITEM_REQUIRED:
            assert it.get(k), (fname, it.get("ticker"), k)
        assert it["sourceUrl"].endswith("/" + str(it["disclosureIndex"]))
