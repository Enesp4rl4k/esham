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
import re

from . import Disclosure
from ..turkish import tr_fold

# Materiality sinyali güçlü kelimeler (pozitif ağırlık = paylaşıma değer).
MATERIAL_KEYWORDS: dict[str, int] = {
    # Kök kullanılır (tam kelime değil) — Türkçe eklemeli dil olduğu için
    # "devral" hem "devralma" hem "devraldı" hem "devralınmasına" ile eşleşir.
    # Birincil sinyal — tek başına eşiği geçer (≥4)
    "birleş": 4, "devral": 4, "satın al": 4, "iştirak": 3,
    "kâr payı": 4, "kar payı": 4, "temettü": 4,
    "sermaye artır": 4, "bedelli": 3, "bedelsiz": 3,
    "iflas": 4, "konkordato": 4, "tasfiye": 4,
    "faaliyet durdur": 4, "üretim durdur": 3,
    "tahvil ihrac": 3, "temerrüt": 4,
    "halka arz": 4, "fiyat tespit": 4, "izahname": 3,
    "hisse devri": 3, "blok satış": 3,
    "kredi notu": 4,  # downgrade/upgrade — tek başına önemli

    # İkincil sinyal — birleşince eşiği geçer (2-3)
    "pay geri alım": 2, "geri alım program": 3,
    "kredi derecelendirme": 2, "not tespit": 2,
    "yönetim kurulu üye": 2, "genel müdür": 2, "ceo": 2,
    "dava": 2, "ceza": 2, "idari para cezası": 3,
    "ihale": 3, "önemli sözleşme": 3, "sözleşme imza": 3,
    "yeni iş ilişkisi": 4, "yeni sipariş": 3, "sipariş": 2,
    "kapasite artır": 2, "ihracat anlaşma": 2,
    "ruhsat": 1, "patent": 1, "lisans anlaşma": 2,
    "grev": 2,
    "teminat mektubu": 1,
    "kâr tahmin": 2, "kar tahmin": 2, "beklenti revizyon": 3,

    # ── Makroekonomik ve para politikası sinyalleri ────────────────────────
    # TCMB & para politikası — yüksek etki, tek başına geçer
    "faiz karar": 4, "faiz artır": 4, "faiz indir": 4,
    "para politikası": 4, "ppk karar": 4, "merkez bankası karar": 4,
    "tcmb": 3, "rezerv": 2, "swap": 2, "zorunlu karşılık": 4,
    "enflasyon hedef": 4, "enflasyon raporu": 4,

    # Hazine & kamu maliyesi
    "hazine ihale": 4, "tahvil ihale": 4, "bono ihale": 3,
    "bütçe açık": 4, "bütçe fazla": 4, "cari açık": 4, "cari denge": 3,
    "eurobond": 4, "dış borç": 2,

    # Makro veri açıklamaları — önemli veriler tek başına geçmeli
    "enflasyon": 2, "tüfe": 4, "üfe": 4, "gsyh": 4, "büyüme": 3,
    "işsizlik": 3, "istihdam": 2, "ihracat": 1, "ithalat": 1,
    "dış ticaret": 2, "sanayi üretim": 2, "kapasite kullanım": 1,

    # SPK & düzenleyici
    "spk karar": 4, "bddk karar": 4, "düzenleyici karar": 3,
    "muafiyet": 2, "spk onay": 3, "spk ret": 3,

    # Uluslararası piyasa & kredi
    "imf": 2, "dünya bankası": 2, "görünüm": 1,
    "yabancı yatırımcı": 2, "portföy akış": 2,
    "döviz kuru": 2, "dolar": 1, "euro": 1, "sterlin": 1,
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

    # ── Gerçek KAP başlık formatları (keyword match'i tutturmak için) ──────────
    # KAP'ın ürettiği gerçek başlık kalıplarına göre eşleştirildi.
    # tr_fold() hem keyword'leri hem metni dönüştürür; ASCII yazım tutarlıdır.
    "bagimsiz denetim kurulusunun belirlenmesi": -3,   # "Bağımsız Denetim Kuruluşunun Belirlenmesi"
    "bagimsiz denetim kurulusu bildirimi": -3,          # "Bağımsız Denetim Kuruluşu Bildirimi"
    "bagimsiz denetim secimi": -3,                      # alternatif başlık formu

    # Rutin tescil bildirimleri — sadece "...tescili" ile biten başlıklar
    # DİKKAT: "tescili hakkında" çok geniş — SPK başvurusu gibi önemli bildirimler
    # de "...tescil" içerebilir. Sadece kesin bağımsız denetim tescilini yakala.
    "denetim sirketi seciminin tescili": -3,            # "Bağımsız Denetim Şirketi Seçiminin Tesceli"
    "denetim kurulusu seciminin tesceli": -3,           # alternatif yazım

    # ── Şirket adresi / unvan / tescil bildirimleri ──────────────────────────
    # "Şirket Merkez Adresinin Tescili", "Merkez Adresi Değişikliği" gibi
    # bildirimlerin yatırımcıya hiçbir yeni bilgi katmaz.
    "merkez adresinin tescili": -5,
    "merkez adresi degisikligi": -5,
    "merkez adresi tescili": -5,
    "sirket merkez adresi": -4,
    "adres degisikligi tescil": -4,
    "esas sozlesme tadil": -2,              # esas sözleşme tadili genellikle rutin
    "unvan degisikligi tescil": -4,
    "ticaret sicil tescil": -4,             # rutin ticaret sicil bildirimleri
    "tescil ve ilan": -3,

    # ── Rutin kurumsal bildirimler ────────────────────────────────────────────
    "ozel hesap donem": -2,                 # özel hesap dönemi bildirimleri
    "kurucu pay": -2,                       # kurucu pay bildirimleri
    "nakdi sermaye artirimi tamamlandi": -1, # tamamlandı bildirimi (SPK başvurusu daha önemli)
    "bilgi formu guncelleme": -3,           # kurumsal yönetim bilgi formu güncellemesi
    "kurumsal yonetim bilgi formu": -3,

    # Vekâlet bildirimleri — spesifik, "vekalet" tek başına çok geniş
    "vekaletname": -3,
    "vekaleten katilim": -2,                            # "vekaleten katılım" zaten yukarıda var ama ASCII form

    # Kurumsal yönetim derecelendirme bildirimleri — not değişmemişse değersiz
    # Not: "kredi derecelendirme" zaten MATERIAL_KEYWORDS'de +2 puan alıyor.
    # KY uyum notu bildirimleri (rutin periyodik güncelleme) -2 ile dengelenir → net 0, eşik 3 → filtre.
    "kurumsal yonetim ilkelerine uyum derecelendirmesi": -2,
    "kurumsal yonetim derecelendirme not bildirimi": -2,

    # Rutin YK/atama bildirimleri — tek başına "atama" ya da "istifa" anlamsız;
    # önemli YK değişiklikleri genellikle "genel müdür", "CEO" gibi keyword'lerle
    # MATERIAL_KEYWORDS'den pozitif puan zaten alır.
    "yonetim kurulu uyesi atamasi hakkinda": -1,        # rutin atama bildirimi
    "yonetim kurulu uyesi istifasi": -1,                # tek başına rutin istifa

    # Rutin tarihli pay geri alım raporları — "X Tarihli Pay Geri Alım İşlemleri"
    # MATERIAL_KEYWORDS'deki "pay geri alım: +2" bu başlığa da uygulanır;
    # -2 ile dengelenir → net 0 → filtre (eşik 3).
        # ── Rutin seans içi tarihli pay geri alım bildirimleri (Spam Kalkanı) ──────
    # Günlük 100 lotluk seans içi rutin geri alımlar analize değmez.
    # Program başlangıcı veya iptali değil, sadece günlük seans listeleridir.
    "tarihli pay geri alim": -6,
    "tarihli geri alim": -6,
    "tarihinde gerceklestirilen pay geri alim": -6,
    "pay geri alim islemleri hakkinda": -4,
    "pay geri alim programi kapsaminda gerceklestirilen": -4,

    # ── Rutin bürokrasi / YK / Denetim / Şube / Yetki ────────────────────────
    "yonetim kurulu gorev dagilimi": -4,
    "yonetim kurulu komiteleri": -4,
    "yetki devri": -4,
    "imza sirkuleri": -5,
    "sube acilisi": -3,
    "sube kapanisi": -3,


    # ── Post-arz bildirimleri (tamamlanmış halka arzlara ait rutin açıklamalar) ──
    # Bunlar yatırımcıya yeni bilgi taşımaz; eski arzların kapanış işlemleridir.
    "fiyat tespit raporuna iliskin": -5,   # analist raporu — eski arz
    "inden fazlasini alanlar": -5,          # %5 bildirim — eski arz
    "arz edilen toplam paylarin": -5,       # pay dağılımı — eski arz
    "pay alimi yapan idari": -5,            # yönetici alımı — eski arz
    "paylarinin halka arzinda": -4,         # genel post-arz ifadesi
    "halka arz isleminde": -4,              # işlem bildirimi
    "talep toplama sonuclari": -5,          # talep toplama bitti
    "kesin tahsisat": -5,                   # tahsisat bildirimi
}

# Genel/kategorisiz KAP akışı için varsayılan eşik. Insider/IPO bu filtreyi
# atladığı için etkilenmez.
# 1 → 3: tek bir ikincil sinyal (ör. "ruhsat", "onay") artık eşiği geçemiyor;
# en az bir birincil sinyal veya birden fazla ikincil sinyal gerekiyor.
DEFAULT_THRESHOLD = 3


def is_routine_daily_buyback(title: str, text: str) -> bool:
    """Günlük seans içi rutin pay geri alım bildirimini tespit eder."""
    norm = tr_fold(f"{title} {text}")
    # Örn: 02.11.2026 Tarihli Pay Geri Alım İşlemleri veya 2 Kasım tarihli geri alım
    if re.search(r"(\d{1,2}[./]\d{1,2}[./]\d{2,4}|\d{1,2}\s+[a-zçğıöşü]+\s+\d{2,4}).*?(geri\s+al[ıi]m)", norm):
        return True
    if "tarihli" in norm and ("geri al" in norm or "pay alim" in norm):
        return True
    return False


def score(d: Disclosure) -> int:
    """Bildirimin önem skoru. Pozitif = önemli sinyal ağır basıyor."""
    # Rutin seans içi geri alım ise doğrudan negatif skor vererek ele
    if is_routine_daily_buyback(d.title, d.raw_text):
        return -5

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
