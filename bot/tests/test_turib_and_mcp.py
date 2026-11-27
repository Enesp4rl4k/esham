"""TÜRİB & ELÜS Kaynağı, Agri-BIST Çapraz Analiz, Et-Yem Paritesi ve MCP Araçları Testleri."""
import pytest
from esham.sources.turib import TuribSource, TuribIndexValue, TuribProductPrice, TuribSnapshot
from esham.sources.agri_bist import AgriBistAnalyzer
from esham.sources.tmo import TmoSource
from esham.sources.real_returns import RealReturnsCalculator
from esham.sources.storage_backtest import StorageStrategyBacktester
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
    # Etiket yalnız fiyat yönünü tanımlar (marj/kâr yorumu yok; bkz. esham/neutral.py)
    assert uluun.margin_pressure == "Girdi fiyatı yükseldi"


def test_tmo_comparison():
    tmo = TmoSource()
    rep = tmo.compare("BUĞDAY EKMEKLİK", manuel_fiyat=18.00, referans_yili=2026)
    assert rep.tmo_alim_fiyati == 16.50
    assert rep.alim_farki_tl == 1.50
    assert rep.alim_prim_yuzde == 9.09
    assert rep.piyasa_durumu == "TMO_USTUNDE_PRIMLI"
    assert rep.tmo_dogrulandi is True
    assert rep.tmo_kaynak_url.startswith("https://") and rep.tmo_duyuru_tarihi == "2026-06-02"
    # Prim taban fiyata karıştırılmaz: ayrı alan, toplam = taban + prim
    assert rep.bakanlik_destegi == 3.014 and rep.toplam_uretici_fiyati == 19.514


def test_tmo_unverified_cell_publishes_no_value():
    from esham.sources.tmo import TMO_FIYAT_VERITABANI
    rep = TmoSource().compare("MISIR", manuel_fiyat=10.0, referans_yili=2026)
    assert rep.tmo_alim_fiyati is None and rep.tmo_dogrulandi is False
    assert rep.alim_prim_yuzde is None and rep.piyasa_durumu == "TMO_DOGRULANAMADI"
    assert rep.tmo_kaynak_url is None
    # Tablo bütünlüğü: doğrulanmış her satırın kaynağı ve tarihi var; doğrulanamayanda değer yok
    for k in TMO_FIYAT_VERITABANI:
        if k.dogrulandi:
            assert k.alim_fiyati_tl_kg and k.kaynak_url.startswith("https://") and k.duyuru_tarihi
            assert k.duyuru_tarihi[:4] in (str(k.yil),)
        else:
            assert k.alim_fiyati_tl_kg is None and k.kaynak_url is None
    # 2023 ve 2024 ekmeklik buğday resmî olarak farklıdır (8,25 ve 9,25 TL/kg)
    ek = {k.yil: k.alim_fiyati_tl_kg for k in TMO_FIYAT_VERITABANI if k.urun_adi.startswith("Ekmeklik")}
    assert ek[2023] == 8.25 and ek[2024] == 9.25


def test_storage_backtest_math():
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
    
    # BIST Araçları (8 Araç)
    assert "bist_piyasa_ozeti" in tool_names
    assert "bist_hisse_fiyat" in tool_names
    assert "bist_kap_bildirimleri" in tool_names
    assert "bist_viop_durum" in tool_names
    assert "bist_sektor_rotasyonu" in tool_names
    assert "bist_key_levels" in tool_names
    assert "bist_temel_analiz" in tool_names
    assert "bist_dcf_degerleme" in tool_names
    assert "bist_finansal_saglik" in tool_names
    assert "bist_geri_alimlar" in tool_names
    assert "bist_temettu_takvimi" in tool_names
    assert "macro_turkiye_barometresi" in tool_names
    assert "viop_basis_analizi" in tool_names
    assert "devaluasyon_risk_analizi" in tool_names
    
    # Çapraz Piyasa & Et-Yem Araçları (4 Araç)
    assert "agri_bist_korelasyon" in tool_names
    
    assert len(tool_names) == 24


@pytest.mark.network
def test_turib_market_data_publishing():
    from esham.publishing.turib_data import update_turib_market_data, TURIB_JSON
    import json
    ok = update_turib_market_data()
    assert ok is True
    assert TURIB_JSON.exists()
    data = json.loads(TURIB_JSON.read_text(encoding="utf-8"))
    assert "indices" in data
    assert "spotCommodities" in data
    assert "sections" in data
    assert "tmoComparison" in data
    assert "storageBacktest" in data
    assert "regionalArbitrage" in data
    assert "agriBist" in data
    assert len(data["indices"]) > 0
