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
from .news_stream import NewsStream
from .pipeline import (
    run_closing_report,
    run_morning_report,
    run_opening_report,
    run_sector_report,
    run_viop_report,
)
from .scheduler import build_default_scheduler
from .publishing.ipo_pdf import IpoPdfGenerator
from .risk.margin import MarginMonitor, default_parameters, load_parameters_file, load_positions_file
from .sources.viop import ViopSource, assess_margin_stress

log = get_logger(__name__)


def _cmd_morning_report(args: argparse.Namespace) -> None:
    run_morning_report(publish_social=not args.no_social)


def _cmd_news_stream(args: argparse.Namespace) -> None:
    stream = NewsStream(
        scan_interval=args.scan_interval,
        publish_interval=args.publish_interval,
    )
    if args.once:
        stream.check_once()
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


def _cmd_viop(args: argparse.Namespace) -> None:
    src = ViopSource()
    quote = src.market_quote()
    print("\n=== VİOP Piyasa ===")
    print(f"  Endeks {quote.index_symbol}: {quote.index_price}  {quote.index_change}")
    if quote.futures_symbol:
        print(
            f"  Vadeli {quote.futures_symbol}: {quote.futures_price}  "
            f"{quote.futures_change}  hacim {quote.futures_volume}"
        )

    snap = src.margin_snapshot()
    stress = assess_margin_stress(snap.margin_call_to_required_pct, args.prior_pct)
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
        slug = run_viop_report(prior_pct=args.prior_pct, publish=True)
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


def _cmd_sector(_: argparse.Namespace) -> None:
    run_sector_report()


def _cmd_evals(_: argparse.Namespace) -> None:
    from .evals.harness import print_report
    from .evals.suites import all_suites

    ok = print_report(all_suites())
    sys.exit(0 if ok else 1)


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
    ns.add_argument("--once", action="store_true", help="Tek tur tara ve tümünü yayınla")
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
    vp.set_defaults(func=_cmd_viop)

    rn = sub.add_parser("run", help="Günlük yayın orkestratörünü başlat (uzun-ömürlü)")
    rn.add_argument("--scan-interval", type=int, default=300, help="Haber tarama aralığı (sn)")
    rn.add_argument("--publish-interval", type=int, default=90, help="Haber yayın aralığı (sn)")
    rn.add_argument("--margin-interval", type=int, default=1800, help="Margin izleme aralığı (sn)")
    rn.set_defaults(func=_cmd_run)

    sub.add_parser("opening", help="BIST açılış notu yayınla").set_defaults(func=_cmd_opening)
    sub.add_parser("closing", help="Kapanış bülteni yayınla").set_defaults(func=_cmd_closing)
    sub.add_parser("sector", help="Haftalık sektör rotasyonu yayınla").set_defaults(func=_cmd_sector)
    sub.add_parser("evals", help="AI çıktı kalitesi/güvenlik eval'lerini çalıştır").set_defaults(func=_cmd_evals)

    ip = sub.add_parser("ipo-pdf", help="Örnek halka arz raporu üret")
    ip.set_defaults(func=_cmd_ipo_pdf)

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
