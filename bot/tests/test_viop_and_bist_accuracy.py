from datetime import datetime, timezone
import pytest
from esham.sources.viop import ViopSource, assess_margin_stress
from esham.sources.bist import BistSource
from esham.sources import MarketSummary
from esham.ai.analyzer import MarketAIAnalyzer


def test_viop_margin_is_official_takasbank():
    vs = ViopSource()
    snap = vs.margin_snapshot()
    
    assert snap is not None
    # 1. Asla yapay/sentetik veri olmamalı; Takasbank resmi bülteni olmalı
    assert snap.is_sample is False
    assert snap.required_margin_total_tl > 50_000_000_000.0
    assert snap.margin_call_total_tl > 0.0
    assert snap.margin_call_to_required_pct > 0.0
    assert snap.margined_account_count > 10_000
    assert len(snap.as_of) > 0
    
    # 2. Pretty strings should format correctly
    assert "Milyar TL" in snap.required_pretty()
    assert ("Milyar TL" in snap.margin_call_pretty()) or ("Milyon TL" in snap.margin_call_pretty())


def test_viop_stress_assessment():
    stress_up = assess_margin_stress(today_pct=1.33, prior_pct=0.45)
    assert stress_up.level == "Yükseliyor"
    assert "sıkılaştırıyor" in stress_up.note

    stress_flat = assess_margin_stress(today_pct=0.83, prior_pct=0.82)
    assert stress_flat.level == "Sabit"

    stress_down = assess_margin_stress(today_pct=0.40, prior_pct=0.90)
    assert stress_down.level == "Geriliyor"


def test_bist_market_summary_fields():
    bs = BistSource()
    summary = bs.market_summary()
    
    assert summary is not None
    assert summary.index == "XU100"
    assert len(summary.price) > 0
    assert len(summary.change) > 0
    # open_price and open_change should be populated from TradingView or Yahoo fallback
    assert len(summary.open_price) > 0
    assert len(summary.open_change) > 0


def test_temerrut_classification_and_no_emojis():
    body, summary, tweet = MarketAIAnalyzer._template_news_analysis(
        title="İşleme Açılan Temerrüt Sırası",
        company="Borsa İstanbul",
        ticker="GARAN",
        disclosure_type="Duyuru",
        raw_text="Takasbank temerrüt takası çerçevesinde ihale usulü ile satış yapılacaktır.",
        is_insider=False,
    )
    
    # Konu tarafsız etiketle verilir; "Pozitif"/"Risk" gibi yargı etiketi yok.
    assert "**Konu:** Temerrüt bildirimi" in body
    assert "Pozitif" not in body
    assert "Sinyal" not in body
    assert "🟢" not in body
    assert "🚨" not in body
    assert "⚡" not in body
    assert "🎯" not in body
    assert "📊" not in body
    assert "🟢" not in summary
    assert "🚨" not in summary
