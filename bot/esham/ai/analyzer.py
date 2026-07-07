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

    def generate_breaking_news_tweet(self, headline: str, macro_context: str = "") -> tuple[str, str]:
        """SON DAKİKA haberi için AI destekli tweet metni ve kısa rapor gövdesi üretir.

        Döndürür: (tweet_text, body_markdown)
        - tweet_text   : 280 karakter hedefli, bağlam ve etki açıklaması olan tweet
        - body_markdown: web raporu için kısa analiz gövdesi
        """
        macro_block = f"\nGüncel makro bağlam: {macro_context}" if macro_context else ""

        prompt = f"""
Sen bir finansal haber masası analistisin. Aşağıdaki son dakika haberini analiz et.

Haber: {headline}
{macro_block}

Şu formatta yanıt ver:

## TWEET
280 karakteri akıllıca kullanan, bilgi yoğun bir tweet yaz. Kurallar:
- Haberin NEDEN önemli olduğunu ve piyasalara/ekonomiye olası etkisini belirt
- Varsa rakam/veri mutlaka ekle (fiyat, oran, tutar, yüzde)
- Sadece başlığı tekrar etme — yorum ve bağlam ekle
- EMOJİ KULLANMA — sadece metin, rakam ve veriler
- Hashtag EKLEMEde — zaten dışarıdan eklenecek

## ANALIZ
3-4 cümlelik kısa Türkçe analiz. Bu haberin piyasalar, sektörler veya Türkiye ekonomisi
üzerindeki etkisini, risk ve fırsatları ve izlenmesi gereken sonraki gelişmeleri açıkla.
Yatırım tavsiyesi verme.
"""
        raw = self.client.generate(prompt, disable_thinking=True, task_type="tweet")
        if not raw:
            # Fallback — sadece başlık
            return headline[:260], f"## {headline}\n\nBu gelişme piyasalar üzerinde etkili olabilir."

        import re
        def _extract(section: str) -> str:
            pattern = rf"##\s*{re.escape(section)}\s*\n(.*?)(?=\n##\s|\Z)"
            m = re.search(pattern, raw, re.DOTALL | re.IGNORECASE)
            return m.group(1).strip() if m else ""

        tweet = _extract("TWEET") or headline[:260]
        analysis = _extract("ANALİZ") or _extract("ANALIZ") or ""
        body = f"## {headline}\n\n{analysis}" if analysis else f"## {headline}\n\n{raw}"
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

        prompt = f"""
Sen üst düzey bir Türk sermaye piyasaları analistisin. Aşağıdaki KAP bildirimini oku ve
derinlemesine, kurumsal kalitede bir piyasa analizi yaz. Yatırım tavsiyesi verme. Türkçe yaz.
{insider_prompt_extra}
Şirket: {company} ({ticker})
Bildirim türü: {disclosure_type}
Başlık: {title}
İçerik: {raw_text or title}
{macro_block}{sector_block}

Şu formatta yanıt ver (başlıkları aynen koru):

## ÖZET
Tek cümlelik özet (max 150 karakter). Rakamsal detay varsa (fiyat, tutar, oran) mutlaka ekle.

## ANALİZ
3-5 madde halinde bildirimin piyasa etkisini, şirketin finansallarına veya sektördeki rekabete olası yansımalarını derinlemesine analiz et. Yüzeysel ifadelerden kaçın; haberin "neden" önemli olduğunu ve satır aralarındaki risk/fırsatları belirt. Sayısal veriler, oranlar veya tutarlar varsa bunları yorumuna dahil et. Her madde 2-3 cümlelik doyurucu bir paragraf olsun.

## BAĞLAM
Bu bildirimi küresel makro trendler (faizler, kurlar) ve ilgili sektördeki rotasyon/gelişmeler ile ilişkilendir. Şirketin bu makro konjonktürdeki pozisyonunu yorumla (2-3 cümle, veri yoksa atla).

## TWEET
280 karakteri iyi kullanan, bilgi yoğun bir tweet yaz. Şu kurallara uy:
- İLK CÜMLE bağımsız okunabilir, çarpıcı ve tek başına paylaşılabilir bir "hook" olsun.
  Örnek format: "X şirketi Y işleminde Z tutar açıkladı — bu [sektör/piyasa] için [etki]."
- Varsa rakam/oran MUTLAKA ekle (fiyat, tutar, yüzde, lot).
- Haberin NEDEN önemli olduğunu ver, sadece ne olduğunu değil.
- İçsel işlemse alım/satım sinyali ve tutar büyüklüğü öne çıksın.
- SORU ile bitir (etkileşimi artırır). Örnek: "Sizce bu [sektör] için ne anlama geliyor?"
- EMOJİ KULLANMA — sadece metin ve veriler.
- Hashtag EKLEMEde — zaten dışarıdan ekleniyor.
"""
        raw = self.client.generate(prompt, disable_thinking=True, task_type="analysis")
        if raw:
            return self._parse_news_analysis(raw, title, company, ticker, is_insider)

        log.info("AI kapalı/başarısız; şablon haber analizi üretiliyor.")
        return self._template_news_analysis(title, disclosure_type, company, ticker, is_insider)

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
        tweet = _extract("TWEET") or f"{'🚨' if is_insider else '📰'} {title[:200]}"

        # Body: ÖZET ve TWEET bölümleri dışındaki her şeyi al; yoksa tamamı
        body_sections = []
        for sec in ("ANALİZ", "BAĞLAM"):
            content = _extract(sec)
            if content:
                body_sections.append(f"## {sec.title()}\n\n{content}")
        body = "\n\n".join(body_sections) if body_sections else raw

        # Özet satırı başa ekle
        body = f"**{summary}**\n\n{body}"
        return body, summary, tweet

    @staticmethod
    def _template_news_analysis(
        title: str, disclosure_type: str, company: str, ticker: str, is_insider: bool
    ) -> tuple[str, str, str]:
        """AI yokken deterministik şablon üretir."""
        emoji = "🚨" if is_insider else "📰"
        summary = f"{company} ({ticker}): {title[:120]}"
        body = (
            f"**{summary}**\n\n"
            f"## Bildirim\n\n"
            f"- **Şirket:** {company} ({ticker})\n"
            f"- **Tür:** {disclosure_type}\n"
            f"- **Başlık:** {title}\n"
            + ("- ⚠️ İçsel bildirim\n" if is_insider else "")
            + "\n## Not\n\nBu bildirim otomatik olarak derlendi; AI analizi şu an kullanılamıyor."
        )
        tweet = f"{emoji} {company} ({ticker}): {title[:200]}"
        return body, summary, tweet

    def generate_morning_report(self, snapshot: MarketSnapshot) -> tuple[str, bool]:
        """Sabah bülteninin markdown gövdesini üretir.

        Döndürür: (body_markdown, ai_used)
        - body_markdown : web raporuna yazılacak markdown gövde
        - ai_used       : True ise AI üretimi, False ise deterministik şablon
        """
        from datetime import datetime, timedelta, timezone

        today = datetime.now(timezone(timedelta(hours=3)))
        date_str = today.strftime("%d.%m.%Y")
        context = self._snapshot_context(snapshot)

        # Hangi veri kaynaklarının mevcut olduğunu belirle
        has_macro = snapshot.macro is not None and bool(snapshot.macro.tickers)
        has_viop = snapshot.viop_quote is not None
        has_sector = bool(snapshot.sector)
        has_kap = bool(snapshot.disclosures)
        has_calendar = bool(snapshot.calendar)

        # Mevcut kaynaklara göre dinamik bölüm listesi oluştur
        sections: list[str] = ["Genel Görünüm (BIST endeksi, genel tablo)"]
        if has_macro:
            sections.append("Küresel Piyasalar (ABD 10Y faiz, EUR/USD, Altın, VIX, Brent — her birinin BIST'e etkisini yorumla)")
        if has_viop:
            sections.append("VİOP & Türev Piyasa (endeks/vadeli fiyat, teminat stresi varsa belirt)")
        if has_sector:
            sections.append("Sektör Rotasyonu (güçlü ve zayıf sektörler, para akışı yorumu)")
        if has_kap:
            sections.append("KAP Öne Çıkanlar (önemli bildirimleri kısa özetle; içsel işlem varsa vurgula)")
        if has_calendar:
            sections.append("Ekonomik Takvim (bugünün kritik veri açıklamaları ve piyasa beklentisi)")
        sections.append("Değerlendirme (özet görüş; yatırım tavsiyesi verme)")

        sections_text = "\n".join(f"  {i+1}. {s}" for i, s in enumerate(sections))

        prompt = f"""
Aracı kurum baş stratejisti kalitesinde, Türkçe bir "sabah piyasa bülteni" yaz. Bugünün tarihi: {date_str}.

Kurallar:
- Markdown kullan (## başlıklar, listeler, gerekirse tablo).
- Yatırım tavsiyesi verme; nesnel, öngörülü, vizyoner ve derinlemesine analitik bir dil kullan. Yüzeysel "arttı/azaldı" yorumlarından kaçın.
- Verileri birbiriyle bağdaştırarak (örneğin ABD faizi ile BIST'teki teknoloji/banka rotasyonunu) bütüncül bir hikaye anlat. Paranın nereye aktığını analiz et.
- ASLA köşeli parantezli yer tutucu ([...]) yazma; sadece aşağıdaki verilerle yaz.
- En üste ## başlık koyma, doğrudan bölümlerle başla.
- Her bölüm doyurucu, bilgi yoğun ve profesyonel argümanlarla desteklenmiş olsun.

Aşağıdaki güncel piyasa verileri sana sağlanmıştır:

{context}

Bülten şu bölümleri SIRALI olarak içersin:
{sections_text}
"""
        body = self.client.generate(prompt, disable_thinking=True, task_type="analysis")
        if body:
            return body, True
        log.info("AI kapalı/başarısız; şablon sabah raporu üretiliyor.")
        return self._template_morning_report(snapshot), False

    def generate_morning_thread(self, snapshot: MarketSnapshot) -> list[str]:
        """Sabah bültenini 5-6 tweet'lik thread olarak üretir.

        Her tweet bağımsız okunabilir, bilgi yoğun ve makro/sektör/KAP verilerini özetler.
        İlk tweet çarpıcı bir "hook" ve genel görünüm, sonrakiler detayları işler.
        
        Döndürür: tweet listesi (her biri max 280 karakter)
        """
        if not self.client.enabled:
            # Fallback: tek tweet
            b = snapshot.bist
            return [f"BIST {b.index if b else 'XU100'} bugün {b.price if b else '—'} seviyesinde. Detaylı bülten web sitesinde."]

        context = self._snapshot_context(snapshot)
        prompt = f"""
Sen üst düzey bir piyasa analisti ve içerik stratejistisin. Aşağıdaki sabah verilerini kullanarak
5-6 tweet'lik bir thread yaz. Her tweet BAĞIMSIZ okunabilir, bilgi yoğun ve çarpıcı olmalı.

KURALLAR:
1. İLK TWEET: Genel görünüm + çarpıcı hook. BIST endeks seviyesi, değişim ve günün en kritik başlığı.
   Örnek format: "BIST100 10.450'de (-%0.8) açılış öncesinde. ABD 10Y faizi %4.5'e yükselirken [etki] izleniyor."

2. İKİNCİ TWEET: Küresel makro gelişmeler (ABD faiz, EUR/USD, altın, VIX). En dikkat çeken 2-3 veriyi yorumla.
   Örnek: "ABD 10Y tahvil faizi %4.5 — son 3 ayın zirvesi. Bu gelişmekte olan piyasalara baskı sinyali."

3. ÜÇÜNCÜ TWEET: VİOP/teminat veya sektör rotasyonu. Hangi sektörlere para akıyor, kim güçlü kim zayıf.
   Örnek: "Sektör rotasyonu: Ulaştırma %3.1 ile öne çıkıyor. Teknoloji -%1.2 ile geri planda."

4. DÖRDÜNCÜ TWEET: KAP öne çıkanlar. İçsel işlem/halka arz/büyük açıklama varsa vurgula.
   Örnek: "KAP'ta dikkat: [Şirket] [işlem] açıkladı. [Etki yorumu]."

5. BEŞİNCİ TWEET (opsiyonel): Ekonomik takvim veya ek bağlam. Bugün açıklanacak kritik veri.
   Örnek: "Bugün 14:30'da ABD istihdam verisi açıklanacak — BIST için volatilite tetikleyicisi olabilir."

6. SON TWEET: Özet değerlendirme + SORU ile bitir (etkileşimi artırır).
   Örnek: "Özetle: Küresel faiz baskısı BIST'te temkinli bir gün işaret ediyor. Sizce sektör rotasyonu devam eder mi?"

HER TWEET için:
- Max 260 karakter (thread'de link yok ama güvenlik payı)
- Rakam/oran MUTLAKA ekle (fiyat, yüzde, tutar)
- SORU formatı etkileşimi artırır (özellikle son tweet)
- EMOJİ KULLANMA, hashtag EKLEMEde
- Her tweet bağımsız anlaşılabilir olsun

Güncel veriler:
{context}

Her tweet'i ayrı satırda "TWEET [numara]:" başlığıyla ver. Örnek format:
TWEET 1: [metin]
TWEET 2: [metin]
...
"""
        raw = self.client.generate(prompt, disable_thinking=True, task_type="analysis")
        if not raw:
            # Fallback
            b = snapshot.bist
            return [f"BIST {b.index if b else 'XU100'} bugün {b.price if b else '—'} seviyesinde. Detaylı sabah bülteni web sitesinde."]

        # Parse tweet'leri
        import re
        pattern = r"TWEET\s+\d+:\s*(.+?)(?=TWEET\s+\d+:|$)"
        matches = re.findall(pattern, raw, re.DOTALL | re.IGNORECASE)
        tweets = [m.strip() for m in matches if m.strip()]
        
        # Her tweet'i 280 karakterle sınırla
        tweets = [t[:280] if len(t) > 280 else t for t in tweets]
        
        # En az 3, en fazla 7 tweet
        if len(tweets) < 3:
            # Fallback
            b = snapshot.bist
            return [f"BIST {b.index if b else 'XU100'} sabah raporu hazır. {b.price if b else '—'} seviyesinde. Detaylar web'de."]
        
        return tweets[:7]  # max 7 tweet

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
- ✅ **[Olumlu Nokta Başlığı]:** [Neden önemli olduğu, şirkete gelecekteki katkısı ve rakamsal/oransal değerlendirmesi (2-3 cümle)] (En az 3 adet)
- 🚨 **[Gizli Tehlike / Risk]:** [Bilanço dipnotlarında veya nakit akışında yatan sinsi risk, operasyonel baskı veya borç yükü analizi (2-3 cümle)] (En az 3 adet)

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

        # Ekonomik takvim
        if snapshot.calendar:
            lines.append("\n### Ekonomik Takvim")
            for ev in snapshot.calendar:
                lines.append(
                    f"- {ev.time} {ev.country}: {ev.event}"
                    f" (önem: {ev.importance}, beklenti: {ev.forecast})"
                )

        # KAP bildirimleri
        if snapshot.disclosures:
            lines.append("\n### KAP Bildirimleri")
            for d in snapshot.disclosures:
                insider_flag = " [İÇSEL]" if d.is_insider else ""
                lines.append(f"- {d.title} [{d.disclosure_type}]{insider_flag}")

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
        return header + macro_sec + cal + viop_sec + sector_sec + kap + footer
