"""Türkçe metin yardımcıları — tek doğruluk kaynağı.

Python'un varsayılan `.upper()`/`.lower()`'ı Türkçe İ/I/ı/i kurallarını doğru
uygulamaz (`'i'.upper() == 'I'` olur ama Türkçede `'İ'` olmalı). Ayrıca gerçek
dünya belgeleri (KAP bildirimleri, OCR'lı PDF'ler, eski sistemler) çoğu zaman
aksan işaretlerini kaybeder ("taahhüt" -> "taahhut"). Kelime eşleştirmesi yapan
her yer (belge bölüm ayıklama, KAP önem filtresi, kart üreticisi) bu modülü
kullanır — aksi halde her biri kendi (muhtemelen hatalı) kopyasını yazar.
"""
from __future__ import annotations

_UPPER_MAP = str.maketrans({"i": "İ", "ı": "I"})
_FOLD_MAP = str.maketrans(
    {
        "İ": "i", "I": "i", "ı": "i", "ş": "s", "Ş": "s", "ğ": "g", "Ğ": "g",
        "ü": "u", "Ü": "u", "ö": "o", "Ö": "o", "ç": "c", "Ç": "c",
    }
)


def tr_upper(s: str) -> str:
    """Türkçe-doğru büyük harf: 'i' -> 'İ' (noktalı), 'ı' -> 'I' önce uygulanır."""
    return s.translate(_UPPER_MAP).upper()


import json as _json
import re as _re
from pathlib import Path as _Path

# KAP API'sinin kendisi, bildirimi giren kurumun yazdığı tipografik kesme işaretini (’) kayıplı bir kod
# sayfasından geçirip "?" olarak saklıyor: "Bulgaristan?da", "Kurulu?na", "CEO?nun". Bizim zincirimizde
# (requests .json() → UTF-8) karakter kaybı YOK; veri bize "?" ile geliyor.
#
# Onarım YALNIZ GÖRÜNTÜLENEN metne uygulanır (kart, Telegram, bülten listeleri). Ham KAP başlığı "görüldü"
# anahtarı (company:title:date), slug ve saklanan kayıt için AYNEN kalır — aksi halde daha önce yayınlanmış
# bildirimler yeni anahtarla yeniden yayınlanır. Yanlış pozitif olmasın diye yalnız "?" + bilinen Türkçe ek
# ("da", "nin", "na", "ki" …; liste neutral-rules.json → apostrophe.suffixes, TS ile ortak) kalıbı onarılır;
# URL/sorgu dizgisi içindeki "?" ve "Neden?Çünkü" gibi durumlar dokunulmaz.
_RULES_PATH = _Path(__file__).resolve().parents[2] / "web" / "src" / "lib" / "neutral-rules.json"
APOSTROPHE_SUFFIXES: frozenset[str] = frozenset(
    _json.loads(_RULES_PATH.read_text(encoding="utf-8"))["apostrophe"]["suffixes"]
)
_LOST_APOSTROPHE_RE = _re.compile(r"(?:(?<=[^\W_])|(?<=\.))\?([^\W\d_]{1,6})(?![^\W_]|[=&/])")


def _proper_noun_before(s: str, q: int) -> bool:
    """'?' öncesindeki kelime en az 3 harf ve büyük harfle başlıyor mu (özel ad: "İstanbul", "ABD")."""
    i = q
    while i > 0 and s[i - 1].isalpha():
        i -= 1
    word = s[i:q]
    return len(word) >= 3 and word[0].isupper()


def repair_lost_apostrophes(s: str) -> str:
    """Görüntüleme için: 'Bulgaristan?da' -> "Bulgaristan'da". Ek listede değilse, ek küçük harfle
    başlamıyorsa ya da "?" bir URL/sorgu dizgisindeyse (kelimede '://', '=' ya da 'www.' varsa) dokunulmaz. "A.Ş.?nin" ve "Kocaeli/Gebze?de" onarılır."""
    s = s or ""

    def fix(m: "_re.Match[str]") -> str:
        suffix = m.group(1)
        start = s.rfind(" ", 0, m.start()) + 1
        end = s.find(" ", m.end())
        token = s[start:end if end >= 0 else len(s)]
        if suffix not in APOSTROPHE_SUFFIXES or "://" in token or "=" in token or token.startswith("www."):
            return m.group(0)
        if len(suffix) == 1 and not _proper_noun_before(s, m.start()):
            return m.group(0)  # "x?a", "Ne?e": tek harfli ek yalnız özel ad sonrası ("İstanbul?a")
        return "'" + suffix

    return _LOST_APOSTROPHE_RE.sub(fix, s)


def tr_fold(s: str) -> str:
    """Aksan-toleranslı katlama + küçük harf — anahtar kelime eşleştirmesi için.

    Hem karşılaştırılan metin hem anahtar kelimeler bu fonksiyondan geçmeli;
    aksi halde "taahhüt" anahtar kelimesi aksansız yazılmış "taahhut" metnini
    hiç bulamaz ve o bölüm AI'a hiç gitmez.
    """
    return s.translate(_FOLD_MAP).lower()
