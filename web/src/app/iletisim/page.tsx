import type { Metadata } from "next";
import { SITE_URL } from "@/lib/config";
import { LegalPage } from "@/components/LegalPage";

export const metadata: Metadata = {
  title: "İletişim",
  description: "Esham ile iletişim: hata bildirimi, KVKK talepleri ve geri bildirim.",
  alternates: { canonical: `${SITE_URL}/iletisim` },
};

export default function ContactPage() {
  return (
    <LegalPage title="İletişim" updated="21 Kasım 2026">
      <p>Hata bildirimi, geri bildirim ve KVKK kapsamındaki talepleriniz için:</p>
      <ul>
        <li>
          X (Twitter): <a href="https://x.com/eshamcomtr" rel="noopener noreferrer">@eshamcomtr</a>
        </li>
      </ul>
      <p>
        Yanlış bir rakam bildirirken hisse veya fon kodunu ve hangi oranı kastettiğinizi yazmanız düzeltmeyi hızlandırır. Doğrulanan hatalar düzeltilir.
      </p>
    </LegalPage>
  );
}
