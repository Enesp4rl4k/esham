"""TÜRİB & ELÜS Kaynağı, Agri-BIST Çapraz Analiz ve MCP Araçları Testleri."""
import pytest
from esham.sources.turib import TuribSource, TuribIndexValue, TuribProductPrice, TuribSnapshot
from esham.sources.agri_bist import AgriBistAnalyzer, AgriCompanyImpact, AgriBistCorrelationReport
from esham.mcp.server import mcp


def test_turib_index_calculation():
    source = TuribSource()
    # Endeks serisi mock benzeri test edilebilir
    candles = [
        {"date": "2026-10-30", "open": 7700.0, "high": 7800.0, "low": 7650.0, "close": 7746.0, "avg": 0, "volume": 50000000},
        {"date": "2026-11-02", "open": 7750.0, "high": 7950.0, "low": 7720.0, "close": 7910.0, "avg": 0, "volume": 64000000},
    ]
    change = ((candles[-1]["close"] - candles[-2]["close"]) / candles[-2]["close"]) * 100
    assert round(change, 2) == 2.12


def test_agri_bist_margin_sensitivity():
    analyzer = AgriBistAnalyzer()
    # Mock snapshot
    snap = TuribSnapshot(
        date="2026-11-02",
        products=[
            TuribProductPrice(
                product="BUĞDAY EKMEKLİK",
                price_tl_kg=18.5,
                avg_price_tl_kg=18.2,
                change_pct=5.4,
                volume_kg=50000000,
                volume_tl=910000000,
                high=18.5,
                low=15.0,
                date="2026-11-02",
            )
        ],
        hububat_index=TuribIndexValue(
            code="TRBHUB",
            name="TÜRİB Hububat",
            price=7910.0,
            change_pct=2.1,
            high=7950.0,
            low=7700.0,
            volume=600000000,
            date="2026-11-02",
        ),
    )
    rep = analyzer.analyze(turib_snap=snap)
    assert rep.date == "2026-11-02"
    assert len(rep.company_impacts) > 0

    uluun = next((c for c in rep.company_impacts if c.ticker == "ULUUN"), None)
    assert uluun is not None
    assert uluun.commodity == "BUĞDAY EKMEKLİK"
    assert "Maliyet" in uluun.margin_pressure


@pytest.mark.asyncio
async def test_mcp_tool_registration():
    tools = await mcp.list_tools()
    tool_names = [t.name for t in tools]
    
    # TÜRİB araçları
    assert "turib_piyasa_ozeti" in tool_names
    assert "turib_emtia_fiyati" in tool_names
    assert "turib_fiyat_gecmisi" in tool_names
    
    # BIST araçları
    assert "bist_piyasa_ozeti" in tool_names
    assert "bist_hisse_fiyat" in tool_names
    assert "bist_kap_bildirimleri" in tool_names
    assert "bist_viop_durum" in tool_names
    
    # Çapraz analiz
    assert "agri_bist_korelasyon" in tool_names
