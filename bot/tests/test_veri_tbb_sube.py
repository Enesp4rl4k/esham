"""TBB şube sayıları: ayrıştırıcı (sentetik fikstür), veri kümesi üretimi, ağ katmanı (sahte), tarafsız dil, PNG kartı.

Ağ YOK: fikstür tests/fixtures/make_tbb_sube_fixture.py ile üretilmiş SENTETİK bir dosyadır (gerçek TBB dosyası depoya
konmaz; bkz. docs/veri-grafikleri.md).
"""
import hashlib
import json
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

from esham import neutral
from esham.jobs import publish_veri_tbb_sube as job
from esham.publishing import veri_cards
from esham.sources import tbb_sube as T

FIX = Path(__file__).parent / "fixtures"
RAW = (FIX / "tbb_sube_sentetik.xlsx").read_bytes()
import importlib.util

_spec = importlib.util.spec_from_file_location("mkfix", FIX / "make_tbb_sube_fixture.py")
mkfix = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mkfix)  # type: ignore[union-attr]

META = {"name": "Sentetik.xlsx", "url": "https://www.tbb.org.tr/download/x", "page": "https://www.tbb.org.tr/istatistiki-raporlar/x", "retrieved": "2026-11-27"}


# ---- ayrıştırıcı ---------------------------------------------------------------------------------

def test_committed_fixture_matches_generator():
    # bayt eşitliği zlib sürümüne bağlı olabilir; içerik (hücreler) eşitliği denetlenir
    assert T.read_xlsx(RAW) == T.read_xlsx(mkfix.build()), "fikstür üreticiyle aynı olmalı (python tests/fixtures/make_tbb_sube_fixture.py)"


def test_parse_fixture_reads_branch_column_of_both_blocks():
    p = T.parse_workbook(RAW)
    assert (p.year, p.quarter) == (2026, 3)
    assert "yurtdışı şube" in p.coverage_note
    v = T.bank_values(p)
    assert {k: c.value for k, c in v.items()} == {"akbank": 111, "garanti": 222, "halkbank": 303, "isbank": 505, "vakifbank": 404, "yapikredi": 606}
    assert v["garanti"].cell == "H8" and v["garanti"].sheet == "sayı"  # ikinci blok (F/H sütunları)
    assert v["vakifbank"].label == "Türkiye Vakıflar Bankası T.A.O."  # fazladan boşluk temizlenir
    assert p.rows["ornek kapanan bank a s"].value is None  # "-" → veri yok (sıfır DEĞİL)


def test_bank_missing_from_table_is_none():
    raw = mkfix.build(overrides={"A16": "Başka Bank A.Ş."})
    assert T.bank_values(T.parse_workbook(raw))["akbank"] is None


def test_title_variants_and_unknown_layouts():
    old = mkfix.build(title="Tablo 1  30 Eylül 2017 İtibariyle Banka, Şube ve Çalışan Sayıları ")
    assert (T.parse_workbook(old).year, T.parse_workbook(old).quarter) == (2017, 3)
    with pytest.raises(T.TbbParseError):
        T.parse_workbook(mkfix.build(title="Tablo 2 Öğrenim Durumu"))
    with pytest.raises(T.TbbParseError):
        T.parse_workbook(b"not a zip")
    with pytest.raises(T.TbbParseError):
        T.parse_workbook(mkfix.build(overrides={"C16": "yüz on bir"}))
    with pytest.raises(T.TbbParseError):
        T.parse_workbook(mkfix.build(overrides={"C16": 11.5}))
    with pytest.raises(T.TbbParseError):
        T.parse_workbook(mkfix.build(overrides={"C3": "Toplam", "H3": "Toplam"}))


# ---- veri kümesi ----------------------------------------------------------------------------------

def _entry(year: int, q: int, **over):
    months = {1: "Mart", 2: "Haziran", 3: "Eylül", 4: "Aralık"}
    raw = mkfix.build(title=f"Tablo 1   {months[q]} {year} İtibarıyla Banka, Şube ve Çalışan Sayıları ", overrides=over)
    return T.parse_workbook(raw), {**META, "name": f"{year}-{q}.xlsx"}


def test_build_dataset_contiguous_periods_and_gaps_are_null():
    entries = {"2026-Q1": _entry(2026, 1), "2026-Q3": _entry(2026, 3, C16=120)}
    ds = job.build_dataset(entries, "2026-11-27")
    assert ds["periods"] == ["2026-Q1", "2026-Q2", "2026-Q3"]
    ak = next(s for s in ds["series"] if s["id"] == "akbank")
    assert ak["values"] == [111, None, 120]  # eksik çeyrek doldurulmaz
    assert ak["provenance"][1] is None
    assert ak["provenance"][2] == {"file": "2026-Q3", "sheet": "sayı", "cell": "C16", "label": "Akbank T.A.Ş."}
    assert set(ds["files"]) == {"2026-Q1", "2026-Q3"}
    assert ds["breaks"] == [] and ds["sample"] is False and ds["unit"] == "adet"
    assert job.validate(ds) == []
    json.dumps(ds, ensure_ascii=False)


def test_build_dataset_rejects_file_from_other_period():
    with pytest.raises(T.TbbParseError):
        job.build_dataset({"2026-Q2": _entry(2026, 3)}, "2026-11-27")


def test_coverage_note_change_becomes_break():
    e2 = _entry(2026, 2, A23="* Yalnızca yurtiçi şubeler.")
    ds = job.build_dataset({"2026-Q1": _entry(2026, 1), "2026-Q2": e2}, "2026-11-27")
    assert [b["period"] for b in ds["breaks"]] == ["2026-Q2"]


def test_validate_catches_gap_and_missing_provenance():
    ds = job.build_dataset({"2026-Q1": _entry(2026, 1), "2026-Q2": _entry(2026, 2)}, "2026-11-27")
    bad = json.loads(json.dumps(ds))
    bad["periods"][1] = "2026-Q3"
    assert any("kesintisiz" in e for e in job.validate(bad))
    bad = json.loads(json.dumps(ds))
    bad["series"][0]["provenance"][0] = None
    assert any("kaynak eksik" in e for e in job.validate(bad))


def test_existing_dataset_roundtrip_is_stable(tmp_path):
    ds = job.build_dataset({"2026-Q1": _entry(2026, 1), "2026-Q2": _entry(2026, 2)}, "2026-11-27")
    out = tmp_path / "x.json"
    assert job.write(ds, out) is True
    again = job.build_dataset(job._entries_from_existing(json.loads(out.read_text(encoding="utf-8"))), "2026-12-01")
    assert job.write(again, out) is False  # yalnız tarih farklı → dosyaya dokunulmaz


# ---- ağ katmanı (sahte istemci; yalnız GET/HEAD) --------------------------------------------------

def test_fetch_quarter_picks_spreadsheet_attachment():
    page = '<a href="/download/node/1/field_raporlar_ekler/10">pdf</a><a href="/download/node/1/field_raporlar_ekler/11">xlsx</a>'
    calls = []

    def get(url, **kw):
        calls.append(("GET", url, kw["headers"]))
        if url.endswith("-banka-calisan-ve-sube-bilgileri"):
            return SimpleNamespace(status_code=200, text=page, raise_for_status=lambda: None)
        return SimpleNamespace(status_code=200, content=RAW, raise_for_status=lambda: None)

    def head(url, **kw):
        calls.append(("HEAD", url, kw["headers"]))
        ct = "application/pdf" if url.endswith("/10") else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        cd = "attachment; filename=Banka_Calisan_ve_Sube_Sayilari-Eylul_2026.xlsx"
        return SimpleNamespace(status_code=200, headers={"Content-Type": ct, "Content-Disposition": cd})

    dl = T.fetch_quarter(2026, 3, get, head, {"User-Agent": "generic"}, pause=0)
    assert dl is not None and dl.file_url.endswith("/11") and dl.file_name == "Banka_Calisan_ve_Sube_Sayilari-Eylul_2026.xlsx"
    assert dl.page_url == "https://www.tbb.org.tr/istatistiki-raporlar/2026-eylul-banka-calisan-ve-sube-bilgileri"
    assert {c[0] for c in calls} == {"GET", "HEAD"}
    assert all(set(c[2]) == {"User-Agent"} for c in calls)  # çerez/oturum/kişisel başlık yok


def test_fetch_quarter_none_when_page_has_no_spreadsheet():
    get = lambda url, **kw: SimpleNamespace(status_code=200, text="<p>ek yok</p>", raise_for_status=lambda: None)  # noqa: E731
    assert T.fetch_quarter(2026, 4, get, None, {}, pause=0) is None
    get404 = lambda url, **kw: SimpleNamespace(status_code=404, text="", raise_for_status=lambda: None)  # noqa: E731
    assert T.fetch_quarter(2026, 4, get404, None, {}, pause=0) is None


def test_filename_from_disposition_variants():
    assert T.filename_from_disposition("attachment; filename=A_B.xlsx") == "A_B.xlsx"
    assert T.filename_from_disposition('attachment; filename="x.xlsx"; filename*=utf-8\'\'%C3%87al%C4%B1%C5%9Fan.xlsx') == "Çalışan.xlsx"
    assert T.quarters((2017, 3), (2018, 2)) == [(2017, 3), (2017, 4), (2018, 1), (2018, 2)]


# ---- tarafsız dil ---------------------------------------------------------------------------------

def test_generated_texts_are_neutral():
    ds = job.build_dataset({"2026-Q1": _entry(2026, 1)}, "2026-11-27")
    texts = [ds["title"], ds["kicker"], ds["measure"], ds["coverage"], ds["description"], ds["source"]["terms"], *ds["methodology"],
             *(s["label"] for s in ds["series"])]
    for t in texts:
        assert neutral.find_banned(t) == [], t


# ---- PNG kartı (sahne → piksel) -------------------------------------------------------------------

SCENE = {
    "w": 320, "h": 180, "theme": "dark",
    "palette": {"bg": "#0a0a0a", "fg": "#f0ede8", "muted": "#a8a39b", "grid": "#232323", "accent": "#e8a030", "s0": "#e69f00", "s1": "#56b4e9"},
    "items": [
        {"k": "rect", "x": 0, "y": 0, "w": 320, "h": 180, "fill": "bg"},
        {"k": "line", "x1": 10, "y1": 150, "x2": 310, "y2": 150, "stroke": "grid", "sw": 1.5},
        {"k": "line", "x1": 10, "y1": 120, "x2": 310, "y2": 120, "stroke": "grid", "sw": 1, "dash": [4, 4]},
        {"k": "path", "pts": [[20, 140], [100, 100], [180, 110]], "stroke": "s0", "sw": 3},
        {"k": "circle", "x": 260, "y": 90, "r": 3, "fill": "s1", "stroke": "bg", "sw": 1},
        {"k": "poly", "pts": [[200, 60], [210, 70], [200, 80], [190, 70]], "fill": "s1"},
        {"k": "text", "x": 10, "y": 30, "size": 18, "font": "display", "anchor": "start", "spans": [{"text": "Es", "fill": "accent"}, {"text": "ham", "fill": "fg"}]},
        {"k": "text", "x": 310, "y": 30, "size": 12, "font": "body", "anchor": "end", "spans": [{"text": "1.119", "fill": "fg"}]},
        {"k": "text", "x": 160, "y": 170, "size": 12, "font": "bodyBold", "anchor": "middle", "spans": [{"text": "Akbank ", "fill": "s0"}, {"text": "601", "fill": "fg"}]},
    ],
    "meta": {"slug": "deneme", "variant": "koyu-etiket"},
}


def test_render_scene_draws_every_text_and_embeds_scene_hash(tmp_path):
    raw = json.dumps(SCENE).encode("utf-8")
    img, texts = veri_cards.render_scene(json.loads(raw))
    assert img.size == (320, 180)
    assert texts == ["Esham", "1.119", "Akbank 601"]  # metinler sahnedeki gibi, değiştirilmeden
    assert img.getpixel((5, 5)) == (10, 10, 10)
    out = tmp_path / "k.png"
    veri_cards.save_png(img, out, raw, SCENE)
    back = Image.open(BytesIO(out.read_bytes()))
    assert back.text["esham:scene-sha256"] == hashlib.sha256(raw).hexdigest()
    assert back.text["esham:slug"] == "deneme"


def test_render_scene_rejects_unknown_item():
    bad = {**SCENE, "items": [{"k": "blob"}]}
    with pytest.raises(ValueError):
        veri_cards.render_scene(bad)
