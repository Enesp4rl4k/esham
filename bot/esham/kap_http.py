"""KAP (kap.org.tr) için nazik HTTP katmanı: pacing, Retry-After, bütçe ve devre kesici.

KAP'ın iyi niyetine dayanıyoruz: yük azaltılır, eşzamanlılık/kimlik gizleme eklenmez.

- Her istek arasında en az ``min_interval`` saniye (süreç genelinde, iş parçacıkları arasında paylaşılan).
- 429/5xx/bağlantı hatasında en çok ``max_attempts`` deneme; bekleme ``Retry-After`` varsa o (üst sınırlı),
  yoksa jitter'lı üstel geri çekilme.
- ``begin_stage()`` ile başlayan aşamanın toplam süre bütçesi vardır; bütçe bitince KAP'a çağrı yapılmaz.
- Ardışık ``breaker_threshold`` adet 429'dan sonra devre açılır: aşama kalan istekleri çağırmadan bitirir.

KAP kullanılamıyorsa ``KapUnavailable`` (``requests.RequestException`` alt sınıfı) fırlatılır; böylece
mevcut ``except RequestException`` / ``except Exception`` yolları değişmeden "veri yok" sayar ve
önceki iyi veri korunur.
"""
from __future__ import annotations

import os
import random
import threading
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any

import requests
from requests import Response

from .config import get_logger

log = get_logger(__name__)

RETRYABLE_STATUS = {429, 500, 502, 503, 504}

# Test için enjekte edilebilir
_clock = time.monotonic
_sleep = time.sleep
_jitter = random.uniform


class KapUnavailable(requests.RequestException):
    """Bütçe tükendi, devre kesici açıldı ya da bekleme bütçeyi aşıyor."""


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, "") or default)
    except ValueError:
        return default


def parse_retry_after(value: str | None, now: datetime | None = None) -> float | None:
    """``Retry-After`` (saniye ya da HTTP tarihi) → saniye; çözülemezse None."""
    if not value:
        return None
    value = value.strip()
    try:
        return max(0.0, float(value))
    except ValueError:
        pass
    try:
        when = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    return max(0.0, (when - (now or datetime.now(timezone.utc))).total_seconds())


class KapGate:
    def __init__(
        self,
        *,
        min_interval: float | None = None,
        max_attempts: int | None = None,
        backoff_base: float | None = None,
        backoff_max: float | None = None,
        budget_seconds: float | None = None,
        breaker_threshold: int | None = None,
        breaker_cooldown: float | None = None,
    ) -> None:
        def pick(given: float | None, env: str, default: float) -> float:
            return _env_float(env, default) if given is None else given

        self.min_interval = pick(min_interval, "ESHAM_KAP_MIN_INTERVAL", 1.0)
        self.max_attempts = max(1, int(pick(max_attempts, "ESHAM_KAP_MAX_ATTEMPTS", 3)))
        self.backoff_base = pick(backoff_base, "ESHAM_KAP_BACKOFF_BASE", 2.0)
        self.backoff_max = pick(backoff_max, "ESHAM_KAP_BACKOFF_MAX", 60.0)
        self.budget_seconds = pick(budget_seconds, "ESHAM_KAP_BUDGET_SECONDS", 300.0)
        self.breaker_threshold = max(1, int(pick(breaker_threshold, "ESHAM_KAP_BREAKER", 5)))
        self.breaker_cooldown = pick(breaker_cooldown, "ESHAM_KAP_BREAKER_COOLDOWN", 900.0)
        self._lock = threading.Lock()
        self._next_slot = 0.0
        self._deadline: float | None = None
        self._tripped_at: float | None = None
        self._consecutive_429 = 0
        self.reset_stats()

    def reset_stats(self) -> None:
        self.ok = 0
        self.failed = 0
        self.skipped = 0
        self.throttled = 0

    def begin_stage(self) -> None:
        """Yeni aşama: bütçeyi başlatır, sayaçları ve devre kesiciyi sıfırlar."""
        with self._lock:
            self._deadline = _clock() + self.budget_seconds if self.budget_seconds > 0 else None
            self._tripped_at = None
            self._consecutive_429 = 0
            self.reset_stats()

    @property
    def stopped(self) -> bool:
        """Devre açık ya da bütçe bitmiş → KAP'a daha fazla çağrı yapılmaz."""
        return self._stop_reason() is not None

    def _stop_reason(self) -> str | None:
        now = _clock()
        if self._tripped_at is not None:
            # Aşamasız (sürekli çalışan) kullanımda devre, bekleme süresinden sonra yarı açılır.
            if self._deadline is None and now - self._tripped_at >= self.breaker_cooldown:
                self._tripped_at = None
                self._consecutive_429 = 0
            else:
                return "devre kesici açık (ardışık 429)"
        if self._deadline is not None and now >= self._deadline:
            return "süre bütçesi tükendi"
        return None

    def remaining(self) -> float | None:
        return None if self._deadline is None else max(0.0, self._deadline - _clock())

    def summary(self) -> str:
        reason = self._stop_reason()
        return (
            f"KAP özeti: {self.ok} istek başarılı, {self.failed} başarısız, {self.skipped} atlandı, "
            f"{self.throttled} adet 429" + (f" — durduruldu: {reason}" if reason else "")
        )

    def _pace(self) -> None:
        if self.min_interval <= 0:
            return
        with self._lock:
            now = _clock()
            slot = max(now, self._next_slot)
            self._next_slot = slot + self.min_interval
        if slot > now:
            _sleep(slot - now)

    def _backoff(self, attempt: int, retry_after: float | None) -> float:
        if retry_after is not None:
            return min(retry_after, self.backoff_max)
        return min(self.backoff_base * (2 ** attempt) + _jitter(0, self.backoff_base), self.backoff_max)

    def _count(self, field: str) -> None:
        with self._lock:
            setattr(self, field, getattr(self, field) + 1)

    def _note_status(self, status: int) -> None:
        with self._lock:
            if status == 429:
                self.throttled += 1
                self._consecutive_429 += 1
                if self._consecutive_429 >= self.breaker_threshold and self._tripped_at is None:
                    self._tripped_at = _clock()
                    log.error("KAP devre kesici açıldı: %d ardışık 429", self._consecutive_429)
            else:
                self._consecutive_429 = 0

    def request(self, method: str, url: str, **kwargs: Any) -> Response:
        fn = requests.get if method == "GET" else requests.post
        last = self.max_attempts - 1
        for attempt in range(self.max_attempts):
            reason = self._stop_reason()
            if reason:
                self._count("skipped")
                raise KapUnavailable(f"KAP çağrısı atlandı ({reason}): {url}")
            self._pace()
            try:
                resp = fn(url, **kwargs)
            except (requests.ConnectionError, requests.Timeout) as exc:
                if attempt == last:
                    self._count("failed")
                    raise
                retry_after, label = None, f"istek hatası ({exc})"
            else:
                self._note_status(resp.status_code)
                if resp.status_code not in RETRYABLE_STATUS:
                    self._count("ok")
                    return resp
                if attempt == last or self.stopped:
                    self._count("failed")
                    return resp
                retry_after, label = parse_retry_after(resp.headers.get("Retry-After")), f"HTTP {resp.status_code}"
            wait = self._backoff(attempt, retry_after)
            left = self.remaining()
            if left is not None and wait >= left:
                self._count("failed")
                raise KapUnavailable(f"KAP bekleme süresi bütçeyi aşıyor ({wait:.0f} s >= {left:.0f} s): {url}")
            log.warning("KAP %s, %.1f s sonra yeniden (%d/%d): %s", label, wait, attempt + 1, self.max_attempts, url)
            _sleep(wait)
        raise KapUnavailable(f"KAP denemeleri tükendi: {url}")  # pragma: no cover


#: Süreç genelinde paylaşılan geçit.
gate = KapGate()


def kap_get(url: str, **kwargs: Any) -> Response:
    return gate.request("GET", url, **kwargs)


def kap_post(url: str, **kwargs: Any) -> Response:
    return gate.request("POST", url, **kwargs)
