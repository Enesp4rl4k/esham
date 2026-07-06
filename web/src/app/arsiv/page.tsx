import type { Metadata } from "next";
import { getAllReports } from "@/lib/content";
import { ArchiveClient } from "@/components/ArchiveClient";

export const metadata: Metadata = {
  title: "Arşiv",
  description: "Tüm Esham raporlarını kategoriye göre filtreleyin ve keşfedin.",
};

export default function ArsivPage() {
  const reports = getAllReports();

  return (
    <div className="container mx-auto px-6 py-16 max-w-5xl">
      <div className="mb-12">
        <h1 className="text-4xl font-outfit font-bold tracking-tight mb-3">
          Arşiv
        </h1>
        <p className="text-zinc-400">
          Tüm raporları keşfedin. Kategoriye göre filtreleyin.
        </p>
      </div>

      <ArchiveClient reports={reports} />
    </div>
  );
}
