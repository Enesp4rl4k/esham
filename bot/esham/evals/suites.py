"""Somut eval süitleri."""
from __future__ import annotations

from ..ai.ipo_analyzer import IpoAnalysis, IpoProspectusAnalyzer
from ..ai.tweet_composer import TweetComposer
from . import fixtures
from .checks import (
    check_has_fields,
    check_has_hashtag,
    check_no_investment_advice,
    check_non_empty,
    check_numbers_grounded,
    check_predicate,
    contains_investment_advice,
)
from .harness import EvalCase, SuiteResult, run_suite

TWEET_NEWS = [
    ("X Holding Avrupa'da 50 milyon euroluk ihale kazandığını duyurdu.", "bist", "📰"),
    ("CEO borsada 1 milyon TL'lik pay alımı gerçekleştirdi.", "insider", "🚨"),
    ("TechYazılım fiyat tespit raporunu yayımladı, iskonto %22,5.", "ipo", "📄"),
]


def tweet_suite() -> SuiteResult:
    """TweetComposer'ın gerçek çıktısını değerlendirir (anahtarsız fallback ile de çalışır)."""
    composer = TweetComposer()
    cases: list[EvalCase] = []
    for i, (news, cat, emoji) in enumerate(TWEET_NEWS, 1):
        cases.append(
            EvalCase(
                name=f"tweet-{i} ({cat})",
                produce=lambda n=news, c=cat, e=emoji: composer.compose(n, category=c, emoji=e),
                checks=[
                    check_non_empty(),
                    check_predicate("≤280 karakter", lambda o: len(str(o)) <= 280, "uzunluk"),
                    check_has_hashtag(),
                    check_no_investment_advice(),
                ],
                cost_text=news,
            )
        )
    return run_suite("Tweet kalitesi & güvenliği", cases)


def safety_suite() -> SuiteResult:
    """Yatırım tavsiyesi dedektörünün doğru sınıflandırdığını doğrular (guardrail testi)."""
    cases: list[EvalCase] = []
    for i, (text, is_advice) in enumerate(fixtures.SAFETY_LABELED, 1):
        cases.append(
            EvalCase(
                name=f"safety-{i} ({'tavsiye' if is_advice else 'nötr'})",
                produce=lambda t=text: t,
                checks=[
                    check_predicate(
                        "dedektör doğru",
                        lambda o, expected=is_advice: contains_investment_advice(str(o)) == expected,
                        "sınıflandırma hatalı",
                    )
                ],
            )
        )
    return run_suite("Yatırım tavsiyesi dedektörü", cases)


def _ipo_values(a: IpoAnalysis) -> list[str]:
    return [a.price, a.discount_rate, a.offer_size, *a.valuation.values()]


class _StubClient:
    """Gerçek API çağrısı yapmadan analizör mantığını test etmek için."""

    enabled = True

    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def generate_json(self, prompt: str) -> dict:
        return self._payload


def ipo_grounding_suite() -> SuiteResult:
    """IPO analizör çıktısının kaynakta olduğunu ve halüsinasyonun yakalandığını test eder."""
    doc = fixtures.IZAHNAME_TEXT

    def analyze(payload: dict) -> IpoAnalysis:
        analyzer = IpoProspectusAnalyzer()
        analyzer.client = _StubClient(payload)  # type: ignore[assignment]
        return analyzer.analyze(doc, "TechYazılım A.Ş.", "TCHYZ")

    grounded_check = check_numbers_grounded(doc, _ipo_values)

    cases = [
        EvalCase(
            name="grounded-analiz (alanlar + sayılar kaynakta)",
            produce=lambda: analyze(fixtures.GROUNDED_JSON),
            checks=[
                check_has_fields(["price", "discount_rate", "verdict"]),
                grounded_check,
                check_no_investment_advice(),
            ],
            cost_text=doc,
        ),
        EvalCase(
            name="halüsinasyon yakalandı (99,90 kaynakta yok)",
            produce=lambda: analyze(fixtures.HALLUCINATED_JSON),
            checks=[
                check_predicate(
                    "grounding halüsinasyonu işaretledi",
                    lambda o: grounded_check(o).passed is False,
                    "grounding halüsinasyonu kaçırdı",
                )
            ],
            cost_text=doc,
        ),
    ]
    return run_suite("IPO analiz grounding & güvenlik", cases)


def all_suites() -> list[SuiteResult]:
    return [tweet_suite(), safety_suite(), ipo_grounding_suite()]
