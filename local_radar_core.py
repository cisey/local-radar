"""
Local Radar - Core Engine (v1.1.2)
Scrapes Google Maps to find highly-rated places around you.

v1.1.2 updates:
  - Tek ve modern HTML çıktısı (eski çift HTML / sade ayrımı kaldırıldı)
  - Yeni koyu tema (Karkamış tarzı) varsayılan şablon yapıldı
  - Yakınımda, Rota, WP butonları tamamen kaldırıldı
v1.1.1 updates:
  - Stop button now works during neighborhood lookup phase
v1.1.0 updates:
  - Overpass: admin_level=10 (mahalle) + place=neighbourhood/suburb node desteği
  - Neighborhood lookup: polygon + nearest node fallback (1.8 km)
  - MAH_RE: Google Maps "Mahalle, Cadde" formatını yakalar
  - Nominatim cache: ~250m grid (sorgu sayısı %70 azalır)
"""
import re, csv, math, time, json, os, urllib.request, urllib.parse, urllib.error, socket, html

# ======================= SETTINGS =======================
SECIM = "nizip"
MIN_PUAN = 0
MIN_OY = 0
EKRANDA_GOSTER = True
MAHALLE_BUL = True
IZGARA_AKTIF = True
SABIT_IZGARA = False
HUCRE_KM = 1.0
MAHALLE_TAKMA_AD = {"Fatih Sultan Mehmet": "Fatih Sultan"}
YENI_GUN = 30
# ========================================================
LOG = print
SURUM = "2026-10-30-v1.1.2-LocalRadar"

# ═══════════════════════════════════════════════════════════
# FILE NAMES (English)
# ═══════════════════════════════════════════════════════════
DOSYA_HAVUZ = "pool.json"
DOSYA_MAHALLE_ONBELLEK = "neighborhood_cache.json"
DOSYA_MANUEL = "manual_places.json"
DOSYA_SECICI = "working_selectors.json"
DOSYA_DEFTER = "scan_ledger.json"
DOSYA_HAM_HAVUZ = "raw_pool.json"
DOSYA_VERIM = "keyword_efficiency.json"
DOSYA_SINIR = "neighborhood_boundaries.json"
DOSYA_AYARLAR = "settings.json"
DOSYA_PROFILLER = "profiles.json"
DOSYA_HATA_LOG = "error_log.txt"
DOSYA_ELENENLER = "excluded_places.csv"
DOSYA_VERIM_RAPOR = "efficiency_report.txt"
DOSYA_TANI = "diagnostic"
DOSYA_TARAMA_HATA = "scan_error.png"

KLASOR_CIKTILAR = "output"

DOSYA_HEPSI_CSV = "local_radar_all.csv"
DOSYA_HEPSI_XLSX = "local_radar_all.xlsx"
DOSYA_HEPSI_JSON = "local_radar_all.json"
DOSYA_HEPSI_HTML = "local_radar_all.html"
DOSYA_HEPSI_HTML_SADE = "local_radar_all.html"  # Artık tek dosya
DOSYA_HEPSI_KML = "local_radar_all.kml"
# False: dev "HEPSİ" dosyaları (local_radar_all.*) üretilmez. Havuz (pool.json) yine güncellenir.
HEPSI_URET = False

KLASOR_TARAMA_JSON = "tarama_json"     # ilçe taramalarının ham/ara kayıt JSON'ları burada toplanır
DOSYA_HAM_PREFIX = KLASOR_TARAMA_JSON + "/raw_"
DOSYA_ARA_KAYIT_PREFIX = KLASOR_TARAMA_JSON + "/scan_resume_"

# Legacy aliases (internal use)
HAVUZ = DOSYA_HAVUZ
ONBELLEK_DOSYASI = DOSYA_MAHALLE_ONBELLEK
MANUEL_DOSYASI = DOSYA_MANUEL
SECICI_DOSYASI = DOSYA_SECICI
DEFTER = DOSYA_DEFTER
HAM_HAVUZ = DOSYA_HAM_HAVUZ
VERIM_DOSYASI = DOSYA_VERIM
SINIR_DOSYASI = DOSYA_SINIR


def manuel_mekanlari_oku():
    if not os.path.exists(MANUEL_DOSYASI):
        return []
    try:
        with open(MANUEL_DOSYASI, "r", encoding="utf-8") as f:
            veri = json.load(f)
    except Exception:
        return []
    return veri if isinstance(veri, list) else []


def manuel_kayitlari_uret(ayar, min_oy=MIN_OY, ilce_filtre=True):
    hedef = (ayar.get("ilce") or "").strip().lower()
    kayitlar = []
    for m in manuel_mekanlari_oku():
        if not isinstance(m, dict):
            continue
        ad = (m.get("ad") or "").strip()
        if not ad:
            continue
        m_ilce = (m.get("ilce") or "").strip().lower()
        if ilce_filtre and m_ilce and m_ilce != hedef:
            continue
        try:
            puan = float(m.get("puan", 0) or 0)
        except (TypeError, ValueError):
            puan = 0.0
        try:
            oy = int(m.get("yorum", 0) or 0)
        except (TypeError, ValueError):
            oy = 0
        tur_m = m.get("tur", "")
        if m.get("bolum") and m.get("grup"):
            bolum_m, grup_m = m["bolum"], m["grup"]
        else:
            bolum_m, grup_m = siniflandir(ad, tur_m, "")
        ilce_m = m.get("ilce") or ayar.get("ilce", "")
        link_m = m.get("link", "") or ("https://www.google.com/maps/search/"
                                       + urllib.parse.quote_plus((ad + " " + ilce_m).strip()))
        en_m, bo_m = m.get("enlem"), m.get("boylam")
        if en_m is None and m.get("link"):
            en_m, bo_m = koordinat(m["link"])
        payda = oy + max(min_oy, 10)
        skor = (oy / payda) * puan + (max(min_oy, 10) / payda) * 4.0
        kayitlar.append({
            "Yer": ad,
            "İlçe": m.get("ilce") or ayar.get("ilce", ""),
            "Mahalle": m.get("mahalle") or "Bilinmiyor",
            "Bölüm": bolum_m,
            "Grup": grup_m,
            "Puan": puan,
            "Yorum Sayısı": oy,
            "Güvenilir Skor": round(skor, 3),
            "Tür": tur_m,
            "Telefon": m.get("telefon", ""),
            "Fiyat": m.get("fiyat", ""),
            "Adres": m.get("adres", ""),
            "Enlem": en_m,
            "Boylam": bo_m,
            "Harita Linki": link_m,
            "kaynak": "manuel",
        })
    return kayitlar


def manuel_ekle(kayitlar, ayar, min_oy=MIN_OY, ilce_filtre=True):
    mevcut = {fold(r.get("Yer", "")) for r in kayitlar}
    for r in manuel_kayitlari_uret(ayar, min_oy, ilce_filtre):
        if fold(r["Yer"]) in mevcut:
            continue
        kayitlar.append(r)
        mevcut.add(fold(r["Yer"]))
    kayitlar.sort(key=lambda x: -x.get("Güvenilir Skor", 0))
    return kayitlar


# ---------- Search keywords ----------
YEMEK = ["restoran", "kebapçı", "lahmacun", "kahvaltı", "kafe", "pastane",
         "baklava", "tatlıcı", "dönerci", "lokanta", "çiğ köfte", "beyran",
         "katmer", "kahve", "dondurma", "fast food", "pizza", "tavuk döner",
         "burger", "pideci", "çorbacı", "balık restoranı"]

GEZI = ["gezilecek yer", "turistik yer", "tarihi yer", "müze", "kale", "tarihi han",
        "çarşı", "bedesten", "hamam", "cami", "kilise", "park", "mesire alanı",
        "seyir terası", "sinema", "tiyatro", "sanat galerisi"]

ALISVERIS = ["market", "süpermarket", "fırın", "kasap", "manav", "kuruyemiş", "avm",
             "giyim", "teknoloji mağazası", "kuyumcu", "kırtasiye", "fıstık"]

SAGLIK = ["hastane", "diş hekimi", "eczane", "veteriner", "klinik", "spor salonu",
          "kuaför", "berber"]

OTO = ["oto tamir", "lastikçi", "otopark", "benzin istasyonu", "çekici"]
KONAKLAMA = ["otel", "pansiyon", "apart"]
BANKA = ["banka", "atm", "kargo"]

DIGER = ALISVERIS + SAGLIK + OTO + KONAKLAMA + BANKA + ["düğün salonu", "çiçekçi", "petshop"]

KATEGORI_GRUPLARI = {"yemek": YEMEK, "gezi": GEZI, "alisveris": ALISVERIS, "saglik": SAGLIK,
                     "oto": OTO, "konaklama": KONAKLAMA, "banka": BANKA}

TUMU = list(dict.fromkeys(YEMEK + GEZI + DIGER))

MODLAR = {
    "Hızlı (yemek ve gezi, tek parça)":  dict(kategoriler=YEMEK[:10] + GEZI[:8], izgara=False),
    "Normal (yemek ve gezi, ızgaralı)":  dict(kategoriler=YEMEK + GEZI + ["kasap"], izgara=True),
    "Kapsamlı (her şey, ızgaralı)":      dict(kategoriler=TUMU, izgara=True),
}

# ---------- Categorization rules ----------
KURALLAR = [
    ("Alışveriş", "Giyim, Teknoloji, Mağaza",
     ["kale cam", "kale balkon", "kale kapı", "kale cam balkon",
      "cam balkon", "pvc", "alüminyum doğrama", "doğrama", "kale kilit", "çilingir", "anahtarcı",
      "hırdavat", "nalbur", "mobilya", "furniture", "halı mağaza", "fıstık halı", "fıstıkçılar halı",
      "güvenlik sistem", "kamera", "alarm", "elektrik", "elektirik",
      "iletişim merkezi", "turkcell", "vodafone", "türk telekom"]),
    ("Alışveriş", "Giyim, Teknoloji, Mağaza",
     ["giyim çarşı", "giyim çarşısı", "giyim mağaza", "ayakkabı çarşı",
      "tekstil çarşı", "kuyumcu çarşı"]),
    ("Diğer", "Diğer hizmetler",
     ["internet", "halı yıka", "halı temiz", "emlak", "gayrimenkul", "mezar", "kefalet", "kooperatif"]),

    ("Diğer", "Ulaşım ve Araç",
     ["otopark", "benzin", "petrol", "akaryakıt", "otogaz", "=shell", "=opet", "=bp", "bpet",
      "aytemiz", "alpet", "kadoil", "hypco", "sunpet", "=oto", "tamir", "lastik", "çekici",
      "vinç", "yol yardım", "yolyardım", "araç bakım", "araba yıkama", "oto yıkama",
      "kurtar", "otogar", "akü"]),

    ("Gezilecek yerler", "Camiler", ["cami", "camii", "mescit", "mescidi"]),
    ("Diğer", "Sağlık ve Bakım",
     ["=diş", "ortodonti", "veteriner", "klinik", "clinic", "poliklinik", "hastane", "eczane",
      "doktor", "=dr", "hekim", "sağlık", "medikal", "ortopedi", "diyetisyen", "fizik tedavi", "optik",
      "fitness", "spor salonu", "spor kulübü", "spor klubu", "gym", "kickboks", "fight",
      "voleybol", "basketbol", "yüzme", "kuaför", "berber", "barber", "güzellik", "beauty",
      "lazer", "epilasyon", "cilt bakım", "=salon", "=saloon"]),

    ("Kebap & Et", "Kebap",
     ["kebap", "kebab", "ciğer", "ciger", "dürüm", "döner", "iskender", "köfteci",
      "ocakbaşı", "mangal", "kavurma", "et lokantası"]),
    ("Tatlı & Pastane", "Tatlı",
     ["baklava", "künefe", "kadayıf", "dondurma", "tatlı", "pastane", "pasta",
      "katmer", "lokum", "helva", "çikolata", "waffle"]),
    ("Hızlı Atıştırmalık", "Hızlı",
     ["pide", "lahmacun", "tost", "börek", "çorba", "=paça", "kelle", "nohut",
      "pizza", "burger", "fast food", "sandviç", "çiğ köf", "tantuni", "büfe"]),
    ("Kafe & Kahvaltı", "Kafe",
     ["cafe", "kafe", "kahve", "coffee", "=çay", "nargile", "kahvaltı",
      "simit", "bistro", "كافتريا"]),
    ("Restoran", "Restoran",
     ["restoran", "restaurant", "lokanta", "ev yemek", "balık", "sofra",
      "nohutçu", "kelle paça", "beyran", "dinlenme tesisi", "tesisleri"]),

    ("Diğer", "Kargo ve Posta",
     ["kargo", "=ptt", "yurtiçi", "=aras", "=mng", "sürat", "=dhl", "=ups", "postane"]),
    ("Diğer", "Banka ve ATM",
     ["banka", "=bank", "=atm", "bankamatik", "ziraat", "=garanti", "halkbank", "vakıfbank", "akbank",
      "yapı kredi", "=qnb", "denizbank", "kuveyt türk", "=teb", "iş bankası", "is bankasi"]),
    ("Diğer", "Konaklama",
     ["otel", "konaklama", "pansiyon", "apart", "=hostel", "konukevi", "konuk evi",
      "öğretmenevi", "öğretmen evi", "uygulama oteli"]),
    ("Diğer", "Evcil Hayvan", ["petshop", "pet shop", "evcil"]),
    ("Diğer", "Çiçekçi", ["çiçekçi", "çiçekcilik", "çiçekçilik", "çiçekevi", "çiçek evi", "flower"]),
    ("Diğer", "Düğün ve Organizasyon",
     ["düğün", "dugun", "nikah", "organizasyon", "davet evi", "kır düğün", "kır düğünü", "plaza", "garden"]),

    ("Gezilecek yerler", "Eğlence ve Sanat",
     ["eğlence", "=oyun", "game center", "sinema", "tiyatro",
      "sanat galeri", "sanat merkezi", "kültür merkezi"]),
    ("Gezilecek yerler", "Gezi ve doğa",
     ["turistik", "antik", "müze", "seyir", "kamp", "millet bahçesi",
      "tarihi", "=kale", "=kalesi", "park", "şelale", "mağara", "ören",
      "plaj", "piknik", "mesire", "hamam", "tarihi çarşı", "bedesten",
      "kapalı çarşı", "kilise", "sinagog", "kervansaray", "mozaik",
      "anıt", "=han", "=hanı", "tapınağı", "tapınak", "su kenarı", "bügeti"]),

    ("Alışveriş", "Market, Fırın, Kasap",
     ["fıstık", "fırın", "unlu", "ekmek", "market", "migros", "carrefour",
      "=avm", "alışveriş merkezi", "gross", "=bim", "=şok", "=a101", "a-101", "a.101",
      "kasap", "manav", "kuruyemiş", "baharat", "gıda", "süpermarket", "toptan", "bakkal"]),
    ("Alışveriş", "Giyim, Teknoloji, Mağaza",
     ["giyim", "ayakkabı", "teknoloji", "elektronik", "telefon mağaza", "=gsm",
      "bilgisayar", "mağaza", "boyner", "lc waikiki", "defacto", "fulla", "outlet",
      "teknosa", "vatan bilgisayar", "kuyumc", "pırlanta", "döviz", "kozmetik", "kırtasiye", "kirtasiye",
      "kitap", "kitab", "oyuncak", "gelinlik", "çeyiz", "dükkan"]),
]

ANA = {"Kebap & Et": "Yemek", "Restoran": "Yemek", "Hızlı Atıştırmalık": "Yemek",
       "Tatlı & Pastane": "Yemek", "Kafe & Kahvaltı": "Yemek", "Gezilecek yerler": "Gezilecek yerler",
       "Alışveriş": "Alışveriş", "Diğer": "Diğer"}

BOLUMLER = list(ANA.keys())
YEMEK_BOLUMLER = BOLUMLER[:5]
ANA_SIRA = ["Yemek", "Gezilecek yerler", "Alışveriş", "Diğer"]

YERLER = {
    "nizip": dict(baslik="Nizip · Local Radar", dosya="nizip", ilce="Nizip", merkez=(37.0108, 37.7952),
                  yaricap=10, bolgeler=["Nizip Gaziantep"], kategoriler=YEMEK + GEZI + DIGER,
                  bolumler=BOLUMLER),
    "gaziantep": dict(baslik="Gaziantep · Local Radar", dosya="gaziantep", ilce="Gaziantep",
                      merkez=(37.0662, 37.3833), yaricap=15,
                      bolgeler=["Şahinbey Gaziantep", "Şehitkamil Gaziantep", "Gaziantep Kalesi çevresi"],
                      kategoriler=YEMEK + GEZI, bolumler=YEMEK_BOLUMLER + ["Gezilecek yerler"]),
}


def fold(s):
    s = s.replace("İ", "i").replace("I", "i").lower()
    return s.translate(str.maketrans("ıçğöşüâîû", "icgosuaiu"))


KURALLAR = [(b, g, [("=" + fold(k[1:]) if k.startswith("=") else fold(k)) for k in kw]) for b, g, kw in KURALLAR]

ALT_SIRA = {a: [] for a in ANA_SIRA}
for _b, _g, _ in KURALLAR:
    _alt = _b if ANA[_b] == "Yemek" else _g
    if _alt not in ALT_SIRA[ANA[_b]]:
        ALT_SIRA[ANA[_b]].append(_alt)

ALT_SIRA["Yemek"] = ["Kebap & Et", "Restoran", "Hızlı Atıştırmalık", "Tatlı & Pastane", "Kafe & Kahvaltı"]
ALT_SIRA["Gezilecek yerler"] = ["Gezi ve doğa", "Camiler", "Eğlence ve Sanat"]
ALT_SIRA["Alışveriş"] = ["Market, Fırın, Kasap", "Giyim, Teknoloji, Mağaza"]
ALT_SIRA["Diğer"] = ["Sağlık ve Bakım", "Ulaşım ve Araç", "Konaklama", "Banka ve ATM",
                     "Kargo ve Posta", "Düğün ve Organizasyon", "Çiçekçi", "Evcil Hayvan", "Diğer hizmetler"]

VARSAYILAN_ESIKLER = {
    "Kebap & Et": {"puan": 0.0, "oy": 0, "puansiz": True},
    "Restoran": {"puan": 0.0, "oy": 0, "puansiz": True},
    "Hızlı Atıştırmalık": {"puan": 0.0, "oy": 0, "puansiz": True},
    "Tatlı & Pastane": {"puan": 0.0, "oy": 0, "puansiz": True},
    "Kafe & Kahvaltı": {"puan": 0.0, "oy": 0, "puansiz": True},
    "Gezilecek yerler": {"puan": 0.0, "oy": 0, "puansiz": True},
    "Eğlence ve Sanat": {"puan": 0.0, "oy": 0, "puansiz": True},
    "Camiler": {"puan": 0.0, "oy": 0, "puansiz": True},
    "Konaklama": {"puan": 0.0, "oy": 0, "puansiz": True},
    "Market, Fırın, Kasap": {"puan": 0.0, "oy": 0, "puansiz": True},
    "Giyim, Teknoloji, Mağaza": {"puan": 0.0, "oy": 0, "puansiz": True},
    "Sağlık ve Bakım": {"puan": 0.0, "oy": 0, "puansiz": True},
    "Düğün ve Organizasyon": {"puan": 0.0, "oy": 0, "puansiz": True},
    "Çiçekçi": {"puan": 0.0, "oy": 0, "puansiz": True},
    "Ulaşım ve Araç": {"puan": 0.0, "oy": 0, "puansiz": True},
    "Banka ve ATM": {"puan": 0.0, "oy": 0, "puansiz": True},
    "Kargo ve Posta": {"puan": 0.0, "oy": 0, "puansiz": True},
    "Evcil Hayvan": {"puan": 0.0, "oy": 0, "puansiz": True},
    "Diğer hizmetler": {"puan": 0.0, "oy": 0, "puansiz": True},
}

KATEGORI_ESIKLERI = {k: dict(v) for k, v in VARSAYILAN_ESIKLER.items()}


def _esik_cozumle(veri, varsayilan_puan, varsayilan_oy, varsayilan_puansiz=False):
    if not isinstance(veri, dict):
        return float(varsayilan_puan), int(varsayilan_oy), bool(varsayilan_puansiz)
    try:
        puan = float(veri.get("puan", varsayilan_puan))
    except (TypeError, ValueError):
        puan = float(varsayilan_puan)
    try:
        oy = int(veri.get("oy", varsayilan_oy))
    except (TypeError, ValueError):
        oy = int(varsayilan_oy)
    puansiz = bool(veri.get("puansiz", varsayilan_puansiz))
    return puan, oy, puansiz


def esikleri_yukle(ayar=None):
    global KATEGORI_ESIKLERI
    taban = {k: dict(v) for k, v in VARSAYILAN_ESIKLER.items()}
    aday = (ayar or {}).get("kategori_esikleri") if isinstance(ayar, dict) else None
    if isinstance(aday, dict):
        for grup, deger in aday.items():
            vp, vo, vz = _esik_cozumle(taban.get(grup), MIN_PUAN, MIN_OY, False)
            p, o, z = _esik_cozumle(deger, vp, vo, vz)
            taban[str(grup)] = {"puan": p, "oy": o, "puansiz": z}
    KATEGORI_ESIKLERI = taban
    return KATEGORI_ESIKLERI


def esik_al(grup, varsayilan_puan, varsayilan_oy, esikler=None):
    tablo = esikler if isinstance(esikler, dict) else KATEGORI_ESIKLERI
    kayit = tablo.get(grup) if isinstance(tablo, dict) else None
    return _esik_cozumle(kayit, varsayilan_puan, varsayilan_oy, False)


def _esik_grubu(kayit):
    bolum = kayit.get("Bölüm", "")
    ana = ANA.get(bolum, "Diğer")
    return bolum if ana == "Yemek" else (kayit.get("Grup") or bolum)


def _grup_sira(kayit):
    bolum = kayit.get("Bölüm", "")
    ana = ANA.get(bolum, "Diğer")
    alt = bolum if ana == "Yemek" else (kayit.get("Grup") or bolum)
    try:
        i_ana = ANA_SIRA.index(ana)
    except ValueError:
        i_ana = len(ANA_SIRA)
    alt_liste = ALT_SIRA.get(ana, [])
    try:
        i_alt = alt_liste.index(alt)
    except ValueError:
        i_alt = len(alt_liste)
    return i_ana, i_alt, fold(kayit.get("Yer", ""))


def esik_uygula(kayitlar, varsayilan_puan, varsayilan_oy, esikler=None):
    tablo = esikler if isinstance(esikler, dict) else KATEGORI_ESIKLERI
    sonuc = []
    for r in kayitlar:
        grup = _esik_grubu(r)
        min_p, min_o, puansiz_izin = esik_al(grup, varsayilan_puan, varsayilan_oy, tablo)
        puansiz = bool(r.get("_puansiz"))
        if puansiz and not puansiz_izin:
            continue
        if not puansiz:
            try:
                puan = float(r.get("Puan", 0) or 0)
            except (TypeError, ValueError):
                puan = 0.0
            try:
                oy = int(r.get("Yorum Sayısı", 0) or 0)
            except (TypeError, ValueError):
                oy = 0
            if puan < min_p or oy < min_o:
                continue
        sonuc.append(r)

    def _sirala(r):
        puansiz = 1 if r.get("_puansiz") else 0
        try:
            puan = float(r.get("Puan", 0) or 0)
        except (TypeError, ValueError):
            puan = 0.0
        try:
            oy = int(r.get("Yorum Sayısı", 0) or 0)
        except (TypeError, ValueError):
            oy = 0
        return (_grup_sira(r), puansiz, -puan, -oy, -float(r.get("Güvenilir Skor", 0) or 0))

    return sorted(sonuc, key=_sirala)


def _cikti_satiri(r):
    satir = dict(r)
    if satir.get("_puansiz"):
        satir["Puan"] = "puansız"
        satir["Yorum Sayısı"] = "puansız"
        satir["Güvenilir Skor"] = ""
    return satir


def siniflandir(ad, tur, fiyat):
    if GURULTU.search(fold(tur or "")):
        tur = ""
    m = fold(ad + " " + tur)
    kelimeler = set(re.findall(r"[a-z0-9]+", m))
    for bolum, grup, kws in KURALLAR:
        for k in kws:
            if k.startswith("="):
                if k[1:] in kelimeler:
                    return bolum, grup
            else:
                if k in m:
                    return bolum, grup
    if fiyat:
        return "Restoran", "Restoran"
    return "Diğer", "Diğer hizmetler"


# ==================== RESILIENT JS SELECTORS ====================
JS_KARTLAR = """() => {
  const SECICILER = [
    'a.hfpxzc',
    'a[href*="/maps/place/"]',
    'div[role="feed"] a[aria-label]',
    'div[role="article"] a[href]',
  ];
  let linkler = [];
  let kullanilan = '';
  for (const s of SECICILER) {
    const n = document.querySelectorAll(s);
    if (n.length > 0) { linkler = n; kullanilan = s; break; }
  }
  if (!linkler.length) return [];
  if (!window.__gezi_log) {
    console.log('[gezi] Çalışan kart seçici:', kullanilan, '(', linkler.length, 'kart)');
    window.__gezi_log = true;
  }
  return Array.from(linkler).map(a => {
    const kart = a.closest('div[role="article"]')
              || a.closest('div[jsaction]')
              || a.parentElement;
    const y = kart ? (kart.querySelector('span[role="img"]')
                   || kart.querySelector('[aria-label*="yıldız"]')
                   || kart.querySelector('[aria-label*="stars"]')) : null;
    return {
      link: a.href,
      ad: a.getAttribute('aria-label') || a.textContent?.trim() || '',
      metin: kart ? kart.innerText : '',
      yildiz: y ? (y.getAttribute('aria-label') || '') : ''
    };
  }).filter(x => x.link && x.link.includes('/maps/place/'));
}"""

JS_SAYI = """() => {
  for (const s of ['a.hfpxzc', 'a[href*="/maps/place/"]', 'div[role="article"] a[href]']) {
    const n = document.querySelectorAll(s).length;
    if (n > 0) return n;
  }
  return 0;
}"""

JS_KAYDIR = """() => {
  const FEED = ['div[role="feed"]', 'div[aria-label*="Sonuçlar"]',
                'div[aria-label*="Results"]', 'div[jsaction*="scroll"]'];
  for (const s of FEED) {
    const f = document.querySelector(s);
    if (f && f.scrollHeight > f.clientHeight) { f.scrollBy(0, f.scrollHeight); return; }
  }
  const enBuyuk = [...document.querySelectorAll('div')]
    .filter(d => d.scrollHeight > d.clientHeight + 200)
    .sort((a, b) => b.scrollHeight - a.scrollHeight)[0];
  if (enBuyuk) enBuyuk.scrollBy(0, enBuyuk.scrollHeight);
}"""

JS_SON = """() => {
  const FEED = ['div[role="feed"]', 'div[aria-label*="Sonuçlar"]',
                'div[aria-label*="Results"]'];
  for (const s of FEED) {
    const f = document.querySelector(s);
    if (f) return f.innerText.slice(-400);
  }
  const enBuyuk = [...document.querySelectorAll('div')]
    .filter(d => d.scrollHeight > d.clientHeight + 200)
    .sort((a, b) => b.scrollHeight - a.scrollHeight)[0];
  return enBuyuk ? enBuyuk.innerText.slice(-400) : '';
}"""


def puan_oy(yildiz, metin):
    desenler = [
        (yildiz, r"(\d)[,.](\d)\s*(?:yıldız|stars?)\s*([\d.,]+)"),
        (metin, r"(\d)[,.](\d)\s*\(\s*([\d.,]+)\s*\)"),
        ((yildiz or "") + " " + (metin or ""), r"(\d)[,.](\d)\D{0,20}?([\d.,]+)\s*(?:yorum|reviews?)"),
    ]
    for kaynak, desen in desenler:
        m = re.search(desen, kaynak or "", re.I)
        if m:
            try:
                return float(f"{m.group(1)}.{m.group(2)}"), int(re.sub(r"\D", "", m.group(3)))
            except ValueError:
                pass
    return None, None


def koordinat(link):
    m = re.search(r"!3d(-?\d+\.\d+)!4d(-?\d+\.\d+)", link)
    return (float(m.group(1)), float(m.group(2))) if m else (None, None)


def mesafe_km(a, b):
    p1, p2 = math.radians(a[0]), math.radians(b[0])
    dp, dl = p2 - p1, math.radians(b[1] - a[1])
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * 6371 * math.asin(math.sqrt(h))


GURULTU = re.compile(
    r"^(acik|kapali|kapanis|kapanmak uzere|acilis|24 saat acik|yemek yerinde|paket|kapida|siparis|"
    r"rezervasyon|gel-al|teslimat|saat)|\(0\d|^(?:\+?90[\s-]?)?0?[2-58]\d{2}[\s-]?\d{3}|^444[\s-]?\d{4}|saati|^\d{1,2}:\d{2}$|^[0-9a-z]{4}\+[0-9a-z]{2,}")
ADRES = re.compile(r"\d|\b(sk|sok|cd|cad|blv|bulvar|mah|caddesi|sokak)\b")


def bilgi_ayikla(metin):
    parcalar = []
    for satir in (metin or "").replace("\ue88e", "").split("\n"):
        if "·" in satir:
            parcalar += [p.strip() for p in satir.split("·")]
    parcalar = [p for p in parcalar if p]
    fiyat = next((p for p in parcalar if "₺" in p), "")
    kalan = [p for p in parcalar if "₺" not in p and not re.match(r"^\d[,.]\d\s*\(", p)
             and not GURULTU.search(fold(p))]
    adres = next((p for p in kalan if ADRES.search(fold(p))), "")
    tur = next((p for p in kalan if p != adres), "")
    return tur, adres, fiyat


def detay_topla(sayfa, link):
    sayfa.goto(link, wait_until="domcontentloaded")
    sayfa.wait_for_selector("h1", timeout=10000)
    time.sleep(1.5)

    def metin(secici, nitelik="aria-label"):
        try:
            el = sayfa.query_selector(secici)
            return (el.get_attribute(nitelik) or "").strip() if el else ""
        except Exception:
            return ""
    return {
        "Telefon": metin('button[data-item-id^="phone"]'),
        "Web": metin('a[data-item-id="authority"]', "href"),
        "Adres2": metin('button[data-item-id="address"]'),
    }


MAH_RE = re.compile(
    r"(?:^|,\s*)([^,\d]+?)\s+(?:mahallesi|mahalle|mah\.|mah\b|mh\.|mh\b)"
    r"|^([A-ZÇĞİÖŞÜa-zçğıöşü\s]{3,25}?),\s*(?:[^,\d]+\s+(?:cd|cad|caddesi|sk|sok|sokak|blv|bulvar|bulvarı)\b)",
    re.I
)


def tr_title(s):
    s = s.replace("İ", "i").replace("I", "ı").lower()
    sonuc = []
    for w in s.split():
        if not w:
            continue
        bas = "İ" if w[0] == "i" else ("I" if w[0] == "ı" else w[0].upper())
        sonuc.append(w.upper() if w == "osb" else bas + w[1:])
    return " ".join(sonuc)


def mahalle_yaz(ad, tur="suburb"):
    if not ad:
        return "Bilinmiyor"
    sonek = r"\s*(mahallesi|mahalle|mah\.?|mh\.?)\s*$"
    soneki_var = bool(re.search(sonek, ad.strip(), flags=re.I))
    temiz = tr_title(re.sub(sonek, "", ad.strip(), flags=re.I).strip())
    temiz = MAHALLE_TAKMA_AD.get(temiz, temiz)
    if not temiz:
        return "Bilinmiyor"
    if tur in ("village", "hamlet", "city_district") and not soneki_var:
        return temiz
    return temiz + " Mahallesi"


def nominatim(lat, lon):
    url = "https://nominatim.openstreetmap.org/reverse?" + urllib.parse.urlencode(
        {"format": "jsonv2", "lat": lat, "lon": lon, "zoom": 16, "addressdetails": 1, "accept-language": "tr"})
    istek = urllib.request.Request(url, headers={"User-Agent": "local-radar/1.1"})
    for _ in range(2):
        try:
            with urllib.request.urlopen(istek, timeout=15) as r:
                adr = json.load(r).get("address", {})
            for anahtar in ("suburb", "neighbourhood", "quarter", "village", "hamlet", "city_district"):
                if adr.get(anahtar):
                    return [adr[anahtar], anahtar]
            return None
        except Exception:
            time.sleep(5)
    return None


def kapali_mi(metin):
    m = fold(metin or "")
    return any(x in m for x in ("kalici olarak kapali", "permanently closed"))


ALANLAR = ["Yer", "İlçe", "Mahalle", "Bölüm", "Grup", "Puan", "Yorum Sayısı", "Güvenilir Skor",
           "Tür", "Fiyat", "Adres", "Enlem", "Boylam", "Harita Linki"]
HAVUZ_ALANLAR = ALANLAR + ["İlk Görülme", "Son Görülme", "Telefon", "Web", "Adres2", "Detay Tarihi"]


def kayitlari_hazirla(kartlar, ayar, min_puan=MIN_PUAN, min_oy=MIN_OY, mahalle_aktif=MAHALLE_BUL, durdur=lambda: False):
    onbellek = {}
    if os.path.exists(ONBELLEK_DOSYASI):
        try:
            onbellek = json.load(open(ONBELLEK_DOSYASI, encoding="utf-8"))
        except Exception:
            onbellek = {}

    alanlar = ayar.get("alanlar") or [(ayar["merkez"][0], ayar["merkez"][1], ayar["yaricap"], None)]
    esikler = esikleri_yukle(ayar)

    adaylar, puansiz, kapali = [], 0, 0
    elenen = []
    for k in kartlar:
        ad0 = (k.get("ad") or "").strip()
        if kapali_mi(k.get("metin", "")):
            kapali += 1
            elenen.append((ad0, "", "", "kalıcı olarak kapalı"))
            continue

        puan_ham, oy_ham = puan_oy(k.get("yildiz", ""), k.get("metin", ""))
        puan_var = puan_ham is not None and oy_ham is not None
        puan = float(puan_ham or 0.0)
        oy = int(oy_ham or 0)

        lat, lon = koordinat(k.get("link", ""))
        if lat is not None and not any(mesafe_km((a[0], a[1]), (lat, lon)) <= a[2] for a in alanlar):
            elenen.append((ad0, puan if puan_var else "", oy if puan_var else "", "seçilen alanın dışında"))
            continue

        tur, adres, fiyat = bilgi_ayikla(k.get("metin", ""))
        bolum, grup = siniflandir(k.get("ad", ""), tur, fiyat)
        esik_grup = bolum if ANA.get(bolum, "Diğer") == "Yemek" else grup
        mp, mo, puansiz_izin = esik_al(esik_grup, min_puan, min_oy, esikler)

        if not puan_var:
            puansiz += 1
            if not puansiz_izin:
                elenen.append((ad0, "", "", "puan/yorum okunamadı"))
                continue
            puan, oy = 0.0, 0
        elif puan < mp or oy < mo:
            elenen.append((ad0, puan, oy, f"eşiğin altında (en az {mp} puan / {mo} yorum)"))
            continue

        if bolum not in ayar["bolumler"]:
            elenen.append((ad0, puan if puan_var else "", oy if puan_var else "", f"seçili kategorilerde değil ({bolum})"))
            continue

        adaylar.append((k, puan, oy, lat, lon, tur, adres, fiyat, bolum, grup, not puan_var))

    LOG(f"[Core version {SURUM}] {len(kartlar)} cards processed, {len(adaylar)} passed filters.")
    ozet_n = {}
    for _, _, _, neden in elenen:
        anahtar = neden.split(" (")[0]
        ozet_n[anahtar] = ozet_n.get(anahtar, 0) + 1
    if ozet_n:
        LOG("Exclusion reasons: " + " · ".join(f"{n}: {s}" for n, s in sorted(ozet_n.items(), key=lambda x: -x[1])))
    if kapali:
        LOG(f"{kapali} permanently closed places excluded")
    puansiz_listede = sum(1 for a in adaylar if a[-1])
    if puansiz:
        LOG(f"Rating/review unreadable: {puansiz} · added as no-rating: {puansiz_listede}")
    try:
        with open(DOSYA_ELENENLER, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(["Yer", "Puan", "Yorum", "Neden elendi"])
            w.writerows(elenen)
    except Exception:
        pass

    if mahalle_aktif and adaylar:
        sinirlari_hazirla(ayar.get("alanlar"))

    kayitlar = []
    for i, (k, puan, oy, lat, lon, tur, adres, fiyat, bolum, grup, puansiz_mi) in enumerate(adaylar, 1):
        if durdur():
            LOG("   ⏹ Kullanıcı tarafından durduruldu (kalan yerler mahallesiz eklenecek).")
            mahalle_aktif = False
        if mahalle_aktif and i % 10 == 0:
            LOG(f"   Neighborhood lookup: {i}/{len(adaylar)}")
        if puansiz_mi:
            skor = 0.0
        else:
            w_ = max(min_oy, 10)
            skor = (oy / (oy + w_)) * puan + (w_ / (oy + w_)) * 4.0
        kayitlar.append({
            "Yer": k.get("ad", "").strip(), "İlçe": ayar.get("ilce", ""),
            "Mahalle": mahalle_bul(adres, lat, lon, onbellek, mahalle_aktif),
            "Bölüm": bolum, "Grup": grup, "Puan": puan, "Yorum Sayısı": oy,
            "Güvenilir Skor": round(skor, 3), "_puansiz": puansiz_mi,
            "Tür": tur, "Fiyat": fiyat, "Adres": adres,
            "Enlem": lat, "Boylam": lon,
            "Harita Linki": (k.get("link", "") or "").split("?")[0],
        })

    if mahalle_aktif and adaylar:
        m_ = MAHALLE_ISTATISTIK
        LOG(f"Neighborhood source: boundaries {m_['sinir']} · address text {m_['adres']} · "
            f"internet {m_['internet']} · not found {m_['yok']}")
    elif adaylar:
        LOG("   ⏹ Mahalle araması kullanıcı tarafından durduruldu.")

    benzersiz = {}
    for r in kayitlar:
        if r["Enlem"] is not None:
            anahtar = (fold(r["Yer"]), round(r["Enlem"], 3), round(r["Boylam"], 3))
        else:
            anahtar = (fold(r["Yer"]), r["Mahalle"])
        mevcut = benzersiz.get(anahtar)
        if not mevcut:
            benzersiz[anahtar] = r
            continue
        if float(r.get("Güvenilir Skor", 0) or 0) > float(mevcut.get("Güvenilir Skor", 0) or 0):
            benzersiz[anahtar] = r

    kayitlar = esik_uygula(list(benzersiz.values()), min_puan, min_oy, esikler=esikler)
    return kayitlar, puansiz


def csv_yaz(kayitlar, yol, alanlar=None):
    alanlar = alanlar or ALANLAR
    with open(yol, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=alanlar, extrasaction="ignore", restval="")
        w.writeheader()
        w.writerows([_cikti_satiri(r) for r in kayitlar])


def json_yaz(kayitlar, yol, alanlar=None):
    alanlar = alanlar or HAVUZ_ALANLAR
    satirlar = []
    for r in kayitlar:
        duz = dict(r)
        puansiz = bool(duz.get("_puansiz"))
        satir = {a: duz.get(a, "") for a in alanlar}
        if puansiz:
            satir["Puan"] = None
            satir["Yorum Sayısı"] = None
            satir["Güvenilir Skor"] = None
            satir["_puansiz"] = True
        satirlar.append(satir)
    with open(yol, "w", encoding="utf-8") as f:
        json.dump(satirlar, f, ensure_ascii=False, indent=2)
    return yol


def kml_yaz(kayitlar, yol):
    def esc(v):
        return html.escape(str(v or ""), quote=True)

    placemarks = []
    for r in kayitlar:
        try:
            lat = float(r.get("Enlem"))
            lon = float(r.get("Boylam"))
        except (TypeError, ValueError):
            continue

        aciklama = " · ".join([
            str(r.get("Bölüm", "") or ""),
            ("puansız" if r.get("_puansiz") else f"Puan: {r.get('Puan', '')}"),
            ("" if r.get("_puansiz") else f"Yorum: {r.get('Yorum Sayısı', '')}"),
            str(r.get("Grup", "") or ""),
        ]).strip(" ·")
        if r.get("Adres"):
            aciklama += ("\nAdres: " + str(r.get("Adres")))

        placemarks.append(
            "<Placemark>"
            f"<name>{esc(r.get('Yer', ''))}</name>"
            f"<description>{esc(aciklama)}</description>"
            "<Point>"
            f"<coordinates>{lon:.7f},{lat:.7f},0</coordinates>"
            "</Point>"
            "</Placemark>"
        )

    kml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<kml xmlns="http://www.opengis.net/kml/2.2">\n'
        '<Document>\n'
        '<name>Local Radar</name>\n'
        + "\n".join(placemarks)
        + '\n</Document>\n</kml>\n'
    )
    with open(yol, "w", encoding="utf-8") as f:
        f.write(kml)
    return yol


def xlsx_yaz(kayitlar, yol, alanlar=None):
    alanlar = alanlar or ALANLAR
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill, Alignment
        from openpyxl.utils import get_column_letter
    except ImportError:
        LOG("openpyxl is required for Excel output. Install: pip install openpyxl")
        return None

    wb = Workbook()
    ws = wb.active
    ws.title = "Places"
    ws.append(alanlar)

    baslik_dolgu = PatternFill("solid", fgColor="1A73E8")
    for hucre in ws[1]:
        hucre.font = Font(bold=True, color="FFFFFF")
        hucre.fill = baslik_dolgu
        hucre.alignment = Alignment(vertical="center")

    yesil = (PatternFill("solid", fgColor="C6EFCE"), Font(color="006100", bold=True))
    sari = (PatternFill("solid", fgColor="FFEB9C"), Font(color="9C0006", bold=True))
    kirmizi = (PatternFill("solid", fgColor="FFC7CE"), Font(color="9C0006", bold=True))

    puan_sutun = alanlar.index("Puan") + 1
    link_sutun = alanlar.index("Harita Linki") + 1
    for r in kayitlar:
        rr = _cikti_satiri(r)
        ws.append([rr.get(a, "") for a in alanlar])
        satir = ws.max_row
        p = ws.cell(row=satir, column=puan_sutun)
        try:
            deger = float(p.value)
            dolgu, yazi = yesil if deger >= 4.5 else (sari if deger >= 4.0 else kirmizi)
            p.fill, p.font = dolgu, yazi
        except (TypeError, ValueError):
            pass
        link = ws.cell(row=satir, column=link_sutun)
        if link.value:
            link.hyperlink = link.value
            link.font = Font(color="1A73E8", underline="single")

    genislik = {"Yer": 34, "İlçe": 12, "Mahalle": 20, "Bölüm": 16, "Grup": 18, "Puan": 8,
                "Yorum Sayısı": 12, "Güvenilir Skor": 13, "Tür": 18, "Fiyat": 10, "Adres": 42,
                "Enlem": 11, "Boylam": 11, "Harita Linki": 40, "İlk Görülme": 12, "Son Görülme": 12}
    for i, a in enumerate(alanlar, 1):
        ws.column_dimensions[get_column_letter(i)].width = genislik.get(a, 14)
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:{get_column_letter(len(alanlar))}{ws.max_row}"
    wb.save(yol)
    return yol


def _yeni_mi(tarih):
    try:
        return (time.time() - time.mktime(time.strptime(tarih, "%d.%m.%Y"))) <= YENI_GUN * 86400
    except Exception:
        return False


LEAFLET_CSS = r""".leaflet-pane,.leaflet-tile,.leaflet-marker-icon,.leaflet-marker-shadow,.leaflet-tile-container,.leaflet-pane>svg,.leaflet-pane>canvas,.leaflet-zoom-box,.leaflet-image-layer,.leaflet-layer{position:absolute;left:0;top:0;}.leaflet-container{overflow:hidden;}.leaflet-tile,.leaflet-marker-icon,.leaflet-marker-shadow{-webkit-user-select:none;-moz-user-select:none;user-select:none;-webkit-user-drag:none;}.leaflet-tile::selection{background:transparent;}.leaflet-safari .leaflet-tile{image-rendering:-webkit-optimize-contrast;}.leaflet-safari .leaflet-tile-container{width:1600px;height:1600px;-webkit-transform-origin:0 0;}.leaflet-marker-icon,.leaflet-marker-shadow{display:block;}.leaflet-container .leaflet-overlay-pane svg{max-width:none !important;max-height:none !important;}.leaflet-container .leaflet-marker-pane img,.leaflet-container .leaflet-shadow-pane img,.leaflet-container .leaflet-tile-pane img,.leaflet-container img.leaflet-image-layer,.leaflet-container .leaflet-tile{max-width:none !important;max-height:none !important;width:auto;padding:0;}.leaflet-container img.leaflet-tile{mix-blend-mode:plus-lighter;}.leaflet-container.leaflet-touch-zoom{-ms-touch-action:pan-x pan-y;touch-action:pan-x pan-y;}.leaflet-container.leaflet-touch-drag{-ms-touch-action:pinch-zoom;touch-action:none;touch-action:pinch-zoom;}.leaflet-container.leaflet-touch-drag.leaflet-touch-zoom{-ms-touch-action:none;touch-action:none;}.leaflet-container{-webkit-tap-highlight-color:transparent;}.leaflet-container a{-webkit-tap-highlight-color:rgba(51,181,229,0.4);}.leaflet-tile{filter:inherit;visibility:hidden;}.leaflet-tile-loaded{visibility:inherit;}.leaflet-zoom-box{width:0;height:0;-moz-box-sizing:border-box;box-sizing:border-box;z-index:800;}.leaflet-overlay-pane svg{-moz-user-select:none;}.leaflet-pane{z-index:400;}.leaflet-tile-pane{z-index:200;}.leaflet-overlay-pane{z-index:400;}.leaflet-shadow-pane{z-index:500;}.leaflet-marker-pane{z-index:600;}.leaflet-tooltip-pane{z-index:650;}.leaflet-popup-pane{z-index:700;}.leaflet-map-pane canvas{z-index:100;}.leaflet-map-pane svg{z-index:200;}.leaflet-vml-shape{width:1px;height:1px;}.lvml{behavior:url(#default#VML);display:inline-block;position:absolute;}.leaflet-control{position:relative;z-index:800;pointer-events:visiblePainted;pointer-events:auto;}.leaflet-top,.leaflet-bottom{position:absolute;z-index:1000;pointer-events:none;}.leaflet-top{top:0;}.leaflet-right{right:0;}.leaflet-bottom{bottom:0;}.leaflet-left{left:0;}.leaflet-control{float:left;clear:both;}.leaflet-right .leaflet-control{float:right;}.leaflet-top .leaflet-control{margin-top:10px;}.leaflet-bottom .leaflet-control{margin-bottom:10px;}.leaflet-left .leaflet-control{margin-left:10px;}.leaflet-right .leaflet-control{margin-right:10px;}.leaflet-fade-anim .leaflet-popup{opacity:0;-webkit-transition:opacity 0.2s linear;-moz-transition:opacity 0.2s linear;transition:opacity 0.2s linear;}.leaflet-fade-anim .leaflet-map-pane .leaflet-popup{opacity:1;}.leaflet-zoom-animated{-webkit-transform-origin:0 0;-ms-transform-origin:0 0;transform-origin:0 0;}svg.leaflet-zoom-animated{will-change:transform;}.leaflet-zoom-anim .leaflet-zoom-animated{-webkit-transition:-webkit-transform 0.25s cubic-bezier(0,0,0.25,1);-moz-transition:-moz-transform 0.25s cubic-bezier(0,0,0.25,1);transition:transform 0.25s cubic-bezier(0,0,0.25,1);}.leaflet-zoom-anim .leaflet-tile,.leaflet-pan-anim .leaflet-tile{-webkit-transition:none;-moz-transition:none;transition:none;}.leaflet-zoom-anim .leaflet-zoom-hide{visibility:hidden;}.leaflet-interactive{cursor:pointer;}.leaflet-grab{cursor:-webkit-grab;cursor:-moz-grab;cursor:grab;}.leaflet-crosshair,.leaflet-crosshair .leaflet-interactive{cursor:crosshair;}.leaflet-popup-pane,.leaflet-control{cursor:auto;}.leaflet-dragging .leaflet-grab,.leaflet-dragging .leaflet-grab .leaflet-interactive,.leaflet-dragging .leaflet-marker-draggable{cursor:move;cursor:-webkit-grabbing;cursor:-moz-grabbing;cursor:grabbing;}.leaflet-marker-icon,.leaflet-marker-shadow,.leaflet-image-layer,.leaflet-pane>svg path,.leaflet-tile-container{pointer-events:none;}.leaflet-marker-icon.leaflet-interactive,.leaflet-image-layer.leaflet-interactive,.leaflet-pane>svg path.leaflet-interactive,svg.leaflet-image-layer.leaflet-interactive path{pointer-events:visiblePainted;pointer-events:auto;}.leaflet-container{background:#ddd;outline-offset:1px;}.leaflet-container a{color:#0078A8;}.leaflet-zoom-box{border:2px dotted #38f;background:rgba(255,255,255,0.5);}.leaflet-container{font-family:"Helvetica Neue",Arial,Helvetica,sans-serif;font-size:12px;font-size:0.75rem;line-height:1.5;}.leaflet-bar{box-shadow:0 1px 5px rgba(0,0,0,0.65);border-radius:4px;}.leaflet-bar a{background-color:#fff;border-bottom:1px solid #ccc;width:26px;height:26px;line-height:26px;display:block;text-align:center;text-decoration:none;color:black;}.leaflet-bar a,.leaflet-control-layers-toggle{background-position:50% 50%;background-repeat:no-repeat;display:block;}.leaflet-bar a:hover,.leaflet-bar a:focus{background-color:#f4f4f4;}.leaflet-bar a:first-child{border-top-left-radius:4px;border-top-right-radius:4px;}.leaflet-bar a:last-child{border-bottom-left-radius:4px;border-bottom-right-radius:4px;border-bottom:none;}.leaflet-bar a.leaflet-disabled{cursor:default;background-color:#f4f4f4;color:#bbb;}.leaflet-touch .leaflet-bar a{width:30px;height:30px;line-height:30px;}.leaflet-touch .leaflet-bar a:first-child{border-top-left-radius:2px;border-top-right-radius:2px;}.leaflet-touch .leaflet-bar a:last-child{border-bottom-left-radius:2px;border-bottom-right-radius:2px;}.leaflet-control-zoom-in,.leaflet-control-zoom-out{font:bold 18px 'Lucida Console',Monaco,monospace;text-indent:1px;}.leaflet-touch .leaflet-control-zoom-in,.leaflet-touch .leaflet-control-zoom-out{font-size:22px;}.leaflet-control-layers{box-shadow:0 1px 5px rgba(0,0,0,0.4);background:#fff;border-radius:5px;}.leaflet-control-layers-toggle{background-image:none;width:36px;height:36px;}.leaflet-retina .leaflet-control-layers-toggle{background-image:none;background-size:26px 26px;}.leaflet-touch .leaflet-control-layers-toggle{width:44px;height:44px;}.leaflet-control-layers .leaflet-control-layers-list,.leaflet-control-layers-expanded .leaflet-control-layers-toggle{display:none;}.leaflet-control-layers-expanded .leaflet-control-layers-list{display:block;position:relative;}.leaflet-control-layers-expanded{padding:6px 10px 6px 6px;color:#333;background:#fff;}.leaflet-control-layers-scrollbar{overflow-y:scroll;overflow-x:hidden;padding-right:5px;}.leaflet-control-layers-selector{margin-top:2px;position:relative;top:1px;}.leaflet-control-layers label{display:block;font-size:13px;font-size:1.08333em;}.leaflet-control-layers-separator{height:0;border-top:1px solid #ddd;margin:5px -10px 5px -6px;}.leaflet-default-icon-path{background-image:none;}.leaflet-container .leaflet-control-attribution{background:#fff;background:rgba(255,255,255,0.8);margin:0;}.leaflet-control-attribution,.leaflet-control-scale-line{padding:0 5px;color:#333;line-height:1.4;}.leaflet-control-attribution a{text-decoration:none;}.leaflet-control-attribution a:hover,.leaflet-control-attribution a:focus{text-decoration:underline;}.leaflet-attribution-flag{display:inline !important;vertical-align:baseline !important;width:1em;height:0.6669em;}.leaflet-left .leaflet-control-scale{margin-left:5px;}.leaflet-bottom .leaflet-control-scale{margin-bottom:5px;}.leaflet-control-scale-line{border:2px solid #777;border-top:none;line-height:1.1;padding:2px 5px 1px;white-space:nowrap;-moz-box-sizing:border-box;box-sizing:border-box;background:rgba(255,255,255,0.8);text-shadow:1px 1px #fff;}.leaflet-control-scale-line:not(:first-child){border-top:2px solid #777;border-bottom:none;margin-top:-2px;}.leaflet-control-scale-line:not(:first-child):not(:last-child){border-bottom:2px solid #777;}.leaflet-touch .leaflet-control-attribution,.leaflet-touch .leaflet-control-layers,.leaflet-touch .leaflet-bar{box-shadow:none;}.leaflet-touch .leaflet-control-layers,.leaflet-touch .leaflet-bar{border:2px solid rgba(0,0,0,0.2);background-clip:padding-box;}.leaflet-popup{position:absolute;text-align:center;margin-bottom:20px;}.leaflet-popup-content-wrapper{padding:1px;text-align:left;border-radius:12px;}.leaflet-popup-content{margin:13px 24px 13px 20px;line-height:1.3;font-size:13px;font-size:1.08333em;min-height:1px;}.leaflet-popup-content p{margin:17px 0;margin:1.3em 0;}.leaflet-popup-tip-container{width:40px;height:20px;position:absolute;left:50%;margin-top:-1px;margin-left:-20px;overflow:hidden;pointer-events:none;}.leaflet-popup-tip{width:17px;height:17px;padding:1px;margin:-10px auto 0;pointer-events:auto;-webkit-transform:rotate(45deg);-moz-transform:rotate(45deg);-ms-transform:rotate(45deg);transform:rotate(45deg);}.leaflet-popup-content-wrapper,.leaflet-popup-tip{background:white;color:#333;box-shadow:0 3px 14px rgba(0,0,0,0.4);}.leaflet-container a.leaflet-popup-close-button{position:absolute;top:0;right:0;border:none;text-align:center;width:24px;height:24px;font:16px/24px Tahoma,Verdana,sans-serif;color:#757575;text-decoration:none;background:transparent;}.leaflet-container a.leaflet-popup-close-button:hover,.leaflet-container a.leaflet-popup-close-button:focus{color:#585858;}.leaflet-popup-scrolled{overflow:auto;}.leaflet-oldie .leaflet-popup-content-wrapper{-ms-zoom:1;}.leaflet-oldie .leaflet-popup-tip{width:24px;margin:0 auto;-ms-filter:"progid:DXImageTransform.Microsoft.Matrix(M11=0.70710678,M12=0.70710678,M21=-0.70710678,M22=0.70710678)";filter:progid:DXImageTransform.Microsoft.Matrix(M11=0.70710678,M12=0.70710678,M21=-0.70710678,M22=0.70710678);}.leaflet-oldie .leaflet-control-zoom,.leaflet-oldie .leaflet-control-layers,.leaflet-oldie .leaflet-popup-content-wrapper,.leaflet-oldie .leaflet-popup-tip{border:1px solid #999;}.leaflet-div-icon{background:#fff;border:1px solid #666;}.leaflet-tooltip{position:absolute;padding:6px;background-color:#fff;border:1px solid #fff;border-radius:3px;color:#222;white-space:nowrap;-webkit-user-select:none;-moz-user-select:none;-ms-user-select:none;user-select:none;pointer-events:none;box-shadow:0 1px 3px rgba(0,0,0,0.4);}.leaflet-tooltip.leaflet-interactive{cursor:pointer;pointer-events:auto;}.leaflet-tooltip-top:before,.leaflet-tooltip-bottom:before,.leaflet-tooltip-left:before,.leaflet-tooltip-right:before{position:absolute;pointer-events:none;border:6px solid transparent;background:transparent;content:"";}.leaflet-tooltip-bottom{margin-top:6px;}.leaflet-tooltip-top{margin-top:-6px;}.leaflet-tooltip-bottom:before,.leaflet-tooltip-top:before{left:50%;margin-left:-6px;}.leaflet-tooltip-top:before{bottom:0;margin-bottom:-12px;border-top-color:#fff;}.leaflet-tooltip-bottom:before{top:0;margin-top:-12px;margin-left:-6px;border-bottom-color:#fff;}.leaflet-tooltip-left{margin-left:-6px;}.leaflet-tooltip-right{margin-left:6px;}.leaflet-tooltip-left:before,.leaflet-tooltip-right:before{top:50%;margin-top:-6px;}.leaflet-tooltip-left:before{right:0;margin-right:-12px;border-left-color:#fff;}.leaflet-tooltip-right:before{left:0;margin-left:-12px;border-right-color:#fff;}@media print{.leaflet-control{-webkit-print-color-adjust:exact;print-color-adjust:exact;}}"""


# ---------- Yemek alt kategorileri ----------
YEMEK_ALT_SIRA = ["Döner & Kebap", "Çiğ Köfte", "Pide & Lahmacun", "Fast food & Burger & Pizza",
                  "Türk & Aile Restoranı", "Balık & Deniz Ürünleri", "Kafe & Kahve", "Kahvaltı", "Fırın & Tatlı", "Kasap"]

_YEMEK_ALT_KURAL = [
    ("Kasap", ["kasap", "sarkuteri", "kasab"]),
    ("Çiğ Köfte", ["cig kofte", "cigkofte"]),
    ("Pide & Lahmacun", ["pide", "lahmacun"]),
    ("Döner & Kebap", ["doner", "kebap", "kebab", "durum", "et lokanta", "et restoran", "et yemek",
                       "ciger", "kofte", "mangal", "et ve tavuk"]),
    ("Kahvaltı", ["kahvalti", "serpme", "brunch"]),
    ("Fast food & Burger & Pizza", ["fast food", "fastfood", "pizza", "burger", "hoagie", "tost", "sandvic", "cajun"]),
    ("Fırın & Tatlı", ["firin", "pastane", "tatli", "baklava", "kunefe", "dondurma", "pasta", "kadayif",
                       "simit", "borek", "gozleme", "katmer", "sikma", "waffle", "puding", "tatlici"]),
    ("Kafe & Kahve", ["kafe", "cafe", "kahve", "kiraathane", "coffee", "starbucks"]),
]


BALIK_ALT = "Balık & Deniz Ürünleri"
_BALIK_TUR = ("balik restoran", "deniz mahsul", "deniz urun", "kabuklu deniz")
_BALIK_AD = re.compile(r"\bbalikci|alabalik|\bbalik\s+(?:lokanta|restoran|restaurant|evi|ekmek|sofra|tava|izgara|"
                       r"pisirici|meyhane|dunya|cesme|pazari|mutfak)|\bbalik\s*&|deniz\s*urun|deniz\s*mahsul")
_BALIK_TUR_ISARET = ("restor", "lokanta", "balik", "deniz", "meyhane", "kebap", "izgara", "yemek")


def balik_mi(ad, tur):
    t = fold(tur or "")
    if any(k in t for k in _BALIK_TUR):
        return True
    return bool(_BALIK_AD.search(fold(ad or ""))) and (not t or any(k in t for k in _BALIK_TUR_ISARET))


def yemek_alt(r):
    bolum = r.get("Bölüm", "")
    if not (ANA.get(bolum) == "Yemek" or bolum == "Alışveriş"):
        return None
    if ANA.get(bolum) == "Yemek" and balik_mi(r.get("Yer", ""), r.get("Tür", "")):
        return BALIK_ALT
    m = fold(f"{r.get('Yer', '')} {r.get('Tür', '') or ''}")
    for alt, kws in _YEMEK_ALT_KURAL:
        if any(k in m for k in kws):
            return alt
    return "Türk & Aile Restoranı" if ANA.get(bolum) == "Yemek" else None


# ============================================================
# TEK VE MODERN HTML ÇIKTISI (Karkamış Teması)
# ============================================================
SABLON = r"""<!DOCTYPE html>
<html lang="tr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="color-scheme" content="light dark">
<title>__BASLIK__</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<style>__LEAFLET_CSS__</style>
<style>
:root {
  --bg: #f3f4f6; --card: #ffffff; --text: #111827; --muted: #6b7280;
  --line: #e5e7eb; --accent: #2563eb; --accent-soft: rgba(37,99,235,.08); --gold: #d97706;
  color-scheme: light dark;
}
@media (prefers-color-scheme:dark){
  :root {
    --bg: #0f172a; --card: #1e293b; --text: #f8fafc; --muted: #94a3b8;
    --line: #334155; --accent: #3b82f6; --accent-soft: rgba(59,130,246,.15); --gold: #fbbf24;
  }
}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--text);font-family:'Plus Jakarta Sans',system-ui,-apple-system,sans-serif;line-height:1.45;padding:12px 12px 56px;-webkit-font-smoothing:antialiased}
.wrap{max-width:580px;margin:0 auto}
a.back{display:inline-block;color:var(--muted);text-decoration:none;font-size:13px;font-weight:600;padding:4px 2px 10px}
.head{padding:0 2px 12px}
h1{font-size:22px;font-weight:800;letter-spacing:-.03em;color:var(--text)}
.sub-meta{color:var(--muted);font-size:13px;margin-top:4px;font-weight:500}
.filters{display:flex;flex-direction:column;gap:8px;margin-bottom:12px}
.frow{display:flex;gap:8px}
.frow>*{flex:1;min-width:0}
input,select{width:100%;font:inherit;font-size:14px;padding:11px 14px;border:1px solid var(--line);border-radius:12px;background:var(--card);color:var(--text);outline:none;transition:all 0.2s}
input:focus,select:focus{border-color:var(--accent);box-shadow:0 0 0 3px var(--accent-soft)}
input:focus,select:focus{border-color:var(--accent);box-shadow:0 0 0 3px var(--accent-soft)}
.frow input,.frow select{font-size:13px;padding:10px}
input:focus,select:focus{border-color:var(--accent)}
input::placeholder{color:var(--muted)}
.reset{align-self:flex-end;background:none;border:0;color:var(--muted);font:inherit;font-size:12.5px;font-weight:600;padding:2px 4px;cursor:pointer}
.tabs,.chips{display:flex;flex-wrap:wrap;gap:6px;margin:0 0 10px}
.tabs button,.chips button{flex:0 0 auto;font:inherit;font-size:13px;font-weight:600;color:var(--muted);background:transparent;border:1px solid var(--line);border-radius:99px;padding:6px 13px;cursor:pointer}
.tabs button:hover,.chips button:hover{border-color:var(--muted);color:var(--text)}
.tabs button[aria-selected="true"],.chips button[aria-pressed="true"]{background:var(--accent-soft);border-color:var(--accent);color:var(--accent);font-weight:700}
h2{font-size:12px;font-weight:700;color:var(--muted);text-transform:uppercase;letter-spacing:.06em;margin:18px 4px 8px}
#list>div{background:var(--card);border:1px solid var(--line);border-radius:18px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.04);margin-bottom:16px}
@media (prefers-color-scheme:dark){#list>div{box-shadow:0 4px 20px rgba(0,0,0,0.2)}}
.row{position:relative;display:flex;align-items:center;gap:16px;padding:16px 18px;border-bottom:1px solid var(--line);transition:background 0.15s}
.row:last-child{border-bottom:0}
@media (prefers-color-scheme:dark){.row:hover{background:rgba(255,255,255,0.02)}}
.row:last-child{border-bottom:0}
.row:hover{background:rgba(0,0,0,0.015)}
@media (prefers-color-scheme:dark){.row:hover{background:rgba(255,255,255,0.03)}}
.row:active{background:var(--accent-soft)}
.pt{flex:0 0 44px;text-align:center}
.pt b{display:block;font-size:16px;font-weight:800;color:var(--gold);letter-spacing:-0.02em}
.pt small{display:block;font-size:11.5px;color:var(--muted);margin-top:3px}
.body{flex:1;min-width:0}
.nm{font-weight:700;font-size:15px;overflow-wrap:anywhere}
a.nm-link{color:inherit;text-decoration:none}
a.nm-link::after{content:'';position:absolute;inset:0}
.meta-tags{font-size:12.5px;color:var(--muted);margin-top:4px;line-height:1.4}
.meta-adres{font-size:12.5px;color:var(--muted);margin-top:3px;overflow-wrap:anywhere;line-height:1.4}
.map-btn{display:inline-flex;align-items:center;justify-content:center;padding:8px 14px;border-radius:10px;background:var(--accent-soft);color:var(--accent);font-size:13px;font-weight:700;text-decoration:none;position:relative;z-index:2;white-space:nowrap;margin-left:10px;flex-shrink:0;transition:background 0.2s}
.map-btn:hover{background:var(--accent);color:#fff}
.foot{color:var(--muted);font-size:11.5px;margin-top:32px;text-align:center}
.none{color:var(--muted);text-align:center;padding:40px 0}
#map{display:none;height:60vh;border-radius:16px;border:1px solid var(--line)}
</style>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
</head><body><div class="wrap">

<a class="back" href="https://cisey.github.io/LocalRadar/">← Rehberler</a>

<div class="head">
  <h1>📡 __BASLIK__</h1>
  <div class="sub-meta">Veri tarihi: __TARIH__ · <span id="yerSayisi">0</span> mekan</div>
</div>

<div class="filters">
  <input id="q" type="search" placeholder="🔍 Mekan, yemek veya mahalle ara">
  <input id="mq" type="hidden">
  <div class="frow">
    <select id="mh" aria-label="Mahalle"></select>
    <select id="sirala" aria-label="Sıralama">
      <option value="skor">Güvenilir Skor</option>
      <option value="puan">Puan (Yüksek)</option>
      <option value="yorum">Yorum (Çok)</option>
      <option value="yakin">Bana Yakın</option>
    </select>
  </div>
  <div class="frow">
    <input id="mp" type="number" step="0.1" inputmode="decimal" placeholder="En az puan">
    <input id="my" type="number" step="10" inputmode="numeric" placeholder="En az yorum">
    <select id="gs" aria-label="Görünüm" style="display:none;">
      <option value="">Tümü</option>
    </select>
  </div>
  <select id="ic" aria-label="İlçe" style="display:none;"></select>
  <button class="reset" onclick="tumVerileriTemizle()">↺ Sıfırla</button>
</div>

<div class="tabs" id="tabs" role="tablist"></div>
<div class="chips" id="chips"></div>

<div id="map"></div>
<div id="list"></div>

<p class="foot">📡 Local Radar · Google Maps verileri · Harita: © OpenStreetMap · İlçe sınırları: geoBoundaries (CC BY 4.0)</p>
</div>

<script>
const V=__DATA__,O=V.O,I=V.I,ANA=Object.keys(O);
let ana='',alt='',map=null,katman=null;
const HARITA='__MAP__';
const RENK={'Yemek':'#fb923c','Gezilecek yerler':'#38bdf8','Alışveriş':'#34d399','Diğer':'#94a3b8'};
const $=id=>document.getElementById(id);
const tabs=$('tabs'),chips=$('chips'),list=$('list'),q=$('q'),mh=$('mh'),mq=$('mq'),ic=$('ic'),mp=$('mp'),my=$('my'),sirala=$('sirala'),gs=$('gs'),mapEl=$('map'),yerSayisi=$('yerSayisi');
const esc=s=>String(s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const tl=s=>String(s).toLocaleLowerCase('tr');

function durumOku(){try{return JSON.parse(localStorage.getItem('gezi_durum')||'{}')}catch(e){return {}}}
function durumYaz(){try{localStorage.setItem('gezi_durum',JSON.stringify(durum))}catch(e){}}
let durum=durumOku();
let konum=null;

function km(a,b,c,d){const t=x=>x*Math.PI/180,R=6371,dl=t(c-a),dg=t(d-b);
  const h=Math.sin(dl/2)**2+Math.cos(t(a))*Math.cos(t(c))*Math.sin(dg/2)**2;return 2*R*Math.asin(Math.sqrt(h));}
function uzak(x){return(konum&&x.e!=null)?km(konum.lat,konum.lon,x.e,x.b):null}

function konumAl(sonra){
  if(!navigator.geolocation)return;
  navigator.geolocation.getCurrentPosition(
    p=>{konum={lat:p.coords.latitude,lon:p.coords.longitude};if(sonra)sonra();},
    null,{enableHighAccuracy:true,timeout:10000});
}

const ilceler=[...new Set(I.map(x=>x.c).filter(Boolean))].sort((a,b)=>a.localeCompare(b,'tr'));
if(ilceler.length>=2) {
  ic.style.display='';
  ic.innerHTML='<option value="">Tüm ilçeler</option>'+ilceler.map(c=>`<option value="${esc(c)}">${esc(c)}</option>`).join('');
}

const mahSayisi=new Set(I.filter(x=>x.m!=='Bilinmiyor').map(x=>x.c+'|'+x.m)).size;
function mahalleListe(){
  if(mahSayisi<2){mh.style.display='none';return;}
  const c=ic.value,t=tl(mq.value.trim()),say={};
  I.forEach(x=>{if((c&&x.c!==c)||x.m==='Bilinmiyor')return;const k=x.c+'|'+x.m;say[k]=(say[k]||0)+1});
  const ks=Object.keys(say).filter(k=>tl(k.split('|')[1]).includes(t)).sort((a,b)=>a.split('|')[1].localeCompare(b.split('|')[1],'tr'));
  const onceki=mh.value;
  mh.innerHTML='<option value="">Tüm mahalleler</option>'+ks.map(k=>{const p=k.split('|');
    return `<option value="${esc(k)}">${esc(p[1])}${(!c&&p[0])?' · '+esc(p[0]):''} (${say[k]})</option>`}).join('');
  if(ks.includes(onceki))mh.value=onceki;
}

function ok(x){
  const t=tl(q.value.trim()),p0=parseFloat(mp.value)||0,y0=parseInt(my.value,10)||0;
  return (!ic.value||x.c===ic.value)&&(!mh.value||(x.c+'|'+x.m)===mh.value)&&
    (!t||tl(x.n+' '+x.t+' '+x.m).includes(t))&&(p0===0&&y0===0&&x.u ? true : (parseFloat(x.p.replace(',','.'))>=p0&&(x.y||0)>=y0))&&
    (gs.value===''||(gs.value==='fav'&&(durum[x.l]||{}).fav));
}

function kiyas(a,b){
  const s=sirala.value;
  if(s==='puan')return parseFloat(b.p.replace(',','.'))-parseFloat(a.p.replace(',','.'));
  if(s==='yorum')return b.y-a.y;
  if(s==='yakin'){ if(!konum){konumAl(draw);return 0;} return (uzak(a)??1e9)-(uzak(b)??1e9); }
  return b.s-a.s;
}

function haritaCiz(){
  list.style.display='none';mapEl.style.display='block';
  if(!map){
    map=L.map('map');
    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:19,attribution:'© OpenStreetMap'}).addTo(map);
  }
  setTimeout(()=>map.invalidateSize(),60);
  if(katman)map.removeLayer(katman);
  const pts=I.filter(x=>ok(x)&&typeof x.e==='number'&&typeof x.b==='number');
  const isaretler=pts.map(x=>L.circleMarker([x.e,x.b],{radius:7,weight:2,color:'#fff',fillColor:RENK[x.A]||'#3b82f6',fillOpacity:.9})
    .bindPopup('<b>'+esc(x.n)+'</b><br>⭐ '+esc(x.p)+' · '+x.y+' yorum<br>'+esc(x.m!=='Bilinmiyor'?x.m:'')+
      '<br><a href="'+esc(x.l)+'" target="_blank" rel="noopener">Google Haritalar\'da aç</a>'));
  katman=L.featureGroup(isaretler).addTo(map);
  if(pts.length)map.fitBounds(katman.getBounds().pad(0.15));
  else map.setView([37.0,37.5],10);
}

function satir(x){
  const puan=x.u?'<b>—</b><small>puansız</small>':`<b>★ ${x.p}</b><small>${x.y} oy</small>`;
  const mah=x.m!=='Bilinmiyor'?x.m.replace(' Mahallesi',''):'';
  const meta=[x.t,mah].filter(Boolean).map(esc).join(' · ');
  return `<div class="row">
    <div class="pt">${puan}</div>
    <div class="body">
      <div class="nm"><a class="nm-link" href="#" onclick="return false;" style="cursor:default;text-decoration:none;">${esc(x.n)}</a></div>
      ${meta?`<div class="meta-tags">${meta}</div>`:''}
      ${x.a?`<div class="meta-adres">${esc(x.a)}</div>`:''}
    </div>
    <a class="map-btn" href="${esc(x.l)}" target="_blank" rel="noopener">🗺️ Haritada Aç</a>
  </div>`;
}

function tumVerileriTemizle(){
  if(!confirm('Tüm favoriler ve filtreler sıfırlansın mı?'))return;
  localStorage.removeItem('gezi_durum');
  durum={};
  ic.value='';mq.value='';mahalleListe();mh.value='';
  mp.value='';my.value='';q.value='';
  sirala.value='skor';gs.value='';ana='';alt='';
  draw();
}

function draw(){
  if(ana===HARITA){haritaCiz();}
  else{mapEl.style.display='none';list.style.display='';}
  const f=I.filter(ok),arama=q.value.trim()!=='';
  yerSayisi.textContent=f.length;

  const cnt={};f.forEach(x=>{cnt[x.A]=(cnt[x.A]||0)+1});
  const TEK=ANA.length===1;
  if(TEK){
    const a0=ANA[0],c3={};f.forEach(x=>{c3[x.S]=(c3[x.S]||0)+1});
    tabs.innerHTML=`<button role="tab" aria-selected="${ana===''}" data-a="">✨ Tümü (${f.length})</button>`+
      O[a0].filter(s=>c3[s]).map(s=>`<button role="tab" aria-selected="${ana===a0&&alt===s}" data-a="${esc(a0)}" data-s="${esc(s)}">${esc(s)} (${c3[s]})</button>`).join('')+
      `<button role="tab" aria-selected="${ana===HARITA}" data-a="${HARITA}">🗺️ Harita</button>`;
  }else{
    tabs.innerHTML=`<button role="tab" aria-selected="${ana===''}" data-a="">✨ Tümü (${f.length})</button>`+
      ANA.map(a=>`<button role="tab" aria-selected="${ana===a}" data-a="${esc(a)}">${esc(a)} (${cnt[a]||0})</button>`).join('')+
      `<button role="tab" aria-selected="${ana===HARITA}" data-a="${HARITA}">🗺️ Harita</button>`;
  }

  if(!TEK&&ana&&ana!==HARITA){
    const c2={};f.filter(x=>x.A===ana).forEach(x=>{c2[x.S]=(c2[x.S]||0)+1});
    chips.innerHTML=`<button aria-pressed="${alt===''}" data-s="">Hepsi</button>`+
      O[ana].filter(s=>c2[s]).map(s=>`<button aria-pressed="${alt===s}" data-s="${esc(s)}">${esc(s)} (${c2[s]})</button>`).join('');
    chips.style.display='';
  }else chips.style.display='none';

  if(ana===HARITA)return;

  const sec=f.filter(x=>arama||!ana||(x.A===ana&&(!alt||x.S===alt)));
  const tumu=arama||!ana;let out='';

  ANA.forEach(a=>O[a].forEach(s=>{
    const it=sec.filter(x=>x.A===a&&x.S===s);if(!it.length)return;
    it.sort(kiyas);
    const bas=tumu?a+' · '+s:(alt?'':s);
    out+=(bas?`<h2>${esc(bas)}</h2>`:'')+'<div>'+it.map(satir).join('')+'</div>';
  }));
  list.innerHTML=out||'<p class="none">Aramanıza uygun mekan bulunamadı.</p>';
}

tabs.onclick=e=>{const b=e.target.closest('button');if(b){ana=b.dataset.a;alt=b.dataset.s||'';draw();}};
chips.onclick=e=>{const b=e.target.closest('button');if(b){alt=b.dataset.s;draw()}};
ic.onchange=()=>{mahalleListe();draw()};
mh.onchange=draw;mp.oninput=draw;my.oninput=draw;q.oninput=draw;gs.onchange=draw;sirala.onchange=draw;

mahalleListe();
draw();
</script></body></html>
"""

# Sade ayrımı kaldırıldığı için aynı şablona referans verildi
SABLON_SADE = SABLON


# ---------- "En iyi 10" kutusu (Tümü görünümünün en üstü) ----------
EN_IYI_ISARET = "enIyiKutusu"
EN_IYI_CSS = ("<style>.eniyi-not{font-size:12px;line-height:1.5;color:var(--muted);margin:10px 6px 4px}"
              ".eniyi-h{color:var(--gold)}</style>")
EN_IYI_JS = r"""
function enIyiKutusu(f,tumu,arama){
  if(ana!==''||arama)return '';
  const pn=x=>parseFloat(String(x.p).replace(',','.'))||0;
  const ad=f.filter(x=>!x.u&&pn(x)>=4.3).sort((a,b)=>(b.y||0)-(a.y||0)||pn(b)-pn(a)).slice(0,10);
  if(!ad.length)return '';
  return '<h2 class="eniyi-h">⭐ En iyi '+ad.length+'</h2><div>'+ad.map(satir).join('')+'</div>'+
    '<p class="eniyi-not"><b>Bu liste nasıl seçildi?</b> Google Haritalar puanı <b>4,3 ve üzeri</b> olan yerler alınır, '+
    '<b>yorum sayısı en çok olandan başlayarak</b> sıralanır. Yani çok kişinin gidip beğendiği yerler öne çıkar; '+
    'az yorumlu yüksek puanlar ve puanı düşük kalabalık yerler listeye girmez. Veriler Google Haritalar\'dan alınmıştır ve değişebilir.</p>';
}
"""
EN_IYI_ESKI = "list.innerHTML=out||'<p class=\"none\">Aramanıza uygun mekan bulunamadı.</p>';"
EN_IYI_YENI = "list.innerHTML=enIyiKutusu(f,tumu,arama)+(out||'<p class=\"none\">Aramanıza uygun mekan bulunamadı.</p>');"


def en_iyi_ekle(h):
    """Rehber sayfasına 'En iyi 10' kutusunu ekler. Zaten varsa ya da sayfa yapısı farklıysa dokunmaz."""
    if EN_IYI_ISARET in h or "function draw(){" not in h or EN_IYI_ESKI not in h or "</head>" not in h:
        return h
    h = h.replace("function draw(){", EN_IYI_JS + "function draw(){", 1)
    h = h.replace(EN_IYI_ESKI, EN_IYI_YENI, 1)
    return h.replace("</head>", EN_IYI_CSS + "</head>", 1)



# ---------- Mekan satırı: cadde/no ve güvenilmez mahalle bilgisi gizlenir ----------
ADRES_V1 = "${/*ilceMahalleSatiri*/mah?`<div class=\"meta-adres\">${esc(mah)}</div>`:''}"
ADRES_V2 = "${/*adresGizli*/''}"
ADRES_DEGISIM = [
    ("const meta=[x.t,mah].filter(Boolean)",
     "const meta=[x.t].filter(Boolean)"),
    ("${x.a?`<div class=\"meta-adres\">${esc(x.a)}</div>`:''}", ADRES_V2),
    ("tl(x.n+' '+x.t+' '+x.m)",
     "tl(x.n+' '+x.t+' '+x.m+' '+(x.a||''))"),
]


def adres_sade_ekle(h):
    """Mekan satırında adres satırını gizler (arama adresi yine kapsar). Tekrar çalıştırılabilir."""
    if "adresGizli" in h:
        return h
    if ADRES_V1 in h:                      # önceki sürümle güncellenmiş sayfa
        return h.replace(ADRES_V1, ADRES_V2, 1)
    if not all(eski in h for eski, _ in ADRES_DEGISIM[:2]):
        return h
    for eski, yeni in ADRES_DEGISIM:
        h = h.replace(eski, yeni, 1)
    return h


# ---------- Paket: sayfalama, arama gecikmesi, koyu+kümeli harita, mesafe, favori, paylaşılabilir link ----------
OZELLIK_ISARET = "ozellikPaketi"
OZELLIK_HEAD = (
    '<link rel="stylesheet" href="https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.css">'
    '<link rel="stylesheet" href="https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.Default.css">'
    '<script src="https://unpkg.com/leaflet.markercluster@1.5.3/dist/leaflet.markercluster.js"></script>'
    '<style>/*ozellikPaketi*/'
    '.daha{display:block;width:100%;margin:-4px 0 16px;padding:12px;font:inherit;font-size:13.5px;font-weight:700;'
    'color:var(--accent);background:var(--accent-soft);border:1px solid var(--accent);border-radius:14px;cursor:pointer}'
    '.fav{display:block;margin:2px auto 0;position:relative;z-index:2;background:none;border:0;font-size:17px;'
    'line-height:1;padding:4px;cursor:pointer}'
    '</style>')
OZELLIK_JS = r"""
/*ozellikPaketi*/
const LIM=60;let ekstra={},sonImza='',qt=null;
const sk=x=>{if(x.u)return -1;const y=x.y||0,p=parseFloat(String(x.p).replace(',','.'))||0;return y/(y+100)*p+100/(y+100)*4};
function mesafeYazi(d){return d<1?Math.round(d*1000)+' m':d.toFixed(1).replace('.',',')+' km'}
function bolumHtml(it,k){
  const n=LIM+(ekstra[k]||0);
  let s='<div>'+it.slice(0,n).map(satir).join('')+'</div>';
  if(it.length>n)s+='<button class="daha" data-k="'+esc(k)+'">Daha fazla göster ('+(it.length-n)+' mekan daha)</button>';
  return s;
}
mh.style.display='none';
gs.style.display='';
gs.innerHTML='<option value="">Tümü</option><option value="fav">❤️ Favori</option>';
function favSay(){const n=I.filter(x=>(durum[x.l]||{}).fav).length;gs.options[1].textContent='❤️ Favori ('+n+')';}
function hashYaz(){
  try{
    const p=new URLSearchParams();
    if(q.value.trim())p.set('q',q.value.trim());
    if(mp.value)p.set('mp',mp.value);
    if(my.value)p.set('my',my.value);
    if(ic.value)p.set('ic',ic.value);
    if(sirala.value==='puan'||sirala.value==='yorum')p.set('s',sirala.value);
    if(ana&&ana!==HARITA){p.set('a',ana);if(alt)p.set('t',alt);}
    if(gs.value)p.set('g',gs.value);
    const s=p.toString();
    history.replaceState(null,'',location.pathname+location.search+(s?'#'+s:''));
  }catch(e){}
}
function hashOku(){
  try{
    const p=new URLSearchParams(location.hash.slice(1));
    if(p.get('q'))q.value=p.get('q');
    if(p.get('mp'))mp.value=p.get('mp');
    if(p.get('my'))my.value=p.get('my');
    const i0=p.get('ic');if(i0&&[...ic.options].some(o=>o.value===i0))ic.value=i0;
    const s0=p.get('s');if(s0==='puan'||s0==='yorum')sirala.value=s0;
    if(p.get('g')==='fav')gs.value='fav';
    const a0=p.get('a');if(a0&&ANA.includes(a0)){ana=a0;alt=p.get('t')||'';}
  }catch(e){}
}
function ozetGuncelle(){
  const im=[q.value,mp.value,my.value,ic.value,sirala.value,ana,alt,gs.value].join('|');
  if(im!==sonImza){ekstra={};sonImza=im;}
  favSay();hashYaz();
}
list.addEventListener('click',e=>{
  const d=e.target.closest('.daha');
  if(d){const y=window.scrollY;ekstra[d.dataset.k]=(ekstra[d.dataset.k]||0)+100;draw();window.scrollTo(0,y);return;}
  const b=e.target.closest('.fav');
  if(b){
    const l=b.dataset.l;durum[l]=durum[l]||{};durum[l].fav=!durum[l].fav;
    if(!durum[l].fav)delete durum[l];
    durumYaz();b.textContent=(durum[l]||{}).fav?'❤️':'🤍';favSay();
    if(gs.value==='fav')draw();
  }
});
(function(){
  const r=document.querySelector('button.reset');if(!r)return;
  const w=document.createElement('div');w.style.cssText='display:flex;justify-content:flex-end;gap:14px';
  const b=document.createElement('button');b.className='reset';b.textContent='🔗 Bu görünümü paylaş';
  b.onclick=()=>{
    hashYaz();const u=location.href;
    if(navigator.share){navigator.share({title:document.title,url:u}).catch(()=>{});}
    else if(navigator.clipboard){navigator.clipboard.writeText(u).then(()=>{b.textContent='✓ Link kopyalandı';setTimeout(()=>{b.textContent='🔗 Bu görünümü paylaş'},2000)},()=>{prompt('Linki kopyala',u)});}
    else prompt('Linki kopyala',u);
  };
  r.parentNode.insertBefore(w,r);w.appendChild(b);w.appendChild(r);
})();
hashOku();
"""
OZELLIK_DEGISIM = [
    ("return b.s-a.s;", "return sk(b)-sk(a);"),
    ("'<div>'+it.map(satir).join('')+'</div>'", "bolumHtml(it,a+'|'+s)"),
    ("mp.oninput=draw;my.oninput=draw;q.oninput=draw;",
     "mp.oninput=()=>{clearTimeout(qt);qt=setTimeout(draw,200)};my.oninput=mp.oninput;"
     "q.oninput=()=>{clearTimeout(qt);qt=setTimeout(draw,200)};"),
    ("yerSayisi.textContent=f.length;", "yerSayisi.textContent=f.length;ozetGuncelle();"),
    ("const meta=[x.t].filter(Boolean).map(esc).join(' · ');",
     "const dm=uzak(x);const meta=[x.t,dm!=null?'\U0001F4CD '+mesafeYazi(dm):''].filter(Boolean).map(esc).join(' · ');"),
    ('<div class="pt">${puan}</div>',
     '<div class="pt">${puan}<button class="fav" data-l="${esc(x.l)}" aria-label="Favori">${(durum[x.l]||{}).fav?\'❤️\':\'\U0001F90D\'}</button></div>'),
    ("L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:19,attribution:'© OpenStreetMap'}).addTo(map);",
     "const koyu=!!(window.matchMedia&&matchMedia('(prefers-color-scheme: dark)').matches);"
     "L.tileLayer(koyu?'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png':'https://tile.openstreetmap.org/{z}/{x}/{y}.png',"
     "{maxZoom:19,subdomains:'abcd',attribution:'© OpenStreetMap'+(koyu?' © CARTO':'')}).addTo(map);"),
    ("katman=L.featureGroup(isaretler).addTo(map);",
     "katman=(L.markerClusterGroup?L.markerClusterGroup({chunkedLoading:true,maxClusterRadius:50,disableClusteringAtZoom:17}):L.featureGroup());"
     "isaretler.forEach(m=>katman.addLayer(m));katman.addTo(map);"),
]


def ozellik_ekle(h):
    """Sayfalama, arama gecikmesi, koyu/kümeli harita, mesafe, favori, paylaşılabilir link, güvenilir skor düzeltmesi.
    Tekrar çalıştırılabilir; sayfa yapısı beklenenden farklıysa hiçbir şeye dokunmaz."""
    if OZELLIK_ISARET in h or "function draw(){" not in h or "</head>" not in h:
        return h
    if not all(h.count(eski) == 1 for eski, _ in OZELLIK_DEGISIM):
        return h
    for eski, yeni in OZELLIK_DEGISIM:
        h = h.replace(eski, yeni, 1)
    h = h.replace("function draw(){", OZELLIK_JS + "function draw(){", 1)
    return h.replace("</head>", OZELLIK_HEAD + "</head>", 1)



# ---------- Filtre kutularına açıklayıcı etiket ----------
ETIKET_ISARET = "etiketPaketi"
ETIKET_JS = r"""
/*etiketPaketi*/
[[mp,'En az puan','örn. 4,3'],[my,'En az yorum','örn. 50'],[gs,'Görünüm','']].forEach(([el,t,ph])=>{
  const w=document.createElement('label');
  w.style.cssText='display:flex;flex-direction:column;gap:3px;flex:1;min-width:0;font-size:11.5px;font-weight:600;color:var(--muted)';
  el.parentNode.insertBefore(w,el);w.append(t,el);if(ph)el.placeholder=ph;
});
"""


def etiket_ekle(h):
    if ETIKET_ISARET in h or "ozellikPaketi" not in h or "function draw(){" not in h:
        return h
    return h.replace("function draw(){", ETIKET_JS + "function draw(){", 1)


# ---------- Paket 2: Tümü önizleme (kategori başına 5), favori sekmesi, tek satır kalp, harita düzeltmesi ----------
PAKET2_ISARET = "paket2Paketi"
PAKET2_FAV_CSS_ESKI = (".fav{display:block;margin:2px auto 0;position:relative;z-index:2;background:none;border:0;font-size:17px;"
                       "line-height:1;padding:4px;cursor:pointer}")
PAKET2_FAV_CSS_YENI = (".fav{display:inline;position:relative;z-index:2;background:none;border:0;font-size:14px;"
                       "line-height:1;padding:0;margin:0;cursor:pointer}")
PAKET2_HEAD = (
    "<style>/*paket2Paketi*/"
    ".gec{display:block;width:100%;margin:-4px 0 16px;padding:12px;font:inherit;font-size:13.5px;font-weight:700;"
    "color:var(--accent);background:var(--accent-soft);border:1px solid var(--accent);border-radius:14px;cursor:pointer}"
    "@media (prefers-color-scheme:dark){#map .leaflet-tile-pane{filter:invert(1) hue-rotate(180deg) brightness(.9) contrast(.95)}}"
    "</style>")
PAKET2_JS = r"""
/*paket2Paketi*/
let ONIZ=false;const ONIZ_N=7;
function bolumHtml2(it,k){
  if(ONIZ){
    let s='<div>'+it.slice(0,ONIZ_N).map(satir).join('')+'</div>';
    if(it.length>ONIZ_N)s+='<button class="gec" data-gec="'+esc(k)+'">'+esc(k.split('|')[1])+' bölümünün tamamını gör ('+it.length+') →</button>';
    return s;
  }
  return bolumHtml(it,k);
}
(gs.closest('label')||gs).style.display='none';
const _drawEski=draw;
draw=function(){
  ONIZ=(ana===''&&q.value.trim()===''&&gs.value!=='fav');
  _drawEski();
  favSekme();
};
function favSekme(){
  const eski=tabs.querySelector('button[data-fav]');if(eski)eski.remove();
  const n=I.filter(x=>(durum[x.l]||{}).fav).length;
  if(n>0||gs.value==='fav'){
    if(gs.value==='fav')tabs.querySelectorAll('button[aria-selected="true"]').forEach(b=>b.setAttribute('aria-selected','false'));
    const bt=document.createElement('button');bt.setAttribute('role','tab');bt.dataset.fav='1';
    bt.textContent='❤️ Favorilerim ('+n+')';bt.setAttribute('aria-selected',gs.value==='fav'?'true':'false');
    tabs.appendChild(bt);
  }
}
list.addEventListener('click',e=>{if(e.target.closest('.fav'))favSekme();});
tabs.addEventListener('click',e=>{
  const b=e.target.closest('button');if(!b)return;
  if(b.dataset.fav){e.stopPropagation();gs.value=gs.value==='fav'?'':'fav';ana='';alt='';draw();}
  else if(gs.value==='fav')gs.value='';
},true);
list.addEventListener('click',e=>{
  const g=e.target.closest('.gec');if(!g)return;
  const p=g.dataset.gec.split('|');gs.value='';ana=p[0];alt=p[1];draw();
  tabs.scrollIntoView({behavior:'smooth',block:'start'});
});
"""
PAKET2_FIT_ESKI = "if(pts.length)map.fitBounds(katman.getBounds().pad(0.15));"
PAKET2_FIT_YENI = ("if(pts.length){const la=pts.map(x=>x.e).sort((a,b)=>a-b),lo=pts.map(x=>x.b).sort((a,b)=>a-b),"
                   "a1=Math.floor(pts.length*.01),a2=Math.max(a1,Math.ceil(pts.length*.99)-1);"
                   "map.fitBounds([[la[a1],lo[a1]],[la[a2],lo[a2]]],{padding:[20,20]});}")
PAKET2_NM_ESKI = "${esc(x.n)}</a></div>"
PAKET2_NM_YENI = ("${esc(x.n)}</a>\u00a0<button class=\"fav\" data-l=\"${esc(x.l)}\" aria-label=\"Favori\">"
                  "${(durum[x.l]||{}).fav?'❤️':'\U0001F90D'}</button></div>")
PAKET2_DEGISIM = [
    (OZELLIK_DEGISIM[5][1], OZELLIK_DEGISIM[5][0]),                 # kalp artık puan sütununda değil
    (PAKET2_NM_ESKI, PAKET2_NM_YENI),                                # kalp isim satırında
    (PAKET2_FAV_CSS_ESKI, PAKET2_FAV_CSS_YENI),
    (OZELLIK_DEGISIM[6][1], OZELLIK_DEGISIM[6][0]),                 # CARTO (anahtar ister) yerine OSM
    (PAKET2_FIT_ESKI, PAKET2_FIT_YENI),
    ("bolumHtml(it,a+'|'+s)", "bolumHtml2(it,a+'|'+s)"),
    ("if(ana!==''||arama)return '';", "if(ana!==''||arama||gs.value==='fav')return '';"),
]


def paket2_ekle(h):
    if PAKET2_ISARET in h or "ozellikPaketi" not in h or "function draw(){" not in h or "</head>" not in h:
        return h
    if not all(h.count(eski) == 1 for eski, _ in PAKET2_DEGISIM):
        return h
    for eski, yeni in PAKET2_DEGISIM:
        h = h.replace(eski, yeni, 1)
    h = h.replace("function draw(){", PAKET2_JS + "function draw(){", 1)
    return h.replace("</head>", PAKET2_HEAD + "</head>", 1)


# ---------- Favori özelliği kaldırıldı (kalp düğmesi, Favorilerim sekmesi) ----------
FAV_KALDIR_ISARET = "favoriKaldirildi"
FAV_KALDIR_JS = r"""
/*favoriKaldirildi*/
favSekme=function(){};
gs.value='';
"""


def favori_kaldir(h):
    """Kalp düğmelerini ve Favorilerim sekmesini kaldırır. Tekrar çalıştırılabilir."""
    if FAV_KALDIR_ISARET in h or "ozellikPaketi" not in h or "function draw(){" not in h:
        return h
    h = re.sub(' ?<button class="fav"[^>]*>.*?</button>', '', h, flags=re.S)
    h = h.replace("confirm('Tüm favoriler ve filtreler sıfırlansın mı?')", "confirm('Filtreler sıfırlansın mı?')")
    if "function favSekme(" in h:
        h = h.replace("function draw(){", FAV_KALDIR_JS + "function draw(){", 1)
    return h


# ---------- Şehre göre ölçeklenen skor (En iyi 10 + kategori içi Güvenilir Skor) ----------
SKOR_ISARET = "skorDinamik"
SKOR_ESKI_ENIYI = "const ad=f.filter(x=>!x.u&&pn(x)>=4.3).sort((a,b)=>(b.y||0)-(a.y||0)||pn(b)-pn(a)).slice(0,10);"
SKOR_YENI_ENIYI = ("/*skorDinamik*/let mxY=0;f.forEach(x=>{if((x.y||0)>mxY)mxY=x.y||0;});const WB=Math.max(250,Math.round(mxY*0.05));"
                   "const bs=x=>{const y=x.y||0;return y/(y+WB)*pn(x)+WB/(y+WB)*4};"
                   "const ad=f.filter(x=>!x.u&&pn(x)>=4.3).sort((a,b)=>bs(b)-bs(a)).slice(0,10);")
SKOR_ESKI_NOT = "<b>yorum sayısı en çok olandan başlayarak</b> sıralanır. Yani çok kişinin gidip beğendiği yerler öne çıkar; "
SKOR_YENI_NOT = ("<b>puan ve yorum sayısı birlikte</b> değerlendirilerek sıralanır: çok yorumu olan yerlerin puanı olduğu gibi geçerli sayılır, "
                 "az yorumlu yerlerin puanı ise ortalamaya doğru çekilir. Yani hem çok sevilen hem çok kişi tarafından onaylanan yerler öne çıkar; ")
SKOR_ESKI_SK = ("const sk=x=>{if(x.u)return -1;const y=x.y||0,p=parseFloat(String(x.p).replace(',','.'))||0;"
                "return y/(y+100)*p+100/(y+100)*4};")
SKOR_YENI_SK = ("/*skorDinamik*/const WK={};I.forEach(x=>{const k=x.S||'';if((x.y||0)>(WK[k]||0))WK[k]=x.y||0;});"
                "const sk=x=>{if(x.u)return -1;const y=x.y||0,p=parseFloat(String(x.p).replace(',','.'))||0,"
                "W=Math.max(50,Math.round((WK[x.S||'']||0)*0.05));return y/(y+W)*p+W/(y+W)*4};")


def skor_ayarla(h):
    """En iyi 10: sahte yorum = rehberdeki en yüksek yorumun %5'i (en az 250). Kategori sıralaması: kategorinin kendi
    en yüksek yorumunun %5'i (en az 50). Tekrar çalıştırılabilir."""
    if SKOR_ISARET in h or "enIyiKutusu" not in h or "ozellikPaketi" not in h:
        return h
    for eski, _ in ((SKOR_ESKI_ENIYI, 0), (SKOR_ESKI_NOT, 0), (SKOR_ESKI_SK, 0)):
        if h.count(eski) != 1:
            return h
    return (h.replace(SKOR_ESKI_ENIYI, SKOR_YENI_ENIYI, 1)
             .replace(SKOR_ESKI_NOT, SKOR_YENI_NOT, 1)
             .replace(SKOR_ESKI_SK, SKOR_YENI_SK, 1))


# ---------- En iyi 10 notuna "detaylı açıklama" bağlantısı ----------
PUAN_LINK_ESKI = "<b>Bu liste nasıl seçildi?</b>"
PUAN_LINK_YENI = '<b>Bu liste nasıl seçildi?</b> (<a href="../puanlama.html" style="color:inherit;text-decoration:underline">detaylı açıklama</a>)'


def puan_link_ekle(h):
    if "puanlama.html" in h or h.count(PUAN_LINK_ESKI) != 1:
        return h
    return h.replace(PUAN_LINK_ESKI, PUAN_LINK_YENI, 1)


# ---------- Mevcut sayfalarda "Balık & Deniz Ürünleri" kategorisi ----------
def balik_ekle(h):
    """Gömülü veride balık lokantalarını/balıkçıları yeni kategoriye taşır. Tekrar çalıştırılabilir."""
    i = h.find("const V=")
    if i < 0:
        return h
    i += len("const V=")
    try:
        veri, bitis = json.JSONDecoder().raw_decode(h[i:])
    except Exception:
        return h
    yemek = veri.get("O", {}).get("Yemek")
    if not yemek or "Türk & Aile Restoranı" not in yemek:
        return h
    degisti = False
    for x in veri.get("I", []):
        if x.get("A") == "Yemek" and x.get("S") != BALIK_ALT and balik_mi(x.get("n", ""), x.get("t", "")):
            x["S"] = BALIK_ALT
            degisti = True
    if BALIK_ALT not in yemek and any(x.get("S") == BALIK_ALT for x in veri["I"]):
        yemek.insert(yemek.index("Türk & Aile Restoranı") + 1, BALIK_ALT)
        degisti = True
    if not degisti:
        return h
    yeni = json.dumps(veri, ensure_ascii=False).replace("</", "<\\/")
    return h[:i] + yeni + h[i + bitis:]


# ---------- Aynı mekanın çift kaydı, En iyi kutusunda tür kotası, ilçeye göre ölçek ----------
_KIMLIK_RE = re.compile(r"!1s(0x[0-9a-f]+:0x[0-9a-f]+)|!19s(ChIJ[\w-]+)")


def _yer_kimligi(link):
    m = _KIMLIK_RE.search(link or "")
    return (m.group(1) or m.group(2)) if m else None


def _tekrarsiz(kayitlar, yorum_anahtari, link_anahtari):
    """Aynı Google mekan kimliğine sahip kayıtlardan yorumu en çok olanı tutar; sırayı korur."""
    konum, cikti = {}, []
    for r in kayitlar:
        k = _yer_kimligi(r.get(link_anahtari, ""))
        if k is None:
            cikti.append(r)
        elif k not in konum:
            konum[k] = len(cikti)
            cikti.append(r)
        elif (r.get(yorum_anahtari) or 0) > (cikti[konum[k]].get(yorum_anahtari) or 0):
            cikti[konum[k]] = r
    return cikti


def tekrar_temizle(h):
    """Gömülü veride aynı mekan kimliğiyle tekrar eden kayıtları teke indirir. Tekrar çalıştırılabilir."""
    i = h.find("const V=")
    if i < 0:
        return h
    i += len("const V=")
    try:
        veri, bitis = json.JSONDecoder().raw_decode(h[i:])
    except Exception:
        return h
    eski = veri.get("I", [])
    yeni_liste = _tekrarsiz(eski, "y", "l")
    if len(yeni_liste) == len(eski):
        return h
    veri["I"] = yeni_liste
    return h[:i] + json.dumps(veri, ensure_ascii=False).replace("</", "<\\/") + h[i + bitis:]


KOTA_ISARET = "kotaVar"
KOTA_ESKI_ENIYI = ("const ad=f.filter(x=>!x.u&&pn(x)>=4.3).sort((a,b)=>bs(b)-bs(a))"
                   ".slice(0,(ic.value===''&&/Tum-Ilceler/i.test(location.pathname))?20:10);")
KOTA_YENI_ENIYI = ("/*kotaVar*/const NN=(ic.value===''&&/Tum-Ilceler/i.test(location.pathname))?20:10,CAP=NN>10?4:3,sc={},ad=[],ar=[];"
                   "f.filter(x=>!x.u&&pn(x)>=4.3).sort((a,b)=>bs(b)-bs(a)||(b.y||0)-(a.y||0)).forEach(x=>{"
                   "if(ad.length<NN&&(sc[x.S]||0)<CAP){sc[x.S]=(sc[x.S]||0)+1;ad.push(x);}else ar.push(x);});"
                   "if(ad.length<NN){ar.slice(0,NN-ad.length).forEach(x=>ad.push(x));ad.sort((a,b)=>bs(b)-bs(a)||(b.y||0)-(a.y||0));}")
KOTA_ESKI_NOT = "yerler listeye girmez. Veriler"
KOTA_YENI_NOT = "yerler listeye girmez. Çeşitlilik için aynı türden en fazla 3 yer (il rehberlerinde 4) gösterilir. Veriler"
KOTA_JS = r"""
/*kotaVar*/
function WKyenile(){
  for(const k in WK)delete WK[k];
  const il=ic.value;
  I.forEach(x=>{if(il&&x.c!==il)return;const k=x.S||'';if((x.y||0)>(WK[k]||0))WK[k]=x.y||0;});
}
const _drawKapsam=draw;
draw=function(){WKyenile();_drawKapsam();};
"""


def kota_ekle(h):
    """En iyi kutusuna tür kotası (10'da 3, 20'de 4; boş kalırsa doldurulur), eşitlikte yorum sayısı,
    kategori sıralamasında ilçe filtresine göre ölçek. Tekrar çalıştırılabilir."""
    if KOTA_ISARET in h or "skorDinamik" not in h or "function draw(){" not in h:
        return h
    for eski in (KOTA_ESKI_ENIYI, KOTA_ESKI_NOT):
        if h.count(eski) != 1:
            return h
    h = h.replace(KOTA_ESKI_ENIYI, KOTA_YENI_ENIYI, 1).replace(KOTA_ESKI_NOT, KOTA_YENI_NOT, 1)
    return h.replace("function draw(){", KOTA_JS + "function draw(){", 1)


# ---------- Paket 3: Türkçe karakter eşitlemeli arama, harita görünümü, Ne yesem?, WhatsApp, yemek dışı ayıklama ----------
PAKET3_ISARET = "paket3Paketi"
_YEMEK_DISI_TUR = re.compile(r"evcil hayvan|ayna dukkan|mutfak ekipman|ekipmanlari|produksiyon|isletme yonetimi|"
                             r"danisman|egitim merkezi|parti planlay|organizasyon|toptanci")


def yemek_disi_mi(tur):
    """Google türü yemek dışı bir işletmeyi gösteriyorsa True (Kahve/Şarküteri/Mangal mağazası ELENMEZ)."""
    return bool(_YEMEK_DISI_TUR.search(fold(tur or "")))


def yemek_disi_temizle(h):
    i = h.find("const V=")
    if i < 0:
        return h
    i += len("const V=")
    try:
        veri, bitis = json.JSONDecoder().raw_decode(h[i:])
    except Exception:
        return h
    eski = veri.get("I", [])
    yeni = [x for x in eski if not yemek_disi_mi(x.get("t", ""))]
    degisti = len(yeni) != len(eski)
    for x in yeni:
        for k in ("n", "t"):
            v = x.get(k)
            if v and _PUA.search(v):
                x[k] = _PUA.sub("", v).strip()
                degisti = True
    if not degisti:
        return h
    veri["I"] = yeni
    return h[:i] + json.dumps(veri, ensure_ascii=False).replace("</", "<\\/") + h[i + bitis:]


PAKET3_TL_ESKI = "const tl=s=>String(s).toLocaleLowerCase('tr');"
PAKET3_TL_YENI = ("const tl=s=>String(s).toLocaleLowerCase('tr').replace(/[çğıöşü]/g,c=>({'ç':'c','ğ':'g','ı':'i','ö':'o','ş':'s','ü':'u'}[c]));")

PAKET3_HEAD = r"""<script>/*paket3Paketi*/try{var _m=/[?&]harita=(\d)/.exec(location.search);if(_m)localStorage.setItem('hv',_m[1]);document.documentElement.setAttribute('data-hv',_m?_m[1]:(localStorage.getItem('hv')||'1'))}catch(e){document.documentElement.setAttribute('data-hv','1')}</script>
<style>/*paket3Paketi*/
html[data-hv="1"] #map .leaflet-tile-pane{filter:saturate(.65) contrast(.95) brightness(1.03)}
html[data-hv="2"] #map .leaflet-tile-pane{filter:grayscale(.6) brightness(1.04)}
html[data-hv="3"] #map .leaflet-tile-pane{filter:sepia(.15) saturate(.7)}
#map .leaflet-tile{outline:1px solid transparent}
#map .marker-cluster-small,#map .marker-cluster-medium,#map .marker-cluster-large{background:rgba(37,99,235,.28)}
#map .marker-cluster-small div,#map .marker-cluster-medium div,#map .marker-cluster-large div{background:rgba(37,99,235,.85);color:#fff;font-weight:700}
#map .leaflet-bar{border:0;box-shadow:0 2px 8px rgba(0,0,0,.25)}
#map .leaflet-bar a{border-radius:10px;margin-bottom:4px;border:0}
.nesec{margin:0 0 14px;padding:12px;background:var(--card);border:1px solid var(--accent);border-radius:14px}
.nesec h4{margin:0 0 8px;font-size:13.5px}
.nesec a.ny{display:block;padding:8px 0;border-top:1px solid var(--line);color:var(--text);text-decoration:none;font-size:14px;font-weight:600}
.nesec small{display:block;color:var(--muted);font-weight:400}
.nesec button{font:inherit;font-size:13px;font-weight:700;color:var(--accent);background:none;border:0;cursor:pointer;padding:6px 10px 0 0}
@media (prefers-color-scheme:dark){
html[data-hv="1"] #map .leaflet-tile-pane{filter:grayscale(.85) invert(.92) hue-rotate(185deg) brightness(.95) contrast(.9)}
html[data-hv="2"] #map .leaflet-tile-pane{filter:invert(1) hue-rotate(200deg) saturate(.55) brightness(.8) contrast(.9)}
html[data-hv="3"] #map .leaflet-tile-pane{filter:grayscale(1) invert(1) brightness(.75) contrast(1.05)}
#map{background:#0f172a}
#map .leaflet-bar a{background:#1e293b;color:#e2e8f0}
#map .leaflet-bar a:hover{background:#334155}
}
</style>
"""

PAKET3_JS = r"""<script>/*paket3Paketi*/
(function(){
  const r=document.querySelector('button.reset');if(!r)return;
  const w=r.parentNode;
  const kutu=document.createElement('div');kutu.className='nesec';kutu.style.display='none';
  const liste=document.getElementById('list');if(liste)liste.parentNode.insertBefore(kutu,liste);
  function cek(){
    const adaylar=I.filter(x=>ok(x)&&!x.u&&parseFloat(String(x.p).replace(',','.'))>=4.5&&(x.y||0)>=50);
    for(let i=adaylar.length-1;i>0;i--){const j=Math.floor(Math.random()*(i+1));[adaylar[i],adaylar[j]]=[adaylar[j],adaylar[i]];}
    const s=adaylar.slice(0,3);
    kutu.style.display='block';
    kutu.innerHTML='<h4>🎲 Bugün şunlara bak</h4>'+(s.length?s.map(x=>'<a class="ny" href="'+esc(x.l)+'" target="_blank" rel="noopener">'+esc(x.n)+'<small>'+esc(x.t||'')+' · ⭐ '+esc(x.p)+' · '+(x.y||0)+' yorum</small></a>').join(''):'<div style="font-size:13px;color:var(--muted)">Bu filtreyle 4,5+ puanlı ve 50+ yorumlu yer yok. Filtreleri gevşet.</div>')
      +'<button id="nyTekrar">🔄 Başka öner</button><button id="nyKapat">✕ Kapat</button>';
    document.getElementById('nyTekrar').onclick=cek;
    document.getElementById('nyKapat').onclick=()=>{kutu.style.display='none'};
  }
  const b=document.createElement('button');b.className='reset';b.textContent='🎲 Ne yesem?';b.onclick=cek;
  const wa=document.createElement('button');wa.className='reset';wa.textContent='💬 WhatsApp';
  wa.onclick=()=>{try{hashYaz();}catch(e){}window.open('https://wa.me/?text='+encodeURIComponent(document.title+' '+location.href),'_blank');};
  w.insertBefore(b,w.firstChild);w.insertBefore(wa,r);
  w.style.flexWrap='wrap';
})();
</script>
"""


def paket3_ekle(h):
    """Arama Türkçe karakter eşitleme, harita görünümü (?harita=1/2/3), Ne yesem?, WhatsApp, 'Veri tarihi'. Tekrar çalıştırılabilir."""
    if PAKET3_ISARET in h or "</head>" not in h or "</body>" not in h or "const V=" not in h:
        return h
    if h.count(PAKET3_TL_ESKI) != 1:
        return h
    h = h.replace(PAKET3_TL_ESKI, PAKET3_TL_YENI, 1)
    h = h.replace("</head>", PAKET3_HEAD + "</head>", 1)
    h = re.sub(r'(<div class="sub-meta">)(\d\d\.\d\d\.\d{4} · )', r"\1Veri tarihi: \2", h, count=1)
    k = h.rfind("</body>")
    return h[:k] + PAKET3_JS + h[k:]


# ---------- "Neler yenir?" popüler yerler sayfası (her il için, statik) ----------
POPULER_KATEGORILER = ["Döner & Kebap", "Çiğ Köfte", "Pide & Lahmacun", "Türk & Aile Restoranı",
                       "Balık & Deniz Ürünleri", "Kahvaltı", "Fırın & Tatlı", "Kafe & Kahve", "Fast food & Burger & Pizza"]
POPULER_KISA = {"Döner & Kebap": "🥙 Kebap", "Çiğ Köfte": "🌯 Çiğ köfte", "Pide & Lahmacun": "🍕 Pide",
                "Türk & Aile Restoranı": "🍲 Restoran", "Balık & Deniz Ürünleri": "🐟 Balık", "Kahvaltı": "🍳 Kahvaltı",
                "Fırın & Tatlı": "🍯 Tatlı", "Kafe & Kahve": "☕ Kafe", "Fast food & Burger & Pizza": "🍔 Fast food"}
POPULER_MIN_PUAN = 4.0
_PUA = re.compile(r"[-]")
_ULUSAL_ZINCIR = ("komagene", "mado", "burger king", "mcdonald", "starbucks", "kahve dunyasi", "tavuk dunyasi",
                  "domino", "pizza hut", "popeyes", "little caesars", "kfc", "subway", "dunkin", "simit sarayi",
                  "baydoner", "arbys", "carls jr", "sbarro", "gloria jeans", "caffe nero", "espresso lab", "usta donerci",
                  "kofteci yusuf", "pizza pizza", "burger lab")
_LEZZET = [("beyran", "Beyran"), ("paca", "Paça"), ("katmer", "Katmer"), ("kusleme", "Küşleme"), ("ciger", "Ciğer"),
           ("kunefe", "Künefe"), ("baklava", "Baklava"), ("lahmacun", "Lahmacun"), ("kelle", "Kelle"),
           ("iskembe", "İşkembe"), ("corba", "Çorba"), ("durum", "Dürüm"), ("simit", "Simit"), ("borek", "Börek"),
           ("yuvalama", "Yuvalama"), ("ali nazik", "Ali Nazik"), ("kaburga", "Kaburga"), ("tantuni", "Tantuni"),
           ("ic kofte", "İçli köfte"), ("sikma", "Sıkma"), ("manti", "Mantı"), ("pide", "Pide"), ("kahvalti", "Kahvaltı")]


def _ek_de(ad):
    """Yer eki: Gaziantep'te, Kilis'te, Hatay'da, İstanbul'da."""
    l = (ad or "").replace("İ", "i").replace("I", "ı").lower()
    unluler = "aıoueiöü"
    son_unlu = next((c for c in reversed(l) if c in unluler), "e")
    arka = son_unlu in "aıou"
    son = l[-1:] or "e"
    t = "t" if (son in "fstkçşhp" and son not in unluler) else "d"
    return f"{ad}'{t}{'a' if arka else 'e'}"


def _populer_anahtar(ad):
    a = fold(ad or "")
    for ayir in (" - ", "-", "(", " | ", ","):
        a = a.split(ayir)[0]
    return re.sub(r"\s+", " ", a).strip()


_ZINCIR_RE = re.compile(r"(?<![a-z0-9])(" + "|".join(re.escape(z) for z in _ULUSAL_ZINCIR) + r")(?![a-z0-9])")


def _zincir_mi(ad):
    return bool(_ZINCIR_RE.search(fold(ad or "")))


def populer_sayfa(h, dosya_adi, ad=None, ust=None):
    """'Tüm İlçeler' rehber HTML'sinden 'Neler yenir?' sayfası üretir. Yeni tarama gerekmez. HTML metni ya da None döner."""
    import html as _h
    i = h.find("const V=")
    if i < 0:
        return None
    try:
        veri = json.JSONDecoder().raw_decode(h[i + 8:])[0]
    except Exception:
        return None
    m = re.search(r"<title>([^<·–-]+)", h)
    il = ad or (m.group(1).strip() if m else dosya_adi.replace("-Tum-Ilceler", "").replace("-", " "))
    hepsi = []
    for x in veri.get("I", []):
        if x.get("S") not in POPULER_KATEGORILER or x.get("u") or not x.get("l"):
            continue
        try:
            x["_p"] = float(str(x.get("p", "0")).replace(",", "."))
        except ValueError:
            continue
        x["n"] = _PUA.sub("", x.get("n") or "").strip()
        x["t"] = _PUA.sub("", x.get("t") or "").strip()
        hepsi.append(x)
    iyi40 = sum(1 for x in hepsi if x["_p"] >= POPULER_MIN_PUAN)
    taban = POPULER_MIN_PUAN if iyi40 >= 12 else 3.8
    kayit = [x for x in hepsi if x["_p"] >= taban]
    dusuk = sorted([x for x in hepsi if x["_p"] < taban], key=lambda x: -(x.get("y") or 0))
    if len(kayit) < 5:
        return None
    mx = max(x.get("y") or 1 for x in kayit)
    esik = max(30, round(mx * 0.08))      # il eşiği: en çok yorumlunun %8'i (en az 30)
    C = sum(x["_p"] for x in kayit) / len(kayit)
    mm = max(20, min(250, round(mx * 0.05)))

    def skor(x):                          # puan ağırlıklı logaritmik popülerlik
        v = x.get("y") or 0
        rb = (v * x["_p"] + mm * C) / (v + mm)
        return rb * math.log(v + 10)

    for x in hepsi:
        x["_z"] = _zincir_mi(x["n"])
    kayit.sort(key=lambda x: (x["_z"], -skor(x)))
    e = lambda t: _h.escape(str(t or ""), quote=True)

    def etiketler(x):
        a = fold(f"{x['n']} {x['t']}")
        bulunan = [ad for k, ad in _LEZZET if k in a][:3]
        return "".join(f"<s>{e(t)}</s>" for t in bulunan)

    def kart(x, sira):
        y = x.get("y") or 0
        gen = 100 if mx <= 100 else max(8, min(100, round(100 * math.log(max(y, 100) / 100) / math.log(mx / 100))))
        rozet = " 💎" if x["_p"] >= 4.7 else ""
        zin = "<s class=\"z\">Ulusal zincir</s>" if x["_z"] else ""
        return (f'<a class="k" href="{e(x["l"])}" target="_blank" rel="noopener">'
                f'<span class="no">{sira}</span><span class="g"><b>{e(x["n"])}</b>'
                f'<small>{e(x.get("t"))}</small><span class="et">{zin}{etiketler(x)}</span><i style="width:{gen}%"></i></span>'
                f'<span class="r"><em>⭐ {e(x["p"])}{rozet}</em><u>{y:,} yorum</u></span></a>').replace(",", ".")

    nitelikli = sum(1 for x in kayit if (x.get("y") or 0) >= esik and not x["_z"])
    boyut = 12 if nitelikli >= 40 else (8 if nitelikli >= 20 else 6)
    efsane, sayac, marka = [], {}, {}
    for x in sorted((x for x in kayit if not x["_z"]), key=lambda x: -skor(x)):
        if len(efsane) >= boyut:
            break
        mk = _populer_anahtar(x.get("n"))
        if sayac.get(x["S"], 0) >= 4 or marka.get(mk, 0) >= 2:
            continue
        sayac[x["S"]] = sayac.get(x["S"], 0) + 1
        marka[mk] = marka.get(mk, 0) + 1
        efsane.append(x)
    devam = []
    if boyut == 12:                       # büyük illerde 13-30 arası açılır liste (JavaScript'siz)
        secildi = {id(x) for x in efsane}
        sayac2, marka2 = dict(sayac), dict(marka)
        for x in sorted((x for x in kayit if not x["_z"]), key=lambda x: -skor(x)):
            if len(devam) >= 18:
                break
            mk = _populer_anahtar(x.get("n"))
            if id(x) in secildi or sayac2.get(x["S"], 0) >= 8 or marka2.get(mk, 0) >= 2:
                continue
            sayac2[x["S"]] = sayac2.get(x["S"], 0) + 1
            marka2[mk] = marka2.get(mk, 0) + 1
            devam.append(x)
    devam_html = ""
    if len(devam) >= 3:
        devam_html = (f'<details class="dev"><summary>▼ Devamını göster ({len(efsane) + 1}–{len(efsane) + len(devam)})</summary>'
                      + "".join(kart(x, len(efsane) + n + 1) for n, x in enumerate(devam)) + "</details>")
    bol = [("kacirma", "🔥 Kaçırma", f'<section id="kacirma"><h2>🔥 Şehrin klasikleri: en çok konuşulan {len(efsane)} mekan</h2>'
            + "".join(kart(x, n + 1) for n, x in enumerate(efsane)) + devam_html + "</section>")]
    for sn, kat in enumerate(POPULER_KATEGORILER):
        tum = [x for x in kayit if x["S"] == kat]
        if not tum:
            continue
        kmax = max(x.get("y") or 0 for x in tum)
        ke = max(min(esik, round(kmax * 0.30)), min(100, esik))
        ic = [x for x in tum if (x.get("y") or 0) >= ke][:20]
        if len(ic) >= 2:
            sid = f"k{sn}"
            bol.append((sid, POPULER_KISA.get(kat, kat),
                        f'<section id="{sid}"><h2>{e(kat)}</h2>' + "".join(kart(x, n + 1) for n, x in enumerate(ic)) + "</section>"))
    dl = dusuk[:8]
    tb = str(taban).replace(".", ",")
    tek = "4,0'ın" if taban == 4.0 else "3,8'in"
    if len(dl) >= 2:
        bol.append(("dusuk", "⚠️ Puanı düşük",
                    f'<section id="dusuk"><h2>⚠️ Çok popüler ama puanı {tek} altında</h2>'
                    '<p class="not">Yorum sayısı yüksek, fakat memnuniyet puanı düşük kalan meşhur duraklar. Gitmeden önce güncel yorumlara göz atmanda fayda var.</p>'
                    + "".join(kart(x, n + 1) for n, x in enumerate(dl)) + "</section>"))
    tarih = time.strftime("%d.%m.%Y")
    rehber = dosya_adi
    ilde = _ek_de(il)
    cipler = "".join(f'<a href="#{sid}">{e(ad)}</a>' for sid, ad, _ in bol)
    govde = "".join(b for _, _, b in bol)
    return f"""<!DOCTYPE html>
<html lang="tr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="color-scheme" content="light dark">
<title>{e(ilde)} ne yenir, nerede yenir? · Local Radar</title>
<meta name="description" content="{e(il)}'a ilk kez gelenler için Google Haritalar'da en çok değerlendirilen favori mekanlar.">
<style>
:root{{--bg:#fff8ef;--card:#fff;--text:#2b1d12;--muted:#7a6a5c;--line:#f0e1cf;--accent:#c2410c;--bar:#fdba74}}
@media (prefers-color-scheme:dark){{:root{{--bg:#1a120c;--card:#261a12;--text:#f6eadc;--muted:#b9a592;--line:#3a2a1e;--accent:#fb923c;--bar:#9a4a16}}}}
*{{box-sizing:border-box}}html{{scroll-behavior:smooth}}body{{margin:0;background:var(--bg);color:var(--text);font:16px/1.4 system-ui,-apple-system,"Segoe UI",sans-serif}}
.w{{max-width:760px;margin:0 auto;padding:0 16px 40px}}
header{{padding:20px 0 14px}}.geri{{display:inline-block;margin:0 6px 14px 0;padding:6px 12px;border-radius:999px;border:1px solid var(--line);background:var(--card);color:var(--text);text-decoration:none;font-size:13px;font-weight:600}}header small{{color:var(--accent);font-weight:700;letter-spacing:.08em;text-transform:uppercase;font-size:12px}}
h1{{font-size:clamp(28px,7vw,44px);line-height:1.1;margin:6px 0 10px;font-weight:800}}
header p{{margin:0;color:var(--muted);font-size:14.5px}}
.cip{{display:flex;gap:8px;overflow-x:auto;padding:4px 0 12px;scrollbar-width:none}}.cip::-webkit-scrollbar{{display:none}}
.cip a{{flex:none;padding:8px 13px;border-radius:999px;background:var(--card);border:1px solid var(--line);color:var(--text);text-decoration:none;font-size:13.5px;font-weight:600}}
section{{scroll-margin-top:12px}}
h2{{font-size:19px;margin:26px 0 10px;color:var(--accent)}}
.k{{display:flex;gap:12px;align-items:center;padding:12px;margin-bottom:8px;background:var(--card);border:1px solid var(--line);border-radius:16px;color:inherit;text-decoration:none}}
.k:hover{{border-color:var(--accent)}}
.no{{flex:none;width:30px;height:30px;border-radius:50%;background:var(--accent);color:#fff;font-weight:800;display:grid;place-items:center;font-size:14px}}
.g{{flex:1;min-width:0}}.g b{{display:block;font-size:15.5px;line-height:1.25}}
.g small{{display:block;color:var(--muted);font-size:12.5px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
.et{{display:flex;flex-wrap:wrap;gap:4px;margin-top:4px}}.et:empty{{display:none}}
.et s{{text-decoration:none;font-size:11px;font-weight:700;padding:2px 8px;border-radius:999px;background:rgba(194,65,12,.1);color:var(--accent)}}
.et s.z{{background:rgba(120,120,120,.15);color:var(--muted)}}
.g i{{display:block;height:5px;border-radius:3px;background:var(--bar);margin-top:7px}}
.r{{flex:none;text-align:right}}.r em{{display:block;font-style:normal;font-weight:700;font-size:14px}}.r u{{text-decoration:none;color:var(--muted);font-size:12px}}
.dev summary{{cursor:pointer;list-style:none;text-align:center;padding:12px;margin:4px 0 10px;font-weight:700;font-size:13.5px;color:var(--accent);background:rgba(194,65,12,.08);border:1px solid var(--accent);border-radius:14px}}
.dev summary::-webkit-details-marker{{display:none}}
.dev[open] summary{{display:none}}
.not{{margin:-4px 0 10px;color:var(--muted);font-size:13px}}
.alt{{margin-top:28px;padding:14px;border-radius:14px;background:var(--card);border:1px solid var(--line);font-size:13px;color:var(--muted)}}
.alt a{{color:var(--accent);font-weight:700}}
</style></head><body><div class="w">
<header><a class="geri" href="../index.html">← Ana sayfa</a> <a class="geri" href="../rehberler/{e(rehber)}">← {e(il)} rehberi</a><br><small>Local Radar · {e(ust + " · " if ust else "")}Şehir lezzet rehberi</small><h1>{e(ilde)} ne yenir, nerede yenir?</h1>
<p>{e(il)}'a ilk kez gelenler için Google Haritalar'da en çok değerlendirilen ve {tb} üzeri puan alan favori mekanlar. Sıralama yorum sayısı ağırlıklıdır, puanla dengelenir. Çubuklar yorum yoğunluğunu gösterir (logaritmik ölçek, kabaca kıyas içindir). 💎 = 4,7 ve üzeri puan. Güncelleme: {tarih}</p></header>
<nav class="cip">{cipler}</nav>
{govde}
<div class="alt">Aynı markanın şubeleri, sana yakın olanı seçebilmen için ayrı listelenir (en üstte aynı markadan en fazla 2 şube). Ulusal zincirler listelerin sonuna alınır. İlçeye göre filtre ve harita için
<a href="../rehberler/{e(rehber)}">{e(il)} rehberine</a> ya da <a href="../index.html">ana sayfaya</a> göz at.
Veriler Google Haritalar'dan alınmıştır, yorum sayısı popülerliği gösterir; kalite için puana da bak.</div>
</div></body></html>"""


POPULER_LINK_ISARET = "populerLink"
eski_js_ayni = """    const a=document.createElement('a');a.href=u;a.textContent='🍽 Neler yenir? Misafir rehberi →';
    a.style.cssText='display:block;margin-top:10px;padding:10px 14px;border-radius:12px;background:var(--accent-soft);border:1px solid var(--accent);color:var(--accent);font-weight:700;font-size:14px;text-decoration:none';"""
yeni_js_ayni = """    const a=document.createElement('a');a.href=u;
    a.innerHTML='<span style="font-size:26px">🍽</span><span style="flex:1;line-height:1.25"><b style="display:block;font-size:16px">Burada neler yenir?</b><span style="font-size:12.5px;opacity:.92">Şehrin en çok sevilen yerleri · Misafir rehberi</span></span><b style="font-size:20px">→</b>';
    a.style.cssText='display:flex;align-items:center;gap:12px;margin:12px 0 4px;padding:14px 16px;border-radius:16px;background:linear-gradient(135deg,#ea580c,#f59e0b);color:#fff;text-decoration:none;box-shadow:0 6px 18px rgba(234,88,12,.35)';"""
POPULER_LINK_JS = r"""<script>/*populerLink*/
(function(){
  const m=location.pathname.match(/\/([^\/]+?)(?:-Tum-Ilceler)?\.html$/i);if(!m||/^(index|harita|bolge|puanlama)$/i.test(m[1]))return;
  const u='../populer/'+m[1]+'.html';
  fetch(u,{method:'HEAD'}).then(r=>{
    if(!r.ok)return;
    const hedef=document.querySelector('.sub-meta');if(!hedef)return;
    const a=document.createElement('a');a.href=u;
    a.innerHTML='<span style="font-size:26px">🍽</span><span style="flex:1;line-height:1.25"><b style="display:block;font-size:16px">Burada neler yenir?</b><span style="font-size:12.5px;opacity:.92">Şehrin en çok sevilen yerleri · Misafir rehberi</span></span><b style="font-size:20px">→</b>';
    a.style.cssText='display:flex;align-items:center;gap:12px;margin:12px 0 4px;padding:14px 16px;border-radius:16px;background:linear-gradient(135deg,#ea580c,#f59e0b);color:#fff;text-decoration:none;box-shadow:0 6px 18px rgba(234,88,12,.35)';
    hedef.parentNode.insertBefore(a,hedef.nextSibling);
  }).catch(()=>{});
})();
</script>
"""


POPULER_LINK2_ISARET = "Burada neler yenir?"


def populer_link_yenile(h):
    """Daha önce eklenmiş 'Neler yenir?' bağlantısını yeni (dikkat çekici) tasarımla değiştirir."""
    if POPULER_LINK2_ISARET in h or eski_js_ayni not in h:
        return h
    return h.replace(eski_js_ayni, yeni_js_ayni, 1)


_LINK_ESKI_SATIR = "const m=location.pathname.match(/\\/([^\\/]+)-Tum-Ilceler\\.html$/i);if(!m)return;"
_LINK_YENI_SATIR = "const m=location.pathname.match(/\\/([^\\/]+?)(?:-Tum-Ilceler)?\\.html$/i);if(!m||/^(index|harita|bolge|puanlama)$/i.test(m[1]))return;"


def populer_link_ilce(h):
    """Daha önce eklenmiş bağlantı koduna ilçe rehberlerini de tanıtır (ilçenin 'Neler yenir?' sayfası varsa görünür)."""
    if _LINK_ESKI_SATIR not in h:
        return h
    return h.replace(_LINK_ESKI_SATIR, _LINK_YENI_SATIR, 1)


def populer_link_ekle(h):
    """'Tüm İlçeler' rehberine 'Neler yenir?' sayfasına bağlantı ekler (sayfa varsa görünür). Tekrar çalıştırılabilir."""
    if POPULER_LINK_ISARET in h or "</body>" not in h or "sub-meta" not in h:
        return h
    k = h.rfind("</body>")
    return h[:k] + POPULER_LINK_JS + h[k:]


HARITA_EK_ISARET = "harita456Paketi"
HARITA_EK_CSS = """<style>/*harita456Paketi*/
@media (prefers-color-scheme:dark){
html[data-hv="4"] #map .leaflet-tile-pane{filter:saturate(.5) brightness(.7) contrast(1.05)}
html[data-hv="5"] #map .leaflet-tile-pane{filter:grayscale(.7) invert(.9) hue-rotate(185deg) brightness(1.25) contrast(.85)}
html[data-hv="6"] #map .leaflet-tile-pane{filter:saturate(.55) brightness(.92)}
}
</style>
"""


HARITA_NORMAL_ISARET = "haritaNormal"
HARITA_ESKI_BETIK = ("try{var _m=/[?&]harita=(\\d)/.exec(location.search);if(_m)localStorage.setItem('hv',_m[1]);"
                     "document.documentElement.setAttribute('data-hv',_m?_m[1]:(localStorage.getItem('hv')||'1'))}"
                     "catch(e){document.documentElement.setAttribute('data-hv','1')}")
HARITA_YENI_BETIK = ("try{var _m=/[?&]harita=(\\d)/.exec(location.search);"
                     "document.documentElement.setAttribute('data-hv',_m?_m[1]:'0')}"
                     "catch(e){document.documentElement.setAttribute('data-hv','0')}/*haritaNormal*/")
HARITA_NORMAL_CSS = '<style>/*haritaNormal*/html[data-hv="0"] #map .leaflet-tile-pane{filter:none}</style>\n'


def harita_normal(h):
    """Harita koyu temada da normal (filtresiz) açılır. ?harita=1..6 ile eski görünümler denenebilir."""
    if HARITA_NORMAL_ISARET in h or HARITA_ESKI_BETIK not in h:
        return h
    h = h.replace(HARITA_ESKI_BETIK, HARITA_YENI_BETIK, 1)
    return h.replace("</head>", HARITA_NORMAL_CSS + "</head>", 1)


def harita_ek(h):
    """Koyu temada ek harita görünümleri: ?harita=4 (kısık açık harita), 5 (daha açık gri-mavi), 6 (gündüz haritası, yumuşak)."""
    if HARITA_EK_ISARET in h or "paket3Paketi" not in h or "</head>" not in h:
        return h
    return h.replace("</head>", HARITA_EK_CSS + "</head>", 1)


TUM_ENIYI_ISARET = "TumEnIyiYok"


def tum_en_iyi_kaldir(h):
    """'Tüm İlçeler' rehberlerinde En iyi kutusu gösterilmez (yerine 'Neler yenir?' sayfası var). İlçe rehberleri aynı kalır."""
    if TUM_ENIYI_ISARET in h:
        return h
    m = re.search(r"if\(ana!==''\|\|arama[^\n;]*\)return '';", h)
    if not m:
        return h
    return h[:m.end()] + "if(/Tum-Ilceler/i.test(location.pathname))return '';/*TumEnIyiYok*/" + h[m.end():]


def en_iyi_min_yorum(h):
    """'En iyi' kutusuna 1-3 yorumlu yerlerin girmesini engeller (en az 10 yorum)."""
    return h.replace("!x.u&&pn(x)>=4.3)", "!x.u&&pn(x)>=4.3&&(x.y||0)>=10)")


def kaynak_notu_ekle(h):
    """Sayfa altındaki kaynak notuna ilçe sınırı verisinin (geoBoundaries, CC BY 4.0) adını ekler. Tekrar çalıştırılabilir."""
    if "geoBoundaries" in h:
        return h
    return h.replace("Harita: © OpenStreetMap</p>",
                     "Harita: © OpenStreetMap · İlçe sınırları: geoBoundaries (CC BY 4.0)</p>")


def sayfa_iyilestir(h):
    """Rehber sayfasına bütün iyileştirmeleri uygular (hepsi tekrar çalıştırılabilir)."""
    h = en_iyi_ekle(h)
    h = adres_sade_ekle(h)
    h = ozellik_ekle(h)
    h = etiket_ekle(h)
    h = paket2_ekle(h)
    h = favori_kaldir(h)
    h = skor_ayarla(h)
    h = puan_link_ekle(h)
    h = h.replace("const ONIZ_N=5;", "const ONIZ_N=7;")
    h = h.replace("bs(b)-bs(a)).slice(0,10);", "bs(b)-bs(a)).slice(0,(ic.value===''&&/Tum-Ilceler/i.test(location.pathname))?20:10);")
    h = kota_ekle(h)
    h = balik_ekle(h)
    h = yemek_disi_temizle(h)
    h = paket3_ekle(h)
    h = populer_link_ekle(h)
    h = en_iyi_min_yorum(h)
    h = kaynak_notu_ekle(h)
    h = harita_ek(h)
    h = harita_normal(h)
    h = tum_en_iyi_kaldir(h)
    h = populer_link_yenile(h)
    h = populer_link_ilce(h)
    return tekrar_temizle(h)



def html_yaz(kayitlar, ayar, yol, sade=False, yemek_sadece=False, alisveris_acik=True):
    ogeler = []
    kasap_var = False
    balik_var = False
    for r in _tekrarsiz(kayitlar, "Yorum Sayısı", "Harita Linki"):
        bolum = r["Bölüm"]
        if ANA.get(bolum) == "Yemek" and yemek_disi_mi(r.get("Tür", "")):
            continue
        alt = yemek_alt(r)
        if yemek_sadece:
            if alt is None:
                continue
            ana, sub = "Yemek", alt
        else:
            if bolum == "Alışveriş" and alt is None and not alisveris_acik:
                continue
            ana = ANA.get(bolum, "Diğer")
            sub = bolum if ana == "Yemek" else r["Grup"]
            if alt in ("Kasap", BALIK_ALT):
                ana, sub = "Yemek", alt
        if sub == "Kasap":
            kasap_var = True
        if sub == BALIK_ALT:
            balik_var = True
        ogeler.append({"n": r["Yer"], "p": str(r["Puan"]).replace(".", ","), "y": r["Yorum Sayısı"],
                       "u": 1 if r.get("_puansiz") else 0,
                       "s": r["Güvenilir Skor"],
                       "t": r.get("Tür", ""), "a": r.get("Adres", ""), "f": r.get("Fiyat", ""),
                       "m": r.get("Mahalle", "Bilinmiyor"), "c": r.get("İlçe", ""), "l": r["Harita Linki"],
                       "e": r.get("Enlem"), "b": r.get("Boylam"),
                       "w": 1 if _yeni_mi(r.get("İlk Görülme", "")) else 0,
                       "A": ana, "S": sub})

    if yemek_sadece:
        O = {"Yemek": list(YEMEK_ALT_SIRA)}
    else:
        O = {k: list(v) for k, v in ALT_SIRA.items()}
        if kasap_var:
            O["Yemek"].append("Kasap")
        if balik_var:
            O["Yemek"].append(BALIK_ALT)
    veri = {"O": O, "I": ogeler}
    alt = "Scan, discover, plan. Google Maps results filtered and organized by Local Radar."
    tarih = time.strftime("%d.%m.%Y")

    sayfa = (SABLON.replace("__LEAFLET_CSS__", LEAFLET_CSS)
             .replace("__DATA__", json.dumps(veri, ensure_ascii=False).replace("</", "<\\/"))
             .replace("__BASLIK__", ayar["baslik"])
             .replace("__ALT__", alt)
             .replace("__TARIH__", tarih))

    with open(yol, "w", encoding="utf-8") as f:
        f.write(sayfa_iyilestir(sayfa))


ENGEL_IPUCU = ("unusual traffic", "olağan dışı trafik", "robot olmadığınız",
               "not a robot", "before you continue", "recaptcha", "captcha")


def engel_var_mi(page):
    try:
        govde = page.evaluate("() => document.body ? document.body.innerText.slice(0, 3000) : ''") or ""
        metin = ((page.title() or "") + " " + govde).lower()
        if any(ip in metin for ip in ENGEL_IPUCU):
            return True
        dom_bos = page.evaluate("""() => {
            return document.querySelectorAll('a[href*="/maps/"], div[role="feed"]').length === 0
                   && document.body && document.body.innerText.length < 100;
        }""")
        return bool(dom_bos)
    except Exception:
        return False


def _calisan_secici_kaydet(rapor):
    try:
        kayit = {
            "tarih": time.strftime("%Y-%m-%d %H:%M"),
            "feed": rapor.get("feed"),
            "kart": rapor.get("kart"),
            "yildiz": rapor.get("yildiz"),
        }
        with open(SECICI_DOSYASI, "w", encoding="utf-8") as f:
            json.dump(kayit, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def google_yapisi_saglikli_mi(sayfa):
    try:
        rapor = sayfa.evaluate("""() => {
            const FEED = ['div[role="feed"]', 'div[aria-label*="Sonuçlar"]',
                          'div[aria-label*="Results"]', 'div[jsaction*="scroll"]'];
            const KART = ['a.hfpxzc', 'a[href*="/maps/place/"]',
                          'div[role="feed"] a[aria-label]', 'div[role="article"] a[href]'];
            const YILDIZ = ['span[role="img"]', '[aria-label*="yıldız"]', '[aria-label*="stars"]'];

            const rapor = {feed: null, kart: null, yildiz: null, toplam_kart: 0};
            for (const s of FEED) {
                const el = document.querySelector(s);
                if (el) { rapor.feed = s; break; }
            }
            for (const s of KART) {
                const n = document.querySelectorAll(s).length;
                if (n > 0) { rapor.kart = s; rapor.toplam_kart = n; break; }
            }
            for (const s of YILDIZ) {
                if (document.querySelector(s)) { rapor.yildiz = s; break; }
            }
            return rapor;
        }""")
    except Exception as e:
        LOG(f"   Health check failed: {e}")
        return None

    if not rapor.get("kart"):
        LOG("⚠️  WARNING: Google Maps card selector not found!")
        LOG(f"   Feed selector: {rapor.get('feed')}")
        LOG(f"   Star selector: {rapor.get('yildiz')}")
        try:
            zaman = int(time.time())
            sayfa.screenshot(path=f"{DOSYA_TANI}_{zaman}.png")
            with open(f"{DOSYA_TANI}_{zaman}.html", "w", encoding="utf-8") as f:
                f.write(sayfa.content())
            LOG(f"   Diagnostic files saved: {DOSYA_TANI}_{zaman}.png / {DOSYA_TANI}_{zaman}.html")
        except Exception:
            pass
        return rapor

    _calisan_secici_kaydet(rapor)
    return rapor


GORUNUM_PX = 700
ZOOM_MAKS = 17


def kenar_km(lat, zoom):
    return GORUNUM_PX * 156.543 * math.cos(math.radians(lat)) / (2 ** zoom)


def zoom_sec(yaricap, lat=37.0):
    for z in range(ZOOM_MAKS, 7, -1):
        if kenar_km(lat, z) >= 2 * yaricap * 1.02:
            return z
    return 8


def yer_bul(*sorgular):
    for sorgu in sorgular:
        url = "https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode(
            {"q": sorgu, "format": "jsonv2", "limit": 1, "accept-language": "tr", "countrycodes": "tr"})
        istek = urllib.request.Request(url, headers={"User-Agent": "local-radar/1.1"})
        try:
            with urllib.request.urlopen(istek, timeout=15) as r:
                sonuc = json.load(r)
        except Exception:
            sonuc = []
        if sonuc:
            s0 = sonuc[0]
            gu, ku, ba, do = [float(x) for x in s0["boundingbox"]]
            yaricap = min(max(mesafe_km((gu, ba), (ku, do)) / 2 * 1.1, 1.0), 12.0)
            return float(s0["lat"]), float(s0["lon"]), round(yaricap, 1)
        time.sleep(1.1)
    return None


BILINEN_YERLER = {
    "nizip": (37.0108, 37.7952, 10.0),
    "gaziantep": (37.0662, 37.3833, 10.0),
}
ILCE_MIN_YARICAP = 3.0
ILCE_VARSAYILAN_YARICAP = 8.0


def alan_bul(ad, sorgular, ilce_geneli=True):
    if ilce_geneli and fold(ad) in BILINEN_YERLER:
        e, b, r = BILINEN_YERLER[fold(ad)]
        return e, b, r, "built-in table"
    s = yer_bul(*sorgular)
    if not s:
        return None
    e, b, r = s
    if ilce_geneli and r < ILCE_MIN_YARICAP:
        return e, b, ILCE_VARSAYILAN_YARICAP, f"area too small ({r} km), expanded to {ILCE_VARSAYILAN_YARICAP} km"
    return e, b, r, "map service"


def izgara_noktalari(enlem, boylam, yaricap, aktif=True):
    if not aktif or yaricap <= 2.0:
        return [(enlem, boylam, yaricap)]
    adim = max(1.8, yaricap * 0.55)
    pts = []
    for _ in range(4):
        pts = []
        dy = adim * 0.87
        cosl = max(math.cos(math.radians(enlem)), 0.2)
        j, yy = 0, -yaricap
        while yy <= yaricap + 1e-9:
            xx = -yaricap + (adim / 2 if j % 2 else 0)
            while xx <= yaricap + 1e-9:
                if xx * xx + yy * yy <= yaricap * yaricap:
                    pts.append((enlem + yy / 111.0, boylam + xx / (111.0 * cosl), adim * 0.8))
                xx += adim
            yy += dy
            j += 1
        if len(pts) <= 30:
            return pts
        adim *= 1.25
    return pts


def izgara_genislet(alanlar, aktif=True):
    sonuc = []
    for (en, bo, r, _z) in alanlar:
        for (e2, b2, r2) in izgara_noktalari(en, bo, r, aktif):
            sonuc.append((e2, b2, r2, zoom_sec(r2)))
    return sonuc


ARA_KAYIT_SIKLIGI = 5
DOLU_ESIK = 100
MAKS_YIGIN = 1500


def _arama_anahtari(kat, yer, alanli):
    if alanli:
        return f"{kat}|{round(yer[0], 4)},{round(yer[1], 4)}"
    return f"{kat}|{yer}"


HIZLI_YUKLEME = True
HIZLI_KAYDIRMA = True
PARALEL = 1
TEKRAR_ONLEME_GUN = 0
VERIMSIZ_ATLA = False
YOKLAMA_ESIK_ARAMA = 8
ALAN_DISI_ORAN = 0.8
SINIR_ONBELLEK_BASARILI_GUN = 365
SINIR_ONBELLEK_HATA_GUN = 2
SINIR_MAKS_DERECE = 1.0

SON_ISARETLERI = ("sonuna ulastiniz", "end of the list", "reached the end")


def _kare_disi(la, lo, h, pay=1.1):
    dy = abs(la - h[0]) * 111.0
    dx = abs(lo - h[1]) * 111.0 * max(math.cos(math.radians(h[0])), 0.2)
    return dy > h[2] * pay or dx > h[2] * pay


def _dis_orani(kartlar, hucre):
    kon = dis = 0
    for k in kartlar:
        la, lo = koordinat(k["link"])
        if la is None:
            continue
        kon += 1
        if _kare_disi(la, lo, hucre):
            dis += 1
    return (dis / kon) if kon else 0.0


def _tile_xy(lat, lon, t):
    n = 2 ** t
    x = int((lon + 180.0) / 360.0 * n)
    y = int((1.0 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2.0 * n)
    return min(max(x, 0), n - 1), min(max(y, 0), n - 1)


def _tile_sinir(t, x, y):
    n = 2 ** t

    def enlem(yy):
        return math.degrees(math.atan(math.sinh(math.pi * (1 - 2.0 * yy / n))))
    return enlem(y + 1), x / n * 360.0 - 180.0, enlem(y), (x + 1) / n * 360.0 - 180.0


def tile_hucre(t, x, y):
    s, w, n_, e = _tile_sinir(t, x, y)
    lat, lon = (s + n_) / 2.0, (w + e) / 2.0
    return (lat, lon, 40075.0 * math.cos(math.radians(lat)) / (2 ** t) / 2.0, t + 1)


def _kare_alanla_kesisir(tid, alanlar):
    s, w, n_, e = _tile_sinir(*tid)
    for a in alanlar:
        dy = max(0.0, s - a[0], a[0] - n_) * 111.0
        dx = max(0.0, w - a[1], a[1] - e) * 111.0 * max(math.cos(math.radians(a[0])), 0.2)
        if math.hypot(dx, dy) <= a[2]:
            return True
    return False


def kok_seviye(alanlar):
    sev = []
    for a in alanlar:
        kenar = 40075.0 * math.cos(math.radians(a[0])) / (2 * a[2])
        sev.append(int(math.floor(math.log2(max(kenar, 1.0)))))
    return max(8, min(ZOOM_MAKS - 1, min(sev)))


def kok_kareleri(alanlar, t):
    kareler = set()
    for a in alanlar:
        cosl = max(math.cos(math.radians(a[0])), 0.2)
        dlat, dlon = a[2] / 111.0, a[2] / (111.0 * cosl)
        x0, y1 = _tile_xy(a[0] - dlat, a[1] - dlon, t)
        x1, y0 = _tile_xy(a[0] + dlat, a[1] + dlon, t)
        for x in range(x0, x1 + 1):
            for y in range(y0, y1 + 1):
                if _kare_alanla_kesisir((t, x, y), alanlar):
                    kareler.add((t, x, y))
    return sorted(kareler)


def kare_bol(tid):
    t, x, y = tid
    return [(t + 1, 2 * x + i, 2 * y + j) for i in (0, 1) for j in (0, 1)]


def _sabit_izgara_zoomu(alanlar, hucre_km):
    hucre_km = max(0.2, float(hucre_km or HUCRE_KM))
    ort_lat = sum(a[0] for a in alanlar) / max(len(alanlar), 1)
    cosl = max(math.cos(math.radians(ort_lat)), 0.2)
    for t in range(8, 23):
        kenar = 40075.0 * cosl / (2 ** t)
        if kenar <= hucre_km:
            return t
    return 22


def sabit_izgara_hucreleri(alanlar, hucre_km):
    if not alanlar:
        return []
    t = _sabit_izgara_zoomu(alanlar, hucre_km)
    return [tile_hucre(*tid) for tid in kok_kareleri(alanlar, t)]


def arama_sayisi_tahmini(alanlar, kelime_sayisi, hucre_km):
    return len(sabit_izgara_hucreleri(alanlar, hucre_km)) * max(0, int(kelime_sayisi or 0))


def kaydir_ve_topla(page, durdur=lambda: False, hucre=None):
    toplanan, hareketsiz = {}, 0
    if not HIZLI_KAYDIRMA:
        for _ in range(40):
            if durdur():
                break
            for k in page.evaluate(JS_KARTLAR):
                toplanan[k["link"]] = k
            onceki = len(toplanan)
            page.evaluate(JS_KAYDIR)
            time.sleep(1.5)
            for k in page.evaluate(JS_KARTLAR):
                toplanan[k["link"]] = k
            hareketsiz = hareketsiz + 1 if len(toplanan) == onceki else 0
            if hareketsiz >= 3:
                break
        return toplanan.values()

    try:
        feed_ok = page.evaluate("""() => {
            const FEED = ['div[role="feed"]', 'div[aria-label*="Sonuçlar"]',
                          'div[aria-label*="Results"]', 'div[jsaction*="scroll"]'];
            for (const s of FEED) if (document.querySelector(s)) return true;
            return [...document.querySelectorAll('div')]
                     .some(d => d.scrollHeight > d.clientHeight + 200);
        }""")
        if not feed_ok:
            LOG("   ⚠️  No scrollable feed found.")
    except Exception:
        pass

    for _ in range(80):
        if durdur():
            break
        yeniler = []
        for k in page.evaluate(JS_KARTLAR):
            if k["link"] not in toplanan:
                toplanan[k["link"]] = k
                yeniler.append(k)
        hareketsiz = 0 if yeniler else hareketsiz + 1
        if hareketsiz >= 2:
            break
        try:
            son = fold(page.evaluate(JS_SON) or "")
        except Exception:
            son = ""
        if any(x in son for x in SON_ISARETLERI):
            break
        if hucre and len(yeniler) >= 8 and len(toplanan) >= 20 and _dis_orani(yeniler, hucre) >= ALAN_DISI_ORAN:
            break
        onceki_dom = page.evaluate(JS_SAYI)
        page.evaluate(JS_KAYDIR)
        for _ in range(10):
            time.sleep(0.3)
            if page.evaluate(JS_SAYI) > onceki_dom:
                break
    return toplanan.values()


def cerez_gec(page):
    for yazi in ("Tümünü kabul et", "Accept all", "Kabul et"):
        try:
            el = page.query_selector(f'button:has-text("{yazi}")')
            if el:
                el.click(timeout=2000)
                time.sleep(0.5)
                return
        except Exception:
            pass


def doygun_mu(kartlar, hucre):
    if len(kartlar) < DOLU_ESIK:
        return False
    return _dis_orani(kartlar, hucre) <= 0.3


def arama_yap(sayfa, url, hucre, durdur):
    sayfa.goto(url, wait_until="domcontentloaded")
    if "consent" in (getattr(sayfa, "url", "") or ""):
        cerez_gec(sayfa)

    sayfa.wait_for_selector(
        'div[role="feed"], div[aria-label*="Sonuçlar"], div[aria-label*="Results"], '
        'a[href*="/maps/place/"]',
        timeout=10000
    )

    if HIZLI_KAYDIRMA:
        try:
            sayfa.wait_for_selector(
                'a.hfpxzc, a[href*="/maps/place/"], div[role="article"] a[href]',
                timeout=4000
            )
        except Exception:
            pass
    else:
        time.sleep(2)

    rapor = google_yapisi_saglikli_mi(sayfa)
    if rapor and not rapor.get("kart"):
        LOG("   ⚠️  No cards found in this search (Google structure may have changed).")
        return []

    return list(kaydir_ve_topla(sayfa, durdur, hucre))


def _json_oku(yol, varsayilan):
    try:
        return json.load(open(yol, encoding="utf-8"))
    except Exception:
        return varsayilan


def json_eskileri_tasi():
    """Ana klasördeki eski raw_*.json ve scan_resume_*.json dosyalarını tarama_json klasörüne taşır.
    Zaten orada aynı adlı dosya varsa dokunmaz. Kaç dosya taşındığını döndürür."""
    import glob, shutil
    n = 0
    try:
        for desen in ("raw_*.json", "scan_resume_*.json"):
            for yol in glob.glob(desen):
                if yol == DOSYA_HAM_HAVUZ:          # raw_pool.json havuz dosyası, taşınmaz
                    continue
                hedef = os.path.join(KLASOR_TARAMA_JSON, os.path.basename(yol))
                if os.path.exists(hedef):
                    continue
                os.makedirs(KLASOR_TARAMA_JSON, exist_ok=True)
                shutil.move(yol, hedef)
                n += 1
    except Exception:
        pass
    return n


def _json_yaz(yol, veri):
    try:
        os.makedirs(os.path.dirname(yol) or ".", exist_ok=True)
        with open(yol, "w", encoding="utf-8") as f:
            json.dump(veri, f, ensure_ascii=False)
    except Exception:
        pass


def _gun_farki(tarih):
    try:
        return (time.time() - time.mktime(time.strptime(tarih, "%Y-%m-%d"))) / 86400.0
    except Exception:
        return 1e9


def _hucre_anahtari(kat, yer, alanli):
    if alanli and isinstance(yer, tuple) and yer and yer[0] == "sabit":
        return f"{kat}|s{yer[1]}"
    if alanli:
        return f"{kat}|k{yer[0]}/{yer[1]}/{yer[2]}"
    return f"{kat}|{yer}"


def _kelime_verimi_guncelle(verim, tekil):
    kayit = _json_oku(VERIM_DOSYASI, {})
    bugun = time.strftime("%Y-%m-%d")
    for kat, v in verim.items():
        e = kayit.setdefault(kat, {"arama": 0, "tekil": 0, "son": bugun})
        e["arama"] += v[0]
        e["tekil"] += tekil.get(kat, 0)
        e["son"] = bugun
    _json_yaz(VERIM_DOSYASI, kayit)


def _verimsiz_kelimeler(kategoriler):
    kayit = _json_oku(VERIM_DOSYASI, {})
    cikar = []
    for k in kategoriler:
        e = kayit.get(k)
        if e and e["arama"] >= YOKLAMA_ESIK_ARAMA and e["tekil"] == 0:
            cikar.append(k)
    return cikar


def tara(ayar, ilerleme=lambda i, n, m: print(f"[{i}/{n}] {m}"), durdur=lambda: False,
         ekranda_goster=EKRANDA_GOSTER, devam=False):
    import threading, random, collections
    from playwright.sync_api import sync_playwright
    json_eskileri_tasi()
    ara_yolu = f"{DOSYA_ARA_KAYIT_PREFIX}{ayar['dosya']}.json"
    tum, bitenler, verim = {}, set(), {}
    if devam and os.path.exists(ara_yolu):
        veri = _json_oku(ara_yolu, {})
        tum, bitenler = veri.get("tum", {}), set(veri.get("biten", []))
        if tum:
            LOG(f"Resume file found: {len(bitenler)} searches will be skipped, {len(tum)} places ready.")

    kilit = threading.Lock()
    alanlar = ayar.get("alanlar")
    bolme = bool(ayar.get("bolme", True))
    sabit_izgara = bool(ayar.get("sabit_izgara", SABIT_IZGARA))
    try:
        hucre_km = float(ayar.get("hucre_km", HUCRE_KM) or HUCRE_KM)
    except (TypeError, ValueError):
        hucre_km = HUCRE_KM
    if hucre_km <= 0:
        hucre_km = HUCRE_KM
    kategoriler = list(ayar["kategoriler"])
    if VERIMSIZ_ATLA:
        atlanan = _verimsiz_kelimeler(kategoriler)
        if atlanan:
            kategoriler = [k for k in kategoriler if k not in atlanan]
            LOG(f"{len(atlanan)} inefficient keywords skipped: {', '.join(atlanan)}")

    defter = _json_oku(DEFTER, {}) if True else {}
    bugun = time.strftime("%Y-%m-%d")
    havuz_kartlari = _json_oku(HAM_HAVUZ, {})

    gorevler = collections.deque()
    gorunen_gorev = set()
    if alanlar and sabit_izgara:
        hucreler = sabit_izgara_hucreleri(alanlar, hucre_km)
        kesin = arama_sayisi_tahmini(alanlar, len(kategoriler), hucre_km)
        LOG(f"Fixed grid enabled: {len(hucreler)} cells to scan (exact search count: {kesin}).")
        for i, hucre in enumerate(hucreler):
            hedef = ("sabit", i, hucre)
            for k in kategoriler:
                gorevler.append((k, hedef))
                gorunen_gorev.add((k, hedef))
    elif alanlar:
        t0 = kok_seviye(alanlar)
        kokler = kok_kareleri(alanlar, t0)
        LOG(f"Area will be scanned with {len(kokler)} root tiles (overlapping neighborhoods scanned once).")
        for tid in kokler:
            for k in kategoriler:
                gorevler.append((k, tid))
                gorunen_gorev.add((k, tid))
    else:
        for b in ayar["bolgeler"]:
            for k in kategoriler:
                gorevler.append((k, b))

    durum = {"i": 0, "aktif": 0, "atlanan": 0, "bolunen": 0, "hata": None}

    def kaydet():
        _json_yaz(ara_yolu, {"tum": tum, "biten": sorted(bitenler)})

    def bol(kat, tid):
        with kilit:
            if (not sabit_izgara) and bolme and alanlar and tid[0] + 2 <= ZOOM_MAKS and len(gorevler) < MAKS_YIGIN:
                for ch in kare_bol(tid):
                    if (kat, ch) not in gorunen_gorev and _kare_alanla_kesisir(ch, alanlar):
                        gorunen_gorev.add((kat, ch))
                        gorevler.append((kat, ch))
                durum["bolunen"] += 1

    def isci(no):
        ust_uste_hata = 0
        with sync_playwright() as p:
            try:
                tarayici = p.chromium.launch(channel="msedge", headless=not ekranda_goster)
            except Exception:
                tarayici = p.chromium.launch(headless=not ekranda_goster)
            try:
                baglam = tarayici.new_context(locale="tr-TR", viewport={"width": 1400, "height": 1000})
                if HIZLI_YUKLEME:
                    def engelle(rota):
                        try:
                            if rota.request.resource_type in ("image", "media", "font"):
                                rota.abort()
                            else:
                                rota.continue_()
                        except Exception:
                            pass
                    try:
                        baglam.route("**/*", engelle)
                    except Exception:
                        pass
                sayfa = baglam.new_page()
                if PARALEL > 1:
                    time.sleep(random.uniform(0, 2.0))
                sayfa.goto("https://www.google.com/maps?hl=tr", wait_until="domcontentloaded")
                cerez_gec(sayfa)

                if PARALEL > 1:
                    time.sleep(1)
                    if engel_var_mi(sayfa):
                        LOG(f"   ⚠️  Worker {no+1}: Google block detected on homepage!")
                        with kilit:
                            durum["hata"] = ("Google is blocking requests (CAPTCHA). "
                                             "Reduce parallel count to 1 and try again.")
                        return

                while True:
                    if durdur() or durum["hata"]:
                        break
                    with kilit:
                        if not gorevler:
                            bitti = durum["aktif"] == 0
                            gorev = None
                        else:
                            gorev = gorevler.popleft()
                            durum["aktif"] += 1
                    if gorev is None:
                        if bitti:
                            break
                        time.sleep(0.5)
                        continue
                    kat, hedef = gorev
                    if alanlar and isinstance(hedef, tuple) and hedef and hedef[0] == "sabit":
                        yer = hedef[2]
                    else:
                        yer = tile_hucre(*hedef) if alanlar else hedef
                    try:
                        anahtar = _hucre_anahtari(kat, hedef, bool(alanlar))
                        eski = defter.get(anahtar)
                        if anahtar in bitenler:
                            continue
                        if eski and eski.get("bitti"):
                            if devam or (TEKRAR_ONLEME_GUN > 0 and _gun_farki(eski.get("t", "")) <= TEKRAR_ONLEME_GUN):
                                with kilit:
                                    durum["atlanan"] += 1
                                bitenler.add(anahtar)
                                continue
                        if (TEKRAR_ONLEME_GUN > 0 and eski and _gun_farki(eski.get("t", "")) <= TEKRAR_ONLEME_GUN):
                            with kilit:
                                durum["atlanan"] += 1
                            if eski.get("d") and alanlar and not sabit_izgara:
                                bol(kat, hedef)
                            continue
                        with kilit:
                            durum["i"] += 1
                            sira, kalan = durum["i"], len(gorevler)
                        if alanlar:
                            sorgu = kat
                            url = ("https://www.google.com/maps/search/" + urllib.parse.quote_plus(kat)
                                   + f"/@{yer[0]},{yer[1]},{yer[3]}z?hl=tr")
                        else:
                            sorgu = f"{kat} {yer}"
                            url = "https://www.google.com/maps/search/" + sorgu.replace(" ", "+") + "?hl=tr"
                        ilerleme(sira, sira + kalan, f"Searching: {sorgu}  (total {len(tum)} places)")
                        try:
                            kartlar = arama_yap(sayfa, url, yer if alanlar else None, durdur)
                            ust_uste_hata = 0
                        except Exception:
                            ust_uste_hata += 1
                            LOG("   (search failed, skipping)")
                            if not bitenler and ust_uste_hata == 1 and not engel_var_mi(sayfa):
                                try:
                                    sayfa.screenshot(path=f"{DOSYA_TANI}.png")
                                    open(f"{DOSYA_TANI}.html", "w", encoding="utf-8").write(sayfa.content())
                                    LOG(f"WARNING: First search returned no results. Google structure may have changed. "
                                        f"{DOSYA_TANI}.png and {DOSYA_TANI}.html saved.")
                                except Exception:
                                    pass
                            if ust_uste_hata >= 3 and engel_var_mi(sayfa):
                                try:
                                    sayfa.screenshot(path=DOSYA_TARAMA_HATA)
                                except Exception:
                                    pass
                                durum["hata"] = ("Google appears to be blocking requests (CAPTCHA). Data saved; "
                                                 "wait a bit and resume with 'Resume incomplete scan'.")
                            continue
                        doygun = bool(alanlar) and (not sabit_izgara) and doygun_mu(kartlar, yer)
                        with kilit:
                            yeni = 0
                            for k in kartlar:
                                c = tum.get(k["link"])
                                if c is None:
                                    k["_b"] = [kat]
                                    tum[k["link"]] = k
                                    yeni += 1
                                elif kat not in c.setdefault("_b", []):
                                    c["_b"].append(kat)
                            v = verim.setdefault(kat, [0, 0, 0, 0])
                            v[0] += 1
                            v[1] += len(kartlar)
                            v[2] += yeni
                            v[3] = max(v[3], len(kartlar))
                            bitenler.add(anahtar)
                            defter[anahtar] = {"t": bugun, "d": doygun, "bitti": True}
                            if len(bitenler) % ARA_KAYIT_SIKLIGI == 0:
                                kaydet()
                        LOG(f"   -> {len(kartlar)} places, {yeni} new" + ("  [dense: splitting]" if doygun else ""))
                        if doygun:
                            bol(kat, hedef)
                        time.sleep(random.uniform(0.7, 1.5) if HIZLI_KAYDIRMA else 2)
                    finally:
                        with kilit:
                            durum["aktif"] -= 1
            finally:
                try:
                    tarayici.close()
                except Exception:
                    pass

    n_isci = max(1, int(PARALEL))
    try:
        if n_isci == 1:
            isci(0)
        else:
            LOG(f"{n_isci} browsers running in parallel (Google block risk slightly higher).")
            diziler = [threading.Thread(target=isci, args=(i,), daemon=True) for i in range(n_isci)]
            for t in diziler:
                t.start()
            for t in diziler:
                t.join()
    finally:
        with kilit:
            kaydet()
        _json_yaz(DEFTER, defter)

    if durum["atlanan"]:
        LOG(f"{durum['atlanan']} cells skipped (previously scanned).")
    if durum["bolunen"]:
        LOG(f"{durum['bolunen']} dense cells automatically split.")

    tekil = {}
    for k in tum.values():
        b = k.get("_b", [])
        if len(b) == 1:
            tekil[b[0]] = tekil.get(b[0], 0) + 1
    satirlar = [f"{k:<22} search:{v[0]:>3}  found:{v[1]:>5}  new:{v[2]:>5}  max cards:{v[3]:>4}  "
                f"unique to this keyword:{tekil.get(k, 0):>4}" for k, v in verim.items()]
    gereksiz = [k for k, v in verim.items() if v[0] >= YOKLAMA_ESIK_ARAMA and tekil.get(k, 0) == 0]
    if gereksiz:
        satirlar.append("")
        satirlar.append("Keywords that found nothing unique in this scan (can be removed): "
                        + ", ".join(gereksiz))
    try:
        with open(DOSYA_VERIM_RAPOR, "w", encoding="utf-8") as f:
            f.write("\n".join(satirlar))
    except Exception:
        pass
    _kelime_verimi_guncelle(verim, tekil)

    if durum["hata"]:
        raise RuntimeError(durum["hata"])

    for link, k in tum.items():
        havuz_kartlari[link] = {"link": k["link"], "ad": k["ad"], "metin": k["metin"],
                                "yildiz": k["yildiz"], "_g": bugun}
    havuz_kartlari = {l: c for l, c in havuz_kartlari.items() if _gun_farki(c.get("_g", "")) <= 180}
    _json_yaz(HAM_HAVUZ, havuz_kartlari)
    if TEKRAR_ONLEME_GUN > 0:
        for link, c in havuz_kartlari.items():
            if link not in tum and _gun_farki(c.get("_g", "")) <= TEKRAR_ONLEME_GUN:
                tum[link] = c

    if not durdur() and os.path.exists(ara_yolu):
        try:
            os.remove(ara_yolu)
        except Exception:
            pass
    return tum


SINIRLAR = []
MAHALLE_ISTATISTIK = {"sinir": 0, "adres": 0, "internet": 0, "yok": 0}


def _halkalar_olustur(uyeler):
    parcalar = []
    for m in uyeler:
        if m.get("type") == "way" and m.get("role", "outer") in ("outer", "") and m.get("geometry"):
            parcalar.append([(p["lat"], p["lon"]) for p in m["geometry"]])
    halkalar = []
    while parcalar:
        halka = parcalar.pop(0)
        degisti = True
        while halka[0] != halka[-1] and degisti:
            degisti = False
            for i, w in enumerate(parcalar):
                if w[0] == halka[-1]:
                    halka = halka + w[1:]
                elif w[-1] == halka[-1]:
                    halka = halka + w[::-1][1:]
                elif w[-1] == halka[0]:
                    halka = w[:-1] + halka
                elif w[0] == halka[0]:
                    halka = w[::-1][:-1] + halka
                else:
                    continue
                parcalar.pop(i)
                degisti = True
                break
        if len(halka) >= 4 and halka[0] == halka[-1]:
            halkalar.append(halka)
    return halkalar


def _halka_alani(h):
    return abs(sum(h[i][1] * h[i + 1][0] - h[i + 1][1] * h[i][0] for i in range(len(h) - 1))) / 2.0


def _icinde_mi(lat, lon, halka):
    ic = False
    for i in range(len(halka) - 1):
        (y1, x1), (y2, x2) = halka[i], halka[i + 1]
        if (y1 > lat) != (y2 > lat) and lon < (x2 - x1) * (lat - y1) / (y2 - y1) + x1:
            ic = not ic
    return ic


def sinirlari_isle(veri):
    sonuc = []
    for e in veri.get("elements", []):
        etiket = e.get("tags", {})
        ad = etiket.get("name", "")
        if not ad:
            continue
        mahalle_gibi = (
            etiket.get("admin_level") in ("9", "10")
            or "mahalle" in fold(ad)
            or etiket.get("place") in ("suburb", "neighbourhood", "quarter", "village", "hamlet")
        )
        if not mahalle_gibi:
            continue

        if e.get("type") == "relation":
            halkalar = _halkalar_olustur(e.get("members", []))
            if not halkalar:
                continue
            tum_nokta = [p for h in halkalar for p in h]
            kutu = (min(p[0] for p in tum_nokta), min(p[1] for p in tum_nokta),
                    max(p[0] for p in tum_nokta), max(p[1] for p in tum_nokta))
            sonuc.append({"ad": ad, "tip": "poligon", "halkalar": halkalar, "kutu": kutu,
                          "alan": sum(_halka_alani(h) for h in halkalar)})
        elif e.get("type") == "node" and "lat" in e and "lon" in e:
            sonuc.append({"ad": ad, "tip": "nokta", "lat": float(e["lat"]), "lon": float(e["lon"])})
    return sonuc


def _overpass_indir(s, w, n, e):
    sunucular = (
        "https://overpass-api.de/api/interpreter",
        "https://overpass.kumi.systems/api/interpreter",
        "https://overpass.private.coffee/api/interpreter",
    )
    bbox = f"{s:.4f},{w:.4f},{n:.4f},{e:.4f}"
    sorgular = (
        ("mahalle_full", f'[out:json][timeout:25];('
                         f'rel["boundary"="administrative"]["admin_level"="10"]({bbox});'
                         f'node["place"~"^(suburb|neighbourhood|quarter|village)$"]({bbox});'
                         f');out geom;'),
        ("mahalle_node", f'[out:json][timeout:15];'
                         f'node["place"~"^(suburb|neighbourhood|quarter|village)$"]({bbox});'
                         f'out body;'),
    )
    hatalar = []

    for etiket, sorgu in sorgular:
        for sunucu in sunucular:
            try:
                istek = urllib.request.Request(
                    sunucu,
                    data=urllib.parse.urlencode({"data": sorgu}).encode(),
                    headers={"User-Agent": "local-radar/1.1"},
                )
                with urllib.request.urlopen(istek, timeout=20) as r:
                    ham = r.read()
                if not ham:
                    continue
                veri = json.loads(ham.decode("utf-8"))
                eleman = len(veri.get("elements", [])) if isinstance(veri, dict) else 0
                if eleman > 0:
                    LOG(f"   Overpass başarılı ({etiket}, {sunucu}): {eleman} mahalle verisi indi.")
                    return veri, None
            except Exception as ex:
                hatalar.append(f"{sunucu} -> {type(ex).__name__}")

    return None, " | ".join(hatalar) if hatalar else "bilinmeyen hata"


_SINIR_OTURUM_HATA = False


def sinirlari_hazirla(alanlar):
    global SINIRLAR, _SINIR_OTURUM_HATA
    SINIRLAR = []
    for k in MAHALLE_ISTATISTIK:
        MAHALLE_ISTATISTIK[k] = 0
    if not alanlar:
        return 0
    if _SINIR_OTURUM_HATA:
        LOG("   Boundary servers failed earlier in this session; skipping download.")
        return 0
    kuzey = max(a[0] + a[2] / 111.0 for a in alanlar) + 0.01
    guney = min(a[0] - a[2] / 111.0 for a in alanlar) - 0.01
    cosl = max(math.cos(math.radians(alanlar[0][0])), 0.2)
    dogu = max(a[1] + a[2] / (111.0 * cosl) for a in alanlar) + 0.01
    bati = min(a[1] - a[2] / (111.0 * cosl) for a in alanlar) - 0.01

    if (kuzey - guney) > SINIR_MAKS_DERECE or (dogu - bati) > SINIR_MAKS_DERECE:
        LOG("   WARNING: area too large, boundaries not downloaded; falling back to per-query lookup.")
        return 0

    anahtar = f"{guney:.2f},{bati:.2f},{kuzey:.2f},{dogu:.2f}"
    onbellek = _json_oku(SINIR_DOSYASI, {})
    kayit = onbellek.get(anahtar)
    veri = None

    if isinstance(kayit, dict):
        yas = _gun_farki(kayit.get("t", ""))
        if kayit.get("hata") and yas <= SINIR_ONBELLEK_HATA_GUN:
            LOG(f"   Boundary download failed within last {SINIR_ONBELLEK_HATA_GUN} days; skipping retry.")
            return 0
        if kayit.get("veri") is not None and yas <= SINIR_ONBELLEK_BASARILI_GUN:
            veri = kayit.get("veri")

    if veri is None:
        LOG("Downloading neighborhood boundaries (one-time)...")
        veri, hata = _overpass_indir(guney, bati, kuzey, dogu)
        if veri is None:
            onbellek[anahtar] = {
                "t": time.strftime("%Y-%m-%d"),
                "veri": None,
                "hata": True,
                "mesaj": (hata or "")[:240],
            }
            _json_yaz(SINIR_DOSYASI, onbellek)
            LOG(f"   Boundaries failed: {hata} — falling back to per-query.")
            _SINIR_OTURUM_HATA = True
            return 0
        onbellek[anahtar] = {"t": time.strftime("%Y-%m-%d"), "veri": veri, "hata": False}
        _json_yaz(SINIR_DOSYASI, onbellek)

    SINIRLAR = sinirlari_isle(veri)
    LOG(f"   {len(SINIRLAR)} neighborhood boundaries ready." if SINIRLAR else
        "   No neighborhood boundary found; using fallback.")
    return len(SINIRLAR)


def _sinirdan_mahalle(lat, lon):
    en_iyi = None
    for s in SINIRLAR:
        if s.get("tip") != "poligon":
            continue
        k = s["kutu"]
        if not (k[0] <= lat <= k[2] and k[1] <= lon <= k[3]):
            continue
        if any(_icinde_mi(lat, lon, h) for h in s["halkalar"]):
            if en_iyi is None or s["alan"] < en_iyi["alan"]:
                en_iyi = s
    if en_iyi:
        return en_iyi["ad"]

    en_yakin_ad, min_mesafe = None, 1.8
    for s in SINIRLAR:
        if s.get("tip") == "nokta":
            d = mesafe_km((lat, lon), (s["lat"], s["lon"]))
            if d < min_mesafe:
                min_mesafe = d
                en_yakin_ad = s["ad"]
    return en_yakin_ad


def mahalle_bul(adres, lat, lon, onbellek, aktif=True):
    m = MAH_RE.search(adres or "")
    if m:
        MAHALLE_ISTATISTIK["adres"] += 1
        return mahalle_yaz(m.group(1))

    if not aktif or lat is None:
        MAHALLE_ISTATISTIK["yok"] += 1
        return "Bilinmiyor"

    if SINIRLAR:
        ad = _sinirdan_mahalle(lat, lon)
        if ad:
            MAHALLE_ISTATISTIK["sinir"] += 1
            return mahalle_yaz(ad, "suburb")

    parcalar = [p.strip() for p in (adres or "").split(",") if p.strip()]
    if parcalar:
        ilk = parcalar[0]
        yasakli = ("trabzon", "yomra", "ortahisar", "türkiye", "turkey", "no:", "kat:")
        if len(ilk) <= 35 and not any(x in ilk.lower() for x in yasakli):
            MAHALLE_ISTATISTIK["adres"] += 1
            return mahalle_yaz(ilk)

    MAHALLE_ISTATISTIK["yok"] += 1
    return "Bilinmiyor"


def havuz_yukle():
    try:
        return json.load(open(HAVUZ, encoding="utf-8"))
    except Exception:
        return {}


def havuz_birlestir(kayitlar, ayar, tam_tarama=False):
    bugun = time.strftime("%d.%m.%Y")
    havuz = havuz_yukle()
    yeni = guncellenen = 0
    bu_linkler = set()
    for r in kayitlar:
        bu_linkler.add(r["Harita Linki"])
        eski = havuz.get(r["Harita Linki"])
        if eski:
            guncellenen += 1
            r["İlk Görülme"] = eski.get("İlk Görülme", bugun)
            if eski.get("İlçe"):
                r["İlçe"] = eski["İlçe"]
        else:
            yeni += 1
            r["İlk Görülme"] = bugun
        r["Son Görülme"] = bugun
        havuz[r["Harita Linki"]] = r

    with open(HAVUZ, "w", encoding="utf-8") as f:
        json.dump(havuz, f, ensure_ascii=False)

    kayip = 0
    if tam_tarama and ayar.get("ilce"):
        taranan_gruplar = {r.get("Grup") for r in kayitlar}
        kayip = sum(1 for link, v in havuz.items()
                    if v.get("İlçe") == ayar["ilce"] and link not in bu_linkler
                    and v.get("Son Görülme") != bugun
                    and v.get("Grup") in taranan_gruplar)
    return havuz, yeni, guncellenen, kayip


def manuel_mekan_kaydet(veri):
    liste = manuel_mekanlari_oku()
    liste = [m for m in liste if fold(str(m.get("ad", ""))) != fold(veri["ad"])]
    liste.append(veri)
    with open(MANUEL_DOSYASI, "w", encoding="utf-8") as f:
        json.dump(liste, f, ensure_ascii=False, indent=1)
    return len(liste)


def hepsi_yenile(ayar=None):
    if not HEPSI_URET:
        return 0
    ayar = ayar or {}
    hepsi = sorted(havuz_yukle().values(), key=lambda x: -x.get("Güvenilir Skor", 0))
    manuel_ekle(hepsi, ayar, MIN_OY, ilce_filtre=False)
    hepsi = esik_uygula(hepsi, MIN_PUAN, MIN_OY, esikler=KATEGORI_ESIKLERI)
    if not hepsi:
        return 0
    ilceler = sorted({r.get("İlçe", "") for r in hepsi if r.get("İlçe")})
    a2 = dict(ayar, baslik="Local Radar" + (" · " + ", ".join(ilceler) if ilceler else ""))
    csv_yaz(hepsi, DOSYA_HEPSI_CSV, HAVUZ_ALANLAR)
    xlsx_yaz(hepsi, DOSYA_HEPSI_XLSX, HAVUZ_ALANLAR)
    json_yaz(hepsi, DOSYA_HEPSI_JSON, HAVUZ_ALANLAR)
    html_yaz(hepsi, a2, DOSYA_HEPSI_HTML)
    kml_yaz(hepsi, DOSYA_HEPSI_KML)
    return len(hepsi)


# ============================================================
# calistir — Tek HTML çıktısı üretilir
# ============================================================
def calistir(ayar, ilerleme=lambda i, n, m: print(f"[{i}/{n}] {m}"), durdur=lambda: False,
             birlestir=True, min_puan=MIN_PUAN, min_oy=MIN_OY, mahalle_aktif=MAHALLE_BUL,
             ekranda_goster=EKRANDA_GOSTER, ham_kullan=None, devam=False):
    ham_yolu = f"{DOSYA_HAM_PREFIX}{ayar['dosya']}.json"
    if ham_kullan:
        LOG(f"Scan skipped, reading raw data: {ham_kullan}")
        try:
            kartlar = json.load(open(ham_kullan, encoding="utf-8"))
            if isinstance(kartlar, dict):
                kartlar = list(kartlar.get("tum", {}).values())
        except Exception as e:
            raise RuntimeError(f"Raw data could not be read: {e}")
        tum = {k["link"]: k for k in kartlar}
    else:
        tum = tara(ayar, ilerleme, durdur, ekranda_goster, devam)
        if not tum:
            return None
        try:
            os.makedirs(os.path.dirname(ham_yolu) or ".", exist_ok=True)
            with open(ham_yolu, "w", encoding="utf-8") as f:
                json.dump(list(tum.values()), f, ensure_ascii=False)
            LOG(f"Raw data saved: {ham_yolu} (you can re-process without scanning)")
        except Exception:
            pass
    if not tum:
        return None

    LOG("\n📡 Local Radar · Preparing results...")
    kayitlar, puansiz = kayitlari_hazirla(tum.values(), ayar, min_puan, min_oy, mahalle_aktif, durdur=durdur)
    manuel_ekle(kayitlar, ayar, min_oy, ilce_filtre=True)
    kayitlar = esik_uygula(kayitlar, min_puan, min_oy, esikler=KATEGORI_ESIKLERI)

    if tum and puansiz / len(tum) > 0.5:
        LOG("WARNING: More than half of places had unreadable ratings; Google structure may have changed.")

    yeni = guncellenen = kayip = 0
    if birlestir:
        _, yeni, guncellenen, kayip = havuz_birlestir(
            kayitlar, ayar, tam_tarama=bool(ayar.get("tam_tarama")) and not ham_kullan)

    klasor = os.path.join(KLASOR_CIKTILAR, time.strftime("%Y%m%d_%H%M") + "_" + ayar["dosya"])
    os.makedirs(klasor, exist_ok=True)
    slug = ayar["dosya"]
    csv_yolu = os.path.join(klasor, f"{slug}_places.csv")
    xlsx_yolu = os.path.join(klasor, f"{slug}_places.xlsx")
    yemek_sadece = bool(ayar.get("yemek_sadece"))
    alisveris_acik = bool(ayar.get("alisveris_acik", True))
    cikti_adi = slug
    html_yolu = os.path.join(klasor, f"{cikti_adi}.html")
    kml_yolu = os.path.join(klasor, f"{slug}_places.kml")
    json_yolu = os.path.join(klasor, f"{slug}_places.json")

    csv_yaz(kayitlar, csv_yolu, HAVUZ_ALANLAR)
    xlsx_yaz(kayitlar, xlsx_yolu, HAVUZ_ALANLAR)
    json_yaz(kayitlar, json_yolu, HAVUZ_ALANLAR)
    html_yaz(kayitlar, ayar, html_yolu, yemek_sadece=yemek_sadece, alisveris_acik=alisveris_acik)
    kml_yaz(kayitlar, kml_yolu)

    ozet = {"csv": os.path.abspath(csv_yolu), "xlsx": os.path.abspath(xlsx_yolu),
            "json": os.path.abspath(json_yolu), "html": os.path.abspath(html_yolu),
            "html_sade": os.path.abspath(html_yolu),  # Sade butonuna basılırsa da bu tek dosyayı açar
            "kml": os.path.abspath(kml_yolu),
            "ham": os.path.abspath(ham_yolu), "klasor": os.path.abspath(klasor),
            "okunan": len(tum), "puansiz": puansiz, "adet": len(kayitlar),
            "yeni": yeni, "guncellenen": guncellenen, "kayip": kayip}

    if birlestir and HEPSI_URET:
        hepsi = sorted(havuz_yukle().values(), key=lambda x: -x["Güvenilir Skor"])
        manuel_ekle(hepsi, ayar, min_oy, ilce_filtre=False)
        hepsi = esik_uygula(hepsi, min_puan, min_oy, esikler=KATEGORI_ESIKLERI)
        ilceler = sorted({r.get("İlçe", "") for r in hepsi if r.get("İlçe")})
        a2 = dict(ayar, baslik="Local Radar" + (" · " + ", ".join(ilceler) if ilceler else ""))
        csv_yaz(hepsi, DOSYA_HEPSI_CSV, HAVUZ_ALANLAR)
        xlsx_yaz(hepsi, DOSYA_HEPSI_XLSX, HAVUZ_ALANLAR)
        json_yaz(hepsi, DOSYA_HEPSI_JSON, HAVUZ_ALANLAR)
        html_yaz(hepsi, a2, DOSYA_HEPSI_HTML)
        kml_yaz(hepsi, DOSYA_HEPSI_KML)
        ozet.update(hepsi_csv=os.path.abspath(DOSYA_HEPSI_CSV),
                    hepsi_xlsx=os.path.abspath(DOSYA_HEPSI_XLSX),
                    hepsi_json=os.path.abspath(DOSYA_HEPSI_JSON),
                    hepsi_html=os.path.abspath(DOSYA_HEPSI_HTML),
                    hepsi_html_sade=os.path.abspath(DOSYA_HEPSI_HTML),
                    hepsi_kml=os.path.abspath(DOSYA_HEPSI_KML), toplam=len(hepsi))

    return ozet


def main():
    ozet = calistir(YERLER[SECIM])
    if not ozet:
        print("\nNo places were read. Check the messages above.")
        return
    print(f"\n📡 LOCAL RADAR · Scan complete")
    print(f"   {ozet['okunan']} places read. {ozet['adet']} passed filters.")
    print(f"   New: {ozet['yeni']}  |  Updated: {ozet['guncellenen']}  |  No longer visible: {ozet.get('kayip', 0)}")
    print(f"   Scan folder : {ozet['klasor']}")
    if ozet.get('hepsi_html'):
        print(f"   Combined guide ({ozet['toplam']} places): {ozet['hepsi_html']}")


if __name__ == "__main__":
    main()