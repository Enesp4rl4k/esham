# Kaynak fizibilitesi: kaldırılan bölümler gerçek kaynakla geri gelebilir mi? (23 Kas 2026)

Soru: PR #25'te sayıları uydurma olduğu için kaldırılan bölümler (kâr payı takvimi, geri alımlar, et-yem, devalüasyon
radarı, VİOP baz farkı, makro barometre, kantitatif değerleme) **uydurmadan** geri eklenebilir mi? Cevap bölüm bölüm
aşağıda. Kural değişmedi: kaynaksız ve tarihsiz sayı yayınlanmaz; alınamayan veri "yok" der.

Ölçüm yöntemi: aşağıdaki her URL bu makineden (ağ çıkışı KKTC) en fazla birkaç kez, anahtarsız ve herkese açık GET ile
denendi; KAP için PR #25'in istek bütçesi ve nazik HTTP katmanı (`kap_http`) kullanıldı. Üretim döngüsü GitHub Actions
(ABD/AB IP'leri) üzerinde koşar: **bu makineden erişilebilir olan bir kaynağın Actions'tan da erişilebileceği yalnızca
çıkarımdır** (KAP, TCMB, TÜİK, BIST sitelerinin yurt dışı IP'lerini kısıtlamadığı varsayımı doğrulanmadı). KAP kâr payı ve
geri alım liste/ayrıntı uçları finansal raporlarla aynı uçlar olduğundan, PR #25'in üretim ölçümü (hâlâ yapılmadı) bu
varsayımı da sınayacaktır. Terim: "şartlar bulunamadı" = ilgili sitede yeniden yayına dair bir metin bulunamadı; bu
"serbest" demek değildir. Hukuki görüş değildir.

## Özet tablo

| Özellik | Aday kaynak (URL / uç) | Biçim, sıklık, gecikme | Anahtar | Bu makineden erişim | Şartlar / atıf | Karar |
|---|---|---|---|---|---|---|
| **Kâr payı takvimi** | KAP bildirim listesi `POST https://www.kap.org.tr/tr/api/disclosure/members/byCriteria` (konu "Kar Payı Dağıtım İşlemlerine İlişkin Bildirim", `subjectOid=4028328d5988e2630159d5fb51c81fe6`) + ayrıntı `https://www.kap.org.tr/tr/Bildirim/<no>` | JSON liste + sayfa içi HTML tabloları (`SHARE_DIVIDEND_FLEX_TABLE_2/3`: brüt/net/stopaj, teklif/kesinleşen hak kullanım, ödeme, kayıt). Bildirim anında; teklif (yönetim kurulu) ve kesinleşme (genel kurul) ayrı bildirim | yok | 200 (liste ve ayrıntı sayfaları, 23 Kas) | şartlar bulunamadı (aşağıya bakın) | **Kullanılabilir şimdi — yapıldı** |
| **Geri alımlar** | Aynı uç, konu "Payların Geri Alınmasına İlişkin Bildirim", `subjectOid=4028328d6233239a01629b43e4694fae` | Aynı; günlük işlem bildirimleri (tarih, nominal, fiyat, program limiti, fon) | yok | 200 | şartlar bulunamadı (aşağıya bakın) | **Kullanılabilir şimdi — yapıldı** |
| Kâr payı / geri alım çapraz kontrol | MKK (mkk.com.tr), Borsa İstanbul sayfaları | Ana sayfalar 200; bildirim düzeyinde ikinci kaynak aranmadı | - | 200 (yalnız ana sayfa) | şartlar bulunamadı | Çapraz kontrol için kullanılmadı; bunun yerine bildirim içi tutarlılık denetimi (net = brüt × (1 − stopaj), ödeme ≥ hak kullanım, geri alım satırlarının "daha önce alınan" sütunuyla toplamı) ve bir bildirimin kendi metniyle karşılaştırma yapıldı |
| **Et–yem: et tarafı** | Et ve Süt Kurumu `https://www.esk.gov.tr/tr/11861/Fiyatlarimiz` | Statik HTML tablo (Excel yapıştırması, 7 sütun, `th` yok). **Canlı hayvan alım** fiyatı (TL/et kg, randımana göre); **karkas fiyatı yok**; sayfada **tarih alanı yok**, `Last-Modified` yok, geçmiş seri yok | yok | 200 | şartlar bulunamadı | **Kullanılamaz (tek başına)**: tarihsiz, geçmişsiz; "karkas et" tanımına uymuyor |
| Et–yem: yem tarafı | TÜİK Tarımsal Girdi Fiyat Endeksi (yem); TÜRİB spot arpa/mısır; TMO alım fiyatları; TÜYSAD | TÜİK: `veriportali.tuik.gov.tr` yalnız JavaScript kabuğu, SDMX `nsiws.tuik.gov.tr/rest/...` **401**; TÜRİB: tablo JS ile geliyor; TMO: `www.tmo.gov.tr` bu makineden **bağlantı kurulamadı**; TÜYSAD: herkese açık makine okunur seri bulunamadı | TÜİK: anahtar/oturum | TÜİK 401; TMO erişilemedi | TÜRİB (turib.com.tr/kullanim-sart-ve-kosullari): "robotlar ... otomatik mekanizmalar ... kopyalanması ... yasaktır" | **Kullanılamaz**: makine okunur ve yeniden yayına açık bir besi yemi/arpa serisi yok |
| Süt/yem paritesi (et-yem değil) | Ulusal Süt Konseyi `https://ulusalsutkonseyi.org.tr/cig-sut-yem-paritesi-627/` | HTML (TablePress), aylık, 1-2 ay gecikme (Eki-Kas 2026 hücreleri boş); çiğ süt tavsiye fiyatı yalnız serbest metin duyuru | yok | 200 | şartlar bulunamadı | Kullanılabilir (**et-yem değil**, ayrı bir gösterge). Yapılmadı: istenen göstergeyi karşılamıyor |
| **Dürüst et–yem tanımı** | "karkas dana eti / besi yemi fiyat oranı" | İki seri de gerekli: karkas fiyatı (ESK karkas listesi yok; TÜİK madde fiyatları programatik değil) ve besi yemi (kaynak yok) | - | - | - | **Şimdi yapılamaz.** Gerekenler: TÜİK API erişimi (yazılı talep) veya ESK/TÜYSAD'dan düzenli, tarihli, yeniden yayına izinli veri |
| **Devalüasyon göstergeleri** (tahmin değil) | (1) TCMB günlük döviz XML `https://www.tcmb.gov.tr/kurlar/YYYYMM/DDMMYYYY.xml` → USD/TRY 30 gün / 12 ay değişimi | XML, iş günü ~15:30; | yok | 200 | TCMB: kaynak gösterilerek yayımlanabilir, ticari kullanım yazılı izne bağlı (aşağıya bakın) | **Kullanılabilir şimdi — yapıldı** |
| | (2) TCMB 1 Hafta Repo (politika faizi) `.../Para+Politikasi/Merkez+Bankasi+Faiz+Oranlari/1+Hafta+Repo`, `table#midTable` | HTML; yalnız değişiklik tarihleri (son: 23.10.2026, 36,00); | yok | 200 | TCMB: kaynak gösterilerek yayımlanabilir, ticari kullanım yazılı izne bağlı (aşağıya bakın) | **Kullanılabilir şimdi — yapıldı** (veri tarihi = son değişiklik tarihi) |
| | (3) Reel efektif döviz kuru (REK) EVDS `TP.RK.T1.Y` | JSON, aylık; | **EVDS anahtarı** | EVDS API anahtarsız 403 ("Required request header 'key'") | EVDS kullanım şartları anahtar alırken kabul edilir; okunmadı | **Anahtarla** — fetcher yazıldı (`EVDS_API_KEY`); seri kodu doğrulanmadı |
| | (4) TÜFE yıllık değişim EVDS `TP.FG.J0` (12 ay önceki gözlemle bot hesaplar) | JSON, aylık; ayın 3'ü civarı | **EVDS anahtarı** | aynı | aynı | **Anahtarla** — yazıldı; kod doğrulanmadı |
| | (5) TCMB brüt rezerv / analitik bilanço (haftalık) | EVDS serisi (kod doğrulanmadı) ya da TCMB sayfası (biçim incelenmedi) | EVDS | - | - | Yapılmadı: kod doğrulanmadan seri yazılmaz. Anahtar gelince `tumSeriler` listesinden kod doğrulanıp eklenebilir |
| | (6) 5 yıllık CDS | worldgovernmentbonds.com (değerler JS ile geliyor, kaynak olarak Investing/TradingEconomics gösteriliyor), investing.com | - | 200 (değerler boş) | yeniden yayın izni yok | **Kullanılamaz**: serbest ve yeniden yayına açık CDS kaynağı bulunamadı |
| **VİOP baz farkı** | Borsa İstanbul günlük dosyası `https://www.borsaistanbul.com/data/vadeli/viop_YYYYMMDD.csv` (uzlaşma fiyatı) ve `.../data/thb/YYYY/MM/thbYYYYMMDD1.zip` (pay günlük bülteni) | Noktalı virgüllü CSV, iş günü; anahtarsız, teknik olarak açık | yok | 200 | BIST (borsaistanbul.com telif sayfası): "önceden yazılı olarak izni alınmadan ... dağıtılamaz, ... çoğaltılamaz ..." — veri dağıtım sözleşmesi ve lisans ister | **Kullanılamaz (şart)**: teknik olarak açık ama yeniden yayın için yazılı izin/lisans gerekir |
| **Makro barometre** | TCMB faiz sayfası, TCMB döviz XML (yukarıda); EVDS: TÜFE, REK; TÜİK: işsizlik, sanayi üretimi, cari işlemler (cari denge TCMB/EVDS) | TÜİK bültenleri JS kabuğu / 401; EVDS anahtarlı | EVDS | TÜİK: kullanılamaz | TÜİK: şartlar bulunamadı | Anahtarsız yalnız faiz ve kur değişimi (yapıldı). İşsizlik, sanayi üretimi, cari işlemler: EVDS serileri olarak mümkün, **kodlar doğrulanmadı**, yapılmadı |
| **Değerleme (kantitatif)** | KAP finansalları (zaten ayrıştırılıyor) + kapanış fiyatı | Fiyat: Yahoo (resmî olmayan uçlar), BIST günlük bülten dosyası | - | Yahoo: erişilir | Yahoo (legal.yahoo.com): "you may not access or reuse the Services ... for any commercial purpose"; BIST: yukarıdaki lisans cümlesi | **Kullanılamaz**: fiyat kaynağı yeniden yayına açık değil. Fiyatsız oranlar (ROE, marj, borç/özkaynak) KAP'tan zaten hesaplanıyor. Her oran için fiyat tarihi ve finansal dönem gösterilmeden F/K ve PD/DD yayınlanmaz |

KAP şartları: **şartlar bulunamadı.** kap.org.tr'de yeniden yayına dair kullanım koşulları sayfası bulunamadı (tahmin edilen birkaç adres 404; web aramasında da çıkmadı; KAP bildirimlerinin veri yayın kuruluşlarınca eş zamanlı yayımlandığı belirtiliyor). Bu izin anlamına gelmez; her satırda bildirim bağlantısı verilerek atıf yapılır, ticari kullanım için MKK/KAP'a (kapdestek@mkk.com.tr) yazılması önerilir.

TCMB şartları: TCMB Kullanım Şartları (`.../Bottom+Menu/Diger/Kullanim+Sartlari`): "Sitede yer alan bilgiler, kaynak gösterilmek suretiyle yayımlanabilir; ancak bu bilgilerin ticari amaçlarla kullanımı TCMB'nin yazılı iznine tabidir." Atıf bölümlerde yazıyor ("Kaynak: T.C. Merkez Bankası (tcmb.gov.tr)"). Esham ticari gelir elde ediyorsa yazılı izin gerekir: **sahibin kararı**.

## Lisans uyarıları (sahibin kararı)

1. **TÜRİB**: sitenin mevcut emtia bölümü TÜRİB ELÜS bültenini kazıyor; TÜRİB'in kullanım şartları "robotlar ... otomatik mekanizmalar" ile kopyalanmasını ve yeniden yayını yasaklıyor ve yazılı izin istiyor. Bu PR değiştirmiyor; hukuken en riskli mevcut kaynak.
2. **Yahoo Finance**: mevcut fiyat/temettü kaynağı; şartlar ticari kullanımı yasaklıyor (aynı risk).
3. **Borsa İstanbul verisi**: günlük dosyalar anahtarsız indirilebiliyor ama şartlar yeniden yayını lisansa bağlıyor; bu yüzden VİOP baz farkı ve fiyatlı değerleme eklenmedi.
4. **KAP**: kullanılan bölümler KAP şartlarına bağlı (yukarıdaki satır); ticari kullanım için KAP/MKK ile yazışma önerilir.
5. **TCMB**: atıf zorunlu; ticari kullanım yazılı izne bağlı.

## Faz 2 / Faz 3: yapılanlar

- `python -m esham.main kap-events`: KAP kâr payı (`web/public/data/kap-dividends.json`) ve geri alım (`kap-buybacks.json`).
  Biçimi tanınmayan bildirim atlanır ve nedeniyle sayılır; her satır bildirim numarası, bağlantı, yayın tarihi (veri tarihi) ve çekiliş zamanı taşır.
  KAP önbelleğini (`bot/cache/kap/events`) ve `kap_http` geçidini paylaşır, koşu başına en çok 40 bildirim sayfası indirir ve sonraki koşuda kaldığı yerden devam eder.
  İstek ölçümü (23 Kas, 2 sn aralık): liste için 2 istek; ilk doldurma (150 gün kâr payı: 22 bildirim, 30 gün geri alım) yaklaşık 130 sayfa; sonraki günlük tur: 2 liste + yeni bildirim sayısı kadar sayfa.
  İlk denemede 1,5 sn aralıkla ~100 ardışık sayfa **429** (devre kesici açıldı) verdi; bu yüzden koşu başına sınır 40 ve aralık 2 sn'ye çekildi.
- `python -m esham.main macro`: `macro-indicators.json` (politika faizi, USD/TRY 30 gün ve 12 ay; `EVDS_API_KEY` varsa TÜFE yıllık ve REK).
- Sayfalar: `/piyasa/temettu-takvimi`, `/piyasa/geri-alimlar`, `/piyasa/makro-gostergeler`; hisse sayfasındaki "kâr payı ve geri alım" kartı yeni veriyle çalışır; `data-status.json` ve /yontem tablosu üç yeni bölümü ölçer.
- Koruma testleri: `bot/tests/test_kap_events.py` (gerçek bildirimlerden alınmış fixture'lar; yayınlanan dosyalarda kaynak, tarih, kapsam zorunlu) ve `bot/tests/test_macro_evds.py` (anahtarın log, hata, iz ve dosyalarda bulunmadığı).

## EVDS (TCMB) için sahibin yapacakları

1. https://evds3.tcmb.gov.tr adresinde ücretsiz üye olup profil sayfasından API anahtarı alın (kullanım şartlarını kabul etmeniz gerekir; ben okumadım).
2. GitHub deposunda Settings → Secrets and variables → Actions → **`EVDS_API_KEY`** adıyla secret ekleyin. İş akışı bunu `EVDS_API_KEY` ortam değişkeni olarak bota geçirir; tanımlı değilse EVDS göstergeleri çekilmez ve sayfada görünmez.
3. İlk koşudan sonra `Actions → macro` günlüğüne bakın: seri kodları (`TP.FG.J0`, `TP.RK.T1.Y`) **doğrulanmadı**; yanlışsa gösterge hata sayılır, "alınamadı" uyarısı yazılır, uydurma değer çıkmaz. Doğru kodları EVDS "Tüm seriler" sayfasından bulup `bot/esham/sources/tcmb_evds.py` içindeki `INDICATORS` listesinde düzeltin.
4. Anahtar yalnızca `key` istek başlığında gider (EVDS yanıtı "Required request header 'key'" diyor; URL biçimi kullanılmaz). Anahtarın hiçbir log, hata iletisi, iz ya da dosyada görünmediği test edilir.
