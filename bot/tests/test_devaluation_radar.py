"""TRY Devalüasyon / Kur Şoku Basınç Radarı Testleri."""
import pytest
from esham.sources.devaluation_radar import DevaluationRadarAnalyzer, export_devaluation_radar_json


def test_devaluation_radar_calculation():
    analyzer = DevaluationRadarAnalyzer()
    res = analyzer.analyze()

    assert 0 <= res.composite_score <= 100
    assert res.risk_level in ["LOW", "MODERATE", "HIGH", "CRITICAL"]
    assert res.risk_label != ""
    assert res.risk_summary != ""

    # Bileşenler
    assert res.viop_spot_usd > 0
    assert res.viop_futures_usd > res.viop_spot_usd
    assert res.policy_rate_pct > 0
    assert res.cds_5y_bps > 0
    assert res.reer_index > 0
    assert len(res.historical_benchmarks) >= 3
    assert len(res.actionable_notes) >= 3

    # Sözlük dönüşümü
    d = res.to_dict()
    assert "composite_score" in d
    assert "components" in d
    assert "viop_implied_yield" in d["components"]
    assert "tcmb_reserves" in d["components"]
    assert "grand_bazaar_spread" in d["components"]


def test_devaluation_radar_export(tmp_path):
    target = tmp_path / "devaluation-radar.json"
    p = export_devaluation_radar_json(target_path=target)
    assert p.exists()
    assert p.stat().st_size > 100
