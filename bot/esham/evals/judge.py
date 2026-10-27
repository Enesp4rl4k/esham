"""LLM-as-judge — analiz kalitesi puanı (nitel rubrik, kuantitatif çıktı).

Deterministik check'ler (`checks.py`) "bu çıktı hatalı mı?" der: tavsiye var mı,
sayılar kaynakta mı, biçim doğru mu. Bunlar bloklayıcıdır ve anahtarsız çalışır.
Judge ise "bu çıktı iyi mi?" sorusunu yanıtlar: üretilen analizi dört eksenli bir
rubriğe göre 0-5 puanlar ve her puanı gerekçelendirir.

- Anahtar **varsa** gerçek LLM çağrısı yapılır; `AnalysisJudge.enabled` True döner.
- Anahtar **yoksa** judge devre dışıdır (`enabled=False`) — eval süiti bunu
  "atlandı" olarak raporlar ve **CI kapısını kırmaz** (repo'nun zarif bozulma
  ilkesine uyar).

Puanlama rubriği (her eksen 0-5, tümü tamsayı):
  grounding     — sayısal/iddia niteliğindeki her şey kaynak belgede destekleniyor mu
  completeness  — fiyat, iskonto, büyüklük, fon kullanımı, çarpanlar, riskler dolu mu
  neutrality    — yatırım tavsiyesi/ton yok, nesnel ve SPK uyumlu dil
  clarity       — özet net, gereksiz jargon/yineleme yok, karar anlamlı
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field

from ..ai.client import LlmClient
from ..config import get_logger, settings

log = get_logger(__name__)

DIMS: tuple[str, ...] = ("grounding", "completeness", "neutrality", "clarity")

DIM_LABELS: dict[str, str] = {
    "grounding": "Kaynakta dayanak",
    "completeness": "Tam kapsamlı",
    "neutrality": "Nesnel / tavsiyesiz",
    "clarity": "Açıklık",
}

# Değerlendirme süiti bu ortalamanın altını başarısız sayar.
DEFAULT_THRESHOLD = 3.0

_PROMPT = """Sen sermaye piyasalarında içerik denetimi yapan kıdemli bir editör/yargıçsın.
Aşağıda bir belgeden (kaynak) üretilmiş yapılandırılmış analiz veriliyor.
Analizi aşağıdaki rubriğe göre 0-5 arası puanla ve her puanı bir cümleyle gerekçelendir.

RUBRİK (her eksen için 0-5 tam sayı):
- grounding: Analizdeki sayısal değerler ve iddialar kaynak belgede gerçekten geçiyor mu?
  (0 = ciddi halüsinasyon var, 3 = bazı unsurlar dayanaksız, 5 = tamamen kaynaklı)
- completeness: Fiyat, iskonto, halka arz büyüklüğü, fon kullanımı, değerleme
  çarpanları ve riskler gibi beklenen bölümler dolu ve anlamlı mı?
  (0 = neredeyse boş, 5 = tüm beklenen alanlar dolu)
- neutrality: Yatırım tavsiyesi, alım/satım çağrısı veya abartılı ton var mı?
  Nesnel, SPK uyumlu dil korunuyor mu? (0 = tavsiye/abartı var, 5 = tamamen nesnel)
- clarity: Özet ve değerlendirme net mi, yineleme/jargon fazla mı?
  (0 = anlaşılmaz, 5 = net ve okunabilir)

Kural: Bulamadığın/ölçemediğin bir ekseni uydurma; o eksen için ölçebildiğin kadar
ver. Yatırım tavsiyesi verme.

Kaynak belge (ilgili bölümler):
\"\"\"
{source}
\"\"\"

Analiz (JSON):
\"\"\"
{analysis}
\"\"\"

Yalnızca şu şemada JSON döndür:
{{
  "grounding": {{"score": 0-5, "reason": "tek cümle"}},
  "completeness": {{"score": 0-5, "reason": "tek cümle"}},
  "neutrality": {{"score": 0-5, "reason": "tek cümle"}},
  "clarity": {{"score": 0-5, "reason": "tek cümle"}}
}}"""


@dataclass
class JudgeResult:
    """Tek bir analizin yargı sonucu."""

    scores: dict[str, int] = field(default_factory=dict)
    reasons: dict[str, str] = field(default_factory=dict)
    ok: bool = False          # LLM çağrısı yapıldı ve şema doğru doldu mu
    skipped: bool = False     # anahtar yok → eval bunu "atlandı" sayar
    raw: str = ""

    @property
    def overall(self) -> float:
        if not self.scores:
            return 0.0
        return sum(self.scores.values()) / len(self.scores)

    def summary(self) -> str:
        parts = [f"{DIM_LABELS.get(k, k)}={v}" for k, v in self.scores.items()]
        return f"{self.overall:.1f}/5 ({' · '.join(parts)})"


class AnalysisJudge:
    """Bir LLM çıktısını rubriğe göre puanlar. Anahtar yoksa `enabled=False`."""

    def __init__(self, client: LlmClient | None = None, threshold: float = DEFAULT_THRESHOLD) -> None:
        self.client = client or LlmClient(max_output_tokens=2048, temperature=0.1)
        self.threshold = threshold

    @property
    def enabled(self) -> bool:
        return self.client.enabled

    def judge(self, source_text: str, analysis: object) -> JudgeResult:
        """`analysis`: `IpoAnalysis`/`FinancialAnalysis` ya da dict/str — JSON'a çevrilir."""
        if not self.enabled:
            log.info("LLM-as-judge devre dışı (API anahtarı yok); puan atlandı.")
            return JudgeResult(skipped=True)

        analysis_json = _as_pretty_json(analysis)
        data = self.client.generate_json(
            _PROMPT.format(source=source_text[:24000], analysis=analysis_json)
        )
        if not data:
            log.warning("Judge çağrısı boş/dönüşü JSON değil; puan atlandı.")
            return JudgeResult(skipped=True, raw=str(data))

        result = JudgeResult(raw=json.dumps(data, ensure_ascii=False))
        for dim in DIMS:
            entry = data.get(dim)
            if not isinstance(entry, dict):
                continue
            score = _as_score(entry.get("score"))
            if score is None:
                continue
            result.scores[dim] = score
            reason = entry.get("reason")
            if isinstance(reason, str) and reason.strip():
                result.reasons[dim] = reason.strip()

        # Dört eksenden en az üçü doluysa sonuç geçerli sayılır.
        result.ok = len(result.scores) >= 3
        if not result.ok:
            log.warning("Judge şeması eksik doldu (bulunan eksenler: %s).", list(result.scores))
        return result


def _as_score(value: object) -> int | None:
    try:
        n = int(round(float(str(value).strip())))
    except (TypeError, ValueError):
        return None
    return max(0, min(5, n))


def _as_pretty_json(analysis: object) -> str:
    """Analiz nesnesini judge prompt'u için okunabilir JSON'a çevirir."""
    if isinstance(analysis, str):
        return analysis[:8000]
    for conv in ("to_pdf_data", "to_dict"):
        fn = getattr(analysis, conv, None)
        if callable(fn):
            try:
                return json.dumps(fn(), ensure_ascii=False, indent=2, default=str)
            except Exception:  # noqa: BLE001 — dönüşüm başarısızsa genel yola düş
                break
    if isinstance(analysis, dict):
        return json.dumps(analysis, ensure_ascii=False, indent=2, default=str)
    return str(analysis)[:8000]


def score_analysis(source_text: str, analysis: object) -> JudgeResult:
    """Modül-seviyesi kısayol — yayın hattında da kullanılabilir."""
    return AnalysisJudge().judge(source_text, analysis)
