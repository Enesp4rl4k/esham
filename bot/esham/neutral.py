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
from dataclasses import dataclass
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
    s = s.replace("İ", "i").replace("I", "i").replace("ı", "i").lower()
    s = _COMBINING_RE.sub("", unicodedata.normalize("NFD", s))
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
# İlke: ayrıştırma KESİN değilse tutar gösterilmez. Belirsiz sayı biçimi tahminle çözülmez.

_CURRENCY = {
    "tl": "TL", "try": "TL", "₺": "TL", "turk lirasi": "TL",
    "usd": "USD", "abd dolari": "USD", "amerikan dolari": "USD", "dolar": "USD", "$": "USD",
    "eur": "EUR", "euro": "EUR", "avro": "EUR", "€": "EUR",
    "gbp": "GBP", "sterlin": "GBP", "ingiliz sterlini": "GBP", "£": "GBP",
    "chf": "CHF", "isvicre frangi": "CHF",
    "jpy": "JPY", "japon yeni": "JPY", "yen": "JPY",
}
_SCALES = {
    "milyar": 1_000_000_000, "billion": 1_000_000_000, "bn": 1_000_000_000,
    "milyon": 1_000_000, "million": 1_000_000, "mn": 1_000_000,
    "bin": 1_000, "thousand": 1_000,
}
_CUR_ALT = "|".join(sorted((re.escape(k) for k in _CURRENCY), key=len, reverse=True))
_SCALE_ALT = "|".join(sorted(_SCALES, key=len, reverse=True))
_NUM = r"\d[\d.,]*\d|\d"
# Sayı + (ölçek) + para birimi  |  para birimi + sayı + (ölçek)
_AMOUNT_AFTER_RE = re.compile(
    rf"(?<![\w.,%])({_NUM})(?: ?({_SCALE_ALT}))? ?({_CUR_ALT})(?![a-z])", re.ASCII
)
_AMOUNT_BEFORE_RE = re.compile(
    rf"(?<![a-z])({_CUR_ALT}) ?({_NUM})(?: ?({_SCALE_ALT})(?![a-z]))?(?![\d%])", re.ASCII
)
# Tablo birimi bildirimi: "(Bin TL)", "Milyon TL" başlığı → tablodaki sayıların ölçeği metinden güvenle
# çıkarılamaz; bu durumda hiçbir tutar gösterilmez.
_TABLE_UNIT_RE = re.compile(r"(?:\(|^|[^\d ] )(bin|milyon|milyar) (tl|try|usd|eur)\b", re.ASCII | re.M)
_NOMINAL_RE = re.compile(r"nominal", re.ASCII)


def parse_number_strict(raw: str) -> float | None:
    """Sayıyı yalnız biçim KESİNSE çözer; belirsizse None.

    Kesin biçimler: ``4.950.000,00`` (TR), ``25,000,000.50`` (EN), ``250,000`` / ``250.000`` (tek ayraç +
    tam 3 hane → binlik), ``1,5`` / ``12.5`` (tek ayraç + 1-2 hane → ondalık), ``42`` (düz). Diğer her şey
    (``1,2345``, ``1.234,567.8``, ``1.23.4``) belirsizdir.
    """
    s = raw.strip()
    if re.fullmatch(r"\d+", s):
        return float(s)
    m = re.fullmatch(r"(\d{1,3}(?:\.\d{3})+)(?:,(\d+))?", s)  # TR binlik
    if m:
        return float(m.group(1).replace(".", "") + ("." + m.group(2) if m.group(2) else ""))
    m = re.fullmatch(r"(\d{1,3}(?:,\d{3})+)(?:\.(\d+))?", s)  # EN binlik
    if m:
        return float(m.group(1).replace(",", "") + ("." + m.group(2) if m.group(2) else ""))
    m = re.fullmatch(r"(\d+)[.,](\d{1,2})", s)  # tek ayraç + 1-2 hane → ondalık
    if m:
        return float(f"{m.group(1)}.{m.group(2)}")
    return None


# Geriye dönük ad
parse_number_tr = parse_number_strict


@dataclass(frozen=True)
class Amount:
    value: float
    unit: str  # TL | USD | EUR | GBP | CHF | JPY
    raw: str  # kaynaktaki sayı dizgisi (birebir)
    scale: int = 1

    def formatted(self) -> str:
        return format_amount_tr(self.value, self.unit)


def _group_tr(int_part: int) -> str:
    return f"{int_part:,}".replace(",", ".")


def format_amount_tr(value: float, unit: str = "TL") -> str:
    """Tutarı Türkçe biçimde yazar: 1.5e9 → '1,5 milyar TL', 4950123 → '4.950.123 TL'.

    "milyar/milyon" yalnızca kayıpsızsa (en çok 2 ondalıkla tam) kullanılır; tutar yuvarlanmaz.
    """
    unit = unit or "TL"
    neg = value < 0
    v = abs(value)
    for word, scale in (("milyar", 1_000_000_000), ("milyon", 1_000_000)):
        if v >= scale and abs(v / scale * 100 - round(v / scale * 100)) < 1e-6:
            scaled = round(v / scale, 2)
            ip = int(scaled)
            frac = f"{scaled - ip:.2f}"[2:].rstrip("0")
            num = _group_tr(ip) + (f",{frac}" if frac else "")
            return f"{'-' if neg else ''}{num} {word} {unit}"
    rounded = round(v, 2)
    ip = int(rounded)
    cents = int(round((rounded - ip) * 100))
    return f"{'-' if neg else ''}{_group_tr(ip)}{f',{cents:02d}' if cents else ''} {unit}"


def extract_amounts(text: str, limit: int = 5) -> list[Amount]:
    """Bildirim metninde para birimiyle birlikte ve KESİN biçimde geçen tutarlar.

    Gösterilmeyenler: yüzdeler, belirsiz sayı biçimleri, "nominal" değerler (ör. "1 TL nominal değerli"),
    tablo birimi ("(Bin TL)") bildirilmiş metinler (o durumda hiç tutar dönmez). Tutarın ANLAMI metinden
    çıkarılmaz; çağıran taraf "bildirimde geçen tutarlar" diye etiketlemeli, manşet rakamı yapmamalı.
    """
    if not text:
        return []
    found: list[tuple[int, Amount]] = []
    seen: set[tuple[float, str]] = set()
    for line in _LINE_SPLIT_RE.split(text):
        norm = normalize(line)
        if _TABLE_UNIT_RE.search(norm):
            return []
        hits: list[tuple[int, int, str, str | None, str]] = []
        for m in _AMOUNT_AFTER_RE.finditer(norm):
            hits.append((m.start(), m.end(), m.group(1), m.group(2), m.group(3)))
        for m in _AMOUNT_BEFORE_RE.finditer(norm):
            hits.append((m.start(), m.end(), m.group(2), m.group(3), m.group(1)))
        hits.sort()
        last_end = -1
        for start, end, num_s, scale_s, cur_s in hits:
            if start < last_end:
                continue  # çakışan eşleşme
            last_end = end
            window = norm[max(0, start - 25): end + 25]
            if _NOMINAL_RE.search(window):
                continue
            num = parse_number_strict(num_s)
            if num is None or num <= 0:
                continue
            scale = _SCALES.get(scale_s or "", 1)
            unit = _CURRENCY[cur_s]
            value = num * scale
            key = (round(value, 4), unit)
            if key in seen:
                continue
            seen.add(key)
            found.append((len(found), Amount(value=value, unit=unit, raw=num_s, scale=scale)))
    return [a for _, a in found][:limit]


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
