"""Sabah bülteni PDF üreticisi.

Esham marka kimliğiyle branded, A4 formatında sabah piyasa bülteni PDF'i üretir.
HTML şablonu oluşturur; PDF dönüşümü için WeasyPrint veya pdfkit kullanır.
Her ikisi de kurulu değilse HTML dosyası diske kaydedilir ve uyarı loglanır.

Çıktı: web/public/reports/{slug}.pdf (Cloudflare Pages'te statik dosya olarak sunulur)
"""
from __future__ import annotations

import html as _html
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ..config import get_logger, settings
from ..sources import MarketSnapshot

log = get_logger(__name__)

# Çıktı klasörü — web/public/reports/ altında statik olarak sunulur
_DEFAULT_OUT_DIR = Path(__file__).resolve().parents[4] / "web" / "public" / "reports"


def _esc(v: object) -> str:
    """HTML özel karakterlerini kaçışlar."""
    if v in (None, ""):
        return ""
    return _html.escape(str(v))


def _md_to_html(md: str) -> str:
    """Basit markdown → HTML dönüştürücü (başlıklar, bold, liste, paragraf).
    Tam markdown parser gerekmeden temel biçimlendirmeyi destekler.
    """
    lines = md.split("\n")
    out: list[str] = []
    in_list = False

    for line in lines:
        stripped = line.strip()

        # Boş satır
        if not stripped:
            if in_list:
                out.append("</ul>")
                in_list = False
            out.append("")
            continue

        # ## Başlık 2
        if stripped.startswith("## "):
            if in_list:
                out.append("</ul>")
                in_list = False
            out.append(f'<h2 class="section-title">{_esc(stripped[3:])}</h2>')
            continue

        # ### Başlık 3
        if stripped.startswith("### "):
            if in_list:
                out.append("</ul>")
                in_list = False
            out.append(f'<h3 class="sub-title">{_esc(stripped[4:])}</h3>')
            continue

        # Liste öğesi (- veya *)
        if stripped.startswith(("- ", "* ", "• ")):
            if not in_list:
                out.append('<ul class="bullet-list">')
                in_list = True
            item = stripped[2:]
            # Bold içinde **...**
            item = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", _esc(item))
            out.append(f"<li>{item}</li>")
            continue

        # Numaralı liste
        num_match = re.match(r"^(\d+)\.\s+(.+)$", stripped)
        if num_match:
            if not in_list:
                out.append('<ul class="bullet-list">')
                in_list = True
            item = num_match.group(2)
            item = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", _esc(item))
            out.append(f"<li>{item}</li>")
            continue

        # Normal paragraf
        if in_list:
            out.append("</ul>")
            in_list = False
        para = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", _esc(stripped))
        out.append(f"<p>{para}</p>")

    if in_list:
        out.append("</ul>")

    return "\n".join(out)


def _snapshot_pills(snapshot: MarketSnapshot) -> str:
    """Snapshot verilerinden üst bant için HTML pill'leri üretir."""
    pills: list[str] = []

    if snapshot.bist:
        b = snapshot.bist
        color = "positive" if b.change and b.change.startswith("+") else "negative"
        pills.append(
            f'<span class="pill">'
            f'<span class="pill-label">{_esc(b.index)}</span>'
            f'<span class="pill-value">{_esc(b.price)}</span>'
            f'<span class="pill-change {color}">{_esc(b.change)}</span>'
            f"</span>"
        )

    if snapshot.macro and snapshot.macro.tickers:
        for t in snapshot.macro.tickers[:5]:
            pills.append(
                f'<span class="pill">'
                f'<span class="pill-label">{_esc(t.label)}</span>'
                f'<span class="pill-value">{_esc(t.value_str)}</span>'
                f"</span>"
            )

    return "\n".join(pills)


def _sector_table(snapshot: MarketSnapshot) -> str:
    """Sektör tablosu HTML'i."""
    if not snapshot.sector:
        return ""
    rows = []
    for s in sorted(snapshot.sector, key=lambda x: float(x.change_pct or 0), reverse=True)[:8]:
        pct = getattr(s, "change_pct", None)
        color = "positive" if pct and float(pct) >= 0 else "negative"
        rows.append(
            f"<tr>"
            f"<td>{_esc(getattr(s, 'name', ''))}</td>"
            f'<td class="{color}">{float(pct):+.2f}%</td>'
            f"</tr>"
        )
    if not rows:
        return ""
    return (
        '<table class="sector-table">'
        "<thead><tr><th>Sektör</th><th>Değişim</th></tr></thead>"
        "<tbody>" + "".join(rows) + "</tbody>"
        "</table>"
    )


def build_html(
    body_md: str,
    snapshot: MarketSnapshot,
    title: str = "BIST & Küresel Piyasalar Sabah Raporu",
    slug: str = "",
    site_url: str = "",
) -> str:
    """Branded HTML sabah bülteni şablonu üretir."""
    today = datetime.now(timezone(timedelta(hours=3)))
    date_str = today.strftime("%d %B %Y")
    time_str = today.strftime("%H:%M")

    body_html = _md_to_html(body_md)
    pills_html = _snapshot_pills(snapshot)
    sector_html = _sector_table(snapshot)

    report_url = f"{site_url}/rapor/{slug}" if site_url and slug else site_url

    return f"""<!DOCTYPE html>
<html lang="tr">
<head>
  <meta charset="UTF-8" />
  <title>{_esc(title)}</title>
  <style>
    /* ── Genel reset ── */
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
      background: #ffffff;
      color: #1e293b;
      font-size: 13px;
      line-height: 1.6;
    }}

    /* ── Üst başlık bandı ── */
    .header {{
      background: #060b18;
      color: #ffffff;
      padding: 28px 40px 20px;
      border-bottom: 3px solid #3b82f6;
    }}
    .header-top {{
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      margin-bottom: 16px;
    }}
    .brand {{
      display: flex;
      flex-direction: column;
    }}
    .brand-name {{
      font-size: 32px;
      font-weight: 800;
      letter-spacing: -0.5px;
    }}
    .brand-name .accent {{ color: #3b82f6; }}
    .brand-tagline {{
      font-size: 11px;
      color: #64748b;
      letter-spacing: 0.8px;
      text-transform: uppercase;
      margin-top: 2px;
    }}
    .header-meta {{
      text-align: right;
    }}
    .report-type {{
      font-size: 11px;
      letter-spacing: 1px;
      text-transform: uppercase;
      color: #3b82f6;
      font-weight: 700;
      margin-bottom: 4px;
    }}
    .report-date {{
      font-size: 20px;
      font-weight: 700;
      color: #ffffff;
    }}
    .report-time {{
      font-size: 12px;
      color: #64748b;
      margin-top: 2px;
    }}

    /* ── Piyasa pills bandı ── */
    .ticker-band {{
      background: #0f172a;
      padding: 12px 40px;
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
      border-bottom: 1px solid #1e293b;
    }}
    .pill {{
      display: flex;
      align-items: center;
      gap: 6px;
      background: #1e293b;
      border-radius: 6px;
      padding: 5px 10px;
    }}
    .pill-label {{
      font-size: 10px;
      font-weight: 700;
      letter-spacing: 0.5px;
      text-transform: uppercase;
      color: #64748b;
    }}
    .pill-value {{
      font-size: 12px;
      font-weight: 600;
      color: #f1f5f9;
    }}
    .pill-change {{
      font-size: 11px;
      font-weight: 600;
    }}
    .positive {{ color: #22c55e; }}
    .negative {{ color: #ef4444; }}

    /* ── Ana başlık ── */
    .report-title {{
      padding: 24px 40px 0;
      background: #f8fafc;
      border-bottom: 1px solid #e2e8f0;
    }}
    .report-title h1 {{
      font-size: 22px;
      font-weight: 800;
      color: #0f172a;
      letter-spacing: -0.3px;
      padding-bottom: 20px;
    }}

    /* ── İçerik alanı ── */
    .content {{
      padding: 28px 40px;
      max-width: 900px;
    }}

    /* ── Bölüm başlıkları ── */
    h2.section-title {{
      font-size: 15px;
      font-weight: 700;
      color: #0f172a;
      border-left: 4px solid #3b82f6;
      padding-left: 10px;
      margin: 24px 0 10px;
      text-transform: uppercase;
      letter-spacing: 0.3px;
    }}
    h2.section-title:first-child {{ margin-top: 0; }}

    h3.sub-title {{
      font-size: 13px;
      font-weight: 700;
      color: #334155;
      margin: 16px 0 6px;
    }}

    p {{
      margin-bottom: 8px;
      color: #334155;
    }}

    /* ── Listeler ── */
    ul.bullet-list {{
      margin: 6px 0 10px 18px;
      color: #334155;
    }}
    ul.bullet-list li {{
      margin-bottom: 4px;
    }}

    /* ── Sektör tablosu ── */
    .sector-section {{
      margin-top: 24px;
      padding-top: 20px;
      border-top: 1px solid #e2e8f0;
    }}
    .sector-section h2 {{
      font-size: 13px;
      font-weight: 700;
      color: #0f172a;
      border-left: 4px solid #3b82f6;
      padding-left: 10px;
      margin-bottom: 12px;
      text-transform: uppercase;
      letter-spacing: 0.3px;
    }}
    .sector-table {{
      width: 320px;
      border-collapse: collapse;
      font-size: 12px;
    }}
    .sector-table th {{
      background: #f1f5f9;
      color: #64748b;
      font-weight: 700;
      text-align: left;
      padding: 6px 10px;
      font-size: 10px;
      letter-spacing: 0.5px;
      text-transform: uppercase;
    }}
    .sector-table td {{
      padding: 6px 10px;
      border-bottom: 1px solid #f1f5f9;
      color: #334155;
    }}
    .sector-table td:last-child {{
      font-weight: 700;
      text-align: right;
    }}

    /* ── Footer ── */
    .footer {{
      background: #060b18;
      color: #64748b;
      padding: 16px 40px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      font-size: 10px;
      border-top: 1px solid #1e293b;
      margin-top: 32px;
    }}
    .footer a {{
      color: #3b82f6;
      text-decoration: none;
    }}
    .footer .disclaimer {{
      color: #475569;
      font-style: italic;
    }}
  </style>
</head>
<body>

  <!-- Üst başlık -->
  <div class="header">
    <div class="header-top">
      <div class="brand">
        <div class="brand-name"><span class="accent">E</span>sham</div>
        <div class="brand-tagline">Yapay Zeka Destekli Piyasa Analizi</div>
      </div>
      <div class="header-meta">
        <div class="report-type">Sabah Bülteni</div>
        <div class="report-date">{_esc(date_str)}</div>
        <div class="report-time">{_esc(time_str)} TR</div>
      </div>
    </div>
  </div>

  <!-- Piyasa ticker bandı -->
  {"<div class='ticker-band'>" + pills_html + "</div>" if pills_html else ""}

  <!-- Rapor başlığı -->
  <div class="report-title">
    <h1>{_esc(title)}</h1>
  </div>

  <!-- Ana içerik -->
  <div class="content">
    {body_html}

    <!-- Sektör tablosu (varsa) -->
    {('<div class="sector-section"><h2>Sektör Görünümü</h2>' + sector_html + "</div>") if sector_html else ""}
  </div>

  <!-- Footer -->
  <div class="footer">
    <div>
      <strong style="color:#94a3b8;">esham.pages.dev</strong>
      {(' · <a href="' + _esc(report_url) + '">Tam Rapor</a>') if report_url else ''}
    </div>
    <div class="disclaimer">Bu rapor yatırım tavsiyesi değildir.</div>
  </div>

</body>
</html>"""


def generate_pdf(
    body_md: str,
    snapshot: MarketSnapshot,
    slug: str,
    title: str = "BIST & Küresel Piyasalar Sabah Raporu",
    out_dir: Path | None = None,
) -> Path | None:
    """PDF sabah bülteni üretir. Başarılıysa PDF Path'ini, başarısızsa None döner.

    Önce WeasyPrint, sonra pdfkit dener. Her ikisi de yoksa HTML kaydeder ve None döner.
    """
    out_dir = out_dir or _DEFAULT_OUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    site_url = settings.site_url
    html_content = build_html(
        body_md=body_md,
        snapshot=snapshot,
        title=title,
        slug=slug,
        site_url=site_url,
    )

    pdf_path = out_dir / f"{slug}.pdf"
    html_path = out_dir / f"{slug}.html"

    # Önce WeasyPrint dene
    try:
        from weasyprint import HTML  # type: ignore[import]
        HTML(string=html_content).write_pdf(str(pdf_path))
        log.info("PDF üretildi (WeasyPrint): %s", pdf_path)
        return pdf_path
    except ImportError:
        log.debug("WeasyPrint kurulu değil, pdfkit deneniyor.")
    except Exception as exc:
        log.warning("WeasyPrint PDF hatası: %s", exc)

    # pdfkit dene
    try:
        import pdfkit  # type: ignore[import]
        pdfkit.from_string(html_content, str(pdf_path))
        log.info("PDF üretildi (pdfkit): %s", pdf_path)
        return pdf_path
    except ImportError:
        log.debug("pdfkit kurulu değil.")
    except Exception as exc:
        log.warning("pdfkit PDF hatası: %s", exc)

    # Fallback: sadece HTML kaydet
    html_path.write_text(html_content, encoding="utf-8")
    log.warning(
        "PDF kütüphanesi bulunamadı; HTML kaydedildi: %s. "
        "PDF için: pip install weasyprint",
        html_path,
    )
    return None
