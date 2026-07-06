import Link from "next/link";
import { Search, Home, BarChart3 } from "lucide-react";

export default function NotFound() {
  return (
    <div className="flex flex-col items-center justify-center min-h-[70vh] px-6 text-center">
      {/* Büyük 404 */}
      <p className="text-8xl font-outfit font-bold text-zinc-800 select-none mb-2">
        404
      </p>

      <h1 className="text-2xl font-outfit font-bold text-zinc-100 mb-3">
        Sayfa bulunamadı
      </h1>
      <p className="text-zinc-500 max-w-sm mb-10">
        Aradığınız rapor veya sayfa mevcut değil ya da taşınmış olabilir.
      </p>

      {/* Aksiyon düğmeleri */}
      <div className="flex flex-col sm:flex-row gap-3">
        <Link
          href="/"
          className="inline-flex items-center gap-2 px-6 py-3 rounded-full bg-white text-black text-sm font-medium hover:bg-zinc-200 transition-colors"
        >
          <Home className="w-4 h-4" aria-hidden="true" />
          Ana Sayfaya Dön
        </Link>
        <Link
          href="/arama"
          className="inline-flex items-center gap-2 px-6 py-3 rounded-full bg-zinc-900 border border-zinc-800 text-white text-sm font-medium hover:bg-zinc-800 transition-colors"
        >
          <Search className="w-4 h-4" aria-hidden="true" />
          Rapor Ara
        </Link>
        <Link
          href="/kategori/bist"
          className="inline-flex items-center gap-2 px-6 py-3 rounded-full bg-zinc-900 border border-zinc-800 text-white text-sm font-medium hover:bg-zinc-800 transition-colors"
        >
          <BarChart3 className="w-4 h-4" aria-hidden="true" />
          BIST Raporları
        </Link>
      </div>
    </div>
  );
}
