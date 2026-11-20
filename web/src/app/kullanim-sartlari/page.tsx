import type { Metadata } from "next";
import { SITE_URL } from "@/lib/config";
import { LegalPage } from "@/components/LegalPage";

export const metadata: Metadata = {
  title: "Kullanım Şartları ve Yasal Uyarı",
  description: "Esham içeriğinin niteliği, yatırım tavsiyesi olmadığı ve sorumluluk sınırları.",
  alternates: { canonical: `${SITE_URL}/kullanim-sartlari` },
};

export default function TermsPage() {
  return (
    <LegalPage title="Kullanım Şartları ve Yasal Uyarı" updated="21 Kasım 2026">
      <h2>Yatırım tavsiyesi değildir</h2>
      <p>
        Esham&apos;de yer alan oranlar, hesaplayıcılar, raporlar ve yorumlar yalnızca bilgilendirme amaçlıdır. Sermaye Piyasası Kurulu düzenlemeleri kapsamında yatırım danışmanlığı veya portföy yöneticiliği hizmeti sunmuyoruz; içerik, herhangi bir menkul kıymet ya da fonun alım-satımına yönelik tavsiye veya öneri değildir. Yatırım kararlarınızı kendi araştırmanıza ve yetkili bir kuruluştan alacağınız danışmanlığa dayandırın.
      </p>

      <h2>Veri kaynakları ve doğruluk</h2>
      <p>
        Finansal tablolar öncelikle KAP&apos;tan, kapsam dışında kalan şirketlerde Yahoo Finance&apos;ten; fon verileri TEFAS&apos;tan alınır ve oranlar Esham tarafından hesaplanır. Veriler gecikmeli, eksik veya hatalı olabilir; tutarlılığı, güncelliği ve eksiksizliği garanti edilmez. Hesaplama yöntemleri <a href="/yontem">Yöntem ve Kaynaklar</a> sayfasında açıklanmıştır. Bir hata fark ederseniz <a href="/iletisim">bize bildirin</a>.
      </p>

      <h2>Geçmiş performans</h2>
      <p>Geçmiş getiri, gelecekteki getirinin göstergesi değildir. Hesaplayıcılardaki (DCF, NAV) sonuçlar sizin girdiğiniz varsayımların matematiksel çıktısıdır; hedef fiyat önerisi değildir.</p>

      <h2>Sorumluluk sınırı</h2>
      <p>
        Esham ve içerik üreticileri, sitedeki bilgilerin kullanımından doğabilecek doğrudan veya dolaylı zararlardan sorumlu tutulamaz. Dış bağlantılar kendi sahiplerinin sorumluluğundadır.
      </p>

      <h2>Fikri haklar</h2>
      <p>
        Sitenin özgün içeriği ve tasarımı Esham&apos;e aittir. Kısa alıntılar kaynak ve bağlantı gösterilerek yapılabilir. Üçüncü taraf veriler (KAP, TEFAS, Yahoo Finance) kendi sahiplerinin koşullarına tabidir.
      </p>

      <h2>Değişiklikler</h2>
      <p>Bu şartlar zaman zaman güncellenebilir; güncel sürüm bu sayfada yayımlanır.</p>
    </LegalPage>
  );
}
