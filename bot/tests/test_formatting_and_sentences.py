"""Tek Türkçe sayı/yüzde biçimi, sayı/kısaltma farkında cümle bölme ve kaynakta onarılan kesme işareti.

İnceleme 2026-11-27: "S&P 500 +1,16% yükseldi (7" (özet binlik noktada kesildi), "+2,18%" ile "(%+4.66)"
karışık biçim, "Bulgaristan?da" (kayıp kesme işareti). Ağ yok.
"""
from __future__ import annotations

import json
import random
import re
from pathlib import Path

import pytest

from esham.formatting import parse_tr_pct, tr_bp, tr_number, tr_pct, tr_signed
from esham.neutral import strip_banned
from esham.sentences import first_sentence, parens_balanced, safe_truncate, split_sentences
from esham.turkish import repair_lost_apostrophes

ROOT = Path(__file__).resolve().parents[2]
VECTORS = json.loads((ROOT / "web" / "src" / "lib" / "neutral-vectors.json").read_text(encoding="utf-8"))


# ---- biçim kuralı (bir kez seçildi: formatting.py başı) -----------------------------------------

@pytest.mark.parametrize("value,expected", [
    (2.18, "+%2,18"), (-1.02, "-%1,02"), (0.0, "%0,00"), (-0.001, "%0,00"), (0.004, "%0,00"),
    (1234.5, "+%1.234,50"), (-0.06, "-%0,06"),
])
def test_tr_pct_signed(value, expected):
    assert tr_pct(value) == expected


def test_tr_pct_level_and_other_helpers():
    assert tr_pct(4.912, 2, signed=False) == "%4,91"
    assert tr_pct(0.431, 3, signed=False) == "%0,431"
    assert tr_number(10977.01) == "10.977,01" and tr_number(54623, 0) == "54.623"
    assert tr_signed(-0.004) == "0,00" and tr_signed(12.5, 1) == "+12,5"
    assert tr_bp(0.06) == "+6 baz puan" and tr_bp(-0.0449) == "-4 baz puan" and tr_bp(0.001) == "0 baz puan"
    for s, v in (("+%2,18", 2.18), ("-%1,02", -1.02), ("+2,18%", 2.18), ("%0,00", 0.0), ("+%1.234,50", 1234.5)):
        assert parse_tr_pct(s) == pytest.approx(v)
    assert parse_tr_pct("—") is None


# Üreticilerde ad-hoc yüzde/ondalık f-string'i YOK: hepsi formatting.py'den geçer.
PRODUCER_FILES = [
    "esham/pipeline.py", "esham/ai/analyzer.py", "esham/market_text.py", "esham/sources/news_detector.py",
    "esham/sources/bist.py", "esham/sources/sector.py", "esham/sources/global_macro.py", "esham/sources/viop.py",
    "esham/sources/peer.py", "esham/sources/crypto.py", "esham/sources/watchlist.py", "esham/scheduler.py",
]
_ADHOC = re.compile(r"""\{[^{}]*:[+,]?[,.]?\d*f\}\s*%|%\{[^{}]*:[+]?\.\d+f\}|\{[^{}]*:,\.\d+f\}""")


@pytest.mark.parametrize("rel", PRODUCER_FILES)
def test_no_adhoc_number_format_in_producers(rel):
    src = (ROOT / "bot" / rel).read_text(encoding="utf-8")
    # Kurumsal teknik tablo (TechnicalSnapshot) yayın üreticilerinde kullanılmıyor; sözleşmesi ayrı.
    src = re.sub(r"class TechnicalSnapshot:.*?(?=\nCHART_URL)", "", src, flags=re.S)
    hits = [m.group(0) for m in _ADHOC.finditer(src)]
    assert not hits, (rel, hits)


# ---- cümle bölme ---------------------------------------------------------------------------------

@pytest.mark.parametrize("text,expected", VECTORS["sentences"])
def test_shared_sentence_vectors(text, expected):
    assert split_sentences(text) == expected


def test_first_sentence_keeps_turkish_numbers_and_abbreviations():
    assert first_sentence("S&P 500 +1,16% yükseldi (7.266,17).") == "S&P 500 +1,16% yükseldi (7.266,17)."
    assert first_sentence("AKTİF YATIRIM BANKASI A.Ş. Özet yayımladı. Ek bilgi.") == "AKTİF YATIRIM BANKASI A.Ş. Özet yayımladı."
    assert first_sentence("T.C. Hazine 27.11.2026 saat 08.30'da ihale açtı. Sonuç 10.30'da.") == \
        "T.C. Hazine 27.11.2026 saat 08.30'da ihale açtı."
    assert first_sentence("X Ltd. Şti. ile kira, aidat vb. giderler için sözleşme imzalandı. Y.") == \
        "X Ltd. Şti. ile kira, aidat vb. giderler için sözleşme imzalandı."
    assert first_sentence("") == ""


_ABBR = ["A.Ş.", "T.C.", "Ltd. Şti.", "vb.", "Dr."]


def _num(rng: random.Random) -> str:
    kind = rng.randrange(5)
    if kind == 0:
        return tr_number(rng.uniform(0, 99999), 2)
    if kind == 1:
        return tr_pct(rng.uniform(-9, 9))
    if kind == 2:
        return f"{rng.randint(1, 28):02d}.{rng.randint(1, 12):02d}.20{rng.randint(20, 30)}"
    if kind == 3:
        return f"{rng.randint(0, 23):02d}.{rng.randint(0, 59):02d}"
    return tr_number(rng.uniform(1e6, 1e10), 0)


def test_property_no_piece_ends_inside_number_or_open_parenthesis():
    """Rastgele şablon metinler: hiçbir parça sayının ortasında bitmez, parantezler parça içinde dengelidir."""
    rng = random.Random(20261127)
    for _ in range(3000):
        n = rng.randint(1, 4)
        sentences = []
        for _ in range(n):
            s = f"{rng.choice(['XU100', 'Şirket', 'Endeks', 'S&P 500'])} {rng.choice(_ABBR)} {_num(rng)} oldu"
            if rng.random() < 0.5:
                s += f" ({_num(rng)}; {rng.choice(_ABBR)} {_num(rng)})"
            sentences.append(s + rng.choice([".", "!", "…"]))
        text = " ".join(sentences)
        pieces = split_sentences(text)
        assert " ".join(pieces) == text
        for i, p in enumerate(pieces):
            assert parens_balanced(p), (text, p)
            if i + 1 < len(pieces):
                assert not (p[-2:-1].isdigit() and pieces[i + 1][:1].isdigit()), (text, p)
        summary = first_sentence(text)
        assert summary == sentences[0], (text, summary)


@pytest.mark.parametrize("limit", [20, 35, 50, 80])
def test_safe_truncate_never_cuts_numbers_or_leaves_open_paren(limit):
    text = "S&P 500 önceki kapanışa göre +%1,16 (7.266,17; 27.11.2026 19:24 TSİ) seviyesinde ve hacim 1.234.567 adet oldu"
    out = safe_truncate(text, limit)
    assert len(out) <= limit and parens_balanced(out)
    body = out.rstrip("…")
    assert text.startswith(body)
    nxt = text[len(body):len(body) + 1]
    assert nxt in ("", " ") or not (body[-1:].isalnum() and nxt.isalnum()), (out, nxt)


def test_strip_banned_uses_abbreviation_aware_splitter():
    # Kısaltmada bölünüp yarım cümle kalmıyor (eski davranış "ABC A.Ş. Teslimat..." bırakıyordu).
    assert strip_banned("ABC A.Ş. hedef fiyatını 150 TL olarak açıkladı. Teslimat 2027'de.") == "Teslimat 2027'de."


# ---- kayıp kesme işareti (yalnız görüntüleme katmanı) ---------------------------------------------

@pytest.mark.parametrize("raw,fixed", VECTORS["apostrophe"])
def test_repair_lost_apostrophes_shared_vectors(raw, fixed):
    """Ortak vektörler (TS: repairLostApostrophes). Yalnız 'harf?Türkçe-ek'; URL ve 'Neden?Çünkü' dokunulmaz."""
    assert repair_lost_apostrophes(raw) == fixed


def _archived_kap_titles_with_lost_apostrophe() -> list[dict]:
    import os

    base = ROOT / "web" / "content" / "reports"
    prefix = "\\\\?\\" if os.name == "nt" else ""  # Windows uzun yol sınırı (bazı slug'lar 260+ karakter)
    out = []
    for name in sorted(os.listdir(prefix + str(base))):
        with open(prefix + str(base / name), encoding="utf-8") as fh:
            doc = json.load(fh)
        if "KAP" in (doc.get("sources") or []) and re.search(r"[^\W\d_]\?[^\W\d_]", doc.get("title", "")):
            out.append(doc)
    return out


def test_raw_kap_title_key_and_slug_unchanged_so_archive_is_not_republished():
    """Onarım kaynakta YAPILMAZ: ham başlık "görüldü" anahtarında, slug'da ve kayıtta aynen kalır.

    Arşivde "?" taşıyan KAP başlıkları için: KapSource aynı başlığı üretir, NewsStream anahtarı onarımdan
    bağımsızdır ve yayın slug'ı saklanan slug ile aynıdır → birleştirme günü bu bildirimler yeniden yayınlanmaz.
    """
    from esham.news_stream import NewsStream
    from esham.publishing.content_store import slugify
    from esham.sources.kap import KapSource

    docs = _archived_kap_titles_with_lost_apostrophe()
    assert len(docs) >= 10, len(docs)  # 2026-11-28 itibarıyla arşivde 14 başlık
    key = NewsStream._key
    for doc in docs:
        company, content = doc["title"].split(": ", 1)
        d = KapSource()._to_disclosure({"kapTitle": company, "subject": doc.get("kap", {}).get("type", "x"),
                                        "summary": content, "disclosureIndex": doc.get("kap", {}).get("index")})
        assert d.title == doc["title"], doc["title"]  # ham başlık aynen
        assert key(None, d) == f"{d.company}:{doc['title']}:{d.date}"  # anahtar ham başlıktan
        idx = (doc.get("kap") or {}).get("index", "")
        assert doc["slug"].startswith(slugify(d.title) + (f"-{idx}" if idx else "")), doc["slug"]
        # görüntülenen metin onarılır (arşivdeki tüm örnekler bilinen Türkçe eklerle), anahtar/slug buna dayanmaz
        shown = repair_lost_apostrophes(d.title)
        assert not re.search(r"[^\W\d_]\?[^\W\d_]", shown), shown


def test_kap_report_keeps_raw_title_but_card_and_telegram_are_repaired(monkeypatch):
    from esham import pipeline
    from esham.ai.client import LlmClient
    from esham.sources import Disclosure

    monkeypatch.setattr(LlmClient, "generate", lambda self, *a, **k: None)
    drafts, posts, cards = [], [], []

    class _Store:
        last_status = "published"

        def prepare(self, draft):
            return "ok"

        def publish(self, draft, prepared=False):
            drafts.append(draft)
            return Path("x.json")

    class _Social:
        def broadcast(self, message, *a, **k):
            posts.append((message, k.get("verbatim")))

    monkeypatch.setattr(pipeline, "ContentStore", _Store)
    monkeypatch.setattr(pipeline, "SocialPublisher", _Social)
    monkeypatch.setattr(pipeline, "_render_card", lambda spec: cards.append(spec.headline))
    monkeypatch.setattr(pipeline, "KapSource", lambda: type("K", (), {"get_detail_text": lambda s, i: ""})())
    raw = "KIRAÇ GALVANİZ A.Ş.: Bulgaristan?da İhale Kazanılması"
    d = Disclosure(raw, "KIRAÇ GALVANİZ A.Ş.", "2026-11-27", "Yeni İş İlişkisi", ticker="KRGLV", disclosure_index="1703999")
    pipeline.run_news_report(disclosure=d, publish_social=True)
    (draft,) = drafts
    assert draft.title == raw and draft.summary == raw  # saklanan kayıt: ham KAP başlığı
    assert draft.resolved_slug().startswith("kirac-galvaniz-a-s-bulgaristan-da-ihale-kazanilmasi-1703999")
    assert cards == ["KIRAÇ GALVANİZ A.Ş.: Bulgaristan'da İhale Kazanılması"]
    (msg, verbatim), = posts
    assert "Bulgaristan'da" in msg and "?" not in msg.split("\n")[0]
    assert verbatim and verbatim[0] in msg  # birebir parça (onarılmış görünüm) mesajda aynen geçer
