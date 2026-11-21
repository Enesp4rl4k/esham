"""Esham BIST + TÜRİB (ELÜS) Unified MCP Server.

Borsa İstanbul (BIST 100, KAP, VİOP, Sektörler, Peer) ve
Türkiye Ürün İhtisas Borsası (TÜRİB ELÜS emtia fiyatları, hububat endeksleri,
günlük bültenler) piyasalarını Claude, Cursor, Windsurf ve diğer LLM
ajanlarına açan birleşik MCP sunucusu.
"""
from __future__ import annotations

import json
from typing import Any

from mcp.server.mcpserver import MCPServer

from ..sources.bist import BistSource
from ..sources.kap import KapSource
from ..sources.kap_filter import is_significant as _kap_significant
from ..sources.viop import ViopSource, assess_margin_stress
from ..sources.sector import SectorSource
from ..sources.peer import PeerSource
from ..sources.turib import TuribSource, ENDEKS_KODLARI, VARSAYILAN_URUNLER
from ..sources.agri_bist import AgriBistAnalyzer
from ..sources.meat_feed_index import ET_YEM_UNAVAILABLE, MeatFeedIndexAnalyzer
from ..sources.tmo import TmoSource
from ..sources.real_returns import RealReturnsCalculator
from ..sources.storage_backtest import StorageStrategyBacktester
from ..sources.regional_arbitrage import RegionalArbitrageScanner

# MCP Sunucusunu Başlat
mcp = MCPServer(
    name="esham-market-mcp",
    instructions=(
        "Esham Market MCP: Borsa İstanbul (BIST) ve TÜRİB (Elektronik Ürün Senedi - ELÜS) "
        "piyasaları için birleşik finans ve tarımsal emtia araştırma asistanı. "
        "BIST hisseleri, KAP bildirimleri, VİOP teminatları, TÜRİB buğday/mısır/arpa fiyatları "
        "ve gıda sektörü maliyet korelasyonlarını sunar."
    ),
)


# ============================================================================
# TÜRİB / ELÜS ARAÇLARI (Tarımsal Emtia & Hububat)
# ============================================================================

@mcp.tool()
def turib_piyasa_ozeti() -> dict[str, Any]:
    """TÜRİB ELÜS tarımsal emtia piyasasının son durum özeti.
    
    Hububat Endeksi (TRBHUB), Buğday Ekmeklik/Makarnalık, Mısır, Arpa
    ağırlıklı ortalama TL/kg fiyatları, değişimleri ve toplam işlem hacmi.
    """
    source = TuribSource()
    snap = source.snapshot()
    return {
        "tarih": snap.date,
        "ozet_metin": snap.summary_text,
        "hububat_endeksi": {
            "kod": snap.hububat_index.code if snap.hububat_index else "TRBHUB",
            "deger": snap.hububat_index.price if snap.hububat_index else None,
            "degisim_yuzde": snap.hububat_index.change_pct if snap.hububat_index else None,
        } if snap.hububat_index else None,
        "urunler": [
            {
                "urun": p.product,
                "ortalama_fiyat_tl_kg": p.avg_price_tl_kg,
                "son_fiyat_tl_kg": p.price_tl_kg,
                "degisim_yuzde": p.change_pct,
                "hacim_ton": round(p.volume_kg / 1000.0, 1),
                "hacim_tl": p.volume_tl,
                "en_yuksek": p.high,
                "en_dusuk": p.low,
            }
            for p in snap.products
        ],
        "toplam_hacim_ton": round(snap.total_volume_tons, 1),
        "toplam_hacim_tl": snap.total_volume_tl,
    }


@mcp.tool()
def turib_emtia_fiyati(urun: str = "BUĞDAY EKMEKLİK") -> dict[str, Any]:
    """Belirtilen tarımsal emtianın TÜRİB'deki son işlem ve ağırlıklı ortalama fiyatı.
    
    Geçerli örnek ürünler: 'BUĞDAY EKMEKLİK', 'BUĞDAY MAKARNALIK', 'MISIR', 'ARPA'.
    Fiyatlar TL/kg cinsindendir.
    """
    source = TuribSource()
    price_info = source.fetch_latest_product_price(urun.upper())
    if not price_info:
        return {"hata": f"TÜRİB üzerinde '{urun}' için güncel fiyat bulunamadı."}
    return {
        "urun": price_info.product,
        "tarih": price_info.date,
        "ortalama_fiyat_tl_kg": price_info.avg_price_tl_kg,
        "kapanis_fiyati_tl_kg": price_info.price_tl_kg,
        "degisim_yuzde": price_info.change_pct,
        "en_yuksek_tl_kg": price_info.high,
        "en_dusuk_tl_kg": price_info.low,
        "islem_hacmi_kg": price_info.volume_kg,
        "islem_hacmi_ton": round(price_info.volume_kg / 1000.0, 1),
        "islem_tutari_tl": price_info.volume_tl,
    }


@mcp.tool()
def turib_fiyat_gecmisi(urun: str = "BUĞDAY EKMEKLİK", bar_sayisi: int = 30) -> list[dict[str, Any]]:
    """Belirtilen emtianın son N günlük TÜRİB OHLCV mum geçmişi.
    
    Dönen her mum: tarih, açılış, yüksek, düşük, kapanış, ağırlıklı ortalama ve hacim (kg).
    """
    source = TuribSource()
    candles = source.fetch_product_series(urun.upper())
    return candles[-bar_sayisi:] if candles else []


@mcp.tool()
def turib_endeks_serisi(endeks_kodu: str = "TRBHUB", bar_sayisi: int = 30) -> list[dict[str, Any]]:
    """TÜRİB endeksinin (TRBHUB, TRBBGD, TRBMSR, TRBARP) günlük mum geçmişi."""
    source = TuribSource()
    candles = source.fetch_index_series(endeks_kodu.upper())
    return candles[-bar_sayisi:] if candles else []


@mcp.tool()
def turib_tmo_karsilastir(urun_grubu: str = "BUĞDAY EKMEKLİK", referans_yili: int = 2026) -> dict[str, Any]:
    """TÜRİB serbest borsa fiyatını Toprak Mahsulleri Ofisi (TMO) müdahale alım/satış fiyatlarıyla kıyaslar.
    
    TMO taban çıpasını, çiftçi prim desteğini ve serbest piyasanın TMO'ya göre prim/iskonto durumunu döner.
    """
    tmo = TmoSource()
    rep = tmo.compare(urun_grubu, referans_yili=referans_yili)
    return {
        "urun_grubu": rep.urun_grubu,
        "serbest_piyasa_fiyati_tl_kg": rep.serbest_piyasa_fiyati,
        "tarih": rep.tarih,
        "tmo_referans": {
            "yil": rep.tmo_yil,
            "urun_adi": rep.tmo_urun_adi,
            "tmo_alim_taban_tl_kg": rep.tmo_alim_fiyati,
            "bakanlik_prim_destegi_tl_kg": rep.bakanlik_destegi,
            "toplam_uretici_fiyati_tl_kg": rep.toplam_uretici_fiyati,
            "tmo_satis_fiyati_tl_kg": rep.tmo_satis_fiyati,
        },
        "analiz": {
            "tmo_alima_gore_fark_tl": rep.alim_farki_tl,
            "tmo_alima_gore_prim_yuzde": rep.alim_prim_yuzde,
            "tmo_toplama_gore_fark_tl": rep.toplam_fark_tl,
            "tmo_toplama_gore_prim_yuzde": rep.toplam_prim_yuzde,
            "tmo_satisa_gore_fark_tl": rep.satis_farki_tl,
            "piyasa_durumu": rep.piyasa_durumu,
            "piyasa_yorumu": rep.piyasa_yorumu,
        },
    }


@mcp.tool()
def turib_tmo_fiyat_listesi(yil: int | None = 2026, kategori: str | None = None) -> list[dict[str, Any]]:
    """Resmî TMO müdahale alım ve prim fiyatları arşiv listesi (2021-2026)."""
    tmo = TmoSource()
    kayitlar = tmo.list_records(yil=yil, kategori=kategori)
    return [
        {
            "yil": k.yil,
            "kategori": k.kategori,
            "urun_adi": k.urun_adi,
            "alim_fiyati_tl_kg": k.alim_fiyati_tl_kg,
            "bakanlik_destegi_tl_kg": k.bakanlik_destegi_tl_kg,
            "toplam_uretici_fiyati_tl_kg": k.toplam_uretici_fiyati_tl_kg,
            "tmo_satis_fiyati_tl_kg": k.satis_fiyati_tl_kg,
            "notlar": k.notlar,
        }
        for k in kayitlar
    ]


@mcp.tool()
def turib_reel_getiri(
    urun_grubu: str = "BUĞDAY EKMEKLİK",
    baslangic_tarihi: str | None = "2022-01-01",
    bitis_tarihi: str | None = None,
) -> dict[str, Any]:
    """TÜRİB tarım emtiasının TCMB kurları (USD, EUR) ve TÜİK TÜFE enflasyonundan arındırılmış reel getiri analizi.
    
    Nominal TL getirisinin gerçek satın alma gücünü koruyup korumadığını hesaplar.
    """
    calc = RealReturnsCalculator()
    rep = calc.calculate(urun_grubu, baslangic=baslangic_tarihi, bitis=bitis_tarihi)
    return {
        "urun_grubu": rep.urun_grubu,
        "donem": {
            "baslangic": rep.baslangic_tarihi,
            "bitis": rep.bitis_tarihi,
            "islem_gun_sayisi": rep.islem_gun_sayisi,
        },
        "fiyatlar": {
            "ilk_fiyat_tl": rep.ilk_fiyat_tl,
            "son_fiyat_tl": rep.son_fiyat_tl,
            "ilk_fiyat_usd": rep.ilk_fiyat_usd,
            "son_fiyat_usd": rep.son_fiyat_usd,
            "ilk_fiyat_eur": rep.ilk_fiyat_eur,
            "son_fiyat_eur": rep.son_fiyat_eur,
        },
        "getiriler": {
            "nominal_tl_getiri_yuzde": rep.nominal_tl_getiri_pct,
            "dolar_usd_getiri_yuzde": rep.usd_getiri_pct,
            "euro_eur_getiri_yuzde": rep.eur_getiri_pct,
            "enflasyondan_arindirilmis_reel_getiri_yuzde": rep.reel_enflasyon_getiri_pct,
        },
        "analiz_yorumu": rep.analiz_yorumu,
    }


@mcp.tool()
def turib_depolama_backtest(
    urun_grubu: str = "BUĞDAY EKMEKLİK",
    yillik_faiz_yuzde: float = 45.0,
) -> dict[str, Any]:
    """Tarımsal depolama stratejisi simülatörü (2020-2026 backtest).
    
    'Hasatta Spot Sat' vs '3 Ay Depola' vs '6 Ay Depola' vs '9 Ay Depola' stratejilerini
    resmî lisanslı depo kirası, yasal fire ve finansman maliyetiyle test eder.
    """
    bt = StorageStrategyBacktester()
    rep = bt.run_backtest(urun_grubu, yillik_faiz_pct=yillik_faiz_yuzde)
    return {
        "urun_grubu": rep.urun_grubu,
        "test_edilen_sezon_sayisi": rep.test_edilen_sezon_sayisi,
        "varsayimlar": {
            "yillik_finansman_faizi_yuzde": rep.yillik_faiz_pct,
            "depolama_kaynagi": "Resmî LİDAŞ kira tarifesi (günlük ~0.005 TL/kg)",
            "yasal_fire_orani": "Uygulandı (%0.35 - %1.15)",
        },
        "istatistikler": {
            "strateji_3ay_kazanma_orani_yuzde": rep.strateji_3ay_kazanma_orani_pct,
            "strateji_6ay_kazanma_orani_yuzde": rep.strateji_6ay_kazanma_orani_pct,
            "strateji_9ay_kazanma_orani_yuzde": rep.strateji_9ay_kazanma_orani_pct,
            "ortalama_6ay_net_getiri_yuzde": rep.ortalama_6ay_net_getiri_pct,
            "en_basarili_strateji": rep.en_basarili_strateji,
        },
        "sezon_detaylari": [
            {
                "sezon": s.sezon_yili,
                "spot_hasat_fiyati": s.hasat_spot_fiyati,
                "kazanan": s.kazanan_strateji,
                "strateji_sonuclari": [
                    {
                        "vade": x.strateji_adi,
                        "satis_fiyati": x.satis_fiyati,
                        "toplam_maliyet_tl_kg": x.toplam_maliyet_tl_kg,
                        "net_kar_tl_kg": x.net_kar_zarar_tl_kg,
                        "net_getiri_yuzde": x.net_getiri_pct,
                        "spotu_gecti_mi": x.spotu_gecti_mi,
                    }
                    for x in s.stratejiler
                ],
            }
            for s in rep.sezon_sonuclari
        ],
        "stratejik_tavsiye": rep.stratejik_tavsiye,
    }


@mcp.tool()
def turib_bolgesel_arbitraj(
    urun: str = "BUĞDAY",
    tahmini_nakliye_maliyeti_tl_kg: float = 0.50,
) -> dict[str, Any]:
    """TÜRİB günlük bülteninde iller ve lisanslı depolar (LİDAŞ) arasındaki fiyat makasını tarar.
    
    Nakliye maliyetini düşerek risksiz net arbitraj potansiyeli olan rotaları tespit eder.
    """
    scanner = RegionalArbitrageScanner()
    rep = scanner.scan(urun=urun, nakliye_maliyeti_tl_kg=tahmini_nakliye_maliyeti_tl_kg)
    return {
        "bulten_tarihi": rep.tarih,
        "urun": rep.urun_filtresi,
        "taranan_islem_adedi": rep.taranan_islem_sayisi,
        "genel_degerlendirme": rep.genel_degerlendirme,
        "en_iyi_arbitraj_rotalari": [
            {
                "alim_yapilacak_depo": f"{f.ucuz_il} ({f.ucuz_lidas})",
                "alim_fiyati": f.ucuz_fiyat,
                "satis_yapilacak_depo": f"{f.pahali_il} ({f.pahali_lidas})",
                "satis_fiyati": f.pahali_fiyat,
                "brut_fark_tl_kg": f.brut_makas_tl_kg,
                "nakliye_maliyeti_tl_kg": f.tahmini_nakliye_tl_kg,
                "net_arbitraj_tl_kg": f.net_arbitraj_tl_kg,
                "net_kar_marji_yuzde": f.net_arbitraj_pct,
                "firsat_seviyesi": f.firsat_seviyesi,
                "not": f.aciklama,
            }
            for f in rep.en_iyi_firsatlar
        ],
        "bolgesel_fiyat_tablosu": [
            {
                "il": b.il,
                "lidas": b.lidas_adi,
                "fiyat_tl_kg": b.agirlikli_ortalama_fiyat,
                "miktar_ton": round(b.toplam_miktar_kg / 1000.0, 1),
            }
            for b in rep.bolgesel_fiyatlar[:8]
        ],
    }


# ============================================================================
# BIST ARAÇLARI (Borsa İstanbul, KAP, VİOP, Sektörler)
# ============================================================================

@mcp.tool()
def bist_piyasa_ozeti(endeks: str = "XU100") -> dict[str, Any]:
    """BIST 100 veya BIST 30 endeksinin son işlem fiyatı, günlük yüzdelik değişimi ve hacmi."""
    symbol = f"{endeks.upper()}.IS" if not endeks.endswith(".IS") else endeks.upper()
    source = BistSource(symbol=symbol)
    summary = source.market_summary()
    return {
        "endeks": summary.index,
        "fiyat": summary.price,
        "degisim": summary.change,
        "hacim": summary.volume,
    }


@mcp.tool()
def bist_hisse_fiyat(ticker: str) -> dict[str, Any]:
    """Borsa İstanbul'da işlem gören bir hissenin (ör. THYAO, EREGL, ULUUN) son fiyatı ve değişimi."""
    symbol = f"{ticker.upper()}.IS" if not ticker.endswith(".IS") else ticker.upper()
    source = BistSource(symbol=symbol)
    summary = source.market_summary()
    return {
        "sembol": ticker.upper(),
        "fiyat_tl": summary.price,
        "gunluk_degisim": summary.change,
        "hacim": summary.volume,
    }


@mcp.tool()
def bist_kap_bildirimleri(limit: int = 10, sadece_onemli: bool = True) -> list[dict[str, Any]]:
    """Kamuyu Aydınlatma Platformu (KAP) son bildirimleri.
    
    sadece_onemli=True seçildiğinde rutin/idari bildirimler elenir,
    yalnızca finansal ve operasyonel etkisi olan bildirimler döner.
    """
    raw = KapSource().latest_disclosures()
    if sadece_onemli:
        disclosures = [d for d in raw if _kap_significant(d)]
    else:
        disclosures = raw

    return [
        {
            "sirket": d.company,
            "ticker": d.ticker,
            "baslik": d.title,
            "tarih": d.date,
            "tur": d.disclosure_type,
            "pdf_link": d.pdf_link,
            "insider": d.is_insider,
        }
        for d in disclosures[:limit]
    ]


@mcp.tool()
def bist_viop_durum() -> dict[str, Any]:
    """VİOP vadeli işlem piyasası kotasyonu ve Takasbank teminat stresi analizi.

    Gerçek veri alınamayan alanlar None döner; sabit/örnek değer üretilmez."""
    viop = ViopSource()
    quote = viop.market_quote()
    margin = viop.margin_snapshot()
    stress = assess_margin_stress(margin.margin_call_to_required_pct) if margin else None
    fut = quote if quote is not None and quote.has_futures else None
    stress_level = stress.level if stress else "Bilinmiyor"
    stress_note = stress.note if stress else ""

    return {
        "endeks_sembol": quote.index_symbol if quote else None,
        "endeks_fiyat": quote.index_price if quote else None,
        "endeks_degisim": quote.index_change if quote else None,
        "vadeli_sembol": fut.futures_symbol if fut else None,
        "vadeli_fiyat": fut.futures_price if fut else None,
        "vadeli_degisim": fut.futures_change if fut else None,
        "takasbank_teminat": {
            "veri_tarihi": margin.as_of,
            "teminatli_hesap_sayisi": margin.margined_account_count,
            "teminat_tamamlama_toplam_tl": margin.margin_call_total_tl,
            "gereken_teminat_toplam_tl": margin.required_margin_total_tl,
            "teminat_tamamlama_orani_yuzde": margin.margin_call_to_required_pct,
            "stres_seviyesi": stress_level,
            "stres_yorumu": stress_note,
        } if margin else None,
    }


@mcp.tool()
def bist_sektor_rotasyonu() -> list[dict[str, Any]]:
    """BIST sektör endekslerinin (Bankacılık, Sınai, Gıda, Ulaştırma vb.) haftalık performansı."""
    source = SectorSource()
    moves = source.snapshot()
    return [
        {
            "sektor": m.name,
            "kod": m.code,
            "haftalik_degisim_yuzde": m.change_pct,
            "yon": "yukari" if m.change_pct >= 0 else "asagi",
        }
        for m in moves
    ]


@mcp.tool()
def bist_key_levels(ticker: str) -> dict[str, Any]:
    """Borsa İstanbul hissesi için Pivot noktaları, R1-R2 dirençleri, S1-S2 destekleri,
    Fibonacci seviyeleri (%38.2, %50, %61.8), 14G RSI, 20G/50G HO ve 52 haftalık zirve/dip seviyelerini hesaplar."""
    from ..sources.bist_quant import BistQuantAnalyzer
    analyzer = BistQuantAnalyzer()
    res = analyzer.get_key_levels(ticker)
    if not res:
        return {"hata": f"{ticker} için teknik seviyeler hesaplanamadı."}
    return res.to_dict()


@mcp.tool()
def bist_temel_analiz(ticker: str, sozlesme_tutari_tl: float | None = None) -> dict[str, Any]:
    """Borsa İstanbul şirketinin temel analiz çarpanlarını (Piyasa Değeri, F/K, PD/DD, FD/FAVÖK,
    yıllık hasılat, net kâr marjı, ROE) çeker. İsteğe bağlı olarak verilen sözleşme tutarının (TL)
    yıllık ciroya oranını (Ciro Etki Çarpanı) hesaplar."""
    from ..sources.bist_quant import BistQuantAnalyzer
    analyzer = BistQuantAnalyzer()
    res = analyzer.get_fundamental_metrics(ticker, contract_amount_try=sozlesme_tutari_tl)
    if not res:
        return {"hata": f"{ticker} için temel analiz verileri alınamadı."}
    return res.to_dict()


@mcp.tool()
def bist_dcf_degerleme(
    ticker: str,
    wacc: float | None = None,
    buyume_orani: float | None = None,
    uc_buyume_orani: float | None = None,
    tahmin_yili: int = 5,
) -> dict[str, Any]:
    """Borsa İstanbul hissesi için İndirgenmiş Nakit Akışı (İNA / DCF) değerleme modeli çalıştırır.
    
    Serbest nakit akımı (FCF), firma değeri (EV), net borç köprüsü, hisse başına adil değer,
    prim/iskonto potansiyeli (%), 5x5 WACC vs. Uç Büyüme duyarlılık matrisi ve Ayı/Baz/Boğa senaryolarını üretir.
    Parametre verilmezse şirketin fonksiyonel para birimine (TRY/USD) uygun varsayılan oranlar kullanılır."""
    from ..sources.bist_quant import BistQuantAnalyzer
    analyzer = BistQuantAnalyzer()
    res = analyzer.calculate_dcf(
        ticker,
        wacc=wacc,
        growth_rate=buyume_orani,
        terminal_growth=uc_buyume_orani,
        projection_years=tahmin_yili,
    )
    if not res:
        return {"hata": f"{ticker} için DCF değerlemesi hesaplanamadı (pozitif serbest nakit akımı veya bilanço verisi eksik)."}
    return res.to_dict()


@mcp.tool()
def bist_finansal_saglik(ticker: str) -> dict[str, Any]:
    """Borsa İstanbul şirketi için Piotroski F-Score (0-9), Altman Z-Score iflas riski ve 3 Aşamalı DuPont kârlılık analizini hesaplar.
    
    9 kriterli Piotroski F-Skoru (kârlılık, likidite/kaldıraç, operasyonel verimlilik), Altman Z-Skoru (Güvenli, Gri, Riskli bölge)
    ve DuPont ROE ayrıştırması (Net Kâr Marjı x Aktif Devir Hızı x Finansal Kaldıraç) sunar."""
    from ..sources.bist_quant import BistQuantAnalyzer
    analyzer = BistQuantAnalyzer()
    res = analyzer.get_financial_health(ticker)
    if not res:
        return {"hata": f"{ticker} için finansal sağlık metrikleri hesaplanamadı."}
    return res.to_dict()


@mcp.tool()
def bist_geri_alimlar(ticker: str | None = None) -> list[dict[str, Any]]:
    """Borsa İstanbul şirketlerinin aktif pay geri alım (share buyback) programlarını listeler.
    
    Ayrılan fon tutarı, azami lot, geri alınan lot, sermaye oranı (%), ortalama maliyet
    ve piyasa fiyatına göre prim/iskonto getirisini sunar."""
    from ..sources.bist_corporate_actions import BistCorporateActionsSource
    source = BistCorporateActionsSource()
    return [b.to_dict() for b in source.get_buybacks(ticker)]


@mcp.tool()
def bist_temettu_takvimi(ticker: str | None = None) -> list[dict[str, Any]]:
    """Borsa İstanbul şirketlerinin temettü dağıtım takvimi, net temettü tutarları ve temettü verimlerini listeler.
    
    Hak kullanım (ex-date) ve ödeme tarihleri, kâr dağıtım oranları (%) ve hisse başına net tutarları gösterir."""
    from ..sources.bist_corporate_actions import BistCorporateActionsSource
    source = BistCorporateActionsSource()
    return [d.to_dict() for d in source.get_dividends(ticker)]


@mcp.tool()
def macro_turkiye_barometresi() -> dict[str, Any]:
    """Türkiye 5 Yıllık CDS Primi, TCMB Brüt / Net / Swap Hariç Net Rezervleri ve Hisse Risk Primini (ERP) sunar.
    
    Piyasa risk iştahını ve getiri dengesini (mevduat vs tahvil vs hisse) analiz eder."""
    from ..sources.macro_radar import MACRO_BAROMETER_UNAVAILABLE, MacroRadarAnalyzer
    MacroRadarAnalyzer().get_macro_barometer()  # kaynak yok: her zaman None (uyarı loglanır)
    return {"veri": None, "neden": MACRO_BAROMETER_UNAVAILABLE}


@mcp.tool()
def viop_basis_analizi() -> dict[str, Any]:
    """VİOP BIST 30 vadeli kontratı ile spot endeks arasındaki basis (puan ve %), canlı kotasyondan.
    Kotasyon alınamazsa veri None döner; sabit/örnek değer üretilmez."""
    from ..sources.macro_radar import VIOP_BASIS_UNAVAILABLE, MacroRadarAnalyzer
    res = MacroRadarAnalyzer().get_viop_basis()
    if res is None:
        return {"veri": None, "neden": VIOP_BASIS_UNAVAILABLE}
    return res.to_dict()


@mcp.tool()
def devaluasyon_risk_analizi() -> dict[str, Any]:
    """TRY Devalüasyon / Kur Şoku Basınç Endeksi (0-100) ve risk seviyesini sunar.
    
    VİOP USDTRY ima edilen faiz vs TCMB politika faizi, TCMB swap hariç rezerv yanma hızı,
    Kapalıçarşı (Tahtakale) vs bankalararası makas, Türkiye 5Y CDS ve TÜFE Reel Efektif Kur (REER)
    bileşenlerini ve kriz stres kıyaslamalarını analiz eder."""
    from ..sources.devaluation_radar import DEVALUATION_RADAR_UNAVAILABLE, DevaluationRadarAnalyzer
    res = DevaluationRadarAnalyzer().analyze()
    return {"veri": res, "neden": DEVALUATION_RADAR_UNAVAILABLE if res is None else None}


# ============================================================================
# ÇAPRAZ PİYASA (BIST x TÜRİB) ARAÇLARI
# ============================================================================

@mcp.tool()
def et_yem_paritesi() -> dict[str, Any]:
    """Türkiye hayvancılık sektörü kârlılık göstergesi: Dana Karkas, Tavuk ve Kuzu et-yem pariteleri.
    
    1 kg karkas et ile kaç kg fabrika yemi veya TÜRİB arpa/mısır alınabildiğini hesaplar.
    Dana besisinde 20 eşiği kârlılık, 18 altı ise üretici zararı ve arz krizi sinyalidir.
    """
    analyzer = MeatFeedIndexAnalyzer()
    rep = analyzer.analyze()
    if rep is None:
        return {"veri": None, "neden": ET_YEM_UNAVAILABLE}
    return {
        "tarih": rep.tarih,
        "pariteler": [
            {
                "kategori": p.kategori,
                "karkas_fiyati_tl_kg": p.karkas_fiyati_tl_kg,
                "yem_fiyati_tl_kg": p.yem_fiyati_tl_kg,
                "parite_orani": p.parite_orani,
                "ideal_basabas_esigi": p.esik_basabasi,
                "durum": p.kar_marji_durumu,
                "yorum": p.sinyal_yorumu,
            }
            for p in rep.pariteler
        ],
        "bist_etkisi": rep.bist_etkisi_ozeti,
    }


@mcp.tool()
def et_tufe_endeksi() -> dict[str, Any]:
    """TÜİK Et ve Et Ürünleri TÜFE Endeksi ile Manşet TÜFE enflasyonu ayrışma analizi.
    
    Yıllık et enflasyonunun genel tüketici enflasyonuna göre primini (Et Enflasyon Primi)
    ve TÜRİB yem emtiasından tüketici et fiyatlarına geçişkenliği sunar.
    """
    analyzer = MeatFeedIndexAnalyzer()
    rep = analyzer.analyze()
    if rep is None:
        return {"veri": None, "neden": ET_YEM_UNAVAILABLE}
    return {
        "tarih": rep.tarih,
        "et_tufe_endeks_degeri": rep.et_tufe_endeks,
        "manset_tufe_endeks_degeri": rep.manset_tufe_endeks,
        "yillik_et_enflasyonu_yuzde": rep.et_enflasyonu_yillik_pct,
        "yillik_manset_enflasyon_yuzde": rep.manset_enflasyon_yillik_pct,
        "et_enflasyon_primi_puan": rep.et_enflasyon_primi_pct,
        "makro_degerlendirme": rep.makro_degerlendirme,
    }


@mcp.tool()
def et_sektoru_bist_etkisi() -> dict[str, Any]:
    """Et-yem pariteleri ve Et TÜFE enflasyonunun BIST hisselerine (BANVT, PETUN, BIMAS, MGROS) kârlılık yansıması."""
    analyzer = MeatFeedIndexAnalyzer()
    rep = analyzer.analyze()
    if rep is None:
        return {"veri": None, "neden": ET_YEM_UNAVAILABLE}
    return {
        "tarih": rep.tarih,
        "bist_etkisi_ozeti": rep.bist_etkisi_ozeti,
        "makro_degerlendirme": rep.makro_degerlendirme,
    }


@mcp.tool()
def agri_bist_korelasyon() -> dict[str, Any]:
    """BIST Gıda Endeksi (XGIDA) ve hisseleri (ULUUN, BANVT, TATGD, PETUN, TUKAS) ile
    TÜRİB ELÜS tarımsal emtia fiyatlarının (Buğday, Mısır, Arpa) çapraz marj ve kârlılık analizi.
    
    Emtia fiyat artışlarının şirket girdi maliyetlerine ve hisse kârlılıklarına etkisini inceler.
    """
    analyzer = AgriBistAnalyzer()
    rep = analyzer.analyze()
    return {
        "tarih": rep.date,
        "xgida_endeks_fiyati": rep.xgida_price,
        "xgida_gunluk_degisim": rep.xgida_change,
        "turib_hububat_endeksi": rep.turib_hububat_index,
        "turib_hububat_degisimi": rep.turib_hububat_change,
        "sirket_etkileri": [
            {
                "hisse": c.ticker,
                "sirket": c.company_name,
                "hisse_fiyati": c.stock_price,
                "hisse_degisimi": c.stock_change,
                "bagli_emtia": c.commodity,
                "emtia_fiyati_tl_kg": c.commodity_price,
                "emtia_gunluk_degisimi": f"%{c.commodity_change}",
                "marj_baskisi": c.margin_pressure,
                "yorum": c.commentary,
            }
            for c in rep.company_impacts
        ],
        "makro_cikari": rep.macro_takeaway,
    }


# ============================================================================
# HAZIR PROMPT VE KAYNAKLAR
# ============================================================================

@mcp.prompt()
def kombine_piyasa_raporu() -> str:
    """BIST 100, VİOP, KAP ve TÜRİB ELÜS piyasasını bütüncül yorumlayan analiz promptu."""
    return (
        "Borsa İstanbul ve TÜRİB piyasalarını birlikte analiz et.\n"
        "Şu adımları izle:\n"
        "1. bist_piyasa_ozeti ile BIST 100 endeks ve hacim durumunu al.\n"
        "2. turib_piyasa_ozeti ile Hububat Endeksi ve buğday/mısır/arpa fiyatlarını al.\n"
        "3. agri_bist_korelasyon ile tarımsal emtia fiyatlarının BIST gıda şirketlerine (ULUUN, BANVT vb.) etkisini çıkar.\n"
        "4. bist_kap_bildirimleri ile son önemli şirket açıklamalarını incele.\n"
        "5. Elde ettiğin verilerle yatırımcılara yönelik profesyonel, veri odaklı bir günlük bülten hazırla."
    )


def run_server() -> None:
    """FastMCP sunucusunu stdio üzerinden çalıştırır."""
    mcp.run()


if __name__ == "__main__":
    run_server()
