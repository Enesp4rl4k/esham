"""Yeniden kullanılabilir eval/guardrail kontrolleri.

Her factory bir `Check` döndürür: çıktıyı alıp `CheckResult` üreten bir fonksiyon.
"""
from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

from .harness import CheckResult

Check = Callable[[Any], CheckResult]

# Örtük/açık yatırım tavsiyesi kalıpları (finansal içerikte YASAK).
# "alım-satım", "pay alım" gibi meşru terimleri yakalamamak için buyruk/öneri kalıpları.
ADVICE_PATTERNS = [
    r"tavsiye ederim",
    r"öneririm",
    r"portföyünüze ekleyin",
    r"kesinlikle al(ın|manız)",
    r"kesinlikle sat(ın|manız)",
    r"mutlaka al",
    r"garanti (getiri|kazanç|kâr)",
    r"kesin kazanç",
    r"al[ıi]m tavsiyesi",
    r"sat[ıi]m tavsiyesi",
    r"bu (hisseyi|hisse senedini) al",
    r"şimdi al",
]
_ADVICE_RE = re.compile("|".join(ADVICE_PATTERNS), re.IGNORECASE)

_NUMBER_RE = re.compile(r"\d{1,3}(?:[.\s]\d{3})*(?:,\d+)?|\d+(?:[.,]\d+)?")


def contains_investment_advice(text: str) -> bool:
    return bool(_ADVICE_RE.search(text or ""))


def _numbers(text: str) -> set[str]:
    """Metindeki sayıları normalize ederek çıkarır (binlik/ondalık ayraçlar kaldırılır)."""
    out = set()
    for m in _NUMBER_RE.findall(text or ""):
        norm = m.replace(".", "").replace(" ", "").replace(",", "")
        if norm and norm.strip("0"):  # sadece anlamlı sayılar
            out.add(norm)
    return out


# ---- Check factory'leri ----------------------------------------------------


def check_non_empty() -> Check:
    def run(output: Any) -> CheckResult:
        ok = bool(str(output).strip())
        return CheckResult("boş değil", ok, "" if ok else "çıktı boş")
    return run


def check_tweet_limit(limit: int = 280) -> Check:
    def run(output: Any) -> CheckResult:
        n = len(str(output))
        return CheckResult(f"≤{limit} karakter", n <= limit, f"uzunluk={n}")
    return run


def check_has_hashtag() -> Check:
    def run(output: Any) -> CheckResult:
        ok = "#" in str(output)
        return CheckResult("hashtag var", ok)
    return run


def check_no_investment_advice() -> Check:
    def run(output: Any) -> CheckResult:
        bad = contains_investment_advice(str(output))
        detail = "" if not bad else "yatırım tavsiyesi kalıbı bulundu"
        return CheckResult("yatırım tavsiyesi yok", not bad, detail)
    return run


def check_has_fields(fields: list[str]) -> Check:
    def run(output: Any) -> CheckResult:
        missing = []
        for f in fields:
            val = getattr(output, f, None) if not isinstance(output, dict) else output.get(f)
            if val in (None, "", [], {}):
                missing.append(f)
        ok = not missing
        return CheckResult("alanlar dolu", ok, "" if ok else f"eksik: {missing}")
    return run


def check_numbers_grounded(source_text: str, getter: Callable[[Any], list[str]]) -> Check:
    """Çıktıdaki sayısal değerlerin kaynak belgede geçtiğini doğrular (halüsinasyon önler)."""
    source_numbers = _numbers(source_text)

    def run(output: Any) -> CheckResult:
        ungrounded = []
        for value in getter(output):
            for num in _numbers(value):
                if num not in source_numbers:
                    ungrounded.append(value)
                    break
        ok = not ungrounded
        detail = "" if ok else f"kaynakta olmayan değer(ler): {ungrounded}"
        return CheckResult("sayılar kaynakta", ok, detail)
    return run


def check_predicate(name: str, predicate: Callable[[Any], bool], detail: str = "") -> Check:
    def run(output: Any) -> CheckResult:
        return CheckResult(name, bool(predicate(output)), detail)
    return run
