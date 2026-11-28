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

from .config import get_logger, settings
from .formatting import tr_date_text, tr_pct
from .news_stream import NewsStream
from .pipeline import (
    run_closing_report,
    run_global_report,
    run_morning_report,
    run_opening_report,
    run_peer_report,
    run_sector_report,
    run_viop_report,
    run_weekly_summary,
)
from .jobs.publish_heatmap import run_heatmap
from .newsletter import run_newsletter
from .publishing.turib_data import update_turib_market_data
from .publishing.social import SocialPublisher
from .sources.peer import sector_for_today
from .sources.viop import ViopSource, assess_margin_stress
from .state import get_state

log = get_logger(__name__)

# Bir iş bu kadar ardışık başarısız olursa TEK SEFERLİK bir operasyonel uyarı
# gönderilir (Telegram'a — halka açık Twitter'a DEĞİL). Her hatada spam olmasın
# diye eşik + "zaten uyarıldı" izlemesi kullanılır.
ALERT_FAILURE_THRESHOLD = 3

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
    """Teminat stresi önceki değere göre sıçrarsa VİOP margin-call raporu yayınlar.

    `_prev_pct` diske kalıcıdır (StateStore) — süreç yeniden başlasa da (Render
    restart/deploy) karşılaştırma sıfırlanmaz. Kalıcı olmasaydı her restart'ta
    "önceki gün verisi yok" durumuna dönerdi ve gerçek bir stres sıçraması
    kaçırılabilirdi.
    """

    def __init__(self, jump_threshold: float = 0.05) -> None:
        self.jump_threshold = jump_threshold
        self.social = SocialPublisher()
        self._state = get_state()
        self._prev_pct: float | None = self._state.get_margin_prev_pct()

    def check(self) -> None:
        snap = ViopSource().margin_snapshot()
        pct = snap.margin_call_to_required_pct
        stress = assess_margin_stress(pct, self._prev_pct, jump_threshold=self.jump_threshold)
        if self._prev_pct is not None and stress.level == "Yükseliyor":
            log.warning("MARGIN-CALL STRESİ: %s", stress.note)
            slug = run_viop_report(prior_pct=self._prev_pct, publish=True)
            self.social.broadcast(
                f"⚠️ VİOP teminat stresi yükseliyor: margin-call/gereken "
                f"{tr_pct(pct, 3, signed=False)} ({tr_date_text(snap.as_of)}). Detay raporda. #VİOP #MarginCall"
            )
        self._prev_pct = pct
        self._state.set_margin_prev_pct(pct)


class Scheduler:
    def __init__(self, tick_seconds: int = 30) -> None:
        self.tick_seconds = tick_seconds
        self.daily: list[DailyJob] = []
        self.interval: list[IntervalJob] = []
        self._state = get_state()
        self._alerted_jobs: set[str] = set()  # bu çalıştırmada zaten uyarılan işler

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
        self._state.record_heartbeat()

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

    def _safe_run(self, name: str, func: Callable[[], object]) -> None:
        try:
            log.info("İş çalışıyor: %s", name)
            func()
            self._state.record_job_result(name, ok=True)
            if name in self._alerted_jobs:
                self._alerted_jobs.discard(name)
                self._notify_ops(f"✅ Düzeldi: '{name}' işi tekrar başarılı çalışıyor.")
        except Exception as exc:  # bir işin hatası döngüyü durdurmamalı
            log.error("İş başarısız (%s): %s", name, exc)
            self._state.record_job_result(name, ok=False, detail=str(exc))
            self._maybe_alert_failure(name, str(exc))

    def _maybe_alert_failure(self, name: str, detail: str) -> None:
        """Bir iş eşiği aşacak kadar ardışık başarısız olursa TEK SEFERLİK uyarır
        (her hatada değil — spam olmasın). Düzelince de tek seferlik "düzeldi" mesajı."""
        jobs = self._state.snapshot().get("jobs", {})
        consecutive = jobs.get(name, {}).get("consecutive_failures", 0)
        if consecutive >= ALERT_FAILURE_THRESHOLD and name not in self._alerted_jobs:
            self._alerted_jobs.add(name)
            self._notify_ops(
                f"🔧 UYARI: '{name}' işi {consecutive} kez üst üste başarısız oldu.\n"
                f"Son hata: {detail[:200]}"
            )

    @staticmethod
    def _notify_ops(message: str) -> None:
        """Operasyonel uyarı — Telegram'a (varsa) gider, ASLA Twitter'a değil."""
        try:
            SocialPublisher().post_telegram(message)
        except Exception as exc:
            log.error("Operasyonel uyarı gönderilemedi: %s", exc)

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
    macro_scan_interval: int = 600,
) -> Scheduler:
    """İstenen günlük döngüyü kuran hazır orkestratör.

    scan_interval       — KAP bildirim tarama sıklığı (saniye, varsayılan 5 dk)
    macro_scan_interval — Makro/sektör fiyat hareketi tarama sıklığı (saniye, varsayılan 10 dk)
    publish_interval    — Kuyruktan tek haber yayın aralığı (saniye, drip)
    margin_interval     — VİOP teminat stres kontrolü sıklığı (saniye)
    """
    sched = Scheduler()
    stream = NewsStream()  # KAP + makro tarama + drip yayın + halka arz otomatik analizi
    watcher = MarginWatcher()

    # Sürekli akış — KAP bildirimleri
    sched.add_interval("haber-tarama", scan_interval, stream.scan)
    # Sürekli akış — Makro/sektör fiyat hareketleri (VIX, faiz, altın, sektör vb.)
    sched.add_interval("makro-tarama", macro_scan_interval, stream.macro_scan)
    sched.add_interval("haber-yayın", publish_interval, stream.publish_next)
    sched.add_interval("margin-call-izleyici", margin_interval, watcher.check)

    # Sabit saatli (TR)
    sched.add_daily("gunluk-bulten", "08:30", lambda: run_morning_report())
    # E-posta özeti — sabah bülteni hemen ardından (SMTP yoksa dry-run, zarif bozulma)
    sched.add_daily("bulten-gonder", "08:40", lambda: run_newsletter())
    sched.add_daily("kuresel-makro", "08:45", lambda: run_global_report())
    sched.add_daily("viop-acilis", "09:30", lambda: run_viop_report(publish=True))
    sched.add_daily("bist-acilis", "10:00", lambda: run_opening_report(publish_social=True))
    sched.add_daily("turib-seans-ortasi", "11:15", lambda: update_turib_market_data())
    sched.add_daily("heatmap-ogle", "13:00", lambda: run_heatmap())
    sched.add_daily("turib-kapanis", "16:30", lambda: update_turib_market_data())
    sched.add_daily("kapanis", "18:15", lambda: run_closing_report())
    sched.add_daily("heatmap-aksam", "18:30", lambda: run_heatmap())

    # Haftalık (Pazartesi)
    sched.add_daily("haftalik-sektor", "09:00", lambda: run_sector_report(), days={0})
    # Haftalık peer kıyası — sektör haftaya göre döner (09:15, sektör rotasyonunun hemen sonrası)
    sched.add_daily("haftalik-peer", "09:15", lambda: run_peer_report(sector_for_today()), days={0})

    # Haftalık özet (Cuma kapanış sonrası 18:30 TR)
    sched.add_daily("haftalik-ozet", "18:30", lambda: run_weekly_summary(), days={4})

    return sched
