"""Ortak LLM istemcisi — Groq primary, Gemini fallback.

Öncelik sırası:
1. Groq (GROQ_API_KEY varsa) — dakikada 30, günde 14.400 ücretsiz istek
2. Gemini (GEMINI_API_KEY varsa) — günde 20 ücretsiz istek (fallback)
3. Her ikisi de yoksa None döner, pipeline şablona düşer

Groq OpenAI-uyumlu API kullandığı için `groq` paketi gerekir:
    pip install groq==0.13.1

Rate-limit (429) yönetimi:
- Her provider kendi retry'ını yönetir
- Groq başarısız olursa Gemini'ye düşer
- Her ikisi de başarısız olursa None döner
"""
from __future__ import annotations

import json
import re
import time

from ..config import get_logger, settings

log = get_logger(__name__)

_RATE_LIMIT_MAX_RETRIES = 3
_RATE_LIMIT_BASE_WAIT = 10  # Groq rate-limit genelde 5-10sn; Gemini için 30sn kullanılır


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
                log.warning("Groq rate-limit; Gemini fallback'e geçiliyor.")
            elif is_too_large:
                # Prompt çok büyük — kısaltarak tekrar dene
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

    @staticmethod
    def _parse_retry_delay(exc: Exception) -> float | None:
        msg = str(exc)
        m = re.search(r"retry(?:Delay)?['\"\s:]+(\d+(?:\.\d+)?)\s*s", msg, re.IGNORECASE)
        if m:
            return float(m.group(1))
        m = re.search(r"retry in (\d+(?:\.\d+)?)", msg, re.IGNORECASE)
        if m:
            return float(m.group(1))
        return None

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
                log.warning("Gemini rate-limit; şablona düşülüyor.")
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


class LlmClient:
    """Groq primary + Gemini fallback LLM istemcisi.

    Groq API key varsa Groq kullanılır (çok daha yüksek ücretsiz kota).
    task_type parametresiyle görev bazlı model seçimi yapılır:
    - "filter": hızlı/ucuz model (haber filtreleme, binary kararlar)
    - "tweet": büyük model (tweet üretimi)
    - "analysis": büyük model (rapor analizi)
    Groq başarısız olursa ya da yoksa Gemini'ye düşer.
    Her ikisi de yoksa None döner.
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

        # Primary: Groq (task bazlı model seçimi için backend'i lazy init ediyoruz)
        self._groq_default = _GroqBackend(settings.groq_model)
        self._groq_fast = _GroqBackend(settings.groq_tweet_model)  # llama-3.1-8b-instant
        # Fallback: Gemini
        self._gemini = _GeminiBackend(model_name or settings.gemini_model)

        if self._groq_default.enabled:
            log.info("LLM: Groq primary (%s) + fast (%s) + Gemini fallback",
                     settings.groq_model, settings.groq_tweet_model)
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
        """Groq → Gemini sıralamasıyla üretim yapar.

        task_type: "filter" (hızlı/ucuz), "tweet", "analysis", "default"
        """
        if not self.enabled:
            return None

        # Görev türüne göre uygun Groq backend'ini seç
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

        # Gemini fallback
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
