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
    """VİOP vadeli işlem piyasası kotasyonu ve Takasbank teminat stresi analizi."""
    viop = ViopSource()
    quote = viop.market_quote()
    margin = viop.margin_snapshot()
    stress = assess_margin_stress(margin) if margin else None

    return {
        "viop_fiyat": quote.price if quote else None,
        "viop_degisim": quote.change if quote else None,
        "takasbank_teminat": {
            "toplam_teminat_tl": margin.total_margin_try if margin else None,
            "teminat_acigi_tl": margin.deficit_try if margin else None,
            "stres_seviyesi": stress.level if stress else "Bilinmiyor",
            "stres_yorumu": stress.commentary if stress else "",
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


# ============================================================================
# ÇAPRAZ PİYASA (BIST x TÜRİB) ARAÇLARI
# ============================================================================

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
