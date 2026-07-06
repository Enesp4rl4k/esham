"""HTTP istek yardımcısı — üstel geri çekilme ile yeniden deneme.

Kullanım
--------
    from .http import retry_get

    resp = retry_get(url, headers=headers, timeout=10)
    resp.raise_for_status()

Varsayılan davranış:
- 3 deneme (ilk + 2 yeniden deneme)
- Denemeler arası bekleme: 1 s, 2 s (2 ** attempt)
- Yeniden deneme tetikleyen durumlar: bağlantı hatası, zaman aşımı,
  429 (Too Many Requests) ve 5xx sunucu hataları.
"""
from __future__ import annotations

import time
from typing import Any

import requests
from requests import Response

from .config import get_logger

log = get_logger(__name__)

#: Yeniden deneme yapılacak HTTP durum kodları.
RETRYABLE_STATUS = {429, 500, 502, 503, 504}


def _retry(
    method: str,
    url: str,
    *,
    retries: int,
    backoff_base: float,
    **kwargs: Any,
) -> Response:
    """Ortak yeniden deneme motoru (GET ve POST için)."""
    last_exc: Exception | None = None
    fn = requests.get if method == "GET" else requests.post

    for attempt in range(retries):
        try:
            resp = fn(url, **kwargs)
            if resp.status_code in RETRYABLE_STATUS and attempt < retries - 1:
                wait = backoff_base * (2 ** attempt)
                log.warning(
                    "HTTP %s alındı, %.1f s sonra yeniden deneniyor (%d/%d): %s",
                    resp.status_code,
                    wait,
                    attempt + 1,
                    retries,
                    url,
                )
                time.sleep(wait)
                continue
            return resp

        except (requests.ConnectionError, requests.Timeout) as exc:
            last_exc = exc
            if attempt < retries - 1:
                wait = backoff_base * (2 ** attempt)
                log.warning(
                    "İstek hatası (%s), %.1f s sonra yeniden deneniyor (%d/%d): %s",
                    exc,
                    wait,
                    attempt + 1,
                    retries,
                    url,
                )
                time.sleep(wait)
            else:
                log.error("Tüm denemeler tükendi: %s — %s", url, exc)

    if last_exc is not None:
        raise last_exc
    return fn(url, **kwargs)  # pragma: no cover


def retry_get(
    url: str,
    *,
    retries: int = 3,
    backoff_base: float = 1.0,
    **kwargs: Any,
) -> Response:
    """``requests.get`` etrafında üstel geri çekilmeli sarmalayıcı."""
    return _retry("GET", url, retries=retries, backoff_base=backoff_base, **kwargs)


def retry_post(
    url: str,
    *,
    retries: int = 3,
    backoff_base: float = 1.0,
    **kwargs: Any,
) -> Response:
    """``requests.post`` etrafında üstel geri çekilmeli sarmalayıcı."""
    return _retry("POST", url, retries=retries, backoff_base=backoff_base, **kwargs)
