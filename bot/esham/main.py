"""Esham CLI.

Kullanım:
    py -m esham.main morning-report        # sabah bültenini üret ve yayınla
    py -m esham.main morning-report --no-social
    py -m esham.main news-stream --interval 300
    py -m esham.main ipo-pdf               # örnek halka arz PDF/HTML raporu
"""
from __future__ import annotations

import argparse
import sys

from .analysis import analyze_company_report, analyze_ipo_document
from .config import configure_logging, get_logger
from .jobs.publish_fear_greed import run_fear_greed_report
from .jobs.publish_heatmap import run_heatmap
from .news_stream import NewsStream
from .pipeline import (
    run_closing_report,
    run_global_report,
    run_gundem_report,
    run_morning_report,
    run_news_report,
    run_opening_report,
    run_peer_report,
    run_sector_report,
    run_viop_report,
    run_weekly_summary,
)
from .scheduler import build_default_scheduler
from .publishing.ipo_pdf import IpoPdfGenerator
from .risk.margin import MarginMonitor, default_parameters, load_parameters_file, load_positions_file
from .sources.peer import available_groups
from .sources.viop import ViopSource, assess_margin_stress
from .state import get_state

log = get_logger(__name__)


def _cmd_morning_report(args: argparse.Namespace) -> None:
    run_morning_report(publish_social=not args.no_social)


def _cmd_fear_greed(args: argparse.Namespace) -> None:
    from .jobs.publish_fear_greed import run_fear_greed_report
    run_fear_greed_report()


def _cmd_heatmap(args: argparse.Namespace) -> None:
    from .jobs.publish_heatmap import run_heatmap
    run_heatmap()


def _cmd_news_stream(args: argparse.Namespace) -> None:
    stream = NewsStream(
        scan_interval=args.scan_interval,
        publish_interval=args.publish_interval,
    )
    if args.once:
        stream.check_once(max_publish=args.max_publish)
    else:
        stream.run()


def _cmd_analyze_ipo(args: argparse.Namespace) -> None:
    analyze_ipo_document(
        args.source,
        company=args.company,
        ticker=args.ticker,
        publish=not args.no_publish,
        make_pdf=not args.no_pdf,
    )


def _cmd_analyze_company(args: argparse.Namespace) -> None:
    analyze_company_report(
        args.source,
        company=args.company,
        period=args.period,
        publish=not args.no_publish,
    )


def _cmd_turib(args: argparse.Namespace) -> None:
    from .sources.turib import TuribSource
    src = TuribSource()
    snap = src.snapshot()
    print("\n=== TÜRİB ELÜS Tarımsal Emtia Piyasası ===")
    print(snap.summary_text)
    if snap.indices:
        print("\n--- TÜRİB Endeksleri ---")
        for idx in snap.indices:
            sign = "+" if idx.change_pct >= 0 else ""
            print(f"  {idx.name} ({idx.code}): {idx.price} ({sign}{idx.change_pct}%) [Hacim: {idx.volume:,.0f}]")
    if snap.products:
        print("\n--- Emtia Fiyatları (TL/kg) ---")
        for p in snap.products:
            sign = "+" if p.change_pct >= 0 else ""
            print(f"  {p.product}: Ort {p.avg_price_tl_kg:.2f} TL/kg (Son: {p.price_tl_kg:.2f}, {sign}{p.change_pct}%) | Hacim: {p.volume_kg/1000.0:,.1f} Ton")


def _cmd_agri_bist(args: argparse.Namespace) -> None:
    from .sources.agri_bist import AgriBistAnalyzer
    analyzer = AgriBistAnalyzer()
    rep = analyzer.analyze()
    print("\n=== BIST & TÜRİB Çapraz Piyasa Analizi (Agri-BIST) ===")
    print(f"  BIST Gıda Endeksi (XGIDA): {rep.xgida_price} ({rep.xgida_change})")
    print(f"  TÜRİB Hububat Endeksi (TRBHUB): {rep.turib_hububat_index} ({rep.turib_hububat_change})")
    print("\n--- Şirket Bazlı Girdi & Kârlılık Duyarlılığı ---")
    for c in rep.company_impacts:
        print(f"  [{c.ticker}] {c.company_name}: Hisse {c.stock_price} ({c.stock_change})")
        print(f"    -> Girdi: {c.commodity} ({c.commodity_price} TL/kg, %{c.commodity_change}) | Marj: {c.margin_pressure}")
        print(f"    -> Not: {c.commentary}")
    print(f"\nMakro Değerlendirme: {rep.macro_takeaway}")


def _cmd_tmo(args: argparse.Namespace) -> None:
    from .sources.tmo import TmoSource
    tmo = TmoSource()
    if args.list:
        kayitlar = tmo.list_records(yil=args.year, kategori=args.category)
        print(f"\n=== TMO Müdahale Fiyatları Arşivi ({len(kayitlar)} Kayıt) ===")
        for k in kayitlar:
            satis = f"{k.satis_fiyati_tl_kg:.2f}" if k.satis_fiyati_tl_kg else "—"
            print(f"  [{k.yil}] {k.urun_adi} ({k.kategori}): Alım={k.alim_fiyati_tl_kg:.2f} TL/kg | Prim={k.bakanlik_destegi_tl_kg:.2f} TL | Toplam={k.toplam_uretici_fiyati_tl_kg:.2f} TL | Satış={satis} TL")
    else:
        rep = tmo.compare(args.product, referans_yili=args.year)
        print(f"\n=== TMO vs TÜRİB Fiyat Karşılaştırması ({rep.tmo_yil}) ===")
        print(f"  Ürün: {rep.urun_grubu} (TMO: {rep.tmo_urun_adi})")
        print(f"  TÜRİB Serbest Piyasa: {rep.serbest_piyasa_fiyati:.2f} TL/kg")
        print(f"  TMO Alım Tabanı: {rep.tmo_alim_fiyati:.2f} TL/kg (Bakanlık Primi: {rep.bakanlik_destegi:.2f} TL/kg)")
        print(f"  TMO Alıma Göre Prim: %{rep.alim_prim_yuzde:+.1f} ({rep.alim_farki_tl:+.2f} TL/kg)")
        print(f"  Piyasa Durumu: {rep.piyasa_durumu}")
        print(f"  Yorum: {rep.piyasa_yorumu}")


def _cmd_real_return(args: argparse.Namespace) -> None:
    from .sources.real_returns import RealReturnsCalculator
    calc = RealReturnsCalculator()
    rep = calc.calculate(args.product, baslangic=args.start, bitis=args.end)
    print(f"\n=== TÜRİB Reel Getiri Analizi (TÜFE & Döviz) ===")
    print(f"  Ürün: {rep.urun_grubu} | Dönem: {rep.baslangic_tarihi} - {rep.bitis_tarihi} ({rep.islem_gun_sayisi} işlem günü)")
    print(f"  TL Fiyatı: {rep.ilk_fiyat_tl:.2f} TL -> {rep.son_fiyat_tl:.2f} TL (Nominal Getiri: %{rep.nominal_tl_getiri_pct:+.1f})")
    print(f"  USD Fiyatı: ${rep.ilk_fiyat_usd:.3f} -> ${rep.son_fiyat_usd:.3f} (Dolar Getirisi: %{rep.usd_getiri_pct:+.1f})")
    print(f"  EUR Fiyatı: €{rep.ilk_fiyat_eur:.3f} -> €{rep.son_fiyat_eur:.3f} (Euro Getirisi: %{rep.eur_getiri_pct:+.1f})")
    print(f"  TÜFE Enflasyonundan Arındırılmış Reel Getiri: %{rep.reel_enflasyon_getiri_pct:+.1f}")
    print(f"  Değerlendirme: {rep.analiz_yorumu}")


def _cmd_storage_backtest(args: argparse.Namespace) -> None:
    from .sources.storage_backtest import StorageStrategyBacktester
    bt = StorageStrategyBacktester()
    rep = bt.run_backtest(args.product, yillik_faiz_pct=args.interest)
    print(f"\n=== Tarımsal Emtia Depolama Stratejisi Backtest'i ===")
    print(f"  Ürün: {rep.urun_grubu} ({rep.test_edilen_sezon_sayisi} Sezon, Yıllık Finansman Faizi: %{rep.yillik_faiz_pct:.0f})")
    print(f"  3 Ay Depolama Başarı Oranı: %{rep.strateji_3ay_kazanma_orani_pct:.1f}")
    print(f"  6 Ay Depolama Başarı Oranı: %{rep.strateji_6ay_kazanma_orani_pct:.1f} (Ortalama Net Getiri: %{rep.ortalama_6ay_net_getiri_pct:+.1f})")
    print(f"  9 Ay Depolama Başarı Oranı: %{rep.strateji_9ay_kazanma_orani_pct:.1f}")
    print(f"  Tarihsel En Başarılı Strateji: {rep.en_basarili_strateji}")
    print(f"  Stratejik Tavsiye: {rep.stratejik_tavsiye}")


def _cmd_arbitrage(args: argparse.Namespace) -> None:
    from .sources.regional_arbitrage import RegionalArbitrageScanner
    scanner = RegionalArbitrageScanner()
    rep = scanner.scan(urun=args.product, nakliye_maliyeti_tl_kg=args.freight)
    print(f"\n=== TÜRİB Lisanslı Depolar Bölgesel Arbitraj Taraması ===")
    print(f"  Tarih: {rep.tarih} | Ürün: {rep.urun_filtresi} | Taranan İşlem: {rep.taranan_islem_sayisi}")
    print(f"  Genel Durum: {rep.genel_degerlendirme}")
    if rep.en_iyi_firsatlar:
        print("\n--- Tespit Edilen Arbitraj Fırsatları ---")
        for f in rep.en_iyi_firsatlar:
            print(f"  [{f.firsat_seviyesi}] {f.ucuz_il} ({f.ucuz_fiyat:.2f} TL) -> {f.pahali_il} ({f.pahali_fiyat:.2f} TL)")
            print(f"    -> Brüt Makas: {f.brut_makas_tl_kg:.2f} TL | Nakliye: {f.tahmini_nakliye_tl_kg:.2f} TL | Net Kâr: {f.net_arbitraj_tl_kg:+.2f} TL/kg (%{f.net_arbitraj_pct:+.1f})")


def _cmd_meat_index(args: argparse.Namespace) -> None:
    from .sources.meat_feed_index import MeatFeedIndexAnalyzer
    analyzer = MeatFeedIndexAnalyzer()
    rep = analyzer.analyze()
    print("\n=== Et-Yem Paritesi & Et TÜFE Enflasyon Raporu ===")
    print(f"  Tarih: {rep.tarih}")
    print(f"  Et TÜFE Endeksi: {rep.et_tufe_endeks} (Yıllık: %{rep.et_enflasyonu_yillik_pct:+.1f})")
    print(f"  Manşet TÜFE: {rep.manset_tufe_endeks} (Yıllık: %{rep.manset_enflasyon_yillik_pct:+.1f})")
    print(f"  Et Enflasyon Primi: {rep.et_enflasyon_primi_pct:+.1f} puan")
    print("\n--- Karkas Et / Yem Pariteleri ---")
    for p in rep.pariteler:
        print(f"  [{p.kategori}]: Karkas={p.karkas_fiyati_tl_kg:.2f} TL/kg | Yem={p.yem_fiyati_tl_kg:.2f} TL/kg -> Parite={p.parite_orani:.1f} ({p.kar_marji_durumu})")
        print(f"    -> {p.sinyal_yorumu}")
    print(f"\nBIST Sektör Yansıması: {rep.bist_etkisi_ozeti}")
    print(f"Makro Değerlendirme: {rep.makro_degerlendirme}")


def _cmd_mcp(args: argparse.Namespace) -> None:
    from .mcp.server import run_server
    print("Esham BIST + TÜRİB MCP Sunucusu başlatılıyor (stdio)...")
    run_server()


def _cmd_viop(args: argparse.Namespace) -> None:
    src = ViopSource()
    quote = src.market_quote()
    print("\n=== VİOP Piyasa ===")
    if quote is None:
        print("  (kotasyon alınamadı)")
    else:
        print(f"  Endeks {quote.index_symbol}: {quote.index_price}  {quote.index_change}")
    if quote and quote.has_futures:
        print(
            f"  Vadeli {quote.futures_symbol}: {quote.futures_price}  "
            f"{quote.futures_change or '—'}  hacim {quote.futures_volume or '—'}"
        )

    snap = src.margin_snapshot()
    prior = args.prior_pct if args.prior_pct is not None else get_state().get_margin_prev_pct()
    stress = assess_margin_stress(snap.margin_call_to_required_pct, prior)
    print("\n=== VİOP Marketwide Teminat (Takasbank) ===")
    print(f"  Teminatlı hesap: {snap.margined_account_count:,}")
    print(f"  Margin-call toplam: {snap.margin_call_pretty()}")
    print(f"  Gereken teminat: {snap.required_pretty()}")
    print(f"  Margin-call/Gereken: %{snap.margin_call_to_required_pct:.3f}")
    print(f"  Stres: [{stress.level}] {stress.note}")
    if snap.is_sample:
        print("  (örnek veri — Takasbank URL tanımlı değil)")

    if args.positions:
        account, cash, positions = load_positions_file(args.positions)
        params = load_parameters_file(args.params) if args.params else default_parameters()
        report = MarginMonitor(params).evaluate(positions, cash, account=account)
        print("\n=== Hesap Margin Monitor ===")
        print("  " + report.summary_line())
        print(
            f"  Gerçekleşmemiş K/Z: {report.unrealized_pnl:,.0f} TL | "
            f"Serbest teminat: {report.free_margin:,.0f} TL"
        )
        for alert in report.alerts:
            print(f"  {alert}")

    if args.publish:
        slug = run_viop_report(
            prior_pct=prior, publish=True, publish_social=not args.no_social
        )
        print(f"\n  Web raporu yayınlandı: /rapor/{slug}")


def _cmd_run(args: argparse.Namespace) -> None:
    build_default_scheduler(
        scan_interval=args.scan_interval,
        publish_interval=args.publish_interval,
        margin_interval=args.margin_interval,
    ).run()


def _cmd_opening(_: argparse.Namespace) -> None:
    run_opening_report(publish_social=True)


def _cmd_closing(_: argparse.Namespace) -> None:
    run_closing_report()


def _cmd_gundem(args: argparse.Namespace) -> None:
    slug = run_gundem_report(
        headline=args.headline,
        body=args.body,
        summary=args.summary or args.headline,
        tags=args.tags or [],
        publish_social=not args.no_social,
    )
    if slug:
        print(f"Gündem raporu yayınlandı: /rapor/{slug}")


def _cmd_sector(_: argparse.Namespace) -> None:
    run_sector_report()


def _cmd_peer(args: argparse.Namespace) -> None:
    if args.list_sectors:
        print("Kullanılabilir sektörler:")
        for key in available_groups():
            print(f"  - {key}")
        return
    slug = run_peer_report(args.sector, publish_social=not args.no_social)
    if slug:
        print(f"Peer kıyas raporu yayınlandı: /rapor/{slug}")


def _cmd_global(_: argparse.Namespace) -> None:
    run_global_report()


def _cmd_weekly_summary(args: argparse.Namespace) -> None:
    slug = run_weekly_summary(publish_social=not args.no_social)
    if slug:
        print(f"Haftalık özet yayınlandı: /rapor/{slug}")


def _cmd_newsletter(args: argparse.Namespace) -> None:
    from .newsletter import run_newsletter

    sent = run_newsletter(limit=args.limit, test_to=args.test_to, dry_run=args.dry_run)
    if sent:
        print(f"Bülten gönderildi: {sent} alıcı")
    else:
        print(
            "Bülten gönderilmedi (abone yok / rapor yok / SMTP yapılandırılmamış / dry-run)."
        )


def _cmd_evals(_: argparse.Namespace) -> None:
    from .evals.harness import print_report
    from .evals.suites import all_suites

    ok = print_report(all_suites())
    sys.exit(0 if ok else 1)


def _cmd_publish_turib(_: argparse.Namespace) -> None:
    from .publishing.turib_data import update_turib_market_data
    ok = update_turib_market_data()
    if ok:
        print("TÜRİB & Tarımsal Emtia verileri başarıyla web/public/data/turib-market.json dosyasına yazıldı.")
    else:
        print("Hata: TÜRİB verisi yazılamadı.")
        sys.exit(1)


def _cmd_stocks(args: argparse.Namespace) -> None:
    from .jobs.publish_stocks import run_stocks

    n = run_stocks(tickers=args.tickers, workers=args.workers, with_prices=not args.no_prices)
    print(f"{n} hisse için veri yazıldı.")
    if n == 0:
        sys.exit(1)


def _cmd_funds(args: argparse.Namespace) -> None:
    from .jobs.publish_funds import run_funds

    n = run_funds(limit=args.limit, codes=args.codes, min_interval=args.interval)
    print(f"{n} fon için veri yazıldı.")
    if n == 0:
        sys.exit(1)


def _cmd_kap_financials(args: argparse.Namespace) -> None:
    from .jobs.publish_kap import run_kap

    n = run_kap(tickers=args.tickers, months=args.months, workers=args.workers)
    print(f"{n} hisse için KAP finansalları yazıldı.")
    if n == 0:
        sys.exit(1)


def _cmd_nav(args: argparse.Namespace) -> None:
    from .jobs.publish_nav import run_nav

    n = run_nav(tickers=args.tickers)
    print(f"{n} şirket için KAP iştirak payları yazıldı.")
    if n == 0:
        sys.exit(1)


def _cmd_health(args: argparse.Namespace) -> None:
    from .jobs.health import report, run_health

    sys.exit(report(run_health(args.site, offline=args.offline)))


def _cmd_ipo_pdf(_: argparse.Namespace) -> None:
    generator = IpoPdfGenerator()
    generator.create(
        {
            "company_name": "TechYazılım Bilişim A.Ş.",
            "ticker": "TCHYZ",
            "price": "45,50",
            "discount": "22,5",
            "funds_usage": "Kapasite artırımı (%50), Ar-Ge (%30), İşletme sermayesi (%20)",
            "commitments": "1 yıl bedelli/bedelsiz sermaye artırımı yok. 1 yıl ortak satışı yok.",
            "financials": "2025 hasılat: 500 Milyon TL | Net kâr marjı: %18",
        }
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="esham", description="Esham içerik motoru")
    sub = parser.add_subparsers(dest="command", required=True)

    mr = sub.add_parser("morning-report", help="Sabah bültenini üret ve yayınla")
    mr.add_argument("--no-social", action="store_true", help="Sosyal medya paylaşımını atla")
    mr.set_defaults(func=_cmd_morning_report)

    ns = sub.add_parser("news-stream", help="Anlık haber akışını çalıştır")
    ns.add_argument(
        "--scan-interval", type=int, default=None, help="Kaynak tarama aralığı (saniye)"
    )
    ns.add_argument(
        "--publish-interval",
        type=int,
        default=None,
        help="Haberler arası yayın aralığı/drip (saniye)",
    )
    ns.add_argument("--once", action="store_true", help="Tek tur tara ve yayınla")
    ns.add_argument(
        "--max-publish",
        type=int,
        default=5,
        dest="max_publish",
        help="--once ile en fazla kaç haber yayınlanacak (varsayılan: 5, spam/rate-limit önler)",
    )
    ns.set_defaults(func=_cmd_news_stream)

    ai = sub.add_parser("analyze-ipo", help="İzahname/fiyat tespit raporunu analiz et")
    ai.add_argument("source", help="PDF yolu/URL, KAP linki veya ham metin")
    ai.add_argument("--company", required=True, help="Şirket adı")
    ai.add_argument("--ticker", required=True, help="Borsa kodu")
    ai.add_argument("--no-publish", action="store_true", help="Web raporu yayımlama")
    ai.add_argument("--no-pdf", action="store_true", help="PDF üretme")
    ai.set_defaults(func=_cmd_analyze_ipo)

    ac = sub.add_parser("analyze-company", help="Şirket finansal raporunu analiz et")
    ac.add_argument("source", help="PDF yolu/URL, KAP linki veya ham metin")
    ac.add_argument("--company", required=True, help="Şirket adı")
    ac.add_argument("--period", default="", help="Dönem (ör. 2025/Q1)")
    ac.add_argument("--no-publish", action="store_true", help="Web raporu yayımlama")
    ac.set_defaults(func=_cmd_analyze_company)

    vp = sub.add_parser("viop", help="VİOP piyasa + teminat/margin-call durumu")
    vp.add_argument(
        "--positions", help="Hesap pozisyon dosyası (JSON) — margin monitor çalıştırır"
    )
    vp.add_argument("--params", help="Teminat parametre dosyası (JSON); yoksa temsili")
    vp.add_argument(
        "--prior-pct",
        type=float,
        default=None,
        help="Önceki gün margin-call/gereken oranı (stres karşılaştırması için)",
    )
    vp.add_argument("--publish", action="store_true", help="Web'e VİOP raporu yayınla")
    vp.add_argument("--no-social", action="store_true", help="Sosyal medya paylaşımını atla")
    vp.set_defaults(func=_cmd_viop)

    rn = sub.add_parser("run", help="Günlük yayın orkestratörünü başlat (uzun-ömürlü)")
    rn.add_argument("--scan-interval", type=int, default=300, help="Haber tarama aralığı (sn)")
    rn.add_argument("--publish-interval", type=int, default=90, help="Haber yayın aralığı (sn)")
    rn.add_argument("--margin-interval", type=int, default=1800, help="Margin izleme aralığı (sn)")
    rn.set_defaults(func=_cmd_run)

    sub.add_parser("opening", help="BIST açılış notu yayınla").set_defaults(func=_cmd_opening)
    sub.add_parser("closing", help="Kapanış bülteni yayınla").set_defaults(func=_cmd_closing)
    sub.add_parser("sector", help="Haftalık sektör rotasyonu yayınla").set_defaults(func=_cmd_sector)

    pr = sub.add_parser("peer", help="Sektör içi eş/değer kıyası (F/K, PD/DD medyanı) yayınla")
    pr.add_argument(
        "--sector",
        default="bankacilik",
        choices=available_groups(),
        help="Kıyaslama sektörü (varsayılan: bankacilik)",
    )
    pr.add_argument("--list-sectors", action="store_true", help="Sektör listesini bas ve çık")
    pr.add_argument("--no-social", action="store_true", help="Sosyal medya paylaşımını atla")
    pr.set_defaults(func=_cmd_peer)

    fg = sub.add_parser("fear-greed", help="Korku & Açgözlülük endeksi raporu yayınla")
    fg.set_defaults(func=_cmd_fear_greed)
    sub.add_parser("global-report", help="Küresel makro raporu yayınla").set_defaults(func=_cmd_global)
    sub.add_parser("heatmap", help="BIST30 Piyasa Isı Haritası üret ve yayınla").set_defaults(func=_cmd_heatmap)

    tb = sub.add_parser("turib", help="TÜRİB ELÜS tarımsal emtia piyasası özeti")
    tb.set_defaults(func=_cmd_turib)

    ab = sub.add_parser("agri-bist", help="BIST Gıda & TÜRİB ELÜS çapraz kârlılık analizi")
    ab.set_defaults(func=_cmd_agri_bist)

    mc = sub.add_parser("mcp", help="Esham BIST + TÜRİB Unified MCP Sunucusunu çalıştır (stdio)")
    mc.set_defaults(func=_cmd_mcp)

    tm = sub.add_parser("tmo", help="TMO müdahale fiyatları arşivi ve TÜRİB karşılaştırması")
    tm.add_argument("--product", default="BUĞDAY EKMEKLİK", help="Ürün adı (varsayılan: BUĞDAY EKMEKLİK)")
    tm.add_argument("--year", type=int, default=2026, help="Referans yılı (varsayılan: 2026)")
    tm.add_argument("--category", default=None, help="Kategori filtresi (ör. Buğday, Arpa, Mısır)")
    tm.add_argument("--list", action="store_true", help="Tüm TMO arşiv kayıtlarını listele")
    tm.set_defaults(func=_cmd_tmo)

    rr = sub.add_parser("real-return", help="TÜRİB enflasyondan ve dövizden arındırılmış reel getiri")
    rr.add_argument("--product", default="BUĞDAY EKMEKLİK", help="Ürün adı (varsayılan: BUĞDAY EKMEKLİK)")
    rr.add_argument("--start", default="2022-01-01", help="Başlangıç tarihi (YYYY-AA-GG)")
    rr.add_argument("--end", default=None, help="Bitiş tarihi (YYYY-AA-GG)")
    rr.set_defaults(func=_cmd_real_return)

    bt = sub.add_parser("backtest", help="Tarımsal depolama stratejisi simülatörü")
    bt.add_argument("--product", default="BUĞDAY EKMEKLİK", help="Ürün adı (varsayılan: BUĞDAY EKMEKLİK)")
    bt.add_argument("--interest", type=float, default=45.0, help="Yıllık alternatif faiz (yüzde, varsayılan: 45)")
    bt.set_defaults(func=_cmd_storage_backtest)

    ar = sub.add_parser("arbitrage", help="LİDAŞ depoları arası bölgesel arbitraj taraması")
    ar.add_argument("--product", default="BUĞDAY", help="Ürün filtresi (varsayılan: BUĞDAY)")
    ar.add_argument("--freight", type=float, default=0.50, help="Tahmini nakliye maliyeti TL/kg (varsayılan: 0.50)")
    ar.set_defaults(func=_cmd_arbitrage)

    mi = sub.add_parser("meat-index", help="Et-yem paritesi ve Et TÜFE enflasyon analizi")
    mi.set_defaults(func=_cmd_meat_index)

    ws = sub.add_parser("weekly-summary", help="Haftalık piyasa özeti üret ve yayınla")
    ws.add_argument("--no-social", action="store_true", help="Sosyal medya paylaşımını atla")
    ws.set_defaults(func=_cmd_weekly_summary)

    gn = sub.add_parser("gundem", help="Anlık gündem haberi / piyasa yorumu yayınla")
    gn.add_argument("headline", help="Kısa başlık (tweet ve kart için)")
    gn.add_argument("body", help="Markdown formatında rapor gövdesi")
    gn.add_argument("--summary", default="", help="Tek cümlelik özet (opsiyonel; verilmezse başlık kullanılır)")
    gn.add_argument("--tags", nargs="*", default=[], metavar="TAG", help="Etiketler (opsiyonel)")
    gn.add_argument("--no-social", action="store_true", help="Sosyal medya paylaşımını atla")
    gn.set_defaults(func=_cmd_gundem)
    sub.add_parser("evals", help="AI çıktı kalitesi/güvenlik eval'lerini çalıştır").set_defaults(func=_cmd_evals)

    nl = sub.add_parser("newsletter", help="Bülten abonelerine e-posta özeti gönder")
    nl.add_argument("--limit", type=int, default=None, help="Kaç rapor kapsansın (varsayılan: 6)")
    nl.add_argument("--test-to", default=None, metavar="EMAIL",
                    help="Yalnızca bu adrese gönder (liste abonelerine dokunulmaz)")
    nl.add_argument("--dry-run", action="store_true", help="Göndermeden üret ve logla")
    nl.set_defaults(func=_cmd_newsletter)

    ip = sub.add_parser("ipo-pdf", help="Örnek halka arz raporu üret")
    ip.set_defaults(func=_cmd_ipo_pdf)

    pt = sub.add_parser("publish-turib", help="TÜRİB & Et-yem verilerini web JSON'a yaz")
    pt.set_defaults(func=_cmd_publish_turib)

    st = sub.add_parser("stocks", help="Hisse finansalları + oranlar (web/public/data/stocks) üret")
    st.add_argument("--tickers", nargs="*", help="Sadece bu hisseler (varsayılan: tüm evren)")
    st.add_argument("--workers", type=int, default=4)
    st.add_argument("--no-prices", action="store_true", help="Fiyat geçmişini atla")
    st.set_defaults(func=_cmd_stocks)

    fd = sub.add_parser("funds", help="TEFAS fonları (web/public/data/funds + universe-funds.json) üret")
    fd.add_argument("--limit", type=int, default=200, help="En büyük kaç fon (varsayılan 200, üst sınır 2000)")
    fd.add_argument("--codes", nargs="*", help="Sadece bu fon kodları (mevcut evreni bozmaz)")
    fd.add_argument("--interval", type=float, default=0.4, help="İstekler arası saniye (TEFAS hız sınırı için)")
    fd.set_defaults(func=_cmd_funds)

    kf = sub.add_parser("kap-financials", help="KAP finansal raporlarından IFRS tabloları (web/public/data/kap) üret")
    kf.add_argument("--tickers", nargs="*", help="Sadece bu hisseler (varsayılan: bankasız tüm evren)")
    kf.add_argument("--months", type=int, default=18, help="Geriye dönük ay (varsayılan 18)")
    kf.add_argument("--workers", type=int, default=3)
    kf.set_defaults(func=_cmd_kap_financials)

    nv = sub.add_parser("nav", help="Holdinglerin KAP iştirak pay tablosu (web/public/data/nav) — NAV girdisi")
    nv.add_argument("--tickers", nargs="*", help="Sadece bu şirketler (varsayılan: Holding sektörü + ALARK, TKFEN)")
    nv.set_defaults(func=_cmd_nav)

    hl = sub.add_parser("health", help="Veri tazeliği + canlı site/dağıtım sağlık denetimi (başarısızlıkta çıkış 1)")
    hl.add_argument("--site", default="https://esham.pages.dev", help="Canlı site adresi")
    hl.add_argument("--offline", action="store_true", help="Ağ sorgusu yapma, yalnızca yerel dosya tazeliği")
    hl.set_defaults(func=_cmd_health)

    return parser


def main() -> None:
    if sys.stdout.encoding != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")
    configure_logging()
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
