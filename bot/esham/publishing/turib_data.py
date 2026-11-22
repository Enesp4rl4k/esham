"""TÜRİB ELÜS ve Tarımsal Emtia verilerini web/public/data/turib-market.json'a yazar.

Statik export (Cloudflare Pages) ortamında Next.js API route yerine bot tarafından
her tarama turunda bu modül çağrılır. Üretilen JSON dosyası /tarim-emtia sayfasında
kullanıcılar tarafından dinamik incelenir ve doğrudan ham veri olarak indirilebilir.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from ..config import PROJECT_ROOT, get_logger
from ..freshness import build_section_meta
from ..sources.turib import TuribSource
from ..sources.tmo import TmoSource
from ..sources.real_returns import RealReturnsCalculator
from ..sources.storage_backtest import StorageStrategyBacktester
from ..sources.regional_arbitrage import RegionalArbitrageScanner
from ..sources.agri_bist import AgriBistAnalyzer

log = get_logger(__name__)

TURIB_JSON = PROJECT_ROOT / "web" / "public" / "data" / "turib-market.json"


#: Taşınan (son iyi) değer bundan eski ise yayından çıkarılır: eski veri "güncel değil" notuyla bile sonsuza dek asılı kalmaz.
MAX_CARRY_DAYS = 14

#: Boğaz sayıları haftalık ve ~1 hafta gecikmeli yayımlanır: daha uzun tolerans.
STRAIT_MAX_CARRY_DAYS = 35

TR_TZ = timezone(timedelta(hours=3))


def _today() -> date:
    return datetime.now(TR_TZ).date()


def _too_old(as_of: str | None, max_days: int | None = MAX_CARRY_DAYS) -> bool:
    """as_of (YYYY-MM-DD...) `max_days`ten eskiyse ya da çözülemiyorsa True (max_days None: sınırsız)."""
    if max_days is None:
        return False
    try:
        d = date.fromisoformat(str(as_of)[:10])
    except (TypeError, ValueError):
        return True
    return (_today() - d).days > max_days


def load_previous_market_data(path: Path | None = None) -> dict[str, Any] | None:
    """Daha önce yayınlanmış turib-market.json'u okur; yoksa/bozuksa None."""
    p = path or TURIB_JSON
    try:
        prev = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return prev if isinstance(prev, dict) else None


def _carry_over(
    skipped: list[str],
    previous: dict[str, Any] | None,
    section: str,
    key: str,
    date_keys: tuple[str, ...],
    max_age_days: int | None = MAX_CARRY_DAYS,
) -> list[dict[str, Any]]:
    """Canlı veri alınamayan girdiler için son yayınlanmış değeri özgün tarihiyle taşır.

    Taşınan girdiye `asOf` (özgün veri tarihi) ve `stale: true` yazılır; önceki değer
    yoksa ya da tarihi bilinmiyorsa girdi atlanır (tarihsiz eski veri taze gibi sunulmaz).
    """
    carried: list[dict[str, Any]] = []
    if not previous:
        return carried
    old_entries = previous.get(section)
    if not isinstance(old_entries, list):
        return carried
    for name in skipped:
        old = next((e for e in old_entries if isinstance(e, dict) and e.get(key) == name), None)
        if old is None:
            continue
        as_of = old.get("asOf") or next((old[k] for k in date_keys if old.get(k)), None) or previous.get("date")
        if not as_of or _too_old(as_of, max_age_days):
            continue
        entry = dict(old)
        entry["asOf"] = as_of
        entry["stale"] = True
        carried.append(entry)
        log.warning("TuribData: %s %s canlı veri yok; son yayınlanan değer (%s) taşındı.", section, name, as_of)
    return carried


_SECTION_DATE_KEYS = ("asOf", "date", "cpiDate", "endDate")


def _section_as_of(entry: Any, previous: dict[str, Any]) -> str | None:
    """Bölüm/girdi için özgün veri tarihi; bilinmiyorsa None (tarihsiz eski veri taşınmaz)."""
    if isinstance(entry, dict):
        for k in _SECTION_DATE_KEYS:
            if entry.get(k):
                return str(entry[k])
        if entry.get("updatedAt"):
            return str(entry["updatedAt"])[:10]
    return previous.get("date") or None


def _carry_entries(old: list[Any], previous: dict[str, Any]) -> list[dict[str, Any]]:
    carried: list[dict[str, Any]] = []
    for e in old:
        as_of = _section_as_of(e, previous) if isinstance(e, dict) else None
        if as_of and not _too_old(as_of):
            carried.append({**e, "asOf": as_of, "stale": True})
    return carried


def _carry_section(data: dict[str, Any], previous: dict[str, Any] | None, section: str) -> None:
    """Bölüm bu turda boş çıktıysa son iyi bölümü özgün tarihiyle (`asOf`) ve `stale: true` ile taşır.

    Önceki yayında da bölüm yoksa ya da tarihi bilinmiyorsa bölüm boş kalır (tarihsiz veri taze gibi sunulmaz).
    """
    old = previous.get(section) if previous else None
    if data.get(section) or not old or previous is None:
        return
    if isinstance(old, list):
        carried = _carry_entries(old, previous)
        data[section].extend(carried)
        if carried:
            log.warning("TuribData: bölüm canlı veri yok; son yayın girdileri taşındı (adet=%d).", len(carried))
    elif isinstance(old, dict):
        as_of = _section_as_of(old, previous)
        if as_of and not _too_old(as_of):
            data[section] = {}
            data[section].update({**old, "asOf": as_of, "stale": True})
            log.warning("TuribData: bölüm canlı veri yok; son yayın bölümü taşındı.")


def _collect_straits(previous: dict[str, Any] | None) -> list[dict[str, Any]]:
    """PortWatch boğaz sayıları; alınamayan boğaz için son iyi girdi özgün `asOf` ile ve `stale: true` ile taşınır."""
    fresh: list[dict[str, Any]] = []
    try:
        from ..sources.portwatch import STRAITS, PortWatchSource

        fresh = [o.to_dict() for o in (PortWatchSource().fetch_straits() or [])]
        got = {e["strait"] for e in fresh}
        missing = [key for key, _name in STRAITS.values() if key not in got]
    except Exception as exc:  # noqa: BLE001 - kaynak hatası yayını durdurmamalı
        log.warning("TuribData: PortWatch boğaz verisi derlenirken hata: %s", exc)
        missing = ["Bosporus"]
    old_pt = (previous or {}).get("petrolTanker")
    old_straits = old_pt.get("straits") if isinstance(old_pt, dict) else None
    shim = {"straits": old_straits, "date": (previous or {}).get("date")}
    return fresh + _carry_over(missing, shim, "straits", "strait", ("weekEnd",), max_age_days=STRAIT_MAX_CARRY_DAYS)


def generate_turib_market_data(previous: dict[str, Any] | None = None) -> dict[str, Any]:
    """Tüm tarım, emtia, TÜRİB ve emtia veri setini yapılandırılmış sözlük olarak derler.

    `previous`: önceki yayın; atlanan girdiler (örn. TMO MISIR/ARPA) buradan taşınır.
    """
    now = datetime.now(TR_TZ)
    now_str = now.isoformat(timespec="seconds")
    date_str = now.strftime("%Y-%m-%d")

    data: dict[str, Any] = {
        "updatedAt": now_str,
        "date": date_str,
        "indices": [],
        "spotCommodities": [],
        "bulletinSummary": {},
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
                "asOf": idx.date,  # TÜRİB'in kendi işlem günü (hafta sonu çalışmada bot tarihinden farklıdır)
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
                "asOf": prod.date,
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
            "asOf": min((e.date for e in [*snap.indices, *snap.products] if e.date), default=None),
            "hububatIndex": snap.hububat_index.price if snap.hububat_index else None,
            "summaryText": snap.summary_text,
        }
    except Exception as exc:
        log.warning("TuribData: TÜRİB snapshot derlenirken hata: %s", exc)

    # 2. TMO Müdahale & Alım Fiyat Kıyaslama
    try:
        tmo_src = TmoSource()
        commodities_live = [
            ("BUĞDAY EKMEKLİK", None),
            ("BUĞDAY MAKARNALIK", None),
            ("MISIR", None),
            ("ARPA", None),
        ]
        tmo_skipped: list[str] = []
        for comm, live_price in commodities_live:
            try:
                rep = tmo_src.compare(urun_grubu=comm, manuel_fiyat=live_price)
                data["tmoComparison"].append({
                    "commodity": rep.urun_grubu,
                    "asOf": rep.tarih,
                    "tmoProductName": rep.tmo_urun_adi,
                    "year": rep.tmo_yil,
                    "tmoSeason": str(rep.tmo_yil),
                    "tmoSource": rep.tmo_kaynak_url,
                    "tmoAsOf": rep.tmo_duyuru_tarihi,
                    "tmoVerified": rep.tmo_dogrulandi,
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
                tmo_skipped.append(comm)
        # Eski yayından taşınan satır yalnızca birincil kaynağa bağlı (tmoVerified) ise yayınlanır;
        # kaynaksız/eski şemadaki elle girilmiş TMO değerleri asla geri taşınmaz.
        data["tmoComparison"].extend(
            e for e in _carry_over(tmo_skipped, previous, "tmoComparison", "commodity", (), max_age_days=None)
            if e.get("tmoVerified") is True and e.get("tmoSource")
        )
    except Exception as exc:
        log.warning("TuribData: TMO kıyaslama derlenirken hata: %s", exc)

    # 3. LİDAŞ Depolama Backtest
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
            "asOf": date_str,  # hesaplama tarihi (TÜRİB tarihsel serisinin çekildiği gün)
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

    # 4. Bölgesel LİDAŞ Depo Arbitrajı
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

    # 5. Agri-BIST Çapraz Piyasa Hisseleri
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

    # 6. Döviz cinsinden getiri (TCMB kurları; son 12 ay). Kur bülteni yoksa girdi atlanır, son iyi değer taşınır.
    try:
        real_calc = RealReturnsCalculator()
        real_skipped: list[str] = []
        window_start = (now - timedelta(days=365)).strftime("%Y-%m-%d")
        for comm in ["BUĞDAY EKMEKLİK", "BUĞDAY MAKARNALIK"]:
            try:
                r = real_calc.calculate(urun_grubu=comm, baslangic=window_start)
                data["realReturns"].append({
                    "commodityGroup": r.urun_grubu,
                    "startDate": r.baslangic_tarihi,
                    "endDate": r.bitis_tarihi,
                    "asOf": r.bitis_tarihi,
                    "tradingDays": r.islem_gun_sayisi,
                    "startPriceTl": r.ilk_fiyat_tl,
                    "endPriceTl": r.son_fiyat_tl,
                    "nominalReturnPct": r.nominal_tl_getiri_pct,
                    "usdReturnPct": r.usd_getiri_pct,
                    "eurReturnPct": r.eur_getiri_pct,
                    "fxDateStart": r.kur_tarihi_baslangic,
                    "fxDateEnd": r.kur_tarihi_bitis,
                    "usdTryStart": r.usd_try_baslangic,
                    "usdTryEnd": r.usd_try_bitis,
                    "eurTryStart": r.eur_try_baslangic,
                    "eurTryEnd": r.eur_try_bitis,
                    "source": r.kaynak,
                    "sourceUrl": r.kaynak_url,
                    "fetchedAt": r.cekilis_zamani,
                    "commentary": r.analiz_yorumu,
                })
            except Exception as e_r:
                log.warning("TuribData: döviz cinsinden getiri %s hatası: %s", comm, e_r)
                real_skipped.append(comm)
        data["realReturns"].extend(
            _carry_over(real_skipped, previous, "realReturns", "commodityGroup", ("endDate",))
        )
    except Exception as exc:
        log.warning("TuribData: döviz cinsinden getiriler derlenirken hata: %s", exc)

    # 8. Petrol & Tanker Navlun Veri Seti
    try:
        from ..sources.tanker_freight import TankerFreightSource
        tanker_src = TankerFreightSource()
        tanker_snap = tanker_src.fetch_snapshot()
        data["petrolTanker"] = tanker_snap.to_dict() if tanker_snap else {}
    except Exception as exc:
        log.warning("TuribData: Petrol & Tanker verisi derlenirken hata: %s", exc)
        data["petrolTanker"] = {}

    # 8b. Boğaz geçiş sayıları (IMF PortWatch; gözlem — yalnızca tamamlanmış haftalar)
    # Brent bölümü önce (son iyi değer taşıma), sonra boğaz girdileri kendi asOf/stale kuralıyla.
    _carry_section(data, previous, "petrolTanker")
    straits = _collect_straits(previous)
    pt = {k: v for k, v in data.get("petrolTanker", {}).items() if k != "straits"}
    if straits:
        pt["straits"] = straits
    data["petrolTanker"] = pt

    # Bölüm düzeyinde başarısızlık: boş yayın yerine son iyi bölümü özgün tarihiyle taşı.
    for section in (
        "indices", "spotCommodities", "bulletinSummary", "storageBacktest",
        "regionalArbitrage", "agriBist", "petrolTanker",
    ):
        _carry_section(data, previous, section)

    data["sections"] = build_section_meta(data, now_str)
    return data


def update_turib_market_data() -> bool:
    """Tüm TÜRİB ve tarımsal emtia verisini derler ve web/public/data/turib-market.json'a kaydeder."""
    try:
        data = generate_turib_market_data(previous=load_previous_market_data())
        TURIB_JSON.parent.mkdir(parents=True, exist_ok=True)
        TURIB_JSON.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        log.info("TÜRİB Piyasa JSON güncellendi: %s (%d bayt)", TURIB_JSON, TURIB_JSON.stat().st_size)
        return True
    except Exception as exc:
        log.error("TÜRİB Piyasa JSON yazılamadı: %s", exc)
        return False
