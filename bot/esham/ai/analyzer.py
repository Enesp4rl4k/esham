"""Gemini tabanlı analiz ve içerik üretimi.

Tasarım ilkeleri:
- API anahtarı yoksa AI devre dışı kalır ama pipeline çökmemesi için deterministik
  şablon üretimine düşülür (graceful degradation).
- Ağ/model hataları yakalanır ve loglanır (LlmClient içinde).
"""
from __future__ import annotations

from ..config import get_logger, settings
from ..sources import MarketSnapshot
from .client import LlmClient

log = get_logger(__name__)


class MarketAIAnalyzer:
    def __init__(self) -> None:
        self.client = LlmClient(settings.gemini_model, max_output_tokens=2048, temperature=0.4)
        if not self.client.enabled:
            log.warning("AI devre dışı; şablon üretimi kullanılacak.")

    def analyze_macro_impact(self, news_text: str) -> str:
        prompt = f"""
Sen profesyonel ve öngörülü bir portföy yöneticisisin. Aşağıdaki makroekonomik
gelişmeyi oku ve bunun Borsa İstanbul (BIST), ons altın ve kripto paralar üzerindeki
olası etkilerini çok kısa, net ve anlaşılır bir dille (yatırım tavsiyesi vermeden)
özetle.

Haber: {news_text}
"""
        return self.client.generate(prompt) or "🤖 Yapay zeka yorumu şu an üretilemedi."

    def generate_morning_report(self, snapshot: MarketSnapshot) -> str:
        """Sabah bülteninin markdown gövdesini üretir."""
        from datetime import datetime, timedelta, timezone

        today = datetime.now(timezone(timedelta(hours=3)))
        date_str = today.strftime("%d.%m.%Y")
        context = self._snapshot_context(snapshot)
        prompt = f"""
Aracı kurum kalitesinde, Türkçe bir "sabah piyasa bülteni" yaz. Bugünün tarihi: {date_str}.
Markdown kullan (## başlıklar, listeler, gerekirse tablo). Yatırım tavsiyesi verme;
nesnel ve öngörülü bir dil kullan. ASLA köşeli parantezli yer tutucu ([...]) yazma;
elindeki verilerle yaz. En üste ## başlık koyma, doğrudan bölümlerle başla.
Aşağıdaki verilere dayan:

{context}

Bülten şu bölümleri içersin: Genel Görünüm, Öne Çıkanlar, Küresel Makro,
Değerlendirme. Kısa ve okunur olsun.
"""
        body = self.client.generate(prompt)
        if body:
            return body
        log.info("AI kapalı/başarısız; şablon sabah raporu üretiliyor.")
        return self._template_morning_report(snapshot)

    def analyze_balance_sheet_red_flags(self, financial_data_text: str) -> str:
        prompt = f"""
Aşağıdaki finansal tablo özetini/dipnotlarını incele. Şirketin finansal sağlığıyla
ilgili küçük yatırımcının gözden kaçırabileceği 3 olumlu noktayı (✅) ve 3 gizli
tehlikeyi/riskli noktayı (🚨) markdown listesi olarak yaz.

Veri: {financial_data_text}
"""
        return self.client.generate(prompt) or "Analiz şu an üretilemedi."

    # ---- yardımcılar -----------------------------------------------------------

    @staticmethod
    def _snapshot_context(snapshot: MarketSnapshot) -> str:
        lines: list[str] = []
        if snapshot.bist:
            b = snapshot.bist
            lines.append(f"- BIST {b.index}: {b.price} ({b.change}), hacim {b.volume}")
        for ev in snapshot.calendar:
            lines.append(
                f"- Takvim {ev.time} {ev.country}: {ev.event} (önem: {ev.importance}, beklenti: {ev.forecast})"
            )
        for d in snapshot.disclosures:
            lines.append(f"- KAP: {d.title} [{d.disclosure_type}]")
        return "\n".join(lines) or "- Veri bulunamadı."

    @staticmethod
    def _template_morning_report(snapshot: MarketSnapshot) -> str:
        b = snapshot.bist
        header = "## Genel Görünüm\n\n"
        if b:
            header += (
                f"BIST {b.index} son işlemde **{b.price}** seviyesinde ({b.change}), "
                f"hacim {b.volume}.\n\n"
            )
        else:
            header += "Endeks verisi şu an alınamadı.\n\n"

        cal = "## Küresel Makro & Takvim\n\n"
        if snapshot.calendar:
            cal += "| Saat | Ülke | Olay | Beklenti |\n| --- | --- | --- | --- |\n"
            for ev in snapshot.calendar:
                cal += f"| {ev.time} | {ev.country} | {ev.event} | {ev.forecast} |\n"
            cal += "\n"
        else:
            cal += "Bugün için öne çıkan veri bulunmuyor.\n\n"

        kap = ""
        if snapshot.disclosures:
            kap = "## KAP Öne Çıkanlar\n\n"
            for d in snapshot.disclosures:
                kap += f"- **{d.title}** — {d.disclosure_type}\n"
            kap += "\n"

        footer = (
            "## Değerlendirme\n\n"
            "Bu bülten otomatik olarak derlenmiştir. Küresel risk iştahı ve yurt içi "
            "veri akışı gün içi yönü belirleyecek başlıklar olmayı sürdürüyor."
        )
        return header + cal + kap + footer
