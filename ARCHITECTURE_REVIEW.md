# Esham — Mimari Değerlendirme (20 Kasım 2026)

Soru: *"Mevcut mimari doğru mu, sitenin akışı sağlam mı?"* Aşağıdaki her bulgu ölçüme dayanır; ölçülemeyen yerlerde bunu açıkça yazdım.

## 1. Mevcut mimari

```
GitHub Actions (zamanlanmış, ~13 çalışma/gün)
  └─ bot/ (Python): KAP · Yahoo · TÜRİB · AI → JSON
        │  git commit + push → master        ← depo = veritabanı
        ▼
  web/ (Next.js 16, output:"export") → statik HTML → Cloudflare Pages (wrangler)
        ▲
  web/content/reports/*.json (1.762 rapor) · web/public/data/*.json · web/public/cards/* (164 MB görsel)
```

Güçlü yanları: tek bir sözleşme (JSON), sunucu yok, çok ucuz barındırma, hızlı sayfalar, hata durumunda "zarif bozulma" (anahtarsız çalışan bot).

## 2. Bulgular

| # | Önem | Bulgu | Kanıt | Durum |
| --- | --- | --- | --- | --- |
| F1 | **Kritik** | Zamanlanmış akış 16 Kasım'dan beri **hiç başlamıyor**; site 13 Kasım'dan beri güncellenmedi. Neden GitHub'ın kendi mesajı: *"recent account payments have failed or your spending limit needs to be increased"* | Son 60+ çalışma `failure`, süre **2 sn**, adım yok; iş annotation'ı yukarıdaki metin; `master`'daki son içerik commit'i 13 Kasım 22:36 | **Sizin eyleminiz gerekli** (Settings → Billing). Tespit için `health.yml` eklendi |
| F2 | **Kritik** | Statik çıktı **19.115 dosya**; Cloudflare Pages sınırı **20.000**. ~6 rapor/gün × ~9 dosya → **~16 gün** sonra (≈5 Aralık) dağıtım reddedilirdi | `rapor/` = 15.858 dosya: 1.762 `.html` + 14.096 `.txt` (her sayfa için 7 istemci-prefetch parçası) | **Düzeltildi:** `postbuild` budama → **5.948 dosya** (−%69); rapor başına 9 → 2 dosya, ~3 yıllık pay |
| F3 | Yüksek | Hatalar yutuluyordu: dağıtım adımı `continue-on-error: true`; içerik push'u `git push ... \|\| true`. Dağıtım kırılsa iş yeşil kalır, kimse bilmezdi | `esham-schedule.yml` (satır 161-162, 177) | **Düzeltildi:** yeniden denemeli push + gerçek hata; ayrı derleme/dağıtım adımları, sessiz yutma yok |
| F4 | Yüksek | Web kodu için **hiç CI yoktu** (tsc/test/build). Dağıtım yalnızca zamanlanmış içerik akışının içindeydi: bir PR birleşince **site güncellenmiyordu** | `evals.yml` yalnızca `bot/**`; dağıtım yalnızca `esham-schedule.yml` | **Düzeltildi:** `web-ci.yml` (PR), `deploy.yml` (master'a web değişikliği birleşince) |
| F5 | Yüksek | Ana sayfada **React #418 hydration hatası**: `MorningCockpit` render sırasında bugünün tarihini yazıyor; statik HTML derleme gününü taşır. `TickerBand`/emtia saatleri derleme makinesinin saat dilimine bağlı (CI = UTC, kullanıcı = İstanbul) | Tarayıcı konsolu; kaynak `new Date().toLocaleDateString` | **Düzeltildi:** tarih yalnızca istemcide, tüm saat biçimleri `Europe/Istanbul` sabit |
| F6 | Orta | Depo şişiyor: 976 commit'in **883'ü (%90) bot**, `.git` 154 MB, `web/public/cards` **164 MB / 1.786 görsel** depoda | `git count-objects`, `du` | Plan (§4): görseller R2'ye / üretimi derlemeye |
| F7 | Orta | Dakika modeli kırılgan: özel depoda ücretli kota; normal günlerde ~50-100 dk/gün (kota altında) ama 11 Kasım'da **6.280 dk'lık** açıklanamayan uç değer (muhtemelen takılı iş). Faturalama durumu **ölçülemedi** | `gh run list` süreleri; ücret bilgisine erişim yok | Karar gerekli (§3) |
| F8 | Orta | Tek veri kaynağı bağımlılığı: oranlar Yahoo'ya (kanıtlanmış hatalar: PETKM, DOAS) dayanıyor; KAP ayrıştırıcısı var ama siteye bağlı değil; `stocks/*.json` için şema doğrulaması yok | Faz C çapraz kontrolü (25 hissede 11'i birebir) | Plan: KAP'ı birincil yap + JSON Schema |
| F9 | Orta | Birleşmemiş PR zinciri (#2→#3→#4→#5, + bu dal): entegrasyon riski ve "bitti ama canlıda değil" durumu | `gh pr list` | Süreç: sırayla birleştir |
| F10 | Düşük | Lint CI'da yok (ESLint yapılandırılmış ama çalıştırılmıyor); web testleri yalnızca `src/lib`; uçtan uca test yok | `package.json`, workflow'lar | Plan: Playwright ile 3 akış |

## 3. Asıl mimari soru: "depo = veritabanı + statik dışa aktarma" doğru mu?

| Seçenek | Artı | Eksi | Ne zaman |
| --- | --- | --- | --- |
| **A. Sakla ve sertleştir** (bu PR) | Ucuz, basit, sunucu yok; F2-F5 çözüldü | Veri güncellemesi = commit + derleme + dağıtım (dakikalar); depo büyür; Actions'a bağımlı | Önümüzdeki 3-6 ay |
| **B. Depoyu herkese açık yap** | Actions dakikası ücretsiz → F1/F7 kökten biter | Bot kodu ve içerik görünür olur (sırlar Actions Secrets'ta kalır) | İçerik zaten herkese açıksa **en ucuz çözüm** |
| **C. Veriyi depodan çıkar** (Cloudflare R2/KV + Worker cron) | Commit gürültüsü ve depo şişmesi biter; veri dakikalar içinde güncellenir, derleme gerekmez | Sayfaları istemcide veya Pages Functions'ta okumak gerekir; SEO için SSR (OpenNext) ya da dikkatli hibrit; 2-3 haftalık iş | Hisse/fon kapsamı genişleyip (≈2.600 sayfa) dosya/derleme süresi yeniden sorun olunca |

**Önerim:** Şimdi A (yapıldı) + F1'i çöz (faturalamayı düzelt **ya da** B). C'yi fon sayfalarıyla (Faz D) birlikte değerlendir: fonlar günlük fiyat verisi üretir ve bu hacim depo-veritabanı modelini zorlar.

## 4. Yol haritası

**Faz 0 — Acil (sizin eyleminiz):** GitHub → Settings → Billing → ödeme/harcama limitini düzelt (F1). Sonra "Esham Yayın Döngüsü"nü elle çalıştırıp `force_build` ile siteyi güncelle. Bu PR'ı #2-#5 ile sırayla birleştir.

**Faz 1 — Sağlamlık (bu PR, yapıldı):** dosya bütçesi + budama (F2), sessiz hata yok (F3), web CI + master'da dağıtım (F4), hydration (F5), günlük sağlık denetimi (`health.yml`).

**Faz 2 — Veri güvenilirliği (1-2 hafta):** KAP'ı birincil kaynak yap, Yahoo yedek; `stocks/*.json` ve `universe.json` için JSON Schema doğrulaması (bot yazarken + CI); Actions'ta `actions/cache` ile KAP önbelleği; bayat veri rozeti (sayfada "veri tarihi" ve 4 günden eskiyse uyarı).

**Faz 3 — Depo ve maliyet (1 hafta):** `web/public/cards` → R2 veya derleme sırasında üretim; bot içerik commit'lerini seyrekleştir (toplu) ya da veri dalına taşı; zamanlama sıklığını gözden geçir (haber taraması 15 dk).

**Faz 4 — Kapsam (Faz D/E, GELISTIRME_PLANI.md):** fonlar, karşılaştırma. Başlamadan karar: Seçenek C.

**Sürekli:** Playwright ile 3 uçtan uca akış (ana sayfa → hisse → sekme; tarayıcı filtre; düzen kaydetme), ESLint'i CI'ya ekle, `npm test`'i genişlet.

## 5. Bu PR'ın kapsamı ve sınırı
- Eklenen: `web/scripts/` (budama, bütçe, Pages benzeri yerel sunucu), `bot/esham/jobs/health.py` + 8 test, `web-ci.yml`, `deploy.yml`, `health.yml`, zamanlanmış akışta sessiz hataların giderilmesi, hydration düzeltmeleri.
- **Yapılamayan:** F1 (faturalama) bir hesap ayarıdır; ben değiştiremem. Yeni iş akışlarını (web CI, deploy, health) **faturalama çözülene kadar çalıştıramam**; hepsi YAML olarak doğrulandı ama GitHub'da henüz denenmedi.
- Budamanın yan etkisi doğrulandı: rapor ve hisse sayfalarına tıklayarak geçiş hâlâ tam sayfa yüklemesi olmadan çalışıyor (`slug.txt` korunuyor).
