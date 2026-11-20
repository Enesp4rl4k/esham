from esham.kap_merge import MAX_REVENUE_DIFF_PCT, choose_source, merge_statements, revenue_diff_pct


def q(date, rev=100.0, ni=10.0):
    return {"date": date, "revenue": rev, "net_income": ni}


def quarters(last="2026-09-30", rev=100.0, ni=10.0):
    dates = ["2025-12-31", "2026-03-31", "2026-06-30", last]
    return [q(d, rev, ni) for d in dates]


def doc(**kw):
    base = {"currency": "TRY", "quarterly": quarters(), "annual": [{"date": "2025-12-31", "currency": "TRY"}]}
    base.update(kw)
    return base


def test_kap_yok_yahoo_ve_neden_yok():
    assert choose_source(None, quarters(), 1.0) == ("Yahoo", None)


def test_uygun_kap_secilir():
    assert choose_source(doc(), quarters(), 1.0) == ("KAP", None)


def test_az_donem_yahoo():
    d = doc(quarterly=quarters()[:3])
    assert choose_source(d, quarters(), 1.0) == ("Yahoo", "kap_yetersiz_donem")


def test_eski_kap_yahoo():
    d = doc(quarterly=quarters(last="2026-06-30"))
    assert choose_source(d, quarters(last="2026-09-30"), 1.0) == ("Yahoo", "kap_eski")


def test_hasilat_farki_buyukse_yahoo():
    d = doc(quarterly=quarters(rev=40.0))  # %-60
    assert choose_source(d, quarters(rev=100.0), 1.0) == ("Yahoo", "kap_hasilat_farki_buyuk")


def test_net_kar_farki_olcut_degil():
    # Yahoo'nun net kâr hatası (DOAS/PETKM) KAP'ı seçmemizin nedeni; fark tek başına elemez
    d = doc(quarterly=quarters(ni=-5.0))
    assert choose_source(d, quarters(ni=10.0), 1.0)[0] == "KAP"


def test_dovizli_yahoo_kurla_karsilastirilir():
    # Yahoo USD 2 birim hasılat × 50 = 100 TL; KAP 100 TL → fark 0
    assert revenue_diff_pct(quarters(rev=100.0), quarters(rev=2.0), 50.0) == 0.0
    assert choose_source(doc(), quarters(rev=2.0), 50.0)[0] == "KAP"


def test_eksik_kalem_yahoo():
    qs = quarters()
    qs[-1]["net_income"] = None
    assert choose_source(doc(quarterly=qs), quarters(), 1.0) == ("Yahoo", "kap_eksik_kalem")


def test_yillik_kisa_ve_ayni_para_birimi_yahoo_yillik_korunur():
    yahoo_a = [{"date": "2024-12-31"}, {"date": "2025-12-31"}]
    kq, ka = merge_statements(doc(), quarters(), yahoo_a, "TRY")
    assert ka is yahoo_a and kq == doc()["quarterly"]


def test_para_birimi_farkliysa_kap_yillik():
    yahoo_a = [{"date": "2024-12-31"}, {"date": "2025-12-31"}]
    _, ka = merge_statements(doc(), quarters(), yahoo_a, "USD")
    assert ka == doc()["annual"]


def test_esik_makul():
    assert 20 <= MAX_REVENUE_DIFF_PCT <= 50
