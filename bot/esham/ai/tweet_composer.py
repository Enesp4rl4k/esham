"""Haberi tweet'e çeviren ucuz AI aracı.

Maliyet ilkeleri:
- En küçük/hızlı model (varsayılan `gemini-2.5-flash-lite`).
- Kısa prompt + düşük `max_output_tokens` → az token, az para.
- Anahtar yoksa veya hata olursa AI çağrısı YAPMADAN kural-tabanlı kısaltma (bedava).
- Çıktı her hâlükârda 280 karaktere sığdırılır (kelime sınırında kırpılır).
"""
from __future__ import annotations

import re

from ..config import get_logger, settings
from ..sentences import first_sentence, safe_truncate
from .client import LlmClient

log = get_logger(__name__)

TWEET_LIMIT = 280
# Güvenli hedef: model/karakter sayımı sapmalarına pay bırak.
SAFE_TARGET = 274

# Kategori bazlı hazır hashtag'ler (fallback ve ipucu için).
CATEGORY_HASHTAGS: dict[str, list[str]] = {
    "bist": ["#BIST100", "#Borsa"],
    "global": ["#Piyasalar", "#Makro"],
    "ipo": ["#HalkaArz", "#BIST"],
    "gundem": ["#Ekonomi", "#Gündem"],
    "insider": ["#BIST100", "#Hisse"],
}

_PROMPT = """Aşağıdaki haberi Türkçe, tek bir tweet'e dönüştür.
Kurallar:
- En fazla 280 karakter (hashtag dahil).
- Başında {emoji} emoji, çarpıcı ama abartısız ve nesnel.
- 1-2 ilgili hashtag ekle.
- Yatırım tavsiyesi verme. Sadece tweet metnini yaz, başka hiçbir şey yazma.

Haber: {news}"""


class TweetComposer:
    """Haber metnini paylaşılabilir bir tweet'e çevirir."""

    def __init__(self) -> None:
        # Kısa çıktı = düşük maliyet. Ucuz model + düşük token limiti.
        self.client = LlmClient(settings.tweet_model, max_output_tokens=120, temperature=0.4)
        if self.client.enabled:
            log.info("Tweet aracı hazır (ucuz model: %s)", settings.tweet_model)
        else:
            log.info("Tweet aracı: AI kapalı, kural-tabanlı kısaltma kullanılacak.")

    def compose(self, news: str, category: str = "gundem", emoji: str = "📰") -> str:
        news = (news or "").strip()
        if not news:
            return ""

        text = self._compose_ai(news, emoji) if self.client.enabled else None
        if not text:
            text = self._compose_fallback(news, category, emoji)

        return self._fit(text, category)

    # ---- AI yolu ---------------------------------------------------------------

    def _compose_ai(self, news: str, emoji: str) -> str | None:
        prompt = _PROMPT.format(emoji=emoji, news=news[:600])  # girdiyi de sınırla
        text = self.client.generate(prompt)
        if not text:
            return None
        # Model bazen tırnak/ön ek ekler; temizle.
        return text.strip().strip('"').strip("“”").strip() or None

    # ---- kural-tabanlı fallback (bedava) --------------------------------------

    def _compose_fallback(self, news: str, category: str, emoji: str) -> str:
        # İlk cümleyi al, gerekirse kısalt, kategori hashtag'lerini ekle.
        sentence = first_sentence(news)  # sayı/kısaltma farkında (A.Ş., 7.266,17)
        tags = " ".join(CATEGORY_HASHTAGS.get(category, CATEGORY_HASHTAGS["gundem"]))
        return f"{emoji} {sentence} {tags}".strip()

    # ---- karakter denetimi -----------------------------------------------------

    def _fit(self, text: str, category: str) -> str:
        text = re.sub(r"\s+", " ", text).strip()
        if len(text) <= TWEET_LIMIT:
            return text

        # Hashtag'leri ayır ki kırparken kaybolmasınlar.
        tags = re.findall(r"#\w+", text)
        body = re.sub(r"#\w+", "", text).strip()
        suffix = (" " + " ".join(tags[:2])) if tags else ""

        budget = SAFE_TARGET - len(suffix) - 1  # "…" için pay
        if budget < 0:
            budget = SAFE_TARGET
            suffix = ""
        return f"{safe_truncate(body, budget + 1)}{suffix}".strip()
