# Esham — Geliştirme Planı (güncel: 13 Kasım 2026)

Hedef: Her BIST hissesi ve her TEFAS fonu için kendi sayfası; Fintables tarzı, bilançodan hesaplanan oranlar; ilk girişte kullanıcıyı doğrudan keşfe yönlendiren bir site.

## 1. Şu an nerede (`feat/universe-ratio-engine`, push edildi, PR açılmadı)

| Alan | Durum |
| --- | --- |
| Oran motoru (`bot/esham/ratios.py`) — değerleme, karlılık, borçluluk, verimlilik, büyüme, çeyreklik seri | ✅ 12 test |
| Veri çekme (`sources/financials.py`) — Yahoo → normalize, USD/EUR → TL kur uyumu | ✅ |
| Evren (`universe.py`) — 104 hisse, 101'inde veri var (KOZAL, KOZAA, KERVT yok) | ✅ |
| `py -m esham.main stocks` → `web/public/data/stocks/`, `prices/`, `universe.json` | ✅ elle çalışıyor |
| Hisse sayfası: Finansal Oranlar kartı + 6 çeyreklik trend grafiği | ✅ |
| `/hisseler` tarayıcı (arama, sektör, hazır filtreler, sıralama) | ✅ |
| Ana sayfa: hero + arama + liderlik tabloları + sektör özeti; menü/arama 101 hisseyi kapsıyor | ✅ |
| Fon sayfaları | ❌ başlanmadı |
| Veri doğrulama (KAP ile), zamanlanmış güncelleme | ❌ |

**Bilinen eksikler / borç**
- Veri yalnızca Yahoo; çeyreklik geçmiş en fazla 5-7 çeyrek. KAP ile teyit edilmedi (DOAS temettü %24, ALBRK F/K 2,3 gibi uç değerler şüpheli).
- `stocks` işi GitHub Actions'ta yok → veri bayatlar.
- `prices/<T>.json` (5 yıllık haftalık fiyat) üretiliyor ama hiçbir yerde kullanılmıyor.
- Eski kartlar (FundamentalMetricsCard, StockPeerComparisonCard, `bist-quant-valuation.json` yalnızca 14 hisse) yeni oran seti ile çakışıyor; iki farklı F/K görünebilir.
- Hisse sayfasının üst başlığı hâlâ eski, elle yazılmış verilerden besleniyor; bot günlük içerik commit'leri JSON veriyle aynı depoda (commit gürültüsü).
- Web tarafında otomatik test yok; yalnızca build + elle kontrol.

## 2. Yol haritası

### Faz A — Birleştirmeden önce (1-2 gün) 🔴
1. **Zamanlama:** `esham-schedule.yml`'e günlük `stocks` işi (hafta içi, kapanıştan sonra; bilanço dönemlerinde sık). Bot commit'lerini `[skip ci]` kuralıyla uyumlu tut.
2. **Veri doğrulama:** 10 hisse için oranları KAP/Fintables ile elle karşılaştır, sonucu `bot/tests` altına fixture olarak ekle. `evals`'a sayısal kapı: F/K<0.5 veya temettü verimi>%15 gibi uç değerleri `quality` bayrağıyla işaretle ve ana sayfa liderlik tablolarından ele.
3. **Çakışmaları temizle:** hisse sayfasında tek oran kaynağı (yeni `stocks/<T>.json`); eski FundamentalMetricsCard'ı kaldır/yeni karta bağla; peer kartını `universe.json` medyanlarından besle.
4. **Eksik 3 hisse:** KOZAL, KOZAA, KERVT için alternatif sembol/kaynak ya da evrenden çıkar.
5. PR aç, Cloudflare Pages önizleme build'ini kontrol et (build süresi, dosya sayısı < 20.000).

### Faz B — Hisse sayfasını Fintables seviyesine taşı (1-1,5 hafta) 🟠
1. **Sekmeli yapı:** Özet · Finansallar · Oranlar · Değerleme · Teknik · KAP/Haberler · Temettü.
2. **Finansallar sekmesi:** bilanço / gelir tablosu / nakit akışı tabloları; yıllık ↔ çeyreklik geçiş; YoY değişim sütunu; TL/USD gösterim seçeneği.
3. **Fiyat grafiği:** hazır `prices/` verisiyle 1A/6A/1Y/5Y; 52 hafta aralığı; F/K ve PD/DD tarihsel bandı (fiyat ÷ TTM kâr ile hesaplanabilir).
4. **Oran bileşeni:** değer + 5Y mini grafik + sektör medyanı bandı + formül tooltip'i; "Oranlar" kartındaki metrikleri sıralı, kopyalanabilir tabloya çevir.
5. Üst özet şeridi: fiyat, değişim, piyasa değeri, 52H, F/K · PD/DD · FD/FAVÖK rozetleri.
6. SEO: sayfa başına `FinancialProduct` JSON-LD'yi gerçek verilerle (fiyat, piyasa değeri) güncelle; `generateMetadata` açıklamasına gerçek oranları koy.

### Faz C — Durum (14 Kasım 2026)

**Yapıldı:** KAP finansal rapor ayrıştırıcısı (`sources/kap_financials.py`, `esham kap-financials`). KAP bildirim sayfası IFRS/XBRL kavram kodlarıyla (`ifrs-full_Revenue`…) tabloları veriyor; birim/para birimi/konsolide bilgisi sayfada. 25 hissede Yahoo ile çapraz kontrol: **11'inde birebir aynı**, geri kalanında fark çoğunlukla **Yahoo'nun hatası** (PETKM 2026 Ç3 hasılatı Yahoo'da 82,7 mr, KAP 32,0 mr; DOAS 2026 Ç3 Yahoo'da yok; Yahoo THYAO'yu USD, KAP TL gösteriyor).
**Bulgular:** (1) KAP `byCriteria` en fazla 2000 satır döndürür; rapor sezonunda pencere bölünmeli (uygulandı). (2) Çeyreklik akım için raporun kendi "3 Aylık" sütunu kullanılır (TMS 29 fiyat seviyesi tutarlı); Ç4 = yıllık − 9 ay türetilir (`derived`). (3) Rapor başına ~5 MB HTML → bildirim numarasıyla önbellek şart.
**Sırada:** KAP'ı birincil kaynak yap (Yahoo yedek) · Actions'ta kalıcı önbellek (`actions/cache`) ve ilk doldurma (backfill) için ayrı iş · banka/sigorta taksonomisi · tüm evren.

### Değerleme ve sektör (14 Kasım 2026)

**Yapıldı:** etkileşimli reel DCF (tüm bankasız hisseler; kaydırıcılar, senaryolar, duyarlılık tablosu, `lib/dcf.ts` + 6 test) · sektörde konum bileşeni (sıra, medyan, %10–%90 aralık çubuğu, şüpheli hisseler istatistikten hariç, `lib/sector.ts` + 6 test) · NAV (KAP Genel Bilgi Formu'ndan doğrudan iştirak payları, 9 holding; `sources/kap_holdings.py`, `esham nav`, `lib/nav.ts` + 4 test) · yazı okunabilirliği (288 küçük px yazı → ölçek, 316 düşük kontrastlı gri açıldı, kök 17px).
**NAV sınırı:** KAP yalnızca DOĞRUDAN payları veriyor; ara holdingler (ör. KCHOL → Enerji Yatırımları → Tüpraş) ünvan aramasıyla güvenilir bulunamadığından dolaylı paylar yok. Bu yüzden NAV "kısmi" etiketli, listelenmeyen değer ve holding borcu kullanıcı girdisi; girdi yokken prim/iskonto gösterilmez.
**Sırada:** dolaylı pay zinciri (ara şirket sayfaları için KAP şirket OID haritası) · NAV'da listelenmeyen iştirakler için defter değeri · `npm test`'i CI'ya ekle · DCF'de kira yükümlülükleri ve azınlık payı.

### Faz C — Veri derinliği ve kapsam (1-2 hafta) 🟠
1. **KAP finansal rapor ingestion** (XBRL/FR): 5-10 yıllık çeyreklik geçmiş, gerçek TTM-ROE serisi, kalem bazlı doğruluk. Yahoo yedek kalsın; kaynak alanı JSON'a yazılsın.
2. **TMS 29 yaklaşımı:** enflasyon düzeltmeli tabloların dönemler arası karşılaştırma kuralı; UI'da uyarı yerine düzeltilmiş seri.
3. **Tüm BIST evreni** (~600): kapsam artınca sayfa sayısı için strateji — hisse sayfaları SSG, ağır seriler (fiyat, finansal tablo) istemcide `fetch`; sitemap/indeks bütçesi.
4. Kurumsal eylemler: bedelsiz/bedelli düzeltmeli fiyat; temettü geçmişi ve 5Y temettü verimi.
5. Piotroski/Altman/DuPont'u yeni motora taşı (şu an `bist_quant.py`'de ayrı, yfinance çağırıyor).

### Faz D — Fonlar (1-1,5 hafta) 🟡
1. TEFAS ingestion (kullanım şartları kontrolü): fon listesi, günlük fiyat, portföy dağılımı, yatırımcı sayısı, büyüklük.
2. Hesaplamalar: 1A/3A/YTD/1Y getiri (nominal, reel, USD), volatilite, Sharpe, maks. düşüş, kategori sıralaması.
3. `/fon/[kod]` sayfası (grafik, dağılım halkası, risk, kategori kıyası) ve `/fonlar` tarayıcısı.
4. Arama paleti ve sitemap'e fonlar; ana sayfaya "en iyi fonlar" liderlik tablosu.
5. Kapsam: önce en büyük ~200 fon, sonra tümü (≈2.000; bu noktada Faz C-3'teki istemci tarafı veri stratejisi zorunlu).

### Faz E — Kullanıcı özellikleri (1 hafta) 🟡
- `/karsilastir?a=THYAO&b=ASELS` yan yana oran + grafik.
- Watchlist'i oran bazlı hale getir (liste üzerinde F/K, ROE, günlük değişim).
- Uyarılar/bülten: "haftanın en ucuz/en yüksek ROE hisseleri" bülten bölümü; yeni bilanço açıklanınca ilgili hisse için KAP özeti.
- Tarayıcıda kayıtlı filtreler, CSV indirme, URL ile filtre paylaşımı (`?pe_max=8&roe_min=25`).

### Faz F — Kalite, performans, güvenlik (sürekli)
- Web testleri: Vitest (oran formatlama, `fold`, `buildLeaderboards`) + Playwright (ana sayfa, `/hisseler`, bir hisse sayfası, mobil).
- CI: `tsc`, `next build`, bot `pytest`, veri şeması doğrulaması (JSON Schema ile `stocks/*.json`).
- Build süresi izleme; bot veri commit'lerini ayrı bir `data` dalına/artifact'a taşıma değerlendirmesi.
- Erişilebilirlik: tablo başlıkları, klavye ile gezinme, renk dışı işaretler; Lighthouse ≥ 90 hedefi.
- Yasal: "yatırım tavsiyesi değildir" ifadesi her veri sayfasında; veri kaynağı lisans/ToS (Yahoo, TEFAS, KAP) yazılı kontrol.

## 3. Önerilen sıra ve takvim

| Hafta | İş |
| --- | --- |
| 1 | Faz A (birleştir, zamanla, doğrula) + Faz B-1/2 başlangıç |
| 2 | Faz B tamamla (sekmeler, finansal tablolar, fiyat grafiği) |
| 3-4 | Faz C (KAP ingestion, tüm evren) |
| 5-6 | Faz D (fonlar) |
| 7 | Faz E (karşılaştır, bülten) |
| süreç | Faz F |

## 4. Riskler

| Risk | Etki | Önlem |
| --- | --- | --- |
| Yahoo verisi eksik/hatalı, ToS belirsiz | Yanlış oran, itibar kaybı | Faz C KAP ingestion; uç değer bayrakları; kaynak etiketi |
| Statik export + binlerce sayfa | Build yavaşlar, Cloudflare dosya sınırı | İstemci tarafı veri, artımlı build ya da Supabase/Postgres |
| TEFAS'ın erişim kısıtları (WAF/captcha) | Fon verisi kesintili | Önbellek, yedek kaynak, hata toleranslı iş |
| TMS 29 kaynaklı karşılaştırma hataları | Yanıltıcı büyüme | Dönem bazlı uyarı + düzeltilmiş seri |
| Bot commit gürültüsü | Depo şişer | Veriyi ayrı dal/artifact'a taşı |
| Yatırım tavsiyesi algısı | Düzenleyici risk | Mevcut guardrails + tüm sayfalarda uyarı; "ucuz/pahalı" yerine nötr dil |

## 5. Karar bekleyen noktalar
1. **Veri kaynağı:** KAP ingestion'a ne zaman geçelim (Faz C'yi öne çekmek ister misiniz)?
2. **Barındırma:** Statik export'ta kalıp istemci tarafı veri mi, yoksa veritabanı + sunucu mu?
3. **Fon kapsamı:** önce en büyük 200 fon mu, tüm TEFAS evreni mi?
4. **Sayfa dili:** "en ucuz/en yüksek" gibi liderlik başlıkları yatırım yönlendirmesi sayılır mı; hukuki görüş gerekli mi?
