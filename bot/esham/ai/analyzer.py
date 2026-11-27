"""Gemini tabanlı analiz ve içerik üretimi.

Tasarım ilkeleri:
- API anahtarı yoksa AI devre dışı kalır ama pipeline çökmemesi için deterministik
  şablon üretimine düşülür (graceful degradation).
- Ağ/model hataları yakalanır ve loglanır (LlmClient içinde).
"""
from __future__ import annotations

from ..config import get_logger, settings
from ..neutral import NOTE_AMOUNT_MISSING, extract_amounts, strip_banned
from ..translation import ensure_turkish, translate_to_turkish, is_mostly_english
from ..sources import MarketSnapshot
from .client import LlmClient

log = get_logger(__name__)

# Tüm üretim prompt'larına eklenir. Model kurala uymasa bile çıktı `neutral.strip_banned` ile
# deterministik olarak süzülür ve ContentStore/SocialPublisher'da tekrar denetlenir.
NEUTRAL_RULES = """
KESİN KURALLAR (SPK: yatırım danışmanlığı yalnızca yetkili kurumlarca yapılabilir):
- Yalnızca kaynakta yazanları aktar; kendi yorumunu, tahminini veya değerlendirmeni ekleme.
- Al/sat/tut önerisi, hedef fiyat, destek/direnç, pivot, kâr satışı veya alım bölgesi, RSI gibi teknik seviye YAZMA.
- "Pozitif/negatif sinyal", "olumlu/olumsuz algı", boğa/ayı senaryosu gibi yargı etiketleri KULLANMA.
- Fiyatın, hissenin, piyasanın veya haber akışının nasıl etkileneceğine dair tahmin YAPMA ("beklenir", "katalizör", "yükselebilir" vb.).
- "Mega", "dev", "tarihi" gibi abartılı nitelemeler KULLANMA.
- Kaynakta olmayan rakam UYDURMA. Tutarları kaynaktaki birimi ve anlamıyla yaz; bilgi yoksa "Belirtilmemiş" yaz.
"""


def filing_facts_markdown(
    company: str,
    ticker: str,
    title: str,
    disclosure_type: str,
    text: str,
    disclosure_index: str = "",
    date: str = "",
) -> str:
    """KAP bildirimi için BİREBİR bilgi bloğu (süzülmez): başlık aynen, şirket, tarih, KAP bildirim türü,
    bildirimde kesin biçimde geçen tutarlar, KAP bağlantısı.

    Tutar ayrıştırması kesin değilse tutar listelenmez; "bulunamadı" gibi olumsuz bir iddia da yazılmaz.
    """
    amounts = extract_amounts(text or "")
    who = f"{company} ({ticker})" if ticker and ticker != company else company
    lines = [
        "### Bildirim Bilgileri",
        f"- **Başlık (KAP):** {title}",
        f"- **Şirket:** {who}",
    ]
    if date:
        lines.append(f"- **Tarih:** {date}")
    lines.append(f"- **Bildirim türü (KAP):** {disclosure_type or 'Belirtilmemiş'}")
    if amounts:
        lines.append(
            "- **Bildirim metninde geçen tutarlar:** "
            + ", ".join(a.formatted() for a in amounts)
            + " (ne anlama geldikleri için bildirime bakın)"
        )
    else:
        lines.append(f"- **Tutar:** {NOTE_AMOUNT_MISSING}")
    if disclosure_index:
        lines.append(
            f"- **Kaynak:** [KAP bildirimi #{disclosure_index}](https://www.kap.org.tr/tr/Bildirim/{disclosure_index})"
        )
    else:
        lines.append("- **Kaynak:** KAP (Kamuyu Aydınlatma Platformu)")
    return "\n".join(lines)


class MarketAIAnalyzer:
    def __init__(self) -> None:
        # Sabah bülteni 4-5 bölümden oluşur; 2048 token Gemini 2.5'in thinking
        # bütçesini de kapsadığında yetmiyordu. 8192'ye çıkarıldı.
        self.client = LlmClient(settings.gemini_model, max_output_tokens=8192, temperature=0.4)
        if not self.client.enabled:
            log.warning("AI devre dışı; şablon üretimi kullanılacak.")

    def analyze_macro_impact(self, news_text: str) -> str:
        prompt = f"""
Sen tarafsız bir ekonomi editörüsün. Aşağıdaki makroekonomik gelişmede NE açıklandığını
(kim, ne, ne zaman, hangi rakamlar) çok kısa ve anlaşılır bir dille özetle.
{NEUTRAL_RULES}
Haber: {news_text}
"""
        out = self.client.generate(prompt, task_type="analysis")
        return strip_banned(out) if out else "Yapay zeka özeti şu an üretilemedi."

    def generate_event_analysis(
        self,
        event: "MarketEvent",
        macro_context: str = "",
    ) -> tuple[str, str, str]:
        """Piyasa olayı (Teknoloji, Kripto, Makro, Hisse veya Son Dakika) için
        zengin analiz gövdesi, özet ve tweet üretir.

        Döndürür: (body_markdown, summary_line, tweet_text)
        - body_markdown : Web raporu için detaylı, yapılandırılmış markdown metni (başlık içermez)
        - summary_line  : Başlıktan bağımsız, 1-2 cümlelik vurucu yönetici özeti (lead)
        - tweet_text    : Bilgi yoğunluğu yüksek sosyal medya paylaşımı (≤260 karakter)
        """
        macro_block = f"\nGüncel makro bağlam:\n{macro_context}" if macro_context else ""
        details_block = f"\nGelişme Detayları & Açıklama:\n{event.details}" if getattr(event, "details", "") else ""
        source_name = getattr(event, "source_name", "")
        source_info = f"\nKaynak: {source_name}" if source_name else ""

        prompt = f"""Sen küresel piyasalar, teknoloji ve finans haberlerini özetleyen tarafsız bir ekonomi editörüsün.
Aşağıdaki gelişmeyi az, öz ve kurumsal kalitede özetle. Boş laf, basmakalıp dolgu cümleler ve uzun girişler YAZMA. Doğrudan kaynaktaki somut bilgiye odaklan. Türkçe yaz.
{NEUTRAL_RULES}

Gelişme Türü: {event.kind} (Kategori: {event.category})
Konu / Başlık: {event.headline}
{details_block}{macro_block}{source_info}

Şu formatta eksiksiz yanıt ver:

## ÖZET
Başlığı doğrudan KOPYALAMADAN, gelişmenin özünü 1-2 net cümlede (maksimum 160 karakter) özetle.

## ANALİZ
Aşağıdaki 3 bölümü yapılandırılmış markdown olarak hazırla (yalnızca kaynakta geçen bilgilerle):

### Gelişmenin Detayları
Olayın arka planı, ilgili şirketlerin veya aktörlerin rolleri ve kaynakta geçen somut veriler.

### Bağlam
Kaynakta açıklanan arka plan bilgisi (önceki benzer gelişmeler, ilgili düzenlemeler). Tahmin yapma.

### Açıklanan Sonraki Adımlar
Yalnızca kaynakta açıklanan tarihler ve süreç adımları. Kaynakta yoksa bu bölümü "Belirtilmemiş" olarak bırak.

## TWEET
260 karakter sınırını aşmayan, bilgi yoğun tek bir tarafsız tweet.
- Format: [Konu/Aktör] [ne yaptı/oldu].
- Varsa rakam/oran ekle.
- EMOJİ KULLANMA. Hashtag EKLEME. Yorum ekleme.
"""
        raw = self.client.generate(prompt, disable_thinking=True, task_type="analysis")
        if raw:
            return self._parse_event_analysis(raw, event)

        log.info("AI kapalı/başarısız; şablon piyasa olayı analizi üretiliyor: %s", event.headline[:60])
        return self._template_event_analysis(event, macro_context)

    @staticmethod
    def _parse_event_analysis(raw: str, event: "MarketEvent") -> tuple[str, str, str]:
        import re

        def _extract(section: str) -> str:
            pattern = rf"##\s*{re.escape(section)}\s*\n(.*?)(?=\n##\s|\Z)"
            m = re.search(pattern, raw, re.DOTALL | re.IGNORECASE)
            return m.group(1).strip() if m else ""

        summary = _extract("ÖZET")
        if not summary or summary.strip().lower() == event.headline.strip().lower():
            first_clause = event.headline.split('.')[0]
            summary = f"{first_clause}; sektör dinamikleri ve piyasa fiyatlamaları üzerindeki yansımaları takip ediliyor."

        analiz = _extract("ANALİZ") or _extract("ANALIZ") or raw.strip()

        # Başlığın gövde başında gereksiz H1/H2 olarak tekrarlanmasını engelle
        cleaned_body = re.sub(
            rf"^#{{1,3}}\s+{re.escape(event.headline)}\s*\n+", "", analiz, flags=re.IGNORECASE
        ).strip()

        # Deterministik son süzgeç: model kurala uymadıysa yasaklı içerik yayına gitmez.
        cleaned_body = strip_banned(cleaned_body)
        summary = strip_banned(summary) or event.headline.split('.')[0]
        tweet_raw = strip_banned(_extract("TWEET"))
        if not tweet_raw or len(tweet_raw.strip()) < 30:
            tweet_raw = f"{event.headline[:200]} — gelişmenin özeti raporda:"

        return cleaned_body, summary, tweet_raw

    @staticmethod
    def _template_event_analysis(event: "MarketEvent", macro_context: str = "") -> tuple[str, str, str]:
        """AI devre dışıyken veya başarısız olduğunda zengin, yapılandırılmış finansal analiz üretir."""
        details_clean = getattr(event, "details", "").strip()
        if details_clean and is_mostly_english(details_clean):
            details_clean = translate_to_turkish(details_clean)

        first_clause = event.headline.split('.')[0].rstrip(" ,;:")
        if is_mostly_english(first_clause):
            first_clause = ensure_turkish(first_clause) or first_clause

        if event.kind == "TEKNOLOJI_HAREKET":
            summary = f"{first_clause}; yapay zeka altyapısı, donanım talebi ve teknoloji hisseleri üzerindeki etkileriyle takip ediliyor."
            
            detay_metni = details_clean if details_clean else (
                f"{event.headline}. Yapay zeka ve yüksek teknoloji odaklı bu gelişme, küresel bilişim mimarisi "
                "ve kurumsal yazılım çözümlerinde yeni bir dönüşüm dalgasını temsil ediyor."
            )

            body = (
                f"### Gelişmenin Detayları\n"
                f"{detay_metni}\n\n"
                f"### Teknoloji & Yapay Zeka Ekosistemine Etkisi\n"
                f"Yapay zeka modellerinin hesaplama maliyetleri ve veri işleme ihtiyaçları katlanarak artarken, "
                f"yeni nesil çip tasarımları ve sunucu mimarileri teknoloji devlerinin sermaye harcamalarında (CapEx) "
                f"birinci sıraya yerleşmiş durumda. Söz konusu gelişme, donanım tedarik zinciri ve bulut bilişim "
                f"sağlayıcıları açısından takip edilen bir başlık.\n\n"
                f"### Takip Edilen Başlıklar\n"
                f"- Yeni mimari ve teknolojinin ticari pazara sunulma takvimi ile hacimli üretim metrikleri.\n"
                f"- Enerji verimliliği, soğutma sistemleri ve veri merkezi altyapı sınırlamalarına yönelik çözümler.\n"
                f"- Küresel regülasyon kurumlarının büyük teknoloji platformlarına yönelik rekabet ve yapay zeka standartları."
            )
            tweet = f"{first_clause} — gelişmenin özeti raporda:"

        elif event.kind == "KRIPTO_HAREKET":
            if event.change_pct != 0.0:
                direction = "yükselişle" if event.change_pct >= 0 else "düşüşle"
                sign = "+" if event.change_pct >= 0 else ""
                summary = f"{event.label} son 24 saatte %{sign}{event.change_pct:.2f} {direction} {event.value_str} seviyesinde."

                body = (
                    f"### Piyasa Hareketi\n"
                    f"{event.label} ({event.value_str}), son 24 saatte **%{sign}{event.change_pct:.2f}** "
                    f"oranında değişti.\n\n"
                    f"### Takip Edilen Başlıklar\n"
                    f"- ABD Merkez Bankası (Fed) faiz beklentileri ve küresel tahvil getirilerindeki yönelim.\n"
                    f"- Kurumsal saklama çözümleri ve regülatif adımlara ilişkin resmi açıklamalar."
                )
            else:
                summary = f"{first_clause}; dijital varlık ekosistemi ve kurumsal fon hareketleri üzerindeki etkileriyle izleniyor."
                detay_metni = details_clean if details_clean else (
                    f"{event.headline}. Dijital varlıklar ve blokzincir teknolojisi ekseninde yaşanan bu gelişme, "
                    "sektördeki kurumsal benimseme ve güvenlik standartları açısından kritik önem taşıyor."
                )
                body = (
                    f"### Haberin Detayları\n"
                    f"{detay_metni}\n\n"
                    f"### Dijital Varlıklar & Düzenleyici Etki\n"
                    f"Kripto para piyasalarında kurumsal güven, kullanıcı varlıklarının saklama güvencesi ve yasal düzenlemelere uyum "
                    f"ön planda kalmaya devam ediyor. Büyük platformların attığı stratejik adımlar piyasa likiditesini doğrudan belirliyor.\n\n"
                    f"### Piyasa Algısı & Likidite Yansıması\n"
                    f"Gelişmenin ardından majör kripto varlıklar ile altcoinlerdeki risk primi yeniden dengelenirken, "
                    f"türev piyasalardaki volatilite beklentileri ve fonlama oranları takip ediliyor.\n\n"
                    f"### Yakından İzlenecekler\n"
                    f"- İlgili kurum ve platformlardan gelecek resmi açıklamalar ve yasal süreçler.\n"
                    f"- Kripto varlık fon akımları ve borsa rezerv hareketleri."
                )
            tweet = f"{first_clause} — gelişmenin özeti raporda:"

        elif event.category == "gundem":
            summary = f"{first_clause}; Türkiye ekonomisi, makro dengeler ve piyasa fiyatlamaları üzerindeki yansımalarıyla izleniyor."
            detay_metni = details_clean if details_clean else (
                f"{event.headline}. Türkiye ekonomisi ve finansal piyasaları yakından ilgilendiren bu gelişme, "
                "makroekonomik istikrar ve piyasa beklentileri açısından önem taşıyor."
            )
            body = (
                f"### Gelişmenin Detayları\n"
                f"{detay_metni}\n\n"
                f"### Makroekonomik Etki & Politika Görünümü\n"
                f"Türkiye Cumhuriyet Merkez Bankası (TCMB) para politikası, dezenflasyon patikası ve mali disiplin hedefleri "
                f"doğrultusunda atılan adımlar, yurtiçi piyasalarda güven ortamı ve risk priminin (CDS) seyrini belirlemeyi sürdürüyor. "
                f"Söz konusu gelişme, makro dengelerin korunması açısından yakından değerlendiriliyor.\n\n"
                f"### Piyasa & TL Varlıkları Yansıması\n"
                f"Gelişmenin Türk Lirası varlıkları, Borsa İstanbul endeksleri ve tahvil faizleri üzerindeki seyri "
                f"yurtiçi ve yurtdışı yatırımcı algısı üzerinden takip ediliyor.\n\n"
                f"### Yakından İzlenecekler\n"
                f"- İlgili kamu otoriteleri ve regülatör kurumların yönlendirmeleri.\n"
                f"- Enflasyon, cari denge ve rezerv göstergelerindeki dönemsel gerçekleşmeler."
            )
            tweet = f"{first_clause} — Türkiye ekonomisi ve piyasa yansımaları değerlendirildi:"

        else:
            summary = f"{first_clause}; küresel piyasalardaki risk iştahı ve makro varlık fiyatlamaları üzerindeki yansımalarıyla değerlendiriliyor."
            detay_metni = details_clean if details_clean else (
                f"{event.headline}. Piyasaların yakından takip ettiği bu gelişme, varlık fiyatlamaları "
                "ve makroekonomik beklentiler üzerinde doğrudan etkili olma potansiyeli taşıyor."
            )
            body = (
                f"### Gelişmenin Detayları\n"
                f"{detay_metni}\n\n"
                f"### Makroekonomik Bağlam & Küresel Risk İştahı\n"
                f"Küresel enflasyon dinamikleri, merkez bankalarının para politikası patikası ve tahvil faizlerindeki dalgalanma, "
                f"uluslararası fon akımlarını yönlendiren temel unsurlar olmaya devam ediyor. Gelişmekte olan piyasalar "
                f"ve riskli varlıklar bu dalgalanmalardan öncelikli olarak etkileniyor.\n\n"
                f"### Piyasa & Varlık Yansıması\n"
                f"Gelişmenin küresel tahvil faizleri, emtia (altın, petrol) ve döviz kurları üzerindeki seyri Borsa İstanbul "
                f"ve Türk Lirası varlıkları açısından çarpan ve getiri arayışı üzerinden izleniyor.\n\n"
                f"### Yakından İzlenecekler\n"
                f"- Açıklanacak öncü makroekonomik göstergeler ve merkez bankası yönlendirmeleri.\n"
                f"- Küresel hisse senedi piyasalarında volatilite endekslerinin (VIX) seyri."
            )
            tweet = f"{first_clause} — küresel piyasalar ve makroekonomik yansımaları analiz edildi:"

        return strip_banned(body), strip_banned(summary) or first_clause, strip_banned(tweet) or first_clause

    def generate_breaking_news_tweet(self, headline: str, macro_context: str = "") -> tuple[str, str]:
        """Geriye dönük uyumluluk wrapper'ı: (tweet, body) ikilisi döner."""
        from ..sources.news_detector import MarketEvent
        event = MarketEvent(
            kind="SON_DAKIKA",
            label="Son Dakika",
            change_pct=0.0,
            value_str="",
            change_str="",
            headline=headline,
            key="",
        )
        body, _, tweet = self.generate_event_analysis(event, macro_context)
        return tweet, body

    def analyze_global_breaking_news(self, news_title: str) -> str | None:
        """Haber başlığını analiz edip çok önemliyse Türkçe SON DAKİKA başlığına çevirir.

        Kapsam: ekonomi, piyasalar, kripto, teknoloji/AI (piyasa etkisi olan) haberleri.
        Önemsiz haberler için None döner — AI prompt'u agresif filtreler.
        """
        if not self.client.enabled:
            return None

        prompt = f"""
Sen bir finansal haber masası şefisin. Aşağıdaki haber başlığını analiz et.

Bu haber aşağıdaki kategorilerden birinde DOĞRUDAN ve ÖNEMLİ bir gelişme mi?
1. Makro Ekonomi: Merkez bankası faiz kararları (FED, ECB, TCMB), enflasyon sürprizi, resesyon, savaş/jeopolitik kriz
2. Küresel Piyasalar: Büyük borsa çöküşü/rallisi, büyük şirket iflası/satın alması, S&P500/NASDAQ/BIST sert hareketi
3. Kripto: Bitcoin/ETH sert hareket, büyük exchange çöküşü/hack, ülke yasağı/kabulü, balina hareketi
4. Teknoloji/AI (Piyasa Etkisi): Yeni büyük AI modeli lansmanı (GPT-5, Claude 4 vb.), çip/yarı iletken krizi, büyük tech şirketi satın alması, NVIDIA/AMD/TSMC önemli haberi, veri merkezi yatırımı/krizi
5. Türkiye Ekonomisi: TCMB kararı, enflasyon verisi, döviz krizi, büyük şirket haberi

Eğer haber yukarıdaki kategorilerden birinde SÜRPRIZ, ÖNEMLİ ve DOĞRUDAN ETKİ YARATABİLECEK bir gelişmeyse:
→ Türkçe, kısa (max 120 karakter), çok vurucu ve bilgi yoğun bir başlık yaz. "SON DAKİKA: " ile başla.

Eğer haber sıradan bir analiz, rutin güncelleme, tahmin raporu, ikincil bir gelişme veya yukarıdaki kategorilerle ilgisizse:
→ Sadece "NO" yaz.

Haber Başlığı: {news_title}
"""
        result = self.client.generate(prompt, disable_thinking=True, task_type="filter")
        if not result:
            return None
        first_line = result.strip().split("\n")[0].strip().upper()
        if first_line == "NO" or first_line.startswith("NO ") or first_line.startswith("NO."):
            return None

        # Temizle
        result = result.strip().strip('"').strip("'")
        clean_text = result.removeprefix("SON DAKİKA:").removeprefix("SON DAKIKA:").strip()
        if is_mostly_english(clean_text):
            clean_text = translate_to_turkish(clean_text)
            if not clean_text or is_mostly_english(clean_text):
                return None
        return f"SON DAKİKA: {clean_text}"

    def generate_news_analysis(
        self,
        title: str,
        disclosure_type: str,
        company: str,
        ticker: str,
        raw_text: str,
        is_insider: bool = False,
        macro_context: str = "",
        sector_context: str = "",
        disclosure_index: str = "",
    ) -> tuple[str, str, str]:
        """KAP bildirimi için tarafsız ÜRETİLMİŞ özet: bildirimde NE açıklandı.

        Döndürür: (generated_body, summary_line, tweet_text). Hepsi tarafsız dil süzgecinden geçmiştir.
        Birebir bilgi bloğu (başlık, şirket, tür, tutarlar, bağlantı) burada DEĞİL, çağıran tarafta
        ``filing_facts_markdown`` ile ayrıca eklenir ve süzülmez.

        AI kapalı/başarısızsa yorum üretilmez: gövde boş, özet ve tweet KAP başlığının kendisidir.
        ``macro_context``/``sector_context``/``is_insider``/``disclosure_index`` geriye dönük uyumluluk içindir.
        """
        code = f" ({ticker})" if ticker else ""
        prompt = f"""Sen bir KAP (Kamuyu Aydınlatma Platformu) bildirimi özetleyicisisin. Görevin bildirimde NE açıklandığını sade ve tarafsız Türkçe ile aktarmak.
{NEUTRAL_RULES}
Şirket: {company}{code}
Bildirim türü: {disclosure_type}
Başlık: {title}
Bildirim içeriği:
{raw_text or title}

Şu formatta yanıt ver (kısa ve somut maddeler):

## ÖZET
Tek cümle (max 140 karakter): kim, neyi açıkladı. Bildirimde tutar/oran varsa birimiyle ekle.

## BİLDİRİM
- **Ne açıklandı:** Bildirimdeki ifadelere sadık 1-2 cümle.
- **Taraflar:** Bildirimde geçen şirket/kişi/kurumlar; yoksa "Belirtilmemiş".
- **Tutar / oran:** Bildirimde geçtiği şekliyle ve neyin tutarı olduğu; yoksa "Belirtilmemiş".
- **Tarihler:** Bildirimde geçen tarih ve süreler; yoksa "Belirtilmemiş".
- **Açıklanan sonraki adım:** Yalnızca bildirimde yazan süreç adımı (ör. SPK onayı, genel kurul); yoksa "Belirtilmemiş".

## TWEET
260 karakteri aşmayan tek, tarafsız cümle: [Şirket] [ne açıkladı]. Varsa tutarı birimiyle ekle.
- EMOJİ KULLANMA. Hashtag EKLEME. Yorum ekleme.
"""
        raw = self.client.generate(prompt, disable_thinking=True, task_type="analysis")
        if raw:
            return self._parse_news_analysis(raw, title, company, ticker, is_insider)
        log.info("AI kapalı/başarısız; yorum üretilmiyor, yalın KAP bilgisi yayınlanacak.")
        return self._template_news_analysis(title, disclosure_type, company, ticker, is_insider, raw_text=raw_text)

    # ---- yardımcılar (generate_news_analysis) ----------------------------------

    @staticmethod
    def _parse_news_analysis(
        raw: str, title: str, company: str, ticker: str, is_insider: bool
    ) -> tuple[str, str, str]:
        """AI çıktısını (generated_body, summary, tweet) üçlüsüne dönüştürür ve yasaklı içeriği süzer.

        Özet süzgece takılır/boş kalırsa KAP başlığı (birebir) kullanılır."""
        import re

        def _extract(section: str) -> str:
            pattern = rf"##\s*{re.escape(section)}\s*\n(.*?)(?=\n##\s|\Z)"
            m = re.search(pattern, raw, re.DOTALL | re.IGNORECASE)
            return m.group(1).strip() if m else ""

        summary = strip_banned(_extract("ÖZET")) or title
        tweet = strip_banned(_extract("TWEET"))
        if not tweet or len(tweet.strip()) < 30 or tweet.strip().lower() == title.strip().lower():
            tweet = summary
        if len(tweet) > 230 and tweet != title:
            tweet = tweet[:230].rsplit(" ", 1)[0].rstrip(" ,.;:") + "…"

        detail = strip_banned(
            _extract("BİLDİRİM") or _extract("BILDIRIM") or _extract("ANALİZ") or _extract("ANALIZ")
        )
        parts = []
        if summary != title:
            parts.append(f"### Özet\n{summary}")
        if detail:
            parts.append(f"### Bildirim Özeti\n{detail}")
        return "\n\n".join(parts), summary, tweet

    @staticmethod
    def _template_news_analysis(
        title: str,
        disclosure_type: str,
        company: str,
        ticker: str,
        is_insider: bool,
        raw_text: str = "",
        disclosure_index: str = "",
    ) -> tuple[str, str, str]:
        """AI yokken yorum üretilmez: gövde boş; özet ve tweet KAP başlığının kendisi (birebir)."""
        return "", title, title

    @staticmethod
    def generate_sector_movement_analysis(
        sector_name: str, change_pct: float, headline: str, macro_context: str = ""
    ) -> tuple[str, str, str]:
        """BIST sektör endeksi hareketi için yalnızca veriyi aktaran kısa metin (yorum yok)."""
        pct = f"%{change_pct:+.2f}".replace(".", ",")
        summary = f"BIST {sector_name} endeksi son verilere göre {pct} değişti."
        body = (
            f"### Endeks Verisi\n"
            f"- **Endeks:** BIST {sector_name}\n"
            f"- **Değişim:** {pct}\n"
            f"- **Kaynak:** Borsa İstanbul endeks verisi (gecikmeli olabilir)"
        )
        tweet = f"BIST {sector_name} endeksi son verilere göre {pct} değişti. Endeks verisi raporda:"
        return body, summary, tweet

    def generate_morning_report_and_thread(
        self, snapshot: MarketSnapshot
    ) -> tuple[str, bool, list[str]]:
        """Sabah bültenini VE tweet thread'ini tek AI çağrısında üretir.

        Rate limit sorununu önlemek için rapor + thread tek prompt'ta istenir,
        ardından parse edilir.

        Döndürür: (body_markdown, ai_used, tweets)
        """
        from datetime import datetime, timedelta, timezone
        import re

        today = datetime.now(timezone(timedelta(hours=3)))
        date_str = today.strftime("%d.%m.%Y")
        context = self._snapshot_context(snapshot)

        has_macro = snapshot.macro is not None and bool(snapshot.macro.tickers)
        has_viop = snapshot.viop_quote is not None
        has_sector = bool(snapshot.sector)
        has_kap = bool(snapshot.disclosures)
        has_calendar = bool(snapshot.calendar)

        sections: list[str] = ["Genel Görünüm (BIST endeksi, genel tablo)"]
        if has_macro:
            sections.append("Küresel Piyasalar (ABD 10Y faiz, EUR/USD, Altın, VIX, Brent — BIST etkisini yorumla)")
        if has_viop:
            sections.append("VİOP & Türev Piyasa (endeks/vadeli fiyat, teminat stresi)")
        if has_sector:
            sections.append("Sektör Rotasyonu (güçlü ve zayıf sektörler, para akışı)")
        if has_kap:
            sections.append("KAP Öne Çıkanlar (önemli bildirimler; içsel işlem varsa vurgula)")
        if has_calendar:
            sections.append("Ekonomik Takvim (bugünün kritik veri açıklamaları)")
        sections.append("Özet (yalnızca yukarıdaki verilerin kısa özeti; tahmin ve görüş yok)")
        sections_text = "\n".join(f"  {i+1}. {s}" for i, s in enumerate(sections))

        prompt = f"""Sen tarafsız bir piyasa veri editörüsün. \
{date_str} sabahı için kurumsal kalitede, veri odaklı bir piyasa bülteni ve Twitter thread'i yaz. \
Türkçe yaz. Yer tutucu (köşeli parantez içi metin) KULLANMA.
{NEUTRAL_RULES}

=== BÖLÜM A: SABAH BÜLTENİ (RAPOR) ===
Markdown formatında (## başlıklar, madde listeleri, kalın vurgular). \
Her bölümü en az 4-5 cümleyle doyurucu biçimde doldur. \
Verileri bağlamıyla ver (dünkü değer, haftalık değişim gibi) ama tahmin ve görüş ekleme. \
En üste ## başlık KOYMA (dışarıdan eklenecek).

Bölümler (sırayla, her birini tam doldur):
{sections_text}

Yazım kuralları:
- Her bölüm kendi içinde eksiksiz olmalı; okuyucu bölümü atlayabilmeli
- Rakamları bağlam içinde ver (örn: "XU100 %1,2 geriledi — Mart'tan bu yana en büyük günlük düşüş")
- Sektör verisi varsa en çok yükselen ve düşen sektörleri rakamlarıyla listele
- KAP bildirimi varsa bildirimde ne açıklandığını bir cümleyle aktar
- Ekonomik takvim varsa açıklanacak veriyi ve (varsa) beklenti değerini belirt

=== BÖLÜM B: TWITTER THREAD ===
6 tweet'lik thread. Her tweet tam bağımsız okunabilir ve değer katmalı.
- Her tweet max 260 karakter
- Her tweet farklı bir konuyu ele alsın (BIST, küresel, sektör, KAP, takvim, özet)
- Rakam/oran/yüzde içermeli — soyut ifadeden kaçın
- Birinci tweet en vurucu "hook" olsun — günün en önemli gelişmesini tek cümlede ver
- Son tweet günün özeti + soru olsun (etkileşim için)
- EMOJİ KULLANMA. Hashtag EKLEME.

Format (kesinlikle bu şablonu kullan, başka metin ekleme):
TWEET 1: [metin]
TWEET 2: [metin]
TWEET 3: [metin]
TWEET 4: [metin]
TWEET 5: [metin]
TWEET 6: [metin]

=== PİYASA VERİLERİ ===
{context}

Çıktı formatı (başka hiçbir şey ekleme, sadece bu iki bölüm):
---RAPOR---
[bülten metni buraya — markdown]
---THREAD---
TWEET 1: [metin]
TWEET 2: [metin]
TWEET 3: [metin]
TWEET 4: [metin]
TWEET 5: [metin]
TWEET 6: [metin]
"""
        raw = self.client.generate(prompt, disable_thinking=True, task_type="analysis")
        if not raw:
            log.info("AI kapalı/başarısız; şablon sabah raporu üretiliyor.")
            body = self._template_morning_report(snapshot)
            tweets = self._fallback_tweets(snapshot)
            return body, False, tweets

        # --- Rapor bölümünü parse et ---
        report_match = re.search(r"---RAPOR---\s*(.*?)(?=---THREAD---|$)", raw, re.DOTALL)
        body = strip_banned(report_match.group(1).strip() if report_match else raw.strip())
        if not body:
            body = self._template_morning_report(snapshot)

        # --- Thread bölümünü parse et ---
        thread_match = re.search(r"---THREAD---\s*(.*?)$", raw, re.DOTALL)
        thread_raw = thread_match.group(1).strip() if thread_match else raw

        tweet_pattern = r"TWEET\s+\d+:\s*(.+?)(?=TWEET\s+\d+:|$)"
        matches = re.findall(tweet_pattern, thread_raw, re.DOTALL | re.IGNORECASE)
        tweets = [strip_banned(m.strip())[:280] for m in matches if m.strip()]
        tweets = [t for t in tweets if t]

        if len(tweets) < 3:
            tweets = self._fallback_tweets(snapshot)

        return body, True, tweets[:7]

    def generate_morning_report(self, snapshot: MarketSnapshot) -> tuple[str, bool]:
        """Sadece rapor üretir (eski uyumluluk). Thread gerekmiyorsa bunu kullan."""
        body, ai_used, _ = self.generate_morning_report_and_thread(snapshot)
        return body, ai_used

    def generate_morning_thread(self, snapshot: MarketSnapshot) -> list[str]:
        """Sadece thread üretir. generate_morning_report_and_thread kullanılması önerilir."""
        _, _, tweets = self.generate_morning_report_and_thread(snapshot)
        return tweets

    def _fallback_tweets(self, snapshot: MarketSnapshot) -> list[str]:
        """AI başarısız olduğunda snapshot verisiyle deterministik tweet listesi üretir."""
        b = snapshot.bist
        index = b.index if b else "XU100"
        price = b.price if b else "—"
        change = b.change if b else "—"

        tweets = [
            f"BIST {index} bugün {price} seviyesinde, {change} değişimle açıldı. Sabah bülteni hazır.",
        ]
        if snapshot.macro and snapshot.macro.tickers:
            macro_bits = []
            for t in snapshot.macro.tickers[:3]:
                macro_bits.append(f"{t.label}: {t.value_str}")
            tweets.append("Küresel piyasalar: " + " | ".join(macro_bits))
        if snapshot.turib and snapshot.turib.hububat_index:
            h = snapshot.turib.hububat_index
            sign = "+" if h.change_pct >= 0 else ""
            tweets.append(f"TÜRİB Hububat: {h.price} ({sign}{h.change_pct}%). Tarımsal emtia özeti bültende.")

        if snapshot.sector:
            top = sorted(snapshot.sector, key=lambda s: abs(float(s.change_pct or 0)), reverse=True)[:2]
            sector_bits = [f"{s.name} {s.change_pct:+.1f}%" for s in top if hasattr(s, "change_pct")]
            if sector_bits:
                tweets.append("Öne çıkan sektörler: " + ", ".join(sector_bits))
        tweets.append(f"Detaylı sabah raporu web sitesinde. Bugün piyasayı ne yönlendirir sizce?")
        return tweets

    def generate_global_report(self, macro_snapshot: str) -> tuple[str, str]:
        """Küresel makro verilerini alıp detaylı bir AI raporu ve tweet üretir.
        Döndürür: (body_markdown, tweet_text)
        """
        prompt = f"""
Sen tarafsız bir küresel piyasalar veri editörüsün. Aşağıdaki güncel küresel makro
verilerini özetleyen kısa ve profesyonel bir bülten yaz. S&P 500, DAX gibi ana
endekslerdeki, tahvil faizlerindeki, kurlardaki ve emtialardaki değişimleri rakamlarıyla aktar.
{NEUTRAL_RULES}
Veriler:
{macro_snapshot}

Şu formatta yanıt ver:

## GÖRÜNÜM
[Verilerin 2-3 cümlelik özeti]

## ÖNE ÇIKAN GELİŞMELER
- **ABD ve Avrupa Endeksleri:** [Veri]
- **Tahvil ve Döviz:** [Veri]
- **Emtia (Altın/Petrol) & VIX:** [Veri]

## TWEET
280 karakter hedefli, tarafsız bir tweet. Kurallar:
- En büyük makro hareketi rakamıyla ver.
- Tarihsel bağlam ekle (örn: "Son 3 ayın en yüksek X değeri").
- Tahmin ve yorum ekleme.
- EMOJİ KULLANMA, hashtag EKLEME.
"""
        raw = self.client.generate(prompt, task_type="analysis")
        if raw:
            import re
            def _extract(section: str) -> str:
                pattern = rf"##\s*{re.escape(section)}\s*\n(.*?)(?=\n##\s|\Z)"
                m = re.search(pattern, raw, re.DOTALL | re.IGNORECASE)
                return m.group(1).strip() if m else ""
                
            tweet = strip_banned(_extract("TWEET"))
            body_sections = []
            for sec in ("GÖRÜNÜM", "ÖNE ÇIKAN GELİŞMELER"):
                content = strip_banned(_extract(sec))
                if content:
                    body_sections.append(f"## {sec.title()}\n\n{content}")
            body = "\n\n".join(body_sections) if body_sections else strip_banned(raw)
            return body, tweet

        log.info("AI kapalı/başarısız; şablon makro raporu üretilecek.")
        return "", ""

    def analyze_balance_sheet_red_flags(self, financial_data_text: str) -> str:
        prompt = f"""
Aşağıdaki finansal tablo özetini/dipnotlarını incele. Şirketin finansal sağlığı,
büyüme potansiyeli ve riskleriyle ilgili küçük yatırımcının gözden kaçırabileceği,
ancak profesyonellerin dikkat edeceği derinlemesine bir analiz yap.

Şu formatta yanıt ver:
- **[Olumlu Nokta Başlığı]:** [Neden önemli olduğu, şirkete gelecekteki katkısı ve rakamsal/oransal değerlendirmesi (2-3 cümle)] (En az 3 adet)
- **[Risk / Olumsuz Nokta]:** [Bilanço dipnotlarında veya nakit akışında yatan sinsi risk, operasyonel baskı veya borç yükü analizi (2-3 cümle)] (En az 3 adet)

Veri: {financial_data_text}
"""
        return self.client.generate(prompt, task_type="analysis") or "Analiz şu an üretilemedi."

    # ---- yardımcılar -----------------------------------------------------------

    @staticmethod
    def _snapshot_context(snapshot: MarketSnapshot) -> str:
        lines: list[str] = []

        # BIST
        if snapshot.bist:
            b = snapshot.bist
            lines.append(f"- BIST {b.index}: {b.price} ({b.change}), hacim {b.volume}")

        # Küresel makro
        if snapshot.macro and snapshot.macro.tickers:
            lines.append("\n### Küresel Makro")
            for t in snapshot.macro.tickers:
                lines.append(f"- {t.label}: {t.value_str} ({t.change_str})")

        # VİOP kotasyonu
        if snapshot.viop_quote:
            q = snapshot.viop_quote
            lines.append("\n### VİOP")
            lines.append(f"- {q.index_symbol}: {q.index_price} ({q.index_change})")
            if q.has_futures:
                lines.append(
                    f"- {q.futures_symbol} Vadeli: {q.futures_price} ({q.futures_change or '—'})"
                    + (f", hacim {q.futures_volume}" if q.futures_volume else "")
                )

        # VİOP teminat stresi
        if snapshot.viop_margin:
            m = snapshot.viop_margin
            lines.append(
                f"- Teminat stresi: margin-call/gereken = %{m.margin_call_to_required_pct:.3f}"
                f" (margin-call toplam: {m.margin_call_pretty()})"
            )

        # Sektör rotasyonu (en güçlü 3 + en zayıf 3)
        if snapshot.sector:
            leaders = [s for s in snapshot.sector[:3]]
            laggards = [s for s in snapshot.sector[-3:]]
            lines.append("\n### Sektör Rotasyonu")
            lines.append("Güçlü: " + ", ".join(f"{s.name} ({s.change_str})" for s in leaders))
            lines.append("Zayıf: " + ", ".join(f"{s.name} ({s.change_str})" for s in laggards))

        # TÜRİB ELÜS (Tarımsal Emtia & Hububat)
        if snapshot.turib:
            t = snapshot.turib
            lines.append("\n### TÜRİB ELÜS (Tarımsal Emtia)")
            if t.hububat_index:
                sign = "+" if t.hububat_index.change_pct >= 0 else ""
                lines.append(f"- TÜRİB Hububat Endeksi (TRBHUB): {t.hububat_index.price} ({sign}{t.hububat_index.change_pct}%)")
            for p in t.products:
                sign = "+" if p.change_pct >= 0 else ""
                lines.append(f"- {p.product}: {p.avg_price_tl_kg} TL/kg ({sign}{p.change_pct}%), hacim: {p.volume_kg/1000.0:.1f} Ton")

        # Ekonomik takvim (en fazla 5 kritik olay)
        if snapshot.calendar:
            lines.append("\n### Ekonomik Takvim")
            for ev in snapshot.calendar[:5]:
                lines.append(
                    f"- {ev.time} {ev.country}: {ev.event}"
                    f" (önem: {ev.importance}, beklenti: {ev.forecast})"
                )

        # KAP bildirimleri (en fazla 10 — prompt boyutunu kontrol altında tut)
        if snapshot.disclosures:
            lines.append("\n### KAP Bildirimleri (öne çıkanlar)")
            for d in snapshot.disclosures[:10]:
                insider_flag = " [İÇSEL]" if d.is_insider else ""
                lines.append(f"- {d.title[:80]} [{d.disclosure_type}]{insider_flag}")

        return "\n".join(lines) or "- Veri bulunamadı."

    @staticmethod
    def _template_morning_report(snapshot: MarketSnapshot) -> str:
        b = snapshot.bist
        header = "## Genel Görünüm\n\n"
        if b:
            header += (
                f"BIST {b.index} son işlemde **{b.price}** seviyesinde ({b.change}), "
                f"hacim {b.volume}.\n\n"
            )
        else:
            header += "Endeks verisi şu an alınamadı.\n\n"

        # Küresel makro tablosu
        macro_sec = ""
        if snapshot.macro and snapshot.macro.tickers:
            macro_sec = "## Küresel Makro\n\n" + snapshot.macro.to_markdown_table() + "\n\n"

        cal = "## Ekonomik Takvim\n\n"
        if snapshot.calendar:
            cal += "| Saat | Ülke | Olay | Beklenti |\n| --- | --- | --- | --- |\n"
            for ev in snapshot.calendar:
                cal += f"| {ev.time} | {ev.country} | {ev.event} | {ev.forecast} |\n"
            cal += "\n"
        else:
            cal += "Bugün için öne çıkan veri bulunmuyor.\n\n"

        # TÜRİB ELÜS Tarımsal Emtia bölümü
        turib_sec = ""
        if snapshot.turib and snapshot.turib.summary_text:
            turib_sec = f"## TÜRİB ELÜS Tarımsal Emtia\n\n{snapshot.turib.summary_text}\n\n"

        # VİOP bölümü
        viop_sec = ""
        if snapshot.viop_quote:
            q = snapshot.viop_quote
            viop_sec = (
                f"## VİOP\n\n"
                f"{q.index_symbol}: **{q.index_price}** ({q.index_change})"
            )
            if q.has_futures:
                viop_sec += f" | Vadeli {q.futures_symbol}: {q.futures_price} ({q.futures_change or '—'})"
            viop_sec += "\n\n"

        # Sektör bölümü
        sector_sec = ""
        if snapshot.sector:
            leaders = ", ".join(
                f"{s.name} ({s.change_str})" for s in snapshot.sector[:3]
            )
            laggards = ", ".join(
                f"{s.name} ({s.change_str})" for s in snapshot.sector[-3:]
            )
            sector_sec = (
                f"## Sektör Rotasyonu\n\n"
                f"- **Güçlü:** {leaders}\n"
                f"- **Zayıf:** {laggards}\n\n"
            )

        kap = ""
        if snapshot.disclosures:
            kap = "## KAP Öne Çıkanlar\n\n"
            for d in snapshot.disclosures:
                kap += f"- **{d.title}** — {d.disclosure_type}\n"
            kap += "\n"

        footer = (
            "## Not\n\n"
            "Bu bülten kamuya açık piyasa verilerinden otomatik olarak derlenmiştir; "
            "yatırım tavsiyesi değildir."
        )
        return header + macro_sec + turib_sec + cal + viop_sec + sector_sec + kap + footer
