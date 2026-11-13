# Esham — Geliştirme Planı: Hisse/Fon Sayfaları + Fintables Tarzı Oranlar

## 1. Mevcut durum (inceleme özeti)

- **Mimari:** `bot/` (Python, içerik+veri üretir) → `web/content/reports/*.json` + `web/public/data/*.json` → `web/` (Next.js 16, `output: "export"` tamamen statik, Cloudflare Pages).
- **Hisse sayfası zaten var:** `web/src/app/hisse/[ticker]/page.tsx` (456 satır). Kartlar: DCF, KeyLevels, FundamentalMetrics, FinancialHealth, Peer, KurumsalEylemler, grafik, ilgili raporlar.
- **Asıl darboğaz veri kapsamı:** `bist-quant-valuation.json` sadece **14 hisse** içeriyor (THYAO, ASELS, TUPRS, BIMAS, EREGL, KCHOL, PGSUS, FROTO, SISE, SAHOL, PETKM, TCELL, TTKOM, ULUUN). Sayfa ise ~50 ticker için üretiliyor → çoğu sayfa boş/yarım. Ticker bandı 29 hisse.
- **Oranlar:** yalnızca F/K, PD/DD, FD/FAVÖK, net marj, ROE — Yahoo `quoteSummary` anlık özet değerleri. Çeyreklik bilanço tablosu, geçmiş seri, sektör/geçmiş kıyası yok.
- **Fon:** hiç yok (TEFAS ile ilgili kod/sayfa bulunmuyor).
- **Tasarım:** koyu tema (#0a0a0a), amber vurgu (#e8a030), Outfit/Inter, inline `style` + Tailwind karışık. Tutarlı ama kart başına tekrar eden stil; mobil/arama/watchlist mevcut. `hisse/[ticker]/page.tsx` içindeki şirket adı sözlüğü elle yazılmış.
- Ek gözlem: repoda `run_log.txt`, `kap_test.json`, `kap_detail.html`, `imghdr.py` gibi kök/bot çöp dosyaları var; bot her gün commit atıyor (1700+ rapor JSON).

## 2. Hedef

Her BIST hissesi ve her TEFAS fonu için **kendi sayfası**; Fintables benzeri **finansal tablo + oran hesaplama** (tüm oranlar bilançodan kendi kodumuzla hesaplanır, kaynak şeffaf).

## 3. Veri katmanı (önce bu — her şey buna bağlı)

| Veri | Kaynak seçeneği | Not |
| --- | --- | --- |
| BIST evreni (~600 hisse, ad, sektör, endeks üyeliği) | KAP şirket listesi / Borsa İstanbul | Tek `universe.json`; elle sözlük kalkar |
| Fiyat geçmişi (OHLCV) | Yahoo chart (zaten kullanılıyor) | Günlük, 5 yıl; hisse başına `prices/<T>.json` |
| **Finansal tablolar** (bilanço, gelir, nakit akış; çeyreklik/yıllık) | **KAP finansal rapor (XBRL/FR)** birincil; Yahoo fundamentals yedek | Fintables'ın çekirdeği. TFRS, enflasyon düzeltmeli (TMS 29) farkı işaretlenmeli |
| Temettü/bedelli-bedelsiz | KAP + mevcut `bist_corporate_actions` | Düzeltilmiş fiyat için gerekli |
| Fon (fiyat, portföy dağılımı, getiri, risk) | **TEFAS** (fiyat/dağılım API'leri) | Fon başına `funds/<KOD>.json`, ~2000 fon |
| Makro (TÜFE, USD/TRY) | Mevcut `real_returns` | Reel/dolar bazlı getiri için |

Dosya düzeni: `web/public/data/stocks/<T>.json`, `web/public/data/funds/<KOD>.json`, `universe.json`. Statik export'ta 600+2000 sayfa build süresini artırır → ya JSON'u client'ta çekeriz (sayfa iskeleti statik, veri `fetch`) ya da yalnızca hisse için SSG, fon için client fetch. **Karar gerekli (bkz. §7).**

## 4. Oran motoru (`bot/esham/analysis/ratios.py`, saf fonksiyonlar + testler)

Girdi: çeyreklik finansal tablolar + fiyat. Çıktı: oran + geçmiş seri + sektör medyanı.

- **Değerleme:** F/K, PD/DD, FD/FAVÖK, FD/Satışlar, PEG, temettü verimi, serbest nakit akışı verimi
- **Karlılık:** brüt/faaliyet/FAVÖK/net marj, ROE, ROA, ROIC
- **Büyüme:** satış, FAVÖK, net kâr — yıllık ve çeyreklik YoY/QoQ, 3-5Y CAGR
- **Borçluluk/likidite:** net borç/FAVÖK, borç/özkaynak, faiz karşılama, cari oran, asit-test
- **Verimlilik:** stok/alacak/borç devir günleri, nakit döngüsü, aktif devir hızı
- **Kalite skorları:** Piotroski F-skoru, Altman Z, Beneish M (opsiyonel)
- **Kritik doğruluk kuralları:** TTM (son 4 çeyrek) hesabı; bilanço kalemleri için dönem sonu, akım kalemleri için kümülatif→çeyrek dönüşümü; finansal şirketler (banka/sigorta) için ayrı oran seti (FAVÖK/FD anlamsız); enflasyon muhasebesi dipnotu; negatif/0 payda → `null`, "N/A" gösterimi.
- **Testler:** bilinen 3-4 şirket için elle doğrulanmış oran fixture'ı; mevcut `evals` yapısına sayısal grounding eklenir.

## 5. Web / tasarım

**Hisse sayfası (`/hisse/[ticker]`) — sekmeli yapı:** Özet · Finansallar (bilanço/gelir/nakit, yıllık↔çeyreklik) · Oranlar (tablo + sparkline + sektör kıyası) · Değerleme (DCF, mevcut) · Teknik (mevcut) · Haberler/KAP · Temettü & Eylemler · Benzer şirketler.
- Üst şerit: fiyat, günlük değişim, piyasa değeri, 52H aralığı, F/K · PD/DD · FD/FAVÖK · temettü rozetleri.
- "Oran" bileşeni: değer + 5Y geçmiş mini grafik + sektör medyanına göre renk bandı (ucuz/pahalı) + tooltip'te formül.

**Fon sayfası (`/fon/[kod]`):** fiyat grafiği, 1A/3A/YTD/1Y getiri (nominal + reel + USD), portföy dağılımı (halka), yönetim ücreti/stopaj, risk (volatilite, Sharpe, max düşüş), kategori kıyası, büyüklük/yatırımcı sayısı trendi.

**Liste/keşif:** `/hisseler` (filtrelenebilir tarayıcı: sektör, F/K aralığı, ROE vb.), `/fonlar` (kategori, getiri sıralaması), arama paletine fon+hisse birleşik indeks, `/karsilastir?a=THYAO&b=ASELS`.

**Tasarım iyileştirmeleri:** ortak `<Card>`, `<Stat>`, `<RatioRow>`, `<DataTable>` primitifleri (inline style tekrarı azalır); sayısal sütunlar tabular-nums + sağa hizalı; Türkçe sayı biçimi (1.234,56) tek util; sticky sekme çubuğu; mobilde yatay kaydırılan tablolar; erişilebilir renk (yeşil/kırmızı yanında ok/işaret); SEO: sayfa başına JSON-LD (`FinancialProduct`), sitemap'e hisse+fon.

## 6. Fazlar

1. **Faz 0 — Temizlik (0,5 gün):** kök çöp dosyaları sil, hisse adı sözlüğünü `universe.json`'a taşı, bot commit'lerini içerik dalına ayırmayı değerlendir.
2. **Faz 1 — Evren + fiyat (2-3 gün):** `universe.json`, tüm BIST için fiyat serisi, mevcut hisse sayfasında boş durumların düzgün gösterimi.
3. **Faz 2 — Finansal tablolar + oran motoru (1-1,5 hafta):** KAP/Yahoo ingestion, `ratios.py`, testler, 14 → ~100 (BIST100+), sonra tüm hisse.
4. **Faz 3 — Hisse sayfası yeniden tasarımı (1 hafta):** sekmeler, Oranlar/Finansallar bileşenleri, tarayıcı sayfası.
5. **Faz 4 — Fonlar (1-1,5 hafta):** TEFAS ingestion, getiri/risk hesapları, `/fon/[kod]`, `/fonlar`.
6. **Faz 5 — Karşılaştırma, uyarılar, SEO, performans (1 hafta).**

## 7. Karar bekleyen noktalar

1. **Veri kaynağı:** KAP finansal raporları (doğru ama zor: XBRL ayrıştırma) vs. Yahoo fundamentals (kolay ama BIST'te eksik/hatalı olabilir)? Önerim: Yahoo ile başla, KAP ile doğrula/yedekle.
2. **Barındırma:** Statik export (Cloudflare Pages) ile 2600 sayfa mümkün ama build yavaşlar; alternatif veriyi client'ta fetch etmek ya da Supabase/Postgres'e geçmek (README'de zaten öngörülmüş).
3. **Kapsam:** önce BIST100 + en büyük 200 fon mu, yoksa baştan tüm evren mi?
4. **Yasal:** tavsiye içermeyen dil (mevcut `guardrails`/`Disclaimer` korunur), veri kaynağı lisans/kullanım şartları (TEFAS, KAP) kontrol edilmeli.
