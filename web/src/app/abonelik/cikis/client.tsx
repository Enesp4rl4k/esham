"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { CheckCircle2, AlertCircle, Loader2, ArrowLeft } from "lucide-react";
import { BOT_API_URL } from "@/lib/config";

type Status = "loading" | "ok" | "error" | "unconfigured";

/** `?email=...&token=...` — statik export olduğu için searchParams yerine
 *  `window.location` okunur (Suspense/prerender sınırı olmadan çalışır). */
function readParams(): { email: string; token: string } {
  const qs = new URLSearchParams(window.location.search);
  return {
    email: qs.get("email") ?? "",
    token: qs.get("token") ?? "",
  };
}

export function UnsubscribeClient() {
  const [status, setStatus] = useState<Status>("loading");
  const [message, setMessage] = useState("");

  useEffect(() => {
    if (!BOT_API_URL) {
      setStatus("unconfigured");
      return;
    }
    const { email, token } = readParams();
    if (!email || !token) {
      setStatus("error");
      setMessage("Eksik bağlantı: e-posta veya çıkış anahtarı bulunamadı.");
      return;
    }
    fetch(
      `${BOT_API_URL}/unsubscribe?email=${encodeURIComponent(email)}&token=${encodeURIComponent(token)}`,
    )
      .then(async (res) => {
        const data = (await res.json().catch(() => ({}))) as {
          ok?: boolean;
          message?: string;
        };
        if (res.ok && data.ok !== false) {
          setStatus("ok");
          setMessage(data.message ?? "Aboneliğiniz sonlandırıldı.");
        } else {
          setStatus("error");
          setMessage(data.message ?? "Çıkış yapılamadı.");
        }
      })
      .catch(() => {
        setStatus("error");
        setMessage("Bağlantı hatası — birkaç dakika sonra tekrar deneyin.");
      });
  }, []);

  const icon =
    status === "ok" ? (
      <CheckCircle2 className="w-8 h-8 text-emerald-400" />
    ) : status === "error" ? (
      <AlertCircle className="w-8 h-8 text-red-400" />
    ) : (
      <Loader2 className="w-8 h-8 text-cyan-400 animate-spin" />
    );

  return (
    <div className="container mx-auto px-6 py-24 max-w-xl text-center">
      <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-zinc-900 border border-zinc-800 mb-6">
        {icon}
      </div>
      <h1 className="text-3xl font-display font-bold mb-4">Bülten Aboneliği</h1>

      {status === "loading" && <p className="text-zinc-400">İşleniyor…</p>}

      {status === "ok" && (
        <>
          <p className="text-emerald-400 text-lg mb-2">{message}</p>
          <p className="text-zinc-500 text-sm">
            Artık bülten e-postaları gönderilmeyecek. Dilerseniz daha sonra
            tekrar abone olabilirsiniz.
          </p>
        </>
      )}

      {status === "error" && <p className="text-red-400 text-lg">{message}</p>}

      {status === "unconfigured" && (
        <div className="text-left bg-zinc-950 border border-zinc-800 rounded-xl p-6 text-sm text-zinc-400 leading-relaxed">
          <p className="mb-3">
            Abonelik servisi bu kurulumda tanımlı değil. Çıkış bağlantısını
            kullanmaya devam edebilirsiniz: bot sunucusunun{" "}
            <code className="text-amber-400">/unsubscribe</code> ucuna e-posta ve
            anahtar parametreleriyle açılması yeterlidir.
          </p>
          <p>
            Kurulum: bot ortamına{" "}
            <code className="text-amber-400">ESHAM_SMTP_*</code> ve siteye{" "}
            <code className="text-amber-400">NEXT_PUBLIC_ESHAM_BOT_URL</code>{" "}
            ekleyin (bkz. KURULUM_REHBERI.md).
          </p>
        </div>
      )}

      <Link
        href="/"
        className="inline-flex items-center gap-2 mt-8 text-sm text-cyan-400 hover:text-white transition-colors"
      >
        <ArrowLeft className="w-4 h-4" /> Ana sayfaya dön
      </Link>
    </div>
  );
}
