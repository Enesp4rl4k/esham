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
    extract_amounts,
    find_banned,
    format_amount_tr,
    normalize,
    parse_number_strict,
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
    monkeypatch.setattr(social.SocialPublisher, "post_telegram",
                        lambda self, message, image_path=None: posts.append(message) or True)
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
    assert "500 milyon USD" in doc["body"]
    assert "Tier 2" in news_env["posts"][0]


def test_kontrolmatik_signalling_end_to_end(news_env, monkeypatch):
    """İnceleme B1: 'Sinyalizasyon' başlığı guardrail'a takılıp bildirim kayboluyordu."""
    filing = FILINGS[1]
    slug, files, doc = _run(news_env, monkeypatch, filing, _good_llm(filing[0], filing[2], filing[4]))
    assert slug and "Demiryolu Sinyalizasyon Projesi Sözleşmesi" in doc["body"]
    assert "sinyalizasyon" in doc["body"].lower().split("### bildirim bilgileri")[0]  # LLM özeti korundu
    assert "1,2 milyar TL" in doc["body"]
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


# ---- 5. tutarlar ------------------------------------------------------------------------------------

@pytest.mark.parametrize("text,expected", [
    ("Bağlı ortaklığımız 250,000 USD tutarında sipariş almıştır.", ["250.000 USD"]),
    ("USD 750,000,000 tutarında tahvil ihracı tamamlanmıştır.", ["750 milyon USD"]),
    ("Toplam GBP 20.000.000 kredi kullanılmıştır.", ["20 milyon GBP"]),
    ("Sözleşme bedeli 12,5 milyon EUR'dur.", ["12,5 milyon EUR"]),
    ("Satış bedeli 6.700.000.000 TL olarak tahsil edilmiştir.", ["6,7 milyar TL"]),
    ("Bedel 25,000,000.50 USD.", ["25.000.000,50 USD"]),
    ("Bedel 4.950.000,25 TL.", ["4.950.000,25 TL"]),
    ("İşin bedeli 250 bin TL'dir.", ["250.000 TL"]),
    ("Şirketimiz 85 milyon TL tutarında iş almıştır.", ["85 milyon TL"]),
    ("Ücret ₺1.250.000 olarak belirlendi.", ["1,25 milyon TL"]),
    ("1 TL nominal değerli 100.000 adet pay ortalama 42,10 TL fiyattan geri alınmıştır.", ["42,10 TL"]),
    ("Pay oranı %100, 100%.", []),
    ("Bedel 1,2345 TL.", []),                                   # belirsiz
    ("Bedel 1.234,567.8 TL.", []),                              # tutarsız ayraçlar
    ("Gelir Tablosu (Bin TL)\nHasılat 1.234.567 TL", []),        # tablo birimi → hiç tutar yok
    ("Hasılat Milyon TL\n3.200", []),
    ("Tutar (TL) 11.000.000.000", []),                          # birim parantezde → güvenli eşleşme yok
])
def test_amount_extraction_cases(text, expected):
    assert [a.formatted() for a in extract_amounts(text)] == expected


def test_no_amount_message_is_not_a_false_negative_claim():
    facts = pipeline.__dict__  # noqa: F841
    from esham.ai.analyzer import filing_facts_markdown

    md = filing_facts_markdown("X A.Ş.", "XXXXX", "X A.Ş.: Duyuru", "Duyuru", "Tutar (TL) 11.000.000.000", "1")
    assert NOTE_AMOUNT_MISSING in md and "bulunamadı" not in md


_CURRENCIES = [("TL", "TL"), ("TRY", "TL"), ("USD", "USD"), ("ABD Doları", "USD"), ("EUR", "EUR"),
               ("Avro", "EUR"), ("GBP", "GBP"), ("CHF", "CHF")]


def _fmt_tr(v: float, dec: bool) -> str:
    ip = int(v)
    s = f"{ip:,}".replace(",", ".")
    return s + (f",{int(round((v - ip) * 100)):02d}" if dec else "")


def _fmt_en(v: float, dec: bool) -> str:
    ip = int(v)
    return f"{ip:,}" + (f".{int(round((v - ip) * 100)):02d}" if dec else "")


def test_amount_property_never_wrong_magnitude():
    """Özellik testi: üretilen her tutar ya doğru büyüklükte çıkar ya da hiç çıkmaz; asla yanlış değil."""
    rng = random.Random(20261127)
    extracted = 0
    for _ in range(3000):
        ip = rng.choice([rng.randint(1, 999), rng.randint(1_000, 999_999), rng.randint(1_000_000, 9_999_999_999)])
        dec = rng.random() < 0.3
        value = ip + (rng.randint(1, 99) / 100 if dec else 0)
        style = rng.choice(["tr", "en", "plain"])
        if style == "tr":
            num = _fmt_tr(value, dec)
        elif style == "en":
            num = _fmt_en(value, dec)
        else:
            num = str(ip) + ((("," if rng.random() < .5 else ".") + f"{int(round((value - ip) * 100)):02d}") if dec else "")
        cur, unit = rng.choice(_CURRENCIES)
        amount = f"{cur} {num}" if rng.random() < 0.3 else f"{num} {cur}"
        text = rng.choice([
            f"Şirketimiz {amount} tutarında sözleşme imzalamıştır. Oran %12,5 olarak belirlenmiştir.",
            f"Toplam {amount} bedelle satış tamamlanmıştır.",
            f"Kredi tutarı: {amount}; vade 3 yıl.",
        ])
        got = extract_amounts(text)
        for a in got:
            assert a.unit == unit, (text, a)
            assert abs(a.value - value) < 0.005, (text, a, value)
            assert a.raw in normalize(text)
            assert parse_number_strict(a.raw) * a.scale == pytest.approx(a.value)
        extracted += bool(got)
    assert extracted > 2000  # kesin biçimlerin büyük çoğunluğu gerçekten çıkarılıyor


def test_amount_property_on_real_kap_text():
    """Gerçek KAP fikstürlerinde çıkan her tutar kaynaktaki bir sayının birebir büyüklüğüdür."""
    for f in FIX.glob("kap_*.html"):
        text = BeautifulSoup(f.read_text(encoding="utf-8"), "html.parser").get_text(" ", strip=True)
        for a in extract_amounts(text, limit=50):
            assert a.raw in normalize(text)
            assert parse_number_strict(a.raw) * a.scale == pytest.approx(a.value)


@pytest.mark.parametrize("value,unit,expected", [
    (4_950_000, "TL", "4,95 milyon TL"),
    (4_950_123, "TL", "4.950.123 TL"),
    (4_950_000.5, "TL", "4.950.000,50 TL"),
    (6_712_345_678, "TL", "6.712.345.678 TL"),
    (1_500_000_000, "USD", "1,5 milyar USD"),
    (250_000, "USD", "250.000 USD"),
    (42.1, "TL", "42,10 TL"),
])
def test_format_amount_turkish(value, unit, expected):
    assert format_amount_tr(value, unit) == expected


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
    monkeypatch.setattr(social.SocialPublisher, "post_telegram", lambda self, m, image_path=None: posts.append(m) or True)
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
    got = {r["slug"]: r["summary"] for r in newsletter.latest_reports()}
    assert got == {"a": "X A.Ş.: Duyuru", "b": "Y A.Ş. bildirim yayımladı."}
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
