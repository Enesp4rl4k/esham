import { promises as fs } from "fs";
import path from "path";

interface StatusRow {
  id: string;
  label: string;
  source: string;
  source_url: string;
  as_of: string | null;
  fetched_at: string | null;
  status: "fresh" | "stale" | "missing";
  detail: string;
}

interface StatusDoc {
  generated_at: string;
  sections: StatusRow[];
}

const LABEL: Record<StatusRow["status"], string> = { fresh: "güncel", stale: "güncel değil", missing: "veri yok" };

async function load(): Promise<StatusDoc | null> {
  try {
    const raw = await fs.readFile(path.join(process.cwd(), "public", "data", "data-status.json"), "utf-8");
    const doc = JSON.parse(raw) as StatusDoc;
    return Array.isArray(doc.sections) ? doc : null;
  } catch {
    return null;
  }
}

/** Bot'un her yayın turunda ölçtüğü bölüm bazlı veri durumu (bot/esham/freshness.py). Dosya yoksa hiçbir şey çizilmez. */
export async function DataStatusTable() {
  const doc = await load();
  if (!doc) return null;
  return (
    <section className="mb-8">
      <h2 className="text-xl font-display font-semibold mb-3">Bölüm bazında veri durumu</h2>
      <p className="text-sm text-zinc-400 mb-3">
        Son ölçüm: {new Date(doc.generated_at).toLocaleString("tr-TR", { timeZone: "Europe/Istanbul" })}. Bir kaynak
        alınamazsa son geçerli veri kendi tarihiyle gösterilir ve burada &quot;güncel değil&quot; yazar; tarihsiz veri
        yayınlanmaz.
      </p>
      <div className="overflow-x-auto rounded-xl border border-zinc-800">
        <table className="w-full text-left text-sm text-zinc-300">
          <thead className="text-zinc-400">
            <tr>
              <th className="px-3 py-2">Bölüm</th>
              <th className="px-3 py-2">Veri tarihi</th>
              <th className="px-3 py-2">Durum</th>
              <th className="px-3 py-2">Kaynak</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-800/60">
            {doc.sections.map((s) => (
              <tr key={s.id}>
                <td className="px-3 py-2 font-medium text-white">{s.label}</td>
                <td className="px-3 py-2">{s.as_of ? s.as_of.slice(0, 10) : "—"}</td>
                <td className="px-3 py-2">
                  {LABEL[s.status] ?? s.status}
                  {s.detail ? <span className="block text-xs text-zinc-400">{s.detail}</span> : null}
                </td>
                <td className="px-3 py-2">
                  <a href={s.source_url} className="underline" target="_blank" rel="noopener noreferrer">
                    {s.source}
                  </a>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
