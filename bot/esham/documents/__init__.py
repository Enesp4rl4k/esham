"""Belge katmanı: PDF metin çıkarma ve ilgili bölüm ayıklama.

Uzun belgeleri (izahname, fiyat tespit raporu, faaliyet raporu) AI'a göndermeden
önce token maliyetini düşürmek için anahtar kelimeyle ilgili bölümleri süzeriz.
"""
from .loader import load_document_text
from .sections import extract_relevant

__all__ = ["load_document_text", "extract_relevant"]
