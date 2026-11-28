"""Yayın kapısı kuralları, Python tarafı.

- ``distinct_summary`` web'deki ``distinctSummary`` ile aynı ortak vektörlerden geçer
  (``web/src/lib/summary-vectors.json``; TS: ``web/src/lib/report-gate.test.mjs``).
- KAP olgu bloğu (``filing_facts_markdown``) bildirim gövdesinden HİÇBİR rakam taşımaz.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from esham.ai.analyzer import filing_facts_markdown
from esham.neutral import NOTE_AMOUNT_MISSING, distinct_summary

ROOT = Path(__file__).resolve().parents[2]
CASES = json.loads((ROOT / "web" / "src" / "lib" / "summary-vectors.json").read_text(encoding="utf-8"))["cases"]


@pytest.mark.parametrize("case", CASES, ids=[c["summary"] or "<boş>" for c in CASES])
def test_shared_vectors_distinct_summary(case):
    assert distinct_summary(case["title"], case["summary"]) == case["expected"]


BODIES = [
    "Şirketimiz 1.250.000.000 TL tutarında sözleşme imzalamıştır. Sözleşme bedeli %12,5 artmıştır.",
    "1 TL nominal değerli 100.000 adet pay ortalama 42,10 TL fiyattan geri alınmıştır; toplam 4.210.000 TL.",
    "USD 750,000,000 tutarında tahvil ihracı tamamlanmış, kupon oranı 9.875 olarak belirlenmiştir (2031 vadeli).",
]


@pytest.mark.parametrize("body", BODIES)
def test_kap_facts_block_carries_no_figures_from_filing_body(body):
    title, company, ticker, dtype, index, date = (
        "X A.Ş.: Özel Durum Açıklaması", "X A.Ş.", "XXXXX", "Özel Durum Açıklaması (Genel)", "1700856", "2026-11-04",
    )
    facts = filing_facts_markdown(company, ticker, title, dtype, body, index, date=date)
    for num in re.findall(r"\d[\d.,]*\d|\d", body):
        if len(num) >= 3:  # tek/iki haneli sayılar bildirim no/tarih içinde geçebilir; aşağıdaki denetim kapsar
            assert num not in facts, num
    rest = facts
    for q in (title, company, ticker, dtype, date, f"https://www.kap.org.tr/tr/Bildirim/{index}", f"#{index}"):
        rest = rest.replace(q, "")
    assert re.findall(r"\d", rest) == [], rest
    assert f"- **Tutar:** {NOTE_AMOUNT_MISSING}" in facts
