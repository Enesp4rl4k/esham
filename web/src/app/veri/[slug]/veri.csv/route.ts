import { toCsv } from "@/lib/veri";
import { getDataset, loadDatasets } from "@/lib/veri-data";

export const dynamic = "force-static";
export const dynamicParams = false;

export function generateStaticParams(): { slug: string }[] {
  const all = loadDatasets();
  return all.length ? all.map((d) => ({ slug: d.slug })) : [{ slug: "yok" }];
}

/** Grafik ve tablodaki değerlerin ham hali (aynı veri kümesinden). UTF-8 BOM: Excel Türkçe karakterleri doğru açar. */
export async function GET(_req: Request, { params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const ds = getDataset(slug);
  if (!ds) return new Response("bulunamadı", { status: 404 });
  return new Response("﻿" + toCsv(ds), { headers: { "Content-Type": "text/csv; charset=utf-8" } });
}
