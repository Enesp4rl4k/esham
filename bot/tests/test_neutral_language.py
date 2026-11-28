"""Tarafsız dil koruması: KAP raporu/kart/Telegram çıktısında yatırım tavsiyesi gibi okunan içerik olmamalı,
ve hiçbir bildirim sessizce kaybolmamalı.

İlkeler (bkz. esham/neutral.py):
- Süzgeç YALNIZ üretilmiş yoruma uygulanır; KAP başlığı ve bildirimden birebir bilgi süzülmez.
- Üretilmiş kısım reddedilirse yalın rapor yayınlanır (başlık aynen, şirket, tarih, tür, KAP bağlantısı).
- Konu etiketi KAP'ın kendi bildirim türüdür; genel türde "KAP bildirimi".
- Tutar yalnız kesin ayrıştırılabiliyorsa gösterilir.
- Normalizasyon + kalıplar tek veri dosyasından; davranış eşitliği ortak vektörlerle (TS de aynı dosyayı koşar).

Testler ağsız ve anahtarsızdır: LLM çağrısı sahte bir istemciyle değiştirilir.
"""
from __future__ import annotations

import json
import random
import re
from pathlib import Path

import pytest
from bs4 import BeautifulSoup

from esham import neutral, pipeline
from esham.ai.analyzer import MarketAIAnalyzer
from esham.ai.client import LlmClient
from esham.guardrails import validate_report, validate_tweet
from esham.neutral import (
    NOTE_AMOUNT_MISSING,
    NOTE_KAP,
    REPORT_SCHEMA_VERSION,
    classify_filing,
    find_banned,
    normalize,
    strip_banned,
)
from esham.publishing import social
from esham.publishing.content_store import ContentStore, ReportDraft
from esham.sources import Disclosure
from esham.sources.kap import pick_ticker
from esham.turkish import tr_upper

ROOT = Path(__file__).resolve().parents[2]
FIX = Path(__file__).parent / "fixtures"
VECTORS = json.loads((ROOT / "web" / "src" / "lib" / "neutral-vectors.json").read_text(encoding="utf-8"))


# ---- 1. ortak davranış vektörleri (web/src/lib/neutral.test.mjs aynı dosyayı koşar) ----------------

@pytest.mark.parametrize("text", VECTORS["block"])
def test_shared_vectors_block(text):
    assert find_banned(text), (text, normalize(text))


@pytest.mark.parametrize("text", VECTORS["keep"])
def test_shared_vectors_keep(text):
    assert not find_banned(text), find_banned(text)


@pytest.mark.parametrize("raw,expected", VECTORS["normalize"])
def test_shared_vectors_normalize(raw, expected):
    assert normalize(raw) == expected


@pytest.mark.parametrize("raw,expected", VECTORS["strip"])
def test_shared_vectors_strip(raw, expected):
    assert strip_banned(raw) == expected


def test_rules_are_single_source():
    """Python kalıpları ve notları web'in okuduğu dosyadan gelir (kopya liste yok)."""
    rules = json.loads((ROOT / "web" / "src" / "lib" / "neutral-rules.json").read_text(encoding="utf-8"))
    assert list(neutral.BANNED_PATTERNS) == rules["patterns"]
    assert NOTE_KAP == rules["notes"]["kap"]
    ts = (ROOT / "web" / "src" / "lib" / "neutral.ts").read_text(encoding="utf-8")
    assert 'from "./neutral-rules.json"' in ts and "BANNED_PATTERNS: readonly string[] = rules.patterns" in ts


# ---- fikstür bildirimler -----------------------------------------------------------------------------

def _garan_buyback_text() -> str:
    html = (FIX / "kap_buyback_garan_1700856.html").read_text(encoding="utf-8")
    return BeautifulSoup(html, "html.parser").get_text(" ", strip=True)


# (title, KAP türü, şirket, kod, metin, beklenen etiket)
FILINGS = [
    ("AKBANK T.A.Ş.: Tier 2 Sermaye Benzeri Borçlanma Aracı İhracı", "Özel Durum Açıklaması (Genel)",
     "AKBANK T.A.Ş.", "AKBNK",
     "Bankamızca 500.000.000 ABD Doları tutarında Tier 2 niteliğinde sermaye benzeri borçlanma aracı ihracı tamamlanmıştır.",
     "KAP bildirimi"),
    ("KONTROLMATİK TEKNOLOJİ A.Ş.: Demiryolu Sinyalizasyon Projesi Sözleşmesi", "Yeni İş İlişkisi",
     "KONTROLMATİK TEKNOLOJİ A.Ş.", "KONTR",
     "Şirketimiz ile TCDD arasında 1,2 milyar TL tutarında demiryolu sinyalizasyon sözleşmesi imzalanmıştır.",
     "Yeni İş İlişkisi"),
    ("TÜPRAŞ A.Ş.: Planlı Bakım Çalışması", "Özel Durum Açıklaması (Genel)", "TÜPRAŞ A.Ş.", "TUPRS",
     "İzmit rafinerisinde katalizör değişimi amacıyla planlı bakım başlatılmıştır. Bakımın 45 gün sürmesi beklenir.",
     "KAP bildirimi"),
    ("X A.Ş.: Kayıtlı Sermaye Tavanı Artırımı", "Esas Sözleşme Tadili", "X A.Ş.", "XXXXX",
     "Kayıtlı sermaye tavanının 5.000.000.000 TL'ye yükseltilmesi için SPK'ya başvurulmuştur.",
     "Esas Sözleşme Tadili"),
    ("BİRLEŞİM MÜHENDİSLİK A.Ş.: Yeni İş İlişkisi", "Özel Durum Açıklaması (Genel)", "BİRLEŞİM MÜHENDİSLİK A.Ş.", "BRLSM",
     "Şirketimiz 85 milyon TL tutarında iklimlendirme işi almıştır.", "KAP bildirimi"),
    ("X A.Ş.: Sürdürülebilirlik Raporu", "Sürdürülebilirlik Raporu", "X A.Ş.", "XXXXX",
     "TSRS kapsamında iklimle ilgili risk ve fırsatlar raporumuz yayımlanmıştır.", "Sürdürülebilirlik Raporu"),
    ("X A.Ş.: Pay Geri Alım", "Payların Geri Alınmasına İlişkin Bildirim", "X A.Ş.", "XXXXX",
     "1 TL nominal değerli 100.000 adet pay ortalama 42,10 TL fiyattan geri alınmıştır.",
     "Payların Geri Alınmasına İlişkin Bildirim"),
    ("X A.Ş.: Eurobond İhracı", "Özel Durum Açıklaması (Genel)", "X A.Ş.", "XXXXX",
     "USD 750,000,000 tutarında tahvil ihracı tamamlanmıştır. Toplam GBP 20.000.000 kredi kullanılmıştır.",
     "KAP bildirimi"),
    ("TÜRKİYE GARANTİ BANKASI A.Ş.: Geri Alınan Paylara İlişkin Bildirim", "Payların Geri Alınmasına İlişkin Bildirim",
     "TÜRKİYE GARANTİ BANKASI A.Ş.", "GARAN", _garan_buyback_text(), "Payların Geri Alınmasına İlişkin Bildirim"),
    # Konusu yapay zekâ olan gerçek bildirim reddedilmez: yayınlanır, Telegram metni oluşur (her kipte).
    ("ASELSAN ELEKTRONİK SANAYİ VE TİCARET A.Ş.: Yapay Zeka Destekli Analiz Platformu İçin Sözleşme İmzalanması",
     "Yeni İş İlişkisi", "ASELSAN ELEKTRONİK SANAYİ VE TİCARET A.Ş.", "ASELS",
     "Yapay zeka destekli analiz platformu geliştirilmesi için sözleşme imzalanmıştır.", "Yeni İş İlişkisi"),
    # KAP'ın resmî başlığı yasaklı kalıp içerse bile AYNEN yayınlanır (olgusal kaynak).
    ("ABC A.Ş.: Mega Sözleşme İmzalanması Hk.", "Yeni İş İlişkisi", "ABC A.Ş.", "ABCDE",
     "Şirketimiz 20.000.000 TL tutarında sözleşme imzalamıştır.", "Yeni İş İlişkisi"),
]
IDS = [f[0][:34] for f in FILINGS]

BAD_LLM_OUTPUT = """## ÖZET
Şirket bildirimi açıkladı; hisse üzerinde kısa vadede pozitif haber akışı etkisi yaratması beklenir.

## BİLDİRİM
**Finansal Sinyal:** Pozitif
- **Ne açıklandı:** Şirket, bildirimde belirtilen işlemi tamamladığını açıkladı.
- **Piyasa Yansıması:** 131,77 TL direnç ve 125,47 TL kritik destek izlenmeli; pivot üstü boğa.
- **Değerlendirme:** TIER-1 (MEGA İŞ ANLAŞMASI), hedef fiyat 150 TL, ilk kâr satışı bölgesi 140 TL.

## TWEET
MEGA İŞ ANLAŞMASI! 🚀 Güçlü AL, hedef  fiyat 150 TL.
"""
ALL_BAD_LLM_OUTPUT = """## ÖZET
Hedef fiyat 150 TL, güçlü AL.

## BİLDİRİM
- Hisse üzerinde pozitif etki bekleniyor; RSI 75.

## TWEET
🚀🚀 Strong buy
"""


def _good_llm(title: str, company: str, raw: str) -> str:
    return f"""## ÖZET
{company}, {title.split(': ', 1)[1]} hakkında bildirim yayımladı.

## BİLDİRİM
- **Ne açıklandı:** {raw[:300]}
- **Taraflar:** Belirtilmemiş

## TWEET
{company}: {raw[:180]}
"""


# ---- 2. uçtan uca: run_news_report ------------------------------------------------------------------

class _FakeState:
    def __init__(self) -> None:
        self.n = 0
        self.seen: set[str] = set()

    def get_daily_post_count(self) -> int:
        return self.n

    def increment_daily_post_count(self) -> None:
        self.n += 1

    def load_seen(self) -> set[str]:
        return set(self.seen)

    def save_seen(self, keys: set[str]) -> None:
        self.seen = set(keys)


@pytest.fixture
def news_env(monkeypatch, tmp_path):
    cards: list = []
    posts: list[str] = []

    class _NoMacro:
        def snapshot(self):
            raise RuntimeError("ağ yok")

    class _FakeKap:
        detail = ""

        def get_detail_text(self, index):
            return _FakeKap.detail

    monkeypatch.delenv("GIT_AUTO_PUSH", raising=False)
    monkeypatch.setattr(pipeline, "GlobalMacroSource", _NoMacro)
    monkeypatch.setattr(pipeline, "KapSource", _FakeKap)
    monkeypatch.setattr(pipeline, "_render_card", lambda spec: cards.append(spec) or None)
    monkeypatch.setattr(pipeline, "ContentStore", lambda: ContentStore(tmp_path / "reports", tmp_path / "cards"))
    monkeypatch.setattr(social, "get_state", lambda: _FakeState())
    # Gönderiler artık giden kutusuna yazılır (doğrudan gönderim yok); yakalama noktası enqueue.
    monkeypatch.setattr(social.SocialPublisher, "enqueue",
                        lambda self, message, image_path=None, **k: posts.append(message) or True)
    assert not pipeline.settings.paused
    return {"cards": cards, "posts": posts, "dir": tmp_path / "reports", "kap": _FakeKap}


def _run(news_env, monkeypatch, filing, llm_output, index="1700000"):
    title, dtype, company, ticker, raw, _label = filing
    monkeypatch.setattr(LlmClient, "generate", lambda self, prompt, **kw: llm_output)
    news_env["kap"].detail = raw
    d = Disclosure(title=title, company=company, date="2026-11-04", disclosure_type=dtype,
                   raw_text=title.split(": ", 1)[-1], ticker=ticker, disclosure_index=index)
    slug = pipeline.run_news_report(disclosure=d, publish_social=True)
    files = list(news_env["dir"].glob("*.json"))
    doc = json.loads(files[0].read_text(encoding="utf-8")) if files else None
    return slug, files, doc


def _generated_part(doc: dict) -> str:
    body = doc["body"]
    return body.split("### Bildirim Bilgileri")[0]


@pytest.mark.parametrize("mode", ["sablon", "iyi-llm", "kotu-llm", "tamamen-kotu-llm"])
@pytest.mark.parametrize("filing", FILINGS, ids=IDS)
def test_every_filing_is_published_never_silently_dropped(news_env, monkeypatch, filing, mode):
    title, dtype, company, ticker, raw, label = filing
    llm = {"sablon": None, "iyi-llm": _good_llm(title, company, raw), "kotu-llm": BAD_LLM_OUTPUT,
           "tamamen-kotu-llm": ALL_BAD_LLM_OUTPUT}[mode]
    slug, files, doc = _run(news_env, monkeypatch, filing, llm)

    assert slug and len(files) == 1 and pipeline.last_news_status() == "published"
    assert doc["title"] == title                                  # başlık AYNEN
    assert f"- **Başlık (KAP):** {title}" in doc["body"]          # birebir blok süzülmedi
    assert f"- **Bildirim türü (KAP):** {dtype}" in doc["body"]
    assert "https://www.kap.org.tr/tr/Bildirim/1700000" in doc["body"]
    assert doc["schemaVersion"] == REPORT_SCHEMA_VERSION
    assert doc["kap"]["url"] == "https://www.kap.org.tr/tr/Bildirim/1700000"
    # Üretilmiş kısım ve özet yasaklı kalıp taşımaz (birebir başlık hariç)
    assert not find_banned(_generated_part(doc)), find_banned(_generated_part(doc))
    assert doc["summary"] == title or not find_banned(doc["summary"])

    (spec,) = news_env["cards"]
    assert spec.kicker == tr_upper(label) and spec.headline == title[:120]
    assert spec.stat_value == "" and spec.metrics == [] and spec.sparkline is None

    (post,) = news_env["posts"]
    assert post.rstrip().endswith(NOTE_KAP)
    masked = post.replace(title, "")
    assert not find_banned(masked), find_banned(masked)


def test_akbank_tier2_end_to_end(news_env, monkeypatch):
    """İnceleme B1: 'Tier 2' başlığı guardrail'a takılıp bildirim kayboluyordu."""
    slug, files, doc = _run(news_env, monkeypatch, FILINGS[0], None)
    assert slug and "Tier 2 Sermaye Benzeri Borçlanma Aracı İhracı" in doc["body"]
    assert "500.000.000" not in doc["body"] and NOTE_AMOUNT_MISSING in doc["body"]  # bildirim gövdesinden rakam yok
    assert "Tier 2" in news_env["posts"][0]


def test_kontrolmatik_signalling_end_to_end(news_env, monkeypatch):
    """İnceleme B1: 'Sinyalizasyon' başlığı guardrail'a takılıp bildirim kayboluyordu."""
    filing = FILINGS[1]
    slug, files, doc = _run(news_env, monkeypatch, filing, _good_llm(filing[0], filing[2], filing[4]))
    assert slug and "Demiryolu Sinyalizasyon Projesi Sözleşmesi" in doc["body"]
    assert "sinyalizasyon" in doc["body"].lower().split("### bildirim bilgileri")[0]  # LLM özeti korundu
    assert NOTE_AMOUNT_MISSING in doc["body"].split("### Bildirim Bilgileri")[1]
    assert "sinyalizasyon" in news_env["posts"][0].lower()


def test_guardrail_rejection_publishes_minimal_report(news_env, monkeypatch, caplog):
    """Üretilmiş metnin tamamı reddedilse bile yalın rapor yayınlanır; 'yayınlandı' logu gerçek yayında."""
    filing = FILINGS[3]
    slug, files, doc = _run(news_env, monkeypatch, filing, ALL_BAD_LLM_OUTPUT)
    assert slug and doc["summary"] == filing[0]
    assert doc["body"].startswith("### Bildirim Bilgileri")
    assert news_env["posts"] and filing[0] in news_env["posts"][0]


def test_duplicate_is_a_decision_and_card_not_rendered(news_env, monkeypatch):
    filing = FILINGS[2]
    _run(news_env, monkeypatch, filing, None)
    news_env["cards"].clear()
    slug, files, _ = _run(news_env, monkeypatch, filing, None)
    assert slug is None and pipeline.last_news_status() == "duplicate"
    assert news_env["cards"] == []  # karar kart çiziminden önce


def test_same_title_different_filings_both_published(news_env, monkeypatch):
    filing = FILINGS[6]
    a, *_ = _run(news_env, monkeypatch, filing, None, index="1")
    b, files, _ = _run(news_env, monkeypatch, filing, None, index="2")
    assert a and b and a != b and len(files) == 2


# ---- 3. news_stream: görüldü işareti yalnız karar sonrası ------------------------------------------

def test_news_stream_marks_seen_only_after_decision(monkeypatch):
    from esham import news_stream as ns

    state = _FakeState()
    d1 = Disclosure("A A.Ş.: Yeni İş İlişkisi", "A A.Ş.", "2026-11-04", "Yeni İş İlişkisi", ticker="AAAAA")
    d2 = Disclosure("B A.Ş.: Yeni İş İlişkisi", "B A.Ş.", "2026-11-04", "Yeni İş İlişkisi", ticker="BBBBB")

    class _Kap:
        def latest_disclosures(self):
            return [d1, d2]

    monkeypatch.setattr(ns, "get_state", lambda: state)
    monkeypatch.setattr(ns, "KapSource", _Kap)
    monkeypatch.setattr(ns, "NewsDetector", lambda: type("D", (), {"scan": lambda self: []})())
    monkeypatch.setattr(ns, "is_significant", lambda d, t: True)
    monkeypatch.setattr(ns, "update_ticker_data", lambda: None)
    outcomes = {"A A.Ş.: Yeni İş İlişkisi": ("error", None), "B A.Ş.: Yeni İş İlişkisi": ("published", "b-slug")}

    def fake_run(disclosure=None, event=None, publish_social=True):
        status, slug = outcomes[disclosure.title]
        pipeline._set_status(status)
        return slug

    monkeypatch.setattr(ns, "run_news_report", fake_run)
    stream = ns.NewsStream()
    stream.check_once(max_publish=5)
    assert any("B A.Ş." in k for k in state.seen)
    assert not any("A A.Ş." in k for k in state.seen)  # hata → yeniden denenecek

    # Sonraki turda A yeniden kuyruğa girer ve başarılı olursa işaretlenir.
    outcomes["A A.Ş.: Yeni İş İlişkisi"] = ("published", "a-slug")
    stream.check_once(max_publish=5)
    assert any("A A.Ş." in k for k in state.seen)


def test_news_stream_leftovers_beyond_max_publish_are_not_lost(monkeypatch):
    from esham import news_stream as ns

    state = _FakeState()
    items = [Disclosure(f"S{i} A.Ş.: Yeni İş İlişkisi", f"S{i} A.Ş.", "2026-11-04", "Yeni İş İlişkisi") for i in range(4)]
    monkeypatch.setattr(ns, "get_state", lambda: state)
    monkeypatch.setattr(ns, "KapSource", lambda: type("K", (), {"latest_disclosures": lambda self: items})())
    monkeypatch.setattr(ns, "NewsDetector", lambda: type("D", (), {"scan": lambda self: []})())
    monkeypatch.setattr(ns, "is_significant", lambda d, t: True)
    monkeypatch.setattr(ns, "update_ticker_data", lambda: None)

    def fake_run(disclosure=None, event=None, publish_social=True):
        pipeline._set_status("published")
        return "slug"

    monkeypatch.setattr(ns, "run_news_report", fake_run)
    ns.NewsStream().check_once(max_publish=2)
    assert len(state.seen) == 2
    ns.NewsStream().check_once(max_publish=2)  # yeni süreç (GitHub Actions --once) kalanları alır
    assert len(state.seen) == 4


# ---- 4. konu etiketi: KAP'ın kendi türü -------------------------------------------------------------

@pytest.mark.parametrize("title,dtype,expected", [
    ("BİRLEŞİM MÜHENDİSLİK A.Ş.: Yeni İş İlişkisi", "Özel Durum Açıklaması (Genel)", "KAP bildirimi"),
    ("BORUSAN BİRLEŞİK BORU FABRİKALARI A.Ş.: 2026 2. Çeyrek Finansal Takvim", "Finansal Rapor Takvimi",
     "Finansal Rapor Takvimi"),
    ("BİRKO BİRLEŞİK KOYUNLULULAR A.Ş.: Fon Kullanım Raporu", "Özel Durum Açıklaması (Genel)", "KAP bildirimi"),
    ("X A.Ş.: Birleşik Arap Emirlikleri'nde Şube Açılışı", "Özel Durum Açıklaması (Genel)", "KAP bildirimi"),
    ("SKY ALP A.Ş.: Sunucu İhtiyaçları Satın Alım İhalesi", "Yeni İş İlişkisi", "Yeni İş İlişkisi"),
    ("X A.Ş.: İştirakimiz MPG'nin Yeni Siparişleri", "Özel Durum Açıklaması (Genel)", "KAP bildirimi"),
    ("X A.Ş.: Kayıtlı Sermaye Tavanı", "Esas Sözleşme Tadili", "Esas Sözleşme Tadili"),
    ("X A.Ş.: Pay Alım Satım Bildirimi", "Pay Alım Satım Bildirimi", "Pay Alım Satım Bildirimi"),
    ("X A.Ş.: Duyuru", "", "KAP bildirimi"),
    ("X A.Ş.: Duyuru", "Duyuru", "KAP bildirimi"),
])
def test_label_comes_from_kap_type_not_title(title, dtype, expected):
    assert classify_filing(title, dtype) == expected


def test_pick_ticker_never_guesses():
    assert pick_ticker("ISATR, ISBTR, ISCTR, ISKUR") == "ISCTR"   # evrende tek eşleşme
    assert pick_ticker("GARAN") == "GARAN"                         # tek kod
    assert pick_ticker("ZZZZA, ZZZZB") == ""                       # evren dışı çok pay grubu → tahmin yok
    assert pick_ticker("") == ""


def test_no_code_company_shows_name_once(news_env, monkeypatch):
    filing = ("ÖRNEK A.Ş.: Yeni İş İlişkisi", "Yeni İş İlişkisi", "ÖRNEK A.Ş.", "", "Sözleşme imzalanmıştır.", "")
    slug, _, doc = _run(news_env, monkeypatch, filing, None)
    assert "- **Şirket:** ÖRNEK A.Ş.\n" in doc["body"] and "(ÖRNEK A.Ş.)" not in doc["body"]
    assert doc["sources"] == ["KAP"] and "" not in doc["tags"]


# ---- 5. tutarlar: rapora hiçbir tutar/rakam taşınmaz ---------------------------------------------------

# Üç inceleme turunun tutar girdileri + üçüncü turun alıntı örnekleri (olumsuzlama kesilmesi, "Şti."/"T.C."
# sonrası bölünme, tek satıra inmiş tablolar). Hiçbirinden olgu bloğuna rakam geçmemeli.
AMOUNT_REGRESSION_INPUTS = [
    "Pay başına brüt 0,125 TL kâr payı ödenecektir.",
    "Sözleşme bedeli 1 250 500 TL",
    "Bedel USD 1 250 500",
    "EUR 2027 vadeli tahvil ihraç edilmiştir.",
    "Net dönem zararı -5.000.000 TL olmuştur.",
    "Bağlı ortaklığımız 250,000 USD tutarında sipariş almıştır.",
    "Sözleşme bedeli 5 milyon TL'dir. Ancak sözleşme henüz imzalanmamıştır.",
    "İhaleye 5 milyon TL teklif verilmiştir. İhale kazanılamamıştır.",
    "X Ltd. Şti. ile 12 milyon TL tutarında sözleşme imzalanmıştır.",
    "T.C. Ziraat Bankası A.Ş. ile 300 milyon TL kredi.",
    "Hasılat (Bin TL) 2025 1.234.567 2024 987.654 Net Kâr 2025 345.678",
    "Sermaye 1.000.000.000 TL Kayıtlı Sermaye Tavanı 5.000.000.000 TL Bildirim İçeriği Şirketimiz 30 milyon TL sipariş almıştır.",
]


def _facts_digits(md: str, title: str, index: str) -> str:
    """Olgu bloğundaki rakamlar — başlık (KAP'ın kendi metni), tarih ve bildirim numarası hariç."""
    rest = md.replace(title, "").replace(f"#{index}", "").replace(f"/Bildirim/{index}", "")
    return "".join(re.findall(r"\d", rest))


@pytest.mark.parametrize("text", AMOUNT_REGRESSION_INPUTS + [_garan_buyback_text()] + [
    BeautifulSoup((FIX / f).read_text(encoding="utf-8"), "html.parser").get_text(" ", strip=True)
    for f in ("kap_div_aygaz_teklif_1700009.html", "kap_div_avod_dagitim_yok_1700335.html",
              "kap_div_yigit_kesinlesen_1700660.html", "kap_buyback_kzgyo_1700896.html")
])
def test_facts_block_carries_no_number_from_filing_body(text):
    from esham.ai.analyzer import filing_facts_markdown

    md = filing_facts_markdown("X A.Ş.", "XXXXX", "X A.Ş.: Bildirim", "Özel Durum Açıklaması (Genel)", text, "1700000")
    assert _facts_digits(md, "X A.Ş.: Bildirim", "1700000") == ""
    assert f"- **Tutar:** {NOTE_AMOUNT_MISSING}" in md
    assert "https://www.kap.org.tr/tr/Bildirim/1700000" in md


@pytest.mark.parametrize("text", AMOUNT_REGRESSION_INPUTS)
def test_template_report_has_no_number_from_filing_body(news_env, monkeypatch, text):
    filing = ("X A.Ş.: Bildirim", "Özel Durum Açıklaması (Genel)", "X A.Ş.", "XXXXX", text, "KAP bildirimi")
    slug, _, doc = _run(news_env, monkeypatch, filing, None, index="1700000")
    body = doc["body"].replace(filing[0], "").replace("#1700000", "").replace("/Bildirim/1700000", "")
    body = body.replace("2026-11-04", "")  # bildirim tarihi
    assert re.findall(r"\d", body) == [], body
    (post,) = news_env["posts"]
    assert not re.findall(r"\d", post.replace(filing[0], "").split("http")[0])


def test_no_amount_code_path_remains():
    """Bildirim tutarını ayrıştıran, biçimlendiren ya da alıntılayan kod yolu kalmamalı."""
    src = (ROOT / "bot" / "esham" / "neutral.py").read_text(encoding="utf-8")
    for gone in ("def extract_amounts", "def format_amount_tr", "def parse_number_strict", "def amount_quotes"):
        assert gone not in src
    an = (ROOT / "bot" / "esham" / "ai" / "analyzer.py").read_text(encoding="utf-8")
    assert "amount_quotes" not in an and "extract_amounts" not in an


# ---- 6. LLM prompt + son süzgeç ---------------------------------------------------------------------

def test_llm_prompt_is_neutral_and_output_is_filtered(monkeypatch):
    prompts: list[str] = []
    monkeypatch.setattr(LlmClient, "generate", lambda self, prompt, **kw: prompts.append(prompt) or BAD_LLM_OUTPUT)
    title, dtype, company, ticker, raw, _ = FILINGS[1]
    body, summary, tweet = MarketAIAnalyzer().generate_news_analysis(
        title=title, disclosure_type=dtype, company=company, ticker=ticker, raw_text=raw,
        macro_context="XU100 %2 yükseldi; boğa piyasası sürüyor",
    )
    for t in (body, summary, tweet):
        assert not find_banned(t), t
    assert "Şirket, bildirimde belirtilen işlemi tamamladığını açıkladı." in body
    assert "hedef fiyat" in prompts[0].lower() and "YAZMA" in prompts[0]
    assert "boğa piyasası" not in prompts[0]


def test_template_produces_no_commentary():
    body, summary, tweet = MarketAIAnalyzer._template_news_analysis(
        FILINGS[0][0], FILINGS[0][1], FILINGS[0][2], FILINGS[0][3], False, raw_text=FILINGS[0][4])
    assert body == "" and summary == FILINGS[0][0] and tweet == FILINGS[0][0]


# ---- 7. guardrail, gönderi, depo, bülten, PDF -------------------------------------------------------

def test_guardrails_check_generated_text_only():
    assert validate_report("Başlık", "Özet", "Hisse üzerinde pozitif haber akışı etkisi yaratması beklenir.")
    assert validate_tweet("GARAN için AL sinyali")
    assert not validate_report("ABC A.Ş.: Mega Sözleşme İmzalanması", "", "")  # KAP başlığı alıntıdır


def test_broadcast_keeps_verbatim_title_and_filters_rest(monkeypatch):
    posts: list[str] = []
    monkeypatch.setattr(social, "get_state", lambda: _FakeState())
    monkeypatch.setattr(social.SocialPublisher, "enqueue", lambda self, m, image_path=None, **k: posts.append(m) or True)
    title = "ABC A.Ş.: Mega Sözleşme İmzalanması Hk."
    social.SocialPublisher().broadcast(f"{title}\nHedef fiyat 150 TL\nhttps://esham.pages.dev/rapor/x",
                                       disclaimer=NOTE_KAP, verbatim=[title])
    (p,) = posts
    assert title in p and "Hedef fiyat" not in p and p.endswith(NOTE_KAP)


def test_content_store_filters_generated_but_not_facts(tmp_path, monkeypatch):
    monkeypatch.delenv("GIT_AUTO_PUSH", raising=False)
    draft = ReportDraft(
        title="X A.Ş.: Tier 2 Sinyalizasyon", category="bist",
        summary="🔥 MEGA SÖZLEŞME | X A.Ş.: Tier 2 Sinyalizasyon",
        body=BAD_LLM_OUTPUT, tags=["Mega Sözleşme", "XXXXX", "KAP"],
        facts="### Bildirim Bilgileri\n- **Başlık (KAP):** X A.Ş.: Tier 2 Sinyalizasyon",
        fallback_summary="X A.Ş.: Tier 2 Sinyalizasyon", schema_version=2,
    )
    store = ContentStore(tmp_path / "r", tmp_path / "c")
    path = store.publish(draft)
    assert path is not None and store.last_status == "published"
    doc = json.loads(path.read_text(encoding="utf-8"))
    assert doc["summary"] == "X A.Ş.: Tier 2 Sinyalizasyon"
    assert doc["tags"] == ["XXXXX", "KAP"]
    assert doc["body"].endswith("- **Başlık (KAP):** X A.Ş.: Tier 2 Sinyalizasyon")
    assert not find_banned(_generated_part(doc))


def test_newsletter_uses_verbatim_title_for_legacy_kap(tmp_path, monkeypatch):
    from esham import newsletter

    legacy = {"slug": "a", "title": "X A.Ş.: Duyuru", "summary": "MEGA SÖZLEŞME | hisseye talep artabilir",
              "sources": ["KAP"], "publishedAt": "2026-11-01T00:00:00Z", "category": "bist"}
    new = {"slug": "b", "title": "Y A.Ş.: Duyuru", "summary": "Y A.Ş. bildirim yayımladı.", "sources": ["KAP"],
           "schemaVersion": 2, "publishedAt": "2026-11-02T00:00:00Z", "category": "bist"}
    (tmp_path / "2026-11-01-a.json").write_text(json.dumps(legacy, ensure_ascii=False), encoding="utf-8")
    (tmp_path / "2026-11-02-b.json").write_text(json.dumps(new, ensure_ascii=False), encoding="utf-8")
    import dataclasses

    monkeypatch.setattr(newsletter, "settings",
                        dataclasses.replace(newsletter.settings, content_dir=tmp_path, newsletter_limit=10))
    got = {r["slug"]: (r["title"], r["summary"]) for r in newsletter.latest_reports()}
    assert got == {"a": ("X A.Ş.: Duyuru", "KAP bildirimi — eski kayıt."), "b": ("Y A.Ş.: Duyuru", "Y A.Ş. bildirim yayımladı.")}
    _subject, html_body, text_body = newsletter.build_digest(newsletter.latest_reports())
    assert neutral.NOTE_GENERIC in text_body and "yapay zeka tarafından üretilir" not in html_body


def test_ipo_pdf_filters_generated_fields(tmp_path):
    from esham.publishing.ipo_pdf import IpoPdfGenerator

    html = IpoPdfGenerator(tmp_path).build_html({
        "company_name": "X A.Ş.", "ticker": "XXXXX", "strengths": ["Güçlü AL", "Kapasite artırımı"],
        "verdict": "Halka arz cazip. Fon kullanımı belgede yer alıyor.",
    })
    assert "Güçlü AL" not in html and "cazip" not in html.lower()
    assert "Kapasite artırımı" in html and neutral.NOTE_GENERIC in html


def test_one_to_ten_scores_not_rendered_on_site():
    """1-10 'radar puanı' modülü kapsam dışı; yalnızca sitede görünmediğini doğrula."""
    web = ROOT / "web" / "src"
    hits = [p for p in web.rglob("*.tsx") if "radar_scores" in p.read_text(encoding="utf-8")]
    assert hits == []
    assert not (ROOT / "web" / "public" / "data" / "bist-quant-valuation.json").exists()


# ---- 8. kopya kontrolü KAP numarasına bağlı, yeniden deneme sınırı -----------------------------------

def test_duplicate_check_uses_kap_index_across_days(tmp_path, monkeypatch):
    from datetime import datetime, timedelta, timezone

    monkeypatch.delenv("GIT_AUTO_PUSH", raising=False)
    store = ContentStore(tmp_path / "r", tmp_path / "c")

    def draft(day):
        return ReportDraft(title="X A.Ş.: Duyuru", category="bist", summary="X A.Ş.: Duyuru", body="",
                           facts="### Bildirim Bilgileri", fallback_summary="X A.Ş.: Duyuru",
                           kap={"index": "1712345"}, slug="x-a-s-duyuru-1712345",
                           published_at=datetime(2026, 11, 27, tzinfo=timezone.utc) + timedelta(days=day))

    assert store.publish(draft(0)) is not None
    assert store.publish(draft(1)) is None and store.last_status == "duplicate"  # ertesi gün yeniden deneme


def test_retry_cap_marks_seen_after_limit_and_logs(monkeypatch, caplog):
    from esham import news_stream as ns

    state = _FakeState()
    d = Disclosure("Z A.Ş.: Yeni İş İlişkisi", "Z A.Ş.", "2026-11-04", "Yeni İş İlişkisi", ticker="ZZZZZ")
    monkeypatch.setattr(ns, "get_state", lambda: state)
    monkeypatch.setattr(ns, "KapSource", lambda: type("K", (), {"latest_disclosures": lambda self: [d]})())
    monkeypatch.setattr(ns, "NewsDetector", lambda: type("D", (), {"scan": lambda self: []})())
    monkeypatch.setattr(ns, "is_significant", lambda d, t: True)
    monkeypatch.setattr(ns, "update_ticker_data", lambda: None)
    calls = []

    def fake_run(disclosure=None, event=None, publish_social=True):
        calls.append(1)
        pipeline._set_status("error")
        return None

    monkeypatch.setattr(ns, "run_news_report", fake_run)
    stream = ns.NewsStream()
    for _ in range(ns.MAX_PUBLISH_ATTEMPTS + 2):
        stream.check_once(max_publish=5)
    assert len(calls) == ns.MAX_PUBLISH_ATTEMPTS               # sınırdan sonra yeniden denenmez
    assert any("Z A.Ş." in k for k in state.seen)
    assert any("deneme sınırı aşıldı" in r.message for r in caplog.records)


# ---- 9. eski kayıt görünümü: web ile ortak vektörler, bülten aynı kararı kullanır ------------------------

@pytest.mark.parametrize("doc,title,summary", VECTORS["legacy"], ids=[v[0]["title"][:30] for v in VECTORS["legacy"]])
def test_shared_vectors_legacy_title(doc, title, summary):
    from esham.neutral import legacy_summary, legacy_title

    assert legacy_title(doc) == title and legacy_summary(doc) == summary


def test_newsletter_legacy_non_kap_uses_neutral_title(tmp_path, monkeypatch):
    import dataclasses

    from esham import newsletter

    old = {"slug": "c", "title": "Altın +1,49% yükseldi (4.145). Güvenli liman talebi artıyor.",
           "summary": "Altın yükseldi; piyasa fiyatlamaları üzerindeki yansımalarıyla izleniyor.",
           "sources": ["Yahoo Finance"], "publishedAt": "2026-08-01T12:00:00Z", "category": "global"}
    (tmp_path / "2026-08-01-c.json").write_text(json.dumps(old, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(newsletter, "settings",
                        dataclasses.replace(newsletter.settings, content_dir=tmp_path, newsletter_limit=10))
    (r,) = newsletter.latest_reports()
    assert r["title"] == "Küresel piyasa notu — 1 Ağustos 2026"
    assert r["summary"] == "Eski kayıt; içerik gösterilmiyor."
    _s, html_body, text_body = newsletter.build_digest([r])
    assert "Güvenli liman" not in html_body + text_body and "izleniyor" not in html_body + text_body

@pytest.mark.parametrize("docs,expected", VECTORS["disambiguate"])
def test_shared_vectors_disambiguate(docs, expected):
    from esham.neutral import disambiguate_legacy_titles

    out = disambiguate_legacy_titles([{**d, "title_derived": d["derived"]} for d in docs])
    assert [d["title"] for d in out] == expected


def test_newsletter_disambiguates_kap_sourced_derived_titles(tmp_path, monkeypatch):
    import dataclasses

    from esham import newsletter

    for n, hhmm in enumerate(("10:05:00", "11:30:00")):
        old = {"slug": f"h{n}", "title": f"Firma{n} A.Ş. Halka Arz Analizi", "summary": "yorum",
               "sources": ["KAP", "İzahname"], "publishedAt": f"2026-07-07T{hhmm}Z", "category": "ipo"}
        (tmp_path / f"2026-07-07-h{n}.json").write_text(json.dumps(old, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(newsletter, "settings",
                        dataclasses.replace(newsletter.settings, content_dir=tmp_path, newsletter_limit=10))
    titles = sorted(r["title"] for r in newsletter.latest_reports())
    assert titles == ["Halka arz belgesi özeti — 7 Temmuz 2026 · 13:05", "Halka arz belgesi özeti — 7 Temmuz 2026 · 14:30"]

