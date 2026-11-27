"""TBB "Banka, Çalışan ve Şube Bilgileri" (çeyreklik) → banka bazında şube sayısı.

Kaynak: Türkiye Bankalar Birliği, İstatistiki Raporlar › Seçilmiş İstatistikler › Banka, Çalışan ve Şube Bilgileri.
Her çeyrek için bir sayfa vardır: ``/istatistiki-raporlar/<yıl>-<ay>-banka-calisan-ve-sube-bilgileri``
(ay: mart | haziran | eylul | aralik). Sayfada PDF / Word / Excel ekleri bulunur; yalnızca Excel kullanılır.
Ekli dosyalar 2017 Eylül döneminden başlar (daha eski sayfalarda ek yoktur).

Kullanım koşulları (docs/veri-grafikleri.md): site içeriği "kaynak gösterilmek suretiyle" yayımlanabilir, ticari kullanım
yazılı izne tabidir; raporun kendisi "kaynak gösterilmek şartıyla yapılacak alıntılar dışında" çoğaltılamaz. Bu yüzden:
  - yalnızca seçili satırların şube sayısı alınır (alıntı), dosyanın kendisi depoya konmaz;
  - her değer kaynağıyla (sayfa, dosya adı, sayfa/hücre, satır etiketi, indirme tarihi) saklanır.

Ayrıştırma ağsızdır (``parse_workbook``): yalnız standart kütüphane ile .xlsx okunur (yeni bağımlılık yok).
"Tablo 1 … İtibarıyla Banka, Şube ve Çalışan Sayıları" sayfası iki sütun bloğu içerir; her blokta banka adı sütunu ve
sağında "Şube Sayısı*" başlıklı sütun vardır. Başlık tanınmazsa ``TbbParseError`` (sessiz yanlış değer yok).
"""
from __future__ import annotations

import re
import time
import zipfile
from dataclasses import dataclass
from io import BytesIO
from typing import Callable, Iterable
from urllib.parse import unquote
from xml.etree import ElementTree as ET

from ..turkish import tr_fold

BASE = "https://www.tbb.org.tr"
PAGE_URL = BASE + "/istatistiki-raporlar/{year}-{month}-banka-calisan-ve-sube-bilgileri"
CATEGORY_URL = BASE + "/istatistiki-raporlar/11237"
TERMS_URL = BASE + "/kullanim-kosullari"
FIRST_PERIOD = (2017, 3)  # ekli dosyaların başladığı dönem
MONTH_SLUG = {1: "mart", 2: "haziran", 3: "eylul", 4: "aralik"}
MONTH_NAME_TO_Q = {"mart": 1, "haziran": 2, "eylul": 3, "aralik": 4}
_NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"


class TbbParseError(ValueError):
    pass


@dataclass(frozen=True)
class Bank:
    id: str
    label: str  # grafikte görünen kısa ad
    source_label: str  # TBB tablosundaki unvan
    ticker: str


# Borsa İstanbul'da hisseleri işlem gören altı mevduat bankası (sabit grup; sıralama değildir).
SIX_LISTED_BANKS: tuple[Bank, ...] = (
    Bank("akbank", "Akbank", "Akbank T.A.Ş.", "AKBNK"),
    Bank("garanti", "Garanti BBVA", "Türkiye Garanti Bankası A.Ş.", "GARAN"),
    Bank("halkbank", "Halkbank", "Türkiye Halk Bankası A.Ş.", "HALKB"),
    Bank("isbank", "İş Bankası", "Türkiye İş Bankası A.Ş.", "ISCTR"),
    Bank("vakifbank", "Vakıfbank", "Türkiye Vakıflar Bankası T.A.O.", "VAKBN"),
    Bank("yapikredi", "Yapı Kredi", "Yapı ve Kredi Bankası A.Ş.", "YKBNK"),
)


def norm_label(s: str) -> str:
    """Satır etiketini eşleştirme anahtarına çevirir: dipnot yıldızları, fazla boşluk ve aksan farkı yok sayılır."""
    s = re.sub(r"\*+", "", s or "")
    s = tr_fold(s)
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return s.strip()


# ---- yalın .xlsx okuyucu (standart kütüphane) ------------------------------------------------

def _col_index(ref: str) -> tuple[int, int]:
    m = re.fullmatch(r"([A-Z]+)(\d+)", ref)
    if not m:
        raise TbbParseError(f"hücre adresi tanınmadı: {ref}")
    col = 0
    for ch in m.group(1):
        col = col * 26 + (ord(ch) - 64)
    return int(m.group(2)), col


def read_xlsx(raw: bytes) -> dict[str, dict[str, object]]:
    """{sayfa adı: {hücre adresi: değer}}. Değer: str, int veya float. Biçim/formül yok sayılır (önbellek değeri okunur)."""
    try:
        zf = zipfile.ZipFile(BytesIO(raw))
    except zipfile.BadZipFile as e:
        raise TbbParseError("dosya .xlsx değil") from e
    names = set(zf.namelist())
    shared: list[str] = []
    if "xl/sharedStrings.xml" in names:
        root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
        for si in root.findall("m:si", _NS):
            shared.append("".join(t.text or "" for t in si.iter(f"{{{_NS['m']}}}t")))
    wb = ET.fromstring(zf.read("xl/workbook.xml"))
    rels = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
    targets = {r.get("Id"): r.get("Target") for r in rels.findall(f"{{{_PKG_REL_NS}}}Relationship")}
    out: dict[str, dict[str, object]] = {}
    for sh in wb.findall("m:sheets/m:sheet", _NS):
        target = targets.get(sh.get(f"{{{_REL_NS}}}id"), "")
        path = target.lstrip("/") if target.startswith("/") else "xl/" + target
        if path not in names:
            continue
        cells: dict[str, object] = {}
        root = ET.fromstring(zf.read(path))
        for c in root.iter(f"{{{_NS['m']}}}c"):
            ref, typ = c.get("r"), c.get("t")
            v = c.find("m:v", _NS)
            if typ == "s" and v is not None:
                val: object = shared[int(v.text or 0)]
            elif typ == "inlineStr":
                val = "".join(t.text or "" for t in c.iter(f"{{{_NS['m']}}}t"))
            elif typ in ("str", "e") and v is not None:
                val = v.text or ""
            elif v is not None and v.text is not None:
                f = float(v.text)
                val = int(f) if f.is_integer() else f
            else:
                continue
            if ref:
                cells[ref] = val
        out[sh.get("name") or ""] = cells
    return out


# ---- Tablo 1 ayrıştırma ----------------------------------------------------------------------

@dataclass(frozen=True)
class CellValue:
    value: int | None  # None: tabloda "-" ya da boş (veri yok)
    sheet: str
    cell: str
    label: str  # tablodaki özgün satır etiketi


@dataclass(frozen=True)
class ParsedFile:
    year: int
    quarter: int
    title: str
    coverage_note: str  # "* Yurtiçi ve yurtdışı şube sayıları toplamından oluşmaktadır." vb.
    rows: dict[str, CellValue]  # norm_label → değer


_TITLE_RE = re.compile(r"tablo\s*1\b(.*?)itibar", re.S)  # katlanmış (tr_fold) başlığa uygulanır


def _find_table1(book: dict[str, dict[str, object]]) -> tuple[str, dict[str, object], str]:
    for name, cells in book.items():
        a1 = cells.get("A1")
        if isinstance(a1, str) and _TITLE_RE.search(tr_fold(a1)) and "sube" in tr_fold(a1):
            return name, cells, a1.strip()
    raise TbbParseError("'Tablo 1 … İtibarıyla Banka, Şube ve Çalışan Sayıları' sayfası bulunamadı")


def _title_period(title: str) -> tuple[int, int]:
    m = _TITLE_RE.search(tr_fold(title))
    seg = m.group(1) if m else ""
    mm = re.search(r"(mart|haziran|eylul|aralik)\s+(\d{4})", seg)
    if not mm:
        raise TbbParseError(f"tablo başlığında dönem tanınmadı: {title!r}")
    return int(mm.group(2)), MONTH_NAME_TO_Q[mm.group(1)]


def parse_workbook(raw: bytes) -> ParsedFile:
    book = read_xlsx(raw)
    sheet, cells, title = _find_table1(book)
    year, quarter = _title_period(title)
    grid: dict[tuple[int, int], tuple[str, object]] = {}
    for ref, val in cells.items():
        grid[_col_index(ref)] = (ref, val)
    # "Şube" başlıklı sütunlar (ilk 6 satır içinde)
    branch_cols = sorted({c for (r, c), (_, v) in grid.items() if r <= 6 and isinstance(v, str) and tr_fold(v).strip().startswith("sube")})
    if not branch_cols:
        raise TbbParseError("'Şube Sayısı' sütun başlığı bulunamadı")
    rows: dict[str, CellValue] = {}
    coverage = ""
    for (r, c), (ref, val) in sorted(grid.items()):
        if not isinstance(val, str):
            continue
        folded = tr_fold(val)
        if "yurtici ve yurtdisi sube" in folded.replace("-", "").replace(" ", " "):
            coverage = re.sub(r"\s+", " ", val).strip()
        if r <= 4 or val.strip().startswith("*") or len(val) > 120:
            continue
        right = [bc for bc in branch_cols if bc > c]
        if not right:
            continue
        bc = right[0]
        # ad sütunu ile şube sütunu arasında başka bir ad sütunu (blok) olmamalı: en fazla 3 sütun mesafe
        if bc - c > 3:
            continue
        key = norm_label(val)
        if not key:
            continue
        target_ref = _ref(r, bc)
        raw_v = cells.get(target_ref)
        if isinstance(raw_v, (int, float)) and not isinstance(raw_v, bool):
            if float(raw_v) != int(raw_v) or raw_v < 0:
                raise TbbParseError(f"{target_ref}: şube sayısı tam sayı değil ({raw_v!r})")
            v: int | None = int(raw_v)
        elif raw_v is None or (isinstance(raw_v, str) and raw_v.strip() in ("", "-", "–")):
            v = None
        else:
            raise TbbParseError(f"{target_ref}: şube sayısı tanınmadı ({raw_v!r})")
        if key in rows:
            raise TbbParseError(f"satır etiketi iki kez geçiyor: {val!r}")
        rows[key] = CellValue(v, sheet, target_ref, re.sub(r"\s+", " ", val).strip())
    if len(rows) < 10:
        raise TbbParseError("tabloda beklenenden az satır var")
    return ParsedFile(year, quarter, title, coverage, rows)


def _ref(row: int, col: int) -> str:
    s = ""
    while col:
        col, rem = divmod(col - 1, 26)
        s = chr(65 + rem) + s
    return f"{s}{row}"


def bank_values(parsed: ParsedFile, banks: Iterable[Bank] = SIX_LISTED_BANKS) -> dict[str, CellValue | None]:
    """Banka id → hücre (tabloda yoksa None)."""
    return {b.id: parsed.rows.get(norm_label(b.source_label)) for b in banks}


# ---- dönemler ve ağ (yalnız okuma) -----------------------------------------------------------

def quarters(start: tuple[int, int], end: tuple[int, int]) -> list[tuple[int, int]]:
    out, (y, q) = [], start
    while (y, q) <= end:
        out.append((y, q))
        y, q = (y + 1, 1) if q == 4 else (y, q + 1)
    return out


def period_key(y: int, q: int) -> str:
    return f"{y}-Q{q}"


def page_url(y: int, q: int) -> str:
    return PAGE_URL.format(year=y, month=MONTH_SLUG[q])


_ATTACH_RE = re.compile(r'href="(/download/node/\d+/field_raporlar_ekler/\d+)"')


def attachment_links(html: str) -> list[str]:
    return list(dict.fromkeys(_ATTACH_RE.findall(html)))


def filename_from_disposition(cd: str) -> str:
    m = re.search(r"filename\*=utf-8''([^;]+)", cd or "", re.I)
    if m:
        return unquote(m.group(1)).strip()
    m = re.search(r'filename="([^"]+)"', cd or "") or re.search(r"filename=([^;\s]+)", cd or "")
    return m.group(1).strip() if m else ""


@dataclass(frozen=True)
class Download:
    page_url: str
    file_url: str
    file_name: str
    content: bytes


def fetch_quarter(y: int, q: int, get: Callable, head: Callable, headers: dict[str, str], pause: float = 1.0) -> Download | None:
    """Çeyrek sayfasındaki Excel ekini indirir; sayfa ya da Excel eki yoksa None. Yalnız GET/HEAD, oturum/çerez yok."""
    url = page_url(y, q)
    resp = get(url, headers=headers, timeout=30)
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    for link in attachment_links(resp.text):
        time.sleep(pause)
        h = head(BASE + link, headers=headers, timeout=30, allow_redirects=True)
        if h.status_code != 200:
            continue
        ct = h.headers.get("Content-Type", "")
        if "spreadsheetml" not in ct:
            continue
        time.sleep(pause)
        f = get(BASE + link, headers=headers, timeout=60)
        f.raise_for_status()
        return Download(url, BASE + link, filename_from_disposition(h.headers.get("Content-Disposition", "")), f.content)
    return None
