"""Belge yükleyici: yerel PDF, URL (KAP PDF'i) veya ham metin.

pypdf kurulu değilse veya çıkarım başarısızsa boş metin döner ve uyarı loglanır;
çağıran taraf fallback'e düşebilir.
"""
from __future__ import annotations

import io
from pathlib import Path

import requests

from ..config import default_headers, get_logger, settings

log = get_logger(__name__)


def _extract_pdf_bytes(data: bytes) -> str:
    try:
        from pypdf import PdfReader
    except Exception:
        log.warning("pypdf kurulu değil; PDF metni çıkarılamıyor.")
        return ""
    try:
        reader = PdfReader(io.BytesIO(data))
        parts = [page.extract_text() or "" for page in reader.pages]
        return "\n".join(parts).strip()
    except Exception as exc:
        log.warning("PDF ayrıştırma hatası: %s", exc)
        return ""


def load_document_text(source: str) -> str:
    """`source`: http(s) URL, yerel dosya yolu veya doğrudan metin.

    KAP göreli linkleri (``/tr/Bildirim/Pdf/...``) mutlak URL'ye çevrilir.
    """
    if not source:
        return ""

    # KAP göreli PDF linki
    if source.startswith("/tr/") or source.startswith("/Bildirim/"):
        source = f"https://www.kap.org.tr{source}"

    if source.startswith("http://") or source.startswith("https://"):
        try:
            resp = requests.get(
                source, headers=default_headers(), timeout=settings.http_timeout
            )
            resp.raise_for_status()
        except requests.RequestException as exc:
            log.warning("Belge indirilemedi (%s): %s", source, exc)
            return ""
        ctype = resp.headers.get("Content-Type", "")
        if "pdf" in ctype.lower() or source.lower().endswith(".pdf"):
            return _extract_pdf_bytes(resp.content)
        return resp.text

    path = Path(source)
    if path.exists():
        if path.suffix.lower() == ".pdf":
            return _extract_pdf_bytes(path.read_bytes())
        return path.read_text(encoding="utf-8", errors="ignore")

    # Dosya/URL değilse ham metin kabul et.
    return source
