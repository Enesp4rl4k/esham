"""Tarafsız dil katmanı — yayınlanan metinde piyasa yargısı/yatırım tavsiyesi olmamasını sağlar.

Esham'ın çıktısı (rapor, kart, Telegram gönderisi) kamuya açık bir bildirimin veya verinin
NE SÖYLEDİĞİNİN özetidir. Al/sat sinyali, hedef fiyat, destek/direnç ve kâr satışı seviyeleri,
boğa/ayı senaryoları, "pozitif/negatif sinyal" etiketleri ve fiyat/haber akışı etkisi tahminleri
SPK mevzuatında yatırım danışmanlığı sayılabilecek içeriklerdir ve yayınlanmaz.

Bu modül deterministiktir (LLM çağırmaz):
- ``find_banned``   : metinde yasaklı kalıp var mı (büyük/küçük harf ve Türkçe aksan duyarsız)
- ``strip_banned``  : markdown'dan yasaklı başlık bölümlerini, satırları ve cümleleri ayıklar
- ``extract_amounts`` / ``format_amount_tr`` : bildirim metnindeki tutarları birimiyle, Türkçe biçimde verir
- ``classify_filing``: bildirim başlığından/türünden tarafsız konu etiketi
- ``DISCLAIMER_*``  : rapor/gönderi uyarı metinleri

Aynı kalıp listesi web tarafında görüntüleme anında eski raporları temizlemek için
``web/src/lib/neutral.ts`` (``BANNED_PATTERNS``) içinde tutulur; değiştirince orayı da güncelleyin.
``tests/test_neutral_language.py`` iki listenin aynı olduğunu doğrular.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

# ---- uyarı metinleri ---------------------------------------------------------

DISCLAIMER_KAP = (
    "Bu içerik, kamuya açık bir KAP bildiriminin otomatik özetidir; yatırım tavsiyesi değildir."
)
DISCLAIMER_GENERIC = (
    "Bu içerik, kamuya açık verilerin otomatik özetidir; yatırım tavsiyesi değildir."
)

# ---- yasaklı kalıplar --------------------------------------------------------
# Kalıplar ``fold`` edilmiş (küçük harf, aksansız, ı→i) metne uygulanır; bu yüzden aksansız yazılır.
# Bilinçli olarak dar tutuldu: bildirimde geçebilecek olgusal terimler ("destekler", "kasım ayı",
# "primli ihraç", "iskontolu bono", "Mega Polietilen") yakalanmaz.
BANNED_PATTERNS: tuple[str, ...] = (
    # sinyal / duyarlılık etiketleri
    r"\bsinyal",
    r"\bpozitif\s*\(",
    r"\bnegatif\s*\(",
    r"\bnotr\s*[-/]\s*pozitif",
    r"\bpozitif haber",
    r"haber akisi etkisi",
    r"\bpozitif fiyatlama",
    r"fiyatlama egilimi",
    r"\b(pozitif|negatif) (etki|yansima|algi)",
    r"\b(olumlu|olumsuz) (algi|senaryo)",
    # fiyat / piyasa etkisi tahmini
    r"etkisi yaratmasi beklenir",
    r"\bbeklenir\b",
    r"fiyatlama etkisi",
    r"\bfiyat etkisi",
    r"\bfiyat algisi",
    r"\bhisse uzerinde\b",
    r"\bhisse fiyatlamasi",
    r"\bhisse yansimasi",
    r"\bpiyasa yansimasi",
    r"\bkatalizor",
    r"(yukselis|dusus|getiri|prim) potansiyeli",
    r"\bpotansiyel:",
    # destek / direnç / seviye
    r"\bdirenc",
    r"\bkritik destek",
    r"\bdestek seviye",
    r"\bdestek bolgesi",
    r"\btaban destegi",
    r"\btepki alim",  # "Olası Tepki Alım Tabanı" (çıplak "alım tabanı" TMO taban fiyatı için olgusaldır)
    r"\b(alim|satis) bolgesi",
    r"\bkar satisi",
    r"\bkar realizasyonu",
    r"\bpivot",
    r"\bfibonacci",
    r"\bkey level",
    r"\bteknik esik",
    r"\basiri (alim|satim)",
    r"\brsi\b",
    r"\bhareketli ortalama",
    # hedef fiyat / değerleme yargısı
    r"\bhedef fiyat",
    r"\bfiyat hedefi",
    r"\badil deger",
    r"\bguclu iskonto",
    r"\byuksek primli",
    r"\bcazip\b",
    # boğa / ayı
    r"\bboga\b",
    r"\bayi (senaryo|piyasa)",
    r"\bbull(ish)?\b",
    r"\bbear(ish)?\b",
    # al / sat çağrısı
    r"\bal\s*/\s*sat\b",
    r"\b(alim|yatirim) firsati",
    r"\b(alim|satim) tavsiyesi",
    r"tavsiye ederim",
    r"\boneririm",
    r"portfoyunuze ekleyin",
    r"\bkesinlikle (al|sat)",
    r"\bmutlaka al",
    r"\bsimdi al\b",
    r"\bgaranti (getiri|kazanc|kar)",
    r"\bkesin kazanc",
    # sansasyonel etiketler
    r"\bmega (is|sozlesme|anlasma)",
    r"\btier-?\s?[12]\b",
    r"\bdev (anlasma|sozlesme|ihale)",
    r"\bstratejik sinif",
    # bildirimden gelmeyen piyasa verisi bölümleri (eski KAP raporlarında yanlış etiketli "sözleşme tutarı")
    r"\btemel finansal carpanlar",
    r"\bciro etki carpani",
    # spekülatif yorum
    r"\bucuz buldugu",
    r"\brisk ve firsatlar",
    r"\bhisseye (olan )?talep",
    r"\byatirimci ilgisini",
    r"\bpara (girisi|cikisi)",
    r"\binsider trading",
)

_BANNED_RE = re.compile("|".join(f"(?:{p})" for p in BANNED_PATTERNS))


def fold(text: str) -> str:
    """Büyük/küçük harf ve aksan duyarsız karşılaştırma için metni katlar (İ/I/ı → i, ş → s ...)."""
    s = (text or "").replace("ı", "i").replace("İ", "i").replace("I", "i")
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return s.lower()


def find_banned(text: str) -> list[str]:
    """Metinde geçen yasaklı kalıpların (katlanmış) eşleşmelerini döner; boşsa temiz."""
    return [m.group(0) for m in _BANNED_RE.finditer(fold(text))]


def is_clean(text: str) -> bool:
    return not find_banned(text)


_HEADING_RE = re.compile(r"^(#{1,6})\s")
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?…])\s+")
_TABLE_SEP_RE = re.compile(r"^\|?\s*:?-{2,}")


def _strip_sentences(line: str) -> str:
    kept = [s for s in _SENTENCE_SPLIT_RE.split(line) if not find_banned(s)]
    return " ".join(kept).strip()


def _drop_orphan_tables(lines: list[str]) -> list[str]:
    """Gövde satırı kalmamış tabloları (yalnız başlık + ayraç) kaldırır."""
    out: list[str] = []
    i = 0
    while i < len(lines):
        if lines[i].lstrip().startswith("|"):
            j = i
            while j < len(lines) and lines[j].lstrip().startswith("|"):
                j += 1
            block = lines[i:j]
            body_rows = [b for b in block[1:] if not _TABLE_SEP_RE.match(b.strip())]
            if body_rows:
                out.extend(block)
            i = j
            continue
        out.append(lines[i])
        i += 1
    return out


def strip_banned(markdown: str) -> str:
    """Yasaklı içeriği markdown'dan ayıklar.

    - Başlığı yasaklı kalıp içeren bölüm (alt başlıklarıyla) tamamen çıkarılır.
    - Madde, tablo satırı ve kalın etiketli satırlar yasaklı kalıp içeriyorsa satır çıkarılır.
    - Düz paragraflarda yalnızca yasaklı kalıp geçen cümleler çıkarılır.
    """
    if not markdown:
        return ""
    out: list[str] = []
    skip_level: int | None = None
    for line in markdown.splitlines():
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
        stripped = line.lstrip()
        if m or stripped.startswith(("|", "-", "*", "+", ">")) or re.match(r"^\d+[.)]\s", stripped):
            continue  # yapısal satır: bütünüyle çıkar
        rest = _strip_sentences(line)
        if rest:
            out.append(rest)
    out = _drop_orphan_tables(out)
    text = "\n".join(out)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def sanitize_summary(summary: str, fallback: str) -> str:
    """Özetteki " | " ile ayrılmış etiket parçalarından ("MEGA SÖZLEŞME | ...") yasaklı olanları atar."""
    if not find_banned(summary or ""):
        return summary
    parts = [p for p in summary.split(" | ") if not find_banned(p)]
    return strip_banned(" | ".join(parts)) or fallback


# ---- tutarlar ----------------------------------------------------------------

_UNIT_MAP = {
    "tl": "TL", "try": "TL", "turk lirasi": "TL",
    "usd": "USD", "abd dolari": "USD", "dolar": "USD", "$": "USD",
    "eur": "EUR", "euro": "EUR", "avro": "EUR", "€": "EUR",
}
_SCALE = {"milyar": 1_000_000_000, "milyon": 1_000_000, "bin": 1_000}

# Kalıp katlanmış metne uygulanır. Sayı: 4.950.000,00 | 30 | 1,5 | 25,000,000
_AMOUNT_RE = re.compile(
    r"(?<![\w.,])(\d{1,3}(?:[.,]\d{3})+(?:[.,]\d+)?|\d+(?:[.,]\d+)?)\s*"
    r"(milyar|milyon|bin)?\s*"
    r"(turk lirasi|abd dolari|tl|try|usd|dolar|eur|euro|avro|\$|€)(?![a-z])"
)


@dataclass(frozen=True)
class Amount:
    value: float
    unit: str  # TL | USD | EUR
    raw: str  # bildirimde geçtiği şekliyle

    def formatted(self) -> str:
        return format_amount_tr(self.value, self.unit)


def parse_number_tr(raw: str) -> float | None:
    """Türkçe/İngilizce yazılmış sayıyı çözer: '4.950.000,00' → 4950000.0, '1,5' → 1.5, '25,000,000' → 25e6."""
    s = raw.strip()
    if not s:
        return None
    dots, commas = s.count("."), s.count(",")
    try:
        if dots and commas:
            # Sondaki ayraç ondalıktır.
            if s.rfind(",") > s.rfind("."):
                return float(s.replace(".", "").replace(",", "."))
            return float(s.replace(",", ""))
        if commas:
            if commas > 1:
                return float(s.replace(",", ""))  # 25,000,000
            return float(s.replace(",", "."))  # tek virgül: Türkçe ondalık
        if dots:
            parts = s.split(".")
            if dots > 1 or len(parts[-1]) == 3:
                return float(s.replace(".", ""))  # Türkçe binlik
            return float(s)
        return float(s)
    except ValueError:
        return None


def _group_tr(int_part: int) -> str:
    return f"{int_part:,}".replace(",", ".")


def format_amount_tr(value: float, unit: str = "TL") -> str:
    """Tutarı Türkçe biçimde yazar: 1.5e9 → '1,5 milyar TL', 4950123 → '4.950.123 TL'.

    "milyar/milyon" yalnızca kayıpsızsa (en çok 2 ondalıkla tam ifade ediliyorsa) kullanılır;
    aksi halde tüm basamaklar binlik noktayla yazılır — bildirimdeki tutar yuvarlanmaz.
    """
    unit = unit or "TL"
    neg = value < 0
    v = abs(value)
    for word, scale in (("milyar", 1_000_000_000), ("milyon", 1_000_000)):
        if v >= scale and abs(v / scale * 100 - round(v / scale * 100)) < 1e-6:
            scaled = round(v / scale, 2)
            if scaled == int(scaled):
                num = _group_tr(int(scaled))
            else:
                ip = int(scaled)
                frac = f"{scaled - ip:.2f}"[2:].rstrip("0")
                num = f"{_group_tr(ip)},{frac}"
            return f"{'-' if neg else ''}{num} {word} {unit}"
    rounded = round(v, 2)
    ip = int(rounded)
    frac_cents = int(round((rounded - ip) * 100))
    num = _group_tr(ip) + (f",{frac_cents:02d}" if frac_cents else "")
    return f"{'-' if neg else ''}{num} {unit}"


def extract_amounts(text: str, limit: int = 5) -> list[Amount]:
    """Bildirim metninde para birimiyle birlikte geçen tutarları sırasıyla döner (yüzdeler hariç).

    Tutarın ANLAMI (sözleşme bedeli mi, ihraç tavanı mı, sermaye mi) metinden güvenle çıkarılamaz;
    bu yüzden çağıran taraf bunları "bildirimde geçen tutarlar" olarak etiketlemeli, manşet rakamı
    olarak kullanmamalıdır.
    """
    if not text:
        return []
    folded = fold(text)
    out: list[Amount] = []
    seen: set[tuple[float, str]] = set()
    for m in _AMOUNT_RE.finditer(folded):
        num = parse_number_tr(m.group(1))
        if num is None or num <= 0:
            continue
        scale = _SCALE.get(m.group(2) or "", 1)
        unit = _UNIT_MAP.get(m.group(3), "TL")
        value = num * scale
        key = (round(value, 2), unit)
        if key in seen:
            continue
        seen.add(key)
        out.append(Amount(value=value, unit=unit, raw=m.group(0).strip()))
        if len(out) >= limit:
            break
    return out


# ---- bildirim konusu ---------------------------------------------------------

# Sıra önemlidir: ilk eşleşen kazanır. Yalnızca başlık + bildirim türüne bakılır; bildirim gövdesi
# ("pay alım satım sözleşmesi" gibi) konu belirlemede kullanılmaz — eski hata buydu
# (iştirak satışı ve tahvil başvurusu "yeni iş anlaşması" sayılıyordu).
_TOPIC_RULES: tuple[tuple[tuple[str, ...], str], ...] = (
    (("temerrut",), "Temerrüt bildirimi"),
    (("geri alim",), "Pay geri alımı"),
    (("kar payi", "temettu"), "Kâr payı"),
    (("tahvil", "borclanma araci", "bono", "sukuk", "kira sertifika", "ihrac tavan"), "Borçlanma aracı ihracı"),
    (("sermaye artir", "bedelli", "bedelsiz", "tahsisli", "fon kullanim"), "Sermaye artırımı"),
    (("istirak", "bagli ortaklik", "pay satis", "satin al", "devral", "birlesme", "birles"),
     "Pay / iştirak alım-satımı"),
    (("pay alim satim",), "Pay alım satım bildirimi"),
    (("yeni is iliskisi", "siparis", "sozlesme", "ihale"), "Sözleşme / iş ilişkisi"),
    (("finansal rapor", "faaliyet raporu"), "Finansal rapor"),
    (("genel kurul",), "Genel kurul"),
    (("derecelendirme",), "Kredi derecelendirme"),
)


def classify_filing(title: str, disclosure_type: str = "") -> str | None:
    """Bildirimin konusunu tarafsız bir etiketle döner; emin olunamazsa None."""
    text = fold(f"{title} {disclosure_type}")
    for keys, label in _TOPIC_RULES:
        if any(k in text for k in keys):
            return label
    return None
