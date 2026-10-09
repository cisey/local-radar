"""
Local Radar - Core Engine (v1.0.0)
Scrapes Google Maps to find highly-rated places around you.

v1.0.0 updates:
  - All file names moved to English (Local Radar branding)
  - Day planner (G1-G5 tags + day filter)
  - Budget tracker (total, per person, per day)
  - Categorization fixes (Kale Cam, Giyim Çarşısı etc.)
  - Resilient Google selectors (self-healing + multi-fallback)
"""
import re, csv, math, time, json, os, urllib.request, urllib.parse, urllib.error, socket, html

# ======================= SETTINGS =======================
SECIM = "nizip"
MIN_PUAN = 4.0
MIN_OY = 50
EKRANDA_GOSTER = True
MAHALLE_BUL = True
IZGARA_AKTIF = True
SABIT_IZGARA = False
HUCRE_KM = 1.0
MAHALLE_TAKMA_AD = {"Fatih Sultan Mehmet": "Fatih Sultan"}
YENI_GUN = 30
# ========================================================
LOG = print
SURUM = "2026-10-08-v1.0.0-LocalRadar"

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
DOSYA_HEPSI_KML = "local_radar_all.kml"

DOSYA_HAM_PREFIX = "raw_"
DOSYA_ARA_KAYIT_PREFIX = "scan_resume_"

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
    "Normal (yemek ve gezi, ızgaralı)":  dict(kategoriler=YEMEK + GEZI, izgara=True),
    "Kapsamlı (her şey, ızgaralı)":      dict(kategoriler=TUMU, izgara=True),
}

# ---------- Categorization rules (v1.0.0) ----------
KURALLAR = [
    ("Alışveriş", "Giyim, Teknoloji, Mağaza",
     ["kale cam", "kale balkon", "kale kapı", "kale cam balkon",
      "cam balkon", "pvc", "alüminyum doğrama", "doğrama"]),
    ("Alışveriş", "Giyim, Teknoloji, Mağaza",
     ["giyim çarşı", "giyim çarşısı", "giyim mağaza", "ayakkabı çarşı",
      "tekstil çarşı", "kuyumcu çarşı"]),
    ("Diğer", "Diğer hizmetler", ["internet", "halı yıka", "halı temiz"]),
    ("Kebap & Et", "Kebap",
     ["kebap", "kebab", "ciğer", "ciger", "dürüm", "döner", "iskender", "köfteci"]),
    ("Restoran", "Restoran",
     ["restoran", "restaurant", "lokanta", "ev yemek", "balık", "sofra",
      "nohutçu", "kelle paça", "beyran"]),
    ("Hızlı Atıştırmalık", "Hızlı",
     ["pide", "lahmacun", "tost", "börek", "çorba", "=paça", "kelle", "nohut",
      "pizza", "burger", "fast food", "sandviç", "çiğ köf", "tantuni"]),
    ("Tatlı & Pastane", "Tatlı",
     ["baklava", "künefe", "kadayıf", "dondurma", "tatlı", "pastane", "pasta",
      "katmer", "lokum", "helva", "çikolata", "waffle"]),
    ("Kafe & Kahvaltı", "Kafe",
     ["cafe", "kafe", "kahve", "coffee", "=çay", "nargile", "kahvaltı",
      "simit", "bistro"]),
    ("Alışveriş", "Market, Fırın, Kasap",
     ["fıstık", "fırın", "unlu", "ekmek", "market", "migros", "carrefour",
      "=avm", "=bim", "=şok", "=a101", "kasap", "manav", "kuruyemiş",
      "gıda", "pazar", "süpermarket"]),
    ("Alışveriş", "Giyim, Teknoloji, Mağaza",
     ["giyim", "ayakkabı", "teknoloji", "elektronik", "telefon mağaza",
      "bilgisayar", "mağaza", "boyner", "lc waikiki", "defacto",
      "teknosa", "vatan bilgisayar", "kuyumc", "kozmetik", "kırtasiye",
      "kitap", "kitab", "gelinlik", "dükkan"]),
    ("Diğer", "Sağlık ve Bakım",
     ["=diş", "veteriner", "klinik", "hastane", "eczane", "doktor", "hekim",
      "fitness", "spor salonu", "kuaför", "berber", "güzellik"]),
    ("Diğer", "Ulaşım ve Araç",
     ["otopark", "benzin", "petrol", "=shell", "=opet", "=bp", "=oto", "tamir",
      "lastik", "çekici", "vinç", "yol yardım", "araç bakım", "araba yıkama",
      "kurtar", "otogar"]),
    ("Diğer", "Konaklama",
     ["otel", "konaklama", "pansiyon", "apart", "=hostel", "konukevi", "konuk evi"]),
    ("Diğer", "Banka ve ATM",
     ["banka", "=atm", "ziraat", "=garanti", "halkbank", "vakıfbank", "akbank",
      "yapı kredi", "=qnb"]),
    ("Diğer", "Kargo ve Posta",
     ["kargo", "=ptt", "yurtiçi", "=aras", "=mng", "sürat"]),
    ("Diğer", "Evcil Hayvan", ["petshop", "pet shop", "evcil"]),
    ("Diğer", "Çiçekçi", ["çiçek", "flower"]),
    ("Diğer", "Diğer hizmetler", ["düğün", "nikah"]),
    ("Gezilecek yerler", "Camiler", ["cami", "mescit"]),
    ("Gezilecek yerler", "Eğlence ve Sanat",
     ["eğlence", "=oyun", "game center", "sinema", "tiyatro",
      "sanat galeri", "sanat merkezi"]),
    ("Gezilecek yerler", "Gezi ve doğa",
     ["turistik", "antik", "müze", "seyir", "kamp", "millet bahçesi",
      "tarihi", "=kale", "=kalesi", "park", "şelale", "mağara", "ören",
      "plaj", "piknik", "mesire", "hamam", "tarihi çarşı", "bedesten",
      "kapalı çarşı", "kilise", "sinagog", "kervansaray", "mozaik",
      "anıt", "=han", "=hanı"]),
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

ALT_SIRA["Gezilecek yerler"] = ["Gezi ve doğa", "Camiler", "Eğlence ve Sanat"]

VARSAYILAN_ESIKLER = {
    "Kebap & Et": {"puan": 4.0, "oy": 50, "puansiz": False},
    "Restoran": {"puan": 4.0, "oy": 50, "puansiz": False},
    "Hızlı Atıştırmalık": {"puan": 4.0, "oy": 50, "puansiz": False},
    "Tatlı & Pastane": {"puan": 4.0, "oy": 50, "puansiz": False},
    "Kafe & Kahvaltı": {"puan": 4.0, "oy": 50, "puansiz": False},
    "Gezilecek yerler": {"puan": 3.8, "oy": 30, "puansiz": False},
    "Eğlence ve Sanat": {"puan": 3.8, "oy": 30, "puansiz": False},
    "Camiler": {"puan": 3.5, "oy": 10, "puansiz": False},
    "Konaklama": {"puan": 4.0, "oy": 30, "puansiz": False},
    "Market, Fırın, Kasap": {"puan": 3.5, "oy": 10, "puansiz": False},
    "Giyim, Teknoloji, Mağaza": {"puan": 3.5, "oy": 10, "puansiz": False},
    "Sağlık ve Bakım": {"puan": 3.5, "oy": 10, "puansiz": False},
    "Çiçekçi": {"puan": 3.5, "oy": 10, "puansiz": False},
    "Ulaşım ve Araç": {"puan": 3.5, "oy": 10, "puansiz": False},
    "Banka ve ATM": {"puan": 0.0, "oy": 0, "puansiz": True},
    "Kargo ve Posta": {"puan": 0.0, "oy": 0, "puansiz": True},
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
    m = fold(ad + " " + tur)
    kelimeler = set(re.findall(r"[a-z0-9]+", m))
    for bolum, grup, kws in KURALLAR:
        for k in kws:
            if k.startswith("="):
                if k[1:] in kelimeler:
                    return bolum, grup
            else:
                if " " in k:
                    if k in m:
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


GURULTU = re.compile(r"^(acik|kapali|kapanis|acilis|yemek yerinde|paket|kapida|siparis|"
                     r"rezervasyon|gel-al|teslimat|saat)|\(0\d|saati|^[0-9a-z]{4}\+[0-9a-z]{2,}")
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


MAH_RE = re.compile(r"(?:^|,\s*)([^,\d]+?)\s+(?:mahallesi|mahalle|mah\.|mah\b|mh\.)", re.I)


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
    istek = urllib.request.Request(url, headers={"User-Agent": "local-radar/1.0"})
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


def kayitlari_hazirla(kartlar, ayar, min_puan=MIN_PUAN, min_oy=MIN_OY, mahalle_aktif=MAHALLE_BUL):
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
    sari = (PatternFill("solid", fgColor="FFEB9C"), Font(color="9C6500", bold=True))
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


def html_yaz(kayitlar, ayar, yol):
    ogeler = []
    for r in kayitlar:
        ana = ANA.get(r["Bölüm"], "Diğer")
        ogeler.append({"n": r["Yer"], "p": str(r["Puan"]).replace(".", ","), "y": r["Yorum Sayısı"],
                       "u": 1 if r.get("_puansiz") else 0,
                       "s": r["Güvenilir Skor"],
                       "t": r.get("Tür", ""), "a": r.get("Adres", ""), "f": r.get("Fiyat", ""),
                       "m": r.get("Mahalle", "Bilinmiyor"), "c": r.get("İlçe", ""), "l": r["Harita Linki"],
                       "e": r.get("Enlem"), "b": r.get("Boylam"),
                       "w": 1 if _yeni_mi(r.get("İlk Görülme", "")) else 0,
                       "A": ana, "S": r["Bölüm"] if ana == "Yemek" else r["Grup"]})

    veri = {"O": ALT_SIRA, "I": ogeler}
    alt = "Scan, discover, plan. Google Maps results filtered and organized by Local Radar."
    tarih = time.strftime("%d.%m.%Y")

    sayfa = (SABLON.replace("__DATA__", json.dumps(veri, ensure_ascii=False).replace("</", "<\\/"))
             .replace("__BASLIK__", ayar["baslik"])
             .replace("__ALT__", alt)
             .replace("__TARIH__", tarih))

    with open(yol, "w", encoding="utf-8") as f:
        f.write(sayfa)


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
        istek = urllib.request.Request(url, headers={"User-Agent": "local-radar/1.0"})
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


def _json_yaz(yol, veri):
    try:
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
        mahalle_gibi = ("mahalle" in fold(ad) or etiket.get("place") in
                        ("suburb", "neighbourhood", "quarter", "village", "hamlet"))
        if e.get("type") != "relation" or not ad or not mahalle_gibi:
            continue
        halkalar = _halkalar_olustur(e.get("members", []))
        if not halkalar:
            continue
        tum_nokta = [p for h in halkalar for p in h]
        kutu = (min(p[0] for p in tum_nokta), min(p[1] for p in tum_nokta),
                max(p[0] for p in tum_nokta), max(p[1] for p in tum_nokta))
        sonuc.append({"ad": ad, "halkalar": halkalar, "kutu": kutu,
                      "alan": sum(_halka_alani(h) for h in halkalar)})
    return sonuc


def _overpass_indir(s, w, n, e):
    sunucular = (
        "https://overpass-api.de/api/interpreter",
        "https://overpass.kumi.systems/api/interpreter",
        "https://overpass.osm.ch/api/interpreter",
        "https://overpass.private.coffee/api/interpreter",
    )
    sorgular = (
        ("8|9", '[out:json][timeout:60];rel["boundary"="administrative"]["admin_level"~"^(8|9)$"]'
                f'({s:.4f},{w:.4f},{n:.4f},{e:.4f});out geom;'),
        ("8", '[out:json][timeout:60];rel["boundary"="administrative"]["admin_level"="8"]'
              f'({s:.4f},{w:.4f},{n:.4f},{e:.4f});out geom;'),
    )
    hatalar = []

    for etiket, sorgu in sorgular:
        for tur in range(1, 3):
            for sunucu in sunucular:
                try:
                    istek = urllib.request.Request(
                        sunucu,
                        data=urllib.parse.urlencode({"data": sorgu}).encode(),
                        headers={"User-Agent": "local-radar/1.0"},
                    )
                    with urllib.request.urlopen(istek, timeout=28) as r:
                        kod = getattr(r, "status", "?")
                        ham = r.read()
                    if not ham:
                        hatalar.append(f"{etiket} t{tur} {sunucu} -> HTTP {kod} | empty")
                        continue
                    try:
                        veri = json.loads(ham.decode("utf-8"))
                    except Exception as ex:
                        onizleme = ham.decode("utf-8", "ignore")[:220].replace("\n", " ").strip()
                        hatalar.append(f"{etiket} t{tur} {sunucu} -> HTTP {kod} | {type(ex).__name__}: {ex} | {onizleme or 'empty'}")
                        continue

                    eleman = len(veri.get("elements", [])) if isinstance(veri, dict) else 0
                    if eleman > 0:
                        LOG(f"   Overpass success ({etiket}, round {tur}, {sunucu}): {eleman} elements")
                        return veri, None
                    hatalar.append(f"{etiket} t{tur} {sunucu} -> HTTP {kod} | 0 elements")
                except urllib.error.HTTPError as ex:
                    govde = ""
                    try:
                        govde = ex.read().decode("utf-8", "ignore")[:220].replace("\n", " ").strip()
                    except Exception:
                        govde = ""
                    ek = f" | msg={govde}" if govde else " | empty"
                    hatalar.append(f"{etiket} t{tur} {sunucu} -> HTTP {ex.code} | {type(ex).__name__}: {ex}{ek}")
                except urllib.error.URLError as ex:
                    neden = getattr(ex, "reason", ex)
                    hatalar.append(f"{etiket} t{tur} {sunucu} -> URLError | {type(neden).__name__}: {neden}")
                except socket.timeout as ex:
                    hatalar.append(f"{etiket} t{tur} {sunucu} -> timeout | {type(ex).__name__}: {ex}")
                except TimeoutError as ex:
                    hatalar.append(f"{etiket} t{tur} {sunucu} -> timeout | {type(ex).__name__}: {ex}")
                except Exception as ex:
                    hatalar.append(f"{etiket} t{tur} {sunucu} -> {type(ex).__name__}: {ex}")

    return None, " || ".join(hatalar) if hatalar else "reason unknown"


def sinirlari_hazirla(alanlar):
    global SINIRLAR
    SINIRLAR = []
    for k in MAHALLE_ISTATISTIK:
        MAHALLE_ISTATISTIK[k] = 0
    if not alanlar:
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
        k = s["kutu"]
        if not (k[0] <= lat <= k[2] and k[1] <= lon <= k[3]):
            continue
        if any(_icinde_mi(lat, lon, h) for h in s["halkalar"]):
            if en_iyi is None or s["alan"] < en_iyi["alan"]:
                en_iyi = s
    return en_iyi["ad"] if en_iyi else None


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
    anahtar = f"{lat:.3f},{lon:.3f}"
    if anahtar not in onbellek:
        time.sleep(1.1)
        sonuc = nominatim(lat, lon)
        onbellek[anahtar] = sonuc if sonuc else [None, None]
        try:
            with open(ONBELLEK_DOSYASI, "w", encoding="utf-8") as f:
                json.dump(onbellek, f, ensure_ascii=False)
        except Exception:
            pass
    ad, tur = onbellek[anahtar]
    if not ad:
        MAHALLE_ISTATISTIK["yok"] += 1
        return "Bilinmiyor"
    MAHALLE_ISTATISTIK["internet"] += 1
    return mahalle_yaz(ad, tur)


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
            with open(ham_yolu, "w", encoding="utf-8") as f:
                json.dump(list(tum.values()), f, ensure_ascii=False)
            LOG(f"Raw data saved: {ham_yolu} (you can re-process without scanning)")
        except Exception:
            pass
    if not tum:
        return None

    LOG("\n📡 Local Radar · Preparing results...")
    kayitlar, puansiz = kayitlari_hazirla(tum.values(), ayar, min_puan, min_oy, mahalle_aktif)
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
    html_yolu = os.path.join(klasor, f"{slug}_guide.html")
    kml_yolu = os.path.join(klasor, f"{slug}_places.kml")
    csv_yaz(kayitlar, csv_yolu, HAVUZ_ALANLAR)
    xlsx_yaz(kayitlar, xlsx_yolu, HAVUZ_ALANLAR)
    json_yolu = os.path.join(klasor, f"{slug}_places.json")
    html_yaz(kayitlar, ayar, html_yolu)
    json_yaz(kayitlar, json_yolu, HAVUZ_ALANLAR)
    kml_yaz(kayitlar, kml_yolu)

    ozet = {"csv": os.path.abspath(csv_yolu), "xlsx": os.path.abspath(xlsx_yolu),
            "json": os.path.abspath(json_yolu), "html": os.path.abspath(html_yolu), "kml": os.path.abspath(kml_yolu),
            "ham": os.path.abspath(ham_yolu), "klasor": os.path.abspath(klasor),
            "okunan": len(tum), "puansiz": puansiz, "adet": len(kayitlar),
            "yeni": yeni, "guncellenen": guncellenen, "kayip": kayip}

    if birlestir:
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
    print(f"   Combined guide ({ozet['toplam']} places): {ozet['hepsi_html']}")


SABLON = r"""<!DOCTYPE html>
<html lang="tr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>__BASLIK__</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<style>
:root{--bg:#f8f9fa;--card:#fff;--ink:#202124;--mut:#5f6368;--line:#dadce0;--primary:#1a73e8;--primarybg:#e8f0fe;--gold:#f29900;--yesil:#0b8043}
@media (prefers-color-scheme:dark){:root{--bg:#202124;--card:#2d2e31;--ink:#e8eaed;--mut:#9aa0a6;--line:#3c4043;--primary:#8ab4f8;--primarybg:#303134;--gold:#fbbc04;--yesil:#81c995}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font-family:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;line-height:1.4;padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}
.wrap{max-width:640px;margin:0 auto;padding:20px 16px 48px}
h1{font-size:28px;font-weight:800;margin:8px 0 4px;letter-spacing:-.02em}
.sub{color:var(--mut);font-size:14px;margin:0 0 12px}
.tabs{display:flex;gap:8px;flex-wrap:wrap;position:sticky;top:0;background:var(--bg);padding:10px 0;z-index:500}
.tabs button{flex:0 0 auto;border:1px solid var(--line);background:var(--card);color:var(--ink);font:inherit;font-weight:600;padding:9px 16px;border-radius:99px;cursor:pointer}
.tabs button[aria-selected="true"]{background:var(--primary);border-color:var(--primary);color:#fff}
.chips{display:flex;gap:6px;flex-wrap:wrap;padding:2px 0 10px}
.chips button{flex:0 0 auto;border:1px solid var(--line);background:transparent;color:var(--mut);font:inherit;font-size:13px;padding:5px 12px;border-radius:99px;cursor:pointer}
.chips button[aria-pressed="true"]{background:var(--primarybg);border-color:var(--primary);color:var(--primary);font-weight:600}
@media (prefers-color-scheme:dark){.tabs button[aria-selected="true"]{color:#202124}}
input,select{width:100%;font:inherit;padding:11px 14px;border:1px solid var(--line);border-radius:12px;background:var(--card);color:var(--ink);margin:6px 0 4px}
input:focus,select:focus{outline:2px solid var(--primary);border-color:transparent}
.f-row{display:flex;gap:12px;margin:8px 0 4px}
.f-row div{flex:1}
.f-row label{display:block;font-size:12px;color:var(--mut);margin:0 0 4px 4px;font-weight:600}
h2{font-size:16px;margin:22px 0 8px;font-weight:700;color:var(--primary);border-bottom:1px solid var(--line);padding-bottom:4px}
.row{display:flex;gap:12px;align-items:flex-start;background:var(--card);border-bottom:1px solid var(--line);padding:12px}
.row:first-of-type{border-radius:14px 14px 0 0}.row:last-child{border-radius:0 0 14px 14px;border-bottom:0}.row:only-child{border-radius:14px}
.pt{flex:0 0 46px;text-align:center;background:var(--primarybg);border-radius:10px;padding:6px 0}
.pt b{display:block;font-size:18px;color:var(--primary)}.pt small{font-size:11px;color:var(--mut)}
.body{flex:1;min-width:0}
.nm{font-weight:600;font-size:16px;overflow-wrap:anywhere}
.meta{font-size:13px;color:var(--mut);margin-top:2px;overflow-wrap:anywhere}
.mah{font-size:13px;color:var(--primary);font-weight:600;margin-top:2px}
.fy{color:var(--gold);font-weight:600}
a.go{display:inline-block;margin-top:8px;font-size:13px;font-weight:600;color:var(--primary);text-decoration:none;border:1px solid var(--line);padding:5px 12px;border-radius:99px}
.ikon{border:1px solid var(--line);background:transparent;color:var(--ink);border-radius:99px;padding:5px 10px;font:inherit;font-size:13px;margin-left:6px;cursor:pointer}
.ikon:hover{background:var(--primarybg)}
.foot{color:var(--mut);font-size:12px;margin-top:28px}
.none{color:var(--mut);padding:24px 0}
#map{display:none;height:68vh;border-radius:14px;border:1px solid var(--line);margin-top:8px}
.leaflet-popup-content{font-family:inherit;font-size:14px}

.gun-btn{border:1px solid var(--line);background:transparent;color:var(--mut);border-radius:99px;padding:3px 8px;font-size:11px;margin-left:3px;cursor:pointer;font-weight:600}
.gun-btn:hover{background:var(--primarybg)}
.gun-btn[data-secili="true"]{background:var(--primary);color:#fff;border-color:var(--primary)}
.gun-filtre{display:flex;gap:6px;flex-wrap:wrap;margin:8px 0 12px 0}
.gun-filtre button{border:1px solid var(--line);background:var(--card);color:var(--ink);padding:6px 14px;border-radius:99px;font-size:13px;cursor:pointer;font-weight:600}
.gun-filtre button[aria-pressed="true"]{background:var(--primary);color:#fff;border-color:var(--primary)}

.butce-panel{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:14px 16px;margin:12px 0;display:grid;grid-template-columns:repeat(auto-fit,minmax(90px,1fr));gap:14px}
.butce-panel .item{display:flex;flex-direction:column;gap:2px}
.butce-panel .etiket{font-size:11px;color:var(--mut);text-transform:uppercase;font-weight:600;letter-spacing:.03em}
.butce-panel .deger{font-size:18px;font-weight:700;color:var(--primary)}
.butce-panel .deger.yesil{color:var(--yesil)}
.butce-panel input[type="number"]{width:100%;padding:5px 8px;font-size:14px;margin:0;border-radius:8px}
.fiyat-input{border:1px solid var(--line);background:var(--card);color:var(--ink);border-radius:6px;padding:3px 6px;font-size:12px;width:72px;margin-left:4px}
.fiyat-input:focus{outline:2px solid var(--primary);border-color:transparent}
.fiyat-input::placeholder{color:var(--mut);opacity:.6}

@media (max-width:680px){
  .wrap{padding:14px 10px 24px}
  h1{font-size:24px}
  .f-row{flex-direction:column;gap:8px}
  .f-row > div{width:100%}
  .tabs button{padding:8px 12px;font-size:14px}
  .chips button{font-size:12px}
  .row{padding:10px}
  #map{height:50vh}
  .butce-panel{padding:10px;gap:10px}
  .butce-panel .deger{font-size:16px}
  .fiyat-input{width:60px}
}
</style>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
</head><body><div class="wrap">

<h1>📡 __BASLIK__</h1>
<p class="sub" style="margin-bottom: 4px;">__ALT__</p>
<div style="font-size: 13px; font-weight: 600; color: var(--primary); margin-bottom: 16px;">📅 __TARIH__</div>

<div class="f-row" style="margin-bottom: 8px;">
  <button class="ikon" style="margin-left:0" onclick="rotaAc()">Rotada Aç</button>
  <button class="ikon" onclick="wpListe()">WP'ye Gönder</button>
  <button class="ikon" onclick="konumAl(draw)">📍 Konum Bul</button>
  <button class="ikon" onclick="tumVerileriTemizle()" style="color:#c00">🗑️ Sıfırla</button>
</div>

<select id="ic" aria-label="İlçe"></select>
<div style="margin-bottom: 4px;">
<input id="mq" type="search" placeholder="📍 Hızlı Mahalle Ara (Örn: Çarşı, Karataş)">
</div>
<select id="mh" aria-label="Mahalle"></select>
<div class="f-row">
  <div><label for="mp">En az puan</label><input id="mp" type="number" step="0.1" placeholder="örn. 4.5"></div>
  <div><label for="my">En az yorum</label><input id="my" type="number" step="10" placeholder="örn. 200"></div>
</div>
<input id="q" type="search" placeholder="Listede kelime ara (örn. pide, kebap)">
<div class="f-row">
  <select id="sirala" aria-label="Sıralama" style="flex:2">
    <option value="skor">Sıralama: Güvenilir skor</option>
    <option value="puan">Sıralama: Puan (yüksekten)</option>
    <option value="yorum">Sıralama: Yorum sayısı (çoktan)</option>
    <option value="yakin">Sıralama: Bana yakın</option>
  </select>
  <select id="gs" style="flex:1">
    <option value="">Hepsi</option>
    <option value="fav">Favoriler</option>
    <option value="gitmedi">Gitmediklerim</option>
    <option value="gunlu">Gün Atanmış</option>
  </select>
</div>

<div class="butce-panel" id="butcePanel">
  <div class="item">
    <span class="etiket">Toplam</span>
    <span class="deger" id="butceToplam">0 ₺</span>
  </div>
  <div class="item">
    <span class="etiket">Kişi Sayısı</span>
    <input type="number" id="kisiSayisi" min="1" value="1" step="1">
  </div>
  <div class="item">
    <span class="etiket">Kişi Başı</span>
    <span class="deger yesil" id="butceKisiBasi">0 ₺</span>
  </div>
  <div class="item">
    <span class="etiket">Gün 1</span>
    <span class="deger" id="butceGun1">0 ₺</span>
  </div>
  <div class="item">
    <span class="etiket">Gün 2</span>
    <span class="deger" id="butceGun2">0 ₺</span>
  </div>
  <div class="item">
    <span class="etiket">Gün 3</span>
    <span class="deger" id="butceGun3">0 ₺</span>
  </div>
</div>

<div class="tabs" id="tabs" role="tablist"></div>

<div class="gun-filtre" id="gunFiltre"></div>

<div class="chips" id="chips"></div>
<div id="map"></div>
<div id="list"></div>
<p class="foot"><b>📡 Local Radar</b> · Data source: Google Maps. Ratings reflect the day the guide was created. Verify opening hours before visiting. Map: © OpenStreetMap contributors.</p>
</div>
<script>
const V=__DATA__,O=V.O,I=V.I,ANA=Object.keys(O);let ana='',alt='',map=null,katman=null;
const HARITA='__MAP__';
const RENK={'Yemek':'#e8710a','Gezilecek yerler':'#1a73e8','Alışveriş':'#0b8043','Diğer':'#5f6368'};
const $=id=>document.getElementById(id);
const tabs=$('tabs'),chips=$('chips'),list=$('list'),q=$('q'),mh=$('mh'),mq=$('mq'),ic=$('ic'),mp=$('mp'),my=$('my'),sirala=$('sirala'),gs=$('gs'),mapEl=$('map');
const esc=s=>String(s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const tl=s=>String(s).toLocaleLowerCase('tr');

function durumOku(){try{return JSON.parse(localStorage.getItem('gezi_durum')||'{}')}catch(e){return {}}}
function durumYaz(){try{localStorage.setItem('gezi_durum',JSON.stringify(durum))}catch(e){}}
let durum=durumOku();
let konum=null;

const GUNLER=[1,2,3,4,5];
let aktifGun='';
function gunDurumOku(){try{return JSON.parse(localStorage.getItem('gezi_gun_durum')||'{}')}catch(e){return {}}}
function gunDurumYaz(){try{localStorage.setItem('gezi_gun_durum',JSON.stringify(gunDurum))}catch(e){}}
let gunDurum=gunDurumOku();

function fiyatDurumOku(){try{return JSON.parse(localStorage.getItem('gezi_fiyat_durum')||'{}')}catch(e){return {}}}
function fiyatDurumYaz(){
  try{
    localStorage.setItem('gezi_fiyat_durum',JSON.stringify(fiyatDurum));
    localStorage.setItem('gezi_kisi_sayisi',document.getElementById('kisiSayisi').value);
  }catch(e){}
}
let fiyatDurum=fiyatDurumOku();

function km(a,b,c,d){const t=x=>x*Math.PI/180,R=6371,dl=t(c-a),dg=t(d-b);
  const h=Math.sin(dl/2)**2+Math.cos(t(a))*Math.cos(t(c))*Math.sin(dg/2)**2;return 2*R*Math.asin(Math.sqrt(h));}
function uzak(x){return(konum&&x.e!=null)?km(konum.lat,konum.lon,x.e,x.b):null}

function konumAl(sonra){
  if(!navigator.geolocation){alert('Bu tarayıcı konum vermiyor');return;}
  navigator.geolocation.getCurrentPosition(
    p=>{konum={lat:p.coords.latitude,lon:p.coords.longitude};if(sonra)sonra();},
    ()=>alert('Konum alınamadı. Tarayıcıda konum iznini aç.'),
    {enableHighAccuracy:true,timeout:10000});
}

const ilceler=[...new Set(I.map(x=>x.c).filter(Boolean))].sort((a,b)=>a.localeCompare(b,'tr'));
if(ilceler.length>=2)ic.innerHTML='<option value="">Tüm ilçeler</option>'+ilceler.map(c=>`<option value="${esc(c)}">${esc(c)}</option>`).join('');
else ic.style.display='none';

const mahSayisi=new Set(I.filter(x=>x.m!=='Bilinmiyor').map(x=>x.c+'|'+x.m)).size;
if(mahSayisi<2){mh.style.display='none';mq.style.display='none'}

function mahalleListe(){
  if(mahSayisi<2)return;
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
  const gunKosul=(aktifGun==='')||(gunDurum[x.l]==aktifGun);
  return (!ic.value||x.c===ic.value)&&(!mh.value||(x.c+'|'+x.m)===mh.value)&&
    (!t||tl(x.n+' '+x.t).includes(t))&&parseFloat(x.p.replace(',','.'))>=p0&&x.y>=y0&&
    (gs.value===''||(gs.value==='fav'&&(durum[x.l]||{}).fav)||(gs.value==='gitmedi'&&!(durum[x.l]||{}).gitti)||(gs.value==='gunlu'&&gunDurum[x.l]))&&
    gunKosul;
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
    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:19,attribution:'© OpenStreetMap katkıcıları'}).addTo(map);
  }
  setTimeout(()=>map.invalidateSize(),60);
  if(katman)map.removeLayer(katman);
  const pts=I.filter(x=>ok(x)&&typeof x.e==='number'&&typeof x.b==='number');
  const isaretler=pts.map(x=>L.circleMarker([x.e,x.b],{radius:7,weight:2,color:'#fff',fillColor:RENK[x.A]||'#5f6368',fillOpacity:.9})
    .bindPopup('<b>'+esc(x.n)+'</b><br>⭐ '+esc(x.p)+' · '+x.y+' yorum<br>'+esc(x.m!=='Bilinmiyor'?x.m:'')+
      '<br><a href="'+esc(x.l)+'" target="_blank" rel="noopener">Google Haritalar\u2019da aç</a>'));
  katman=L.featureGroup(isaretler).addTo(map);
  if(pts.length)map.fitBounds(katman.getBounds().pad(0.15));
  else map.setView([38.96,35.24],6);
}

function gunButonlariHTML(l){
  const seciliGun=gunDurum[l]||null;
  let html='';
  GUNLER.forEach(g=>{
    html+=`<button class="gun-btn" data-l="${esc(l)}" data-gun="${g}" data-secili="${seciliGun===g}">G${g}</button>`;
  });
  return html;
}

function gunFiltreOlustur(){
  const kap=document.getElementById('gunFiltre');
  if(!kap)return;
  let html=`<button data-gun="" aria-pressed="${aktifGun===''}">Tümü</button>`;
  GUNLER.forEach(g=>{
    html+=`<button data-gun="${g}" aria-pressed="${aktifGun===String(g)}">Gün ${g}</button>`;
  });
  kap.innerHTML=html;
}

function satir(x){
  const meta=[esc(x.t),x.f?'<span class="fy">'+esc(x.f)+'</span>':'',esc(x.a)].filter(Boolean).join(' · ');
  const dist=uzak(x)!=null?'<div class="mah">'+uzak(x).toFixed(1).replace('.',',')+' km</div>':'';
  const fDurum=durum[x.l]||{};
  const nBtn=fDurum.not?'<div class="meta">📝 '+esc(fDurum.not)+'</div>':'';
  const puanKutusu=x.u?'<b style="font-size:13px">puansız</b><small>—</small>':`<b>${x.p}</b><small>${x.y}</small>`;
  const fiyatDeger=fiyatDurum[x.l]||'';
  return `<div class="row"><div class="pt">${puanKutusu}</div><div class="body"><div class="nm">${esc(x.n)}</div>`+
    (meta?`<div class="meta">${meta}</div>`:'')+(x.m!=='Bilinmiyor'?`<div class="mah">${esc(x.m)}${(ilceler.length>=2&&x.c)?' · '+esc(x.c):''}</div>`:'')+dist+
    `<div style="margin-top:8px;display:flex;flex-wrap:wrap;align-items:center;gap:4px;">
      <a class="go" href="${esc(x.l)}" target="_blank" rel="noopener">Haritada aç</a>
      <button class="ikon" data-t="fav" data-l="${esc(x.l)}">${fDurum.fav?'★':'☆'}</button>
      <button class="ikon" data-t="gitti" data-l="${esc(x.l)}">${fDurum.gitti?'✓ Gittik':'Gittik mi?'}</button>
      <button class="ikon" data-t="not" data-l="${esc(x.l)}">📝</button>
      <span style="font-size:11px;color:var(--mut);margin-left:6px;">Gün:</span>
      ${gunButonlariHTML(x.l)}
      <input type="number" class="fiyat-input" placeholder="₺" value="${fiyatDeger}" data-fiyat-l="${esc(x.l)}" min="0" step="10" title="Tahmini harcama (₺)">
    </div>${nBtn}</div></div>`;
}

function rotaAc(){
  const d=I.filter(x=>(durum[x.l]||{}).fav&&x.e!=null);
  if(!d.length){alert('Önce yerleri ★ ile işaretle (ve konumları belli olmalı)');return;}
  const son=d[d.length-1], ara=d.slice(0,-1).map(x=>x.e+','+x.b).join('|');
  let url='https://www.google.com/maps/dir/?api=1&destination='+son.e+','+son.b+'&travelmode=driving';
  if(ara) url+='&waypoints='+encodeURIComponent(ara);
  window.open(url,'_blank');
}

function wpListe(){
  const l=I.filter(ok).slice(0,10).filter(x=>x.e!=null);
  if(!l.length){alert('Listede konumlu yer yok');return;}
  const t=l.map((x,i)=>`${i+1}. ${x.n} (${x.p}★, ${x.y} yorum)${x.m!=='Bilinmiyor'?' - '+x.m:''}\nhttps://maps.google.com/?q=${x.e},${x.b}`).join('\n\n');
  window.open('https://wa.me/?text='+encodeURIComponent(t),'_blank');
}

function tumVerileriTemizle(){
  if(!confirm('Tüm favoriler, günler, fiyatlar ve notlar silinecek. Emin misin?'))return;
  localStorage.removeItem('gezi_durum');
  localStorage.removeItem('gezi_gun_durum');
  localStorage.removeItem('gezi_fiyat_durum');
  localStorage.removeItem('gezi_kisi_sayisi');
  durum={};gunDurum={};fiyatDurum={};
  document.getElementById('kisiSayisi').value=1;
  draw();
  butceGuncelle();
}

function tlFormat(sayi){
  if(!sayi||isNaN(sayi))return '0 ₺';
  return Math.round(sayi).toLocaleString('tr-TR')+' ₺';
}

function butceGuncelle(){
  let toplam=0;
  const gunToplamlari={1:0,2:0,3:0,4:0,5:0};
  Object.keys(fiyatDurum).forEach(l=>{
    const fiyat=parseFloat(fiyatDurum[l])||0;
    if(fiyat>0){
      toplam+=fiyat;
      const gun=gunDurum[l];
      if(gun&&gunToplamlari[gun]!==undefined)gunToplamlari[gun]+=fiyat;
    }
  });
  const kisiSayisi=parseInt(document.getElementById('kisiSayisi').value)||1;
  const kisiBasi=kisiSayisi>0?toplam/kisiSayisi:toplam;
  document.getElementById('butceToplam').textContent=tlFormat(toplam);
  document.getElementById('butceKisiBasi').textContent=tlFormat(kisiBasi);
  document.getElementById('butceGun1').textContent=tlFormat(gunToplamlari[1]);
  document.getElementById('butceGun2').textContent=tlFormat(gunToplamlari[2]);
  document.getElementById('butceGun3').textContent=tlFormat(gunToplamlari[3]);
}

document.getElementById('gunFiltre').addEventListener('click',e=>{
  const b=e.target.closest('button');
  if(!b)return;
  aktifGun=b.dataset.gun||'';
  gunFiltreOlustur();
  draw();
});

list.addEventListener('click',e=>{
  const gunBtn=e.target.closest('.gun-btn');
  if(gunBtn){
    const l=gunBtn.dataset.l;
    const g=parseInt(gunBtn.dataset.gun);
    if(gunDurum[l]===g){delete gunDurum[l];}
    else{gunDurum[l]=g;}
    gunDurumYaz();
    butceGuncelle();
    draw();
    return;
  }
  const b=e.target.closest('.ikon'); if(!b) return;
  const l=b.dataset.l; if(!l) return;
  durum[l]=durum[l]||{};
  if(b.dataset.t==='fav') durum[l].fav=!durum[l].fav;
  else if(b.dataset.t==='gitti') durum[l].gitti=!durum[l].gitti;
  else if(b.dataset.t==='not'){ const n=prompt('Not:',durum[l].not||''); if(n!==null) durum[l].not=n; }
  durumYaz(); draw();
});

document.addEventListener('input',e=>{
  const inp=e.target.closest('.fiyat-input');
  if(!inp)return;
  const l=inp.dataset.fiyatL;
  const deger=inp.value.trim();
  if(deger===''){delete fiyatDurum[l];}
  else{fiyatDurum[l]=parseFloat(deger)||0;}
  fiyatDurumYaz();
  butceGuncelle();
});

document.getElementById('kisiSayisi').addEventListener('input',()=>{
  fiyatDurumYaz();
  butceGuncelle();
});

function draw(){
  if(ana===HARITA){haritaCiz();}
  else{mapEl.style.display='none';list.style.display='';}
  const f=I.filter(ok),arama=q.value.trim()!=='';
  const cnt={};f.forEach(x=>{cnt[x.A]=(cnt[x.A]||0)+1});
  tabs.innerHTML=`<button role="tab" aria-selected="${ana===''}" data-a="">Tümü (${f.length})</button>`+
    ANA.map(a=>`<button role="tab" aria-selected="${ana===a}" data-a="${esc(a)}">${esc(a)} (${cnt[a]||0})</button>`).join('')+
    `<button role="tab" aria-selected="${ana===HARITA}" data-a="${HARITA}">🗺️ Harita</button>`;

  if(ana&&ana!==HARITA){
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
  list.innerHTML=out||'<p class="none">Sonuç yok. Süzgeçleri gevşetmeyi dene.</p>';
}

tabs.onclick=e=>{const b=e.target.closest('button');if(b){ana=b.dataset.a;alt='';draw();scrollTo(0,0)}};
chips.onclick=e=>{const b=e.target.closest('button');if(b){alt=b.dataset.s;draw()}};
ic.onchange=()=>{mahalleListe();draw()};
mq.oninput=()=>{mahalleListe();draw()};
mh.onchange=draw;
mp.oninput=draw;
my.oninput=draw;
q.oninput=draw;
gs.onchange=draw;
sirala.onchange=draw;

try{
  const kisi=localStorage.getItem('gezi_kisi_sayisi');
  if(kisi)document.getElementById('kisiSayisi').value=kisi;
}catch(e){}

mahalleListe();
gunFiltreOlustur();
draw();
butceGuncelle();
</script></body></html>
"""


if __name__ == "__main__":
    main()