import type { Metadata } from "next";
import { UnsubscribeClient } from "./client";

export const metadata: Metadata = {
  title: "Bülten Aboneliğinden Çıkış",
  description:
    "Esham günlük bülten aboneliğinizi sonlandırın. İmzalı çıkış bağlantısı güvenli şekilde işleme alınır.",
  robots: { index: false },
};

export default function UnsubscribePage() {
  return <UnsubscribeClient />;
}
