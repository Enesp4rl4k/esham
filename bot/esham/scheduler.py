"""Günlük yayın orkestratörü.

Tek uzun-ömürlü süreç tüm operasyonu yönetir (VPS modeli). TR saatiyle (UTC+3,
DST yok) sabit saatli işler + aralıklı işler + olay-tetikli margin-call izleyici.

Varsayılan program (hafta içi):
    08:30  Günlük bülten (sabah raporu)
    09:30  VİOP açılış + teminat görünümü
    10:00  BIST açılış notu
    18:15  Kapanış bülteni
    Pzt 09:00  Haftalık sektör rotasyonu
    sürekli    KAP/haber taraması + drip yayın (halka arz belgeleri otomatik analiz)
    periyodik  Margin-call izleyici (teminat stresi sıçrarsa yayınla)

Stateless dağıtım (GitHub Actions cron) isteyenler için her iş ayrı CLI komutu
olarak da çağrılabilir; bkz. .github/workflows/esham-schedule.yml.
"""
from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone

from .config import get_logger
from .news_stream import NewsStream
from .pipeline import (
    run_closing_report,
    run_morning_report,
    run_opening_report,
    run_sector_report,
    run_viop_report,
)
from .publishing.social import SocialPublisher
from .sources.viop import ViopSource, assess_margin_stress

log = get_logger(__name__)

# Türkiye saati — kalıcı UTC+3 (2016'dan beri DST yok).
TR_TZ = timezone(timedelta(hours=3))
WEEKDAYS = frozenset({0, 1, 2, 3, 4})  # Pzt-Cum


def tr_now() -> datetime:
    return datetime.now(TR_TZ)


@dataclass
class DailyJob:
    name: str
    at: str  # "HH:MM" (TR)
    func: Callable[[], object]
    days: frozenset[int] = WEEKDAYS
    _last_fired: date | None = None

    def is_due(self, now: datetime) -> bool:
        return (
            now.weekday() in self.days
            and now.strftime("%H:%M") >= self.at
            and self._last_fired != now.date()
        )


@dataclass
class IntervalJob:
    name: str
    every_seconds: int
    func: Callable[[], object]
    _last_mono: float | None = None

    def is_due(self, mono: float) -> bool:
        return self._last_mono is None or (mono - self._last_mono) >= self.every_seconds


class MarginWatcher:
    """Teminat stresi önceki değere göre sıçrarsa VİOP margin-call raporu yayınlar."""

    def __init__(self, jump_threshold: float = 0.05) -> None:
        self.jump_threshold = jump_threshold
        self._prev_pct: float | None = None
        self.social = SocialPublisher()

    def check(self) -> None:
        snap = ViopSource().margin_snapshot()
        pct = snap.margin_call_to_required_pct
        stress = assess_margin_stress(pct, self._prev_pct, jump_threshold=self.jump_threshold)
        if self._prev_pct is not None and stress.level == "Yükseliyor":
            log.warning("MARGIN-CALL STRESİ: %s", stress.note)
            slug = run_viop_report(prior_pct=self._prev_pct, publish=True)
            self.social.broadcast(
                f"⚠️ VİOP teminat stresi yükseliyor: margin-call/gereken "
                f"%{pct:.2f}. Detay raporda. #VİOP #MarginCall"
            )
        self._prev_pct = pct


class Scheduler:
    def __init__(self, tick_seconds: int = 30) -> None:
        self.tick_seconds = tick_seconds
        self.daily: list[DailyJob] = []
        self.interval: list[IntervalJob] = []

    def add_daily(self, name: str, at: str, func: Callable[[], object], days=WEEKDAYS) -> None:
        self.daily.append(DailyJob(name, at, func, frozenset(days)))

    def add_interval(self, name: str, every_seconds: int, func: Callable[[], object]) -> None:
        self.interval.append(IntervalJob(name, every_seconds, func))

    def prime(self, now: datetime | None = None) -> None:
        """Başlangıçta saati geçmiş günlük işleri 'bugün yapıldı' işaretler (geç ateşleme yok)."""
        now = now or tr_now()
        for job in self.daily:
            if now.weekday() in job.days and now.strftime("%H:%M") >= job.at:
                job._last_fired = now.date()

    def tick(self, now: datetime | None = None, mono: float | None = None) -> list[str]:
        """Vadesi gelen işleri çalıştırır; çalıştırılan iş adlarını döner."""
        now = now or tr_now()
        mono = mono if mono is not None else time.monotonic()
        fired: list[str] = []

        for job in self.daily:
            if job.is_due(now):
                job._last_fired = now.date()
                self._safe_run(job.name, job.func)
                fired.append(job.name)

        for job in self.interval:
            if job.is_due(mono):
                job._last_mono = mono
                self._safe_run(job.name, job.func)
                fired.append(job.name)
        return fired

    @staticmethod
    def _safe_run(name: str, func: Callable[[], object]) -> None:
        try:
            log.info("İş çalışıyor: %s", name)
            func()
        except Exception as exc:  # bir işin hatası döngüyü durdurmamalı
            log.error("İş başarısız (%s): %s", name, exc)

    def run(self) -> None:
        self.prime()
        log.info(
            "Esham orkestratörü başladı (TR %s). Günlük iş: %d, aralıklı iş: %d.",
            tr_now().strftime("%H:%M"),
            len(self.daily),
            len(self.interval),
        )
        while True:
            self.tick()
            time.sleep(self.tick_seconds)


def build_default_scheduler(
    scan_interval: int = 300,
    publish_interval: int = 90,
    margin_interval: int = 1800,
) -> Scheduler:
    """İstenen günlük döngüyü kuran hazır orkestratör."""
    sched = Scheduler()
    stream = NewsStream()  # KAP/haber taraması + drip + halka arz otomatik analizi
    watcher = MarginWatcher()

    # Sürekli akış
    sched.add_interval("haber-tarama", scan_interval, stream.scan)
    sched.add_interval("haber-yayın", publish_interval, stream.publish_next)
    sched.add_interval("margin-call-izleyici", margin_interval, watcher.check)

    # Sabit saatli (TR)
    sched.add_daily("gunluk-bulten", "08:30", lambda: run_morning_report())
    sched.add_daily("viop-acilis", "09:30", lambda: run_viop_report(publish=True))
    sched.add_daily("bist-acilis", "10:00", lambda: run_opening_report(publish_social=True))
    sched.add_daily("kapanis", "18:15", lambda: run_closing_report())

    # Haftalık (Pazartesi)
    sched.add_daily("haftalik-sektor", "09:00", lambda: run_sector_report(), days={0})

    return sched
