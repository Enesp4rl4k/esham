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

## bot/ — içerik motoru

`esham` Python paketi:

| Modül | Görev |
| --- | --- |
| `config` | Ortam ayarları (.env) ve loglama |
| `sources/kap` | KAP `memberDisclosureQuery` API — bildirimler (savunmacı parse) |
| `sources/bist` | Yahoo Finance chart JSON API — XU100 canlı endeks |
| `sources/calendar` | TradingView ekonomik takvim API — günlük veri açıklamaları |
| `sources/viop` | VİOP kotasyonu (TradingView) + Takasbank teminat agregatı + stres |
| `risk/margin` | Hesap bazlı teminat izleme & margin-call motoru (deterministik) |
| `evals/` | AI çıktı kalite/güvenlik kapısı — tavsiye dedektörü, grounding, biçim |
| `documents/` | PDF metin çıkarma + ilgili bölüm ayıklama (maliyet kontrolü) |
| `ai/client` | Ortak LLM istemcisi (JSON çıktı, anahtarsız `None`) |
| `ai/tweet_composer` | Ucuz model ile haber→tweet (drip akış için) |
| `ai/ipo_analyzer` | İzahname/fiyat tespit → yapılandırılmış analiz |
| `ai/financial_analyzer` | Şirket finansal raporu → red flags + oranlar |
| `analysis` | Belge → analiz → web raporu + IPO PDF orkestrasyonu |
| `publishing/content_store` | **Web köprüsü** — JSON rapor yazar |
| `publishing/ipo_pdf` | Halka arz analiz PDF/HTML raporu |
| `publishing/social` | Twitter/X ve Telegram paylaşımı |
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

# Belge analizi (PDF yolu/URL, KAP linki veya ham metin kabul eder)
py -m esham.main analyze-ipo <kaynak> --company "TechYazılım A.Ş." --ticker TCHYZ
py -m esham.main analyze-company <kaynak> --company "TechYazılım A.Ş." --period 2025/Q1

# VİOP: piyasa + marketwide teminat stresi + hesap margin-call kontrolü
py -m esham.main viop
py -m esham.main viop --positions hesap.json --prior-pct 0.30 --publish
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
`.github/workflows/evals.yml`). Üç eksen:

- **Güvenlik:** çıktıda örtük/açık yatırım tavsiyesi kalıbı var mı (finansal içerikte yasak)
- **Grounding:** analizdeki sayısal değerler kaynak belgede geçiyor mu (halüsinasyon önler)
- **Biçim & metrik:** tweet ≤280, alan tamlığı; ayrıca gecikme ve tahmini maliyet

Check'ler saf ve yeniden kullanılabilir — aynılar ileride yayın öncesi **guardrail** olarak
da takılabilir. Anahtarsız da çalışır (fallback çıktı + dedektör/grounding testleri).

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
- [ ] Deploy: git repo + Vercel + Actions secrets (domain/anahtar kararları)
- [ ] Gemini anahtarıyla gerçek koşu + AI çıktı doğrulaması
- [ ] LLM-as-judge ile analiz kalitesi puanı
- [ ] Takasbank per-kontrat SPAN parametrelerinin canlı entegrasyonu (captcha/WAF engeli)
- [ ] KAP eklerinden (fiyat tespit PDF'i) otomatik dosya çözümü
- [ ] Peer/sektör karşılaştırması ile değerleme (çarpan kıyası)
- [ ] E-posta bülteni / abonelik
- [ ] Halka arz takvimi sayfası
- [ ] İçerik köprüsünün veritabanına taşınması (anlık güncelleme, arama)
