import type { Metadata } from "next";
import { getAllReports } from "@/lib/content";
import { SearchClient } from "@/components/SearchClient";

export const metadata: Metadata = {
  title: "Rapor Ara",
  description: "Esham rapor arşivinde başlık, özet veya etiket ile arama yapın.",
};

export default function AramaPage() {
  // Tüm raporları sunucu tarafında okuyup istemciye prop olarak geçiriyoruz.
  // Statik export'ta bu veriler derleme anında sayfaya gömülür.
  const reports = getAllReports();

  return (
    <div className="container mx-auto px-6 py-16 max-w-4xl">
      <div className="mb-12">
        <h1 className="text-4xl font-outfit font-bold tracking-tight mb-3">
          Rapor Ara
        </h1>
        <p className="text-zinc-400">
          {reports.length} rapor arasında arama yapın.
        </p>
      </div>

      <SearchClient reports={reports} />
    </div>
  );
}
