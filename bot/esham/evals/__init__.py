"""Eval katmanı — AI çıktılarının doğruluğunu, güvenliğini ve kalitesini ölçer.

"Great AI isn't just a powerful model. It's a well-run factory." Bu katman fabrikanın
kalite kontrolüdür: çıktı doğru mu, güvenli mi, kullanışlı mı; gecikme/maliyet ne?

Check'ler saf ve yeniden kullanılabilirdir; ileride yayın hattına guardrail olarak da
takılabilir (örn. örtük yatırım tavsiyesi içeren bir metni yayınlamadan engellemek).
"""
from .harness import CaseResult, CheckResult, EvalCase, SuiteResult, run_suite

__all__ = ["CaseResult", "CheckResult", "EvalCase", "SuiteResult", "run_suite"]
