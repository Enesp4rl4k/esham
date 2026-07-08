"""Ortak LLM istemcisi — görev bazlı provider seçimi.

Öncelik sırası (tüm task_type'lar için): Groq primary → Gemini fallback.

- "filter": Groq fast (llama-3.1-8b-instant) → Groq default → Gemini fallback
- diğer tüm ("analysis", "tweet", "json", "default"):
    Groq default (llama-3.3-70b-versatile) → Gemini fallback

Groq'un ücretsiz kotası dakikada 30 istek — Gemini'den çok daha cömert.
Gemini yalnızca Groq rate-limit (429) veya hata verince devreye girer.
Her ikisi de yoksa None döner, pipeline şablona düşer.

Groq OpenAI-uyumlu API kullandığı için `groq` paketi gerekir:
    pip install groq==0.13.1

Rate-limit (429) yönetimi:
- Groq 429 alırsa Gemini'ye düşer
- Her ikisi de başarısız olursa None döner
"""
from __future__ import annotations

import json
import re

from ..config import get_logger, settings

log = get_logger(__name__)


# ── Groq backend ──────────────────────────────────────────────────────────────

class _GroqBackend:
    """Groq API wrapper — llama-3.3-70b-versatile varsayılan."""

    def __init__(self, model: str) -> None:
        self.model = model
        self._client = None
        if not settings.groq_api_key:
            return
        try:
            from groq import Groq
            self._client = Groq(api_key=settings.groq_api_key)
            log.info("Groq istemcisi hazır (model: %s).", model)
        except Exception as exc:
            log.warning("Groq istemcisi kurulamadı (%s).", exc)

    @property
    def enabled(self) -> bool:
        return self._client is not None

    def generate(self, prompt: str, *, max_tokens: int = 8192, temperature: float = 0.4) -> str | None:
        if not self._client:
            return None
        try:
            resp = self._client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                temperature=temperature,
            )
            text = resp.choices[0].message.content or ""
            return text.strip() or None
        except Exception as exc:
            msg = str(exc)
            is_rate = "429" in msg or "rate_limit" in msg.lower() or "rate limit" in msg.lower()
            is_too_large = "413" in msg or "payload too large" in msg.lower()
            if is_rate:
                log.warning("Groq rate-limit (429); Gemini fallback'e geçiliyor.")
            elif is_too_large:
                # Prompt çok büyük — kısaltarak tek seferlik tekrar dene
                if len(prompt) > 12000:
                    log.warning("Groq 413: prompt çok büyük (%d karakter); kısaltılıyor.", len(prompt))
                    try:
                        resp = self._client.chat.completions.create(
                            model=self.model,
                            messages=[{"role": "user", "content": prompt[:12000]}],
                            max_tokens=min(max_tokens, 4096),
                            temperature=temperature,
                        )
                        text = resp.choices[0].message.content or ""
                        return text.strip() or None
                    except Exception:
                        pass
                log.error("Groq 413: payload hatası; Gemini fallback'e geçiliyor.")
            else:
                log.error("Groq üretim hatası: %s", exc)
            return None


# ── Gemini backend ────────────────────────────────────────────────────────────

class _GeminiBackend:
    """Gemini API wrapper — fallback provider."""

    def __init__(self, model: str) -> None:
        self.model = model
        self._client = None
        if not settings.gemini_api_key:
            return
        try:
            from google import genai
            self._client = genai.Client(api_key=settings.gemini_api_key)
        except Exception as exc:
            log.warning("Gemini istemcisi kurulamadı (%s).", exc)

    @property
    def enabled(self) -> bool:
        return self._client is not None

    def _config(self, *, as_json: bool = False, disable_thinking: bool = False):
        from google.genai import types
        kwargs: dict = {"max_output_tokens": 8192, "temperature": 0.4}
        if as_json:
            kwargs["response_mime_type"] = "application/json"
        if disable_thinking:
            kwargs["thinking_config"] = types.ThinkingConfig(thinking_budget=0)
        return types.GenerateContentConfig(**kwargs)

    def generate(self, prompt: str, *, disable_thinking: bool = False,
                 max_tokens: int = 8192) -> str | None:
        if not self._client:
            return None
        try:
            resp = self._client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=self._config(disable_thinking=disable_thinking),
            )
            return (resp.text or "").strip() or None
        except Exception as exc:
            msg = str(exc)
            is_rate = "429" in msg or "RESOURCE_EXHAUSTED" in msg
            if is_rate:
                log.warning("Gemini rate-limit (429); Groq fallback'e geçiliyor.")
            else:
                log.error("Gemini üretim hatası: %s", exc)
            return None


# ── Ana LlmClient ─────────────────────────────────────────────────────────────

# ── Görev türleri ──────────────────────────────────────────────────────────────
# Her görev türü için hangi Groq modeli kullanılacağını belirler.
# "filter" görevleri hızlı/ucuz modelle, "analysis" görevleri büyük modelle yapılır.
TASK_MODEL_MAP: dict[str, str] = {
    "filter":   "llama-3.1-8b-instant",    # Haber önem filtresi — binary karar, hızlı
    "tweet":    "llama-3.3-70b-versatile",  # Tweet üretimi — kaliteli metin
    "analysis": "llama-3.3-70b-versatile",  # Rapor analizi — uzun form
    "json":     "llama-3.3-70b-versatile",  # JSON üretimi
    "default":  "llama-3.3-70b-versatile",  # Varsayılan
}


# Groq primary tüm görevler için — dakikada 30 req ücretsiz kota, Gemini'den çok cömert.
# Gemini fallback olarak kalır: Groq rate-limit veya hata verirse devreye girer.
_GEMINI_PRIMARY_TASKS: frozenset[str] = frozenset()  # artık hiçbir görev için Gemini primary değil


class LlmClient:
    """Görev bazlı provider seçimi: Groq primary, Gemini fallback (tüm görevler için).

    task_type bazlı öncelik:
    - "filter": Groq fast (llama-3.1-8b-instant) → Groq default → Gemini fallback
    - diğer tüm ("analysis", "tweet", "json", "default"): Groq default → Gemini fallback

    Groq rate-limit (429) veya hata verirse Gemini devreye girer.
    Her ikisi de yoksa None döner, pipeline şablona düşer.
    """

    def __init__(
        self,
        model_name: str | None = None,
        *,
        max_output_tokens: int = 8192,
        temperature: float = 0.4,
    ) -> None:
        self.max_output_tokens = max_output_tokens
        self.temperature = temperature
        self.model_name = model_name or settings.groq_model

        self._groq_default = _GroqBackend(settings.groq_model)
        self._groq_fast = _GroqBackend(settings.groq_tweet_model)  # llama-3.1-8b-instant
        self._gemini = _GeminiBackend(model_name or settings.gemini_model)

        if self._groq_default.enabled and self._gemini.enabled:
            log.info(
                "LLM: Groq primary (%s) + Gemini fallback (%s) — çapraz fallback aktif.",
                settings.groq_model, settings.gemini_model,
            )
        elif self._groq_default.enabled:
            log.info(
                "LLM: Groq only (%s) + fast (%s) — Gemini key yok",
                settings.groq_model, settings.groq_tweet_model,
            )
        elif self._gemini.enabled:
            log.info("LLM: Gemini only (%s) — Groq key yok", settings.gemini_model)
        else:
            log.warning("LLM: API key yok; şablon üretimi kullanılacak.")

    def _groq_for_task(self, task_type: str) -> "_GroqBackend":
        """Görev türüne göre uygun Groq backend'ini döner."""
        if task_type == "filter":
            return self._groq_fast if self._groq_fast.enabled else self._groq_default
        return self._groq_default

    @property
    def enabled(self) -> bool:
        return self._groq_default.enabled or self._gemini.enabled

    def generate(self, prompt: str, *, disable_thinking: bool = False,
                 task_type: str = "default") -> str | None:
        """Görev türüne göre provider seçerek üretim yapar.

        task_type:
        - "filter" → Groq fast (llama-3.1-8b-instant) primary, Gemini fallback
        - diğer tüm görevler → Groq default (llama-3.3-70b-versatile) primary, Gemini fallback
        """
        if not self.enabled:
            return None

        if task_type in _GEMINI_PRIMARY_TASKS:
            # Gemini primary — analysis/tweet için daha cömert kota
            if self._gemini.enabled:
                result = self._gemini.generate(
                    prompt,
                    disable_thinking=disable_thinking,
                    max_tokens=self.max_output_tokens,
                )
                if result:
                    return result
                log.info("Gemini başarısız/boş [task=%s]; Groq fallback deneniyor.", task_type)

            # Gemini fallback (artık bu dal hiç çalışmaz çünkü _GEMINI_PRIMARY_TASKS boş)
            groq = self._groq_for_task(task_type)
            if groq.enabled:
                return groq.generate(
                    prompt,
                    max_tokens=self.max_output_tokens,
                    temperature=self.temperature,
                )
            return None

        else:
            # Groq primary — tüm görevler için (analysis, tweet, filter, json, default)
            groq = self._groq_for_task(task_type)
            if groq.enabled:
                result = groq.generate(
                    prompt,
                    max_tokens=self.max_output_tokens,
                    temperature=self.temperature,
                )
                if result:
                    return result
                log.info("Groq başarısız/boş [task=%s]; Gemini fallback deneniyor.", task_type)

            # Gemini fallback — Groq rate-limit veya hata verince devreye girer
            if self._gemini.enabled:
                return self._gemini.generate(
                    prompt,
                    disable_thinking=disable_thinking,
                    max_tokens=self.max_output_tokens,
                )
            return None

    def generate_json(self, prompt: str) -> dict | None:
        """JSON üretim — Groq önce (text modu), sonra Gemini (native JSON)."""
        if not self.enabled:
            return None

        # Groq'ta JSON modu yok, prompt'a ekle
        if self._groq_default.enabled:
            json_prompt = (
                prompt
                + "\n\nÖNEMLİ: Yanıtın sadece geçerli JSON olsun. "
                "Başka metin, açıklama veya markdown kodu ekleme."
            )
            raw = self._groq_default.generate(
                json_prompt,
                max_tokens=self.max_output_tokens,
                temperature=0.1,
            )
            if raw:
                result = self._parse_json(raw)
                if result is not None:
                    return result
            log.info("Groq JSON parse başarısız; Gemini fallback deneniyor.")

        # Gemini native JSON modu
        if self._gemini.enabled and self._gemini._client:
            try:
                from google.genai import types
                resp = self._gemini._client.models.generate_content(
                    model=self._gemini.model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        max_output_tokens=self.max_output_tokens,
                        temperature=0.1,
                        response_mime_type="application/json",
                    ),
                )
                return self._parse_json((resp.text or "").strip())
            except Exception as exc:
                log.error("Gemini JSON üretim hatası: %s", exc)
        return None

    @staticmethod
    def _parse_json(text: str) -> dict | None:
        if not text:
            return None
        text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
        try:
            data = json.loads(text)
            return data if isinstance(data, dict) else None
        except json.JSONDecodeError:
            start, end = text.find("{"), text.rfind("}")
            if 0 <= start < end:
                try:
                    data = json.loads(text[start: end + 1])
                    return data if isinstance(data, dict) else None
                except json.JSONDecodeError:
                    pass
        log.warning("LLM çıktısı JSON olarak ayrıştırılamadı.")
        return None
