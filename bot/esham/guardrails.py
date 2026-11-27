"""Yayın öncesi guardrail'lar.

Eval katmanındaki güvenlik kontrolleri burada yayın hattına BLOKLAYICI olarak takılır:
kötü çıktı sadece ölçülmez, gerçekten yayına/paylaşıma gitmesi engellenir.

Mod (ESHAM_GUARDRAILS):
    enforce  — ihlalde yayınlama/gönderme (varsayılan)
    warn     — ihlali logla ama devam et
    off      — kontrol yok
"""
from __future__ import annotations

from .config import get_logger, settings
from .evals.checks import contains_investment_advice
from .neutral import find_banned
from .translation import is_mostly_english

log = get_logger(__name__)

TWEET_LIMIT = 280


def _mode() -> str:
    m = settings.guardrails_mode
    return m if m in ("enforce", "warn", "off") else "enforce"


def validate_report(title: str, summary: str, body: str) -> list[str]:
    """Bir raporun metnini denetler; ihlal listesi döner (boşsa temiz).

    Başlık KAP bildiriminin kendi başlığıdır (olgusal alıntı); yasaklı kalıp denetimi özet ve gövdeye uygulanır.
    """
    text = " ".join([title or "", summary or "", body or ""])
    violations: list[str] = []
    if contains_investment_advice(text):
        violations.append("örtük/açık yatırım tavsiyesi kalıbı")
    banned = find_banned(f"{summary or ''}\n{body or ''}")
    if banned:
        violations.append(f"piyasa yargısı/tavsiye kalıbı: {', '.join(sorted(set(banned))[:5])}")
    if is_mostly_english(title):
        violations.append(f"başlık Türkçe değil / İngilizce kaldı: {title[:50]}")
    return violations


def validate_tweet(text: str) -> list[str]:
    violations: list[str] = []
    if len(text) > TWEET_LIMIT:
        violations.append(f"tweet {TWEET_LIMIT} karakteri aşıyor ({len(text)})")
    if contains_investment_advice(text):
        violations.append("örtük/açık yatırım tavsiyesi kalıbı")
    banned = find_banned(text)
    if banned:
        violations.append(f"piyasa yargısı/tavsiye kalıbı: {', '.join(sorted(set(banned))[:5])}")
    if is_mostly_english(text):
        violations.append(f"tweet Türkçe değil / İngilizce kaldı: {text[:50]}")
    return violations


def allow(context: str, violations: list[str]) -> bool:
    """Guardrail kararı. True=yayınla/gönder, False=engelle.

    enforce+ihlal → False (engelle); warn → logla, True; off → True.
    """
    if not violations:
        return True
    mode = _mode()
    detail = "; ".join(violations)
    if mode == "off":
        return True
    if mode == "warn":
        log.warning("Guardrail (warn) — %s: %s", context, detail)
        return True
    log.error("Guardrail ENGELLEDİ — %s: %s", context, detail)
    return False
