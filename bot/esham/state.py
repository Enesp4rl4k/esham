"""Kalıcı durum katmanı — süreç yeniden başlasa da hafıza kaybolmasın.

Sorun: `NewsStream._seen` ve `MarginWatcher._prev_pct` bellekte tutuluyordu.
Render gibi platformlarda süreç sık yeniden başlar (deploy, uyku modu, çökme) —
bellek sıfırlanınca aynı KAP bildirimi tekrar tweetlenebilir veya margin-call
stresi karşılaştırması "önceki gün verisi yok" durumuna döner.

Çözüm: küçük bir JSON dosyası, atomik yazım (temp + rename, yarım yazılmış
dosya riski yok). Disk kalıcı değilse (bazı ücretsiz PaaS'larda konteyner
yeniden oluşturulduğunda diskle birlikte silinir) en kötü senaryo eskisiyle
AYNI davranışa döner (sıfırdan başlar) — asla daha kötü değil, sadece disk
kalıcıysa (çoğu durumda) strictly daha iyi.

Ayrıca: günlük sosyal paylaşım sayacı (kota koruması) ve iş sağlığı/heartbeat
bilgisi de burada tutulur — tek dosya, tek kilit yok (tek süreç varsayımı).
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from .config import get_logger, settings

log = get_logger(__name__)

_SEEN_RETENTION_SECONDS = 14 * 24 * 3600  # 14 gün — bu süreden eski kayıtlar silinir
_SEEN_MARKET_RETENTION_SECONDS = 24 * 3600  # 1 gün — makro/sektör/bist olaylar


class StateStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or settings.state_file
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._data: dict[str, Any] = self._load()

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {}
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            log.warning("Durum dosyası okunamadı (%s); sıfırdan başlanıyor.", exc)
            return {}

    def _save(self) -> None:
        try:
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self._data, ensure_ascii=False, indent=2), encoding="utf-8")
            tmp.replace(self.path)  # atomik — yarım yazılmış dosya riski yok
        except OSError as exc:
            log.warning("Durum dosyası yazılamadı (%s); bu çalıştırma için bellekte kalacak.", exc)

    # ---- genel amaçlı get/set --------------------------------------------------

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value
        self._save()

    def delete(self, key: str) -> None:
        if key in self._data:
            del self._data[key]
            self._save()

    # ---- KAP "görüldü" kümesi (zaman damgalı, otomatik budanır) ----------------

    def load_seen(self) -> set[str]:
        seen: dict[str, float] = self._data.get("seen_disclosures", {})
        return set(seen.keys())

    def save_seen(self, keys: set[str]) -> None:
        existing: dict[str, float] = self._data.get("seen_disclosures", {})
        now = time.time()
        cutoff = now - _SEEN_RETENTION_SECONDS
        merged = {k: existing.get(k, now) for k in keys}
        # Eski kayıtları buda — kümenin sınırsız büyümesini önler.
        pruned = {k: ts for k, ts in merged.items() if ts >= cutoff}
        self._data["seen_disclosures"] = pruned
        self._save()

    # ---- SON_DAKIKA global haber seen set (24 saatlik TTL) -----------------------
    # KAP bildirimleri 14 gün saklanır ama global haber linkleri 24 saat yeterli —
    # aynı haber ertesi gün tekrar geçerliyse zaten yeni bir event olarak gelir.

    _NEWS_RETENTION_SECONDS = 24 * 3600  # 24 saat

    def load_seen_news(self) -> set[str]:
        seen: dict[str, float] = self._data.get("seen_news", {})
        now = time.time()
        cutoff = now - self._NEWS_RETENTION_SECONDS
        # Süresi dolmuş kayıtları at
        valid = {k for k, ts in seen.items() if ts >= cutoff}
        return valid

    def save_seen_news(self, keys: set[str]) -> None:
        existing: dict[str, float] = self._data.get("seen_news", {})
        now = time.time()
        cutoff = now - self._NEWS_RETENTION_SECONDS
        merged = {k: existing.get(k, now) for k in keys}
        pruned = {k: ts for k, ts in merged.items() if ts >= cutoff}
        self._data["seen_news"] = pruned
        self._save()

    # ---- makro/sektör/bist olay seen set (1 günlük TTL) -------------------------
    # Bellekte tutulduğunda GitHub Actions her çalıştırmasında sıfırlanıyor ve
    # aynı sektör/makro olayı günde onlarca kez paylaşılıyor. Diske yazılarak
    # restart/redeploy'dan sonra da tekrar tetikleme engellenir.

    def load_seen_market_events(self) -> set[str]:
        seen: dict[str, float] = self._data.get("seen_market_events", {})
        now = time.time()
        cutoff = now - _SEEN_MARKET_RETENTION_SECONDS
        return {k for k, ts in seen.items() if ts >= cutoff}

    def save_seen_market_events(self, keys: set[str]) -> None:
        existing: dict[str, float] = self._data.get("seen_market_events", {})
        now = time.time()
        cutoff = now - _SEEN_MARKET_RETENTION_SECONDS
        merged = {k: existing.get(k, now) for k in keys}
        pruned = {k: ts for k, ts in merged.items() if ts >= cutoff}
        self._data["seen_market_events"] = pruned
        self._save()

    # ---- margin-call önceki değer -----------------------------------------------

    def get_margin_prev_pct(self) -> float | None:
        return self._data.get("margin_prev_pct")

    def set_margin_prev_pct(self, pct: float) -> None:
        self.set("margin_prev_pct", pct)

    # ---- günlük sosyal paylaşım sayacı (kota koruması) --------------------------

    def increment_daily_post_count(self) -> int:
        today = time.strftime("%Y-%m-%d")
        counts: dict[str, int] = self._data.get("daily_post_counts", {})
        counts[today] = counts.get(today, 0) + 1
        # Sadece son 3 günü tut.
        counts = dict(sorted(counts.items())[-3:])
        self._data["daily_post_counts"] = counts
        self._save()
        return counts[today]

    def get_daily_post_count(self) -> int:
        today = time.strftime("%Y-%m-%d")
        return self._data.get("daily_post_counts", {}).get(today, 0)

    # ---- sağlık/heartbeat ---------------------------------------------------------

    def record_heartbeat(self) -> None:
        self._data["last_heartbeat"] = time.time()
        self._save()

    def record_job_result(self, name: str, ok: bool, detail: str = "") -> int:
        """İş sonucunu kaydeder; güncel ardışık hata sayısını döner (ok=True -> 0)."""
        jobs: dict[str, dict] = self._data.get("jobs", {})
        prev = jobs.get(name, {})
        consecutive_failures = 0 if ok else prev.get("consecutive_failures", 0) + 1
        jobs[name] = {
            "last_run": time.time(),
            "ok": ok,
            "detail": detail[:300],
            "consecutive_failures": consecutive_failures,
        }
        self._data["jobs"] = jobs
        self._save()
        return consecutive_failures

    def snapshot(self) -> dict:
        """Sağlık uç noktası (render_app.py) için özet durum."""
        return {
            "last_heartbeat": self._data.get("last_heartbeat"),
            "jobs": self._data.get("jobs", {}),
            "daily_post_count": self.get_daily_post_count(),
            "seen_count": len(self._data.get("seen_disclosures", {})),
            "margin_prev_pct": self.get_margin_prev_pct(),
        }


_shared: StateStore | None = None


def get_state() -> StateStore:
    """Süreç genelinde tek paylaşılan StateStore örneği."""
    global _shared
    if _shared is None:
        _shared = StateStore()
    return _shared
