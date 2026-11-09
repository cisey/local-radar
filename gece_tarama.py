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
TEKRAR_ONLEME_GUN = 60               # Bu kadar gün içinde taranmış arama karelerini tekrar arama (0 = kapalı)
ENGEL_BEKLEME_DAKIKA = [30, 60]      # Google engellerse bu kadar bekleyip devam eder
GITHUB_DEPO = "https://github.com/cisey/LocalRadar.git"   # sitenin deposu (cisey.github.io/LocalRadar)
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
GA_KODU = "G-8E6VV7GT3C"   # Google Analytics ölçüm kimliği
SITE_ADRESI = "https://cisey.github.io/LocalRadar"
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
        if GA_KODU not in _h:
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
MANUEL_TUM_KORU = {"Gaziantep", "İstanbul", "Kilis"}

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


def il_birlestir(il):
    """İlin tüm ilçe taramalarını tek rehberde toplar, aynı mekanı bir kez yazar.
    En az 2 ilçe yoksa None. Başarılıysa (slug, html_yolu, yer_sayisi) döner."""
    n_il = _nrm(il)
    paylar = {s: y for s, y in tarama_klasorleri().items() if il_bul(s) and _nrm(il_bul(s)) == n_il}
    if len(paylar) < 2:
        return None

    satirlar, merkezler = {}, {}
    for slug, yol in paylar.items():
        rows = json.load(open(yol, encoding="utf-8"))
        for r in rows:
            if r.get("_puansiz"):                        # kayıtta boş saklanıyor, rehber için sayıya çevir
                r["Puan"], r["Yorum Sayısı"], r["Güvenilir Skor"] = 0.0, 0, 0.0
        satirlar[slug] = rows
        nok = [(r["Enlem"], r["Boylam"]) for r in rows
               if isinstance(r.get("Enlem"), (int, float)) and isinstance(r.get("Boylam"), (int, float))]
        merkezler[slug] = (sum(a for a, _ in nok) / len(nok), sum(b for _, b in nok) / len(nok)) if nok else None

    def uzaklik(slug, r):
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


# ---------- tarama ----------
def alan_hesapla(il, ilce, km=None):
    if g.fold(ilce) in g.BILINEN_YERLER:
        e, b, r = g.BILINEN_YERLER[g.fold(ilce)]
        return e, b, (km or r)
    for _ in range(3):
        s = g.yer_bul(f"{ilce}, {il}", f"{ilce} ilçesi, {il}")
        if s:
            e, b, r = s
            return e, b, (km or max(r, MIN_YARICAP_KM))
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


def main():
    if "--baslat" in sys.argv:
        secim = "1"
    elif "--giris" in sys.argv:
        secim = "2"
    else:
        print("Local Radar · Gece Taraması\n")
        print("  1 = Gece taramasını başlat")
        print("  2 = GitHub giriş testi (ilk kurulumda bir kere)")
        print("  3 = Telegram deneme mesajı")
        print("  4 = Telegram chat numaramı otomatik bul ve dosyaya yaz")
        print("  5 = Bütün illerin 'Tüm İlçeler' birleşik rehberlerini şimdi oluştur ve GitHub'a yükle")
        print("  6 = Mevcut bütün rehber sayfalarına Analytics kodunu ekle ve GitHub'a yükle\n")
        secim = input("Seçim (1-6): ").strip()
    if secim == "6":
        analytics_ekle_hepsine()
        input("\nKapatmak için Enter'a bas...")
    elif secim == "5":
        tum_illeri_birlestir()
        input("\nKapatmak için Enter'a bas...")
    elif secim == "4":
        telegram_chat_id_bul()
        input("\nKapatmak için Enter'a bas...")
    elif secim == "3":
        telegram_testi()
        input("\nKapatmak için Enter'a bas...")
    elif secim == "2":
        github_giris_testi()
        input("\nKapatmak için Enter'a bas...")
    else:
        try:
            gece_calistir()
        except KeyboardInterrupt:
            log("Kullanıcı durdurdu.")
        except Exception:
            log("BEKLENMEYEN HATA:\n" + traceback.format_exc())
        if "--baslat" not in sys.argv:
            input("\nKapatmak için Enter'a bas...")


if __name__ == "__main__":
    main()
