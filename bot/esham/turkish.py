"""Türkçe metin yardımcıları — tek doğruluk kaynağı.

Python'un varsayılan `.upper()`/`.lower()`'ı Türkçe İ/I/ı/i kurallarını doğru
uygulamaz (`'i'.upper() == 'I'` olur ama Türkçede `'İ'` olmalı). Ayrıca gerçek
dünya belgeleri (KAP bildirimleri, OCR'lı PDF'ler, eski sistemler) çoğu zaman
aksan işaretlerini kaybeder ("taahhüt" -> "taahhut"). Kelime eşleştirmesi yapan
her yer (belge bölüm ayıklama, KAP önem filtresi, kart üreticisi) bu modülü
kullanır — aksi halde her biri kendi (muhtemelen hatalı) kopyasını yazar.
"""
from __future__ import annotations

_UPPER_MAP = str.maketrans({"i": "İ", "ı": "I"})
_FOLD_MAP = str.maketrans(
    {
        "İ": "i", "I": "ı", "ş": "s", "Ş": "s", "ğ": "g", "Ğ": "g",
        "ü": "u", "Ü": "u", "ö": "o", "Ö": "o", "ç": "c", "Ç": "c",
    }
)


def tr_upper(s: str) -> str:
    """Türkçe-doğru büyük harf: 'i' -> 'İ' (noktalı), 'ı' -> 'I' önce uygulanır."""
    return s.translate(_UPPER_MAP).upper()


def tr_fold(s: str) -> str:
    """Aksan-toleranslı katlama + küçük harf — anahtar kelime eşleştirmesi için.

    Hem karşılaştırılan metin hem anahtar kelimeler bu fonksiyondan geçmeli;
    aksi halde "taahhüt" anahtar kelimesi aksansız yazılmış "taahhut" metnini
    hiç bulamaz ve o bölüm AI'a hiç gitmez.
    """
    return s.translate(_FOLD_MAP).lower()
