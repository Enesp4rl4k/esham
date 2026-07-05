"""Halka arz analiz PDF üreticisi.

Fintables tarzı tek sayfalık görsel rapor. HTML şablonu üretilir; PDF'e çevirme
adımı pdfkit (wkhtmltopdf) veya WeasyPrint ile yapılır. Bu kütüphaneler kurulu
değilse HTML çıktısı diske yazılır ve uyarı loglanır.
"""
from __future__ import annotations

from pathlib import Path

from ..config import get_logger, settings

log = get_logger(__name__)


class IpoPdfGenerator:
    def __init__(self, output_dir: Path | None = None) -> None:
        self.output_dir = output_dir or settings.ipo_output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _render_field(value) -> str:
        """Liste -> <ul>, sözlük -> tablo, diğer -> düz metin."""
        if isinstance(value, list):
            if not value:
                return "<p>-</p>"
            items = "".join(f"<li>{v}</li>" for v in value)
            return f"<ul>{items}</ul>"
        if isinstance(value, dict):
            if not value:
                return "<p>-</p>"
            rows = "".join(f"<tr><td>{k}</td><td>{v}</td></tr>" for k, v in value.items())
            return f"<table class='ratios'>{rows}</table>"
        return f"<p>{value if value not in (None, '') else '-'}</p>"

    def build_html(self, data: dict) -> str:
        r = self._render_field
        return f"""<!doctype html>
<html lang="tr">
<head>
<meta charset="utf-8" />
<style>
  body {{ font-family: 'Helvetica', Arial, sans-serif; color: #1e293b; margin: 0; }}
  .header {{ background: #0f172a; color: white; padding: 28px; text-align: center; }}
  .title {{ font-size: 26px; font-weight: 700; margin-bottom: 6px; }}
  .content {{ padding: 24px; }}
  .grid {{ display: flex; flex-wrap: wrap; gap: 16px; }}
  .box {{ border: 1px solid #e2e8f0; padding: 16px; width: 45%; border-radius: 10px; }}
  .box.full {{ width: 100%; }}
  .box h3 {{ margin: 0 0 8px; font-size: 15px; color: #0f172a; }}
  .box ul {{ margin: 0; padding-left: 18px; }}
  table.ratios {{ width: 100%; border-collapse: collapse; }}
  table.ratios td {{ border-bottom: 1px solid #e2e8f0; padding: 4px 0; }}
  .risks h3 {{ color: #b91c1c; }}
  .strengths h3 {{ color: #047857; }}
  .disclaimer {{ font-size: 11px; color: #64748b; text-align: center; margin-top: 20px; }}
</style>
</head>
<body>
  <div class="header">
    <div class="title">{data.get('company_name', 'Halka Arz Analizi')}</div>
    <div>Borsa Kodu: {data.get('ticker', 'UNKNOWN')}</div>
  </div>
  <div class="content">
    <div class="grid">
      <div class="box"><h3>Halka Arz Fiyatı & İskonto</h3>
        <p>Fiyat: {data.get('price', '-')} TL</p>
        <p>İskonto Oranı: {data.get('discount', '-')}</p>
        <p>Büyüklük: {data.get('offer_size', '-')}</p></div>
      <div class="box"><h3>Değerleme Çarpanları</h3>{r(data.get('valuation'))}</div>
      <div class="box"><h3>Fonun Kullanım Yeri</h3>{r(data.get('fund_usage', data.get('funds_usage')))}</div>
      <div class="box"><h3>Taahhütler</h3>{r(data.get('commitments'))}</div>
      <div class="box strengths"><h3>✅ Olumlu Noktalar</h3>{r(data.get('strengths'))}</div>
      <div class="box risks"><h3>🚨 Riskler</h3>{r(data.get('risks'))}</div>
      <div class="box full"><h3>Değerlendirme</h3>{r(data.get('verdict', data.get('financials')))}</div>
    </div>
    <hr />
    <p class="disclaimer">Bu rapor yapay zeka tarafından KAP belgeleri analiz edilerek
    üretilmiştir. Yatırım tavsiyesi değildir.</p>
  </div>
</body>
</html>"""

    def create(self, ipo_data: dict) -> Path:
        ticker = ipo_data.get("ticker", "IPO")
        html = self.build_html(ipo_data)
        html_path = self.output_dir / f"{ticker}_Analiz_Raporu.html"
        html_path.write_text(html, encoding="utf-8")

        pdf_path = self.output_dir / f"{ticker}_Analiz_Raporu.pdf"
        try:
            import pdfkit  # type: ignore

            pdfkit.from_string(html, str(pdf_path))
            log.info("Halka arz PDF raporu oluşturuldu: %s", pdf_path)
            return pdf_path
        except Exception as exc:
            log.warning(
                "PDF üretimi atlandı (%s). HTML çıktısı kaydedildi: %s", exc, html_path
            )
            return html_path
