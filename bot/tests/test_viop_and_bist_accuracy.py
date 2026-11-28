from datetime import datetime, timezone
import pytest
from pathlib import Path
from esham.sources.viop import ViopSource, assess_margin_stress
from esham.sources.bist import BistSource
from esham.sources import MarketSummary
from esham.ai.analyzer import MarketAIAnalyzer


FIXTURES = Path(__file__).parent / "fixtures"


class _Resp:
    def __init__(self, text):
        self.text = text

    def raise_for_status(self):
        pass


def test_viop_margin_parser_offline(monkeypatch):
    """Takasbank sayfası yapısındaki SENTETİK fikstürle ayrıştırıcı ve oran hesabı (ağ yok)."""
    html_text = (FIXTURES / "takasbank_viop_synthetic.html").read_text(encoding="utf-8")
    monkeypatch.setattr("esham.sources.viop.requests.get", lambda *a, **k: _Resp(html_text))
    snap = ViopSource().margin_snapshot()
    assert snap is not None and snap.is_sample is False
    assert snap.as_of == "26.11.2026"
    assert snap.required_margin_total_tl == 85_250_000_000.5
    assert snap.margin_call_total_tl == 1_278_750_000.0
    assert snap.margined_account_count == 45123
    assert snap.futures_volume_tl == 310_500_000_000.0
    assert snap.options_volume_tl == 12_400_000_000.0
    assert snap.futures_oi_value_tl == 95_000_000_000.0
    assert snap.profit_loss_total_tl == 2_100_000_000.0
    assert snap.margin_call_to_required_pct == pytest.approx(1.5, abs=0.001)
    assert "Milyar TL" in snap.required_pretty()


def test_viop_margin_parser_offline_no_table_gives_none(monkeypatch):
    monkeypatch.setattr("esham.sources.viop.requests.get", lambda *a, **k: _Resp("<html>bakım</html>"))
    monkeypatch.setattr("esham.sources.viop.settings", type("S", (), {"takasbank_viop_url": "", "http_timeout": 5})())
    assert ViopSource().margin_snapshot() is None  # uydurma rakam üretilmez


@pytest.mark.network
def test_viop_margin_is_official_takasbank():
    """CANLI doğrulama (CI'da `-m "not network"` ile atlanır). Elle: python -m pytest tests/test_viop_and_bist_accuracy.py -m network"""
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
    assert "önceki güne göre yükseldi" in stress_up.note and "olası" not in stress_up.note

    stress_flat = assess_margin_stress(today_pct=0.83, prior_pct=0.82)
    assert stress_flat.level == "Sabit"

    stress_down = assess_margin_stress(today_pct=0.40, prior_pct=0.90)
    assert stress_down.level == "Geriliyor"


def _no_network(*a, **k):
    raise ConnectionError("çevrimdışı test: ağ yok")


def test_bist_market_summary_offline(monkeypatch):
    """TradingView tarayıcı yanıtının yapısındaki sentetik yük ile BIST özeti (ağ yok)."""
    payload = {"data": [{"s": "BIST:XU100", "d": ["XU100", 10000.0, 2.0, 9900.0, 10050.0, 9850.0, 5_000_000_000]}]}

    class _R:
        def raise_for_status(self):
            pass

        def json(self):
            return payload

    monkeypatch.setattr("esham.sources.bist.retry_post", lambda *a, **k: _R())
    # Yahoo grafik çağrıları (yedek kaynak ve oturum/zaman verisi) da ağa çıkmasın; yoksa conftest testi kırar.
    monkeypatch.setattr("esham.sources.bist.retry_get", _no_network, raising=False)
    summary = BistSource().market_summary()
    assert summary is not None and summary.index == "XU100"
    assert summary.price and summary.change.startswith("+") and summary.open_price and summary.open_change


@pytest.mark.network
def test_bist_market_summary_fields():
    """CANLI doğrulama (CI'da atlanır). Elle: python -m pytest tests/test_viop_and_bist_accuracy.py -m network"""
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
    
    # AI yokken yorum üretilmez: gövde boş, özet KAP başlığının kendisi; yargı etiketi yok.
    assert body == ""
    assert summary == "İşleme Açılan Temerrüt Sırası"
    assert "Pozitif" not in body
    assert "Sinyal" not in body
    assert "🟢" not in body
    assert "🚨" not in body
    assert "⚡" not in body
    assert "🎯" not in body
    assert "📊" not in body
    assert "🟢" not in summary
    assert "🚨" not in summary
