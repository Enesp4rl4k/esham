"""SENTETİK TBB 'Banka, Çalışan ve Şube Bilgileri' Excel dosyası üretir (test girdisi).

Düzen gerçek dosyayla aynıdır (kapak / içindekiler / sayı sayfaları; 'Tablo 1 … İtibarıyla' başlığı; iki sütun bloğu;
'Şube / Sayısı*' başlıkları; dipnot; paylaşılan metinler), ama TÜM SAYILAR UYDURMADIR. TBB raporu kaynak gösterilerek
yapılan alıntılar dışında çoğaltılamadığı için gerçek dosya depoya konmaz.

Kullanım: python tests/fixtures/make_tbb_sube_fixture.py  → tests/fixtures/tbb_sube_sentetik.xlsx
"""
from __future__ import annotations

import zipfile
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

OUT = Path(__file__).with_name("tbb_sube_sentetik.xlsx")


def _col(c: int) -> str:
    s = ""
    while c:
        c, r = divmod(c - 1, 26)
        s = chr(65 + r) + s
    return s


def build(title: str = "Tablo 1   Eylül 2026 İtibarıyla Banka, Şube ve Çalışan Sayıları ", overrides: dict[str, object] | None = None) -> bytes:
    # (satır, sütun) → değer. Sütunlar: A ad, B banka sayısı, C şube, D çalışan | F ad, G, H şube, I çalışan
    cells: dict[str, object] = {
        "A1": title,
        "B3": "Banka", "C3": "Şube ", "D3": "Çalışan", "G3": "Banka", "H3": "Şube ", "I3": "Çalışan",
        "B4": "Sayısı", "C4": "Sayısı*", "D4": "Sayısı", "G4": "Sayısı", "H4": "Sayısı*", "I4": "Sayısı",
        "A5": "Sektör Toplamı", "B5": 99, "C5": 9999, "D5": 99999, "F5": "Yabancı Sermayeli Bankalar", "G5": 9, "H5": 999, "I5": 9999,
        "A7": "Mevduat Bankaları", "B7": 9, "C7": 8888, "D7": 88888, "F7": "Örnek Yabancı Bank A.Ş.", "H7": 11, "I7": 111,
        "A9": "Kamu Sermayeli Bankalar", "B9": 3, "C9": 3333, "D9": 33333, "F8": "Türkiye Garanti Bankası A.Ş.", "H8": 222, "I8": 2222,
        "A11": "Türkiye Cumhuriyeti Ziraat Bankası A.Ş.", "C11": 1001, "D11": 10001,
        "A12": "Türkiye Halk Bankası A.Ş.", "C12": 303, "D12": 3030,
        "A13": "Türkiye Vakıflar Bankası T.A.O.           ", "C13": 404, "D13": 4040,
        "A15": "Özel Sermayeli Bankalar", "B15": 5, "C15": 5555, "D15": 55555,
        "A16": "Akbank T.A.Ş.", "C16": 111, "D16": 1111,
        "A17": "Örnek Kapanan Bank A.Ş.**", "C17": "-", "D17": "-",
        "A18": "Türkiye İş Bankası A.Ş.", "C18": 505, "D18": 5050,
        "A19": "Yapı ve Kredi Bankası A.Ş.", "C19": 606, "D19": 6060,
        "A20": "Örnek Dijital Bank A.Ş. (dijital banka)", "C20": 1, "D20": 10,
        "A21": "Örnek Kalkınma Bankası A.Ş.", "C21": 7, "D21": 70,
        "A23": "* Yurtiçi ve yurtdışı şube sayıları toplamından oluşmaktadır.",
        "A24": "** SENTETİK TEST DOSYASI — değerler uydurmadır.",
    }
    cells.update(overrides or {})
    strings: list[str] = []
    sidx: dict[str, int] = {}

    def si(s: str) -> int:
        if s not in sidx:
            sidx[s] = len(strings)
            strings.append(s)
        return sidx[s]

    def sheet_xml(cs: dict[str, object]) -> str:
        import re

        rows: dict[int, list[str]] = {}
        for ref, v in cs.items():
            r = int(re.sub(r"[A-Z]", "", ref))
            if isinstance(v, str):
                rows.setdefault(r, []).append(f'<c r="{ref}" t="s"><v>{si(v)}</v></c>')
            else:
                rows.setdefault(r, []).append(f'<c r="{ref}"><v>{v}</v></c>')
        body = "".join(f'<row r="{r}">{"".join(sorted(c, key=lambda x: (len(x.split(chr(34))[1]), x)))}</row>' for r, c in sorted(rows.items()))
        return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>' + body + "</sheetData></worksheet>")

    sheets = [("kapak", {"A1": " "}), ("içindekiler", {"A1": "İçindekiler"}), ("sayı", cells)]
    sheet_xmls = [sheet_xml(c) for _, c in sheets]
    sst = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
           f'<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" count="{len(strings)}" uniqueCount="{len(strings)}">'
           + "".join(f"<si><t xml:space=\"preserve\">{escape(s)}</t></si>" for s in strings) + "</sst>")
    wb = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
          '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
          'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>'
          + "".join(f'<sheet name="{escape(n)}" sheetId="{i + 1}" r:id="rId{i + 1}"/>' for i, (n, _) in enumerate(sheets))
          + "</sheets></workbook>")
    rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            + "".join(f'<Relationship Id="rId{i + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{i + 1}.xml"/>' for i in range(len(sheets)))
            + f'<Relationship Id="rId{len(sheets) + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/sharedStrings" Target="sharedStrings.xml"/>'
            "</Relationships>")
    ct = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
          '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
          '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
          '<Default Extension="xml" ContentType="application/xml"/>'
          '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
          + "".join(f'<Override PartName="/xl/worksheets/sheet{i + 1}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>' for i in range(len(sheets)))
          + '<Override PartName="/xl/sharedStrings.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/>'
          "</Types>")
    root_rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                 '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                 '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
                 "</Relationships>")
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        # sabit zaman damgası: dosya her üretimde aynı baytlar
        def w(name: str, data: str) -> None:
            info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, data.encode("utf-8"))

        w("[Content_Types].xml", ct)
        w("_rels/.rels", root_rels)
        w("xl/workbook.xml", wb)
        w("xl/_rels/workbook.xml.rels", rels)
        for i, x in enumerate(sheet_xmls):
            w(f"xl/worksheets/sheet{i + 1}.xml", x)
        w("xl/sharedStrings.xml", sst)
    return buf.getvalue()


if __name__ == "__main__":
    OUT.write_bytes(build())
    print(OUT)
