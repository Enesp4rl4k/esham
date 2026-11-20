"""KAP Genel Bilgi Formu iştirak ayrıştırıcısı — sentetik RSC yükü (ağ yok)."""
import json

from esham.sources.kap_holdings import extract_stakes, fold_title, match_listed, parse_pct


def _payload(rows):
    objs = ",".join(json.dumps(r, ensure_ascii=False, separators=(",", ":")) for r in rows)  # KAP yükü sıkıştırılmış JSON
    return f'..."rows":[{objs}]...'


ROWS = [
    {"companyTitle": "Ford Otomotiv Sanayi A.Ş.", "scopeOfActivitiesOfCompany": "Üretim", "taxNo": None,
     "paidInOrIssuedCapital": "3509100000", "capitalShareOfCompany": "1379871895",
     "monetaryUnit": {"key": "TRY", "text": "TRY"}, "ratioOfCapitalShareOfCompany": "39,32", "relationWithTheCompany": "İş Ortaklığı"},
    {"companyTitle": "Koç Medical B.V.", "monetaryUnit": {"key": "EUR", "text": "EUR"},
     "ratioOfCapitalShareOfCompany": "100", "relationWithTheCompany": "Bağlı Ortaklık"},
    {"companyTitle": "Boş Pay A.Ş.", "monetaryUnit": {"key": "TRY"}, "ratioOfCapitalShareOfCompany": "", "relationWithTheCompany": "İştirak"},
]


def test_parse_pct():
    assert parse_pct("39,32") == 39.32
    assert parse_pct("100") == 100.0
    assert parse_pct("1.234,5") == 1234.5
    assert parse_pct("") is None and parse_pct("x") is None


def test_extract_stakes_reads_nested_currency_and_skips_empty_pct():
    st = extract_stakes(_payload(ROWS))
    assert [(s["title"], s["pct"], s["relation"], s["currency"]) for s in st] == [
        ("Ford Otomotiv Sanayi A.Ş.", 39.32, "İş Ortaklığı", "TRY"),
        ("Koç Medical B.V.", 100.0, "Bağlı Ortaklık", "EUR"),
    ]


def test_extract_stakes_dedupes_repeated_table():
    st = extract_stakes(_payload(ROWS) + _payload(ROWS))
    assert len(st) == 2


def test_fold_title_matches_across_spelling():
    assert fold_title("Ford Otomotiv Sanayi A.Ş.") == fold_title("FORD OTOMOTİV SANAYİ A.Ş.")
    assert fold_title("Arçelik A.Ş.") == fold_title("ARÇELİK A.Ş.")
    assert fold_title("TÜPRAŞ-TÜRKİYE PETROL RAFİNERİLERİ A.Ş.") == fold_title("Tüpraş-Türkiye Petrol Rafinerileri A.Ş.")


def test_match_listed_assigns_ticker_only_when_known():
    m = {fold_title("FORD OTOMOTİV SANAYİ A.Ş."): "FROTO"}
    out = match_listed(extract_stakes(_payload(ROWS)), m)
    assert out[0]["ticker"] == "FROTO"
    assert out[1]["ticker"] is None


def test_extract_stakes_tolerates_spaced_json():
    spaced = "x" + ",".join(json.dumps(r, ensure_ascii=False) for r in ROWS) + "y"
    assert len(extract_stakes(spaced)) == 2


def test_match_listed_fuzzy_unique_subset_and_spelling_variants():
    tmap = {
        fold_title("TÜPRAŞ-TÜRKİYE PETROL RAFİNERİLERİ A.Ş."): "TUPRS",
        fold_title("TÜRK TRAKTÖR VE ZİRAAT MAKİNELERİ A.Ş."): "TTRAK",
        fold_title("TÜRKİYE İŞ BANKASI A.Ş."): "ISCTR",
        fold_title("TÜRKİYE GARANTİ BANKASI A.Ş."): "GARAN",
    }
    stakes = [
        {"title": "Türkiye Petrol Rafinerileri A.Ş.", "pct": 3.7, "relation": "", "currency": "TRY"},
        {"title": "Türk Traktör ve Ziraat Makinaları A.Ş.", "pct": 37.5, "relation": "", "currency": "TRY"},
        {"title": "Türkiye Bankası A.Ş.", "pct": 5.0, "relation": "", "currency": "TRY"},   # belirsiz: 2 aday → eşleşmez
        {"title": "Bilinmeyen Şirket A.Ş.", "pct": 1.0, "relation": "", "currency": "TRY"},
    ]
    out = {s["title"]: s["ticker"] for s in match_listed(stakes, tmap)}
    assert out["Türkiye Petrol Rafinerileri A.Ş."] == "TUPRS"
    assert out["Türk Traktör ve Ziraat Makinaları A.Ş."] == "TTRAK"
    assert out["Türkiye Bankası A.Ş."] is None
    assert out["Bilinmeyen Şirket A.Ş."] is None
