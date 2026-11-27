"""Üretici başına sürüm + kaynağında temizlik testi.

Her rapor üreticisi sahte (ağsız) veriyle çalıştırılır ve yayın deposuna GİDEN taslak yakalanır:
- `schemaVersion == 2` (web'in "eski kayıt" kararı yalnız bu alana dayanır; bkz. web/src/lib/neutral.ts),
- şablon metni süzgeçten DEĞİŞMEDEN geçer (yani kaynağında temizdir; ContentStore süzgecine güvenilmez),
- özet ve başlıkta yasaklı kalıp yok; yönlendirici/sıralama dili ("izlenmeye değer", "En ucuz",
  "açılış beklentilerini", "risk iştahı", "Güçlü/Zayıf") yok.
LLM çağrısı yapılmaz (şablon yolu: canlıda çalışan yol budur).
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from esham import analysis, pipeline
from esham.ai.client import LlmClient
from esham.neutral import REPORT_SCHEMA_VERSION, find_banned, normalize, strip_banned
from esham.publishing.content_store import ReportDraft
from esham.sources import Disclosure, MarketSnapshot, MarketSummary
from esham.sources.global_macro import GlobalMacroSnapshot, MacroTicker
from esham.sources.peer import PeerMetric, PeerSnapshot
from esham.sources.sector import SectorMove
from esham.sources.viop import ViopMarginSnapshot, ViopQuote

# Liste dışı, yönlendirici/sıralama/tahmin dili (incelemenin E3 bulguları + benzerleri)
TEMPLATE_STEERING = [
    "izlenmeye deger", "en ucuz", "en pahali", "beklentilerini sekillendir", "risk istahi", "guclu:", "zayif:",
    "guclu sektor", "zayif sektor", "kazananlari", "rotasyon", "para akisi", "momentum", "olasi", "dalgasi",
    "yansiyacak", "takip ediliyor", "izleniyor", "medyanin altinda", "iskonto primi", "prim gerekcesi",
]


class _Store:
    drafts: list[ReportDraft] = []

    def __init__(self, *a, **k):
        self.last_status = "none"

    def prepare(self, draft):
        return "ok"

    def publish(self, draft, prepared=False):
        _Store.drafts.append(draft)
        self.last_status = "published"
        return Path("x.json")


class _Social:
    posts: list[str] = []

    def broadcast(self, message, *a, **k):
        _Social.posts.append(message)

    def broadcast_thread(self, tweets, *a, **k):
        _Social.posts.extend(tweets)


SUMMARY = MarketSummary(index="XU100", price="10.000,00", change="+%1,20", volume="100 milyar TL",
                        open_price="9.950,00", open_change="+%0,50")
SECTORS = [SectorMove("XBANK", "Bankacılık", 2.5), SectorMove("XUSIN", "Sınai", 1.0), SectorMove("XGIDA", "Gıda", 0.2),
           SectorMove("XHOLD", "Holding", -0.4), SectorMove("XILTM", "İletişim", -1.1), SectorMove("XTRZM", "Turizm", -2.0)]
MACRO = GlobalMacroSnapshot(tickers=[MacroTicker("VIX", 16.1, 1.83), MacroTicker("ALTIN", 4145.0, 0.4),
                                     MacroTicker("BRENT", 72.5, -0.2)])
DISCLOSURES = [
    Disclosure("A A.Ş.: Yeni İş İlişkisi", "A A.Ş.", "2026-11-27", "Yeni İş İlişkisi", ticker="AAAAA",
               disclosure_index="1"),
    Disclosure("B A.Ş.: Pay Alım Satım Bildirimi", "B A.Ş.", "2026-11-27", "Pay Alım Satım Bildirimi",
               ticker="BBBBB", is_insider=True, disclosure_index="2"),
]


class _Bist:
    def __init__(self, *a, **k):
        pass

    def market_summary(self):
        return SUMMARY

    def fetch_closes(self, *a, **k):
        return [1.0, 2.0, 3.0]


class _Viop:
    def market_quote(self):
        return ViopQuote("XU030", "11.000,00", "+%1,00")

    def margin_snapshot(self):
        return ViopMarginSnapshot("2026-11-27", 1000, 1_000_000.0, 1_000_000_000.0, 0.1)


class _Sector:
    def snapshot(self):
        return list(SECTORS)


class _Macro:
    def snapshot(self):
        return MACRO

    def fetch_closes(self, *a, **k):
        return [1.0, 2.0]


class _Peer:
    def snapshot(self, key):
        return PeerSnapshot(key, "Bankacılık", peers=[
            PeerMetric("AKBNK", "Akbank", price=60.0, change_pct=1.0, pe=4.0, pb=1.0, ev_ebitda=None, dividend_yield=3.0, roe=25.0),
            PeerMetric("GARAN", "Garanti", price=130.0, change_pct=-0.5, pe=5.5, pb=1.4, dividend_yield=2.0, roe=30.0),
            PeerMetric("YKBNK", "Yapı Kredi", price=30.0, change_pct=0.2, pe=3.2, pb=0.9, dividend_yield=1.0, roe=20.0),
        ])


class _Kap:
    def latest_disclosures(self):
        return list(DISCLOSURES)

    def get_detail_text(self, index):
        return "Şirketimiz 85 milyon TL tutarında iş almıştır."


class _State:
    def get_margin_prev_pct(self):
        return 0.05

    def set_margin_prev_pct(self, pct):
        pass


@pytest.fixture(autouse=True)
def fakes(monkeypatch):
    _Store.drafts = []
    _Social.posts = []
    monkeypatch.setattr(LlmClient, "generate", lambda self, *a, **k: None)
    monkeypatch.setattr(LlmClient, "generate_json", lambda self, *a, **k: None)
    for mod in (pipeline, analysis):
        monkeypatch.setattr(mod, "ContentStore", _Store)
        monkeypatch.setattr(mod, "_render_card", lambda spec: None)
    monkeypatch.setattr(pipeline, "SocialPublisher", _Social)
    monkeypatch.setattr(pipeline, "BistSource", _Bist)
    monkeypatch.setattr(pipeline, "ViopSource", _Viop)
    monkeypatch.setattr(pipeline, "SectorSource", _Sector)
    monkeypatch.setattr("esham.sources.sector.SectorSource", _Sector)
    monkeypatch.setattr(pipeline, "GlobalMacroSource", _Macro)
    monkeypatch.setattr(pipeline, "PeerSource", _Peer)
    monkeypatch.setattr(pipeline, "KapSource", _Kap)
    monkeypatch.setattr(pipeline, "update_ticker_data", lambda: None)
    monkeypatch.setattr(pipeline, "update_turib_market_data", lambda: None)
    monkeypatch.setattr(pipeline, "generate_pdf", lambda **k: None)
    monkeypatch.setattr(pipeline, "_PhotoSource", lambda: type("P", (), {"fetch_photo": lambda s, *a: None})())
    monkeypatch.setattr("esham.state.get_state", lambda: _State())
    monkeypatch.setattr(pipeline, "gather_snapshot", lambda: MarketSnapshot(
        bist=SUMMARY, disclosures=list(DISCLOSURES), sector=list(SECTORS), macro=MACRO))
    monkeypatch.setattr(analysis, "load_document_text", lambda src: "İzahname metni. Halka arz fiyatı 45,50 TL.")
    monkeypatch.setattr(analysis, "IpoPdfGenerator", lambda: type("G", (), {"create": lambda s, d: None})())


def _event():
    from esham.sources.news_detector import MarketEvent
    return MarketEvent(kind="MAKRO_HAREKET", label="VIX", change_pct=1.83, value_str="16,10", change_str="+%1,83",
                       headline="VIX endeksi +%1,83 yükseldi (16,10).", key="k", tags=["Makro"])


PRODUCERS = {
    "sabah bülteni": lambda: pipeline.run_morning_report(publish_social=True),
    "VİOP": lambda: pipeline.run_viop_report(publish=True),
    "açılış bülteni": lambda: pipeline.run_opening_report(publish_social=True),
    "kapanış bülteni": lambda: pipeline.run_closing_report(publish_social=True),
    "gündem": lambda: pipeline.run_gundem_report("TCMB faiz kararını açıkladı", "### Gelişme\nTCMB politika faizini sabit tuttu.",
                                                 "TCMB politika faizini sabit tuttu."),
    "haftalık sektör": lambda: pipeline.run_sector_report(publish_social=True),
    "emsal/çarpan tablosu": lambda: pipeline.run_peer_report("bankacilik", publish_social=True),
    "küresel makro": lambda: pipeline.run_global_report(publish_social=True),
    "KAP haber": lambda: pipeline.run_news_report(disclosure=DISCLOSURES[0], publish_social=True),
    "makro olay": lambda: pipeline.run_news_report(event=_event(), publish_social=True),
    "haftalık özet": lambda: pipeline.run_weekly_summary(publish_social=True),
    "halka arz analizi": lambda: analysis.analyze_ipo_document("x", company="X A.Ş.", ticker="XXXXX", make_pdf=False),
    "finansal tablo analizi": lambda: analysis.analyze_company_report("x", company="X A.Ş.", period="2026/9"),
}


@pytest.mark.parametrize("name", list(PRODUCERS))
def test_producer_writes_schema_v2_and_is_clean_at_source(name):
    PRODUCERS[name]()
    assert _Store.drafts, f"{name}: rapor üretilmedi"
    for d in _Store.drafts:
        doc = d.to_document()
        assert doc["schemaVersion"] == REPORT_SCHEMA_VERSION, name
        generated = d.body  # birebir blok (facts) ayrı; o kaynak alıntısıdır
        squash = lambda t: re.sub(r"\n{3,}", "\n\n", t).strip()  # noqa: E731 — yalnız boş satır farkı yok sayılır
        assert squash(strip_banned(generated)) == squash(generated), (name, find_banned(generated))
        assert not find_banned(d.summary), (name, d.summary)
        assert not find_banned(d.title) or d.kap, (name, d.title)
        text = normalize(" ".join([d.title, d.summary, generated]))
        hits = [p for p in TEMPLATE_STEERING if p in text]
        assert not hits, (name, hits)
    for post in _Social.posts:
        assert not find_banned(post), (name, post)
        hits = [p for p in TEMPLATE_STEERING if p in normalize(post)]
        assert not hits, (name, hits)


def test_every_publishing_producer_is_covered():
    """Yeni bir ReportDraft üreticisi eklenirse bu test listesine de eklenmeli."""
    import re

    root = Path(pipeline.__file__).parent
    src = (root / "pipeline.py").read_text(encoding="utf-8") + (root / "analysis.py").read_text(encoding="utf-8")
    producers = set(re.findall(r"^def (run_\w+|analyze_\w+)\(", src, re.M))
    covered = {"run_morning_report", "run_viop_report", "run_opening_report", "run_closing_report", "run_gundem_report",
               "run_sector_report", "run_peer_report", "run_global_report", "run_news_report", "run_weekly_summary",
               "analyze_ipo_document", "analyze_company_report"}
    assert producers <= covered, producers - covered
