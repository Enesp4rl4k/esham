"""TBB çeyreklik şube sayıları → ``web/public/data/veri/halka-acik-bankalar-sube-sayisi.json``.

Veri kümesi biçimi web/src/lib/veri.ts içindeki ``VeriDataset`` ile aynıdır (şema 1); web derlemesi ve testleri dosyayı
``validateDataset`` ile denetler. Burada da yazmadan önce aynı temel kurallar uygulanır (``validate``).

Çalıştırma:
  python -m esham.jobs.publish_veri_tbb_sube                 # ağ: yalnız eksik çeyrekleri TBB'den indirir (GET/HEAD)
  python -m esham.jobs.publish_veri_tbb_sube --from-dir DIR  # ağsız: DIR/<YYYY-QN>.xlsx + DIR/sources.json
Ardından kartlar: python -m esham.jobs.publish_veri_cards

Zamanlama (henüz kurulu DEĞİL): TBB raporu çeyrek bitiminden ~5 hafta sonra yayımlar (Mart → Mayıs 1. hafta,
Haziran → Ağustos 1. hafta, Eylül → Kasım 1. hafta, Aralık → Şubat 1. hafta). Uygun zamanlama: bu ayların 10'u ve 20'si
(``cron: "0 6 10,20 2,5,8,11 *"``); yeni çeyrek yoksa dosya değişmez ve commit oluşmaz. bkz. docs/veri-grafikleri.md.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path
from typing import Any

from ..config import default_headers, get_logger
from ..sources import tbb_sube as T

log = get_logger(__name__)
ROOT = Path(__file__).resolve().parents[3]
OUT_DIR = ROOT / "web" / "public" / "data" / "veri"
SLUG = "halka-acik-bankalar-sube-sayisi"
OUT_FILE = OUT_DIR / f"{SLUG}.json"
SHEET_CELL_RE = re.compile(r"^[A-Z]{1,3}[1-9]\d{0,6}$")

STATIC: dict[str, Any] = {
    "schema": 1,
    "slug": SLUG,
    "title": "Altı halka açık bankanın şube sayısı",
    "kicker": "Bankacılık",
    "measure": "Şube sayısı",
    "unit": "adet",
    "periodType": "quarter",
    "coverage": "Yurt içi ve yurt dışı şubeler toplamı, dönem sonu",
    "description": (
        "Akbank, Garanti BBVA, Halkbank, İş Bankası, Vakıfbank ve Yapı Kredi'nin çeyreklik şube sayıları; "
        "TBB verisi, tablo ve CSV ile."
    ),
    "sample": False,
    "source": {
        "name": "Türkiye Bankalar Birliği (TBB)",
        "short": "TBB",
        "publication": "Banka, Çalışan ve Şube Bilgileri",
        "url": T.CATEGORY_URL,
        "termsUrl": T.TERMS_URL,
        "terms": (
            "TBB kullanım koşullarına göre sitedeki çalışmalar kaynak gösterilerek yayımlanabilir; ticari amaçlı kullanım "
            "TBB'nin yazılı iznine tabidir. Raporun kendisi kaynak gösterilerek yapılan alıntılar dışında çoğaltılamaz; "
            "bu sayfada yalnızca altı bankanın şube sayısı kaynak gösterilerek alıntılanmıştır."
        ),
    },
}

METHODOLOGY = [
    "Değerler, TBB'nin çeyreklik 'Banka, Çalışan ve Şube Bilgileri' raporundaki 'Tablo 1 – Banka, Şube ve Çalışan Sayıları' "
    "tablosunun 'Şube Sayısı' sütunundan alınmıştır.",
    "TBB dipnotuna göre şube sayısı yurt içi ve yurt dışı şubelerin toplamıdır; değerler çeyrek sonu (dönem sonu) itibarıyladır.",
    "Her çeyreğin değeri o çeyreğe ait raporun kendisinden alınır. Sonraki raporların karşılaştırma sütunlarında geçmiş bir dönem "
    "farklı yayımlanırsa bu grafik o dönemin kendi raporundaki değeri gösterir.",
    "Kapsam: hisseleri Borsa İstanbul'da işlem gören altı mevduat bankası (Akbank, Garanti BBVA, Halkbank, İş Bankası, Vakıfbank, "
    "Yapı Kredi). Grup sabittir; seri sırası alfabetiktir ve bir sıralama ya da değerlendirme içermez.",
    "TBB raporu üye mevduat bankaları ile kalkınma ve yatırım bankalarının bildirimlerine dayanır; katılım bankaları kapsam dışıdır.",
    "Eksik dönem boş bırakılır ve çizgide boşluk olarak görünür; ara değer üretilmez.",
    "TBB sitesinde ekli dosyalar 2017 Eylül döneminden başladığı için seri 3Ç 2017'de başlar.",
]


def _norm_note(s: str) -> str:
    return re.sub(r"[^a-z]", "", T.tr_fold(s or ""))


def build_dataset(entries: dict[str, tuple[T.ParsedFile, dict[str, str]]], updated: str, banks=T.SIX_LISTED_BANKS) -> dict[str, Any]:
    """entries: dönem anahtarı (YYYY-QN) → (ayrıştırılmış dosya, {name,url,page,retrieved}). Saf fonksiyon."""
    if not entries:
        raise ValueError("hiç dönem yok")
    keys = sorted(entries, key=lambda k: (int(k[:4]), int(k[-1])))
    first = tuple(int(x) for x in (keys[0][:4], keys[0][-1]))
    last = tuple(int(x) for x in (keys[-1][:4], keys[-1][-1]))
    periods = [T.period_key(y, q) for y, q in T.quarters(first, last)]  # type: ignore[arg-type]
    files: dict[str, dict[str, str]] = {}
    series = [{"id": b.id, "label": b.label, "sourceLabel": b.source_label, "ticker": b.ticker, "values": [], "provenance": []} for b in banks]
    breaks: list[dict[str, str]] = []
    base_note: str | None = None
    for p in periods:
        if p not in entries:
            for s in series:
                s["values"].append(None)
                s["provenance"].append(None)
            continue
        parsed, meta = entries[p]
        if (parsed.year, parsed.quarter) != (int(p[:4]), int(p[-1])):
            raise T.TbbParseError(f"{p}: dosyadaki tablo başlığı başka bir dönemi gösteriyor ({parsed.title!r})")
        files[p] = {"name": meta["name"], "url": meta["url"], "page": meta["page"], "retrieved": meta["retrieved"]}
        note = _norm_note(parsed.coverage_note)
        if base_note is None:
            base_note = note
        elif note != base_note:
            breaks.append({"period": p, "note": f"Şube sayısı dipnotu bu raporda farklı: \"{parsed.coverage_note}\""})
        vals = T.bank_values(parsed, banks)
        for s in series:
            cv = vals[s["id"]]
            if cv is None or cv.value is None:
                s["values"].append(None)
                s["provenance"].append(None if cv is None else {"file": p, "sheet": cv.sheet, "cell": cv.cell, "label": cv.label})
            else:
                s["values"].append(cv.value)
                s["provenance"].append({"file": p, "sheet": cv.sheet, "cell": cv.cell, "label": cv.label})
    methodology = list(METHODOLOGY)
    if not breaks:
        methodology.append(
            f"Seri kırılması: {len(files)} raporun tamamında şube sayısı dipnotu aynıdır (\"yurtiçi ve yurtdışı şube sayıları "
            "toplamı\"); tanım değişikliği tespit edilmedi. Banka unvanları ve TBB'nin banka grubu sınıflaması dönem içinde "
            "değişebilir; bu, şube sayısının tanımını etkilemez."
        )
    ds = {**STATIC, "methodology": methodology, "breaks": breaks, "updatedAt": updated, "periods": periods, "files": files, "series": series}
    errs = validate(ds)
    if errs:
        raise ValueError("veri kümesi geçersiz: " + "; ".join(errs))
    return ds


def validate(ds: dict[str, Any]) -> list[str]:
    """web/src/lib/veri.ts `validateDataset` ile aynı temel kurallar (dönem sürekliliği, uzunluklar, kaynak)."""
    e: list[str] = []
    periods = ds.get("periods") or []
    for a, b in zip(periods, periods[1:]):
        y, q = int(a[:4]), int(a[-1])
        expected = T.period_key(y + 1, 1) if q == 4 else T.period_key(y, q + 1)
        if b != expected:
            e.append(f"dönemler kesintisiz değil: {a} → {b}")
    files = ds.get("files") or {}
    for s in ds.get("series") or []:
        if len(s["values"]) != len(periods) or len(s["provenance"]) != len(periods):
            e.append(f"{s['id']}: uzunluk dönem sayısına eşit değil")
            continue
        for p, v, pr in zip(periods, s["values"], s["provenance"]):
            if v is None:
                continue
            if not isinstance(v, int) or v < 0:
                e.append(f"{s['id']} {p}: adet negatif olmayan tam sayı olmalı")
            if not pr or pr.get("file") not in files or not SHEET_CELL_RE.match(pr.get("cell", "")) or not pr.get("label") or not pr.get("sheet"):
                e.append(f"{s['id']} {p}: kaynak eksik")
        if all(v is None for v in s["values"]):
            e.append(f"{s['id']}: hiç değer yok")
    return e


def load_existing(path: Path = OUT_FILE) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def entries_from_dir(d: Path) -> dict[str, tuple[T.ParsedFile, dict[str, str]]]:
    """Ağsız: DIR/sources.json {"2026-Q3": {"name","url","page","retrieved"}} + DIR/2026-Q3.xlsx."""
    sources = json.loads((d / "sources.json").read_text(encoding="utf-8"))
    out = {}
    for key, meta in sources.items():
        out[key] = (T.parse_workbook((d / f"{key}.xlsx").read_bytes()), meta)
    return out


def entries_from_network(have: set[str], today: date) -> dict[str, tuple[T.ParsedFile, dict[str, str]]]:
    import requests

    cur_q = (today.month - 1) // 3 + 1
    out = {}
    for y, q in T.quarters(T.FIRST_PERIOD, (today.year, cur_q)):
        key = T.period_key(y, q)
        if key in have:
            continue
        dl = T.fetch_quarter(y, q, requests.get, requests.head, default_headers())
        if dl is None:
            log.info("TBB %s: Excel eki yok (henüz yayımlanmamış olabilir)", key)
            continue
        out[key] = (T.parse_workbook(dl.content), {"name": dl.file_name, "url": dl.file_url, "page": dl.page_url, "retrieved": today.isoformat()})
    return out


def write(ds: dict[str, Any], path: Path = OUT_FILE) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(ds, ensure_ascii=False, indent=1) + "\n"
    old = path.read_text(encoding="utf-8") if path.exists() else None
    if old is not None:
        try:
            o = json.loads(old)
            if {**o, "updatedAt": ds["updatedAt"]} == ds:
                return False  # yalnız tarih değişirdi: dosyaya dokunma
        except ValueError:
            pass
    path.write_text(text, encoding="utf-8")
    return True


def _entries_from_existing(existing: dict[str, Any]) -> dict[str, tuple[T.ParsedFile, dict[str, str]]]:
    """Mevcut veri kümesindeki dönemleri yeniden ayrıştırmadan build_dataset girdisine çevirir."""
    out: dict[str, tuple[T.ParsedFile, dict[str, str]]] = {}
    labels = {b.id: b for b in T.SIX_LISTED_BANKS}
    for i, p in enumerate(existing["periods"]):
        if p not in existing["files"]:
            continue
        rows: dict[str, T.CellValue] = {}
        for s in existing["series"]:
            pr = s["provenance"][i]
            if pr is None or s["id"] not in labels:
                continue
            rows[T.norm_label(labels[s["id"]].source_label)] = T.CellValue(s["values"][i], pr["sheet"], pr["cell"], pr["label"])
        note = "* Yurtiçi ve yurtdışı şube sayıları toplamından oluşmaktadır."
        for b in existing.get("breaks", []):
            if b["period"] == p:
                m = re.search(r'"(.*)"', b["note"])
                note = m.group(1) if m else note
        out[p] = (T.ParsedFile(int(p[:4]), int(p[-1]), f"Tablo 1 {p}", note, rows), existing["files"][p])
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--from-dir", type=Path, help="ağsız: <YYYY-QN>.xlsx dosyaları ve sources.json içeren klasör")
    ap.add_argument("--out", type=Path, default=OUT_FILE)
    args = ap.parse_args(argv)
    today = date.today()
    existing = load_existing(args.out)
    entries = _entries_from_existing(existing) if existing else {}
    if args.from_dir:
        entries.update(entries_from_dir(args.from_dir))
    else:
        entries.update(entries_from_network(set(entries), today))
    ds = build_dataset(entries, today.isoformat())
    changed = write(ds, args.out)
    log.info("veri kümesi %s: %d dönem (%s – %s)%s", args.out.name, len(ds["periods"]), ds["periods"][0], ds["periods"][-1], "" if changed else " — değişiklik yok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
