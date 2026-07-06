"""KAP bildirim önem filtresi — hangi bildirimler paylaşıma değer?

`news_stream` sürekli tarama yaptığı için KAP'ın ürettiği HER bildirimi paylaşmak
(çoğu rutin/idari işlem) tweet akışını gürültüye boğar ve veri yığılmasına yol
açar. Bu filtre gerçek piyasa etkisi olası bildirimleri (birleşme, halka arz,
temettü, sermaye artırımı, önemli sözleşme, yönetim değişikliği, dava/ceza,
derecelendirme...) rutin/idari bildirimlerden (genel kurul çağrısı, bağımsız
denetim sözleşmesi yenileme, imza sirküleri, yatırımcı sunumu, portföy dağılım
raporu...) ayırır.

Insider (pay alım/satım) ve IPO (halka arz/fiyat tespit) bildirimleri zaten ayrı
işlem görür (öncelikli kuyruk / tam analiz) — bu filtre onlara UYGULANMAZ, her
zaman önemli sayılırlar.

Deterministik, saf, ücretsiz (AI çağrısı yok) — yüksek hacimli tarama döngüsünde
gecikme/maliyet eklemez. Ağırlıklar tunable; `score()` şeffaflık için ayrı
dışa açık.
"""
from __future__ import annotations

from . import Disclosure
from ..turkish import tr_fold

# Materiality sinyali güçlü kelimeler (pozitif ağırlık = paylaşıma değer).
MATERIAL_KEYWORDS: dict[str, int] = {
    # Kök kullanılır (tam kelime değil) — Türkçe eklemeli dil olduğu için
    # "devral" hem "devralma" hem "devraldı" hem "devralınmasına" ile eşleşir.
    "birleş": 3, "devral": 3, "satın al": 3, "iştirak": 2,
    "kâr payı": 3, "kar payı": 3, "temettü": 3,
    "sermaye artır": 3, "bedelli": 2, "bedelsiz": 2,
    "pay geri alım": 2, "geri alım program": 2,
    "kredi derecelendirme": 2, "not tespit": 2,
    "yönetim kurulu üye": 2, "genel müdür": 2, "ceo": 2,
    "iflas": 3, "konkordato": 3, "tasfiye": 3,
    "dava": 2, "ceza": 2, "idari para cezası": 2,
    "ihale": 2, "önemli sözleşme": 3, "sözleşme imza": 2,
    "kapasite artır": 2, "ihracat anlaşma": 2,
    "ruhsat": 1, "patent": 1, "lisans anlaşma": 2,
    "grev": 2, "üretim durdur": 2, "faaliyet durdur": 3,
    "tahvil ihrac": 2, "temerrüt": 3, "teminat mektubu": 1,
    "halka arz": 3, "fiyat tespit": 3, "izahname": 2,
    "kâr tahmin": 2, "kar tahmin": 2, "beklenti revizyon": 2,
    "hisse devri": 2, "blok satış": 2,
}

# Rutin/idari bildirimler (negatif ağırlık) — tek başına paylaşıma değmez.
ROUTINE_KEYWORDS: dict[str, int] = {
    "genel kurul": -2, "toplantı tutanağı": -2, "toplantı gündemi": -1,
    "bağımsız denetim sözleşmesi": -2, "denetim kuruluşu seçim": -1,
    "imza sirküleri": -3, "vekaleten katılım": -2,
    "yatırımcı sunum": -2, "portföy dağılım raporu": -3,
    "kap üyelik": -3, "bilgilendirme politikası": -2,
    "finansal rapor gönder": -1, "faaliyet raporu yayım": -1,
    "pay sahipleri": -1, "iç kaynaklardan": -1,
    "ortaklığın adres": -3, "unvan değişikliği": -1,
}

# Genel/kategorisiz KAP akışı için varsayılan eşik. Insider/IPO bu filtreyi
# atladığı için etkilenmez.
DEFAULT_THRESHOLD = 1


def score(d: Disclosure) -> int:
    """Bildirimin önem skoru. Pozitif = önemli sinyal ağır basıyor."""
    text = tr_fold(f"{d.disclosure_type} {d.title} {d.raw_text}")
    total = 0
    for kw, weight in MATERIAL_KEYWORDS.items():
        if tr_fold(kw) in text:
            total += weight
    for kw, weight in ROUTINE_KEYWORDS.items():
        if tr_fold(kw) in text:
            total += weight
    return total


def is_significant(d: Disclosure, threshold: int = DEFAULT_THRESHOLD) -> bool:
    """Eşiği geçen bildirimler paylaşılır. Sadece genel KAP akışı için kullanılır
    — insider/IPO sınıflandırması zaten ayrı ele alındığı için buraya gelmez."""
    return score(d) >= threshold
