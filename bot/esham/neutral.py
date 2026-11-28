"""Tarafsız dil katmanı — yayınlanan metinde piyasa yargısı/yatırım tavsiyesi olmamasını sağlar.

Esham'ın çıktısı (rapor, kart, Telegram gönderisi) kamuya açık bir bildirimin veya verinin NE
SÖYLEDİĞİNİN özetidir. Al/sat sinyali, hedef fiyat, destek/direnç ve kâr satışı seviyeleri, boğa/ayı
senaryoları, "pozitif/negatif sinyal" etiketleri ve fiyat/haber akışı etkisi tahminleri SPK mevzuatında
yatırım danışmanlığı sayılabilecek içeriklerdir ve yayınlanmaz.

Önemli ayrım: süzgeç YALNIZ bizim veya LLM'in ÜRETTİĞİ metne uygulanır. KAP'ın resmî başlığı ve
bildirimden birebir alıntılar olgusal kaynaktır ve süzülmez ("Tier 2", "Sinyalizasyon", "katalizör
değişimi", "adil değer ölçümü" bozulmamalı).

Tek kaynak: normalizasyon kuralları, yasaklı kalıplar ve not metinleri ``web/src/lib/neutral-rules.json``
dosyasındadır; aynı dosyayı ``web/src/lib/neutral.ts`` de okur. Davranış eşitliği
``web/src/lib/neutral-vectors.json`` ortak test vektörleriyle iki tarafta da doğrulanır.

Bu modül deterministiktir (LLM çağırmaz).
"""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

RULES_PATH = Path(__file__).resolve().parents[2] / "web" / "src" / "lib" / "neutral-rules.json"
RULES: dict = json.loads(RULES_PATH.read_text(encoding="utf-8"))

NOTE_KAP: str = RULES["notes"]["kap"]
NOTE_GENERIC: str = RULES["notes"]["generic"]
NOTE_LEGACY: str = RULES["notes"]["legacy"]
NOTE_AMOUNT_MISSING: str = RULES["notes"]["amount_missing"]
# Geriye dönük adlar
DISCLAIMER_KAP = NOTE_KAP
DISCLAIMER_GENERIC = NOTE_GENERIC

#: Bot tarafından üretilen raporların şema sürümü. Web, bu alanı taşımayan (eski) KAP raporlarını yalın
#: görünümde gösterir; yorum gövdesi render edilmez.
REPORT_SCHEMA_VERSION = 2

BANNED_PATTERNS: tuple[str, ...] = tuple(RULES["patterns"])
_BANNED_RE = re.compile("|".join(f"(?:{p})" for p in BANNED_PATTERNS), re.ASCII)

_N = RULES["normalization"]
_REMOVE_RE = re.compile("[" + re.escape(_N["remove"]) + "]")
_SPACE_RE = re.compile("[" + re.escape(_N["space"]) + "]")
_DASH_RE = re.compile("[" + re.escape(_N["dash"]) + "]")
_MULTI_SPACE_RE = re.compile(" {2,}")
_LETTER_SPACING_RE = re.compile(r"(?<![a-z0-9])(?:[a-z] ){%d,}[a-z](?![a-z0-9])" % (_N["letter_spacing_min"] - 1))
_COMBINING_RE = re.compile("[̀-ͯ]")
_CONFUSABLES: dict[str, str] = _N["confusables"]
_LEET: dict[str, str] = _N["leet"]
_MIXED_SCRIPT_RE = re.compile(
    r"[^ ]*(?:[A-Za-z][^ ]*[Ͱ-ϿЀ-ӿ]|[Ͱ-ϿЀ-ӿ][^ ]*[A-Za-z])[^ ]*"
)
_ALNUM_TOKEN_RE = re.compile(r"(?<![a-z0-9])(?=[a-z0-9]*[a-z])(?=[a-z0-9]*[0-9])[a-z0-9]+(?![a-z0-9])")


def normalize(text: str) -> str:
    """Karşılaştırma için tek satırlık metni normalize eder (TS ``normalize`` ile birebir aynı).

    NFKC → sıfır genişlikli/yumuşak tire/varyasyon seçicileri sil → Unicode boşluklar ve tireler tek
    boşluk → Türkçe katlama (İ/I/ı → i) + küçük harf → NFD + birleşen işaretleri sil → çoklu boşluk tek
    → harf aralıklı yazım ("s i n y a l") işaretlenir.
    """
    s = unicodedata.normalize("NFKC", text or "")
    s = _REMOVE_RE.sub("", s)
    s = _SPACE_RE.sub(" ", s)
    s = _DASH_RE.sub(" ", s)
    # Latin + Kiril/Yunan harfleri karışık kelime ("сінyal") → işaretlenir; kalan benzer harfler eşlenir.
    s = _MIXED_SCRIPT_RE.sub("karisik alfabe yazim", s)
    s = s.replace("İ", "i").replace("I", "i").replace("ı", "i").lower()
    s = "".join(_CONFUSABLES.get(ch, ch) for ch in s)
    s = _COMBINING_RE.sub("", unicodedata.normalize("NFD", s))
    # Harf + rakam karışık kelimede rakam → harf ("h3def f1yat" → "hedef fiyat")
    s = _ALNUM_TOKEN_RE.sub(lambda m: "".join(_LEET.get(c, c) for c in m.group(0)), s)
    s = _MULTI_SPACE_RE.sub(" ", s).strip()
    s = _LETTER_SPACING_RE.sub("harf aralikli yazim", s)
    return s


# Geriye dönük ad (anahtar kelime eşleştirmesinde kullanılır)
fold = normalize

_LINE_SPLIT_RE = re.compile(r"\r?\n")


def find_banned(text: str) -> list[str]:
    """Metinde (satır satır) geçen yasaklı kalıp eşleşmeleri; boşsa temiz."""
    out: list[str] = []
    for line in _LINE_SPLIT_RE.split(text or ""):
        out.extend(m.group(0) for m in _BANNED_RE.finditer(normalize(line)))
    return out


def is_clean(text: str) -> bool:
    return not find_banned(text)


_HEADING_RE = re.compile(r"^(#{1,6}) ")
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?…]) +")
_TABLE_SEP_RE = re.compile(r"^\|? *:?-{2,}")
_STRUCTURAL_RE = re.compile(r"^(?:[|\-*+>]|\d+[.)] )")


def _strip_sentences(line: str) -> str:
    return " ".join(s for s in _SENTENCE_SPLIT_RE.split(line) if not find_banned(s)).strip()


def _drop_orphan_tables(lines: list[str]) -> list[str]:
    out: list[str] = []
    i = 0
    while i < len(lines):
        if lines[i].lstrip().startswith("|"):
            j = i
            while j < len(lines) and lines[j].lstrip().startswith("|"):
                j += 1
            block = lines[i:j]
            if any(not _TABLE_SEP_RE.match(b.strip()) for b in block[1:]):
                out.extend(block)
            i = j
            continue
        out.append(lines[i])
        i += 1
    return out


def strip_banned(markdown: str) -> str:
    """ÜRETİLMİŞ markdown'dan yasaklı içeriği ayıklar (TS ``stripBanned`` ile aynı davranış).

    Başlığı yasaklı bölüm alt başlıklarıyla, madde/tablo satırı bütünüyle, düz paragrafta yalnız
    ilgili cümle çıkar. KAP başlığı/alıntısı bu fonksiyona VERİLMEMELİDİR.
    """
    if not markdown:
        return ""
    out: list[str] = []
    skip_level: int | None = None
    for line in _LINE_SPLIT_RE.split(markdown):
        m = _HEADING_RE.match(line)
        if m:
            level = len(m.group(1))
            if skip_level is not None and level <= skip_level:
                skip_level = None
            if skip_level is None and find_banned(line):
                skip_level = level
                continue
        if skip_level is not None:
            continue
        if not find_banned(line):
            out.append(line)
            continue
        if m or _STRUCTURAL_RE.match(line.lstrip()):
            continue
        rest = _strip_sentences(line)
        if rest:
            out.append(rest)
    text = "\n".join(_drop_orphan_tables(out))
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def sanitize_summary(summary: str, fallback: str) -> str:
    """Özetteki " | " ile ayrılmış etiket parçalarından ("MEGA SÖZLEŞME | ...") yasaklı olanları atar."""
    if not find_banned(summary or ""):
        return summary
    parts = [p for p in summary.split(" | ") if not find_banned(p)]
    return strip_banned(" | ".join(parts)) or fallback


# ---- tutarlar ----------------------------------------------------------------
# Rapor ve kartlarda bildirimden HİÇBİR tutar gösterilmez. Üç inceleme turunda hem sayı ayrıştırma
# (büyüklük hataları) hem de birebir alıntı (olumsuzlamanın kesilmesi, "T.C."/"Şti." sonrası bölünme,
# tek satıra inmiş KAP tablolarından bağlamsız parçalar) yanıltıcı çıktı üretti. Olgu bloğu her zaman
# NOTE_AMOUNT_MISSING ("Tutar bilgisi için bildirime bakın.") ve KAP bağlantısını gösterir.


# ---- bildirim konusu ---------------------------------------------------------
# KAP'ın KENDİ bildirim türü alanı (``subject``) kullanılır; başlıkta anahtar kelime aranmaz (şirket adı
# "Birleşik", "Satın Alım İhalesi", "Esas Sözleşme Tadili" gibi yanlış eşleşmeler buradan doğuyordu).
# Genel/boş türlerde güvenli etiket "KAP bildirimi"dir.
GENERIC_LABEL = "KAP bildirimi"
_GENERIC_TYPES = {
    "", "ozel durum aciklamasi", "ozel durum aciklamasi (genel)", "genel", "duyuru", "diger",
    "kap bildirimi", "bildirim", "oda",
}


def classify_filing(title: str = "", disclosure_type: str = "") -> str:
    """Kart/rapor etiketi: KAP'ın kendi bildirim türü; genel veya boşsa "KAP bildirimi".

    ``title`` bilinçli olarak kullanılmaz (geriye dönük imza için duruyor).
    """
    dtype = re.sub(r"\s+", " ", (disclosure_type or "").strip())
    if normalize(dtype) in _GENERIC_TYPES or len(dtype) > 90:
        return GENERIC_LABEL
    return dtype


# ---- eski (sürümsüz) kayıtların görünümü ------------------------------------
# web/src/lib/neutral.ts `legacyTitle` / `legacyView` ile aynı kural (ortak vektörlerle test edilir).

_LEGACY = RULES["legacy"]
_OWN_TEMPLATES = [(re.compile(p, re.ASCII), t) for p, t in _LEGACY["own_templates"]]
NOTE_LEGACY_SUMMARY_KAP: str = RULES["notes"]["legacy_summary_kap"]
NOTE_LEGACY_SUMMARY: str = RULES["notes"]["legacy_summary"]


def is_legacy(doc: dict) -> bool:
    v = doc.get("schemaVersion")
    return not (isinstance(v, int) and v >= REPORT_SCHEMA_VERSION)


def _own_template_type(title: str) -> str | None:
    n = normalize(title)
    for rx, typ in _OWN_TEMPLATES:
        if rx.search(n):
            return typ
    return None


def is_official_kap_title(doc: dict) -> bool:
    """Eski kaydın başlığı KAP'ın kendi metni mi? KAP kaynaklı ve bizim şablon başlıklarımızdan biri değilse."""
    return "KAP" in (doc.get("sources") or []) and _own_template_type(str(doc.get("title", ""))) is None


def _tr_date(iso: str) -> str:
    from datetime import datetime, timedelta, timezone

    try:
        dt = datetime.fromisoformat(str(iso).replace("Z", "+00:00")).astimezone(timezone(timedelta(hours=3)))
    except ValueError:
        return ""
    return f"{dt.day} {_LEGACY['months'][dt.month - 1]} {dt.year}"


def legacy_title(doc: dict) -> str:
    """Sürümsüz kaydın görünen başlığı: resmî KAP başlığı aynen; diğerleri '<tür> — <tarih>'."""
    title = str(doc.get("title", ""))
    if is_official_kap_title(doc):
        return title
    typ = _own_template_type(title) or _LEGACY["category_types"].get(str(doc.get("category", "")), "Piyasa notu")
    date = _tr_date(str(doc.get("publishedAt", "")))
    return f"{typ} — {date}" if date else typ


def legacy_summary(doc: dict) -> str:
    return NOTE_LEGACY_SUMMARY_KAP if is_official_kap_title(doc) else NOTE_LEGACY_SUMMARY

# ---- özet tekrarı -----------------------------------------------------------
# web/src/lib/neutral.ts `distinctSummary` ile aynı kural (ortak vektörler: web/src/lib/summary-vectors.json).
_TRAILING_PUNCT = " \t.…!?;:,"


def distinct_summary(title: str, summary: str | None) -> str:
    """Başlığın altında gösterilecek özet: başlığı tekrarlıyorsa "" (Türkçe büyük/küçük harf, boşluk ve
    sondaki noktalama farkı yok sayılır; karşılaştırma ``normalize`` ile)."""
    s = (summary or "").strip()

    def key(t: str) -> str:
        return normalize(t).rstrip(_TRAILING_PUNCT)

    return s if s and key(s) != key(title or "") else ""
