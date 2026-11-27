# Esham

> **Esham** (Osmanlıca سهام — "sehim"in çoğulu, *hisse senetleri*), yapay zeka
> destekli bir ekonomi/piyasa medya aracıdır. BIST, küresel makro veriler ve KAP
> halka arz belgelerini her gün otomatik analiz ederek profesyonel raporlar yayınlar.

## Mimari

İki ayrı ama tek bir sözleşmeyle bağlı katman:

```
┌────────────────────────┐        JSON rapor        ┌────────────────────────┐
│  bot/  (Python)         │   web/content/reports/   │  web/  (Next.js 16)     │
│  ─ kaynaklar (KAP/BIST) │ ───────────────────────▶ │  ─ dosyadan okur         │
│  ─ AI (Gemini)          │   *.json (içerik köprüsü)│  ─ statik sayfa üretir   │
│  ─ yayıncı              │                          │  ─ RSS, kategori, arşiv  │
└────────────────────────┘                          └────────────────────────┘
```

**Köprü:** Bot, ürettiği her raporu `web/content/reports/<tarih>-<slug>.json` olarak
yazar. Web bunları build/istek anında okuyup render eder. Şema sözleşmesi tek yerde:
Python `ReportDraft.to_document()` ↔ TypeScript `Report` arayüzü
(`web/src/lib/content.ts`). Hacim büyüyünce bu köprü bir veritabanına (Supabase/
Postgres) taşınabilir; iki tarafın da geri kalanı değişmeden kalır.

Rapor JSON'unda opsiyonel alanlar da vardır: `image` (marka kartı) ve `ipo`
(yapılandırılmış halka arz meta verisi — fiyat/iskonto/KAP tarihi/çarpanlar;
`ReportDraft.ipo` ↔ `Report.ipo` / `IpoMeta`). Alan yoksa okuyucu yedeğine
(eski regex/boş durum) düşer — şema geriye dönük uyumlu.

## bot/ — içerik motoru

`esham` Python paketi:

| Modül | Görev |
| --- | --- |
| `config` | Ortam ayarları (.env) ve loglama |
| `sources/kap` | KAP `disclosure/members/byCriteria` API — GERÇEK, doğrulanmış bildirimler |
| `sources/bist` | Yahoo Finance chart JSON API — XU100 canlı endeks |
| `sources/calendar` | TradingView ekonomik takvim API — günlük veri açıklamaları |
| `sources/viop` | VİOP kotasyonu (TradingView) + Takasbank teminat agregatı + stres |
| `sources/kap_filter` | KAP önem filtresi — rutin/idari bildirimleri eler (spam önleme) |
| `sources/sector` | Yahoo BIST sektör endeksleri — haftalık rotasyon |
| `sources/tmo` | **TMO müdahale fiyatları arşivi & analizi** — 2021-2026 resmî alım/satış/prim taban çıpası ve serbest piyasa prim spreadi |
| `sources/real_returns` | **Döviz cinsinden getiri** — TÜRİB fiyat serisinin değişimini TCMB döviz alış kuruyla (anahtarsız XML) USD/EUR'a çevirir; kur yoksa hata verir, TÜFE ile arındırılmış getiri üretilmez (kaynaklı TÜFE serisi bağlı değil) |
| `sources/storage_backtest` | **Tarımsal depolama stratejisi simülatörü** — 2020-2026 gerçek TÜRİB serileri üzerinde spot vs 3/6/9 ay depolama backtest'i (faiz, LİDAŞ kirası, fire) |
| `sources/regional_arbitrage` | **Bölgesel LİDAŞ arbitraj tarayıcısı** — Günlük bültende iller ve depolar arası brüt/net makas ve lojistik arbitraj fırsatları |
| `sources/turib` | **TÜRİB ELÜS veri kaynağı** — Hububat endeksleri (TRBHUB, TRBBGD, TRBMSR), buğday/mısır/arpa fiyat serileri ve günlük bülten |
| `sources/agri_bist` | **BIST x TÜRİB çapraz analizi** — Gıda hisseleri (ULUUN, BANVT, TATGD) ile tarımsal emtia marj duyarlılığı |
| `mcp/server` | **Unified MCP Sunucusu** — BIST ve TÜRİB piyasalarını LLM/Claude/Cursor ortamına açan model context protocol motoru |
| `sources/peer` | **Peer/değer kıyası** — sektördeki çarpanlar (F/K, PD/DD, FD/FAVÖK, temettü) + medyan, Yahoo quoteSummary (cookie+crumb) + chart API |
| `turkish` | Türkçe-doğru büyük harf + aksan-toleranslı eşleştirme (tek kaynak) |
| `state` | Kalıcı durum (seen-set, margin önceki değer, günlük sayaç, iş sağlığı) |
| `risk/margin` | Hesap bazlı teminat izleme & margin-call motoru (deterministik) |
| `evals/` | AI çıktı kalite/güvenlik kapısı — tavsiye dedektörü, grounding, biçim + **LLM-as-judge** (`judge.py`) |
| `publishing/cards` | Marka kartı üreticisi (PIL) — TEK görsel hem tweet'e hem web hero/OG'ye |
| `documents/` | PDF metin çıkarma + ilgili bölüm ayıklama (maliyet kontrolü) |
| `ai/client` | Ortak LLM istemcisi (JSON çıktı, anahtarsız `None`) |
| `ai/tweet_composer` | Ucuz model ile haber→tweet (drip akış için) |
| `ai/ipo_analyzer` | İzahname/fiyat tespit → yapılandırılmış analiz |
| `ai/financial_analyzer` | Şirket finansal raporu → red flags + oranlar |
| `analysis` | Belge → analiz → web raporu + IPO PDF orkestrasyonu |
| `publishing/content_store` | **Web köprüsü** — JSON rapor yazar |
| `publishing/ipo_pdf` | Halka arz analiz PDF/HTML raporu |
| `publishing/social` | Telegram gönderisini hazırlar (süzgeç + uyarı satırı), **giden kutusuna** yazar |
| `publishing/outbox` | Telegram giden kutusu: push sonrası en fazla bir kez gönderim (`bot/state/telegram_outbox.json`) |
| `newsletter` | **Abone deposu + SMTP bülteni** (doğrulama, imzalı çıkış, dry-run) |
| `pipeline` | Sabah raporu orkestrasyonu |
| `news_stream` | Anlık KAP/insider haber akışı (öncelikli kuyruk + drip) |

### Çalıştırma

```bash
cd bot
py -m pip install -r requirements.txt
cp .env.example .env        # anahtarları doldur (anahtarsız da çalışır)

py -m esham.main morning-report          # sabah bültenini üret + yayınla
py -m esham.main morning-report --no-social
py -m esham.main news-stream --once      # tek tur KAP taraması
py -m esham.main ipo-pdf                 # örnek halka arz raporu

# Telegram: komutlar DOĞRUDAN göndermez, giden kutusuna yazar (bot/state/telegram_outbox.json).
py -m esham.main --send-now morning-report   # yerel: komut bitince BU koşunun gönderilerini hemen gönder
py -m esham.main send-outbox                 # KURU ÇALIŞTIRMA: yerel bekleyenleri listeler, dosyaya dokunmaz
py -m esham.main send-outbox --send          # yerel GERÇEK gönderim (git işlemi yapmaz, sonucu push etmez)
# İş akışında sıra: bot koşusu → yayın kapısı (rapor başına web testleri) → commit + push → derleme/dağıtım
# → send-outbox --ci (yalnız başarılı dağıtıma girmiş sayfalar; claim push'u → gönderim → sonuç push'u).
# Uzun ömürlü 'run' / 'news-stream' (sürekli) modları yerel kayıtlarını her işten sonra kendisi gönderir.
#
# UYARI: yerel send-outbox / --send-now ve sürekli kipleri (run, news-stream) zamanlanmış iş akışıyla AYNI ANDA
# ve aynı Telegram kanalına çalıştırmayın: ayrı durum dosyaları birbirini görmez, aynı bildirim iki kez gidebilir.
# Yerel kip yalnız yerel koşuların (created_run "local-…") kayıtlarını gönderir; origin'den çekilmiş iş akışı
# kayıtlarına dokunmaz — sonucu push etmediği için iş akışının kayıtlarını yerelden göndermek çift gönderi demektir.

# Belge analizi (PDF yolu/URL, KAP linki veya ham metin kabul eder)
py -m esham.main analyze-ipo <kaynak> --company "TechYazılım A.Ş." --ticker TCHYZ
py -m esham.main analyze-company <kaynak> --company "TechYazılım A.Ş." --period 2025/Q1

# TÜRİB & ELÜS: Hububat endeksleri ve tarımsal emtia fiyatları
py -m esham.main turib

# Agri-BIST: BIST gıda şirketleri ve TÜRİB tarım emtiası çapraz marj analizi
py -m esham.main agri-bist

# Esham BIST + TÜRİB Unified MCP Sunucusu (Claude / Cursor stdio - 15 Araç)
py -m esham.main mcp

# TMO Müdahale alım fiyatları arşivi & TÜRİB serbest piyasa karşılaştırması
py -m esham.main tmo --product "BUĞDAY EKMEKLİK"
py -m esham.main tmo --list

# TÜFE enflasyonu ve TCMB kurları (USD/EUR) bazlı reel getiri analizi
py -m esham.main real-return --product "BUĞDAY EKMEKLİK" --start 2022-01-01

# Tarımsal emtia depolama stratejisi backtest motoru (2020-2026 sezonları)
py -m esham.main backtest --product "BUĞDAY EKMEKLİK" --interest 45.0

# LİDAŞ depoları arası bölgesel arbitraj taraması
py -m esham.main arbitrage --product "BUĞDAY" --freight 0.50

# VİOP: piyasa + marketwide teminat stresi + hesap margin-call kontrolü
py -m esham.main viop
py -m esham.main viop --positions hesap.json --prior-pct 0.30 --publish

# Peer/değer kıyası — sektör çarpanlarının medyanına göre göreli değerleme
py -m esham.main peer --list-sectors
py -m esham.main peer --sector bankacilik

# E-posta bülteni — abonelere son rapor özeti (SMTP yoksa dry-run)
py -m esham.main newsletter --dry-run
py -m esham.main newsletter --test-to ben@ornek.com
```

### VİOP & margin-call

İki tür teminat riski izlenir:
- **Marketwide stres** — Takasbank agregatından `margin-call / gereken teminat` oranı.
  Önceki güne göre yükselmesi, takas kurumunun teminatı sıkılaştırdığını (margin-call
  dalgası) gösterir. Takasbank doğrudan erişimi captcha/WAF ile kısıtlı olduğundan
  endpoint opsiyoneldir; yoksa gerçek yapıda örnek veriyle çalışır.
- **Hesap bazlı** (`risk/margin`) — pozisyon + güncel fiyat + teminat parametresi →
  gereken başlangıç/sürdürme teminatı vs özkaynak → margin-call/uyarı. Tamamen
  deterministik; veri kaynağından bağımsız çalışır. Teminat parametreleri Takasbank
  değerleriyle beslenmelidir (varsayılanlar temsilidir).

### KAP entegrasyonu — gerçek, doğrulanmış uç noktalar

KAP 2026'da Next.js tabanlı bir SPA'ye geçti; eski `memberDisclosureQuery` uç noktası
artık **yok** (WAF tanınmayan API yollarını sessizce yutuyor, bu yüzden sonsuz
timeout alınıyordu). Gerçek uç noktalar headless tarayıcı (Playwright) ile ağ trafiği
izlenerek bulundu ve gerçek verilerle doğrulandı:

| Amaç | Uç nokta |
| --- | --- |
| Bildirim listesi | `POST /tr/api/disclosure/members/byCriteria` |
| Bildirim detay sayfası | `GET /tr/Bildirim/{disclosureIndex}` |
| KAP'ın kendi bildirim kapağı (birkaç yüz karakter, İÇERİK DEĞİL) | `GET /tr/api/BildirimPdf/{disclosureIndex}` |
| **Gerçek ek dosya** (izahname/fiyat tespit raporu, çok sayfalı) | `GET /tr/api/file/download/{hash}` |

Kritik ayrıntı: gerçek belge içeriği `BildirimPdf` linkinde DEĞİL, ayrı bir ek
dosyadadır — hash'i sadece detay sayfasının HTML'sinde bulunur (arama sonucunda
yoktur). `KapSource.resolve_attachment_url(disclosure_index)` bunu çözer; sadece
IPO analizi tetiklendiğinde çağrılır (her taramada değil, performans için).

Gerçek verilerle uçtan uca doğrulandı: canlı bir "Fiyat Tespit Raporu" (ŞA-RA Enerji
İnşaat, TERA Yatırım aracılığıyla) indirildi, 200K karakterlik gerçek belge metninden
doğru fiyat (70,00 TL), iskonto (%20) ve halka arz büyüklüğü (6.230.000.000 TL)
çıkarıldı — kaynak belgeyle birebir eşleşti. Bu test sırasında iki ek hata bulundu ve
düzeltildi: (1) `extract_relevant` bütçesi (8000→24000 karakter) gerçek belgelerin
çoğu zaman 100-200K karakter olduğunu, fiyat sonucunun genelde giriş/metodoloji
bölümlerinden SONRA geldiğini hesaba katmıyordu; (2) AI'ın döndürdüğü `null` değerler
`_as_list`/`_as_dict` filtrelerinde `"None"` string'ine dönüşüp sızıyordu.

### KAP önem filtresi — spam önleme

`news_stream` KAP'tan gelen HER bildirimi paylaşmaz — bu, akışı gürültüye ve veri
yığılmasına boğar. `sources/kap_filter.py` deterministik, ücretsiz bir ağırlıklı
anahtar kelime skorlayıcısıdır:

- **Materiality sinyali** (pozitif ağırlık): birleşme/devralma, halka arz, kâr payı,
  sermaye artırımı, önemli sözleşme, yönetim değişikliği, dava/ceza, derecelendirme...
- **Rutin/idari** (negatif ağırlık): genel kurul çağrısı, imza sirküleri, bağımsız
  denetim sözleşmesi yenileme, yatırımcı sunumu, portföy dağılım raporu...
- Skor `ESHAM_KAP_MIN_IMPORTANCE` (varsayılan 1) eşiğini geçerse paylaşılır.
- **Insider ve IPO bildirimleri bu filtreyi atlar** — zaten ayrı, öncelikli işlem
  görürler (her zaman önemli sayılır).
- Türkçe eklemeli dil olduğu için anahtar kelimeler **kök** olarak yazılır ("devral"
  hem "devralma" hem "devraldı" ile eşleşir) ve `turkish.tr_fold()` ile aksan-toleranslı
  karşılaştırılır ("taahhüt" aksansız "taahhut" yazılmışsa da bulunur).
- Regresyon koruması: `evals/suites.py`'de 10 vakalık `kap_filter_suite()`.

### Belge analizi nasıl ucuz?

Uzun belge (izahname yüzlerce sayfa) doğrudan AI'a gönderilmez. Önce
`documents/sections.py` anahtar kelimeyle **ilgili bölümleri süzer** (fiyat tespit,
iskonto, fon kullanımı, risk faktörleri, finansal tablolar). Böylece token maliyeti
onlarca kat düşer. Analizör tek çağrıda **yapılandırılmış JSON** (fiyat, iskonto,
çarpanlar, güçlü/riskli noktalar, karar) döndürür; bu çıktı hem web raporunu hem IPO
PDF'ini besler.

> **Zarif bozulma:** API anahtarı yoksa AI devre dışı kalır ve deterministik şablon
> üretilir; bir veri kaynağı kırılırsa örnek veriyle devam edilir. Pipeline hiçbir
> adımda tümden çökmez.

### Evals — kalite/güvenlik kapısı

`py -m esham.main evals` AI çıktılarını ölçer ve başarısızsa **exit 1** döner (CI kapısı,
`.github/workflows/evals.yml`). Dört eksen:

- **Güvenlik:** çıktıda örtük/açık yatırım tavsiyesi kalıbı var mı (finansal içerikte yasak)
- **Grounding:** analizdeki sayısal değerler kaynak belgede geçiyor mu (halüsinasyon önler)
- **Biçim & metrik:** tweet ≤280, alan tamlığı; ayrıca gecikme ve tahmini maliyet
- **LLM-as-judge (kalite puanı):** analiz dört eksenli rubrikle 0-5 puanlanır —
  dayanak, tam kapsamlılık, nesnellik, açıklık; her puan gerekçelidir

Check'ler saf ve yeniden kullanılabilir — aynılar yayın öncesi **guardrail** olarak da
takılıdır (`guardrails.py`): ihlal içeren rapor/tweet `ESHAM_GUARDRAILS=enforce`
modunda hiç yayınlanmaz/gönderilmez. Anahtarsız da çalışır (fallback çıktı +
dedektör/grounding testleri).

**Judge nasıl çalışır:** `evals/judge.py::AnalysisJudge` gerçek (grounded) analize
yüksek, kaynakta olmayan sayılarla dolu (halüsinasyonlu) analize düşük "dayanak"
puanı **verebiliyor mu** — bunu ölçen iki vaka süitede. Anlık puanlama
`score_analysis(kaynak_metni, analiz)` ile çağrılabilir (yayın hattına skor olarak
eklenebilir). LLM anahtarı **yoksa** judge devre dışıdır: vaka "atlandı" olarak
işaretlenir, `evals` yine yeşildir (CI anahtarsız da çalışır).

### Marka kartları — tweet görselleri ve web hero/OG

`publishing/cards.py` (`CardGenerator`) her rapor için **gerçek veriye dayalı, marka
tutarlı** bir kart üretir (1200×630 PNG): Esham wordmark, kategori rengi (cyan/blue/
emerald/violet/amber), büyük rakam + değişim %, gerçek fiyat serisinden sparkline
(BIST/VİOP) veya sektör bar grafiği, metrik chip'leri (IPO fiyat/iskonto/büyüklük).
Fontlar (Outfit/Inter) `esham/assets/fonts/` altında gömülüdür — dış servise bağımlılık
yok, üretim tamamen yerel ve hızlı (<1sn).

**Tek görsel, iki kullanım:** `ReportDraft.image_path` ile üretilen kart hem
`ContentStore.publish()` tarafından `web/public/cards/<slug>.png`'e kopyalanır (web
hero/OG) hem `SocialPublisher.broadcast()`'e verilir (tweet medyası) — aynı görsel,
tek üretim. Kart yoksa (rapor guardrail'a takıldıysa veya üretim başarısızsa) web
tarafı `default-<kategori>.png` yedeğine düşer; dış AI görsel servisi (ör. Pollinations)
**kullanılmaz** (yavaş, markasız, deterministik değil).

> **Not:** `web/content/reports/` boşken (`output: export` + sıfır rapor) Next.js bu
> sürümde build'i tamamen reddeder. `rapor/[slug]/page.tsx` bu yüzden boş durumda bir
> sentinel param döner — repo'da en az bir gerçek rapor bulunmasa bile site build olur.

### Operasyonel dayanıklılık — "izlemezken güvenebilir miyim?"

Tam otomasyonda asıl risk çalışmıyor olması değil, **sessizce** çalışmamasıdır. Dört
katman bunu önler:

1. **Kalıcı durum** (`state.py`) — `NewsStream._seen` ve `MarginWatcher._prev_pct`
   artık `bot/state/esham_state.json`'da (atomik yazım). Render gibi platformlarda
   süreç yeniden başlasa da (deploy/uyku modu/çökme) aynı KAP bildirimi tekrar
   tweetlenmez, margin-call karşılaştırması sıfırlanmaz. Disk kalıcı değilse en kötü
   ihtimalle eskisi gibi davranır — asla daha kötü olmaz.
2. **İş sağlığı + ardışık hata uyarısı** (`scheduler.py`) — her zamanlanmış iş
   sonucu kaydedilir. Bir iş **3 kez üst üste** başarısız olursa **tek seferlik**
   bir operasyonel uyarı Telegram'a gider (halka açık Twitter'a değil); düzelince de
   tek seferlik "düzeldi" mesajı — spam yok, ama sessiz arıza da yok.
3. **Sağlık uç noktası** (`render_app.py` `/health`) — heartbeat, başarısız işler,
   günlük paylaşım sayısı, paused durumu JSON olarak döner. Heartbeat 5 dakikadan
   eskiyse `503` döner — bir uptime pinger (UptimeRobot vb.) buna bağlanıp alarm
   üretebilir.
4. **Acil durdurma + günlük kota** — `ESHAM_PAUSED=true` hem rapor yayınını hem
   sosyal paylaşımı anında durdurur (redeploy gerekir, ama tek değişken). Kota,
   `ESHAM_MAX_POSTS_PER_DAY` (varsayılan 60): bir hata/döngü API kotasını sessizce
   tüketmesin diye güvenlik ağı — sadece gerçek canlı paylaşımları sayar.

Tümü gerçek senaryolarla test edildi: restart sonrası aynı KAP haberi tekrar
işlenmiyor, margin-call karşılaştırması korunuyor, 3 ardışık hatadan sonra tek
uyarı + düzelince tek "düzeldi" mesajı, paused modda hiçbir paylaşım yapılmıyor,
günlük tavan aşılınca paylaşım sessizce durduruluyor.

## web/ — yayın katmanı

Next.js 16 (App Router) + React 19 + Tailwind 4.

| Rota | Açıklama |
| --- | --- |
| `/` | Ana sayfa, son raporlar |
| `/kategori/[category]` | bist · global · ipo · viop · gundem |
| `/rapor/[slug]` | Rapor detayı (markdown render) |
| `/feed.xml` | RSS beslemesi |

```bash
cd web
npm install
npm run dev      # http://localhost:3000
npm run build
```

## Otomasyon — günlük yayın döngüsü

`esham/scheduler.py` tüm operasyonu tek süreçte yönetir (TR saati). Varsayılan program:

| Saat (TR) | İş |
| --- | --- |
| 08:30 | Günlük bülten (sabah raporu) |
| 09:30 | VİOP açılış + teminat görünümü |
| 10:00 | BIST açılış notu |
| 18:15 | Kapanış bülteni |
| Pzt 09:00 | Haftalık sektör rotasyonu |
| sürekli | KAP/haber taraması + drip yayın (halka arz belgeleri otomatik analiz) |
| periyodik | Margin-call izleyici (teminat stresi sıçrarsa yayınlar) |

**İki dağıtım modeli:**
- **Uzun-ömürlü süreç (VPS):** `py -m esham.main run` — sürekli akış + durum-bağımlı
  margin-call izleyici burada çalışır (önerilen).
- **Stateless (GitHub Actions):** `.github/workflows/esham-schedule.yml` her işi kendi
  cron'unda çalıştırır, raporu commit'ler, web otomatik derlenir. Sürekli akış için
  15 dakikada bir tek-tur tarama yapar.

API anahtarları her iki modelde de ortam değişkeni / GitHub **secrets** olarak verilir.

## Yasal

Tüm içerik yapay zeka tarafından üretilir ve **yatırım tavsiyesi niteliği taşımaz**.
Her rapor ve site genelinde SPK uyumlu yasal uyarı gösterilir.

## Yol haritası

- [x] İzahname/fiyat tespit ve şirket finansal raporu analizörleri (yapılandırılmış)
- [x] Belge katmanı: PDF çıkarma + ilgili bölüm ayıklama (maliyet kontrolü)
- [x] Otonom zincir: `news-stream` fiyat tespit/izahname bildirimi görünce PDF'i indirip
      analizi kendiliğinden üretir, web raporu + PDF yayınlar, tweet'i analiz linkine bağlar
- [x] Gerçek veri kaynakları: KAP (memberDisclosureQuery), BIST (Yahoo chart API),
      ekonomik takvim (TradingView). Hepsi hataya dayanıklı, örnek veri fallback'li
- [x] VİOP: piyasa kotasyonu + Takasbank teminat stresi + hesap bazlı margin-call motoru
- [x] Günlük yayın orkestratörü (scheduler): bülten/açılış/kapanış/sektör + sürekli akış
      + margin-call izleyici. VPS (`run`) ve GitHub Actions cron modelleri
- [x] Sektör rotasyonu (Yahoo BIST sektör endeksleri) — haftalık rapor
- [x] Evals: AI çıktı kalite/güvenlik kapısı (tavsiye dedektörü, grounding, biçim) + CI
- [x] Guardrails: eval check'leri yayın öncesi hatta BLOKLAYICI (enforce/warn/off).
      Kötü rapor diske yazılmaz, kötü tweet gönderilmez
- [x] Gerçek sosyal paylaşım: tweepy (X API v2) + Telegram; anahtar yoksa dry-run
- [x] Gemini anahtarıyla gerçek koşu doğrulandı (google-genai SDK'sine geçildi —
      eski google-generativeai Python 3.14 ile uyumsuz); analiz modeli gemini-2.5-flash
      (ücretsiz tier'da pro çalışmıyor)
- [x] Marka kartı üreticisi (`publishing/cards.py`): gerçek veri + Esham kimliği,
      Pollinations AI (rastgele/yavaş/markasız) tamamen kaldırıldı. Tek görsel hem
      tweet hem web hero/OG'de kullanılıyor
- [x] Belge şablonu düzeltmeleri: HTML kaçış (`&`/`<`/`>`), birim tekrarı ("TL TL"),
      Türkçe aksan-toleranslı bölüm eşleştirme (taahhüt/taahhut), Gemini "thinking"
      token tükenmesi (MAX_TOKENS kesilmesi) — `thinking_config` ile çözüldü
- [x] Next.js `output: export` + sıfır rapor build hatası için sentinel fallback
- [x] KAP önem filtresi (`sources/kap_filter.py`): rutin/idari bildirimler (genel
      kurul, imza sirküleri, yatırımcı sunumu...) paylaşılmaz — spam/veri yığılması
      önlenir. Insider/IPO filtreyi atlar (her zaman önemli). Türkçe kök-tabanlı
      eşleştirme + evals regresyon koruması (10 vaka)
- [x] KAP→halka arz otomatik analiz zinciri gerçek Gemini ile uçtan uca doğrulandı
      (sentetik KAP bildirimi → filtre → belge yükleme → analiz → web raporu →
      marka kartı → linkli tweet — canlı paylaşım yapılmadan)
- [x] Operasyonel dayanıklılık: kalıcı durum (`state.py`), iş sağlığı + ardışık
      hata uyarısı (Telegram, spam yok), `/health` uç noktası, acil durdurma
      (`ESHAM_PAUSED`), günlük paylaşım kotası (`ESHAM_MAX_POSTS_PER_DAY`)
- [x] **KAP gerçek entegrasyonu** — eski `memberDisclosureQuery` uç noktası hiç
      var olmayan/kaldırılmış bir yoldu (WAF sessizce yutuyordu, bu yüzden hep
      timeout alıyorduk). Gerçek uç noktalar bulundu, doğrulandı, canlı veriyle
      uçtan uca test edildi (bkz. "KAP entegrasyonu" bölümü)
- [x] **Halka arz takvimi sayfası** — `/halka-arz-takvimi` nav + sitemap'e eklendi;
      bot artık rapor JSON'una yapılandırılmış `ipo` bloğu yazıyor (fiyat, iskonto,
      KAP bildirim tarihi, çarpanlar) — sayfa body markdown'ini regex ile sömmek
      zorunda değil (eski raporlar için regex yedeği duruyor)
- [x] **E-posta bülteni / abonelik** — `newsletter.py` (abone deposu, imzalı çıkış,
      HTML+text digest, SMTP dry-run), Render `/subscribe` + `/unsubscribe` uçları,
      web formu (`NEXT_PUBLIC_ESHAM_BOT_URL` yoksa Formspree yedeği),
      `/abonelik/cikis` sayfası, 08:40 günlük gönderim işi
- [x] **Peer/sektör karşılaştırması** — `sources/peer.py` sektör çarpanları
      (F/K, PD/DD, FD/FAVÖK, temettü, FÖK) + medyan ve göreli konumlanma;
      `py -m esham.main peer`; haftalık iş sektör ISO haftasına göre döner
- [x] **LLM-as-judge ile analiz kalitesi puanı** — `evals/judge.py` dört eksenli
      rubrik (dayanak, tam kapsamlılık, nesnellik, açıklık, 0-5); grounded vs
      halüsinasyonlu analizi ayırt ettiği eval ile ölçülür; anahtar yoksa süit
      "atlandı" olarak yeşil kalır (CI kırmaz)
- [x] **Deploy rehberi** — `DEPLOY.md`: Cloudflare Pages + Render + GitHub Secrets
      tam liste, domain bağlama, doğrulama checklist'i, sır rotasyonu uyarısı
      (canlıya alma adımları hesap tarafında tamamlanacak)
- [ ] Takasbank per-kontrat SPAN parametrelerinin canlı entegrasyonu (captcha/WAF engeli)
- [ ] KAP eklerinden (fiyat tespit PDF'i) otomatik dosya çözümü
- [ ] İçerik köprüsünün veritabanına taşınması (anlık güncelleme, arama)
