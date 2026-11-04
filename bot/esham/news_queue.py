"""Öncelikli, adil (fair-share) kapasiteli haber kuyruğu.

Tasarım:
- Öncelikli kuyruk: IPO ve kritik şirket bildirimleri acil sırada bekler (öncelik 0-1).
- Dengeli çoklu-kategori dağıtımı (Fair-share Round-Robin):
  'kripto', 'global', 'gundem', 'teknoloji', 'bist' kategorileri arasında
  round-robin adil paylaşım yapılır. Böylece KAP akışı ne kadar yoğun olursa olsun
  kripto, küresel makro, teknoloji ve gündem haberleri açlığa (starvation) uğramaz.
- Kategori bazlı kota (per-category capacity):
  Her kategori kendi kuyruğunda tutulur (örn. maks 40 öğe). Bir kategorideki aşırı
  yığılma diğer kategorilerin haberlerini kuyruktan düşüremez.
"""
from __future__ import annotations

from collections import deque
from typing import Generic, TypeVar

from .config import get_logger

log = get_logger(__name__)

ALL_CATEGORIES = ("ipo", "bist", "kripto", "global", "gundem", "teknoloji")
REGULAR_CATEGORIES = ("kripto", "global", "gundem", "teknoloji", "bist")

T = TypeVar("T")


class NewsQueue(Generic[T]):
    def __init__(self, per_category_max: int = 40) -> None:
        self.per_category_max = per_category_max
        self._queues: dict[str, deque[T]] = {cat: deque() for cat in ALL_CATEGORIES}
        self._fallback_queue: deque[T] = deque()
        self._last_category: str | None = None

    def __len__(self) -> int:
        return sum(len(q) for q in self._queues.values()) + len(self._fallback_queue)

    def enqueue(self, item: T, category: str) -> None:
        cat = category.lower() if isinstance(category, str) else "bist"
        if cat == "insider":
            cat = "bist"

        target_q = self._queues.get(cat, self._fallback_queue)
        target_q.append(item)
        if len(target_q) > self.per_category_max:
            target_q.popleft()
            log.debug("Kategori '%s' kuyruğu doldu (%d); en eski öğe budandı.", cat, self.per_category_max)

    def dequeue(self) -> T | None:
        """Adil paylaşım: Önce kritik (IPO), sonra kategoriler arası round-robin."""
        # 1. Kritik / acil bildirimler (IPO)
        if self._queues["ipo"]:
            return self._queues["ipo"].popleft()

        # 2. Normal kategoriler arasında döngüsel adil servis (Round-Robin)
        n = len(REGULAR_CATEGORIES)
        start_idx = 0
        if self._last_category in REGULAR_CATEGORIES:
            start_idx = (REGULAR_CATEGORIES.index(self._last_category) + 1) % n

        for offset in range(n):
            cat = REGULAR_CATEGORIES[(start_idx + offset) % n]
            if self._queues[cat]:
                self._last_category = cat
                return self._queues[cat].popleft()

        # 3. Bilinmeyen kategori kuyruğu varsa
        if self._fallback_queue:
            return self._fallback_queue.popleft()

        return None

    def stats(self) -> dict[str, int]:
        return {cat: len(q) for cat, q in self._queues.items() if len(q) > 0}
