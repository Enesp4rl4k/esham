"""Sağlık denetimi kuralları (saf fonksiyon; ağ ve dosya yok)."""
from datetime import datetime, timedelta, timezone

from esham.jobs.health import evaluate

UTC = timezone.utc
WED = datetime(2026, 11, 18, 9, 0, tzinfo=UTC)  # Çarşamba
MON = datetime(2026, 11, 16, 7, 0, tzinfo=UTC)  # Pazartesi sabahı


def by_name(checks):
    return {c.name: c for c in checks}


def test_all_fresh_and_deployed_passes():
    c = evaluate(WED, WED - timedelta(hours=3), WED - timedelta(hours=20), WED - timedelta(hours=2), 200, True)
    assert all(x.ok for x in c), [x for x in c if not x.ok]


def test_stale_report_fails_on_weekday():
    c = by_name(evaluate(WED, WED - timedelta(hours=40), WED, WED, 200, True))
    assert not c["Son rapor tazeliği"].ok
    assert "40.0 saat" in c["Son rapor tazeliği"].detail


def test_weekend_gap_is_tolerated_on_monday_morning():
    # Cuma 18:30 → Pazartesi 07:00 = 60,5 saat: bot hafta sonu çalışmaz, alarm olmamalı
    c = by_name(evaluate(MON, MON - timedelta(hours=60.5), MON - timedelta(hours=60), MON - timedelta(hours=60), 200, True))
    assert c["Son rapor tazeliği"].ok and c["Piyasa bandı (market-ticker.json) tazeliği"].ok
    assert c["Hisse verisi (universe.json) tazeliği"].ok


def test_stock_data_older_than_4_5_days_fails():
    c = by_name(evaluate(WED, WED, WED - timedelta(days=5), WED, 200, True))
    assert not c["Hisse verisi (universe.json) tazeliği"].ok


def test_site_down_and_silent_deploy_failure_are_caught():
    down = by_name(evaluate(WED, WED, WED, WED, None, None))
    assert not down["Canlı site erişimi"].ok
    stuck = by_name(evaluate(WED, WED, WED, WED, 200, False))
    assert not stuck["Dağıtım güncel mi"].ok       # içerik üretiliyor ama canlıda yok
    assert "dağıtım duruyor" in stuck["Dağıtım güncel mi"].detail


def test_unreadable_timestamp_fails_instead_of_passing_silently():
    c = by_name(evaluate(WED, None, WED, WED, 200, True))
    assert not c["Son rapor tazeliği"].ok


def test_deploy_check_skipped_when_not_queryable():
    c = by_name(evaluate(WED, WED, WED, WED, 200, None))
    assert c["Dağıtım güncel mi"].ok and "atlandı" in c["Dağıtım güncel mi"].detail


def test_offline_skips_live_checks_but_keeps_freshness():
    c = by_name(evaluate(WED, WED - timedelta(hours=40), WED, WED, None, None, offline=True))
    assert c["Canlı site erişimi"].ok and "atlandı" in c["Canlı site erişimi"].detail
    assert not c["Son rapor tazeliği"].ok  # tazelik yine denetlenir
