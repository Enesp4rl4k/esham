"""Sayı ve kısaltma farkında cümle bölme / güvenli kısaltma — TEK kaynak.

Eski kod özet ve tweet için ``text.split('.')[0]`` kullanıyordu; Türkçe biçimli sayıdaki binlik noktada
("7.266,17") cümleyi keserek "S&P 500 +1,16% yükseldi (7" gibi yarım özet yayınladı.

Kural (``web/src/lib/neutral.ts`` ``splitSentences`` ile birebir aynı; ortak vektörler
``web/src/lib/neutral-vectors.json`` → ``strip`` ve ``sentences``):

1. Aday sınır: ``.``, ``!``, ``?`` veya ``…`` (ardından isteğe bağlı tek kapanış ``)`` / tırnak) ARDINDAN en az
   bir boşluk. Noktadan sonra boşluk yoksa sınır
   değildir — böylece "7.266,17", "27.11.2026", "08.30", "www.kap.org.tr" hiç bölünmez.
2. Aday sınır şu durumlarda birleştirilir (cümle sonu sayılmaz):
   - sonraki parça küçük harfle başlıyorsa ("6. madde", "vb. gibi"),
   - önceki parçanın son kelimesi bilinen kısaltmaysa (``neutral-rules.json`` → ``sentences.abbreviations``:
     "Ltd.", "Şti.", "vb." …) ya da büyük harf + nokta dizisiyse ("A.Ş.", "T.C.", "A."),
   - önceki parçada kapanmamış parantez varsa (parantez içi bölünmez),
   - önceki parça yalnız bir sıra numarasıysa ("1. Madde onaylandı.").
"""
from __future__ import annotations

import json
import re
from pathlib import Path

_RULES_PATH = Path(__file__).resolve().parents[2] / "web" / "src" / "lib" / "neutral-rules.json"
ABBREVIATIONS: frozenset[str] = frozenset(
    json.loads(_RULES_PATH.read_text(encoding="utf-8"))["sentences"]["abbreviations"]
)

_CANDIDATE_RE = re.compile(r"(?:(?<=[.!?…])|(?<=[.!?…][)\"”’»])) +")
_ORDINAL_RE = re.compile(r"\d{1,3}\.")
_TRIM_LEAD = "(\"'“‘«["


def _last_token(piece: str) -> str:
    parts = piece.rstrip().split()
    return parts[-1].lstrip(_TRIM_LEAD) if parts else ""


def _is_initials(token: str) -> bool:
    """'A.', 'A.Ş.', 'T.C.' gibi: bir ya da daha çok (büyük harf + nokta)."""
    if len(token) < 2 or len(token) % 2:
        return False
    return all(token[i].isupper() and token[i + 1] == "." for i in range(0, len(token), 2))


def _joins(prev: str, nxt: str) -> bool:
    if nxt[:1].islower():
        return True
    tok = _last_token(prev)
    if tok in ABBREVIATIONS or _is_initials(tok):
        return True
    if _ORDINAL_RE.fullmatch(prev.strip()):  # cümle başı sıra numarası: "1. Madde onaylandı."
        return True
    return prev.count("(") > prev.count(")")


def split_sentences(text: str) -> list[str]:
    """Tek satırlık metni cümlelere böler (boş parça döndürmez)."""
    out: list[str] = []
    for piece in _CANDIDATE_RE.split(text or ""):
        if not piece:
            continue
        if out and _joins(out[-1], piece):
            out[-1] = f"{out[-1]} {piece}"
        else:
            out.append(piece)
    return out


def first_sentence(text: str) -> str:
    """İlk cümle (satır sonları boşluk sayılır). Boş girdi → ''."""
    flat = " ".join((text or "").split())
    parts = split_sentences(flat)
    return parts[0].strip() if parts else ""


# ---- denetim yardımcıları (testler ve güvenli kısaltma için) ---------------------------------

def parens_balanced(text: str) -> bool:
    depth = 0
    for ch in text:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth < 0:
                return False
    return depth == 0


def safe_truncate(text: str, limit: int, ellipsis: str = "…") -> str:
    """En çok ``limit`` karakter: kelime sınırında keser, yarım sayı ve açık parantez bırakmaz.

    Önce cümle sınırında kesmeyi dener; olmazsa kelime sınırına iner, kapanmamış parantezi ve sondaki
    noktalama/ayırıcıyı atar. Metin zaten sığıyorsa aynen döner.
    """
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    budget = max(1, limit - len(ellipsis))
    acc = ""
    for s in split_sentences(text):
        cand = f"{acc} {s}".strip()
        if len(cand) > limit:
            break
        acc = cand
    if acc:
        return acc
    cut = text[:budget]
    if " " in cut and not text[budget:budget + 1].isspace():
        cut = cut.rsplit(" ", 1)[0]
    while cut and not parens_balanced(cut):
        idx = cut.rfind("(")
        if idx < 0:
            break
        cut = cut[:idx]
    cut = cut.rstrip(" ,.;:—-–(")
    return f"{cut}{ellipsis}" if cut else ellipsis
