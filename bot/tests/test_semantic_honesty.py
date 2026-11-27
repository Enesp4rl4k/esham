"""Anlamsal dürüstlük: her şablon cümlesi hangi veri alanını ve hangi zaman kuralını kullandığını söyler.

İnceleme 2026-11-27 bulguları (yayınlanmış raporlar; dosyalar DÜZELTİLMEDİ, yalnız üreticiler):
- Sabah raporu "10.977,01 seviyesinde, +2,18% değişimle güne başladı" — son işlem/önceki kapanış değişimi
  açılış gibi sunuldu (açılış 10.737,18 / -%0,06 idi; rapor anında seans kapalıydı).
- "En çok düşen: GYO (+0,37%), Mali (+0,27%)" — pozitif değişimler düşenler listesinde.
- "S&P 500 +1,16% yükseldi (7" — özet binlik noktada kesildi.
- "Marketwide", "Bulgaristan?da", "+2,18%" / "(%+4.66)" karışık biçim.

Bu dosya (1) ``market_text.SENTENCE_CATALOG`` tablosunu senaryolarla doğrular, (2) bugünün gerçek rakamlarıyla
düzeltilmiş cümleleri ve (3) 13 üreticinin fikstür çıktısını birebir (golden) denetler. Ağ yok, LLM yok.
"""
from __future__ import annotations

import re
from datetime import date, datetime

import pytest

from esham import market_text, pipeline
from esham.formatting import TR_TZ
from esham.freshness import MARKET_DATA_MAX_AGE_DAYS, market_as_of_status
from esham.neutral import find_banned, strip_banned
from esham.sources import MarketSummary
from esham.sources.bars import PeriodChange, daily_bars, period_change, session_info
from esham.sources.global_macro import GlobalMacroSnapshot, MacroTicker
from esham.sources.news_detector import _macro_event, _sector_event, macro_move_size, THRESHOLDS
from esham.sources.sector import SectorMove, movers_lines, split_movers
from esham.sources.viop import ViopQuote

import test_producers_neutral as P  # fikstür üreticileri (sahte kaynaklar) aynen kullanılır

T = lambda *a: datetime(*a, tzinfo=TR_TZ)  # noqa: E731

# 2026-11-27'nin gerçek rakamları (yayınlanmış raporlardan)
REAL_BIST = MarketSummary(
    index="XU100", price="10.977,01", change="+%2,18", open_price="10.737,18", open_change="-%0,06",
    price_value=10977.01, change_pct=2.18, open_value=10737.18, open_change_pct=-0.06,
    as_of=T(2026, 11, 27, 18, 10), market_open=False,
)
REAL_SECTORS = [SectorMove(c, n, p, as_of=date(2026, 11, 27)) for c, n, p in (
    ("XUTEK", "Teknoloji", 4.66), ("XUSIN", "Sınai", 4.48), ("XILTM", "İletişim", 3.12),
    ("XGMYO", "GYO", 0.37), ("XUMAL", "Mali", 0.27), ("XBANK", "Bankacılık", -1.02))]


# ---- (1) katalog: alan + zaman kuralı -------------------------------------------------------------

def _b(**kw) -> MarketSummary:
    base = dict(REAL_BIST.__dict__)
    base.update(kw)
    return MarketSummary(**base)


EVENING = T(2026, 11, 27, 18, 29)     # sabah raporunun bugün fiilen yayınlandığı an (seans kapalı)
NEXT_MONDAY = T(2026, 11, 30, 8, 30)  # bir sonraki işlem gününden önce
STALE_NOW = T(2026, 12, 4, 8, 30)

# şablon, girdi, an, beklenen (None: cümle YAZILMAZ)
HONESTY_TABLE = [
    ("bist_last", REAL_BIST, EVENING,
     "BIST XU100 endeksinde son işlem: 10.977,01 (27.11.2026 18:10 TSİ); önceki kapanışa göre değişim +%2,18."),
    ("bist_last", REAL_BIST, NEXT_MONDAY,
     "BIST XU100 endeksinde son işlem: 10.977,01 (27.11.2026 18:10 TSİ); önceki kapanışa göre değişim +%2,18."),
    ("bist_last", REAL_BIST, STALE_NOW, None),                 # sınırdan eski → yazılmaz
    ("bist_last", _b(as_of=None), EVENING, None),               # zaman damgası yok → yazılmaz
    ("bist_last", _b(change_pct=None), EVENING, None),          # alan eksik → başka alan konmaz
    ("bist_open", REAL_BIST, EVENING,
     "Borsa İstanbul XU100 endeksi 27.11.2026 seansını 10.737,18 puandan açtı; açılışın önceki kapanışa göre farkı -%0,06."),
    ("bist_open", REAL_BIST, NEXT_MONDAY, None),                # açılış bugünün değil → yazılmaz
    ("bist_open", _b(open_price="", open_change_pct=None), EVENING, None),  # açılış yok → son fiyat "açılış" olmaz
    ("bist_close", REAL_BIST, EVENING,
     "BIST XU100 endeksi 27.11.2026 seansını 10.977,01 puandan kapattı; önceki kapanışa göre değişim +%2,18."),
    ("bist_close", _b(market_open=True), EVENING, None),        # seans açıkken "kapattı" denmez
    ("bist_close", _b(market_open=None), EVENING, None),        # seans durumu bilinmiyor
    ("bist_close", REAL_BIST, NEXT_MONDAY, None),               # bugünün kapanışı değil
]


@pytest.mark.parametrize("name,data,now,expected", HONESTY_TABLE)
def test_honesty_table(name, data, now, expected):
    assert name in market_text.SENTENCE_CATALOG
    assert getattr(market_text, name)(data, now) == expected


def test_every_catalog_template_is_exercised():
    covered = {row[0] for row in HONESTY_TABLE} | {"bist_week", "sector_movers", "viop_index"}
    assert covered == set(market_text.SENTENCE_CATALOG)
    for name, (fields, rule) in market_text.SENTENCE_CATALOG.items():
        assert fields and rule, name


def test_bist_week_states_both_dates():
    wk = PeriodChange(pct=-1.39, base_date=date(2026, 11, 20), last_date=date(2026, 11, 27), last_close=10977.01)
    assert market_text.bist_week("XU100", wk) == (
        "BIST XU100 endeksi 27.11.2026 kapanışında 10.977,01; 20.11.2026 kapanışına göre haftalık değişim -%1,39.")
    assert market_text.bist_week("XU100", None) is None


def test_viop_index_line_labels_spot_and_fetch_time():
    q = ViopQuote("XU030", "13.763,83", "+%2,31", fetched_at=T(2026, 11, 27, 19, 54))
    assert market_text.viop_index_line(q) == (
        "BIST 30 endeksi (XU030; VİOP endeks kontratlarının dayanağı): 13.763,83, önceki kapanışa göre +%2,31. "
        "Veri alınma zamanı: 27.11.2026 19:54 TSİ.")


@pytest.mark.parametrize("as_of,now,status", [
    (T(2026, 11, 27, 18, 10), T(2026, 11, 27, 18, 29), "today"),
    (T(2026, 11, 27, 18, 10), T(2026, 11, 30, 8, 30), "previous"),
    (T(2026, 11, 27, 18, 10), T(2026, 12, 4, 8, 30), "stale"),
    (None, T(2026, 11, 27, 18, 29), "unknown"),
    (T(2026, 11, 28, 10, 0), T(2026, 11, 27, 18, 29), "stale"),  # gelecekteki damga güvenilmez
])
def test_freshness_guard(as_of, now, status):
    assert MARKET_DATA_MAX_AGE_DAYS == 4
    assert market_as_of_status(as_of, now) == status


# ---- (2) bugünün gerçek rakamlarıyla düzeltilmiş çıktı -------------------------------------------

def test_morning_summary_no_longer_says_gune_basladi():
    old = "XU100 endeksi 10.977,01 seviyesinde, +2,18% değişimle güne başladı."
    new = market_text.bist_last_short(REAL_BIST, EVENING)
    assert new == "XU100 son işlem 10.977,01 (27.11.2026 18:10 TSİ), önceki kapanışa göre +%2,18."
    assert "güne başladı" not in new and new != old


def test_ranked_lists_respect_sign():
    ups, downs = split_movers(REAL_SECTORS, 3)
    assert [m.name for m in ups] == ["Teknoloji", "Sınai", "İletişim"]
    assert [m.name for m in downs] == ["Bankacılık"]  # GYO +0,37 ve Mali +0,27 artık "düşen" değil
    assert movers_lines(REAL_SECTORS) == (
        "Teknoloji (+%4,66), Sınai (+%4,48), İletişim (+%3,12)", "Bankacılık (-%1,02)")
    all_up = [m for m in REAL_SECTORS if m.change_pct > 0]
    assert movers_lines(all_up)[1] == "düşen sektör yok"
    assert movers_lines([SectorMove("X", "X", -0.5)])[0] == "yükselen sektör yok"
    assert movers_lines([SectorMove("X", "X", 0.001)]) == ("yükselen sektör yok", "düşen sektör yok")
    md = market_text.sector_movers_md(REAL_SECTORS)
    assert md == ("- **Yükselen sektörler (en yüksek günlük değişim):** Teknoloji (+%4,66), Sınai (+%4,48), İletişim (+%3,12)\n"
                  "- **Düşen sektörler (en düşük günlük değişim):** Bankacılık (-%1,02)")
    assert not find_banned(md) and strip_banned(md) == md


def test_morning_template_with_real_numbers():
    from esham.ai.analyzer import MarketAIAnalyzer
    from esham.sources import MarketSnapshot

    snap = MarketSnapshot(bist=REAL_BIST, sector=REAL_SECTORS,
                          viop_quote=ViopQuote("XU030", "13.763,83", "+%2,31"))
    body = MarketAIAnalyzer._template_morning_report(snap, EVENING)
    assert ("BIST XU100 endeksinde son işlem: 10.977,01 (27.11.2026 18:10 TSİ); önceki kapanışa göre değişim "
            "+%2,18. Seans şu an kapalı.") in body
    assert "- **Düşen sektörler (en düşük günlük değişim):** Bankacılık (-%1,02)" in body
    assert "BIST 30 endeksi (XU030; VİOP endeks kontratlarının dayanağı): 13.763,83" in body
    assert "güne başladı" not in body and "En çok düşen" not in body and "Marketwide" not in body
    # tarihi bilinmeyen endeks rakamı yazılmaz; eksik veri eksik görünür
    body2 = MarketAIAnalyzer._template_morning_report(MarketSnapshot(bist=_b(as_of=None)), EVENING)
    assert "10.977,01" not in body2 and "veri zamanı doğrulanamadı" in body2


def test_sp500_event_title_and_summary_are_whole_sentences():
    t = MacroTicker("S&P 500", 7266.17, 1.16, prev=7266.17 / 1.0116, as_of=T(2026, 11, 27, 19, 24))
    ev = _macro_event(t)
    assert ev.headline == "S&P 500 önceki kapanışa göre +%1,16 (7.266,17)."
    assert ev.details == ("S&P 500 son değeri 7.266,17 (veri zamanı: 27.11.2026 19:24 TSİ); "
                          "önceki kapanışa göre değişim +%1,16.")
    from esham.ai.analyzer import MarketAIAnalyzer

    body, summary, tweet = MarketAIAnalyzer._template_event_analysis(ev)
    assert summary == ev.headline  # eskiden "S&P 500 +1,16% yükseldi (7"
    assert "27.11.2026 19:24 TSİ" in body and "(7" not in summary.replace("(7.266,17)", "")


def test_rate_change_in_basis_points_and_threshold_in_points():
    t = MacroTicker("ABD 10Y", 4.91, (4.91 - 4.85) / 4.85 * 100, suffix="%", prev=4.85)
    assert t.value_str == "%4,91" and t.change_report == "+6 baz puan"
    assert _macro_event(t).headline == "ABD 10 yıllık tahvil faizi önceki kapanışa göre +6 baz puan (%4,91)."
    assert macro_move_size(t) == pytest.approx(0.06) and macro_move_size(t) >= THRESHOLDS["ABD 10Y"]
    tiny = MacroTicker("ABD 10Y", 4.911, 0.02, suffix="%", prev=4.910)  # 0,1 baz puan: eskiden tetikleniyordu
    assert macro_move_size(tiny) < THRESHOLDS["ABD 10Y"]


def test_sector_event_has_no_judgement_words():
    ev = _sector_event(SectorMove("XUTEK", "Teknoloji", 4.66, as_of=date(2026, 11, 27)))
    assert ev.headline == "BIST Teknoloji sektör endeksi önceki kapanışa göre +%4,66 (veri tarihi: 27.11.2026)."
    assert "güçlü" not in ev.headline and "sert" not in ev.headline


def test_macro_table_carries_as_of_per_row_and_unknown_is_labelled():
    snap = GlobalMacroSnapshot([MacroTicker("S&P 500", 7243.42, 0.84, prev=7183.1, as_of=T(2026, 11, 27, 18, 0)),
                                MacroTicker("VIX", 26.66, -0.52)])
    assert snap.to_markdown_table().splitlines() == [
        "| Enstrüman | Son değer | Önceki kapanışa göre | Veri zamanı |",
        "| --- | --- | --- | --- |",
        "| S&P 500 | 7.243,42 | +%0,84 | 27.11.2026 18:00 TSİ |",
        "| VIX | 26,66 | -%0,52 | bilinmiyor |",
    ]


def test_stale_macro_rows_are_dropped():
    snap = GlobalMacroSnapshot([MacroTicker("S&P 500", 1.0, 1.0, prev=1.0, as_of=T(2026, 11, 20, 23, 0)),
                                MacroTicker("DAX", 2.0, 1.0, prev=1.0, as_of=T(2026, 11, 27, 19, 0))])
    out = pipeline._drop_stale_macro(snap, T(2026, 11, 27, 19, 30))
    assert [t.label for t in out.tickers] == ["DAX"]


# ---- bar yardımcıları (günlük / haftalık değişimin tanımı) ---------------------------------------

def _chart(days_closes, offset=10800):
    ts = [int(datetime(*d, 15, 0, tzinfo=TR_TZ).timestamp()) for d, _ in days_closes]
    return {"meta": {"gmtoffset": offset}, "timestamp": ts,
            "indicators": {"quote": [{"close": [c for _, c in days_closes]}]}}


def test_period_change_daily_and_weekly():
    bars = daily_bars(_chart([((2026, 11, 19), 100.0), ((2026, 11, 20), 110.0), ((2026, 11, 24), 105.0),
                              ((2026, 11, 27), 99.0), ((2026, 11, 27), 99.0)]))
    assert [d for d, _ in bars] == [date(2026, 11, 19), date(2026, 11, 20), date(2026, 11, 24), date(2026, 11, 27)]
    d = period_change(bars, "1d")
    assert (d.base_date, d.last_date, round(d.pct, 4)) == (date(2026, 11, 24), date(2026, 11, 27), round(-6 / 105 * 100, 4))
    w = period_change(bars, "1w")
    assert (w.base_date, w.last_date, round(w.pct, 4)) == (date(2026, 11, 20), date(2026, 11, 27), -10.0)
    assert period_change(bars[:1], "1d") is None


def test_session_info():
    meta = {"regularMarketTime": int(T(2026, 11, 27, 18, 10).timestamp()),
            "currentTradingPeriod": {"regular": {"start": int(T(2026, 11, 27, 10, 0).timestamp()),
                                                 "end": int(T(2026, 11, 27, 18, 0).timestamp())}}}
    as_of, is_open = session_info(meta, T(2026, 11, 27, 18, 29))
    assert as_of == T(2026, 11, 27, 18, 10) and is_open is False
    assert session_info(meta, T(2026, 11, 27, 11, 0))[1] is True
    assert session_info({}, T(2026, 11, 27, 11, 0)) == (None, None)


# ---- (3) 13 üretici: golden çıktı ---------------------------------------------------------------

@pytest.fixture
def run(fakes):  # noqa: F811 — test_producers_neutral.fakes
    def _run(name):
        P._Store.drafts = []
        P._Social.posts = []
        P.PRODUCERS[name]()
        assert P._Store.drafts, name
        return P._Store.drafts[-1], list(P._Social.posts)
    return _run


fakes = P.fakes

GOLDEN = {
    "sabah bülteni": (
        "XU100 son işlem 10.000,00 (27.11.2026 18:10 TSİ), önceki kapanışa göre +%1,20. "
        "Küresel makro gelişmeler ve KAP gündemi sabah bülteninde.",
        ["BIST XU100 endeksinde son işlem: 10.000,00 (27.11.2026 18:10 TSİ); önceki kapanışa göre değişim +%1,20. "
         "Seans şu an kapalı.",
         "- **Yükselen sektörler (en yüksek günlük değişim):** Bankacılık (+%2,50), Sınai (+%1,00), Gıda (+%0,20)",
         "- **Düşen sektörler (en düşük günlük değişim):** Turizm (-%2,00), İletişim (-%1,10), Holding (-%0,40)",
         "| VIX | 16,10 | +%1,83 | bilinmiyor |"]),
    "VİOP": (
        "VİOP teminat stresi (2026-11-27): Yükseliyor. Margin-call toplam 1,0 Milyon TL.",
        ["| BIST 30 endeksi (XU030, dayanak) | 11.000,00 | +%1,00 |", "## Piyasa Geneli Teminat (Takasbank)",
         "| Margin-call / Gereken | %0,100 |",
         "Margin-call/gereken teminat oranı %0,050 → %0,100 (önceki kayıtlı ölçüme göre yükseldi)."]),
    "açılış bülteni": (
        "Borsa İstanbul XU100 endeksi 27.11.2026 seansını 9.950,00 puandan açtı; açılışın önceki kapanışa göre "
        "farkı +%0,50. BIST XU100 endeksinde son işlem: 10.000,00 (27.11.2026 18:10 TSİ); önceki kapanışa göre "
        "değişim +%1,20. Seans şu an kapalı.",
        ["**Sektör endeksleri — günlük değişim (önceki kapanışa göre; veri tarihi 27.11.2026):**"]),
    "kapanış bülteni": (
        "BIST XU100 endeksi 27.11.2026 seansını 10.000,00 puandan kapattı; önceki kapanışa göre değişim +%1,20.",
        ["| BIST XU100 | 10.000,00 | +%1,20 |", "| BIST 30 (XU030, VİOP dayanağı) | 11.000,00 | +%1,00 |"]),
    "gündem": ("TCMB politika faizini sabit tuttu.", ["TCMB politika faizini sabit tuttu."]),
    "haftalık sektör": (
        "Sektör endeksleri — haftalık değişim (önceki haftanın son kapanışına göre; veri tarihi 27.11.2026). "
        "Yükselenler: Bankacılık (+%2,50), Sınai (+%1,00), Gıda (+%0,20). "
        "Düşenler: Turizm (-%2,00), İletişim (-%1,10), Holding (-%0,40).",
        ["| Sektör | Haftalık değişim |", "| Holding | -%0,40 |",
         "- **Düşen sektörler (en düşük haftalık değişim):** Turizm (-%2,00), İletişim (-%1,10), Holding (-%0,40)"]),
    "emsal/çarpan tablosu": (
        "Bankacılık çarpan tablosu: medyan F/K 4,00, medyan PD/DD 1,00.",
        ["| AKBNK | 60,00 | +%1,00 | 4,00 | 1,00 | — | %3,0 | %25,0 |"]),
    "küresel makro": (
        "Önceki kapanışa göre: VIX +%1,83 | ALTIN +%0,40 | BRENT -%0,20",
        ["Önceki kapanışa göre en büyük mutlak yüzde değişim: VIX +%1,83."]),
    "KAP haber": ("A A.Ş.: Yeni İş İlişkisi", []),
    "makro olay": ("VIX endeksi +%1,83 yükseldi (16,10).",  # fikstür başlığı; dedektör başlığı ayrı testte
                   ["- **VIX:** 16,10 (önceki kapanışa göre +%1,83)"]),
    "haftalık özet": (
        "BIST XU100 endeksi 27.11.2026 kapanışında 10.000,00; 20.11.2026 kapanışına göre haftalık değişim -%1,39. "
        "Yükselen sektörler (haftalık): Bankacılık (+%2,50), Sınai (+%1,00), Gıda (+%0,20).",
        ["## KAP & Şirket Haberleri (son 7 gün)"]),
    "halka arz analizi": ("İzahnamede 45,50 TL fiyatla 1 milyar TL büyüklüğünde arz belirtilmiştir.",
                          ["| Halka Arz Fiyatı | 45,50 TL |"]),
    "finansal tablo analizi": ("Belgede 9 aylık hasılat ve net kâr açıklanmıştır.", ["| Net Kâr Marjı | %12 |"]),
}

_LEFTOVER = re.compile(r"Marketwide|güne başladı|En çok düşen|En çok yükselen|Seans içi|\d\.\d+%|%[+-]\d|�"
                       r"|[^\W\d_]\?[^\W\d_]")


def test_golden_covers_all_producers():
    assert set(GOLDEN) == set(P.PRODUCERS)


@pytest.mark.parametrize("name", list(P.PRODUCERS))
def test_producer_golden(name, run):
    draft, posts = run(name)
    summary, lines = GOLDEN[name]
    assert draft.summary == summary, name
    body_lines = draft.body.splitlines()
    for line in lines:
        assert line in body_lines, (name, line, draft.body)
    for text in [draft.title, draft.summary, draft.body, *posts]:
        assert not _LEFTOVER.search(text), (name, _LEFTOVER.search(text).group(0), text)
    # üretilmiş metin tarafsız süzgeçten DEĞİŞMEDEN geçer
    squash = lambda t: re.sub(r"\n{3,}", "\n\n", t).strip()  # noqa: E731
    assert squash(strip_banned(draft.body)) == squash(draft.body), name


def test_producers_without_timestamp_do_not_publish_dated_claims(monkeypatch, fakes):
    """BIST zaman damgası yoksa açılış/kapanış raporu yok; sabah raporunda BIST rakamı yok."""
    undated = MarketSummary(**{**P.SUMMARY.__dict__, "as_of": None})
    monkeypatch.setattr(P._Bist, "market_summary", lambda self: undated)
    from esham.sources import MarketSnapshot

    monkeypatch.setattr(pipeline, "gather_snapshot", lambda: MarketSnapshot(bist=undated))
    P._Store.drafts = []
    assert pipeline.run_opening_report() is None and pipeline.run_closing_report() is None
    pipeline.run_morning_report(publish_social=False)
    (d,) = P._Store.drafts
    assert "10.000,00" not in d.summary and "10.000,00" not in d.body
    assert d.summary == "Küresel makro gelişmeler ve KAP gündemi sabah bülteninde."
