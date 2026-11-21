"""TÜRİB ELÜS, Et-Yem ve Tarımsal Emtia verilerini web/public/data/turib-market.json'a yazar.

Statik export (Cloudflare Pages) ortamında Next.js API route yerine bot tarafından
her tarama turunda bu modül çağrılır. Üretilen JSON dosyası /tarim-emtia sayfasında
kullanıcılar tarafından dinamik incelenir ve doğrudan ham veri olarak indirilebilir.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from ..config import PROJECT_ROOT, get_logger
from ..sources.turib import TuribSource
from ..sources.meat_feed_index import MeatFeedIndexAnalyzer
from ..sources.tmo import TmoSource
from ..sources.real_returns import RealReturnsCalculator
from ..sources.storage_backtest import StorageStrategyBacktester
from ..sources.regional_arbitrage import RegionalArbitrageScanner
from ..sources.agri_bist import AgriBistAnalyzer

log = get_logger(__name__)

TURIB_JSON = PROJECT_ROOT / "web" / "public" / "data" / "turib-market.json"


def generate_turib_market_data() -> dict[str, Any]:
    """Tüm tarım, emtia, TÜRİB ve et-yem veri setini yapılandırılmış sözlük olarak derler."""
    TR_TZ = timezone(timedelta(hours=3))
    now = datetime.now(TR_TZ)
    now_str = now.isoformat(timespec="seconds")
    date_str = now.strftime("%Y-%m-%d")

    data: dict[str, Any] = {
        "updatedAt": now_str,
        "date": date_str,
        "indices": [],
        "spotCommodities": [],
        "bulletinSummary": {},
        "meatFeed": {},
        "tmoComparison": [],
        "storageBacktest": {},
        "regionalArbitrage": {},
        "agriBist": {},
        "realReturns": [],
    }

    # 1. TÜRİB Snapshot & Endeksler
    try:
        turib_src = TuribSource()
        snap = turib_src.snapshot()

        # Endeksler (TRBHUB, TRBBGD, TRBMSR, TRBARP)
        for idx in snap.indices:
            data["indices"].append({
                "code": idx.code,
                "name": idx.name,
                "value": idx.price,
                "valueStr": f"{idx.price:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
                "change": round(idx.price * (idx.change_pct / 100.0), 2),
                "changePct": idx.change_pct,
                "changeStr": f"{'+' if idx.change_pct >= 0 else ''}{idx.change_pct:.2f}%".replace(".", ","),
                "high": idx.high,
                "low": idx.low,
                "volumeTon": idx.volume,
                "volumeStr": f"{idx.volume:,.1f} Ton".replace(",", "X").replace(".", ",").replace("X", "."),
            })

        # Spot Ürünler
        for prod in snap.products:
            data["spotCommodities"].append({
                "name": prod.product,
                "code": prod.product,
                "avgPrice": prod.avg_price_tl_kg,
                "avgPriceStr": f"{prod.avg_price_tl_kg:.2f} ₺/kg".replace(".", ","),
                "minPrice": prod.low,
                "maxPrice": prod.high,
                "changePct": prod.change_pct,
                "changeStr": f"{'+' if prod.change_pct >= 0 else ''}{prod.change_pct:.2f}%".replace(".", ","),
                "volumeTon": round(prod.volume_kg / 1000.0, 1),
                "volumeStr": f"{round(prod.volume_kg / 1000.0, 1):,.1f} Ton".replace(",", "X").replace(".", ",").replace("X", "."),
                "volumeTl": prod.volume_tl,
                "volumeTlStr": f"{prod.volume_tl:,.0f} ₺".replace(",", "X").replace(".", ",").replace("X", "."),
            })

        # Bülten Özeti
        data["bulletinSummary"] = {
            "totalVolumeTon": snap.total_volume_tons,
            "totalVolumeTonStr": f"{snap.total_volume_tons:,.1f} Ton".replace(",", "X").replace(".", ",").replace("X", "."),
            "totalValueTl": snap.total_volume_tl,
            "totalValueTlStr": f"{snap.total_volume_tl:,.0f} ₺".replace(",", "X").replace(".", ",").replace("X", "."),
            "hububatIndex": snap.hububat_index.price if snap.hububat_index else None,
            "summaryText": snap.summary_text,
        }
    except Exception as exc:
        log.warning("TuribData: TÜRİB snapshot derlenirken hata: %s", exc)

    # 2. Et-Yem Paritesi & Et TÜFE
    try:
        meat_analyzer = MeatFeedIndexAnalyzer()
        meat_report = meat_analyzer.analyze()
        data["meatFeed"] = {
            "cpiDate": meat_report.tarih,
            "meatCpi": meat_report.et_tufe_endeks,
            "headlineCpi": meat_report.manset_tufe_endeks,
            "meatCpiAnnualPct": meat_report.et_enflasyonu_yillik_pct,
            "headlineCpiAnnualPct": meat_report.manset_enflasyon_yillik_pct,
            "meatInflationSpread": meat_report.et_enflasyon_primi_pct,
            "macroCommentary": meat_report.makro_degerlendirme,
            "bistSectorImpact": meat_report.bist_etkisi_ozeti,
            "parities": [
                {
                    "title": p.kategori,
                    "meatType": "Karkas Et",
                    "feedType": "Karma Rasyon",
                    "meatPrice": p.karkas_fiyati_tl_kg,
                    "feedPrice": p.yem_fiyati_tl_kg,
                    "ratio": p.parite_orani,
                    "threshold": p.esik_basabasi,
                    "isProfitable": p.parite_orani >= p.esik_basabasi,
                    "status": p.kar_marji_durumu,
                    "interpretation": p.sinyal_yorumu,
                }
                for p in meat_report.pariteler
            ],
        }
    except Exception as exc:
        log.warning("TuribData: Et-yem verisi derlenirken hata: %s", exc)

    # 3. TMO Müdahale & Alım Fiyat Kıyaslama
    try:
        tmo_src = TmoSource()
        commodities_live = [
            ("BUĞDAY EKMEKLİK", None),
            ("BUĞDAY MAKARNALIK", None),
            ("MISIR", None),
            ("ARPA", None),
        ]
        for comm, live_price in commodities_live:
            try:
                rep = tmo_src.compare(urun_grubu=comm, manuel_fiyat=live_price)
                data["tmoComparison"].append({
                    "commodity": rep.urun_grubu,
                    "tmoProductName": rep.tmo_urun_adi,
                    "year": rep.tmo_yil,
                    "tmoPurchasePrice": rep.tmo_alim_fiyati,
                    "farmerPremium": rep.bakanlik_destegi,
                    "totalFarmerIncome": rep.toplam_uretici_fiyati,
                    "tmoSalesPrice": rep.tmo_satis_fiyati,
                    "turibFreePrice": rep.serbest_piyasa_fiyati,
                    "spreadTl": rep.alim_farki_tl,
                    "spreadPct": rep.alim_prim_yuzde,
                    "totalSpreadPct": rep.toplam_prim_yuzde,
                    "status": rep.piyasa_durumu,
                    "commentary": rep.piyasa_yorumu,
                })
            except Exception as e_c:
                log.warning("TuribData: TMO kıyaslama %s hatası: %s", comm, e_c)
    except Exception as exc:
        log.warning("TuribData: TMO kıyaslama derlenirken hata: %s", exc)

    # 4. LİDAŞ Depolama Backtest
    try:
        storage_tester = StorageStrategyBacktester()
        bt_rep = storage_tester.run_backtest()
        seasons = []
        for s in bt_rep.sezon_sonuclari:
            strats = []
            for st in s.stratejiler:
                strats.append({
                    "strategyName": st.strateji_adi,
                    "termMonths": st.vade_ay,
                    "saleMonth": st.satis_ayi,
                    "salePrice": st.satis_fiyati,
                    "grossSpread": st.brut_fark_tl_kg,
                    "storageCost": st.depolama_maliyeti,
                    "interestCost": st.finansman_maliyeti,
                    "shrinkageCost": st.fire_maliyeti,
                    "totalCost": st.toplam_maliyet_tl_kg,
                    "netProfitTl": st.net_kar_zarar_tl_kg,
                    "netReturnPct": st.net_getiri_pct,
                    "beatSpot": st.spotu_gecti_mi,
                })
            seasons.append({
                "seasonYear": s.sezon_yili,
                "harvestMonth": s.hasat_ayi,
                "harvestSpotPrice": s.hasat_spot_fiyati,
                "winningStrategy": s.kazanan_strateji,
                "strategies": strats,
            })
        data["storageBacktest"] = {
            "productGroup": bt_rep.urun_grubu,
            "testedSeasonsCount": bt_rep.test_edilen_sezon_sayisi,
            "annualInterestPct": bt_rep.yillik_faiz_pct,
            "winRate3mPct": bt_rep.strateji_3ay_kazanma_orani_pct,
            "winRate6mPct": bt_rep.strateji_6ay_kazanma_orani_pct,
            "winRate9mPct": bt_rep.strateji_9ay_kazanma_orani_pct,
            "avgNetReturn6mPct": bt_rep.ortalama_6ay_net_getiri_pct,
            "bestStrategy": bt_rep.en_basarili_strateji,
            "strategicAdvice": bt_rep.stratejik_tavsiye,
            "seasons": seasons,
        }
    except Exception as exc:
        log.warning("TuribData: Depolama backtest derlenirken hata: %s", exc)

    # 5. Bölgesel LİDAŞ Depo Arbitrajı
    try:
        arb_scanner = RegionalArbitrageScanner()
        arb_rep = arb_scanner.scan(urun="BUĞDAY")
        best_spreads = []
        for sp in arb_rep.en_iyi_firsatlar:
            best_spreads.append({
                "commodity": sp.urun,
                "cheapCity": sp.ucuz_il,
                "cheapLidas": sp.ucuz_lidas,
                "cheapPrice": sp.ucuz_fiyat,
                "expensiveCity": sp.pahali_il,
                "expensiveLidas": sp.pahali_lidas,
                "expensivePrice": sp.pahali_fiyat,
                "grossSpread": sp.brut_makas_tl_kg,
                "freightCost": sp.tahmini_nakliye_tl_kg,
                "netArbitrage": sp.net_arbitraj_tl_kg,
                "netArbitragePct": sp.net_arbitraj_pct,
                "opportunityLevel": sp.firsat_seviyesi,
                "notes": sp.aciklama,
            })
        data["regionalArbitrage"] = {
            "date": arb_rep.tarih,
            "totalScannedTrades": arb_rep.taranan_islem_sayisi,
            "evaluation": arb_rep.genel_degerlendirme,
            "opportunities": best_spreads,
        }
    except Exception as exc:
        log.warning("TuribData: Bölgesel arbitraj derlenirken hata: %s", exc)

    # 6. Agri-BIST Çapraz Piyasa Hisseleri
    try:
        agri_bist = AgriBistAnalyzer()
        ab_rep = agri_bist.analyze()
        companies = []
        for imp in ab_rep.company_impacts:
            companies.append({
                "ticker": imp.ticker,
                "companyName": imp.company_name,
                "stockPrice": imp.stock_price,
                "stockChange": imp.stock_change,
                "commodity": imp.commodity,
                "commodityPrice": imp.commodity_price,
                "commodityChange": imp.commodity_change,
                "marginPressure": imp.margin_pressure,
                "commentary": imp.commentary,
            })
        data["agriBist"] = {
            "date": ab_rep.date,
            "xgidaPrice": ab_rep.xgida_price,
            "xgidaChange": ab_rep.xgida_change,
            "turibHububatIndex": ab_rep.turib_hububat_index,
            "turibHububatChange": ab_rep.turib_hububat_change,
            "macroTakeaway": ab_rep.macro_takeaway,
            "companies": companies,
        }
    except Exception as exc:
        log.warning("TuribData: Agri-BIST analizi derlenirken hata: %s", exc)

    # 7. Reel Getiriler (Enflasyon / Döviz)
    try:
        real_calc = RealReturnsCalculator()
        for comm in ["BUĞDAY EKMEKLİK", "BUĞDAY MAKARNALIK"]:
            try:
                r = real_calc.calculate(urun_grubu=comm)
                data["realReturns"].append({
                    "commodityGroup": r.urun_grubu,
                    "startDate": r.baslangic_tarihi,
                    "endDate": r.bitis_tarihi,
                    "tradingDays": r.islem_gun_sayisi,
                    "startPriceTl": r.ilk_fiyat_tl,
                    "endPriceTl": r.son_fiyat_tl,
                    "nominalReturnPct": r.nominal_tl_getiri_pct,
                    "usdReturnPct": r.usd_getiri_pct,
                    "eurReturnPct": r.eur_getiri_pct,
                    "realInflationReturnPct": r.reel_enflasyon_getiri_pct,
                    "commentary": r.analiz_yorumu,
                })
            except Exception as e_r:
                log.warning("TuribData: Reel getiri %s hatası: %s", comm, e_r)
    except Exception as exc:
        log.warning("TuribData: Reel getiriler derlenirken hata: %s", exc)

    # 8. Petrol & Tanker Navlun Veri Seti
    try:
        from ..sources.tanker_freight import TankerFreightSource
        tanker_src = TankerFreightSource()
        data["petrolTanker"] = tanker_src.fetch_snapshot().to_dict()
    except Exception as exc:
        log.warning("TuribData: Petrol & Tanker verisi derlenirken hata: %s", exc)
        data["petrolTanker"] = {}

    return data


def update_turib_market_data() -> bool:
    """Tüm TÜRİB ve tarımsal emtia verisini derler ve web/public/data/turib-market.json'a kaydeder."""
    try:
        data = generate_turib_market_data()
        TURIB_JSON.parent.mkdir(parents=True, exist_ok=True)
        TURIB_JSON.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        log.info("TÜRİB Piyasa JSON güncellendi: %s (%d bayt)", TURIB_JSON, TURIB_JSON.stat().st_size)
        return True
    except Exception as exc:
        log.error("TÜRİB Piyasa JSON yazılamadı: %s", exc)
        return False
