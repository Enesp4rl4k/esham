# Esham — Ürün, SEO ve Pazarlama Planı (20 Kasım 2026)

Bu belge `ARCHITECTURE_REVIEW.md` (teknik sağlamlık) ve `GELISTIRME_PLANI.md` (veri/özellik) belgelerinin ürün ve büyüme tarafıdır. Tasarım taslakları: Claude Design tuvali *"Esham — Yeni Yapı Tasarımı"* (ana sayfa masaüstü/mobil, hisse sayfası, bilgi mimarisi).

## 0. Verilen kararlar
| Konu | Karar |
| --- | --- |
| Konumlandırma | **Hisse analiz aracı** (haber/analiz ikincil) |
| Gelir | **Önce büyüme**, gelir kararı 3-6 ay sonra; ölçüm altyapısı önce |
| Alan adı | **Özel alan adı alınacak** (ör. esham.com.tr) |
| Depo | Herkese açık (Actions ücretsiz) |

## 1. Neredeyiz — ölçümler
**Yapı ve deneyim**
- Menüde 11 farklı hedef, sitede 14 sayfa türü; ana sayfa haber akışı + 9 modül: ilk girişte "bu site ne için?" sorusunun cevabı yok.
- Ana ürün (hisse sayfaları, tarayıcı) menüde 1 öğe; bülten formu ana sayfanın **en altında tek yerde**, hisse sayfalarında yok.
- Haber akışı (1.762 otomatik rapor) siteyi yönetiyor; hisse sayfası (112) kendi arama niyetine sahip olan asıl varlık.

**SEO (üretim HTML'i taranarak, 112 hisse + 1.762 rapor + 8 ana sayfa)**
| Bulgu | Ölçüm | Etki |
| --- | --- | --- |
| Çift marka eki ("… \| Esham \| Esham") | **112/112 hisse sayfası** + tarayıcı, emtia, temettü, radar sayfaları | Başlık gereksiz uzar, kesilir, marka tekrarı |
| Rapor başlığı > 60 karakter | 1.197 / 1.762 (**%68**) | SERP'te kesilir |
| Rapor açıklaması > 160 karakter | 391 | Kesilir |
| Tekrar eden başlık / açıklama | 104 başlık, 167 açıklama | Kopya algısı |
| URL slug uzunluğu | medyan 83, **1.014 adet > 75**, 95 adet > 150, en uzun 239 karakter | Paylaşılabilirlik ve tıklanabilirlik düşük |
| İnce içerik | 531 rapor (**%30**) < 300 kelime; medyan 334 | Otomatik üretim + ince sayfa riski (kalite sinyali) |
| robots.txt | `Disallow: /_next/` | Google'ın sayfayı işlemesi için gereken JS/CSS engelli |
| Open Graph görseli | Hisse ve emtia sayfalarında yok | Sosyal paylaşımda görselsiz kart |
| Analitik / Search Console | **Hiçbiri** | Hiçbir şey ölçülemiyor |
| Alan adı | esham.pages.dev | Marka ve güven zayıf; alt alan adı otoritesi paylaşılmaz |
| Olumlu | Her sayfada canonical, tek H1, JSON-LD (NewsArticle, Breadcrumb), site haritası (1.890 URL), RSS, hisse sayfası medyan 1.322 kelime | Temel sağlam |

## 2. Ürün stratejisi
**Vaat:** *"Borsa İstanbul'daki her hisseyi rakamlarla anla."* Oranlar bilançodan hesaplanır, hesabın kaynağı satırın yanında yazar.

**Hedef kullanıcı (varsayım, doğrulanacak):** bireysel BIST yatırımcısı; hisse araştıran, F/K ve bilançoya bakan, 1-5 yıllık bakış. İş: *"Bu hisse ucuz mu, sağlam mı, sektörüne göre nerede?"*

**Farklılaşma (şu an sahip olduklarımız):** (1) her oranın sektördeki konumu, (2) etkileşimli reel DCF + NAV (Türkiye'de hisse başına yaygın değil), (3) veri güvenilirliğinin açık gösterimi (kaynak, tarih, şüpheli veri bayrağı), (4) günlük otomatik piyasa akışı. **Kapanmayan açık:** veri kalitesi (Yahoo → KAP), fonlar, karşılaştırma, bilanço tarihçesi.

**İlke:** ürün önce, yayın ikinci. Haber sayfaları hisse sayfalarını besleyen yardımcı içerik olur.

## 3. Bilgi mimarisi ve sayfa şablonları (tasarım: "Bilgi mimarisi" tuvali)
**Menü 5 başlık:** Hisseler · Fonlar (Faz D) · Piyasa · Analizler · Araçlar.
- *Hisseler:* tarayıcı, hisse sayfası, **sektör sayfaları**, **karşılaştırma**, endeks sayfaları (BIST 30/100).
- *Piyasa:* temettü/halka arz takvimi, geri alımlar, devalüasyon radarı, emtia, VİOP.
- *Araçlar:* DCF, NAV, izleme listesi, yöntem ve kaynaklar.

**Ana sayfa (tasarım: "Ana sayfa" tuvalleri):** tek soru, tek eylem. Sırayla: arama (büyük) → ürün önizlemesi (gerçek hisse, konum çubuğu) → hazır taramalar + sektörler → "Piyasa bugün" (haber, 1 öne çıkan + 4) → bülten → alt bilgi. Kullanıcı düzeni özelleştirebilir (mevcut "Sayfayı düzenle" korunur).

**Hisse sayfası şablonu:** başlık (fiyat, oranlar, 52H konum çubuğu) → sekmeler → ana sütun (fiyat, **sektörde konum**, KAP/haber) + sağ ray (**hızlı değerleme**, **veri güvenilirliği**, bülten). Mobilde sağ ray ana sütunun altına iner.

**URL planı** (mevcutlar korunur, yenileri eklenir):
`/hisse/THYAO` · `/hisseler/sektor/bankacilik` · `/hisseler/tarama/dusuk-fk` · `/karsilastir/THYAO-vs-PGSUS` · `/endeks/bist-30` · `/analiz/<kısa-slug ≤ 75 kr>` · `/fon/<KOD>` (Faz D).

## 4. Tasarım sistemi (taslakta uygulanan)
- **Açık tema öncelikli, koyu tema seçenekli** (sistem tercihine uyar). Gerekçe: yoğun veri tabloları açık zeminde daha rahat okunur; HIG: *"Ensure that your app looks good in both appearance modes"*.
- Paleti: serin kâğıt zemin `#F3F5F8`, yüzey `#FFFFFF`, mürekkep `#0E1726` (18:1), yardımcı metin `#4B566B` (7,4:1), yükseliş `#0B7A4B`, düşüş `#B42318`. **Amber yalnızca imza öğesinde ve birincil vurguda.**
- Yazı: Schibsted Grotesk (başlık) + Inter (gövde ve veri, `tabular-nums`). İki aile.
- **İmza: konum çubuğu.** Tek görsel dil üç yerde: 52 haftalık aralıkta fiyat, sektör medyanına göre oran, DCF değerine göre fiyat. Kullanıcı bir kez öğrenir, her yerde okur.
- Erişilebilirlik tabanı: gövde ≥ 16 px, dokunma hedefi ≥ 44 px, renk tek başına anlam taşımaz (▲▼ + metin), tüm kontrastlar ≥ 4,5:1 (hesaplandı).
- *Teknik not:* mevcut sitede yüzlerce `zinc-*` sınıfı var; açık tema için önce renk belirteçlerine (CSS değişkenleri) geçiş gerekir (Faz 2).

## 5. SEO planı
### 5.1 Teknik (hemen, düşük riskli)
1. **Çift marka eki** düzelt (112 hisse + 5 sayfa).
2. `robots.txt`: `/_next/` engelini kaldır.
3. **Başlık ve açıklama üst sınırı:** rapor başlıkları ≤ 60, açıklamalar ≤ 155 karakter (akıllı kesim); tekrarlayan otomatik başlıklara tarih eki.
4. Hisse ve emtia sayfalarına **Open Graph görseli** (önce varsayılan, sonra hisse başına üretilmiş kart: ticker + fiyat + 52H çubuğu).
5. **Analitik ve doğrulama:** Cloudflare Web Analytics (çerezsiz) + Search Console doğrulama etiketi (ortam değişkeniyle).
6. Site haritasını bölümle (hisse, analiz, araç), `lastmod` gerçek veri tarihi olsun.

### 5.2 Alan adı geçişi (alan adı alınınca)
1. Cloudflare Pages'e özel alan ekle; `esham.pages.dev` → yeni alan adına **301** (Pages'te `_redirects` / alan ayarı).
2. Canonical, sitemap, `metadataBase`, JSON-LD ve OG URL'lerini yeni alan adına çevir (tek `SITE_URL` sabiti).
3. Search Console'a **alan (domain) mülkü** ekle, eski mülkte "Adres değişikliği" aracını kullan.
4. İlk 2 hafta sıralamayı izle; geçici dalgalanma normaldir.

### 5.3 Programatik sayfalar (en büyük fırsat)
Her hisse bir arama sorgusu. Eklenecek indekslenebilir şablonlar (her biri benzersiz içerik + veri taşır, kopya değil):
| Şablon | Sayı | Örnek arama niyeti |
| --- | --- | --- |
| Sektör sayfaları | ~24 | "bankacılık hisseleri F/K oranları" |
| Hazır tarama sayfaları | ~10 | "F/K'sı düşük hisseler", "temettü verimi yüksek hisseler" |
| Endeks sayfaları | 2-3 | "BIST 30 hisseleri F/K" |
| Karşılaştırma (aynı sektör çiftleri) | seçilmiş ~150 | "THYAO PGSUS karşılaştırma" |
| Fon sayfaları (Faz D) | 200 → ~2.000 | "AFT fonu getirisi" |
**Kalite kapısı:** bir sayfa en az 300 kelime özgün yorum + tablo/grafik içermiyorsa `noindex` (şablon, otomatik üretilen metin boşluğu doldurmasın). Tarama sayfalarında sonuç sayısı, sektör medyanı, tarih ve yöntem notu zorunlu.

### 5.4 İçerik stratejisi
- **Otomatik rapor politikası:** 531 ince rapor (< 300 kelime) iki gruba ayrılır: KAP bildirim özetleri (`noindex, follow`, hisse sayfasından erişilir) ve değerli olanlar (bülten, haftalık özet, sektör analizi) indekslenir. Amaç: indeks kalitesini yükseltmek, taramayı hisse sayfalarına yönlendirmek.
- **Slug ve başlık standardı:** yeni raporlarda slug ≤ 75 karakter, başlık ≤ 60. Mevcut uzun slug'lar **değiştirilmez** (1.762 yönlendirme Cloudflare'in 2.000 statik yönlendirme sınırına çok yakın); yalnızca yeni içerikte uygulanır.
- **Özgün, bağlantı çeken içerik (ayda 2-4):** "BIST'te en ucuz 10 hisse (nasıl hesaplandı)", sektör rehberleri, bilanço sezonu özetleri, "F/K nedir, nasıl yorumlanır" (terimler sözlüğü, uzun kuyruk sorgular).
- **E-E-A-T:** *Yöntem ve kaynaklar* sayfası (formüller, veri kaynağı, güncelleme sıklığı, sınırlar), yazar/ekip sayfası, açık düzeltme politikası. Finans içeriği "Your Money or Your Life" kategorisindedir; güven sinyali zorunlu.
- **İç bağlantı:** her hisse sayfasından sektör sayfasına, benzer hisselere, taramalara; sektör ve tarama sayfalarından hisse sayfalarına. Rapor sayfalarındaki `$TICKER` etiketleri hisse sayfasına bağlansın.
- **Yapılandırılmış veri:** hisse sayfasında `Corporation` + `FinancialProduct` ve `Dataset` (oran tablosu), SSS bölümlerinde `FAQPage`, araç sayfalarında `WebApplication`.

### 5.5 Performans
Hedef: LCP < 2,5 sn, CLS < 0,1 (mobil). Ölçüm Search Console Core Web Vitals + Lighthouse CI. Kritik: yazı tipi `latin-ext` doğru yüklensin (yapıldı), görsel boyutları, ana sayfada ağır istemci bileşenlerinin ertelenmesi.

## 6. Pazarlama ve büyüme
**Prensip:** ürün arama ve bültenle büyür; ücretli kanal yok.
**Huni:** arama/sosyal → hisse sayfası → *aha anı* (sektörde konum, DCF) → izleme listesine ekle → bülten aboneliği → geri dönüş.

| Kanal | Rol | İlk 90 gün |
| --- | --- | --- |
| Arama (SEO) | Ana edinim | §5 programatik sayfalar + özgün içerik |
| Bülten | Geri dönüş ve sadakat | 3 yerleşim (ana sayfa, hisse sayfası sağ ray, yazı sonu); hisse bazlı konu ("bilanço açıkladığında haber ver"); doğrulamalı çift onay (KVKK) |
| X/Twitter (`@eshamcomtr`), Telegram | Dağıtım | Günlük kapanış kartı + haftalık "en ucuz/yüksek ROE" liste; bot zaten kart üretiyor |
| Topluluklar | İlk kullanıcılar | Yatırım forumları ve gruplarında yöntemi açıklayan paylaşım (reklam değil, hesap şeffaflığı) |
| Ortaklıklar | Link ve güven | Finans bloglarına/podcastlere veri sağlama (alıntıda atıf) |
| Paylaşım | Viral döngü | Her hisse ve tarama sayfasında "paylaş" kartı (üretilmiş OG görseli) |

**Aktivasyon ölçütü (öneri):** bir oturumda ≥ 2 hisse sayfası + (sekme görüntüleme veya izleme listesi ekleme).
**Geri dönüş:** izleme listesi sunucusuz (localStorage) çalışıyor; bülten onun dışında tek kalıcı bağ → bülten önceliği yüksek.

## 7. Ölçüm
**Altyapı (ilk hafta):** Cloudflare Web Analytics (çerezsiz, KVKK dostu) + Search Console. Olay sözlüğü (özel olaylar, çerezsiz): `arama_kullanildi`, `tarama_acildi`, `sekme_goruntulendi`, `dcf_degistirildi`, `izleme_eklendi`, `bulten_kaydi`, `duzen_degistirildi`.

**KPI ağacı:** Aylık organik ziyaretçi → hisse sayfası/oturum → aktivasyon oranı → bülten dönüşümü → 30 günde geri dönen kullanıcı.
**Taban çizgisi:** ölçüm kurulmadan hedef yazmak yanıltıcı; ilk 4 haftada taban alınır, ardından 90 günlük hedefler (örn. organik trafikte 3×, bülten dönüşümü > %2) belirlenir.

## 8. Yol haritası
| Faz | Süre | İçerik | Bitti sayılır |
| --- | --- | --- | --- |
| **0 — SEO temeli** (bu PR) | 1-2 gün | Çift ek, robots, başlık/açıklama sınırı, OG varsayılanı, analitik/GSC kancaları, plan | 112 hisse sayfasında tek marka eki; robots `_next` serbest |
| **1 — Yapı** | 1-2 hafta | Yeni ana sayfa (hero + arama + taramalar + piyasa bugün), 5 başlıklı menü, bülten yerleşimleri, kategori sayfaları indeks politikası | İlk ekranda vaat + arama; menü 5 başlık |
| **2 — Tasarım sistemi** | 2 hafta | Renk belirteçleri (CSS değişkenleri), açık/koyu tema, konum çubuğu bileşeni, mobil sağ ray | Sistem temasına uyan site |
| **3 — Programatik SEO** | 2-3 hafta | Sektör, tarama, endeks sayfaları; karşılaştırma; hisse başına OG kartı; sitemap bölümleri | ~40 yeni şablon sayfası indekslenebilir, kalite kapısı geçti |
| **4 — Alan adı ve güven** | 1 hafta | Alan adı geçişi (§5.2), Yöntem ve kaynaklar, ekip sayfası, düzeltme politikası | 301'ler yayında, GSC taşındı |
| **5 — Veri ve kapsam** (GELISTIRME_PLANI Faz C/D) | sürekli | KAP birincil kaynak, fonlar, karşılaştırma aracı | Fon sayfaları, KAP verisi |
| **6 — Büyüme** | sürekli | Sosyal kartlar, ortaklıklar, bülten deneyleri, aylık özgün içerik | Aylık KPI raporu |

## 9. Riskler ve açık kararlar
| Risk / karar | Not |
| --- | --- |
| Otomatik içerik kalite algısı | `noindex` kapısı ve özgün içerik oranı; Google'ın "ölçekli düşük değerli içerik" politikası |
| Yatırım tavsiyesi sınırı | Dil nötr kalmalı ("ucuz/pahalı" yerine "medyana göre"); sayfa başına uyarı; hukuki görüş önerilir (SPK) |
| Veri doğruluğu | Yahoo hataları kanıtlı (PETKM, DOAS); KAP birincil olana kadar "teyit edilmemiştir" notu şart |
| Alan adı geçişi | Kısa süreli sıralama dalgalanması; 301 ve GSC taşıma adımları birebir uygulanmalı |
| Gelir modeli (3-6 ay) | Hesap sistemi ve ücretli katman kararı ölçüm verisiyle |
| **Karar:** alan adı | Önerilen ad(lar) ve satın alma sizde |
| **Karar:** tema | Açık tema öncelikli yön onayı (taslak üzerinden) |
