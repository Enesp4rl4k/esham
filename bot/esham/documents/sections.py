"""İlgili bölüm ayıklama — maliyet kontrolünün kalbi.

Uzun belgeyi paragraflara böler, anahtar kelime içeren paragrafları (ve hemen
sonrasını) tutar, bütçeyi (max_chars) aşınca durur. Böylece AI'a yüzlerce sayfa
yerine yalnızca ilgili birkaç bin karakter gider.
"""
from __future__ import annotations

import re

from ..turkish import tr_fold as _tr_fold

# Halka arz belgeleri için önemli bölümler.
IPO_KEYWORDS = (
    "fiyat tespit",
    "iskonto",
    "halka arz büyüklüğü",
    "halka arz fiyat",
    "fon kullanım",
    "kullanım yer",
    "taahhüt",
    "risk faktör",
    "değerleme",
    "çarpan",
    "f/k",
    "fd/favök",
    "pd/dd",
    "ortaklık yapısı",
    "finansal tablo",
    "net dönem kâr",
    "hasılat",
)

# Şirket finansal/faaliyet raporları için önemli bölümler.
FINANCIAL_KEYWORDS = (
    "bilanço",
    "gelir tablosu",
    "nakit akış",
    "finansal borç",
    "özkaynak",
    "net dönem kâr",
    "net kâr",
    "hasılat",
    "favök",
    "faaliyet kâr",
    "brüt kâr",
    "kur farkı",
    "dipnot",
    "risk",
    "temettü",
)


def _split_paragraphs(text: str) -> list[str]:
    # Boş satır ya da tek satırlık kırılımlara göre kabaca böl.
    chunks = re.split(r"\n\s*\n", text)
    paras: list[str] = []
    for c in chunks:
        c = re.sub(r"[ \t]+", " ", c).strip()
        if c:
            paras.append(c)
    return paras


def extract_relevant(
    text: str,
    keywords: tuple[str, ...],
    *,
    max_chars: int = 8000,
    context_after: int = 1,
) -> str:
    """Anahtar kelime içeren paragrafları (+ sonraki `context_after` paragraf) süzer."""
    if not text:
        return ""
    paras = _split_paragraphs(text)
    if not paras:
        return text[:max_chars]

    folded_paras = [_tr_fold(p) for p in paras]
    folded_keywords = [_tr_fold(k) for k in keywords]
    keep: list[int] = []
    picked: set[int] = set()
    for i, folded in enumerate(folded_paras):
        if any(k in folded for k in folded_keywords):
            for j in range(i, min(i + 1 + context_after, len(paras))):
                if j not in picked:
                    picked.add(j)
                    keep.append(j)

    keep.sort()
    selected = [paras[i] for i in keep]
    if not selected:
        # Hiç eşleşme yoksa baştan bir miktar al (belge kısa/yapısızsa).
        selected = paras

    out: list[str] = []
    total = 0
    for p in selected:
        if total + len(p) > max_chars:
            out.append(p[: max_chars - total])
            break
        out.append(p)
        total += len(p) + 2
    return "\n\n".join(out).strip()
