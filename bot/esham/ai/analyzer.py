"""Gemini tabanlı analiz ve içerik üretimi.

Tasarım ilkeleri:
- API anahtarı yoksa AI devre dışı kalır ama pipeline çökmemesi için deterministik
  şablon üretimine düşülür (graceful degradation).
- Ağ/model hataları yakalanır ve loglanır (LlmClient içinde).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from .. import market_text
from ..config import get_logger, settings
from ..formatting import tr_number, tr_pct
from ..sentences import first_sentence, safe_truncate
from ..sources.sector import movers_lines
from ..turkish import repair_lost_apostrophes
from ..neutral import NOTE_AMOUNT_MISSING, strip_banned
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
    "Tutar bilgisi için bildirime bakın." notu ve KAP bağlantısı. ``text`` bilinçli olarak kullanılmaz:
    bildirim gövdesinden hiçbir rakam rapora taşınmaz.
    """
    who = f"{company} ({ticker})" if ticker and ticker != company else company
    lines = [
        "### Bildirim Bilgileri",
        f"- **Başlık (KAP):** {title}",
        f"- **Şirket:** {who}",
    ]
    if date:
        lines.append(f"- **Tarih:** {date}")
    lines.append(f"- **Bildirim türü (KAP):** {disclosure_type or 'Belirtilmemiş'}")
    # Bildirim gövdesinden hiçbir tutar/rakam alınmaz (ne ayrıştırma ne alıntı); okur bildirime yönlendirilir.
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
            # Sayı/kısaltma farkında: eski split('.') "7.266,17" içindeki noktada kesiyordu.
            summary = first_sentence(event.headline)

        analiz = _extract("ANALİZ") or _extract("ANALIZ") or raw.strip()

        # Başlığın gövde başında gereksiz H1/H2 olarak tekrarlanmasını engelle
        cleaned_body = re.sub(
            rf"^#{{1,3}}\s+{re.escape(event.headline)}\s*\n+", "", analiz, flags=re.IGNORECASE
        ).strip()

        # Deterministik son süzgeç: model kurala uymadıysa yasaklı içerik yayına gitmez.
        cleaned_body = strip_banned(cleaned_body)
        summary = strip_banned(summary) or first_sentence(event.headline)
        tweet_raw = strip_banned(_extract("TWEET"))
        if not tweet_raw or len(tweet_raw.strip()) < 30:
            tweet_raw = f"{safe_truncate(event.headline, 200)} — gelişmenin özeti raporda:"

        return cleaned_body, summary, tweet_raw

    @staticmethod
    def _template_event_analysis(event: "MarketEvent", macro_context: str = "") -> tuple[str, str, str]:
        """AI kapalıyken yalnız kaynaktaki bilgiyi ve veriyi aktarır; dolgu yorum paragrafı üretmez."""
        details_clean = getattr(event, "details", "").strip()
        if details_clean and is_mostly_english(details_clean):
            details_clean = translate_to_turkish(details_clean)

        # Sayı/kısaltma farkında ilk cümle (eski split('.') "S&P 500 +1,16% yükseldi (7" üretti).
        first_clause = first_sentence(event.headline)
        if is_mostly_english(first_clause):
            first_clause = ensure_turkish(first_clause) or first_clause

        parts = [f"### Gelişme\n{details_clean or event.headline}"]
        if getattr(event, "value_str", "") and getattr(event, "change_str", ""):
            parts.append(
                f"### Veri\n- **{event.label}:** {event.value_str} (önceki kapanışa göre {event.change_str})"
            )
        body = "\n\n".join(parts)
        summary = first_clause
        tweet = f"{first_clause} — ayrıntı raporda:"
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
Tek cümle (max 140 karakter): kim, neyi açıkladı. Tutar/rakam YAZMA (okur bildirime yönlendirilir).

## BİLDİRİM
- **Ne açıklandı:** Bildirimdeki ifadelere sadık 1-2 cümle.
- **Taraflar:** Bildirimde geçen şirket/kişi/kurumlar; yoksa "Belirtilmemiş".
- **Tarihler:** Bildirimde geçen tarih ve süreler; yoksa "Belirtilmemiş".
- **Açıklanan sonraki adım:** Yalnızca bildirimde yazan süreç adımı (ör. SPK onayı, genel kurul); yoksa "Belirtilmemiş".

## TWEET
260 karakteri aşmayan tek, tarafsız cümle: [Şirket] [ne açıkladı]. Tutar/rakam yazma.
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
            tweet = safe_truncate(tweet, 230)

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
        pct = tr_pct(change_pct)
        summary = f"BIST {sector_name} endeksinin önceki kapanışa göre değişimi {pct}."
        body = (
            f"### Endeks Verisi\n"
            f"- **Endeks:** BIST {sector_name}\n"
            f"- **Önceki kapanışa göre değişim:** {pct}\n"
            f"- **Kaynak:** Borsa İstanbul endeks verisi (gecikmeli olabilir)"
        )
        tweet = f"BIST {sector_name} endeksinin önceki kapanışa göre değişimi {pct}. Endeks verisi raporda:"
        return body, summary, tweet

    def generate_morning_report_and_thread(
        self, snapshot: MarketSnapshot, now: datetime | None = None
    ) -> tuple[str, bool, list[str]]:
        """Sabah bültenini VE tweet thread'ini tek AI çağrısında üretir.

        Rate limit sorununu önlemek için rapor + thread tek prompt'ta istenir,
        ardından parse edilir.

        Döndürür: (body_markdown, ai_used, tweets)
        """
        import re

        today = now or datetime.now(timezone(timedelta(hours=3)))
        now = today
        date_str = today.strftime("%d.%m.%Y")
        context = self._snapshot_context(snapshot, now)

        has_macro = snapshot.macro is not None and bool(snapshot.macro.tickers)
        has_viop = snapshot.viop_quote is not None
        has_sector = bool(snapshot.sector)
        has_kap = bool(snapshot.disclosures)
        has_calendar = bool(snapshot.calendar)

        sections: list[str] = ["Genel Görünüm (BIST endeksi, genel tablo)"]
        if has_macro:
            sections.append("Küresel Piyasalar (ABD 10Y faiz, EUR/USD, Altın, VIX, Brent — rakamlarıyla)")
        if has_viop:
            sections.append("VİOP & Türev Piyasa (endeks/vadeli fiyat, teminat stresi)")
        if has_sector:
            sections.append("Sektör Endeksleri (yükselen ve düşen sektörler, verilerdeki listelerle ve rakamlarıyla)")
        if has_kap:
            sections.append("KAP Bildirimleri (bildirimlerde ne açıklandığı)")
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
- Her rakamı verilerde yazan anlamıyla ve zamanıyla ver ("son işlem", "önceki kapanışa göre", tarih/saat). Seans açılmadıysa "güne başladı", "bugün açıldı" gibi ifadeler KULLANMA.
- Sektör verisi varsa yükselen (yalnız pozitif değişimli) ve düşen (yalnız negatif değişimli) sektörleri verilerdeki gibi ayrı listele; liste boşsa "yükselen/düşen sektör yok" yaz
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
            body = self._template_morning_report(snapshot, now)
            tweets = self._fallback_tweets(snapshot, now)
            return body, False, tweets

        # --- Rapor bölümünü parse et ---
        report_match = re.search(r"---RAPOR---\s*(.*?)(?=---THREAD---|$)", raw, re.DOTALL)
        body = strip_banned(report_match.group(1).strip() if report_match else raw.strip())
        if not body:
            body = self._template_morning_report(snapshot, now)

        # --- Thread bölümünü parse et ---
        thread_match = re.search(r"---THREAD---\s*(.*?)$", raw, re.DOTALL)
        thread_raw = thread_match.group(1).strip() if thread_match else raw

        tweet_pattern = r"TWEET\s+\d+:\s*(.+?)(?=TWEET\s+\d+:|$)"
        matches = re.findall(tweet_pattern, thread_raw, re.DOTALL | re.IGNORECASE)
        tweets = [strip_banned(m.strip())[:280] for m in matches if m.strip()]
        tweets = [t for t in tweets if t]

        if len(tweets) < 3:
            tweets = self._fallback_tweets(snapshot, now)

        return body, True, tweets[:7]

    def generate_morning_report(self, snapshot: MarketSnapshot) -> tuple[str, bool]:
        """Sadece rapor üretir (eski uyumluluk). Thread gerekmiyorsa bunu kullan."""
        body, ai_used, _ = self.generate_morning_report_and_thread(snapshot)
        return body, ai_used

    def generate_morning_thread(self, snapshot: MarketSnapshot) -> list[str]:
        """Sadece thread üretir. generate_morning_report_and_thread kullanılması önerilir."""
        _, _, tweets = self.generate_morning_report_and_thread(snapshot)
        return tweets

    def _fallback_tweets(self, snapshot: MarketSnapshot, now: datetime | None = None) -> list[str]:
        """AI başarısız olduğunda snapshot verisiyle deterministik tweet listesi üretir.

        Eskiden ilk tweet "bugün {fiyat} seviyesinde, {değişim} değişimle açıldı" diyordu; fiyat son işlem
        (çoğu zaman önceki seansın kapanışı), değişim önceki kapanışa göreydi → yanlış olgu. Artık
        ``market_text`` cümlesi kullanılır; zamanı bilinmeyen endeks rakamı yazılmaz.
        """
        now = now or datetime.now(timezone(timedelta(hours=3)))
        tweets: list[str] = []
        bist_line = market_text.bist_last_short(snapshot.bist, now)
        tweets.append(f"BIST {bist_line} Sabah bülteni hazır." if bist_line else "Sabah bülteni hazır.")
        if snapshot.macro and snapshot.macro.tickers:
            macro_bits = [f"{t.label} {t.value_str} ({t.change_report})" for t in snapshot.macro.tickers[:3]]
            tweets.append("Küresel piyasalar, önceki kapanışa göre: " + " | ".join(macro_bits))
        if snapshot.turib and snapshot.turib.hububat_index:
            h = snapshot.turib.hububat_index
            tweets.append(f"TÜRİB Hububat endeksi: {h.price} ({tr_pct(h.change_pct)}). Tarımsal emtia özeti bültende.")

        if snapshot.sector:
            ups, downs = movers_lines(snapshot.sector, 2)
            tweets.append(f"Sektör endeksleri, önceki kapanışa göre — yükselenler: {ups}; düşenler: {downs}.")
        tweets.append("Detaylı sabah bülteni web sitesinde.")
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
    def _snapshot_context(snapshot: MarketSnapshot, now: datetime | None = None) -> str:
        """LLM'e giden veri bağlamı: her rakam ANLAMI ve ZAMANIYLA verilir (model "güne başladı" uydurmasın)."""
        now = now or datetime.now(timezone(timedelta(hours=3)))
        lines: list[str] = []

        # BIST — zamanı bilinmeyen/eski endeks rakamı bağlama hiç girmez
        bist_line = market_text.bist_last(snapshot.bist, now)
        if bist_line and snapshot.bist is not None:
            lines.append(f"- {bist_line}{market_text.session_note(snapshot.bist)}")

        # Küresel makro
        if snapshot.macro and snapshot.macro.tickers:
            lines.append("\n### Küresel Makro (değişimler önceki kapanışa göre)")
            for t in snapshot.macro.tickers:
                lines.append(f"- {t.label}: {t.value_str} ({t.change_report}; veri zamanı {t.as_of_str})")

        # VİOP kotasyonu
        if snapshot.viop_quote:
            lines.append("\n### VİOP")
            lines.append(f"- {market_text.viop_index_line(snapshot.viop_quote)}")

        # VİOP teminat stresi
        if snapshot.viop_margin:
            m = snapshot.viop_margin
            lines.append(
                f"- Takasbank teminat verisi ({m.as_of}): margin-call/gereken = "
                f"{tr_pct(m.margin_call_to_required_pct, 3, signed=False)} (margin-call toplam: {m.margin_call_pretty()})"
            )

        # Sektörler: yükselen listesi yalnız pozitif, düşen listesi yalnız negatif değişimler
        if snapshot.sector:
            ups, downs = movers_lines(snapshot.sector, 3)
            lines.append(f"\n### Sektör Endeksleri — {market_text.sector_heading_note(snapshot.sector)}")
            lines.append(f"Yükselen sektörler: {ups}")
            lines.append(f"Düşen sektörler: {downs}")

        # TÜRİB ELÜS (Tarımsal Emtia & Hububat)
        if snapshot.turib:
            t = snapshot.turib
            lines.append("\n### TÜRİB ELÜS (Tarımsal Emtia)")
            if t.hububat_index:
                lines.append(f"- TÜRİB Hububat Endeksi (TRBHUB): {t.hububat_index.price} ({tr_pct(t.hububat_index.change_pct)})")
            for p in t.products:
                lines.append(
                    f"- {p.product}: {p.avg_price_tl_kg} TL/kg ({tr_pct(p.change_pct)}), "
                    f"hacim: {tr_number(p.volume_kg / 1000.0, 1)} ton"
                )

        # Ekonomik takvim (en fazla 5 kritik olay)
        if snapshot.calendar:
            lines.append("\n### Ekonomik Takvim (saatler TSİ)")
            for ev in snapshot.calendar[:5]:
                lines.append(
                    f"- {ev.time} {ev.country}: {ev.event}"
                    f" (önem: {ev.importance}, beklenti: {ev.forecast or 'belirtilmemiş'})"
                )

        # KAP bildirimleri (en fazla 10 — prompt boyutunu kontrol altında tut)
        if snapshot.disclosures:
            lines.append("\n### KAP Bildirimleri (öne çıkanlar)")
            for d in snapshot.disclosures[:10]:
                insider_flag = " [İÇSEL]" if d.is_insider else ""
                lines.append(f"- {safe_truncate(repair_lost_apostrophes(d.title), 80)} [{d.disclosure_type}]{insider_flag}")

        return "\n".join(lines) or "- Veri bulunamadı."

    @staticmethod
    def _template_morning_report(snapshot: MarketSnapshot, now: datetime | None = None) -> str:
        now = now or datetime.now(timezone(timedelta(hours=3)))
        b = snapshot.bist
        header = "## Genel Görünüm\n\n"
        bist_line = market_text.bist_last(b, now)
        if bist_line and b is not None:
            header += f"{bist_line}{market_text.session_note(b)}\n\n"
        else:
            # Zamanı bilinmeyen ya da eski endeks verisi güncelmiş gibi yazılmaz: eksik veri eksik görünür.
            header += "Endeks verisi alınamadı ya da veri zamanı doğrulanamadı.\n\n"

        # Küresel makro tablosu (her satır kendi veri zamanıyla)
        macro_sec = ""
        if snapshot.macro and snapshot.macro.tickers:
            macro_sec = "## Küresel Makro\n\n" + snapshot.macro.to_markdown_table() + "\n\n"

        cal = "## Ekonomik Takvim\n\n"
        if snapshot.calendar:
            cal += "| Saat (TSİ) | Ülke | Olay | Beklenti |\n| --- | --- | --- | --- |\n"
            for ev in snapshot.calendar:
                cal += f"| {ev.time} | {ev.country} | {ev.event} | {ev.forecast or '—'} |\n"
            cal += "\n"
        else:
            cal += "Bugün için öne çıkan veri bulunmuyor.\n\n"

        # TÜRİB ELÜS Tarımsal Emtia bölümü
        turib_sec = ""
        if snapshot.turib and snapshot.turib.summary_text:
            turib_sec = f"## TÜRİB ELÜS Tarımsal Emtia\n\n{snapshot.turib.summary_text}\n\n"

        # VİOP bölümü: XU030 spot endekstir (vadeli kontratların dayanağı); vadeli satır ayrı ve yalnız varsa
        viop_sec = ""
        if snapshot.viop_quote:
            viop_sec = f"## VİOP\n\n{market_text.viop_index_line(snapshot.viop_quote)}\n\n"

        # Sektör bölümü: listeler işarete göre süzülür ("En çok düşen" altında pozitif değişim yazılmaz)
        sector_sec = ""
        if snapshot.sector:
            sector_sec = (
                f"## Sektör Endeksleri\n\n"
                f"Sektör endeksleri — {market_text.sector_heading_note(snapshot.sector)}.\n\n"
                f"{market_text.sector_movers_md(snapshot.sector)}\n\n"
            )

        kap = ""
        if snapshot.disclosures:
            kap = "## KAP Bildirimleri\n\n"
            for d in snapshot.disclosures:
                kap += f"- **{repair_lost_apostrophes(d.title)}** — {d.disclosure_type}\n"  # görüntüleme onarımı
            kap += "\n"

        footer = (
            "## Not\n\n"
            "Bu bülten kamuya açık piyasa verilerinden otomatik olarak derlenmiştir; "
            "yatırım tavsiyesi değildir."
        )
        return header + macro_sec + turib_sec + cal + viop_sec + sector_sec + kap + footer
