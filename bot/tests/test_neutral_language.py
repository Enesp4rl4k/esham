"""Tarafsız dil koruması: KAP raporu/kart/Telegram çıktısında yatırım tavsiyesi gibi okunan içerik olmamalı.

SPK mevzuatına göre yatırım danışmanlığı yalnızca yetkili kurumlarca yapılabilir. Esham'ın çıktısı bir
KAP bildiriminin NE SÖYLEDİĞİNİN özetidir; al/sat sinyali, hedef fiyat, destek/direnç, kâr satışı/tepki
alım bölgesi, boğa/ayı, "pozitif sinyal", fiyat/haber akışı etkisi tahmini ve "MEGA" gibi etiketler içermez.

Testler ağsız ve anahtarsızdır: LLM çağrısı sahte bir istemciyle değiştirilir.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from bs4 import BeautifulSoup

from esham import neutral, pipeline
from esham.ai.analyzer import MarketAIAnalyzer
from esham.ai.client import LlmClient
from esham.guardrails import validate_report, validate_tweet
from esham.neutral import (
    BANNED_PATTERNS,
    DISCLAIMER_KAP,
    classify_filing,
    extract_amounts,
    find_banned,
    fold,
    format_amount_tr,
    parse_number_tr,
    strip_banned,
)
from esham.publishing import social
from esham.publishing.content_store import ContentStore
from esham.sources import Disclosure
from esham.sources.kap import pick_ticker
from esham.turkish import tr_upper

ROOT = Path(__file__).resolve().parents[2]
FIX = Path(__file__).parent / "fixtures"

# Testin KENDİ yasaklı ifade listesi (insan okunur, modülden bağımsız). Katlanmış (büyük/küçük harf ve
# aksan duyarsız) alt dize olarak aranır; modüldeki kalıplardan daha katıdır (ör. çıplak "destek", "mega").
GUARD_PHRASES = [
    "Finansal Sinyal", "sinyal", "Pozitif (", "Negatif (", "pozitif haber akışı", "etkisi yaratması beklenir",
    "İlk Kar Satışı", "Kâr satışı", "Tepki Alım", "Alım Tabanı", "Destek", "Direnç", "Pivot", "Fibonacci",
    "RSI", "Boğa", "Ayı Senaryo", "Boğa / Ayı", "Hedef Fiyat", "Adil Değer", "MEGA", "TIER-1", "Key Level", "Teknik Eşik",
    "Aşırı Alım", "Aşırı Satım", "katalizör", "Hisse üzerinde", "Piyasa Yansıması", "AL sinyali",
    "Temel Finansal Çarpanlar", "Ciro Etki Çarpanı", "İçsel İşlem", "insider trading",
]


def _guard_hits(text: str) -> list[str]:
    """Kelime başında eşleşen koruma ifadeleri ("rsi" → "karşılık" içinde sayılmaz, "sinyal" → "sinyali" sayılır)."""
    f = fold(text)
    return [p for p in GUARD_PHRASES if re.search(r"(?<![a-z0-9])" + re.escape(fold(p)), f)]


def _garan_buyback_text() -> str:
    html = (FIX / "kap_buyback_garan_1700856.html").read_text(encoding="utf-8")
    return BeautifulSoup(html, "html.parser").get_text(" ", strip=True)


# (title, disclosure_type, company, ticker, raw_text, beklenen konu)
FIXTURE_FILINGS = [
    (
        "TÜRKİYE İŞ BANKASI A.Ş.: Yurt İçinde Sermaye Benzeri Tahvil İhracına İlişkin SPK Başvurusu",
        "Özel Durum Açıklaması (Genel)", "TÜRKİYE İŞ BANKASI A.Ş.", "ISCTR",
        "Bankamızca yurt içinde 30 milyar TL'ye kadar sermaye benzeri tahvil ihracı için SPK'ya başvurulmuştur.",
        "Borçlanma aracı ihracı",
    ),
    (
        "TÜRKİYE GARANTİ BANKASI A.Ş.: İştirak satışının tamamlanması",
        "Özel Durum Açıklaması (Genel)", "TÜRKİYE GARANTİ BANKASI A.Ş.", "GARAN",
        "İştirakimizin %100 payının satışına ilişkin pay alım satım sözleşmesi kapsamında devir işlemleri "
        "tamamlanmış olup satış bedeli 6.700.000.000 TL olarak tahsil edilmiştir.",
        "Pay / iştirak alım-satımı",
    ),
    (
        "ASELSAN ELEKTRONİK SANAYİ VE TİCARET A.Ş.: Sözleşme İmzalanması",
        "Yeni İş İlişkisi", "ASELSAN ELEKTRONİK SANAYİ VE TİCARET A.Ş.", "ASELS",
        "Şirketimiz ile yurt dışı bir müşteri arasında toplam 1,5 milyar USD tutarında sözleşme imzalanmıştır. "
        "Teslimatların 2027-2029 yıllarında yapılması planlanmaktadır.",
        "Sözleşme / iş ilişkisi",
    ),
    (
        "TÜRKİYE GARANTİ BANKASI A.Ş.: Geri Alınan Paylara İlişkin Bildirim",
        "Pay Geri Alım Bildirimi", "TÜRKİYE GARANTİ BANKASI A.Ş.", "GARAN",
        _garan_buyback_text(),
        "Pay geri alımı",
    ),
    (
        "AYGAZ A.Ş.: Kar Payı Dağıtım İşlemlerine İlişkin Bildirim",
        "Kar Payı Dağıtım İşlemlerine İlişkin Bildirim", "AYGAZ A.Ş.", "AYGAZ",
        "Yönetim kurulumuz pay başına brüt 4,65 TL nakit kâr payı dağıtılmasını genel kurula önermiştir.",
        "Kâr payı",
    ),
    (
        "Borsa İstanbul: İşleme Açılan Temerrüt Sırası",
        "Duyuru", "Borsa İstanbul", "XYZAB",
        "Takasbank temerrüt takası çerçevesinde ihale usulü ile satış yapılacaktır.",
        "Temerrüt bildirimi",
    ),
    (
        "DEMO HOLDİNG A.Ş.: Pay Alım Satım Bildirimi",
        "Pay Alım Satım Bildirimi", "DEMO HOLDİNG A.Ş.", "DEMOH",
        "Yönetim kurulu üyemiz 12.11.2026 tarihinde 150.000 adet payı 42,10 TL fiyattan satın almıştır.",
        "Pay alım satım bildirimi",
    ),
]

# Eski şablonun ve "sinyal" üreten bir LLM'in tipik çıktısı — süzgecin yakalaması gereken içerik.
BAD_LLM_OUTPUT = """## ÖZET
Şirket bildirimi açıkladı; hisse üzerinde kısa vadede pozitif haber akışı etkisi yaratması beklenir.

## BİLDİRİM
**Finansal Sinyal:** Pozitif
- **Ne açıklandı:** Şirket, bildirimde belirtilen işlemi tamamladığını açıkladı.
- **Piyasa Yansıması:** 131,77 TL direnç ve 125,47 TL kritik destek izlenmeli; pivot üstü boğa.
- **Tutar / oran:** Bildirimde belirtildiği şekliyle.
- **Değerlendirme:** TIER-1 (MEGA İŞ ANLAŞMASI), hedef fiyat 150 TL, ilk kâr satışı bölgesi 140 TL.

| Metrik | Seviye | Teknik Anlam / Sinyal |
| :--- | :--- | :--- |
| **Kritik Destek** | 125,47 TL | Olası Tepki Alım Tabanı |

## TWEET
MEGA İŞ ANLAŞMASI! Boğa senaryosunda AL sinyali, hedef fiyat 150 TL.
"""


# ---- yasaklı kalıp listesi ----------------------------------------------------------------

@pytest.mark.parametrize("text", [
    "Finansal Sinyal: Pozitif", "FİNANSAL SİNYAL", "finansal sinyal", "Fınansal Sınyal",
    "Pivot Üstü: Boğa / Altı: Ayı", "PIVOT ÜSTÜ: BOĞA", "boga",
    "İlk Kar Satışı Bölgesi", "İLK KÂR SATIŞI", "ilk kar satisi",
    "Olası Tepki Alım Tabanı", "OLASI TEPKİ ALIM TABANI",
    "Kritik Direnç (R1 / 20G)", "KRİTİK DİRENÇ", "kritik direnc",
    "Hisse üzerinde kısa vadede pozitif haber akışı etkisi yaratması beklenir.",
    "Stratejik Sınıf: TIER-1 (MEGA İŞ ANLAŞMASI)", "Mega Sözleşme", "MEGA SÖZLEŞME",
    "Hedef fiyat 150 TL", "14G RSI 72", "Aşırı Alım", "Yükseliş potansiyeli %30",
    "Ayı senaryosu", "AL sinyali geldi", "alım fırsatı", "tavsiye ederim",
])
def test_banned_phrases_detected_case_and_diacritic_insensitive(text):
    assert find_banned(text), text


@pytest.mark.parametrize("text", [
    DISCLAIMER_KAP,
    neutral.DISCLAIMER_GENERIC,
    "Kasım ayı içinde ödenecektir.",
    "Satış bedeli şirketin nakit varlıklarını destekler.",
    "MEGA POLİETİLEN TEKNOLOJİ A.Ş.: Pay Alım Satım Bildirimi",
    "Nominal değerin üzerinde primli satış yapılacaktır.",
    "İskontolu finansman bonosu ihraç edilecektir.",
    "Pay başına brüt 4,65 TL nakit kâr payı dağıtılacaktır.",
    "Bankamızca 30 milyar TL'ye kadar tahvil ihracı için SPK'ya başvurulmuştur.",
    "TMO alım tabanı 12,50 TL/kg olarak açıklandı.",
    "Sıra, sektördeki 12 hisse üzerinden hesaplanır.",
])
def test_factual_filing_language_is_not_banned(text):
    assert not find_banned(text), find_banned(text)


def test_web_display_filter_uses_same_pattern_list():
    """Web, eski raporları görüntüleme anında aynı listeyle temizler; iki liste ayrışmamalı."""
    src = (ROOT / "web" / "src" / "lib" / "neutral.ts").read_text(encoding="utf-8")
    m = re.search(r"export const BANNED_PATTERNS: readonly string\[\] = (\[.*?\]);", src, re.S)
    assert m, "web/src/lib/neutral.ts içinde BANNED_PATTERNS bulunamadı"
    assert json.loads(m.group(1)) == list(BANNED_PATTERNS)


# ---- deterministik süzgeç ------------------------------------------------------------------

def test_strip_banned_removes_sections_rows_and_sentences():
    out = strip_banned(BAD_LLM_OUTPUT)
    assert not find_banned(out), find_banned(out)
    assert not _guard_hits(out), _guard_hits(out)
    assert "Şirket, bildirimde belirtilen işlemi tamamladığını açıkladı." in out
    assert "| Metrik |" not in out  # gövde satırı kalmayan tablo başlığıyla birlikte gider


def test_strip_banned_cleans_legacy_report_body():
    """Eski bir KAP raporu (İş Bankası tahvil başvurusu) gövdesi: sinyal, çarpanlar ve teknik seviyeler gider."""
    doc = json.loads((ROOT / "web" / "content" / "reports" /
                      "2026-11-04-turkiye-is-bankasi-a-s-yurt-icinde-sermaye-benzeri-tahvil-ihracina-iliskin-spk-basvurusu.json"
                      ).read_text(encoding="utf-8"))
    assert find_banned(doc["body"])  # eski içerik gerçekten sorunlu
    out = strip_banned(doc["body"])
    assert not find_banned(out)
    assert "4950000" not in out and "Sözleşme Tutarı" not in out
    assert "Hızlı Bakış" in out


# ---- üreticiler: KAP bildirimi özetleri -----------------------------------------------------

def _assert_neutral(body: str, summary: str, tweet: str) -> None:
    for name, text in (("body", body), ("summary", summary), ("tweet", tweet)):
        assert not find_banned(text), (name, find_banned(text), text)
        assert not _guard_hits(text), (name, _guard_hits(text), text)


@pytest.mark.parametrize("filing", FIXTURE_FILINGS, ids=[f[3] + "-" + f[5] for f in FIXTURE_FILINGS])
def test_template_generator_is_neutral_for_fixture_filings(filing):
    title, dtype, company, ticker, raw, topic = filing
    body, summary, tweet = MarketAIAnalyzer._template_news_analysis(
        title, dtype, company, ticker, False, raw_text=raw, disclosure_index="1700856",
    )
    _assert_neutral(body, summary, tweet)
    assert f"**Konu:** {topic}" in body
    assert "https://www.kap.org.tr/tr/Bildirim/1700856" in body


@pytest.mark.parametrize("filing", FIXTURE_FILINGS, ids=[f[3] + "-" + f[5] for f in FIXTURE_FILINGS])
def test_llm_generator_output_is_post_filtered(monkeypatch, filing):
    """LLM kurala uymayıp sinyal/seviye yazsa bile yayına giden metin temizdir (gerçek LLM çağrısı yok)."""
    prompts: list[str] = []

    def fake_generate(self, prompt, **kwargs):
        prompts.append(prompt)
        return BAD_LLM_OUTPUT

    monkeypatch.setattr(LlmClient, "generate", fake_generate)
    title, dtype, company, ticker, raw, _topic = filing
    body, summary, tweet = MarketAIAnalyzer().generate_news_analysis(
        title=title, disclosure_type=dtype, company=company, ticker=ticker, raw_text=raw,
        macro_context="XU100 %2 yükseldi; boğa piyasası sürüyor",
    )
    _assert_neutral(body, summary, tweet)
    assert "### Bildirim Bilgileri" in body
    # Prompt tarafsızlık kurallarını içerir ve piyasa bağlamını bildirim özetine taşımaz.
    assert "hedef fiyat" in prompts[0].lower() and "YAZMA" in prompts[0]
    assert "Finansal Sinyal" not in prompts[0]
    assert "boğa piyasası" not in prompts[0]


def test_sector_movement_text_is_data_only():
    body, summary, tweet = MarketAIAnalyzer.generate_sector_movement_analysis("Bankacılık", -1.234, "x")
    _assert_neutral(body, summary, tweet)
    assert "%-1,23" in body


# ---- uçtan uca: run_news_report (rapor JSON + kart + Telegram) ------------------------------

class _FakeState:
    def __init__(self) -> None:
        self.n = 0

    def get_daily_post_count(self) -> int:
        return self.n

    def increment_daily_post_count(self) -> None:
        self.n += 1


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


@pytest.mark.parametrize("llm_output", [None, BAD_LLM_OUTPUT], ids=["sablon", "kotu-llm"])
@pytest.mark.parametrize("filing", FIXTURE_FILINGS, ids=[f[3] + "-" + f[5] for f in FIXTURE_FILINGS])
def test_run_news_report_outputs_are_neutral(news_env, monkeypatch, filing, llm_output):
    title, dtype, company, ticker, raw, topic = filing
    monkeypatch.setattr(LlmClient, "generate", lambda self, prompt, **kw: llm_output)
    news_env["kap"].detail = raw
    d = Disclosure(title=title, company=company, date="2026-11-04", disclosure_type=dtype,
                   raw_text=title.split(": ", 1)[-1], ticker=ticker, disclosure_index="1700000",
                   is_insider="alım satım" in dtype.lower() or "geri alım" in dtype.lower())

    slug = pipeline.run_news_report(disclosure=d, publish_social=True)
    assert slug

    (report_file,) = list(news_env["dir"].glob("*.json"))
    doc = json.loads(report_file.read_text(encoding="utf-8"))
    _assert_neutral(doc["body"], doc["summary"], " ".join(doc["tags"]))
    assert not any(find_banned(t) for t in doc["tags"])

    (spec,) = news_env["cards"]
    assert spec.kicker == tr_upper(topic)
    assert not find_banned(spec.kicker) and "MEGA" not in spec.kicker and "İÇSEL" not in spec.kicker
    # Manşet rakamı/fiyat/RSI/destek çipi yok: bildirimden anlamı bilinmeyen sayı karta basılmaz.
    assert spec.stat_value == "" and spec.stat_change == "" and spec.metrics == [] and spec.sparkline is None

    (post,) = news_env["posts"]
    assert post.rstrip().endswith(DISCLAIMER_KAP)
    assert not find_banned(post) and not _guard_hits(post)


def test_garanti_subsidiary_sale_is_not_labelled_mega_deal(news_env, monkeypatch):
    """Bildirildi: Garanti iştirak satışı kartında 'MEGA İŞ ANLAŞMASI' yazıyordu."""
    monkeypatch.setattr(LlmClient, "generate", lambda self, prompt, **kw: None)
    title, dtype, company, ticker, raw, _ = FIXTURE_FILINGS[1]
    news_env["kap"].detail = raw
    pipeline.run_news_report(disclosure=Disclosure(title, company, "2026-11-03", dtype, ticker=ticker,
                                                   disclosure_index="1"), publish_social=False)
    (spec,) = news_env["cards"]
    assert spec.kicker == "PAY / İŞTİRAK ALIM-SATIMI"
    doc = json.loads(next(news_env["dir"].glob("*.json")).read_text(encoding="utf-8"))
    assert "Mega" not in json.dumps(doc, ensure_ascii=False)
    assert "6,7 milyar TL" in doc["body"]  # tutar bildirimden, birimiyle, Türkçe biçimde


def test_is_bank_bond_card_has_no_price_headline(news_env, monkeypatch):
    """Bildirildi: İş Bankası tahvil başvurusu kartında '4950000.00 TL' (ISATR hisse fiyatı) vardı."""
    monkeypatch.setattr(LlmClient, "generate", lambda self, prompt, **kw: None)
    title, dtype, company, ticker, raw, _ = FIXTURE_FILINGS[0]
    news_env["kap"].detail = raw
    pipeline.run_news_report(disclosure=Disclosure(title, company, "2026-11-04", dtype, ticker=ticker,
                                                   disclosure_index="2"), publish_social=False)
    (spec,) = news_env["cards"]
    assert spec.stat_value == "" and spec.kicker == "BORÇLANMA ARACI İHRACI"
    doc = json.loads(next(news_env["dir"].glob("*.json")).read_text(encoding="utf-8"))
    assert "4950000" not in doc["body"] and "30 milyar TL" in doc["body"]


# ---- etiketleme ve tutarlar --------------------------------------------------------------

def test_pick_ticker_prefers_traded_share_class():
    assert pick_ticker("ISATR, ISBTR, ISCTR, ISKUR") == "ISCTR"
    assert pick_ticker("GARAN") == "GARAN"
    assert pick_ticker("ZZZZA, ZZZZB") == "ZZZZA"
    assert pick_ticker("") == ""


@pytest.mark.parametrize("title,dtype,expected", [
    ("TÜRKİYE GARANTİ BANKASI A.Ş.: İştirak satışının tamamlanması", "Özel Durum Açıklaması (Genel)",
     "Pay / iştirak alım-satımı"),
    ("TÜRKİYE İŞ BANKASI A.Ş.: Yurt İçinde Sermaye Benzeri Tahvil İhracına İlişkin SPK Başvurusu", "ÖDA",
     "Borçlanma aracı ihracı"),
    ("X A.Ş.: Geri Alınan Paylara İlişkin Bildirim", "Pay Geri Alım Bildirimi", "Pay geri alımı"),
    ("X A.Ş.: Sermaye Artırımından Elde Edilen Fonun Kullanım Yerlerine İlişkin Rapor", "ÖDA", "Sermaye artırımı"),
    ("X A.Ş.: Yeni İş İlişkisi", "Yeni İş İlişkisi", "Sözleşme / iş ilişkisi"),
    ("X A.Ş.: SPK Onayı ve İhraç Belgesi", "ÖDA", None),
])
def test_classify_filing_uses_title_and_type_only(title, dtype, expected):
    assert classify_filing(title, dtype) == expected


@pytest.mark.parametrize("value,unit,expected", [
    (4_950_000, "TL", "4,95 milyon TL"),
    (4_950_123, "TL", "4.950.123 TL"),
    (4_950_000.5, "TL", "4.950.000,50 TL"),
    (6_712_345_678, "TL", "6.712.345.678 TL"),
    (1_500_000_000, "USD", "1,5 milyar USD"),
    (30_000_000_000, "TL", "30 milyar TL"),
    (6_700_000_000, "TL", "6,7 milyar TL"),
    (2_500_000, "EUR", "2,5 milyon EUR"),
    (850.0, "TL", "850 TL"),
    (42.1, "TL", "42,10 TL"),
])
def test_format_amount_turkish(value, unit, expected):
    assert format_amount_tr(value, unit) == expected


@pytest.mark.parametrize("raw,expected", [
    ("4.950.000,00", 4_950_000.0), ("1,5", 1.5), ("25,000,000", 25_000_000.0), ("150.000", 150_000.0),
    ("30", 30.0), ("12.5", 12.5),
])
def test_parse_number_tr(raw, expected):
    assert parse_number_tr(raw) == expected


def test_extract_amounts_keeps_unit_and_skips_percentages():
    text = ("Satış bedeli 6.700.000.000 TL olup %100 pay devredilmiştir. Ayrıca 25,000,000 USD ve "
            "30 milyar TL'ye kadar ihraç; 100% oranında.")
    got = [(a.value, a.unit) for a in extract_amounts(text)]
    assert got == [(6_700_000_000.0, "TL"), (25_000_000.0, "USD"), (30_000_000_000.0, "TL")]
    assert extract_amounts("Pay oranı %100, 100%") == []


# ---- guardrail ve gönderi uyarısı ----------------------------------------------------------

def test_guardrails_block_banned_content():
    assert validate_report("Başlık", "Özet", "Hisse üzerinde pozitif haber akışı etkisi yaratması beklenir.")
    assert validate_tweet("GARAN için AL sinyali")
    # KAP başlığı olgusal alıntıdır; şirket adı "Mega" içerse bile rapor engellenmez.
    assert not validate_report("MEGA POLİETİLEN A.Ş.: Pay Alım Satım Bildirimi", "Özet", "Gövde")


def test_prepare_post_strips_and_appends_disclaimer():
    msg = social.prepare_post("GARAN bildirimi yayımladı.\nAL sinyali, hedef fiyat 150 TL", DISCLAIMER_KAP)
    assert msg.startswith("GARAN bildirimi yayımladı.") and msg.endswith(DISCLAIMER_KAP)
    assert not find_banned(msg)
    assert social.prepare_post("MEGA İŞ ANLAŞMASI! AL sinyali", DISCLAIMER_KAP) == ""


def test_content_store_filters_legacy_style_draft(tmp_path, monkeypatch):
    from esham.publishing.content_store import ReportDraft

    monkeypatch.delenv("GIT_AUTO_PUSH", raising=False)
    draft = ReportDraft(
        title="X A.Ş.: İştirak satışının tamamlanması", category="bist",
        summary="🔥 MEGA SÖZLEŞME | X A.Ş. (XXXXX): İştirak satışının tamamlanması",
        body=BAD_LLM_OUTPUT, tags=["Mega Sözleşme", "XXXXX", "KAP"],
    )
    path = ContentStore(tmp_path / "r", tmp_path / "c").publish(draft)
    assert path is not None
    doc = json.loads(path.read_text(encoding="utf-8"))
    assert doc["summary"] == "X A.Ş. (XXXXX): İştirak satışının tamamlanması"
    assert doc["tags"] == ["XXXXX", "KAP"]
    assert not find_banned(doc["body"])
