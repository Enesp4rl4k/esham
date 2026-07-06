"""Ortak LLM istemcisi (Google Gemini — yeni `google-genai` SDK).

Tüm AI çağrıları buradan geçer. Eski `google-generativeai` SDK'si Python 3.14 ile
uyumsuz olduğundan yeni `google-genai` (`from google import genai`) kullanılır.
JSON çıktı desteği, hata/anahtarsız durumda `None` dönüşü ve token limiti tek yerde.
"""
from __future__ import annotations

import json
import re

from ..config import get_logger, settings

log = get_logger(__name__)


class LlmClient:
    def __init__(
        self,
        model_name: str | None = None,
        *,
        max_output_tokens: int = 2048,
        temperature: float = 0.3,
    ) -> None:
        self.model_name = model_name or settings.gemini_model
        self.max_output_tokens = max_output_tokens
        self.temperature = temperature
        self._client = None
        if not settings.ai_enabled:
            return
        try:
            from google import genai

            self._client = genai.Client(api_key=settings.gemini_api_key)
        except Exception as exc:
            log.warning("LLM istemcisi kurulamadı (%s); analiz fallback'e düşecek.", exc)
            self._client = None

    @property
    def enabled(self) -> bool:
        return self._client is not None

    def _config(self, *, as_json: bool = False, disable_thinking: bool = False):
        from google.genai import types

        kwargs = {
            "max_output_tokens": self.max_output_tokens,
            "temperature": self.temperature,
        }
        if as_json:
            kwargs["response_mime_type"] = "application/json"
        if disable_thinking:
            # Gemini 2.5 modelleri "thinking" için token bütçesinden gizlice pay
            # ayırır; bu, doğrudan JSON çıkarım görevlerinde çıktının MAX_TOKENS'a
            # takılıp yarıda kesilmesine yol açabilir. Çıkarım görevi çok adımlı
            # akıl yürütme gerektirmediği için thinking'i kapatıp tüm bütçeyi
            # gerçek çıktıya ayırıyoruz (ayrıca daha hızlı ve ucuz).
            kwargs["thinking_config"] = types.ThinkingConfig(thinking_budget=0)
        return types.GenerateContentConfig(**kwargs)

    @staticmethod
    def _warn_if_truncated(resp) -> None:
        try:
            finish_reason = resp.candidates[0].finish_reason
        except (AttributeError, IndexError, TypeError):
            return
        if finish_reason is not None and "MAX_TOKENS" in str(finish_reason):
            log.warning(
                "LLM yanıtı MAX_TOKENS'a takılıp yarıda kesildi; max_output_tokens "
                "yetersiz kalmış olabilir."
            )

    def generate(self, prompt: str, *, disable_thinking: bool = False) -> str | None:
        if not self._client:
            return None
        try:
            resp = self._client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=self._config(disable_thinking=disable_thinking),
            )
            self._warn_if_truncated(resp)
            return (resp.text or "").strip() or None
        except Exception as exc:
            log.error("LLM üretim hatası: %s", exc)
            return None

    def generate_json(self, prompt: str) -> dict | None:
        """Modelden JSON ister ve güvenli biçimde ayrıştırır."""
        if not self._client:
            return None
        try:
            try:
                resp = self._client.models.generate_content(
                    model=self.model_name,
                    contents=prompt,
                    config=self._config(as_json=True, disable_thinking=True),
                )
            except Exception:
                # Model thinking_config'i desteklemiyorsa (örn. bazı eski modeller)
                # thinking olmadan tekrar dene.
                resp = self._client.models.generate_content(
                    model=self.model_name, contents=prompt, config=self._config(as_json=True)
                )
            self._warn_if_truncated(resp)
            text = (resp.text or "").strip()
        except Exception as exc:
            log.error("LLM JSON üretim hatası: %s", exc)
            return None
        return self._parse_json(text)

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
                    data = json.loads(text[start : end + 1])
                    return data if isinstance(data, dict) else None
                except json.JSONDecodeError:
                    pass
        log.warning("LLM çıktısı JSON olarak ayrıştırılamadı.")
        return None
