"""Öncelikli, kapasiteli haber kuyruğu.

Amaç: aynı anda çok haber gelse bile yayını aralıklı (drip) yapmak. Tarama yeni
haberleri buraya atar; yayıncı tek tek çeker. Böylece tarama hızı ile yayın hızı
birbirinden ayrılır — flood ve rate-limit önlenir.

Öncelik: insider (0) > ipo (1) > bist (2) > global (3) > gundem (4).
Aynı öncelik içinde FIFO (geliş sırası korunur).
"""
from __future__ import annotations

from collections import deque
from typing import Generic, TypeVar

from .config import get_logger

log = get_logger(__name__)

PRIORITY: dict[str, int] = {
    "insider": 0,
    "ipo": 1,
    "bist": 2,
    "global": 3,
    "gundem": 4,
}
_LEVELS = 5
_LOWEST = _LEVELS - 1

T = TypeVar("T")


class NewsQueue(Generic[T]):
    def __init__(self, maxsize: int = 200) -> None:
        self.maxsize = maxsize
        self._buckets: list[deque[T]] = [deque() for _ in range(_LEVELS)]

    def __len__(self) -> int:
        return sum(len(b) for b in self._buckets)

    def enqueue(self, item: T, category: str) -> None:
        level = PRIORITY.get(category, _LOWEST)
        self._buckets[level].append(item)
        if len(self) > self.maxsize:
            self._drop_one()

    def dequeue(self) -> T | None:
        """En yüksek öncelikli, en eski öğeyi döner; kuyruk boşsa None."""
        for bucket in self._buckets:
            if bucket:
                return bucket.popleft()
        return None

    def _drop_one(self) -> None:
        """Kapasite aşılınca en düşük öncelikli en eski öğeyi düşür."""
        for bucket in reversed(self._buckets):
            if bucket:
                bucket.popleft()
                log.warning("Kuyruk doldu (%d); en düşük öncelikli haber düşürüldü.", self.maxsize)
                return
