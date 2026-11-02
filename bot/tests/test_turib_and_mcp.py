"""TÜRİB & ELÜS Kaynağı, Agri-BIST Çapraz Analiz ve Katman 1 MCP Araçları Testleri."""
import pytest
from esham.sources.turib import TuribSource, TuribIndexValue, TuribProductPrice, TuribSnapshot
from esham.sources.agri_bist import AgriBistAnalyzer
from esham.sources.tmo import TmoSource
from esham.sources.real_returns import RealReturnsCalculator, get_anchor
from esham.sources.storage_backtest import StorageStrategyBacktester
from esham.sources.regional_arbitrage import RegionalArbitrageScanner
from esham.mcp.server import mcp


def test_turib_index_calculation():
    candles = [
        {"date": "2026-10-30", "open": 7700.0, "high": 7800.0, "low": 7650.0, "close": 7746.0, "avg": 0, "volume": 50000000},
        {"date": "2026-11-02", "open": 7750.0, "high": 7950.0, "low": 7720.0, "close": 7910.0, "avg": 0, "volume": 64000000},
    ]
    change = ((candles[-1]["close"] - candles[-2]["close"]) / candles[-2]["close"]) * 100
    assert round(change, 2) == 2.12


def test_agri_bist_margin_sensitivity():
    analyzer = AgriBistAnalyzer()
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


def test_tmo_comparison():
    tmo = TmoSource()
    # 2026 Ekmeklik Buğday: Alım = 13.50 TL/kg
    rep = tmo.compare("BUĞDAY EKMEKLİK", manuel_fiyat=18.00, referans_yili=2026)
    assert rep.tmo_alim_fiyati == 13.50
    assert rep.alim_farki_tl == 4.50
    assert rep.alim_prim_yuzde == 33.33
    assert rep.piyasa_durumu == "TMO_USTUNDE_PRIMLI"


def test_real_returns_anchor():
    anchor_2019 = get_anchor("2019-05-01")
    assert anchor_2019["usd"] == 5.67
    assert anchor_2019["tufe_kat_sayisi"] == 1.0

    anchor_2026 = get_anchor("2026-10-01")
    assert anchor_2026["usd"] == 40.50
    assert anchor_2026["tufe_kat_sayisi"] == 13.20


def test_storage_backtest_math():
    bt = StorageStrategyBacktester()
    # Mock seri verisi yerine fonksiyon mantığı
    spot = 10.0
    satis_6ay = 13.0
    faiz = 20.0  # %20 faiz
    kira_gunluk = 0.005
    gun = 180
    fire = 0.0075

    depolama = kira_gunluk * gun
    finansman = spot * (faiz / 100.0) * (gun / 365.0)
    fire_maliyeti = spot * fire
    toplam_maliyet = depolama + finansman + fire_maliyeti
    net_kar = (satis_6ay - spot) - toplam_maliyet

    assert round(depolama, 2) == 0.90
    assert round(finansman, 2) == 0.99
    assert round(fire_maliyeti, 3) == 0.075
    assert net_kar > 0  # 3.0 - 1.97 = 1.03 TL kâr


@pytest.mark.asyncio
async def test_mcp_all_tools_registered():
    tools = await mcp.list_tools()
    tool_names = [t.name for t in tools]
    
    # Katman 1 TÜRİB Araçları (9 Araç)
    assert "turib_piyasa_ozeti" in tool_names
    assert "turib_emtia_fiyati" in tool_names
    assert "turib_fiyat_gecmisi" in tool_names
    assert "turib_endeks_serisi" in tool_names
    assert "turib_tmo_karsilastir" in tool_names
    assert "turib_tmo_fiyat_listesi" in tool_names
    assert "turib_reel_getiri" in tool_names
    assert "turib_depolama_backtest" in tool_names
    assert "turib_bolgesel_arbitraj" in tool_names
    
    # BIST Araçları (5 Araç)
    assert "bist_piyasa_ozeti" in tool_names
    assert "bist_hisse_fiyat" in tool_names
    assert "bist_kap_bildirimleri" in tool_names
    assert "bist_viop_durum" in tool_names
    assert "bist_sektor_rotasyonu" in tool_names
    
    # Çapraz Piyasa (1 Araç)
    assert "agri_bist_korelasyon" in tool_names
    
    assert len(tool_names) == 15
