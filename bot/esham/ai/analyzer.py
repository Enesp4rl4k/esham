"""Gemini tabanlı analiz ve içerik üretimi.

Tasarım ilkeleri:
- API anahtarı yoksa AI devre dışı kalır ama pipeline çökmemesi için deterministik
  şablon üretimine düşülür (graceful degradation).
- Ağ/model hataları yakalanır ve loglanır (LlmClient içinde).
"""
from __future__ import annotations

from ..config import get_logger, settings
from ..sources import MarketSnapshot
from .client import LlmClient

log = get_logger(__name__)


class MarketAIAnalyzer:
    def __init__(self) -> None:
        # Sabah bülteni 4-5 bölümden oluşur; 2048 token Gemini 2.5'in thinking
        # bütçesini de kapsadığında yetmiyordu. 8192'ye çıkarıldı.
        self.client = LlmClient(settings.gemini_model, max_output_tokens=8192, temperature=0.4)
        if not self.client.enabled:
            log.warning("AI devre dışı; şablon üretimi kullanılacak.")

    def analyze_macro_impact(self, news_text: str) -> str:
        prompt = f"""
Sen profesyonel ve öngörülü bir portföy yöneticisisin. Aşağıdaki makroekonomik
gelişmeyi oku ve bunun Borsa İstanbul (BIST), ons altın ve kripto paralar üzerindeki
olası etkilerini çok kısa, net ve anlaşılır bir dille (yatırım tavsiyesi vermeden)
özetle.

Haber: {news_text}
"""
        return self.client.generate(prompt, task_type="analysis") or "Yapay zeka yorumu şu an üretilemedi."

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

        prompt = f"""Sen küresel piyasalar, teknoloji ve finans alanında uzmanlaşmış kıdemli bir ekonomi analisti ve piyasa stratejistisin.
Aşağıdaki gelişmeyi az, öz, derinlikli ve kurumsal kalitede analiz et. Boş laf, basmakalıp dolgu cümleler ve uzun girişler YAZMA. Doğrudan somut bilgiye, sektör etkisine ve piyasa verilerine odaklan. Türkçe yaz. Yatırım tavsiyesi verme.

Gelişme Türü: {event.kind} (Kategori: {event.category})
Konu / Başlık: {event.headline}
{details_block}{macro_block}{source_info}

Şu formatta eksiksiz yanıt ver:

## ÖZET
Başlığı doğrudan KOPYALAMADAN, gelişmenin özünü ve piyasa/sektör açısından neden kritik olduğunu 1-2 net cümlede (maksimum 160 karakter) özetle.

## ANALİZ
Aşağıdaki 4 bölümü yapılandırılmış markdown olarak hazırla (her bölüm en az 2-3 doyurucu ve somut cümle içermeli):

### Gelişmenin Detayları
Olayın arka planı, teknik/finansal özellikleri, ilgili şirketlerin veya aktörlerin rolleri ve somut veriler.

### Sektörel & Stratejik Etki
Gelişmenin ilgili ekosisteme etkisi (Yapay Zeka/Teknoloji için: bilgi işlem kapasitesi, çip talebi, veri merkezi yatırımları; Kripto için: likidite, regülasyon, ağ aktivitesi, faiz etkisi; Makro için: küresel faizler, sermaye akımları, risk iştahı).

### Piyasa & Varlık Yansıması
İlgili varlık sınıfları (teknoloji hisseleri, BIST Teknoloji endeksi, Bitcoin/altcoinler, döviz/tahvil piyasaları) üzerindeki fiyatlama ve risk algısı yansıması.

### Yakından İzlenecekler
Önümüzdeki gün ve haftalarda takip edilecek somut katalizörler, direnç/destek seviyeleri veya beklenen yeni adımlar.

## TWEET
260 karakter sınırını aşmayan, bilgi yoğun tek bir tweet.
- Format: [Konu/Aktör] [ne yaptı/oldu] — bu [neden önemli/etkisi ne] demek.
- Varsa rakam/oran ekle.
- EMOJİ KULLANMA. Hashtag EKLEME.
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

        tweet_raw = _extract("TWEET")
        if not tweet_raw or len(tweet_raw.strip()) < 30:
            tweet_raw = f"{event.headline[:200]} — piyasalar ve sektör üzerindeki etkileri analiz edildi:"

        return cleaned_body, summary, tweet_raw

    @staticmethod
    def _template_event_analysis(event: "MarketEvent", macro_context: str = "") -> tuple[str, str, str]:
        """AI devre dışıyken veya başarısız olduğunda zengin, yapılandırılmış finansal analiz üretir."""
        details_clean = getattr(event, "details", "").strip()
        first_clause = event.headline.split('.')[0].rstrip(" ,;:")

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
                f"sağlayıcıları açısından kritik bir dönüm noktası olarak değerlendiriliyor.\n\n"
                f"### Finansal Piyasalar & Hisse Yansıması\n"
                f"Teknoloji şirketlerinin inovasyon hamleleri Nasdaq teknoloji endeksi başta olmak üzere yarı iletken üreticileri "
                f"ve veri merkezi sağlayıcılarının çarpanlarını doğrudan destekliyor. Gelişmeler küresel risk iştahı kanalıyla "
                f"Borsa İstanbul Teknoloji Endeksi (XUTEK) hisseleri üzerinde de pozitif sektörel çarpan algısını besliyor.\n\n"
                f"### Yakından İzlenecekler\n"
                f"- Yeni mimari ve teknolojinin ticari pazara sunulma takvimi ile hacimli üretim metrikleri.\n"
                f"- Enerji verimliliği, soğutma sistemleri ve veri merkezi altyapı sınırlamalarına yönelik çözümler.\n"
                f"- Küresel regülasyon kurumlarının büyük teknoloji platformlarına yönelik rekabet ve yapay zeka standartları."
            )
            tweet = f"{first_clause} — yapay zeka altyapısı ve küresel teknoloji piyasalarına etkileri analiz edildi:"

        elif event.kind == "KRIPTO_HAREKET":
            if event.change_pct != 0.0:
                direction = "yükselişle" if event.change_pct >= 0 else "düşüşle"
                sign = "+" if event.change_pct >= 0 else ""
                summary = f"{event.label} son 24 saatte %{sign}{event.change_pct:.2f} {direction} {event.value_str} seviyesinde; kaldıraçlı piyasalarda volatilite öne çıkıyor."
                
                body = (
                    f"### Piyasa Hareketi & Anlık Fiyatlama\n"
                    f"{event.label} ({event.value_str}), son 24 saatlik seansta **%{sign}{event.change_pct:.2f}** "
                    f"oranında hareket ederek kripto varlık piyasasında yön arayışına öncülük etti. Türev borsalarda açık pozisyon (OI) "
                    f"ve fonlama oranlarındaki dalgalanma volatiliteyi artırıyor.\n\n"
                    f"### Kripto Dinamikleri & Likidite Akışı\n"
                    f"Spot kripto ETF'lerine yönelik kurumsal para giriş/çıkışları, büyük cüzdanların (balina) transfer hareketleri ve "
                    f"stabilcoin rezervlerindeki değişimler piyasa derinliğini belirlemeyi sürdürüyor. Makro faiz patikası ve Dolar Endeksi (DXY) "
                    f"kripto paralar üzerindeki genel risk iştahını şekillendiren temel faktör konumunda.\n\n"
                    f"### Kritik Seviyeler & Destek / Direnç\n"
                    f"- **Psikolojik Eşik:** {event.value_str} çevresinde yoğunlaşan alım ve satım kademeleri.\n"
                    f"- **Türev Piyasalar:** Tasfiye (liquidation) haritalarında long/short pozisyon dengesizliği.\n"
                    f"- **Momentum:** Günlük RSI ve hareketli ortalama (20/50 günlük) trend bantları.\n\n"
                    f"### Yakından İzlenecekler\n"
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
            tweet = f"{first_clause} — kripto para piyasalarındaki likidite ve fiyat yansıması analiz edildi:"

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

        return body, summary, tweet

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
        if result.upper().startswith("SON DAKİKA:"):
            return result
        return f"SON DAKİKA: {result}"

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
    ) -> tuple[str, str, str]:
        """KAP bildirimi veya anlık gelişme için kısa analiz raporu üretir.

        Döndürür: (body_markdown, summary_line, tweet_text)
        - body_markdown : web raporuna yazılacak markdown gövde
        - summary_line  : tek cümlelik özet (liste/OG description için)
        - tweet_text    : sosyal medya paylaşımı için kısa metin (280 karakter hedef)

        Graceful degradation: AI kapalı/başarısızsa deterministik şablon döner.
        """
        insider_note = "Bu bir içsel bildirimdir (insider trading şüphesi olabilir).\n" if is_insider else ""
        macro_block = f"\nGüncel makro bağlam:\n{macro_context}" if macro_context else ""
        sector_block = f"\nSektör bağlamı:\n{sector_context}" if sector_context else ""

        if is_insider:
            insider_prompt_extra = """
ÖNEMLİ — Bu bir İÇSEL İŞLEM bildirimidir:
- Alım mı satım mı olduğunu net belirt (alım = yönetim güveni sinyali / satım = olası çıkış sinyali)
- Kim yapıyor? (YK üyesi, CEO, büyük ortak) — pozisyon ne kadar önemli?
- Tutar/lot büyüklüğüne dikkat — sembolik mi, yoksa agresif mi?
- İçsel bilgiye sahip kişinin bu hareketi şirketin yakın dönem görünümü hakkında ne söylüyor?
- BIST'teki emsal içsel işlemlerle karşılaştır (varsa bağlam ver)
"""
        else:
            insider_prompt_extra = ""

        prompt = f"""Sen deneyimli bir Türk sermaye piyasaları analistisin. Az, öz, doğrudan sonuca odaklı hap bilgi kalitesinde analiz yap. Boş laf, uzun giriş cümleleri ve dolgu paragraflar YAZMA. Türkçe yaz. Yatırım tavsiyesi verme.
{insider_prompt_extra}
Şirket: {company} ({ticker})
Bildirim türü: {disclosure_type}
Başlık: {title}
Bildirim içeriği:
{raw_text or title}
{macro_block}{sector_block}

Şu formatta yanıt ver (uzun paragraflar yazma, doğrudan net ve somut maddeler ver):

## ÖZET
Tek cümle (max 140 karakter). Varsa sayısal veriyi (tutar, oran, lot, yüzde) dahil et.

## ANALİZ
**Finansal Sinyal:** Pozitif / Nötr / Negatif (hangisi uygunsa birini seç)

- **Gelişmenin Özü:** Haberin şirket için ne anlama geldiği (1 net cümle).
- **Finansal & Bilanço Etkisi:** Gelir, ciro, kâr marjı veya nakit akışına somut etkisi (1 net cümle).
- **Piyasa & Hisse Yansıması:** Hisse fiyatlaması veya yatırımcı açısından oluşturduğu katalizör (1 net cümle).

## TWEET
280 karakter sınırını aşmayan, bilgi yoğun tek bir tweet.
- Format: [Şirket] [ne yaptı] — bu [önemi/etkisi] demek.
- Varsa rakam/tutar ekle.
- EMOJİ KULLANMA. Hashtag EKLEME.
"""
        raw = self.client.generate(prompt, disable_thinking=True, task_type="analysis")
        if raw:
            return self._parse_news_analysis(raw, title, company, ticker, is_insider)

        log.info("AI kapalı/başarısız; şablon haber analizi üretiliyor.")
        return self._template_news_analysis(title, disclosure_type, company, ticker, is_insider, raw_text=raw_text)

    # ---- yardımcılar (generate_news_analysis) ----------------------------------

    @staticmethod
    def _parse_news_analysis(
        raw: str, title: str, company: str, ticker: str, is_insider: bool
    ) -> tuple[str, str, str]:
        """AI çıktısını (body, summary, tweet) üçlüsüne dönüştürür."""
        import re

        def _extract(section: str) -> str:
            pattern = rf"##\s*{re.escape(section)}\s*\n(.*?)(?=\n##\s|\Z)"
            m = re.search(pattern, raw, re.DOTALL | re.IGNORECASE)
            return m.group(1).strip() if m else ""

        summary = _extract("ÖZET") or f"{company} ({ticker}): {title[:100]}"
        tweet_raw = _extract("TWEET")

        # Tweet kalite kontrolü: boşsa veya çok kısaysa summary'den türet.
        def _is_weak_tweet(t: str) -> bool:
            if not t or len(t.strip()) < 30:
                return True
            # Tamamen başlıkla özdeşse (boşluk/büyük-küçük harf farkı hariç) zayıf say
            if t.strip().lower() == title.strip().lower():
                return True
            return False

        if _is_weak_tweet(tweet_raw):
            # AI tweet üretemedi ya da çok zayıf — summary'i yoruma dönüştür.
            # Summary genellikle "Şirket (TİCKER): Kısa açıklama" formatında gelir;
            # bunu tek cümlelik çarpıcı tweet'e çevirmek için summary'i olduğu gibi
            # kullan, başa şirket + ticker ekle, sonuna piyasa etkisi sorusu ekle.
            default_summary = f"{company} ({ticker}): {title[:100]}"
            # AI summary varsa ve başlıktan farklıysa tercih et (daha bilgi yoğun)
            base = summary if (summary and len(summary) > 40
                               and summary.strip().lower() != title.strip().lower()) else title
            tweet = base
            if len(tweet) > 230:
                tweet = tweet[:230].rsplit(" ", 1)[0].rstrip(" ,.;:") + "…"
        else:
            tweet = tweet_raw

        # Body: Az ve öz, doğrudan sonuca odaklı yapı
        analiz = _extract("ANALİZ") or _extract("ANALIZ")
        if analiz:
            body = f"### Hızlı Bakış\n{summary}\n\n### Finansal Sinyal & Analiz\n{analiz}"
        else:
            body = f"### Hızlı Bakış\n{summary}\n\n{raw}"
        return body, summary, tweet

    @staticmethod
    def _template_news_analysis(
        title: str, disclosure_type: str, company: str, ticker: str, is_insider: bool, raw_text: str = ""
    ) -> tuple[str, str, str]:
        """AI yokken az ve öz, doğrudan sonuca odaklı hap finansal analiz üretir."""
        import re
        from ..turkish import tr_fold
        
        full_text = f"{title} {disclosure_type} {raw_text}"
        norm_title = tr_fold(full_text)
        
        amounts = re.findall(r"(\d+(?:[.,]\d+)?\s*(?:milyon|milyar|bin|TL|USD|EUR|adet|lot|%))", full_text, re.IGNORECASE)
        amounts_str = ", ".join(amounts[:2]) if amounts else None

        is_default = any(k in norm_title for k in ("temerrut", "temerrüt"))
        is_order = (not is_default) and any(k in norm_title for k in ("yeni is iliskisi", "siparis", "sozlesme", "ihale", "proje", "is iliskisi"))
        is_buyback = any(k in norm_title for k in ("pay geri alim", "geri alim", "pay alim"))
        is_capital = any(k in norm_title for k in ("sermaye artir", "bedelli", "bedelsiz", "tahsisli"))
        is_dividend = any(k in norm_title for k in ("kar payi", "temettu"))
        is_acquisition = any(k in norm_title for k in ("birles", "devral", "satin al", "istirak"))

        if is_default:
            signal = "Risk / Temerrüt Bildirimi"
            bilanço = f"Takasbank veya Borsa İstanbul temerrüt takası çerçevesinde açılan işlem sırası bildirilmiştir{f' (`{amounts_str}`)' if amounts_str else ''}."
            sektor = "İlgili pay sırasında yükümlülüklerin yerine getirilmesi amacıyla temerrüt satışı/alımı gerçekleştirilmektedir."
            piyasa = "Kısa vadeli likidite ve teminat baskısı yaratabilir; işlem sırası yakından izlenmelidir."
        elif is_order:
            signal = "Pozitif (Yeni Sipariş / İş Anlaşması)"
            bilanço = f"Alınan sipariş/ihale{f' (`{amounts_str}`)' if amounts_str else ''}, şirketin bakiye iş hacmini ve gelecek dönem cirosunu destekler."
            sektor = "Sektördeki pazar payını ve operasyonel kapasite kullanımını güçlendirir."
            piyasa = "Hisse üzerinde kısa vadede pozitif haber akışı etkisi yaratması beklenir."
        elif is_buyback:
            signal = "Pozitif (Pay Geri Alımı / Güven Sinyali)"
            bilanço = f"Geri alım programı{f' (`{amounts_str}`)' if amounts_str else ''}, hisse başına kârı matematiksel olarak destekler."
            sektor = "Şirket yönetiminin mevcut piyasa değerlemesini ucuz bulduğuna işaret eder."
            piyasa = "Fiyat oynaklığını azaltıcı taban desteği oluşturur."
        elif is_dividend:
            signal = "Pozitif (Temettü / Nakit Dağıtımı)"
            bilanço = f"Kâr payı dağıtımı{f' (`{amounts_str}`)' if amounts_str else ''}, şirketin güçlü nakit yaratma kabiliyetini teyit eder."
            sektor = "BIST genelinde temettü verimi odaklı kurumsal ilgiyi canlı tutar."
            piyasa = "Hissede temettü takvimine doğru pozitif fiyatlama eğilimini destekler."
        elif is_acquisition:
            signal = "Stratejik / Nötr-Pozitif (İnorganik Büyüme)"
            bilanço = f"Satın alma/iştirak adımı{f' (`{amounts_str}`)' if amounts_str else ''}, konsolide hasılata doğrudan katkı sunar."
            sektor = "Pazardaki rekabet gücünü ve operasyonel sinerjiyi artırır."
            piyasa = "Entegrasyon süreci ve yatırım geri dönüş süresi piyasa tarafından takip edilir."
        elif is_capital:
            signal = "Nötr / Bilanço Güçlendirme (Sermaye Artırımı)"
            bilanço = f"Sermaye artırımı{f' (`{amounts_str}`)' if amounts_str else ''}, özkaynakları güçlendirerek finansman maliyetini dengeler."
            sektor = "Şirketin borçluluk rasyolarını iyileştirir."
            piyasa = "Sermaye türüne (bedelli/bedelsiz) bağlı olarak likidite etkisi fiyatlanır."
        elif is_insider:
            signal = "İçsel İşlem / Kurumsal Takip"
            bilanço = f"İlişkili taraf pay işlemi{f' (`{amounts_str}`)' if amounts_str else ''}, kurumsal şeffaflık kapsamında bildirilmiştir."
            sektor = "Yönetim/ortaklık pay hareketleri kurumsal yatırımcılar tarafından yakından izlenir."
            piyasa = "İşlemin alış veya satış yönlü oluşu kısa vadeli fiyat algısını etkileyebilir."
        else:
            signal = "Bilgilendirme / Nötr"
            bilanço = f"Bildirilen kurumsal gelişme{f' (`{amounts_str}`)' if amounts_str else ''}, olağan faaliyet takvimi çerçevesindedir."
            sektor = "Operasyonel süreçlerin planlandığı şekilde ilerlediğine işaret eder."
            piyasa = "Doğrudan sert bir fiyatlama etkisi beklenmemektedir."

        summary = f"{company} ({ticker}): {title[:110]}"

        body = (
            f"### Hızlı Bakış\n"
            f"**{company}** ({ticker}), Kamuyu Aydınlatma Platformu'nda `{title}` başlıklı açıklamada bulundu.\n\n"
            f"### Finansal Sinyal: {signal}\n"
            f"- **Bilanço & Ciro:** {bilanço}\n"
            f"- **Sektörel Konum:** {sektor}\n"
            f"- **Piyasa Yansıması:** {piyasa}"
        )

        _prefix = f"${ticker} ({company}): "
        _max_title = max(10, 270 - len(_prefix))
        tweet = f"{_prefix}{title[:_max_title]}"
        return body, summary, tweet

    @staticmethod
    def generate_sector_movement_analysis(
        sector_name: str, change_pct: float, headline: str, macro_context: str = ""
    ) -> tuple[str, str, str]:
        """BIST sektör hareketleri için az, öz ve vurucu analiz üretir."""
        direction = "yükseliş" if change_pct >= 0 else "kâr satışı"
        sign = "+" if change_pct >= 0 else ""
        signal = f"Pozitif (%{sign}{change_pct:.2f})" if change_pct >= 0 else f"Negatif (%{sign}{change_pct:.2f})"
        flow = "güçlü para girişi" if change_pct >= 0 else "kâr realizasyonu ve para çıkışı"
        
        summary = f"BIST {sector_name}: %{sign}{change_pct:.2f} ile {direction} kaydetti."
        
        body = (
            f"### Piyasa Nabzı\n"
            f"Borsa İstanbul'da **BIST {sector_name} Endeksi**, seans genelinde **%{sign}{change_pct:.2f}** değişerek piyasadan ayrıştı.\n\n"
            f"### Sinyal & Rotasyon: {signal}\n"
            f"- **Para Akışı:** Sektör bileşenlerinde gün içi {flow} izlendi; lokomotif hisseler harekete öncülük etti.\n"
            f"- **Sektör Rotasyonu:** Yatırımcı ilgisinin getiri arayışıyla {sector_name} tarafında yoğunlaştığı gözleniyor.\n"
            f"- **Kritik Eşik:** Kısa vadeli hareketli ortalamalar ve göreceli güç (RSI) seviyeleri takip edilmeli."
        )
        
        tweet = f"BIST {sector_name} sektörü %{sign}{change_pct:.2f} {direction} ile ayrışıyor. Para akışı ve sektör rotasyonu özeti raporda:"
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
        sections.append("Değerlendirme (özet görüş; yatırım tavsiyesi verme)")
        sections_text = "\n".join(f"  {i+1}. {s}" for i, s in enumerate(sections))

        prompt = f"""Sen İstanbul merkezli bir aracı kurumun baş piyasa stratejistisin. \
{date_str} sabahı için kurumsal kalitede, veri odaklı bir piyasa bülteni ve Twitter thread'i yaz. \
Türkçe yaz. Yatırım tavsiyesi verme. Yer tutucu (köşeli parantez içi metin) KULLANMA.

=== BÖLÜM A: SABAH BÜLTENİ (RAPOR) ===
Markdown formatında (## başlıklar, madde listeleri, kalın vurgular). \
Her bölümü en az 4-5 cümleyle doyurucu biçimde doldur. \
Verileri birbiriyle ilişkilendir — sadece rakam sıralama değil, yorumlama yap. \
En üste ## başlık KOYMA (dışarıdan eklenecek).

Bölümler (sırayla, her birini tam doldur):
{sections_text}

Yazım kuralları:
- Her bölüm kendi içinde eksiksiz olmalı; okuyucu bölümü atlayabilmeli
- Rakamları mutlaka bağlam içinde yorumla (örn: "XU100 1.2% geriledi — bu Mart'tan bu yana en sert günlük düşüş")
- Küresel veri varsa BIST'e yansımasını açıkla
- Sektör rotasyonu varsa para akışının nereden nereye gittiğini yorumla
- KAP bildirimi varsa sadece başlık değil, bildirimin önemini açıkla
- Ekonomik takvim varsa açıklanacak verinin piyasa beklentisini ve olası etkisini belirt

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
        body = report_match.group(1).strip() if report_match else raw.strip()
        if not body:
            body = self._template_morning_report(snapshot)

        # --- Thread bölümünü parse et ---
        thread_match = re.search(r"---THREAD---\s*(.*?)$", raw, re.DOTALL)
        thread_raw = thread_match.group(1).strip() if thread_match else raw

        tweet_pattern = r"TWEET\s+\d+:\s*(.+?)(?=TWEET\s+\d+:|$)"
        matches = re.findall(tweet_pattern, thread_raw, re.DOTALL | re.IGNORECASE)
        tweets = [m.strip()[:280] for m in matches if m.strip()]

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
Sen üst düzey bir küresel piyasalar stratejistisin. Aşağıdaki güncel küresel makro
verilerine bakarak detaylı, profesyonel ve öngörü dolu bir piyasa değerlendirmesi yaz.
Sadece fiyatları tekrarlama; S&P 500, DAX gibi ana endekslerdeki, tahvil faizlerindeki
ve kurlardaki değişimlerin birbiriyle bağlantısını, paranın nereye aktığını ve
Borsa İstanbul (BIST) için ne gibi etkileri olabileceğini derinlemesine analiz et.

Veriler:
{macro_snapshot}

Şu formatta yanıt ver:

## GÖRÜNÜM
[Genel piyasa iştahı ve özet durumu anlatan 2-3 cümle]

## ÖNE ÇIKAN GELİŞMELER VE ETKİLERİ
- **ABD ve Avrupa Endeksleri:** [Yorum]
- **Tahvil ve Döviz:** [Yorum]
- **Emtia (Altın/Petrol) & VIX:** [Yorum]

## BIST İÇİN BEKLENTİ
[Bu küresel tablonun Türkiye piyasalarına olası yansımaları]

## TWEET
280 karakter hedefli, güçlü bir tweet. Kurallar:
- İLK CÜMLE çarpıcı ve quote tweet'lenebilir bir "hook" olsun.
- En kritik makro hareketi ve BIST için ne anlama geldiğini ver.
- Tarihsel bağlam ekle (örn: "Son 3 ayın en yüksek X değeri").
- SORU ile bitir (etkileşimi artırır).
- EMOJİ KULLANMA, hashtag EKLEMEde.
"""
        raw = self.client.generate(prompt, task_type="analysis")
        if raw:
            import re
            def _extract(section: str) -> str:
                pattern = rf"##\s*{re.escape(section)}\s*\n(.*?)(?=\n##\s|\Z)"
                m = re.search(pattern, raw, re.DOTALL | re.IGNORECASE)
                return m.group(1).strip() if m else ""
                
            tweet = _extract("TWEET")
            body_sections = []
            for sec in ("GÖRÜNÜM", "ÖNE ÇIKAN GELİŞMELER VE ETKİLERİ", "BIST İÇİN BEKLENTİ"):
                content = _extract(sec)
                if content:
                    body_sections.append(f"## {sec.title()}\n\n{content}")
            body = "\n\n".join(body_sections) if body_sections else raw
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
            if q.futures_symbol:
                lines.append(
                    f"- {q.futures_symbol} Vadeli: {q.futures_price} ({q.futures_change})"
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

        # Et-Yem Paritesi ve Et TÜFE Enflasyonu
        if snapshot.meat_feed:
            mf = snapshot.meat_feed
            lines.append("\n### Et-Yem Paritesi & Et TÜFE")
            lines.append(f"- Yıllık Et TÜFE Enflasyonu: %{mf.et_enflasyonu_yillik_pct:.1f} (Manşet TÜFE: %{mf.manset_enflasyon_yillik_pct:.1f}, Prim: %{mf.et_enflasyon_primi_pct:+.1f})")
            for p in mf.pariteler:
                lines.append(f"- {p.kategori}: Karkas={p.karkas_fiyati_tl_kg:.1f} TL, Yem={p.yem_fiyati_tl_kg:.1f} TL -> Parite={p.parite_orani:.1f} ({p.kar_marji_durumu})")

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

        # Et-Yem Paritesi & Et TÜFE bölümü
        meat_sec = ""
        if snapshot.meat_feed:
            mf = snapshot.meat_feed
            meat_sec = (
                "## Et-Yem Paritesi & Et TÜFE Enflasyonu\n\n"
                f"- **Yıllık Et TÜFE Enflasyonu:** %{mf.et_enflasyonu_yillik_pct:.1f} (Manşet TÜFE: %{mf.manset_enflasyon_yillik_pct:.1f})\n"
                f"- **Dana Karkas / Besi Yemi Paritesi:** {mf.pariteler[0].parite_orani if mf.pariteler else '—'} ({mf.pariteler[0].kar_marji_durumu if mf.pariteler else ''})\n"
                f"- **BIST Yansıması:** {mf.bist_etkisi_ozeti}\n\n"
            )

        # VİOP bölümü
        viop_sec = ""
        if snapshot.viop_quote:
            q = snapshot.viop_quote
            viop_sec = (
                f"## VİOP\n\n"
                f"{q.index_symbol}: **{q.index_price}** ({q.index_change})"
            )
            if q.futures_symbol:
                viop_sec += f" | Vadeli {q.futures_symbol}: {q.futures_price} ({q.futures_change})"
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
            "## Değerlendirme\n\n"
            "Bu bülten otomatik olarak derlenmiştir. Küresel risk iştahı, sektör "
            "rotasyonu ve yurt içi veri akışı gün içi yönü belirleyecek başlıklar "
            "olmayı sürdürüyor."
        )
        return header + macro_sec + turib_sec + meat_sec + cal + viop_sec + sector_sec + kap + footer
