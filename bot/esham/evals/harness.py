"""Eval koşum motoru: vaka çalıştırır, kontrolleri uygular, gecikme/maliyet ölçer.

Bir `EvalCase`: adı, çıktı üreten bir fonksiyon (süresi ölçülür) ve kontrol listesi.
Rapor bir puan kartı basar ve tüm vakalar geçti mi bilgisini döner (CI kapısı için).
"""
from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from ..config import get_logger

log = get_logger(__name__)

# Kaba maliyet tahmini için ~4 karakter/token, örnek fiyat (USD / 1M token, flash-lite).
_CHARS_PER_TOKEN = 4
_USD_PER_MTOK = 0.30


@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str = ""


@dataclass
class CaseResult:
    name: str
    checks: list[CheckResult]
    latency_ms: float = 0.0
    est_tokens: int = 0
    error: str = ""

    @property
    def passed(self) -> bool:
        return not self.error and all(c.passed for c in self.checks)

    @property
    def est_cost_usd(self) -> float:
        return self.est_tokens / 1_000_000 * _USD_PER_MTOK


@dataclass
class EvalCase:
    name: str
    produce: Callable[[], Any]
    checks: list[Callable[[Any], CheckResult]]
    # Maliyet tahmini için girdi metni (opsiyonel).
    cost_text: str = ""


@dataclass
class SuiteResult:
    name: str
    cases: list[CaseResult] = field(default_factory=list)

    @property
    def passed(self) -> int:
        return sum(1 for c in self.cases if c.passed)

    @property
    def total(self) -> int:
        return len(self.cases)

    @property
    def all_passed(self) -> bool:
        return self.passed == self.total

    @property
    def avg_latency_ms(self) -> float:
        return sum(c.latency_ms for c in self.cases) / self.total if self.cases else 0.0

    @property
    def total_cost_usd(self) -> float:
        return sum(c.est_cost_usd for c in self.cases)


def run_case(case: EvalCase) -> CaseResult:
    start = time.perf_counter()
    try:
        output = case.produce()
    except Exception as exc:  # üretim hatası vakayı düşürür ama süiti değil
        return CaseResult(case.name, [], (time.perf_counter() - start) * 1000, error=str(exc))
    latency = (time.perf_counter() - start) * 1000

    checks = [chk(output) for chk in case.checks]
    est_tokens = (len(case.cost_text) + len(str(output))) // _CHARS_PER_TOKEN
    return CaseResult(case.name, checks, latency, est_tokens)


def run_suite(name: str, cases: list[EvalCase]) -> SuiteResult:
    return SuiteResult(name, [run_case(c) for c in cases])


def print_report(suites: list[SuiteResult]) -> bool:
    all_ok = True
    for suite in suites:
        print(f"\n■ {suite.name}  ({suite.passed}/{suite.total} geçti, "
              f"ort. {suite.avg_latency_ms:.0f}ms, ~${suite.total_cost_usd:.5f})")
        for case in suite.cases:
            mark = "✓" if case.passed else "✗"
            print(f"  {mark} {case.name}  [{case.latency_ms:.0f}ms]")
            if case.error:
                print(f"      HATA: {case.error}")
            for chk in case.checks:
                if not chk.passed:
                    print(f"      ✗ {chk.name}: {chk.detail}")
        all_ok = all_ok and suite.all_passed

    total_pass = sum(s.passed for s in suites)
    total = sum(s.total for s in suites)
    print(f"\n{'=' * 48}")
    print(f"SONUÇ: {total_pass}/{total} vaka geçti — {'BAŞARILI ✓' if all_ok else 'BAŞARISIZ ✗'}")
    return all_ok
