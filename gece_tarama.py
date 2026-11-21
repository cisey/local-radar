"""
Local Radar - Gece Taraması (sıralı ilçe kuyruğu)

local_radar_core.py ile AYNI klasöre koy, çift tıklayıp çalıştır.
- gece_ilceler.txt içindeki ilçeleri sırayla tarar (her biri ayrı HTML).
- Her ilçe bitince HTML'yi GitHub'daki local-radar-output deposuna yükler.
- Kategori / puan / yorum ayarlarını Local Radar penceresinde en son
  kullandığın ayarlardan (settings.json) alır.
- Biten ilçeler gece_durum.json'a yazılır; tekrar çalıştırınca atlanır.
  Bir ilçeyi yeniden taratmak istersen adını gece_durum.json içinden sil.
- Her şey gece_log.txt dosyasına yazılır.
"""
import os, sys, re, json, time, shutil, subprocess, traceback, datetime
import urllib.request, urllib.parse, urllib.error

KLASOR = os.path.dirname(os.path.abspath(__file__))
os.chdir(KLASOR)
sys.path.insert(0, KLASOR)

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import local_radar_core as g

# ======================= AYARLAR =======================
ILCE_DOSYASI = "gece_ilceler.txt"
DURUM_DOSYASI = "gece_durum.json"
LOG_DOSYASI = "gece_log.txt"
VARSAYILAN_IL = "İstanbul"          # listede "İl/İlçe" yazılmamışsa kullanılır
BITIS_SAATI = None                   # None = sınırsız çalışır. Sabah durması için saat yaz (ör. 8)
EKRANDA_GOSTER = True                # tarayıcı penceresi açık çalışsın (Google engelini azaltır)
MIN_YARICAP_KM = 2.0                 # çok küçük ilçelerde en az bu yarıçap
PARALEL_SAYISI = 1                   # Aynı anda kaç tarayıcı penceresi çalışsın (1 = tek pencere, 2 = iki kat hızlı, 3 = daha riskli)
GERCEK_ILCE_ATA = True               # il rehberlerinde ilçeyi koordinattan bul (ayarlar.json: gercek_ilce_ata)
TEKRAR_ONLEME_GUN = 60               # Bu kadar gün içinde taranmış arama karelerini tekrar arama (0 = kapalı)
ENGEL_BEKLEME_DAKIKA = [30, 60]      # Google engellerse bu kadar bekleyip devam eder
GITHUB_DEPO = ""                                           # sitenin deposu; ayarlar.json içinden gelir
DEPO_KLASORU = os.path.join(KLASOR, "LocalRadar")          # bilgisayarda indirileceği klasör
DEPO_ALT_KLASOR = "rehberler"                              # HTML'lerin duracağı klasör (depo içinde)
# =======================================================

ISTANBUL = ["Adalar", "Arnavutköy", "Ataşehir", "Avcılar", "Bağcılar", "Bahçelievler", "Bakırköy",
            "Başakşehir", "Bayrampaşa", "Beşiktaş", "Beykoz", "Beylikdüzü", "Beyoğlu", "Büyükçekmece",
            "Çatalca", "Çekmeköy", "Esenler", "Esenyurt", "Eyüpsultan", "Fatih", "Gaziosmanpaşa",
            "Güngören", "Kadıköy", "Kağıthane", "Kartal", "Küçükçekmece", "Maltepe", "Pendik",
            "Sancaktepe", "Sarıyer", "Silivri", "Sultanbeyli", "Sultangazi", "Şile", "Şişli", "Tuzla",
            "Ümraniye", "Üsküdar", "Zeytinburnu"]


HEPSI_SONUNDA_YENILE = False   # kuyruk bitince "HEPSİ" dosyaları (local_radar_all.*) bir kere yenilenir
_HEPSI_ERTELE = {"acik": False}


def hepsi_ertele_kur():
    """Her ilçeden sonra bütün havuzu (onbinlerce yer) yeniden CSV/XLSX/HTML yazmak
    ilçe başına 25-30 dakika kaybettiriyordu. Gece boyunca bu yazımı atlıyoruz;
    havuz (pool.json) yine güncelleniyor, HEPSİ dosyaları en sonda bir kere yazılıyor."""
    hepsi = {g.DOSYA_HEPSI_CSV, g.DOSYA_HEPSI_XLSX, g.DOSYA_HEPSI_JSON,
             g.DOSYA_HEPSI_HTML, g.DOSYA_HEPSI_KML}

    def sarmala(orj, yol_sirasi):
        def f(*a, **k):
            yol = a[yol_sirasi] if len(a) > yol_sirasi else k.get("yol")
            if _HEPSI_ERTELE["acik"] and yol in hepsi:
                return None
            return orj(*a, **k)
        return f

    g.csv_yaz = sarmala(g.csv_yaz, 1)
    g.xlsx_yaz = sarmala(g.xlsx_yaz, 1)
    g.json_yaz = sarmala(g.json_yaz, 1)
    g.kml_yaz = sarmala(g.kml_yaz, 1)
    g.html_yaz = sarmala(g.html_yaz, 2)
    _HEPSI_ERTELE["acik"] = True


def log(m):
    satir =f"[{datetime.datetime.now():%d.%m %H:%M:%S}] {m}"
    try:
        print(satir, flush=True)
    except Exception:
        pass
    try:
        with open(LOG_DOSYASI, "a", encoding="utf-8") as f:
            f.write(satir + "\n")
    except Exception:
        pass


# ---------- Telegram bildirimi ----------
TELEGRAM_DOSYASI = "telegram_ayar.json"          # {"token": "...", "chat_id": "..."}  (aynı klasörde)
GA_KODU = ""        # Google Analytics ölçüm kimliği (ayarlar.json'dan)
SITE_ADRESI = ""    # sitenin adresi (ayarlar.json'dan)


# ---------- Kişisel ayarlar (ayarlar.json) ----------
# Bu dosya sana özeldir, GitHub'a yüklenmez. Yoksa şablondan oluşturulur.
AYAR_DOSYASI = "ayarlar.json"
_AYAR_VARSAYILAN = {
    "github_depo": "",            # örn. https://github.com/KULLANICI/DEPO.git
    "depo_alt_klasor": "rehberler",
    "site_adresi": "",            # örn. https://KULLANICI.github.io/DEPO
    "ga_kodu": "",                # Google Analytics ölçüm kimliği (boşsa eklenmez)
    "varsayilan_il": "İstanbul",
    "bitis_saati": None,
    "ekranda_goster": True,
    "paralel_sayisi": 1,
    "gercek_ilce_ata": True,       # il rehberlerinde mekanın ilçesini koordinattan bul (shapely gerekir)
    "tekrar_onleme_gun": 60,      # 0 yaparsan daha önce taranmış kareler de yeniden taranır
}


def _ayarlari_yukle():
    global GITHUB_DEPO, DEPO_ALT_KLASOR, SITE_ADRESI, GA_KODU, VARSAYILAN_IL
    global BITIS_SAATI, EKRANDA_GOSTER, PARALEL_SAYISI, DEPO_KLASORU, TEKRAR_ONLEME_GUN, GERCEK_ILCE_ATA
    if not os.path.exists(AYAR_DOSYASI):
        try:
            with open(AYAR_DOSYASI, "w", encoding="utf-8") as f:
                json.dump(_AYAR_VARSAYILAN, f, ensure_ascii=False, indent=2)
            print(f"{AYAR_DOSYASI} bulunamadı, boş şablon oluşturuldu. GitHub/site bilgilerini oraya yaz.")
        except Exception:
            pass
        d = {}
    else:
        try:
            d = json.load(open(AYAR_DOSYASI, encoding="utf-8"))
        except Exception as e:
            print(f"{AYAR_DOSYASI} okunamadı ({e}); varsayılanlar kullanılıyor.")
            d = {}
    GITHUB_DEPO = d.get("github_depo", GITHUB_DEPO) or ""
    DEPO_ALT_KLASOR = d.get("depo_alt_klasor", DEPO_ALT_KLASOR)
    SITE_ADRESI = (d.get("site_adresi", SITE_ADRESI) or "").rstrip("/")
    GA_KODU = d.get("ga_kodu", GA_KODU) or ""
    VARSAYILAN_IL = d.get("varsayilan_il", VARSAYILAN_IL)
    BITIS_SAATI = d.get("bitis_saati", BITIS_SAATI)
    EKRANDA_GOSTER = d.get("ekranda_goster", EKRANDA_GOSTER)
    PARALEL_SAYISI = d.get("paralel_sayisi", PARALEL_SAYISI)
    TEKRAR_ONLEME_GUN = d.get("tekrar_onleme_gun", TEKRAR_ONLEME_GUN)
    GERCEK_ILCE_ATA = bool(d.get("gercek_ilce_ata", True))
    if GITHUB_DEPO:
        ad = GITHUB_DEPO.rstrip("/").split("/")[-1]
        ad = ad[:-4] if ad.endswith(".git") else ad
        DEPO_KLASORU = os.path.join(KLASOR, ad or "LocalRadar")


_ayarlari_yukle()
ADETLER = {}                                      # slug -> bulunan yer sayısı (mesaj için)
_SESSIZ = {"acik": False}                         # True iken Telegram mesajı gönderilmez


def telegram(mesaj, sessiz_hata=True):
    """Telegram'a mesaj atar. Ayar dosyası yoksa ya da internet yoksa programı asla durdurmaz."""
    if _SESSIZ["acik"]:
        return False
    try:
        ayar = json.load(open(TELEGRAM_DOSYASI, encoding="utf-8"))
        token, chat_id = str(ayar["token"]).strip(), str(ayar["chat_id"]).strip()
    except Exception:
        return False
    try:
        veri = urllib.parse.urlencode({"chat_id": chat_id, "text": mesaj,
                                       "disable_web_page_preview": "true"}).encode()
        with urllib.request.urlopen(
                urllib.request.Request(f"https://api.telegram.org/bot{token}/sendMessage", data=veri),
                timeout=20) as r:
            return r.status == 200
    except Exception as e:
        if not sessiz_hata:
            print("Telegram hatası:", e)
        return False


def telegram_chat_id_bul():
    """Dosyadaki token ile bota gelen mesajlara bakar, senin chat_id'ni bulup dosyaya yazar."""
    try:
        ayar = json.load(open(TELEGRAM_DOSYASI, encoding="utf-8"))
        token = str(ayar["token"]).strip()
    except Exception:
        print(f"{TELEGRAM_DOSYASI} okunamadı. Dosyada \"token\" satırı dolu olmalı.")
        return
    try:
        with urllib.request.urlopen(f"https://api.telegram.org/bot{token}/getUpdates", timeout=20) as r:
            veri = json.load(r)
    except urllib.error.HTTPError as e:
        if e.code in (401, 404):
            print("Token yanlış görünüyor. BotFather'dan token'ı yeniden kopyala (tamamını, iki nokta dahil).")
        else:
            print("Telegram hatası:", e)
        return
    except Exception as e:
        print("Telegram'a ulaşılamadı:", e)
        return
    idler = []
    for u in veri.get("result", []):
        m = u.get("message") or u.get("edited_message") or u.get("my_chat_member") or {}
        c = m.get("chat") or {}
        if c.get("type") == "private" and c.get("id"):
            idler.append(str(c["id"]))
    if not idler:
        print("Bota hiç mesaj gelmemiş görünüyor. Telegram'da botunu aç, Başlat'a bas, 'merhaba' yaz, sonra tekrar dene.")
        return
    ayar["chat_id"] = idler[-1]
    with open(TELEGRAM_DOSYASI, "w", encoding="utf-8") as f:
        json.dump(ayar, f, ensure_ascii=False)
    print(f"Chat numaran bulundu ve {TELEGRAM_DOSYASI} dosyasına yazıldı: {idler[-1]}\n")
    telegram_testi()


def telegram_testi():
    if not os.path.exists(TELEGRAM_DOSYASI):
        print(f"{TELEGRAM_DOSYASI} bulunamadı. Aynı klasörde bu adla bir dosya olmalı.")
        return
    ok = telegram("✅ Local Radar gece taraması: Telegram bağlantısı çalışıyor.", sessiz_hata=False)
    print("Mesaj gönderildi, Telegram'ı kontrol et." if ok else
          "Mesaj gitmedi. Token ve chat_id doğru mu, bota Telegram'da /start yazdın mı?")


# ---------- durum ----------
def durum_oku():
    try:
        d = json.load(open(DURUM_DOSYASI, encoding="utf-8"))
    except Exception:
        d = {}
    d.setdefault("bitenler", [])
    d.setdefault("yuklenmemis", {})
    return d


def durum_yaz(d):
    with open(DURUM_DOSYASI, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)


# ---------- ilçe listesi ----------
def ilceleri_oku():
    if not os.path.exists(ILCE_DOSYASI):
        with open(ILCE_DOSYASI, "w", encoding="utf-8") as f:
            f.write("# Her satıra bir ilçe yaz. Sırayla taranır. Başına # koyarsan atlanır.\n")
            f.write("# Başka ilden eklemek için: Gaziantep/Şehitkamil\n\n")
            f.write("\n".join(ISTANBUL) + "\n")
    sonuc = []
    for satir in open(ILCE_DOSYASI, encoding="utf-8-sig"):
        s = satir.split("#")[0].strip()
        if not s:
            continue
        km = None
        if ":" in s:                      # ör. Hatay/Erzin:8  -> yarıçapı 8 km yap
            s, km_yazi = s.rsplit(":", 1)
            s = s.strip()
            try:
                km = float(km_yazi.strip().replace(",", "."))
            except ValueError:
                km = None
        if "/" in s:
            il, ilce = [x.strip() for x in s.split("/", 1)]
        else:
            il, ilce = VARSAYILAN_IL, s
        sonuc.append((il, ilce, km))
    sayac = {}
    for il, ilce, _km in sonuc:
        sayac.setdefault(_temiz(ilce), set()).add(il)
    CAKISAN.clear()
    CAKISAN.update(k for k, v in sayac.items() if len(v) > 1)
    return sonuc


CAKISAN = set()   # listede birden fazla ilde geçen ilçe adları (ör. Merkez, Yenişehir)


def _temiz(s):
    return re.sub(r"[^a-zA-Z0-9_]+", "", g.fold(s).replace(" ", "_")).title()


# Birden fazla ilde aynı adı taşıyan ilçeler: sitedeki liste yanlış ile koymasın diye
# bunlarda dosya adının başına il yazılır (Diyarbakir_Yenisehir gibi). Diğerleri sade kalır.
AYNI_AD = {"Aksu", "Altinyayla", "Aydincik", "Ayvacik", "Bayat", "Bozkurt", "Edremit", "Eregli",
           "Golbasi", "Gonen", "Kale", "Kemalpasa", "Kemer", "Koprubasi", "Ortakoy", "Ovacik",
           "Pazar", "Pinarbasi", "Saray", "Ulubey", "Yenice", "Yenipazar", "Yenisehir",
           "Yesilyurt", "Merkez"}


def slug_yap(ilce, il=None):
    """Dosya adı: ilçe adı tek başına (Kahta). Sadece ortak adlılarda il öne gelir."""
    taban = _temiz(ilce)
    if il and il != VARSAYILAN_IL and _temiz(il) != taban and taban in AYNI_AD:
        return _temiz(il) + "_" + taban
    return taban


def eski_slug(ilce, il=None):
    """Bu gece kullanılan eski adlandırma (Hatay_Defne); biten ilçeleri tekrar taramamak için."""
    taban = _temiz(ilce)
    if not il or il == VARSAYILAN_IL or _temiz(il) == taban:
        return taban
    return _temiz(il) + "_" + taban


def anahtar_yap(il, ilce, km=None):
    """gece_durum.json'daki kayıt adı. Yarıçaplı satırlar ayrı sayılır (Erzin@8),
    böylece daha önce küçük alanla taranmış ilçe, yeni yarıçapla yeniden taranır."""
    a = slug_yap(ilce, il)
    return a + ("@%g" % km) if km else a


def bitti_mi(il, ilce, km, durum):
    if km:
        return anahtar_yap(il, ilce, km) in durum["bitenler"]
    return slug_yap(ilce, il) in durum["bitenler"] or eski_slug(ilce, il) in durum["bitenler"]


# ---------- Local Radar ayarları (pencerede en son seçtiklerin) ----------
def gui_ayarlari():
    try:
        return json.load(open("settings.json", encoding="utf-8"))
    except Exception:
        return {}


def kategorileri_hazirla(s):
    yemek = s.get("yemek", True)
    gezi = s.get("gezi", True)
    kat, bol = [], []
    if s.get("tumu"):
        kat, bol = list(g.TUMU), list(g.BOLUMLER)
    else:
        def ekle(b):
            if b not in bol:
                bol.append(b)
        if yemek:
            kat += g.YEMEK + ["kasap"]
            for b in ["Kebap & Et", "Restoran", "Hızlı Atıştırmalık", "Tatlı & Pastane", "Kafe & Kahvaltı", "Alışveriş"]:
                ekle(b)
        if gezi:
            kat += g.GEZI
            ekle("Gezilecek yerler")
        if s.get("alisveris"):
            kat += g.ALISVERIS
            ekle("Alışveriş")
        for anahtar, liste in (("saglik", g.SAGLIK), ("oto", g.OTO), ("konaklama", g.KONAKLAMA), ("banka", g.BANKA)):
            if s.get(anahtar):
                kat += liste
                ekle("Diğer")
    ozel = [x.strip() for x in str(s.get("ozel_arama", "")).split(",") if x.strip()]
    if ozel:
        kat += ozel
        bol = list(g.BOLUMLER)
    diger = [s.get(k) for k in ("gezi", "alisveris", "saglik", "oto", "konaklama", "banka")]
    yemek_sadece = bool(yemek and not any(diger) and not s.get("tumu") and not ozel)
    return kat, bol, yemek_sadece


def sayi(deger, varsayilan, tur=float):
    try:
        return tur(str(deger).replace(",", "."))
    except Exception:
        return varsayilan


# ---------- git / GitHub ----------
def git(args, cwd=None, etkilesim=False, zaman=180):
    env = os.environ.copy()
    if not etkilesim:
        env["GIT_TERMINAL_PROMPT"] = "0"
        env["GCM_INTERACTIVE"] = "never"
    kw = {}
    if os.name == "nt":
        kw["creationflags"] = subprocess.CREATE_NO_WINDOW
    try:
        p = subprocess.run(["git"] + args, cwd=cwd, env=env, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=zaman, **kw)
        return p.returncode, (p.stdout + p.stderr).strip()
    except FileNotFoundError:
        return 127, "git bulunamadı (git-scm.com adresinden kurulmalı)"
    except Exception as e:
        return 1, str(e)


def depo_hazirla(etkilesim=False):
    if os.path.isdir(os.path.join(DEPO_KLASORU, ".git")):
        return True
    if not GITHUB_DEPO:
        log("ayarlar.json içinde github_depo boş; GitHub adımları atlandı.")
        return False
    log("GitHub deposu bilgisayara indiriliyor (bir kereye mahsus)...")
    rc, out = git(["clone", GITHUB_DEPO, DEPO_KLASORU], etkilesim=etkilesim, zaman=300)
    if rc != 0:
        log(f"   Depo indirilemedi: {out[:300]}")
        return False
    return True


def yukle(slug, html_yolu):
    """HTML'yi depoya kopyalar, commit'ler, GitHub'a gönderir. Başarılıysa True."""
    if not depo_hazirla():
        return False
    git(["pull", "--rebase", "--autostash"], cwd=DEPO_KLASORU)
    hedef_klasor = os.path.join(DEPO_KLASORU, DEPO_ALT_KLASOR) if DEPO_ALT_KLASOR else DEPO_KLASORU
    try:
        os.makedirs(hedef_klasor, exist_ok=True)
        hedef = os.path.join(hedef_klasor, slug + ".html")
        with open(html_yolu, encoding="utf-8") as _f:
            _h = _f.read()
        _h = g.sayfa_iyilestir(_h)
        if GA_KODU and GA_KODU not in _h:
            _etiket = ('<script async src="https://www.googletagmanager.com/gtag/js?id=' + GA_KODU + '"></script>'
                       '<script>window.dataLayer=window.dataLayer||[];function gtag(){dataLayer.push(arguments);}'
                       "gtag('js',new Date());gtag('config','" + GA_KODU + "');</script>")
            _h = _h.replace("<head>", "<head>" + _etiket, 1) if "<head>" in _h else _etiket + _h
        with open(hedef, "w", encoding="utf-8") as _f:
            _f.write(_h)
    except Exception as e:
        log(f"   Dosya kopyalanamadı: {e}")
        return False
    git(["add", (DEPO_ALT_KLASOR + "/" if DEPO_ALT_KLASOR else "") + slug + ".html"], cwd=DEPO_KLASORU)
    git(["-c", "user.name=Local Radar", "-c", "user.email=local-radar@users.noreply.github.com",
         "commit", "-m", f"{slug} rehberi eklendi/güncellendi"], cwd=DEPO_KLASORU)
    rc, out = git(["push"], cwd=DEPO_KLASORU)
    if rc != 0:
        git(["pull", "--rebase", "--autostash"], cwd=DEPO_KLASORU)
        rc, out = git(["push"], cwd=DEPO_KLASORU)
    if rc != 0:
        log(f"   GitHub'a yüklenemedi: {out[:300]}")
        return False
    log(f"   ✔ GitHub'a yüklendi: {slug}.html")
    return True


def bekleyenleri_yukle(durum):
    for slug, yol in list(durum["yuklenmemis"].items()):
        if os.path.exists(yol) and yukle(slug, yol):
            durum["yuklenmemis"].pop(slug, None)
            durum_yaz(durum)
            adet = ADETLER.get(slug)
            telegram(f"✅ {slug.replace('-Tum-Ilceler', ' · Tüm İlçeler (birleşik)').replace('_', ' ')} GitHub'a yüklendi"
                     + (f" ({adet} yer)" if adet is not None else "")
                     + f"\n{SITE_ADRESI}/rehberler/{slug}.html")


# ---------- İl bazında birleşik rehber ("Hatay · Tüm İlçeler") ----------
# Elle hazırladığın "Tüm İlçeler" dosyaları olan iller: otomatik üretim bunlara DOKUNMAZ.
# Bunları da otomatik üretilenle değiştirmek istersen küme içindeki adı sil: MANUEL_TUM_KORU = set()
MANUEL_TUM_KORU = {"Kilis"}   # Kilis: elle hazırlanan birleşik rehber (Kilis-Merkez dahil) korunur

IL_ILCE = json.loads(r'''{"Adana": ["Aladağ", "Ceyhan", "Çukurova", "Feke", "İmamoğlu", "Karaisalı", "Karataş", "Kozan", "Pozantı", "Saimbeyli", "Sarıçam", "Seyhan", "Tufanbeyli", "Yumurtalık", "Yüreğir"], "Adıyaman": ["Besni", "Çelikhan", "Gerger", "Gölbaşı", "Kahta", "Merkez", "Samsat", "Sincik", "Tut"], "Afyonkarahisar": ["Başmakçı", "Bayat", "Bolvadin", "Çay", "Çobanlar", "Dazkırı", "Dinar", "Emirdağ", "Evciler", "Hocalar", "İhsaniye", "İscehisar", "Kızılören", "Merkez", "Sandıklı", "Sinanpaşa", "Sultandağı", "Şuhut"], "Ağrı": ["Diyadin", "Doğubayazıt", "Eleşkirt", "Hamur", "Merkez", "Patnos", "Taşlıçay", "Tutak"], "Aksaray": ["Ağaçören", "Eskil", "Gülağaç", "Güzelyurt", "Merkez", "Ortaköy", "Sarıyahşi", "Sultanhanı"], "Amasya": ["Göynücek", "Gümüşhacıköy", "Hamamözü", "Merkez", "Merzifon", "Suluova", "Taşova"], "Ankara": ["Akyurt", "Altındağ", "Ayaş", "Bala", "Beypazarı", "Çamlıdere", "Çankaya", "Çubuk", "Elmadağ", "Etimesgut", "Evren", "Gölbaşı", "Güdül", "Haymana", "Kahramankazan", "Kalecik", "Keçiören", "Kızılcahamam", "Mamak", "Nallıhan", "Polatlı", "Pursaklar", "Sincan", "Şereflikoçhisar", "Yenimahalle"], "Antalya": ["Akseki", "Aksu", "Alanya", "Demre", "Döşemealtı", "Elmalı", "Finike", "Gazipaşa", "Gündoğmuş", "İbradı", "Kaş", "Kemer", "Kepez", "Konyaaltı", "Korkuteli", "Kumluca", "Manavgat", "Muratpaşa", "Serik"], "Ardahan": ["Çıldır", "Damal", "Göle", "Hanak", "Merkez", "Posof"], "Artvin": ["Ardanuç", "Arhavi", "Borçka", "Hopa", "Kemalpaşa", "Merkez", "Murgul", "Şavşat", "Yusufeli"], "Aydın": ["Bozdoğan", "Buharkent", "Çine", "Didim", "Efeler", "Germencik", "İncirliova", "Karacasu", "Karpuzlu", "Koçarlı", "Köşk", "Kuşadası", "Kuyucak", "Nazilli", "Söke", "Sultanhisar", "Yenipazar"], "Balıkesir": ["Altıeylül", "Ayvalık", "Balya", "Bandırma", "Bigadiç", "Burhaniye", "Dursunbey", "Edremit", "Erdek", "Gömeç", "Gönen", "Havran", "İvrindi", "Karesi", "Kepsut", "Manyas", "Marmara", "Savaştepe", "Sındırgı", "Susurluk"], "Bartın": ["Amasra", "Kurucaşile", "Merkez", "Ulus"], "Batman": ["Beşiri", "Gercüş", "Hasankeyf", "Kozluk", "Merkez", "Sason"], "Bayburt": ["Aydıntepe", "Demirözü", "Merkez"], "Bilecik": ["Bozüyük", "Gölpazarı", "İnhisar", "Merkez", "Osmaneli", "Pazaryeri", "Söğüt", "Yenipazar"], "Bingöl": ["Adaklı", "Genç", "Karlıova", "Kiğı", "Merkez", "Solhan", "Yayladere", "Yedisu"], "Bitlis": ["Adilcevaz", "Ahlat", "Güroymak", "Hizan", "Merkez", "Mutki", "Tatvan"], "Bolu": ["Dörtdivan", "Gerede", "Göynük", "Kıbrıscık", "Mengen", "Merkez", "Mudurnu", "Seben", "Yeniçağa"], "Burdur": ["Ağlasun", "Altınyayla", "Bucak", "Çavdır", "Çeltikçi", "Gölhisar", "Karamanlı", "Kemer", "Merkez", "Tefenni", "Yeşilova"], "Bursa": ["Büyükorhan", "Gemlik", "Gürsu", "Harmancık", "İnegöl", "İznik", "Karacabey", "Keles", "Kestel", "Mudanya", "Mustafakemalpaşa", "Nilüfer", "Orhaneli", "Orhangazi", "Osmangazi", "Yenişehir", "Yıldırım"], "Çanakkale": ["Ayvacık", "Bayramiç", "Biga", "Bozcaada", "Çan", "Eceabat", "Ezine", "Gelibolu", "Gökçeada", "Lapseki", "Merkez", "Yenice"], "Çankırı": ["Atkaracalar", "Bayramören", "Çerkeş", "Eldivan", "Ilgaz", "Kızılırmak", "Korgun", "Kurşunlu", "Merkez", "Orta", "Şabanözü", "Yapraklı"], "Çorum": ["Alaca", "Bayat", "Boğazkale", "Dodurga", "İskilip", "Kargı", "Laçin", "Mecitözü", "Merkez", "Oğuzlar", "Ortaköy", "Osmancık", "Sungurlu", "Uğurludağ"], "Denizli": ["Acıpayam", "Babadağ", "Baklan", "Bekilli", "Beyağaç", "Bozkurt", "Buldan", "Çal", "Çameli", "Çardak", "Çivril", "Güney", "Honaz", "Kale", "Merkezefendi", "Pamukkale", "Sarayköy", "Serinhisar", "Tavas"], "Diyarbakır": ["Bağlar", "Bismil", "Çermik", "Çınar", "Çüngüş", "Dicle", "Eğil", "Ergani", "Hani", "Hazro", "Kayapınar", "Kocaköy", "Kulp", "Lice", "Silvan", "Sur", "Yenişehir"], "Düzce": ["Akçakoca", "Cumayeri", "Çilimli", "Gölyaka", "Gümüşova", "Kaynaşlı", "Merkez", "Yığılca"], "Edirne": ["Enez", "Havsa", "İpsala", "Keşan", "Lalapaşa", "Meriç", "Merkez", "Süloğlu", "Uzunköprü"], "Elazığ": ["Ağın", "Alacakaya", "Arıcak", "Baskil", "Harput", "Karakoçan", "Keban", "Kovancılar", "Maden", "Merkez", "Palu", "Sivrice"], "Erzincan": ["Çayırlı", "İliç", "Kemah", "Kemaliye", "Merkez", "Otlukbeli", "Refahiye", "Tercan", "Üzümlü"], "Erzurum": ["Aşkale", "Aziziye", "Çat", "Hınıs", "Horasan", "İspir", "Karaçoban", "Karayazı", "Köprüköy", "Narman", "Oltu", "Olur", "Palandöken", "Pasinler", "Pazaryolu", "Şenkaya", "Tekman", "Tortum", "Uzundere", "Yakutiye"], "Eskişehir": ["Alpu", "Beylikova", "Çifteler", "Günyüzü", "Han", "İnönü", "Mahmudiye", "Mihalgazi", "Mihalıççık", "Odunpazarı", "Sarıcakaya", "Seyitgazi", "Sivrihisar", "Tepebaşı"], "Gaziantep": ["Araban", "İslahiye", "Karkamış", "Nizip", "Nurdağı", "Oğuzeli", "Şahinbey", "Şehitkamil", "Yavuzeli"], "Giresun": ["Alucra", "Bulancak", "Çamoluk", "Çanakçı", "Dereli", "Doğankent", "Espiye", "Eynesil", "Görele", "Güce", "Keşap", "Merkez", "Piraziz", "Şebinkarahisar", "Tirebolu", "Yağlıdere"], "Gümüşhane": ["Kelkit", "Köse", "Kürtün", "Merkez", "Şiran", "Torul"], "Hakkari": ["Çukurca", "Derecik", "Merkez", "Şemdinli", "Yüksekova"], "Hatay": ["Altınözü", "Antakya", "Arsuz", "Belen", "Defne", "Dörtyol", "Erzin", "Hassa", "İskenderun", "Kırıkhan", "Kumlu", "Payas", "Reyhanlı", "Samandağ", "Yayladağı"], "Iğdır": ["Aralık", "Karakoyunlu", "Merkez", "Tuzluca"], "Isparta": ["Aksu", "Atabey", "Eğirdir", "Gelendost", "Gönen", "Keçiborlu", "Merkez", "Senirkent", "Sütçüler", "Şarkikaraağaç", "Uluborlu", "Yalvaç", "Yenişarbademli"], "İstanbul": ["Adalar", "Arnavutköy", "Ataşehir", "Avcılar", "Bağcılar", "Bahçelievler", "Bakırköy", "Başakşehir", "Bayrampaşa", "Beşiktaş", "Beykoz", "Beylikdüzü", "Beyoğlu", "Büyükçekmece", "Çatalca", "Çekmeköy", "Esenler", "Esenyurt", "Eyüpsultan", "Fatih", "Gaziosmanpaşa", "Güngören", "Kadıköy", "Kağıthane", "Kartal", "Küçükçekmece", "Maltepe", "Pendik", "Sancaktepe", "Sarıyer", "Silivri", "Sultanbeyli", "Sultangazi", "Şile", "Şişli", "Tuzla", "Ümraniye", "Üsküdar", "Zeytinburnu"], "İzmir": ["Aliağa", "Balçova", "Bayındır", "Bayraklı", "Bergama", "Beydağ", "Bornova", "Buca", "Çeşme", "Çiğli", "Dikili", "Foça", "Gaziemir", "Güzelbahçe", "Karabağlar", "Karaburun", "Karşıyaka", "Kemalpaşa", "Kınık", "Kiraz", "Konak", "Menderes", "Menemen", "Narlıdere", "Ödemiş", "Seferihisar", "Selçuk", "Tire", "Torbalı", "Urla"], "Kahramanmaraş": ["Afşin", "Andırın", "Çağlayancerit", "Dulkadiroğlu", "Ekinözü", "Elbistan", "Göksun", "Nurhak", "Onikişubat", "Pazarcık", "Türkoğlu"], "Karabük": ["Eflani", "Eskipazar", "Merkez", "Ovacık", "Safranbolu", "Yenice"], "Karaman": ["Ayrancı", "Başyayla", "Ermenek", "Kazımkarabekir", "Merkez", "Sarıveliler"], "Kars": ["Akyaka", "Arpaçay", "Digor", "Kağızman", "Merkez", "Sarıkamış", "Selim", "Susuz"], "Kastamonu": ["Abana", "Ağlı", "Araç", "Azdavay", "Bozkurt", "Cide", "Çatalzeytin", "Daday", "Devrekani", "Doğanyurt", "Hanönü", "İhsangazi", "İnebolu", "Küre", "Merkez", "Pınarbaşı", "Seydiler", "Şenpazar", "Taşköprü", "Tosya"], "Kayseri": ["Akkışla", "Bünyan", "Develi", "Felahiye", "Hacılar", "İncesu", "Kocasinan", "Melikgazi", "Özvatan", "Pınarbaşı", "Sarıoğlan", "Sarız", "Talas", "Tomarza", "Yahyalı", "Yeşilhisar"], "Kilis": ["Elbeyli", "Merkez", "Musabeyli", "Polateli"], "Kırıkkale": ["Bahşılı", "Balışeyh", "Çelebi", "Delice", "Karakeçili", "Keskin", "Merkez", "Sulakyurt", "Yahşihan"], "Kırklareli": ["Babaeski", "Demirköy", "Kofçaz", "Lüleburgaz", "Merkez", "Pehlivanköy", "Pınarhisar", "Vize"], "Kırşehir": ["Akçakent", "Akpınar", "Boztepe", "Çiçekdağı", "Kaman", "Merkez", "Mucur"], "Kocaeli": ["Başiskele", "Çayırova", "Darıca", "Derince", "Dilovası", "Gebze", "Gölcük", "İzmit", "Kandıra", "Karamürsel", "Kartepe", "Körfez"], "Konya": ["Ahırlı", "Akören", "Akşehir", "Altınekin", "Beyşehir", "Bozkır", "Cihanbeyli", "Çeltik", "Çumra", "Derbent", "Derebucak", "Doğanhisar", "Emirgazi", "Ereğli", "Güneysınır", "Hadim", "Halkapınar", "Hüyük", "Ilgın", "Kadınhanı", "Karapınar", "Karatay", "Kulu", "Meram", "Sarayönü", "Selçuklu", "Seydişehir", "Taşkent", "Tuzlukçu", "Yalıhüyük", "Yunak"], "Kütahya": ["Altıntaş", "Aslanapa", "Çavdarhisar", "Domaniç", "Dumlupınar", "Emet", "Gediz", "Hisarcık", "Merkez", "Pazarlar", "Simav", "Şaphane", "Tavşanlı"], "Malatya": ["Akçadağ", "Arapgir", "Arguvan", "Battalgazi", "Darende", "Doğanşehir", "Doğanyol", "Hekimhan", "Kale", "Kuluncak", "Pütürge", "Yazıhan", "Yeşilyurt"], "Manisa": ["Ahmetli", "Akhisar", "Alaşehir", "Demirci", "Gölmarmara", "Gördes", "Kırkağaç", "Köprübaşı", "Kula", "Salihli", "Sarıgöl", "Saruhanlı", "Selendi", "Soma", "Şehzadeler", "Turgutlu", "Yunusemre"], "Mardin": ["Artuklu", "Dargeçit", "Derik", "Kızıltepe", "Mazıdağı", "Midyat", "Nusaybin", "Ömerli", "Savur", "Yeşilli"], "Mersin": ["Akdeniz", "Anamur", "Aydıncık", "Bozyazı", "Çamlıyayla", "Erdemli", "Gülnar", "Mezitli", "Mut", "Silifke", "Tarsus", "Toroslar", "Yenişehir"], "Muğla": ["Bodrum", "Dalaman", "Datça", "Fethiye", "Kavaklıdere", "Köyceğiz", "Marmaris", "Menteşe", "Milas", "Ortaca", "Seydikemer", "Ula", "Yatağan"], "Muş": ["Bulanık", "Hasköy", "Korkut", "Malazgirt", "Merkez", "Varto"], "Nevşehir": ["Acıgöl", "Avanos", "Derinkuyu", "Gülşehir", "Hacıbektaş", "Kozaklı", "Merkez", "Ürgüp"], "Niğde": ["Altunhisar", "Bor", "Çamardı", "Çiftlik", "Merkez", "Ulukışla"], "Ordu": ["Akkuş", "Altınordu", "Aybastı", "Çamaş", "Çatalpınar", "Çaybaşı", "Fatsa", "Gölköy", "Gülyalı", "Gürgentepe", "İkizce", "Kabadüz", "Kabataş", "Korgan", "Kumru", "Mesudiye", "Perşembe", "Ulubey", "Ünye"], "Osmaniye": ["Bahçe", "Düziçi", "Hasanbeyli", "Kadirli", "Merkez", "Sumbas", "Toprakkale"], "Rize": ["Ardeşen", "Çamlıhemşin", "Çayeli", "Derepazarı", "Fındıklı", "Güneysu", "Hemşin", "İkizdere", "İyidere", "Kalkandere", "Merkez", "Pazar"], "Sakarya": ["Adapazarı", "Akyazı", "Arifiye", "Erenler", "Ferizli", "Geyve", "Hendek", "Karapürçek", "Karasu", "Kaynarca", "Kocaali", "Pamukova", "Sapanca", "Serdivan", "Söğütlü", "Taraklı"], "Samsun": ["19 Mayıs", "Alaçam", "Asarcık", "Atakum", "Ayvacık", "Bafra", "Canik", "Çarşamba", "Havza", "İlkadım", "Kavak", "Ladik", "Salıpazarı", "Tekkeköy", "Terme", "Vezirköprü", "Yakakent"], "Siirt": ["Baykan", "Eruh", "Kurtalan", "Merkez", "Pervari", "Şirvan", "Tillo"], "Sinop": ["Ayancık", "Boyabat", "Dikmen", "Durağan", "Erfelek", "Gerze", "Merkez", "Saraydüzü", "Türkeli"], "Sivas": ["Akıncılar", "Altınyayla", "Divriği", "Doğanşar", "Gemerek", "Gölova", "Gürün", "Hafik", "İmranlı", "Kangal", "Koyulhisar", "Merkez", "Suşehri", "Şarkışla", "Ulaş", "Yıldızeli", "Zara"], "Şanlıurfa": ["Akçakale", "Birecik", "Bozova", "Ceylanpınar", "Eyyübiye", "Halfeti", "Haliliye", "Harran", "Hilvan", "Karaköprü", "Siverek", "Suruç", "Viranşehir"], "Şırnak": ["Beytüşşebap", "Cizre", "Güçlükonak", "İdil", "Merkez", "Silopi", "Uludere"], "Tekirdağ": ["Çerkezköy", "Çorlu", "Ergene", "Hayrabolu", "Kapaklı", "Malkara", "Marmaraereğlisi", "Muratlı", "Saray", "Süleymanpaşa", "Şarköy"], "Tokat": ["Almus", "Artova", "Başçiftlik", "Erbaa", "Merkez", "Niksar", "Pazar", "Reşadiye", "Sulusaray", "Turhal", "Yeşilyurt", "Zile"], "Trabzon": ["Akçaabat", "Araklı", "Arsin", "Beşikdüzü", "Çarşıbaşı", "Çaykara", "Dernekpazarı", "Düzköy", "Hayrat", "Köprübaşı", "Maçka", "Of", "Ortahisar", "Sürmene", "Şalpazarı", "Tonya", "Vakfıkebir", "Yomra"], "Tunceli": ["Çemişgezek", "Hozat", "Mazgirt", "Merkez", "Nazımiye", "Ovacık", "Pertek", "Pülümür"], "Uşak": ["Banaz", "Eşme", "Karahallı", "Merkez", "Sivaslı", "Ulubey"], "Van": ["Bahçesaray", "Başkale", "Çaldıran", "Çatak", "Edremit", "Erciş", "Gevaş", "Gürpınar", "İpekyolu", "Muradiye", "Özalp", "Saray", "Tuşba"], "Yalova": ["Altınova", "Armutlu", "Çınarcık", "Çiftlikköy", "Merkez", "Termal"], "Yozgat": ["Akdağmadeni", "Aydıncık", "Boğazlıyan", "Çandır", "Çayıralan", "Çekerek", "Kadışehri", "Merkez", "Saraykent", "Sarıkaya", "Sorgun", "Şefaatli", "Yenifakılı", "Yerköy"], "Zonguldak": ["Alaplı", "Çaycuma", "Devrek", "Ereğli", "Gökçebey", "Kilimli", "Kozlu", "Merkez"]}''')


def _nrm(s):
    return re.sub(r"[^a-z0-9]", "", g.fold(str(s)).lower())


_IL_ADI, _PREFIXLI, _TEK = {}, {}, {}


def _tablolari_kur():
    sira = [i for i in IL_ILCE if i != "Gaziantep"] + ["Gaziantep"]   # aynı adlı ilçede Gaziantep öncelikli
    for il in sira:
        _IL_ADI[_nrm(il)] = il
        for ilce in IL_ILCE[il]:
            _PREFIXLI[_nrm(il) + _nrm(ilce)] = il
            if _nrm(ilce) != "merkez":
                _TEK[_nrm(ilce)] = il


_tablolari_kur()


def il_bul(slug):
    """Tarama klasörünün adından (Hatay_Defne, Kahta, Usak...) ilini bulur. Mahalle taramaları (Nizip_Mimar_Sinan gibi) None döner."""
    n = _nrm(slug)
    return _PREFIXLI.get(n) or _IL_ADI.get(n) or _TEK.get(n)


def tarama_klasorleri():
    """slug -> o ilçenin EN YENİ tarama sonucu (…_places.json)."""
    kok = g.KLASOR_CIKTILAR
    sonuc = {}
    if not os.path.isdir(kok):
        return sonuc
    for ad in sorted(os.listdir(kok)):                  # adın başında tarih var; eski -> yeni sıralı
        m = re.match(r"^\d{8}_\d{4}_(.+)$", ad)
        if not m:
            continue
        yol = os.path.join(kok, ad, m.group(1) + "_places.json")
        if os.path.exists(yol):
            sonuc[m.group(1)] = yol
    return sonuc


# ---------- Gerçek ilçe ataması (koordinat + ilçe sınırları) ----------
_ATAYICI = {"nesne": None, "denendi": False}
_SATIR_ONBELLEK = {}           # slug -> ilçe taramasının satırları (bellekte)
_CAPRAZ = {"hazir": False, "il_ekstra": {}, "havuz": {}}


def _atayici():
    if not GERCEK_ILCE_ATA:
        return None
    if not _ATAYICI["denendi"]:
        _ATAYICI["denendi"] = True
        try:
            import ilce_ata
            _ATAYICI["nesne"] = ilce_ata.Atayici(IL_ILCE)
        except Exception as e:
            print(f"   Gerçek ilçe ataması kapalı ({e}). 'pip install shapely' gerekebilir; eski yöntemle devam ediliyor.")
    return _ATAYICI["nesne"]


def _satirlar_oku(slug, yol):
    if slug not in _SATIR_ONBELLEK:
        rows = json.load(open(yol, encoding="utf-8"))
        for r in rows:
            if r.get("_puansiz"):
                r["Puan"], r["Yorum Sayısı"], r["Güvenilir Skor"] = 0.0, 0, 0.0
        _SATIR_ONBELLEK[slug] = rows
    return _SATIR_ONBELLEK[slug]


def _capraz_hazirla():
    """Bütün ilçe taramalarındaki mekanların gerçek ilini bulur; başka ile ait olanları o ilin listesine koyar."""
    if _CAPRAZ["hazir"]:
        return
    _CAPRAZ["hazir"] = True
    at = _atayici()
    if not at:
        return
    print("   Gerçek ilçe ataması hazırlanıyor (ilk seferde birkaç dakika sürebilir)...")
    import ilce_ata
    ekstra, havuz = {}, {}
    for slug, yol in tarama_klasorleri().items():
        kaynak_il = il_bul(slug)
        if not kaynak_il:
            continue
        for r in _satirlar_oku(slug, yol):
            v = at.ata(r)
            if not v:
                continue
            il2, ilce2, kat = v
            r["_gil"], r["_gilce"], r["_gkat"] = il2, ilce2, kat
            if kat != "uzak":                              # ilçe rehberleri için: (il, ilçe) -> mekanlar
                kayit = havuz.setdefault((_nrm(il2), ilce_ata.ilce_anahtar(il2, ilce2)), {})
                yid = ilce_ata._yer_id(r.get("Harita Linki")) or id(r)
                eski = kayit.get(yid)
                if eski is None or (r.get("Yorum Sayısı") or 0) > (eski.get("Yorum Sayısı") or 0):
                    kayit[yid] = r
            if kat != "uzak" and _nrm(il2) != _nrm(kaynak_il):
                ekstra.setdefault(_nrm(il2), []).append(r)
    at.kaydet()
    _CAPRAZ["il_ekstra"] = ekstra
    _CAPRAZ["havuz"] = havuz


def il_birlestir(il):
    """İlin tüm ilçe taramalarını tek rehberde toplar, aynı mekanı bir kez yazar.
    En az 2 ilçe yoksa None. Başarılıysa (slug, html_yolu, yer_sayisi) döner."""
    n_il = _nrm(il)
    paylar = {s: y for s, y in tarama_klasorleri().items() if il_bul(s) and _nrm(il_bul(s)) == n_il}
    if len(paylar) < 2:
        return None

    _capraz_hazirla()
    gercek = bool(_atayici())
    satirlar, merkezler = {}, {}
    for slug, yol in paylar.items():
        rows = list(_satirlar_oku(slug, yol))
        if gercek:                                       # gerçek ile göre süz, ilçe adını düzelt
            temiz = []
            for r in rows:
                if "_gil" in r:
                    if r["_gkat"] == "uzak" or _nrm(r["_gil"]) != n_il:
                        continue                         # yurt dışı/bozuk ya da başka ile ait
                    r = dict(r, **{"İlçe": r["_gilce"]})
                temiz.append(r)
            rows = temiz
        satirlar[slug] = rows
        nok = [(r["Enlem"], r["Boylam"]) for r in rows
               if isinstance(r.get("Enlem"), (int, float)) and isinstance(r.get("Boylam"), (int, float))]
        merkezler[slug] = (sum(a for a, _ in nok) / len(nok), sum(b for _, b in nok) / len(nok)) if nok else None

    if gercek:                                           # başka illerin taramalarında bulunan bu ile ait mekanlar
        ek = [dict(r, **{"İlçe": r["_gilce"]}) for r in _CAPRAZ["il_ekstra"].get(n_il, [])]
        if ek:
            satirlar["_ekstra"] = ek

    def uzaklik(slug, r):
        if slug == "_ekstra":
            return 1e9                                   # aynı mekan zaten varsa onun kaydı kalsın
        m = merkezler.get(slug)
        if not m or not isinstance(r.get("Enlem"), (int, float)):
            return 0.0
        return g.mesafe_km(m, (r["Enlem"], r["Boylam"]))

    # 1) aynı Harita Linki: mekanın konumuna en yakın ilçe taramasındaki kayıt kalır
    secilen = {}
    for slug, rows in satirlar.items():
        for r in rows:
            anahtar = r.get("Harita Linki") or (g.fold(r.get("Yer", "")), r.get("Enlem"), r.get("Boylam"))
            d = uzaklik(slug, r)
            if anahtar not in secilen or d < secilen[anahtar][1]:
                secilen[anahtar] = (r, d)
    # 2) linki farklı ama adı ve konumu aynı olanlar: puanı yüksek olan kalır
    tekil = {}
    for r, _d in secilen.values():
        if isinstance(r.get("Enlem"), (int, float)):
            k = (g.fold(r.get("Yer", "")), round(r["Enlem"], 3), round(r["Boylam"], 3))
        else:
            k = (g.fold(r.get("Yer", "")), r.get("Mahalle"))
        if k not in tekil or float(r.get("Güvenilir Skor") or 0) > float(tekil[k].get("Güvenilir Skor") or 0):
            tekil[k] = r
    kayitlar = sorted(tekil.values(), key=lambda x: -float(x.get("Güvenilir Skor") or 0))

    klasor = os.path.join(g.KLASOR_CIKTILAR, "birlesik")
    os.makedirs(klasor, exist_ok=True)
    slug_b = _temiz(il) + "-Tum-Ilceler"
    yol_b = os.path.join(klasor, slug_b + ".html")
    g.html_yaz(kayitlar, {"baslik": f"{il} · Tüm İlçeler"}, yol_b, yemek_sadece=True, alisveris_acik=False)
    return slug_b, yol_b, len(kayitlar)


def ilce_rehberlerini_duzelt():
    """Menü 9: her ilçe rehberini, gerçekten o ilçede olan mekanlarla yeniden kurar (koordinat + ilçe sınırı)."""
    if not depo_hazirla():
        print("Depo hazırlanamadı.")
        return
    if not _atayici():
        print("Gerçek ilçe ataması kullanılamıyor (shapely yüklü mü? 'pip install shapely').")
        return
    import ilce_ata
    git(["pull", "--rebase", "--autostash"], cwd=DEPO_KLASORU)
    _capraz_hazirla()
    klasor = os.path.join(DEPO_KLASORU, DEPO_ALT_KLASOR) if DEPO_ALT_KLASOR else DEPO_KLASORU
    hedef_klasor = os.path.join(g.KLASOR_CIKTILAR, "duzeltilmis")
    os.makedirs(hedef_klasor, exist_ok=True)
    harita = _ilce_dosya_haritasi(merkez=True)
    uretilen, atlanan, satirlar = {}, [], []
    for ad in sorted(os.listdir(klasor)):
        if not ad.endswith(".html") or ad.endswith("-Tum-Ilceler.html") or ad not in harita:
            continue
        il, ilce = harita[ad]
        anahtar = (_nrm(il), ilce_ata.ilce_anahtar(il, ilce))
        rows = [dict(r, **{"İlçe": r["_gilce"]}) for r in _CAPRAZ["havuz"].get(anahtar, {}).values()]
        try:
            eski = open(os.path.join(klasor, ad), encoding="utf-8").read()
            V = json.JSONDecoder().raw_decode(eski[eski.index("const V=") + 8:])[0]
            eski_say = len(V.get("I", []))
            kategoriler = list(V.get("O", {}).keys())
            bm = re.search(r"<title>(.*?)</title>", eski)
            baslik = bm.group(1) if bm else f"{ilce} · Local Radar"
        except Exception:
            satirlar.append(f"{ad}: eski dosya okunamadı, atlandı")
            continue
        if not rows:
            atlanan.append(ad)
            satirlar.append(f"{ad}: {eski_say} -> 0  (bu ilçede mekan bulunamadı, DOKUNULMADI)")
            continue
        yol = os.path.join(hedef_klasor, ad)
        g.html_yaz(rows, {"baslik": baslik}, yol, yemek_sadece=(kategoriler == ["Yemek"]),
                   alisveris_acik=("Alışveriş" in kategoriler))
        try:
            h = open(yol, encoding="utf-8").read()
            yeni_say = len(json.JSONDecoder().raw_decode(h[h.index("const V=") + 8:])[0].get("I", []))
        except Exception:
            yeni_say = len(rows)
        if yeni_say < 20 and eski_say >= 20:               # içi boşalacak rehberi bozma; elle bakılsın / yeniden taransın
            atlanan.append(ad)
            satirlar.append(f"{ad}: {eski_say} -> {yeni_say}  (DOKUNULMADI: gerçek ilçesinde 20'den az mekan var, yeniden taranmalı)")
            continue
        uretilen[ad] = yol
        satirlar.append(f"{ad}: {eski_say} -> {yeni_say}" + ("   (20'nin altında)" if yeni_say < 20 else ""))
    rapor_yolu = os.path.join(KLASOR, "ilce_duzeltme_raporu.txt")
    with open(rapor_yolu, "w", encoding="utf-8") as f:
        f.write("İlçe rehberi düzeltme önizlemesi (eski mekan sayısı -> yeni)\n\n" + "\n".join(satirlar))
    print(f"\n{len(uretilen)} ilçe rehberi yeniden kuruldu, {len(atlanan)} tanesine dokunulmadı.")
    print(f"Önizleme dosyaları: {hedef_klasor}   (tarayıcıda açıp bakabilirsin)")
    print(f"Eski -> yeni sayılar: {rapor_yolu}")
    if not uretilen:
        return
    if input("\nBunlar GitHub'a yüklensin mi? (e/h): ").strip().lower() not in ("e", "evet"):
        print("Yüklenmedi. Beğenmezsen hiçbir şey değişmedi.")
        return
    git(["pull", "--rebase", "--autostash"], cwd=DEPO_KLASORU)
    for ad, yol in uretilen.items():
        h = g.sayfa_iyilestir(open(yol, encoding="utf-8").read())
        if GA_KODU and GA_KODU not in h:
            et = ('<script async src="https://www.googletagmanager.com/gtag/js?id=' + GA_KODU + '"></script>'
                  '<script>window.dataLayer=window.dataLayer||[];function gtag(){dataLayer.push(arguments);}'
                  "gtag('js',new Date());gtag('config','" + GA_KODU + "');</script>")
            h = h.replace("<head>", "<head>" + et, 1) if "<head>" in h else et + h
        with open(os.path.join(klasor, ad), "w", encoding="utf-8") as f:
            f.write(h)
    git(["add", "-A"], cwd=DEPO_KLASORU)
    git(["-c", "user.name=Local Radar", "-c", "user.email=local-radar@users.noreply.github.com",
         "commit", "-m", "İlçe rehberleri gerçek ilçe sınırlarına göre yeniden kuruldu"], cwd=DEPO_KLASORU)
    rc, out = git(["push"], cwd=DEPO_KLASORU, zaman=900)
    if rc != 0:
        git(["pull", "--rebase", "--autostash"], cwd=DEPO_KLASORU)
        rc, out = git(["push"], cwd=DEPO_KLASORU, zaman=900)
    print("GitHub'a yüklendi." if rc == 0 else f"Yüklenemedi: {out[:300]}")
    if rc == 0:
        print("\n'Neler yenir?' sayfaları yenileniyor...")
        populer_sayfalar_uret()


def il_birlestir_ve_yukle(il, durum):
    """Gece döngüsünden çağrılır: ilin birleşik rehberini yeniler, GitHub'a gönderir."""
    if _nrm(il) in {_nrm(x) for x in MANUEL_TUM_KORU}:
        return
    try:
        b = il_birlestir(il)
        if not b:
            return
        slug_b, yol_b, adet = b
        log(f"   {il} birleşik rehberi hazırlandı: {adet} yer (aynı mekanlar tek kez)")
        ADETLER[slug_b] = adet
        durum["yuklenmemis"][slug_b] = os.path.abspath(yol_b)
        durum_yaz(durum)
        bekleyenleri_yukle(durum)
    except Exception:
        log(f"   {il} birleşik rehberi hazırlanamadı (ilçe taramaları etkilenmedi):\n" + traceback.format_exc())


def tum_illeri_birlestir():
    """Menü 5: şimdiye kadar taranan bütün illerin birleşik rehberlerini bir kerede üretir ve yükler."""
    _SESSIZ["acik"] = True      # 30'a yakın Telegram mesajı gitmesin
    durum = durum_oku()
    iller = sorted({il_bul(s) for s in tarama_klasorleri() if il_bul(s)}, key=lambda x: _nrm(x))
    hazir = 0
    for il in iller:
        if _nrm(il) in {_nrm(x) for x in MANUEL_TUM_KORU}:
            print(f"{il}: elle yaptığın dosya korundu, atlandı.")
            continue
        try:
            b = il_birlestir(il)
        except Exception:
            print(f"{il}: HATA\n{traceback.format_exc()}")
            continue
        if not b:
            print(f"{il}: tek ilçe var, birleşik rehber gerekmiyor.")
            continue
        slug_b, yol_b, adet = b
        print(f"{il}: {adet} yer, birleşik rehber hazır.")
        durum["yuklenmemis"][slug_b] = os.path.abspath(yol_b)
        durum_yaz(durum)
        hazir += 1
    if hazir:
        print("\nGitHub'a yükleniyor...")
        bekleyenleri_yukle(durum)
    _SESSIZ["acik"] = False
    print(f"\nBitti. {hazir} ilin birleşik rehberi hazırlandı.")


def analytics_ekle_hepsine():
    """Menü 6: depodaki bütün rehber sayfalarına Google Analytics kodunu ekler ve GitHub'a yükler."""
    if not GA_KODU:
        print("ayarlar.json içinde ga_kodu boş; Analytics eklenmedi.")
        return
    if not depo_hazirla():
        print("Depo hazırlanamadı.")
        return
    git(["pull", "--rebase", "--autostash"], cwd=DEPO_KLASORU)
    klasor = os.path.join(DEPO_KLASORU, DEPO_ALT_KLASOR) if DEPO_ALT_KLASOR else DEPO_KLASORU
    etiket = ('<script async src="https://www.googletagmanager.com/gtag/js?id=' + GA_KODU + '"></script>'
              '<script>window.dataLayer=window.dataLayer||[];function gtag(){dataLayer.push(arguments);}'
              "gtag('js',new Date());gtag('config','" + GA_KODU + "');</script>")
    eklenen = atlanan = 0
    for ad in sorted(os.listdir(klasor)):
        if not ad.lower().endswith(".html") or ad.lower() == "index.html":
            continue
        yol = os.path.join(klasor, ad)
        try:
            with open(yol, encoding="utf-8") as f:
                h = f.read()
            if GA_KODU in h:
                atlanan += 1
                continue
            h = h.replace("<head>", "<head>" + etiket, 1) if "<head>" in h else etiket + h
            with open(yol, "w", encoding="utf-8") as f:
                f.write(h)
            eklenen += 1
        except Exception as e:
            print(f"{ad}: atlandı ({e})")
    print(f"{eklenen} sayfaya kod eklendi, {atlanan} sayfada zaten vardı.")
    if not eklenen:
        return
    git(["add", "-A"], cwd=DEPO_KLASORU)
    git(["-c", "user.name=Local Radar", "-c", "user.email=local-radar@users.noreply.github.com",
         "commit", "-m", "Analytics kodu eklendi"], cwd=DEPO_KLASORU)
    rc, out = git(["push"], cwd=DEPO_KLASORU, zaman=600)
    if rc != 0:
        git(["pull", "--rebase", "--autostash"], cwd=DEPO_KLASORU)
        rc, out = git(["push"], cwd=DEPO_KLASORU, zaman=600)
    print("GitHub'a yüklendi." if rc == 0 else f"Yükleme başarısız: {out[:300]}")


def en_iyi_ekle_hepsine():
    """Menü 7: depodaki bütün rehber sayfalarını günceller (En iyi 10 kutusu, adres satırı gizli) ve GitHub'a yükler."""
    if not depo_hazirla():
        print("Depo hazırlanamadı.")
        return
    git(["pull", "--rebase", "--autostash"], cwd=DEPO_KLASORU)
    klasor = os.path.join(DEPO_KLASORU, DEPO_ALT_KLASOR) if DEPO_ALT_KLASOR else DEPO_KLASORU
    eklenen = atlanan = 0
    for ad in sorted(os.listdir(klasor)):
        if not ad.lower().endswith(".html") or ad.lower() == "index.html":
            continue
        yol = os.path.join(klasor, ad)
        try:
            with open(yol, encoding="utf-8") as f:
                h = f.read()
            yeni = g.sayfa_iyilestir(h)
            if yeni == h:
                atlanan += 1
                continue
            with open(yol, "w", encoding="utf-8") as f:
                f.write(yeni)
            eklenen += 1
        except Exception as e:
            print(f"{ad}: atlandı ({e})")
    print(f"{eklenen} sayfa güncellendi, {atlanan} sayfada zaten güncel ya da uygun değildi.")
    if not eklenen:
        return
    git(["add", "-A"], cwd=DEPO_KLASORU)
    git(["-c", "user.name=Local Radar", "-c", "user.email=local-radar@users.noreply.github.com",
         "commit", "-m", "Rehber sayfaları iyileştirildi (sayfalama, favori, kümeli harita, paylaşılabilir link)"], cwd=DEPO_KLASORU)
    rc, out = git(["push"], cwd=DEPO_KLASORU, zaman=900)
    if rc != 0:
        git(["pull", "--rebase", "--autostash"], cwd=DEPO_KLASORU)
        rc, out = git(["push"], cwd=DEPO_KLASORU, zaman=900)
    print("GitHub'a yüklendi." if rc == 0 else f"Yükleme başarısız: {out[:300]}")


# Bir ilçe için "Neler yenir?" sayfası şu durumlarda üretilir (hangisi sağlanırsa):
POPULER_ILCE_MIN_MEKAN = 400        # 1) ilçe büyükse: rehberde en az bu kadar mekan var
POPULER_ILCE_MIN_POPULER = 15       # 2) küçük ama ünlüyse: en az 15 mekanın puanı 4,0+ ve yorumu 300+ olsun
POPULER_ILCE_YORUM = 300
POPULER_ILCE_ZORUNLU = {"Safranbolu", "Urgup", "Avanos", "Selcuk", "Kas", "Ayvalik", "Foca", "Cesme",
                        "Bodrum", "Marmaris", "Fethiye", "Amasra", "Sile", "Alacati", "Goreme", "Kekova"}
# 3) listeye eklediğin ilçeler (yukarıdaki POPULER_ILCE_ZORUNLU) küçük de olsa her zaman üretilir (dosya adı, il öneki olmadan)


def _populer_ilce_uygun(h, ad):
    """İlçe rehberi 'Neler yenir?' sayfası için uygun mu?"""
    if ad.replace(".html", "").split("_")[-1] in POPULER_ILCE_ZORUNLU:
        return True
    if h.count('"l": "http') >= POPULER_ILCE_MIN_MEKAN:
        return True
    i = h.find("const V=")
    if i < 0:
        return False
    try:
        veri = json.JSONDecoder().raw_decode(h[i + 8:])[0]
    except Exception:
        return False
    n = 0
    for x in veri.get("I", []):
        try:
            if not x.get("u") and float(str(x.get("p", "0")).replace(",", ".")) >= 4.0 and (x.get("y") or 0) >= POPULER_ILCE_YORUM:
                n += 1
        except ValueError:
            pass
    return n >= POPULER_ILCE_MIN_POPULER


def _ilce_dosya_haritasi(merkez=False):
    """Dosya adı -> (il, ilçe). Hem yeni hem eski adlandırmayı tanır.
    merkez=True: il adıyla duran merkez ilçe rehberlerini de (Isparta.html -> Isparta/Merkez) tanır."""
    harita = {}
    for il, ilceler in IL_ILCE.items():
        for ilce in ilceler:
            harita[slug_yap(ilce, il) + ".html"] = (il, ilce)
            harita.setdefault(eski_slug(ilce, il) + ".html", (il, ilce))
        if merkez and "Merkez" in ilceler:
            harita.setdefault(_temiz(il) + ".html", (il, "Merkez"))
    return harita


def populer_sayfalar_uret():
    """'Neler yenir?' sayfaları: her il için + büyük ilçeler için (populer/ klasörü) ve GitHub'a yükler."""
    if not depo_hazirla():
        print("Depo hazırlanamadı.")
        return
    git(["pull", "--rebase", "--autostash"], cwd=DEPO_KLASORU)
    klasor = os.path.join(DEPO_KLASORU, DEPO_ALT_KLASOR) if DEPO_ALT_KLASOR else DEPO_KLASORU
    hedef = os.path.join(DEPO_KLASORU, "populer")
    os.makedirs(hedef, exist_ok=True)
    dosyalar = sorted(os.listdir(klasor))
    liste, il_say, ilce_say = [], 0, 0
    for ad in dosyalar:                      # 1) il sayfaları
        if not ad.endswith("-Tum-Ilceler.html"):
            continue
        try:
            with open(os.path.join(klasor, ad), encoding="utf-8") as f:
                cikti = g.populer_sayfa(f.read(), ad)
            if cikti:
                cikis = ad.replace("-Tum-Ilceler", "")
                with open(os.path.join(hedef, cikis), "w", encoding="utf-8") as f:
                    f.write(cikti)
                liste.append(ad)
                il_say += 1
        except Exception as e:
            print(f"{ad}: atlandı ({e})")
    harita = _ilce_dosya_haritasi()
    atla = {"index.html", "harita.html", "bolge.html", "puanlama.html"}
    yazilan_adlar = {x.replace("-Tum-Ilceler", "") for x in liste}
    for ad in dosyalar:                      # 2) büyük ilçe sayfaları
        if not ad.endswith(".html") or ad.endswith("-Tum-Ilceler.html") or ad in atla or ad not in harita:
            continue
        if ad in yazilan_adlar:              # il sayfasıyla aynı ad: il sayfası kalsın
            continue
        try:
            with open(os.path.join(klasor, ad), encoding="utf-8") as f:
                h = f.read()
            if not _populer_ilce_uygun(h, ad):
                continue
            il, ilce = harita[ad]
            cikti = g.populer_sayfa(h, ad, ad=ilce, ust=il)
            if cikti:
                with open(os.path.join(hedef, ad), "w", encoding="utf-8") as f:
                    f.write(cikti)
                liste.append(ad)
                ilce_say += 1
        except Exception as e:
            print(f"{ad}: atlandı ({e})")
    with open(os.path.join(DEPO_KLASORU, "populer.json"), "w", encoding="utf-8") as f:
        json.dump(liste, f, ensure_ascii=False)
    print(f"{il_say} il + {ilce_say} ilçe için 'Neler yenir?' sayfası üretildi (populer/ klasörü).")
    if not liste:
        return
    git(["add", "-A"], cwd=DEPO_KLASORU)
    git(["-c", "user.name=Local Radar", "-c", "user.email=local-radar@users.noreply.github.com",
         "commit", "-m", "Neler yenir? popüler yerler sayfaları"], cwd=DEPO_KLASORU)
    rc, out = git(["push"], cwd=DEPO_KLASORU, zaman=900)
    if rc != 0:
        git(["pull", "--rebase", "--autostash"], cwd=DEPO_KLASORU)
        rc, out = git(["push"], cwd=DEPO_KLASORU, zaman=900)
    print("GitHub'a yüklendi." if rc == 0 else f"Yükleme başarısız: {out[:300]}")


def eksik_illeri_listele():
    """Menü 9: 'Tüm İlçeler' rehberi henüz olmayan illeri ve her biri için taranmış/taranmamış ilçeleri yazar."""
    if not depo_hazirla():
        print("Depo hazırlanamadı.")
        return
    git(["pull", "--rebase", "--autostash"], cwd=DEPO_KLASORU)
    klasor = os.path.join(DEPO_KLASORU, DEPO_ALT_KLASOR) if DEPO_ALT_KLASOR else DEPO_KLASORU
    dosyalar = {x.lower() for x in os.listdir(klasor)}
    eksik = [il for il in IL_ILCE if (_temiz(il) + "-Tum-Ilceler.html").lower() not in dosyalar]
    print(f"\n{len(IL_ILCE) - len(eksik)} ilin 'Tüm İlçeler' rehberi var, {len(eksik)} ilin yok.\n")
    for il in eksik:
        ilceler = IL_ILCE[il]
        var = [i for i in ilceler if any(d.startswith(_temiz(i).lower()) for d in dosyalar)]
        print(f"- {il}: {len(var)}/{len(ilceler)} ilçe taranmış" + (f" ({', '.join(var)})" if var else ""))
    if eksik:
        print("\nBunlar için gece taramasına 'İl/İlçe:15' satırı ekleyebilirsin (örn. " + f"{eksik[0]}/{IL_ILCE[eksik[0]][0]}:15)")


# ---------- tarama ----------
def alan_hesapla(il, ilce, km=None):
    if g.fold(ilce) in g.BILINEN_YERLER:
        e, b, r = g.BILINEN_YERLER[g.fold(ilce)]
        return e, b, (km or r)
    for _ in range(3):
        s = g.yer_bul(f"{ilce}, {il}", f"{ilce} ilçesi, {il}")
        if s:
            e, b, r = s
            r = km or max(r, MIN_YARICAP_KM)
            try:                                           # bulunan nokta ilçenin dışındaysa sınırdan düzelt
                at = _atayici()
                a2 = at.alan(il, ilce) if at else None
                if a2 and not at.icinde_mi(a2[3], e, b):
                    log(f"   UYARI: Haritadan bulunan nokta {ilce} sınırının dışında; ilçe sınırından merkez alınıyor.")
                    e, b = a2[0], a2[1]
                    r = km or min(25.0, max(MIN_YARICAP_KM, a2[2]))
            except Exception:
                pass
            return e, b, r
        time.sleep(10)
    return None


def bekle(dakika, bitis_mi):
    bitis = time.time() + dakika * 60
    while time.time() < bitis:
        if bitis_mi():
            return
        time.sleep(20)


def ilce_tara(il, ilce, slug, s, bitis_mi, km=None):
    alan = alan_hesapla(il, ilce, km)
    if not alan:
        raise RuntimeError(f"'{ilce}, {il}' konumu bulunamadı.")
    enlem, boylam, r = alan
    alanlar = [(enlem, boylam, r, g.zoom_sec(r))]
    log(f"   Alan: {enlem:.4f}, {boylam:.4f} · yarıçap {r} km · {max(1, int(PARALEL_SAYISI))} pencere · tekrar önleme {TEKRAR_ONLEME_GUN} gün")

    kategoriler, bolumler, yemek_sadece = kategorileri_hazirla(s)
    if s.get("tumu"):
        log("   UYARI: Pencerede 'TÜMÜNÜ ARA' seçili; her ilçe çok uzun sürebilir.")

    g.HIZLI_YUKLEME = g.HIZLI_KAYDIRMA = bool(s.get("hizli", True))
    g.PARALEL = max(1, int(PARALEL_SAYISI))
    g.TEKRAR_ONLEME_GUN = max(0, int(TEKRAR_ONLEME_GUN))
    g.VERIMSIZ_ATLA = False

    ayar = dict(
        baslik=f"{ilce} · Local Radar", dosya=slug, ilce=ilce,
        merkez=alanlar[0][:2], yaricap=alanlar[0][2], alanlar=alanlar, bolgeler=[""],
        kategoriler=kategoriler, bolumler=bolumler,
        tam_tarama=True, bolme=bool(s.get("izgara", True)),
        sabit_izgara=bool(s.get("sabit_izgara")), hucre_km=sayi(s.get("hucre_km", 1.0), 1.0),
        kategori_esikleri=s.get("kategori_esikleri") or {},
        yemek_sadece=yemek_sadece,
        alisveris_acik=bool(s.get("alisveris") or s.get("tumu")),
    )
    g.esikleri_yukle(ayar)

    def ilerleme(i, n, m):
        if i % 10 == 1 or i == n:
            log(f"   [{i}/{n}] {m}")

    g.json_eskileri_tasi()
    devam = os.path.exists(f"{g.DOSYA_ARA_KAYIT_PREFIX}{slug}.json")
    if devam:
        log("   Yarım kalmış tarama bulundu, kaldığı yerden devam ediliyor.")

    atlanan = 0
    for deneme in range(len(ENGEL_BEKLEME_DAKIKA) + 2):
        try:
            return g.calistir(
                ayar, ilerleme, bitis_mi, birlestir=True,
                min_puan=sayi(s.get("puan", 0), 0.0), min_oy=sayi(s.get("oy", 0), 0, int),
                mahalle_aktif=bool(s.get("mahalle_bul", True)), ekranda_goster=EKRANDA_GOSTER,
                ham_kullan=None, devam=devam,
            )
        except RuntimeError as e:
            mesaj = str(e)
            engel = "blocking" in mesaj.lower() or "captcha" in mesaj.lower()
            if engel and g.PARALEL > 1 and not atlanan:
                g.PARALEL = 1
                atlanan = 1
                devam = True
                log("   Çoklu pencerede sorun çıktı: bekleme yapmadan tek pencereyle devam ediliyor.")
                continue
            if not engel or (deneme - atlanan) >= len(ENGEL_BEKLEME_DAKIKA):
                raise
            dk = ENGEL_BEKLEME_DAKIKA[deneme - atlanan]
            log(f"   Google engeli göründü. {dk} dakika beklenip kaldığı yerden devam edilecek.")
            telegram(f"⏸️ {ilce}: Google engeli çıktı, {dk} dakika bekleyip devam edecek.")
            bekle(dk, bitis_mi)
            if bitis_mi():
                return None
            devam = True
    return None


def uyku_engelle(ac):
    if os.name != "nt":
        return
    try:
        import ctypes
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000000 | 0x00000001 | 0x00000002 if ac else 0x80000000)
    except Exception:
        pass


def gece_calistir():
    g.LOG = log
    hepsi_ertele_kur()
    bu_calismada_biten = 0
    ilceler = ilceleri_oku()
    durum = durum_oku()
    s = gui_ayarlari()

    bitis = None
    if BITIS_SAATI is not None:
        simdi = datetime.datetime.now()
        bitis = simdi.replace(hour=int(BITIS_SAATI), minute=0, second=0, microsecond=0)
        if bitis <= simdi:
            bitis += datetime.timedelta(days=1)
        log(f"Durma zamanı: {bitis:%d.%m %H:%M}")
    bitis_mi = lambda: bool(bitis and datetime.datetime.now() >= bitis)

    kalan = [(il, ilce, km) for il, ilce, km in ilceler if not bitti_mi(il, ilce, km, durum)]
    log(f"Sırada {len(kalan)} ilçe var (listede toplam {len(ilceler)}).")
    telegram(f"📡 Gece taraması başladı. Sırada {len(kalan)} ilçe var.")
    depo_ok = depo_hazirla()
    if not depo_ok:
        log("GitHub deposu hazır değil; taramalar yapılacak, yükleme sonra denenecek.")

    uyku_engelle(True)
    try:
        bekleyenleri_yukle(durum)
        for sira, (il, ilce, km) in enumerate(kalan, 1):
            if bitis_mi():
                log("Sabah oldu, yeni ilçe başlatılmıyor.")
                break
            slug = slug_yap(ilce, il)
            anahtar = anahtar_yap(il, ilce, km)
            if km:
                log(f"━━ {ilce} ({il}) taraması başlıyor ━━  [yarıçap {km:g} km ile yeniden tarama]")
                # İlk kez bu yarıçapla başlıyorsa eski yarım-kalan kaydı sil (baştan taransın);
                # daha önce bu yarıçapla başlayıp yarım kaldıysa kaldığı yerden devam eder.
                basladi = durum.setdefault("km_basladi", [])
                if anahtar not in basladi:
                    try:
                        os.remove(f"{g.DOSYA_ARA_KAYIT_PREFIX}{slug}.json")
                    except OSError:
                        pass
                    basladi.append(anahtar)
                    durum_yaz(durum)
            else:
                log(f"━━ {ilce} ({il}) taraması başlıyor ━━")
            telegram(f"🔎 {ilce} ({il}) taraması başladı. [{sira}/{len(kalan)}]"
                     + (f" (yarıçap {km:g} km ile yeniden tarama)" if km else ""))
            t0 = time.time()
            try:
                ozet = ilce_tara(il, ilce, slug, s, bitis_mi, km)
            except Exception:
                log("   HATA, bu ilçe atlanıyor:\n" + traceback.format_exc())
                telegram(f"⚠️ {ilce} ({il}) taranırken hata oldu, atlandı. Ayrıntı gece_log.txt içinde.")
                continue
            if bitis_mi():
                log(f"   {ilce} yarım kaldı; bir sonraki çalıştırmada devam edecek.")
                break
            if not ozet:
                log(f"   {ilce} için sonuç çıkmadı, atlanıyor.")
                continue
            log(f"   {ilce} bitti: {ozet['adet']} yer ({(time.time() - t0) / 3600:.1f} saat)")
            telegram(f"📍 {ilce} ({il}) taraması bitti: {ozet['adet']} yer, "
                     f"{(time.time() - t0) / 60:.0f} dakika sürdü. GitHub'a yükleniyor...")
            if anahtar not in durum["bitenler"]:
                durum["bitenler"].append(anahtar)
            if km and slug not in durum["bitenler"]:
                durum["bitenler"].append(slug)
            bu_calismada_biten += 1
            ADETLER[slug] = ozet["adet"]
            durum["yuklenmemis"][slug] = ozet["html"]
            durum_yaz(durum)
            bekleyenleri_yukle(durum)
            il_birlestir_ve_yukle(il, durum)      # ilin "Tüm İlçeler" birleşik rehberini güncelle
        bekleyenleri_yukle(durum)
        if HEPSI_SONUNDA_YENILE and bu_calismada_biten and not bitis_mi():
            try:
                log("HEPSİ dosyaları (local_radar_all.*) bir kere yenileniyor, birkaç dakika sürebilir...")
                _HEPSI_ERTELE["acik"] = False
                g.MIN_PUAN = sayi(s.get("puan", 0), 0.0)
                g.MIN_OY = sayi(s.get("oy", 0), 0, int)
                n = g.hepsi_yenile({})
                log(f"HEPSİ dosyaları hazır ({n} yer).")
            except Exception:
                log("HEPSİ yenilenemedi (taramalar etkilenmedi):\n" + traceback.format_exc())
    finally:
        uyku_engelle(False)
    kalan_son = [i for l, i, k in ilceler if not bitti_mi(l, i, k, durum)]
    log(f"Bitti. Tamamlanan: {len(durum['bitenler'])} · Kalan: {len(kalan_son)}")
    telegram(f"🏁 Gece taraması bitti. Bu çalışmada {bu_calismada_biten} ilçe tamamlandı, listede kalan: {len(kalan_son)}.")
    if durum["yuklenmemis"]:
        log("Yüklenemeyen dosyalar var; bir sonraki çalıştırmada tekrar denenecek.")


def github_giris_testi():
    print("GitHub giriş testi. Bir tarayıcı penceresi açılırsa GitHub hesabınla giriş yap.\n")
    if not depo_hazirla(etkilesim=True):
        return
    rc, out = git(["push"], cwd=DEPO_KLASORU, etkilesim=True, zaman=300)
    print(out or "(çıktı yok)")
    print("\nBAŞARILI: giriş çalışıyor." if rc == 0 else "\nSORUN VAR: yukarıdaki mesajı bana gönder.")


def hepsini_sirayla():
    """Menü 10: 5 → 7 → 8'i sırayla çalıştırır. Biri hata verirse yazar ve sıradakine geçer. Bitince Telegram'a haber verir."""
    adimlar = [("Tüm İlçeler rehberleri", tum_illeri_birlestir),
               ("Rehber sayfalarını güncelleme", en_iyi_ekle_hepsine),
               ("'Neler yenir?' sayfaları", populer_sayfalar_uret)]
    sonuc = []
    for ad, fonk in adimlar:
        print(f"\n===== {ad} başlıyor =====")
        try:
            fonk()
            sonuc.append(f"✅ {ad}")
        except Exception:
            print(traceback.format_exc())
            sonuc.append(f"⚠️ {ad}: hata oldu (ayrıntı pencerede)")
    ozet = "Local Radar toplu işlem bitti:\n" + "\n".join(sonuc)
    print("\n" + ozet)
    try:
        telegram(ozet)
    except Exception:
        pass


def kurulum_menusu():
    print("\nKurulum ve testler\n")
    print("  1 = GitHub giriş testi (ilk kurulumda bir kere)")
    print("  2 = Telegram deneme mesajı")
    print("  3 = Telegram chat numaramı otomatik bul ve dosyaya yaz")
    print("  Enter = geri dön\n")
    sec = input("Seçim: ").strip()
    if sec == "1":
        github_giris_testi()
    elif sec == "2":
        telegram_testi()
    elif sec == "3":
        telegram_chat_id_bul()


def ilce_ata_raporu():
    """Menü 8: GitHub'daki rehber klasöründen mekanların gerçek ilçesini hesaplar, sadece rapor üretir."""
    try:
        import ilce_ata
    except Exception as e:
        print(f"ilce_ata.py bulunamadı ya da açılamadı: {e}\nBu dosya gece_tarama.py ile aynı klasörde olmalı.")
        return
    if not depo_hazirla():
        print("Depo hazırlanamadı.")
        return
    git(["pull", "--rebase", "--autostash"], cwd=DEPO_KLASORU)
    klasor = os.path.join(DEPO_KLASORU, DEPO_ALT_KLASOR) if DEPO_ALT_KLASOR else DEPO_KLASORU
    try:
        ilce_ata.rapor(klasor, IL_ILCE, _ilce_dosya_haritasi(merkez=True), cikti_klasoru=KLASOR)
    except ImportError:
        print("Bir paket eksik. Komut satırına şunu yaz:  pip install shapely")
    except Exception:
        print("Rapor hatası:\n" + traceback.format_exc())


def _menu_goster():
    print("\nLocal Radar · Gece Taraması\n")
    print("  1 = Gece taramasını başlat")
    print("  2 = TÜM güncellemeleri yap (Tüm İlçeler rehberleri → rehber sayfaları → Neler yenir?) ve Telegram'a haber ver")
    print("  3 = Sadece 'Tüm İlçeler' birleşik rehberlerini oluştur")
    print("  4 = Sadece mevcut rehber sayfalarını güncelle")
    print("  5 = Sadece 'Neler yenir?' sayfalarını üret (iller + büyük ilçeler)")
    print("  6 = Eksik illeri listele (Tüm İlçeler rehberi olmayan iller)")
    print("  7 = Kurulum ve testler (GitHub giriş, Telegram)")
    print("  8 = İlçe ataması RAPORU (sınır verisini indirir, rehberlere HİÇBİR ŞEY yazmaz)")
    print("  9 = İlçe rehberlerini gerçek ilçelerine göre YENİDEN KUR (önce önizleme, sonra yükleme sorar)")
    print("  0 = Çıkış\n")


def _gece_calistir_guvenli():
    try:
        gece_calistir()
    except KeyboardInterrupt:
        log("Kullanıcı durdurdu.")
    except Exception:
        log("BEKLENMEYEN HATA:\n" + traceback.format_exc())


def main():
    # Kısayol/zamanlanmış görev parametreleri: tek seferlik çalışır
    if "--baslat" in sys.argv:
        _gece_calistir_guvenli()
        return
    if "--giris" in sys.argv:
        github_giris_testi()
        input("\nKapatmak için Enter'a bas...")
        return
    # Normal kullanım: iş bitince menüye döner, 0 ile çıkılır
    while True:
        _menu_goster()
        secim = input("Seçim (0-9): ").strip()
        try:
            if secim == "0":
                return
            elif secim == "7":
                kurulum_menusu()
            elif secim == "8":
                ilce_ata_raporu()
            elif secim == "9":
                ilce_rehberlerini_duzelt()
            elif secim == "6":
                eksik_illeri_listele()
            elif secim == "5":
                populer_sayfalar_uret()
            elif secim == "4":
                en_iyi_ekle_hepsine()
            elif secim == "3":
                tum_illeri_birlestir()
            elif secim == "2":
                hepsini_sirayla()
            elif secim == "1":
                _gece_calistir_guvenli()
            else:
                print("Geçersiz seçim, 0-9 arası bir sayı yaz.")
        except KeyboardInterrupt:
            print("\nDurduruldu.")
        except Exception:
            print("HATA:\n" + traceback.format_exc())
        print("\n" + "-" * 50)


if __name__ == "__main__":
    main()
