"use client";

import { useState } from "react";
import { Mail, CheckCircle2, AlertCircle } from "lucide-react";
import { BOT_API_URL, FORMSPREE_FALLBACK } from "@/lib/config";

type Status = "idle" | "loading" | "ok" | "error";

export function Newsletter() {
  const [email, setEmail] = useState("");
  const [status, setStatus] = useState<Status>("idle");
  const [message, setMessage] = useState("");

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!BOT_API_URL) return; // API yoksa normal (Formspree) gönderim devam eder
    setStatus("loading");
    try {
      // URL-encoded → preflight (OPTIONS) tetiklemez, doğrudan gönderilir
      const res = await fetch(`${BOT_API_URL}/subscribe`, {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: new URLSearchParams({ email }),
      });
      const data = (await res.json().catch(() => ({}))) as {
        ok?: boolean;
        message?: string;
      };
      if (res.ok && data.ok !== false) {
        setStatus("ok");
        setMessage(data.message ?? "Aboneliğiniz alındı.");
        setEmail("");
      } else {
        setStatus("error");
        setMessage(data.message ?? "Kayıt başarısız oldu, tekrar deneyin.");
      }
    } catch {
      setStatus("error");
      setMessage("Bağlantı hatası — birkaç dakika sonra tekrar deneyin.");
    }
  }

  const feedback =
    status === "ok" ? (
      <p className="flex items-center justify-center gap-2 text-sm text-emerald-400 mt-4">
        <CheckCircle2 className="w-4 h-4 shrink-0" />
        {message}
      </p>
    ) : status === "error" ? (
      <p className="flex items-center justify-center gap-2 text-sm text-red-400 mt-4">
        <AlertCircle className="w-4 h-4 shrink-0" />
        {message}
      </p>
    ) : null;

  return (
    <section className="py-24 bg-gradient-to-b from-zinc-950 to-black border-t border-zinc-900">
      <div className="container mx-auto px-6 max-w-4xl text-center">
        <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-cyan-950 text-cyan-400 mb-6">
          <Mail className="w-8 h-8" />
        </div>
        <h2 className="text-3xl md:text-5xl font-outfit font-bold mb-4">
          Piyasalar Her Sabah Kutunuzda
        </h2>
        <p className="text-zinc-400 text-lg mb-8 max-w-2xl mx-auto font-light">
          BIST bülteni, makro özetler ve yeni halka arz analizlerini kaçırmamak için
          email bültenimize ücretsiz katılın.
        </p>

        {/* Bot uç noktası tanımlı → kendi abone depomuza yazılır;
            yoksa Formspree yedeğine normal form gönderimi yapılır. */}
        <form
          action={BOT_API_URL ? undefined : FORMSPREE_FALLBACK}
          method={BOT_API_URL ? undefined : "POST"}
          onSubmit={onSubmit}
          className="flex flex-col sm:flex-row gap-3 max-w-lg mx-auto"
        >
          <input
            type="email"
            name="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="ornek@sirket.com"
            required
            className="flex-1 bg-zinc-900 border border-zinc-800 rounded-full px-6 py-4 text-white focus:outline-none focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500 transition-colors"
          />
          <button
            type="submit"
            disabled={status === "loading"}
            className="bg-cyan-500 hover:bg-cyan-400 text-black font-bold rounded-full px-8 py-4 transition-colors whitespace-nowrap disabled:opacity-60"
          >
            {status === "loading" ? "Gönderiliyor…" : "Abone Ol"}
          </button>
        </form>

        {feedback}

        <p className="text-zinc-400 text-sm mt-4">
          İstediğiniz zaman tek tıkla abonelikten çıkabilirsiniz. Spam yok.
        </p>
      </div>
    </section>
  );
}
