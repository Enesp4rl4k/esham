"""BIST hisse evreni — ticker, ad, sektör, finansal (banka/sigorta/holding?) bayrağı.

Tek kaynak: web ve bot bunu `web/public/data/universe.json` olarak paylaşır.
Liste elle derlenmiştir (BIST 100 ağırlıklı); yeni hisse eklemek için tek satır yeterli.
Verisi bulunamayan ticker üretimde atlanır ve loglanır.
`financial=True` → FAVÖK/FD/stok oranları hesaplanmaz (bkz. ratios.FINANCIAL_RATIO_KEYS).
"""
from __future__ import annotations

# (ticker, şirket adı, sektör, financial)
_RAW: list[tuple[str, str, str, bool]] = [
    # Bankalar
    ("AKBNK", "Akbank", "Bankacılık", True), ("GARAN", "Garanti BBVA", "Bankacılık", True),
    ("ISCTR", "İş Bankası (C)", "Bankacılık", True), ("YKBNK", "Yapı Kredi Bankası", "Bankacılık", True),
    ("HALKB", "Halkbank", "Bankacılık", True), ("VAKBN", "Vakıfbank", "Bankacılık", True),
    ("TSKB", "TSKB", "Bankacılık", True), ("SKBNK", "Şekerbank", "Bankacılık", True),
    ("ALBRK", "Albaraka Türk", "Bankacılık", True), ("QNBTR", "QNB Bank", "Bankacılık", True),
    # Sigorta / finans
    ("AKGRT", "Aksigorta", "Sigorta", True), ("ANSGR", "Anadolu Sigorta", "Sigorta", True),
    ("TURSG", "Türkiye Sigorta", "Sigorta", True), ("ANHYT", "Anadolu Hayat", "Sigorta", True),
    ("ISMEN", "İş Yatırım", "Aracı Kurum", True), ("GLBMD", "Global Menkul", "Aracı Kurum", True),
    # Holdingler
    ("KCHOL", "Koç Holding", "Holding", False), ("SAHOL", "Sabancı Holding", "Holding", False),
    ("DOHOL", "Doğan Holding", "Holding", False), ("AGHOL", "AG Anadolu Grubu", "Holding", False),
    ("ALARK", "Alarko Holding", "Holding", False), ("TKFEN", "Tekfen Holding", "Holding", False),
    ("ENKAI", "Enka İnşaat", "İnşaat", False), ("GSDHO", "GSD Holding", "Holding", False),
    # Sanayi / savunma / otomotiv
    ("THYAO", "Türk Hava Yolları", "Ulaştırma", False), ("PGSUS", "Pegasus", "Ulaştırma", False),
    ("TAVHL", "TAV Havalimanları", "Ulaştırma", False), ("ASELS", "Aselsan", "Savunma", False),
    ("FROTO", "Ford Otosan", "Otomotiv", False), ("TOASO", "Tofaş", "Otomotiv", False),
    ("DOAS", "Doğuş Otomotiv", "Otomotiv", False), ("OTKAR", "Otokar", "Otomotiv", False),
    ("TTRAK", "Türk Traktör", "Otomotiv", False), ("ARCLK", "Arçelik", "Dayanıklı Tüketim", False),
    ("VESTL", "Vestel", "Dayanıklı Tüketim", False), ("VESBE", "Vestel Beyaz Eşya", "Dayanıklı Tüketim", False),
    ("EREGL", "Ereğli Demir Çelik", "Metal", False), ("KRDMD", "Kardemir (D)", "Metal", False),
    ("ISDMR", "İskenderun Demir Çelik", "Metal", False), ("BRSAN", "Borusan Boru", "Metal", False),
    # KOZAL / KOZAA / KERVT: Yahoo Finance .IS için veri döndürmüyor (404/delisted, 13 Kas 2026) → alternatif kaynak
    # (KAP, Faz C) gelene kadar evrende yok.
    ("SASA", "Sasa Polyester", "Kimya", False), ("PETKM", "Petkim", "Kimya", False),
    ("GUBRF", "Gübre Fabrikaları", "Kimya", False), ("HEKTS", "Hektaş", "Kimya", False),
    ("AKSA", "Aksa Akrilik", "Kimya", False), ("TUPRS", "Tüpraş", "Enerji", False),
    ("ASTOR", "Astor Enerji", "Elektrikli Teçhizat", False), ("KONTR", "Kontrolmatik", "Elektrikli Teçhizat", False),
    ("EUPWR", "Europower Enerji", "Elektrikli Teçhizat", False), ("ODAS", "Odaş Elektrik", "Enerji", False),
    ("ENJSA", "Enerjisa Enerji", "Enerji", False), ("AKSEN", "Aksa Enerji", "Enerji", False),
    ("ZOREN", "Zorlu Enerji", "Enerji", False), ("CWENE", "CW Enerji", "Enerji", False),
    ("ALFAS", "Alfa Solar Enerji", "Enerji", False), ("YEOTK", "Yeo Teknoloji", "Enerji", False),
    ("SISE", "Şişecam", "Cam", False), ("CIMSA", "Çimsa", "Çimento", False),
    ("OYAKC", "Oyak Çimento", "Çimento", False), ("AKCNS", "Akçansa", "Çimento", False),
    ("BTCIM", "Batıçim", "Çimento", False), ("NUHCM", "Nuh Çimento", "Çimento", False),
    # Perakende / gıda
    ("BIMAS", "BİM Mağazalar", "Perakende", False), ("MGROS", "Migros", "Perakende", False),
    ("SOKM", "Şok Marketler", "Perakende", False), ("ULKER", "Ülker", "Gıda", False),
    ("AEFES", "Anadolu Efes", "İçecek", False), ("CCOLA", "Coca-Cola İçecek", "İçecek", False),
    ("TATGD", "Tat Gıda", "Gıda", False), ("BANVT", "Banvit", "Gıda", False),
    ("ULUUN", "Ulusoy Un", "Gıda", False), ("TUKAS", "Tukaş", "Gıda", False),
    ("PNSUT", "Pınar Süt", "Gıda", False),
    ("MAVI", "Mavi Giyim", "Perakende", False), ("BIZIM", "Bizim Toptan", "Perakende", False),
    # Telekom / teknoloji
    ("TCELL", "Turkcell", "Telekomünikasyon", False), ("TTKOM", "Türk Telekom", "Telekomünikasyon", False),
    ("LOGO", "Logo Yazılım", "Teknoloji", False), ("MIATK", "Mia Teknoloji", "Teknoloji", False),
    ("REEDR", "Reeder Teknoloji", "Teknoloji", False), ("SMRTG", "Smart Güneş Enerjisi", "Elektrikli Teçhizat", False),
    ("KAREL", "Karel Elektronik", "Teknoloji", False), ("INDES", "İndeks Bilgisayar", "Teknoloji", False),
    # GYO / inşaat / sağlık / diğer
    ("EKGYO", "Emlak Konut GYO", "GYO", False), ("ISGYO", "İş GYO", "GYO", False),
    ("TRGYO", "Torunlar GYO", "GYO", False), ("MPARK", "MLP Sağlık", "Sağlık", False),
    ("LKMNH", "Lokman Hekim", "Sağlık", False), ("SELEC", "Selçuk Ecza Deposu", "Sağlık", False),
    ("DOCO", "DO&CO", "Turizm", False), ("MAALT", "Marmaris Altınyunus", "Turizm", False),
    ("TKNSA", "Teknosa", "Perakende", False), ("KLSER", "Kaleseramik", "İnşaat Malz.", False),
    ("CANTE", "Çan2 Termik", "Enerji", False), ("BERA", "Bera Holding", "Holding", False),
    ("TABGD", "TAB Gıda", "Gıda", False), ("GESAN", "Girişim Elektrik", "Elektrikli Teçhizat", False),
    ("KMPUR", "Kimteks Poliüretan", "Kimya", False), ("BRYAT", "Borusan Yatırım", "Holding", False),
    ("ECILC", "Eczacıbaşı İlaç", "Sağlık", False), ("SOKE", "Söke Değirmencilik", "Gıda", False),
]


def load_universe() -> list[dict[str, object]]:
    seen: set[str] = set()
    out: list[dict[str, object]] = []
    for ticker, name, sector, financial in _RAW:
        if ticker in seen:
            continue
        seen.add(ticker)
        out.append({"ticker": ticker, "name": name, "sector": sector, "financial": financial})
    return out


def is_financial(ticker: str) -> bool:
    t = ticker.strip().upper()
    return any(u["ticker"] == t and u["financial"] for u in load_universe())
