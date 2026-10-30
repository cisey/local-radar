"""
Local Radar - Modern GUI (v1.1.0)
Double-click to launch. No terminal needed.
Must be in the SAME folder as local_radar_core.py.
"""
import os, re, sys, json, time, queue, threading, webbrowser, pathlib, csv
import traceback, datetime
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog


# ═══════════════════════════════════════════════════════════
# LANGUAGE / TRANSLATIONS
# ═══════════════════════════════════════════════════════════
METINLER = {
    "tr": {
        "baslik": "📡 Local Radar · v1.1.0",
        "alt_baslik": "Google Haritalar tarama, puanlama ve interaktif rehber oluşturucu",
        "dil": "Dil:",
        "konum_grup": "📍 Konum ve Filtre Ayarları",
        "il": "İl", "ilce": "İlçe", "mahalle": "Mahalle",
        "il_ipucu": "İl seçin veya yazın (Örn: Gaziantep)",
        "ilce_ipucu": "İlçe seçin veya yazın (Örn: Nizip)",
        "mahalle_ipucu": "Tüm ilçe için boş bırakın veya virgülle ayırın (Örn: الفرات, Cumhuriyet)",
        "yaricap": "Yarıçap (km)", "yaricap_ipucu": "Boş = Otomatik",
        "min_puan": "En az puan", "min_yorum": "En az yorum",
        "ozel_arama": "Özel Arama", "ozel_arama_ipucu": "Ekstra anahtar kelime (isteğe bağlı)",
        "tarama_modu": "Tarama Modu:", "hucre_km": "Hücre boyutu (km):",
        "kategoriler": "🗂️ Kategoriler ve Tarama Kapsamı",
        "yemek": "Yemek (Restoran, Kafe)", "gezi": "Gezilecek Yerler",
        "alisveris": "Alışveriş (Market, Giyim)", "saglik": "Sağlık (Hastane, Eczane)",
        "oto": "Oto & Ulaşım (Tamir, Lastik)", "konaklama": "Konaklama (Otel)",
        "banka": "Banka & Kargo", "tumu": "TÜMÜNÜ ARA (DİKKAT: saatler sürebilir!)",
        "secenekler_grup": "⚙️ Tarama Seçenekleri",
        "mahalle_bul": "Yerlerin mahallesini bul", "goster": "Tarayıcı penceresini göster",
        "izgara": "Yoğun yerleri otomatik parçala (kapsamlı)",
        "ham_kullan": "Tarama yapma, son taramayı (ham veri) kullan",
        "devam": "Yarım kalan taramaya devam et",
        "hizli": "Hızlı mod (resim engelle, kısa bekleme)",
        "tekrar": "Son 30 günde yapılan aramaları atla", "verimsiz": "Verimsiz kelimeleri atla",
        "paralel": "Paralel:", "baslat": "▶ Başlat", "durdur": "⏹ Durdur",
        "havuz_sifirla": "🗑️ Havuzu Sıfırla", "manuel_ekle": "➕ Manuel Mekan Ekle",
        "cikti_grup": "📂 Çıktılar ve Harita Rehberleri",
        "klasor_ac": "📁 Klasörü Aç", "excel_ac": "📊 Excel'i Aç", "json_btn": "{ } JSON", "kml_btn": "🌍 KML",
        "ilce_rehberi": "📍 İlçe Haritası", "hepsi_rehberi": "📡 HEPSİ (Local Radar)",
        "sade_rehberi": "🪶 İlçe (Sade)", "hepsi_sade_rehberi": "🪶 HEPSİ (Sade)",
        "kategori_esikleri": "🎚️ Kategori Eşikleri...",
        "profil_kaydet": "💾 Profil Kaydet", "profil_yukle": "📂 Profil Yükle",
        "sure": "Süre: –",
        "hazir": "📡 Local Radar hazır. Çoklu ilçe taramalarında sonuçlar 'local_radar_all.html' dosyasında birikir.",
        "ipucu": "İpucu: 'Tarama yapma, son taramayı kullan' seçeneğiyle mevcut veriyi saniyeler içinde yeniden işleyebilirsiniz.",
        "mod_ozel": "Özel Seçim",
        "mod_hizli": "Hızlı (yemek ve gezi, tek parça)",
        "mod_normal": "Normal (yemek ve gezi, ızgaralı)",
        "mod_yemek": "Sadece yemek (kasap dahil)",
        "mod_kapsamli": "Kapsamlı (her şey, ızgaralı)",
        "mod_sabit": "Sabit ızgara (hücre boyutu km)",
    },
    "en": {
        "baslik": "📡 Local Radar · v1.1.0",
        "alt_baslik": "Google Maps scanner, scorer and interactive guide builder",
        "dil": "Language:",
        "konum_grup": "📍 Location & Filter Settings",
        "il": "City", "ilce": "District", "mahalle": "Neighborhood",
        "il_ipucu": "Select or type city name (e.g. Gaziantep)",
        "ilce_ipucu": "Select or type district name (e.g. Nizip)",
        "mahalle_ipucu": "Leave empty for whole district, or separate with commas",
        "yaricap": "Radius (km)", "yaricap_ipucu": "Empty = Auto",
        "min_puan": "Min rating", "min_yorum": "Min reviews",
        "ozel_arama": "Custom search", "ozel_arama_ipucu": "Extra keywords (optional)",
        "tarama_modu": "Scan mode:", "hucre_km": "Cell size (km):",
        "kategoriler": "🗂️ Categories & Scan Scope",
        "yemek": "Food (Restaurants, Cafes)", "gezi": "Attractions",
        "alisveris": "Shopping (Market, Clothing)", "saglik": "Health (Hospital, Pharmacy)",
        "oto": "Auto & Transport (Repair, Tires)", "konaklama": "Accommodation (Hotel)",
        "banka": "Bank & Cargo", "tumu": "SCAN EVERYTHING (WARNING: may take hours!)",
        "secenekler_grup": "⚙️ Scan Options",
        "mahalle_bul": "Detect neighborhoods", "goster": "Show browser window",
        "izgara": "Auto-split dense areas (comprehensive)",
        "ham_kullan": "Skip scan, use last raw data",
        "devam": "Resume incomplete scan",
        "hizli": "Fast mode (block images, short waits)",
        "tekrar": "Skip searches from last 30 days", "verimsiz": "Skip inefficient keywords",
        "paralel": "Parallel:", "baslat": "▶ Start", "durdur": "⏹ Stop",
        "havuz_sifirla": "🗑️ Reset Pool", "manuel_ekle": "➕ Add Manual Place",
        "cikti_grup": "📂 Outputs & Map Guides",
        "klasor_ac": "📁 Open Folder", "excel_ac": "📊 Open Excel", "json_btn": "{ } JSON", "kml_btn": "🌍 KML",
        "ilce_rehberi": "📍 District Map", "hepsi_rehberi": "📡 ALL (Local Radar)",
        "sade_rehberi": "🪶 District (Simple)", "hepsi_sade_rehberi": "🪶 ALL (Simple)",
        "kategori_esikleri": "🎚️ Category Thresholds...",
        "profil_kaydet": "💾 Save Profile", "profil_yukle": "📂 Load Profile",
        "sure": "Time: –",
        "hazir": "📡 Local Radar ready. Multi-district scans accumulate in 'local_radar_all.html'.",
        "ipucu": "Tip: Use 'Skip scan' to re-process the last scan with different filters in seconds.",
        "mod_ozel": "Custom Selection",
        "mod_hizli": "Fast (food + attractions, single pass)",
        "mod_normal": "Normal (food + attractions, grid)",
        "mod_yemek": "Food only (incl. butcher)",
        "mod_kapsamli": "Comprehensive (everything, grid)",
        "mod_sabit": "Fixed grid (cell size in km)",
    }
}

_aktif_dil = "tr"


def dil_ayarla(dil):
    global _aktif_dil
    if dil in METINLER:
        _aktif_dil = dil


def dil_al():
    return _aktif_dil


def t(anahtar):
    return METINLER.get(_aktif_dil, METINLER["tr"]).get(anahtar, anahtar)


def sure_yaz(sn):
    sn = int(max(sn, 0))
    if sn >= 3600:
        return f"{sn // 3600}h {(sn % 3600) // 60}m"
    if sn >= 60:
        return f"{sn // 60}m {sn % 60:02d}s"
    return f"{sn}s"


def hata_yaz(metin):
    with open("error_log.txt", "a", encoding="utf-8") as f:
        f.write(f"\n[{datetime.datetime.now()}]\n{metin}\n")


KLASOR = os.path.dirname(os.path.abspath(__file__))
os.chdir(KLASOR)
sys.path.insert(0, KLASOR)

try:
    import local_radar_core as g
except Exception as e:
    hata_yaz(f"Module load error: {e}\n{traceback.format_exc()}")

AYAR_DOSYASI = "settings.json"
PROFILLER_DOSYASI = "profiles.json"

# ---------- İl / İlçe verisi ----------
IL_ILCE = {
"Adana": "Aladağ,Ceyhan,Çukurova,Feke,İmamoğlu,Karaisalı,Karataş,Kozan,Pozantı,Saimbeyli,Sarıçam,Seyhan,Tufanbeyli,Yumurtalık,Yüreğir",
"Adıyaman": "Besni,Çelikhan,Gerger,Gölbaşı,Kahta,Merkez,Samsat,Sincik,Tut",
"Afyonkarahisar": "Başmakçı,Bayat,Bolvadin,Çay,Çobanlar,Dazkırı,Dinar,Emirdağ,Evciler,Hocalar,İhsaniye,İscehisar,Kızılören,Merkez,Sandıklı,Sinanpaşa,Sultandağı,Şuhut",
"Ağrı": "Diyadin,Doğubayazıt,Eleşkirt,Hamur,Merkez,Patnos,Taşlıçay,Tutak",
"Aksaray": "Ağaçören,Eskil,Gülağaç,Güzelyurt,Merkez,Ortaköy,Sarıyahşi,Sultanhanı",
"Amasya": "Göynücek,Gümüşhacıköy,Hamamözü,Merkez,Merzifon,Suluova,Taşova",
"Ankara": "Akyurt,Altındağ,Ayaş,Bala,Beypazarı,Çamlıdere,Çankaya,Çubuk,Elmadağ,Etimesgut,Evren,Gölbaşı,Güdül,Haymana,Kahramankazan,Kalecik,Keçiören,Kızılcahamam,Mamak,Nallıhan,Polatlı,Pursaklar,Sincan,Şereflikoçhisar,Yenimahalle",
"Antalya": "Akseki,Aksu,Alanya,Demre,Döşemealtı,Elmalı,Finike,Gazipaşa,Gündoğmuş,İbradı,Kaş,Kemer,Kepez,Konyaaltı,Korkuteli,Kumluca,Manavgat,Muratpaşa,Serik",
"Ardahan": "Çıldır,Damal,Göle,Hanak,Merkez,Posof",
"Artvin": "Ardanuç,Arhavi,Borçka,Hopa,Kemalpaşa,Merkez,Murgul,Şavşat,Yusufeli",
"Aydın": "Bozdoğan,Buharkent,Çine,Didim,Efeler,Germencik,İncirliova,Karacasu,Karpuzlu,Koçarlı,Köşk,Kuşadası,Kuyucak,Nazilli,Söke,Sultanhisar,Yenipazar",
"Balıkesir": "Altıeylül,Ayvalık,Balya,Bandırma,Bigadiç,Burhaniye,Dursunbey,Edremit,Erdek,Gömeç,Gönen,Havran,İvrindi,Karesi,Kepsut,Manyas,Marmara,Savaştepe,Sındırgı,Susurluk",
"Bartın": "Amasra,Kurucaşile,Merkez,Ulus",
"Batman": "Beşiri,Gercüş,Hasankeyf,Kozluk,Merkez,Sason",
"Bayburt": "Aydıntepe,Demirözü,Merkez",
"Bilecik": "Bozüyük,Gölpazarı,İnhisar,Merkez,Osmaneli,Pazaryeri,Söğüt,Yenipazar",
"Bingöl": "Adaklı,Genç,Karlıova,Kiğı,Merkez,Solhan,Yayladere,Yedisu",
"Bitlis": "Adilcevaz,Ahlat,Güroymak,Hizan,Merkez,Mutki,Tatvan",
"Bolu": "Dörtdivan,Gerede,Göynük,Kıbrıscık,Mengen,Merkez,Mudurnu,Seben,Yeniçağa",
"Burdur": "Ağlasun,Altınyayla,Bucak,Çavdır,Çeltikçi,Gölhisar,Karamanlı,Kemer,Merkez,Tefenni,Yeşilova",
"Bursa": "Büyükorhan,Gemlik,Gürsu,Harmancık,İnegöl,İznik,Karacabey,Keles,Kestel,Mudanya,Mustafakemalpaşa,Nilüfer,Orhaneli,Orhangazi,Osmangazi,Yenişehir,Yıldırım",
"Çanakkale": "Ayvacık,Bayramiç,Biga,Bozcaada,Çan,Eceabat,Ezine,Gelibolu,Gökçeada,Lapseki,Merkez,Yenice",
"Çankırı": "Atkaracalar,Bayramören,Çerkeş,Eldivan,Ilgaz,Kızılırmak,Korgun,Kurşunlu,Merkez,Orta,Şabanözü,Yapraklı",
"Çorum": "Alaca,Bayat,Boğazkale,Dodurga,İskilip,Kargı,Laçin,Mecitözü,Merkez,Oğuzlar,Ortaköy,Osmancık,Sungurlu,Uğurludağ",
"Denizli": "Acıpayam,Babadağ,Baklan,Bekilli,Beyağaç,Bozkurt,Buldan,Çal,Çameli,Çardak,Çivril,Güney,Honaz,Kale,Merkezefendi,Pamukkale,Sarayköy,Serinhisar,Tavas",
"Diyarbakır": "Bağlar,Bismil,Çermik,Çınar,Çüngüş,Dicle,Eğil,Ergani,Hani,Hazro,Kayapınar,Kocaköy,Kulp,Lice,Silvan,Sur,Yenişehir",
"Düzce": "Akçakoca,Cumayeri,Çilimli,Gölyaka,Gümüşova,Kaynaşlı,Merkez,Yığılca",
"Edirne": "Enez,Havsa,İpsala,Keşan,Lalapaşa,Meriç,Merkez,Süloğlu,Uzunköprü",
"Elazığ": "Ağın,Alacakaya,Arıcak,Baskil,Harput,Karakoçan,Keban,Kovancılar,Maden,Merkez,Palu,Sivrice",
"Erzincan": "Çayırlı,İliç,Kemah,Kemaliye,Merkez,Otlukbeli,Refahiye,Tercan,Üzümlü",
"Erzurum": "Aşkale,Aziziye,Çat,Hınıs,Horasan,İspir,Karaçoban,Karayazı,Köprüköy,Narman,Oltu,Olur,Palandöken,Pasinler,Pazaryolu,Şenkaya,Tekman,Tortum,Uzundere,Yakutiye",
"Eskişehir": "Alpu,Beylikova,Çifteler,Günyüzü,Han,İnönü,Mahmudiye,Mihalgazi,Mihalıççık,Odunpazarı,Sarıcakaya,Seyitgazi,Sivrihisar,Tepebaşı",
"Gaziantep": "Araban,İslahiye,Karkamış,Nizip,Nurdağı,Oğuzeli,Şahinbey,Şehitkamil,Yavuzeli",
"Giresun": "Alucra,Bulancak,Çamoluk,Çanakçı,Dereli,Doğankent,Espiye,Eynesil,Görele,Güce,Keşap,Merkez,Piraziz,Şebinkarahisar,Tirebolu,Yağlıdere",
"Gümüşhane": "Kelkit,Köse,Kürtün,Merkez,Şiran,Torul",
"Hakkari": "Çukurca,Derecik,Merkez,Şemdinli,Yüksekova",
"Hatay": "Altınözü,Antakya,Arsuz,Belen,Defne,Dörtyol,Erzin,Hassa,İskenderun,Kırıkhan,Kumlu,Payas,Reyhanlı,Samandağ,Yayladağı",
"Iğdır": "Aralık,Karakoyunlu,Merkez,Tuzluca",
"Isparta": "Aksu,Atabey,Eğirdir,Gelendost,Gönen,Keçiborlu,Merkez,Senirkent,Sütçüler,Şarkikaraağaç,Uluborlu,Yalvaç,Yenişarbademli",
"İstanbul": "Adalar,Arnavutköy,Ataşehir,Avcılar,Bağcılar,Bahçelievler,Bakırköy,Başakşehir,Bayrampaşa,Beşiktaş,Beykoz,Beylikdüzü,Beyoğlu,Büyükçekmece,Çatalca,Çekmeköy,Esenler,Esenyurt,Eyüpsultan,Fatih,Gaziosmanpaşa,Güngören,Kadıköy,Kağıthane,Kartal,Küçükçekmece,Maltepe,Pendik,Sancaktepe,Sarıyer,Silivri,Sultanbeyli,Sultangazi,Şile,Şişli,Tuzla,Ümraniye,Üsküdar,Zeytinburnu",
"İzmir": "Aliağa,Balçova,Bayındır,Bayraklı,Bergama,Beydağ,Bornova,Buca,Çeşme,Çiğli,Dikili,Foça,Gaziemir,Güzelbahçe,Karabağlar,Karaburun,Karşıyaka,Kemalpaşa,Kınık,Kiraz,Konak,Menderes,Menemen,Narlıdere,Ödemiş,Seferihisar,Selçuk,Tire,Torbalı,Urla",
"Kahramanmaraş": "Afşin,Andırın,Çağlayancerit,Dulkadiroğlu,Ekinözü,Elbistan,Göksun,Nurhak,Onikişubat,Pazarcık,Türkoğlu",
"Karabük": "Eflani,Eskipazar,Merkez,Ovacık,Safranbolu,Yenice",
"Karaman": "Ayrancı,Başyayla,Ermenek,Kazımkarabekir,Merkez,Sarıveliler",
"Kars": "Akyaka,Arpaçay,Digor,Kağızman,Merkez,Sarıkamış,Selim,Susuz",
"Kastamonu": "Abana,Ağlı,Araç,Azdavay,Bozkurt,Cide,Çatalzeytin,Daday,Devrekani,Doğanyurt,Hanönü,İhsangazi,İnebolu,Küre,Merkez,Pınarbaşı,Seydiler,Şenpazar,Taşköprü,Tosya",
"Kayseri": "Akkışla,Bünyan,Develi,Felahiye,Hacılar,İncesu,Kocasinan,Melikgazi,Özvatan,Pınarbaşı,Sarıoğlan,Sarız,Talas,Tomarza,Yahyalı,Yeşilhisar",
"Kilis": "Elbeyli,Merkez,Musabeyli,Polateli",
"Kırıkkale": "Bahşılı,Balışeyh,Çelebi,Delice,Karakeçili,Keskin,Merkez,Sulakyurt,Yahşihan",
"Kırklareli": "Babaeski,Demirköy,Kofçaz,Lüleburgaz,Merkez,Pehlivanköy,Pınarhisar,Vize",
"Kırşehir": "Akçakent,Akpınar,Boztepe,Çiçekdağı,Kaman,Merkez,Mucur",
"Kocaeli": "Başiskele,Çayırova,Darıca,Derince,Dilovası,Gebze,Gölcük,İzmit,Kandıra,Karamürsel,Kartepe,Körfez",
"Konya": "Ahırlı,Akören,Akşehir,Altınekin,Beyşehir,Bozkır,Cihanbeyli,Çeltik,Çumra,Derbent,Derebucak,Doğanhisar,Emirgazi,Ereğli,Güneysınır,Hadim,Halkapınar,Hüyük,Ilgın,Kadınhanı,Karapınar,Karatay,Kulu,Meram,Sarayönü,Selçuklu,Seydişehir,Taşkent,Tuzlukçu,Yalıhüyük,Yunak",
"Kütahya": "Altıntaş,Aslanapa,Çavdarhisar,Domaniç,Dumlupınar,Emet,Gediz,Hisarcık,Merkez,Pazarlar,Simav,Şaphane,Tavşanlı",
"Malatya": "Akçadağ,Arapgir,Arguvan,Battalgazi,Darende,Doğanşehir,Doğanyol,Hekimhan,Kale,Kuluncak,Pütürge,Yazıhan,Yeşilyurt",
"Manisa": "Ahmetli,Akhisar,Alaşehir,Demirci,Gölmarmara,Gördes,Kırkağaç,Köprübaşı,Kula,Salihli,Sarıgöl,Saruhanlı,Selendi,Soma,Şehzadeler,Turgutlu,Yunusemre",
"Mardin": "Artuklu,Dargeçit,Derik,Kızıltepe,Mazıdağı,Midyat,Nusaybin,Ömerli,Savur,Yeşilli",
"Mersin": "Akdeniz,Anamur,Aydıncık,Bozyazı,Çamlıyayla,Erdemli,Gülnar,Mezitli,Mut,Silifke,Tarsus,Toroslar,Yenişehir",
"Muğla": "Bodrum,Dalaman,Datça,Fethiye,Kavaklıdere,Köyceğiz,Marmaris,Menteşe,Milas,Ortaca,Seydikemer,Ula,Yatağan",
"Muş": "Bulanık,Hasköy,Korkut,Malazgirt,Merkez,Varto",
"Nevşehir": "Acıgöl,Avanos,Derinkuyu,Gülşehir,Hacıbektaş,Kozaklı,Merkez,Ürgüp",
"Niğde": "Altunhisar,Bor,Çamardı,Çiftlik,Merkez,Ulukışla",
"Ordu": "Akkuş,Altınordu,Aybastı,Çamaş,Çatalpınar,Çaybaşı,Fatsa,Gölköy,Gülyalı,Gürgentepe,İkizce,Kabadüz,Kabataş,Korgan,Kumru,Mesudiye,Perşembe,Ulubey,Ünye",
"Osmaniye": "Bahçe,Düziçi,Hasanbeyli,Kadirli,Merkez,Sumbas,Toprakkale",
"Rize": "Ardeşen,Çamlıhemşin,Çayeli,Derepazarı,Fındıklı,Güneysu,Hemşin,İkizdere,İyidere,Kalkandere,Merkez,Pazar",
"Sakarya": "Adapazarı,Akyazı,Arifiye,Erenler,Ferizli,Geyve,Hendek,Karapürçek,Karasu,Kaynarca,Kocaali,Pamukova,Sapanca,Serdivan,Söğütlü,Taraklı",
"Samsun": "19 Mayıs,Alaçam,Asarcık,Atakum,Ayvacık,Bafra,Canik,Çarşamba,Havza,İlkadım,Kavak,Ladik,Salıpazarı,Tekkeköy,Terme,Vezirköprü,Yakakent",
"Siirt": "Baykan,Eruh,Kurtalan,Merkez,Pervari,Şirvan,Tillo",
"Sinop": "Ayancık,Boyabat,Dikmen,Durağan,Erfelek,Gerze,Merkez,Saraydüzü,Türkeli",
"Sivas": "Akıncılar,Altınyayla,Divriği,Doğanşar,Gemerek,Gölova,Gürün,Hafik,İmranlı,Kangal,Koyulhisar,Merkez,Suşehri,Şarkışla,Ulaş,Yıldızeli,Zara",
"Şanlıurfa": "Akçakale,Birecik,Bozova,Ceylanpınar,Eyyübiye,Halfeti,Haliliye,Harran,Hilvan,Karaköprü,Siverek,Suruç,Viranşehir",
"Şırnak": "Beytüşşebap,Cizre,Güçlükonak,İdil,Merkez,Silopi,Uludere",
"Tekirdağ": "Çerkezköy,Çorlu,Ergene,Hayrabolu,Kapaklı,Malkara,Marmaraereğlisi,Muratlı,Saray,Süleymanpaşa,Şarköy",
"Tokat": "Almus,Artova,Başçiftlik,Erbaa,Merkez,Niksar,Pazar,Reşadiye,Sulusaray,Turhal,Yeşilyurt,Zile",
"Trabzon": "Akçaabat,Araklı,Arsin,Beşikdüzü,Çarşıbaşı,Çaykara,Dernekpazarı,Düzköy,Hayrat,Köprübaşı,Maçka,Of,Ortahisar,Sürmene,Şalpazarı,Tonya,Vakfıkebir,Yomra",
"Tunceli": "Çemişgezek,Hozat,Mazgirt,Merkez,Nazımiye,Ovacık,Pertek,Pülümür",
"Uşak": "Banaz,Eşme,Karahallı,Merkez,Sivaslı,Ulubey",
"Van": "Bahçesaray,Başkale,Çaldıran,Çatak,Edremit,Erciş,Gevaş,Gürpınar,İpekyolu,Muradiye,Özalp,Saray,Tuşba",
"Yalova": "Altınova,Armutlu,Çınarcık,Çiftlikköy,Merkez,Termal",
"Yozgat": "Akdağmadeni,Aydıncık,Boğazlıyan,Çandır,Çayıralan,Çekerek,Kadışehri,Merkez,Saraykent,Sarıkaya,Sorgun,Şefaatli,Yenifakılı,Yerköy",
"Zonguldak": "Alaplı,Çaycuma,Devrek,Ereğli,Gökçebey,Kilimli,Kozlu,Merkez",
}
ILLER = sorted(IL_ILCE.keys())


def tema_uygula(kok):
    stil = ttk.Style(kok)
    try:
        stil.theme_use("clam")
    except Exception:
        pass

    bg = "#f4f6f9"
    card = "#ffffff"
    ink = "#1f2937"
    mut = "#6b7280"
    line = "#dce1e8"
    primary = "#1a73e8"
    primary_hover = "#1557b0"
    green = "#0b8043"
    green_hover = "#086333"
    danger = "#d93025"

    kok.configure(bg=bg)

    stil.configure(".", background=bg, foreground=ink, font=("Segoe UI", 9))
    stil.configure("TFrame", background=bg)
    stil.configure("Card.TFrame", background=card)
    stil.configure("TLabel", background=bg, foreground=ink, font=("Segoe UI", 9))
    stil.configure("Card.TLabel", background=card, foreground=ink, font=("Segoe UI", 9, "bold"))
    stil.configure("Hint.TLabel", background=card, foreground=mut, font=("Segoe UI", 8))
    stil.configure("Header.TLabel", background=bg, foreground=primary, font=("Segoe UI", 16, "bold"))
    stil.configure("SubHeader.TLabel", background=bg, foreground=mut, font=("Segoe UI", 9))
    stil.configure("Status.TLabel", background=bg, foreground=ink, font=("Segoe UI", 9, "bold"))

    stil.configure("TLabelframe", background=card, bordercolor=line, relief="solid", borderwidth=1)
    stil.configure("TLabelframe.Label", background=card, foreground=primary, font=("Segoe UI", 9, "bold"))

    stil.configure("TCheckbutton", background=card, foreground=ink, font=("Segoe UI", 9))
    stil.map("TCheckbutton", background=[("active", card)])

    stil.configure("TEntry", fieldbackground="#f9fafb", bordercolor=line, lightcolor=line, darkcolor=line, padding=5)
    stil.map("TEntry", bordercolor=[("focus", primary)], lightcolor=[("focus", primary)])

    stil.configure("TCombobox", fieldbackground="#f9fafb", background="#ffffff", bordercolor=line, lightcolor=line, darkcolor=line, padding=4)
    stil.map("TCombobox", bordercolor=[("focus", primary)], fieldbackground=[("readonly", "#f9fafb")])

    stil.configure("TSpinbox", fieldbackground="#f9fafb", bordercolor=line, padding=3)

    # Standart Buton
    stil.configure("TButton", background="#ffffff", foreground=ink, bordercolor=line, lightcolor="#ffffff", darkcolor=line,
                   font=("Segoe UI", 9, "bold"), padding=(10, 5), relief="solid")
    stil.map("TButton",
             background=[("active", "#e8f0fe"), ("disabled", "#f1f3f4")],
             foreground=[("active", primary), ("disabled", "#9aa0a6")],
             bordercolor=[("active", primary), ("disabled", "#e0e0e0")])

    # Başlat Butonu (Yeşil)
    stil.configure("Start.TButton", background=green, foreground="#ffffff", bordercolor=green,
                   lightcolor=green, darkcolor=green, font=("Segoe UI", 9, "bold"), padding=(16, 6))
    stil.map("Start.TButton",
             background=[("active", green_hover), ("disabled", "#a8dab5")],
             foreground=[("disabled", "#ffffff")])

    # Durdur Butonu (Kırmızı)
    stil.configure("Stop.TButton", background=danger, foreground="#ffffff", bordercolor=danger,
                   lightcolor=danger, darkcolor=danger, font=("Segoe UI", 9, "bold"), padding=(12, 6))
    stil.map("Stop.TButton",
             background=[("active", "#b3261e"), ("disabled", "#f1f3f4")],
             foreground=[("disabled", "#9aa0a6")],
             bordercolor=[("disabled", "#e0e0e0")])

    # Vurgulu Rehber Butonu (Mavi)
    stil.configure("Primary.TButton", background=primary, foreground="#ffffff", bordercolor=primary,
                   lightcolor=primary, darkcolor=primary, font=("Segoe UI", 9, "bold"), padding=(11, 5))
    stil.map("Primary.TButton",
             background=[("active", primary_hover), ("disabled", "#f1f3f4")],
             foreground=[("disabled", "#9aa0a6")],
             bordercolor=[("disabled", "#e0e0e0")])

    stil.configure("Horizontal.TProgressbar", troughcolor="#e2e8f0", background=primary, bordercolor="#e2e8f0", lightcolor=primary, darkcolor=primary, thickness=8)


class Pencere:
    def __init__(self, kok):
        self.kok = kok
        tema_uygula(kok)
        self.dil = tk.StringVar(value=_aktif_dil)
        kok.title(t("baslik"))
        kok.geometry("880x820")
        kok.minsize(780, 740)
        self.kuyruk = queue.Queue()
        self.durdur = threading.Event()
        self.ozet = None
        self.t0 = None
        self.son_ilerleme = (0, 0)
        self.damgalar = []
        self._tumu_guncelle = False
        self.kategori_esikleri = {k: dict(v) for k, v in getattr(g, 'VARSAYILAN_ESIKLER', {}).items()} if 'g' in globals() else {}

        if 'g' in globals():
            g.LOG = lambda m: self.kuyruk.put(("log", str(m)))

        ana = ttk.Frame(kok, padding=(16, 12, 16, 14))
        ana.pack(fill="both", expand=True)
        ana.columnconfigure(0, weight=1)

        # ── 1. ÜST BAŞLIK (HEADER) ──
        ust = ttk.Frame(ana)
        ust.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        ust.columnconfigure(0, weight=1)

        baslik_sol = ttk.Frame(ust)
        baslik_sol.grid(row=0, column=0, sticky="w")
        ttk.Label(baslik_sol, text=t("baslik"), style="Header.TLabel").pack( anchor="w")
        ttk.Label(baslik_sol, text=t("alt_baslik"), style="SubHeader.TLabel").pack(anchor="w")

        baslik_sag = ttk.Frame(ust)
        baslik_sag.grid(row=0, column=1, sticky="e")
        ttk.Button(baslik_sag, text=t("profil_kaydet"), command=self.profil_kaydet).pack(side="left", padx=(0, 6))
        ttk.Button(baslik_sag, text=t("profil_yukle"), command=self.profil_yukle).pack(side="left", padx=(0, 12))
        ttk.Label(baslik_sag, text=t("dil")).pack(side="left", padx=(0, 4))
        self.dil_kutu = ttk.Combobox(baslik_sag, textvariable=self.dil, values=["tr", "en"], state="readonly", width=4)
        self.dil_kutu.pack(side="left")
        self.dil_kutu.bind("<<ComboboxSelected>>", self.dil_degisti)

        # ── 2. KONUM VE FİLTRE KARTI ──
        konum_kart = ttk.LabelFrame(ana, text=f"  {t('konum_grup')}  ", padding=(12, 8))
        konum_kart.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        for c in (1, 3):
            konum_kart.columnconfigure(c, weight=1)

        self.il = tk.StringVar(value="")
        self.ilce = tk.StringVar(value="")
        self.mahalle = tk.StringVar(value="")
        self.yaricap = tk.StringVar(value="")
        self.puan = tk.StringVar(value="0")
        self.oy = tk.StringVar(value="0")
        self.ozel_arama = tk.StringVar(value="")

        # Satır 0: İl & İlçe yan yana
        ttk.Label(konum_kart, text=t("il"), style="Card.TLabel").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=3)
        self.il_kutu = ttk.Combobox(konum_kart, textvariable=self.il, values=[""] + ILLER)
        self.il_kutu.grid(row=0, column=1, sticky="ew", padx=(0, 16), pady=3)

        ttk.Label(konum_kart, text=t("ilce"), style="Card.TLabel").grid(row=0, column=2, sticky="w", padx=(0, 8), pady=3)
        self.ilce_kutu = ttk.Combobox(konum_kart, textvariable=self.ilce, values=[])
        self.ilce_kutu.grid(row=0, column=3, sticky="ew", pady=3)

        ttk.Label(konum_kart, text=t("il_ipucu"), style="Hint.TLabel").grid(row=1, column=1, sticky="w", padx=(0, 16), pady=(0, 4))
        ttk.Label(konum_kart, text=t("ilce_ipucu"), style="Hint.TLabel").grid(row=1, column=3, sticky="w", pady=(0, 4))

        # Satır 2: Mahalle (tam genişlik)
        ttk.Label(konum_kart, text=t("mahalle"), style="Card.TLabel").grid(row=2, column=0, sticky="w", padx=(0, 8), pady=3)
        ttk.Entry(konum_kart, textvariable=self.mahalle).grid(row=2, column=1, columnspan=3, sticky="ew", pady=3)
        ttk.Label(konum_kart, text=t("mahalle_ipucu"), style="Hint.TLabel").grid(row=3, column=1, columnspan=3, sticky="w", pady=(0, 4))

        # Satır 4: Yarıçap, En Az Puan, En Az Yorum, Özel Arama (kompakt şerit)
        filtre_serit = ttk.Frame(konum_kart, style="Card.TFrame")
        filtre_serit.grid(row=4, column=0, columnspan=4, sticky="ew", pady=(2, 2))
        filtre_serit.columnconfigure(7, weight=1)

        ttk.Label(filtre_serit, text=t("yaricap"), style="Card.TLabel").grid(row=0, column=0, sticky="w", padx=(0, 6))
        ttk.Entry(filtre_serit, textvariable=self.yaricap, width=10).grid(row=0, column=1, sticky="w", padx=(0, 14))

        ttk.Label(filtre_serit, text=t("min_puan"), style="Card.TLabel").grid(row=0, column=2, sticky="w", padx=(0, 6))
        ttk.Entry(filtre_serit, textvariable=self.puan, width=8).grid(row=0, column=3, sticky="w", padx=(0, 14))

        ttk.Label(filtre_serit, text=t("min_yorum"), style="Card.TLabel").grid(row=0, column=4, sticky="w", padx=(0, 6))
        ttk.Entry(filtre_serit, textvariable=self.oy, width=8).grid(row=0, column=5, sticky="w", padx=(0, 14))

        ttk.Label(filtre_serit, text=t("ozel_arama"), style="Card.TLabel").grid(row=0, column=6, sticky="w", padx=(0, 6))
        ttk.Entry(filtre_serit, textvariable=self.ozel_arama).grid(row=0, column=7, sticky="ew")

        def ilce_doldur(*_):
            il = self.il.get().strip()
            self.ilce_kutu.configure(values=IL_ILCE.get(il, "").split(",") if il in IL_ILCE else [])
        self.il.trace_add("write", ilce_doldur)
        ilce_doldur()

        # ── 3. KATEGORİLER VE TARAMA MODU KARTI ──
        kat_frame = ttk.LabelFrame(ana, text=f"  {t('kategoriler')}  ", padding=(12, 8))
        kat_frame.grid(row=2, column=0, sticky="ew", pady=(0, 8))
        for c in range(4):
            kat_frame.columnconfigure(c, weight=1)

        mod_frame = ttk.Frame(kat_frame, style="Card.TFrame")
        mod_frame.grid(row=0, column=0, columnspan=4, sticky="ew", pady=(0, 8))
        ttk.Label(mod_frame, text=t("tarama_modu"), style="Card.TLabel").pack(side="left", padx=(0, 8))
        self.mod_var = tk.StringVar(value=t("mod_ozel"))
        self.mod_kutu = ttk.Combobox(
            mod_frame,
            textvariable=self.mod_var,
            values=[t("mod_ozel"), t("mod_hizli"), t("mod_normal"), t("mod_yemek"), t("mod_kapsamli"), t("mod_sabit")],
            state="readonly",
            width=34,
        )
        self.mod_kutu.pack(side="left")
        self.mod_kutu.bind("<<ComboboxSelected>>", self.mod_degisti)

        self.sabit_izgara = tk.BooleanVar(value=False)
        self.hucre_km = tk.StringVar(value="1.0")
        ttk.Label(mod_frame, text="   " + t("hucre_km"), style="Card.TLabel").pack(side="left", padx=(10, 6))
        self.hucre_km_entry = ttk.Entry(mod_frame, textvariable=self.hucre_km, width=8, state="disabled")
        self.hucre_km_entry.pack(side="left")

        self.yemek = tk.BooleanVar(value=True)
        self.gezi = tk.BooleanVar(value=True)
        self.alisveris = tk.BooleanVar(value=False)
        self.saglik = tk.BooleanVar(value=False)
        self.oto = tk.BooleanVar(value=False)
        self.konaklama = tk.BooleanVar(value=False)
        self.banka = tk.BooleanVar(value=False)
        self.kategoriler = {"yemek": self.yemek, "gezi": self.gezi, "alisveris": self.alisveris,
                            "saglik": self.saglik, "oto": self.oto, "konaklama": self.konaklama,
                            "banka": self.banka}
        self.tumu = tk.BooleanVar(value=False)

        ttk.Checkbutton(kat_frame, text=t("yemek"), variable=self.yemek).grid(row=1, column=0, sticky="w", pady=3)
        ttk.Checkbutton(kat_frame, text=t("gezi"), variable=self.gezi).grid(row=1, column=1, sticky="w", pady=3)
        ttk.Checkbutton(kat_frame, text=t("alisveris"), variable=self.alisveris).grid(row=1, column=2, sticky="w", pady=3)
        ttk.Checkbutton(kat_frame, text=t("saglik"), variable=self.saglik).grid(row=1, column=3, sticky="w", pady=3)
        ttk.Checkbutton(kat_frame, text=t("oto"), variable=self.oto).grid(row=2, column=0, sticky="w", pady=3)
        ttk.Checkbutton(kat_frame, text=t("konaklama"), variable=self.konaklama).grid(row=2, column=1, sticky="w", pady=3)
        ttk.Checkbutton(kat_frame, text=t("banka"), variable=self.banka).grid(row=2, column=2, sticky="w", pady=3)

        tumu_satir = ttk.Frame(kat_frame, style="Card.TFrame")
        tumu_satir.grid(row=3, column=0, columnspan=4, sticky="w", pady=(6, 0))
        self.tumu_cb = ttk.Checkbutton(tumu_satir, text="", variable=self.tumu)
        self.tumu_cb.pack(side="left")
        self.tumu_etiket = tk.Label(
            tumu_satir,
            text=t("tumu"),
            fg="#d93025",
            bg="#ffffff",
            font=("Segoe UI", 9, "bold"),
            cursor="hand2",
        )
        self.tumu_etiket.pack(side="left", padx=(2, 0))
        self.tumu_etiket.bind("<Button-1>", lambda _e: self.tumu.set(not self.tumu.get()))

        def tumu_degisti(*_):
            if self._tumu_guncelle: return
            if self.tumu.get():
                self._tumu_guncelle = True
                for v in self.kategoriler.values(): v.set(True)
                self._tumu_guncelle = False
                self.mod_var.set(t("mod_ozel"))

        def kategori_degisti(*_):
            if self._tumu_guncelle: return
            hepsi_secili = all(v.get() for v in self.kategoriler.values())
            if self.tumu.get() and not hepsi_secili:
                self._tumu_guncelle = True
                self.tumu.set(False)
                self._tumu_guncelle = False
            self.mod_var.set(t("mod_ozel"))

        self.tumu.trace_add("write", tumu_degisti)
        for v in self.kategoriler.values():
            v.trace_add("write", kategori_degisti)

        # ── 4. TARAMA SEÇENEKLERİ KARTI ──
        sec_kart = ttk.LabelFrame(ana, text=f"  {t('secenekler_grup')}  ", padding=(12, 8))
        sec_kart.grid(row=3, column=0, sticky="ew", pady=(0, 8))
        for c in range(3):
            sec_kart.columnconfigure(c, weight=1)

        self.mahalle_bul = tk.BooleanVar(value=True)
        self.goster = tk.BooleanVar(value=True)
        self.izgara = tk.BooleanVar(value=True)
        self.ham = tk.BooleanVar(value=False)
        self.devam = tk.BooleanVar(value=False)
        self.hizli = tk.BooleanVar(value=True)
        self.paralel = tk.IntVar(value=1)
        self.tekrar = tk.BooleanVar(value=False)
        self.verimsiz = tk.BooleanVar(value=False)

        ttk.Checkbutton(sec_kart, text=t("mahalle_bul"), variable=self.mahalle_bul).grid(row=0, column=0, sticky="w", pady=2)
        ttk.Checkbutton(sec_kart, text=t("goster"), variable=self.goster).grid(row=0, column=1, sticky="w", pady=2)
        ttk.Checkbutton(sec_kart, text=t("izgara"), variable=self.izgara).grid(row=0, column=2, sticky="w", pady=2)

        ttk.Checkbutton(sec_kart, text=t("ham_kullan"), variable=self.ham).grid(row=1, column=0, sticky="w", pady=2)
        ttk.Checkbutton(sec_kart, text=t("devam"), variable=self.devam).grid(row=1, column=1, sticky="w", pady=2)
        ttk.Checkbutton(sec_kart, text=t("hizli"), variable=self.hizli).grid(row=1, column=2, sticky="w", pady=2)

        ttk.Checkbutton(sec_kart, text=t("tekrar"), variable=self.tekrar).grid(row=2, column=0, sticky="w", pady=2)
        ttk.Checkbutton(sec_kart, text=t("verimsiz"), variable=self.verimsiz).grid(row=2, column=1, sticky="w", pady=2)

        p_kutu = ttk.Frame(sec_kart, style="Card.TFrame")
        p_kutu.grid(row=2, column=2, sticky="w", pady=2)
        ttk.Label(p_kutu, text=t("paralel"), style="Card.TLabel").pack(side="left", padx=(0, 6))
        ttk.Spinbox(p_kutu, from_=1, to=3, width=4, textvariable=self.paralel).pack(side="left")

        # ── 5. İŞLEM VE ÇIKTI BUTONLARI (2 AYRI SATIR, HİÇBİR BUTON GİZLENMEZ) ──
        aksiyon_bar = ttk.Frame(ana)
        aksiyon_bar.grid(row=4, column=0, sticky="ew", pady=(2, 6))

        self.baslat = ttk.Button(aksiyon_bar, text=t("baslat"), style="Start.TButton", command=self.baslat_tikla)
        self.baslat.pack(side="left")
        self.dur = ttk.Button(aksiyon_bar, text=t("durdur"), style="Stop.TButton", command=self.durdur_tikla, state="disabled")
        self.dur.pack(side="left", padx=(8, 16))

        self.esik_btn = ttk.Button(aksiyon_bar, text=t("kategori_esikleri"), command=self.kategori_esikleri_penceresi)
        self.esik_btn.pack(side="left", padx=(0, 8))
        self.manuel_btn = ttk.Button(aksiyon_bar, text=t("manuel_ekle"), command=self.manuel_penceresi)
        self.manuel_btn.pack(side="left", padx=(0, 8))
        self.havuz_sifirla = ttk.Button(aksiyon_bar, text=t("havuz_sifirla"), command=self.havuz_temizle)
        self.havuz_sifirla.pack(side="left")

        cikti_kart = ttk.LabelFrame(ana, text=f"  {t('cikti_grup')}  ", padding=(12, 8))
        cikti_kart.grid(row=5, column=0, sticky="ew", pady=(0, 8))

        self.rehber = ttk.Button(cikti_kart, text=t("ilce_rehberi"), style="Primary.TButton", command=lambda: self.ac("html"), state="disabled")
        self.rehber.pack(side="left", padx=(0, 6))
        self.rehber_sade = ttk.Button(cikti_kart, text=t("sade_rehberi"), style="Primary.TButton", command=lambda: self.ac("html_sade"), state="disabled")
        self.rehber_sade.pack(side="left", padx=(0, 12))

        self.hepsi_rehber = ttk.Button(cikti_kart, text=t("hepsi_rehberi"), command=lambda: self.ac("hepsi_html"))
        self.hepsi_rehber.pack(side="left", padx=(0, 6))
        self.hepsi_sade = ttk.Button(cikti_kart, text=t("hepsi_sade_rehberi"), command=lambda: self.ac("hepsi_html_sade"))
        self.hepsi_sade.pack(side="left", padx=(0, 12))

        self.klasor_btn = ttk.Button(cikti_kart, text=t("klasor_ac"), command=lambda: self.ac("klasor"), state="disabled")
        self.klasor_btn.pack(side="right")
        self.excel = ttk.Button(cikti_kart, text=t("excel_ac"), command=lambda: self.ac("xlsx"), state="disabled")
        self.excel.pack(side="right", padx=(0, 6))
        self.json_btn = ttk.Button(cikti_kart, text=t("json_btn"), command=self.json_disari_aktar, state="disabled")
        self.json_btn.pack(side="right", padx=(0, 6))
        self.kml_btn = ttk.Button(cikti_kart, text=t("kml_btn"), command=lambda: self.ac("kml"), state="disabled")
        self.kml_btn.pack(side="right", padx=(0, 6))

        # ── 6. İLERLEME ÇUBUĞU VE KONSOL EKRANI ──
        self.cubuk = ttk.Progressbar(ana, mode="determinate", style="Horizontal.TProgressbar")
        self.cubuk.grid(row=6, column=0, sticky="ew", pady=(2, 4))

        self.sure = ttk.Label(ana, text=t("sure"), style="Status.TLabel")
        self.sure.grid(row=7, column=0, sticky="w", pady=(0, 4))

        log_cerceve = ttk.Frame(ana)
        log_cerceve.grid(row=8, column=0, sticky="nsew")
        log_cerceve.columnconfigure(0, weight=1)
        log_cerceve.rowconfigure(0, weight=1)
        ana.rowconfigure(8, weight=1)

        self.gunluk = tk.Text(
            log_cerceve,
            height=9,
            state="disabled",
            wrap="word",
            bg="#1e293b",
            fg="#e2e8f0",
            insertbackground="#ffffff",
            selectbackground="#3b82f6",
            font=("Consolas", 9),
            relief="flat",
            padx=10,
            pady=8,
        )
        self.gunluk.grid(row=0, column=0, sticky="nsew")
        log_sb = ttk.Scrollbar(log_cerceve, orient="vertical", command=self.gunluk.yview)
        log_sb.grid(row=0, column=1, sticky="ns")
        self.gunluk.configure(yscrollcommand=log_sb.set)

        self.yaz(t("hazir"))
        self.yaz(t("ipucu"))
        kok.after(200, self.kuyruk_oku)

        self.ayarlari_yukle()
        self._openpyxl_acilis_uyarisi()
        kok.protocol("WM_DELETE_WINDOW", self.kapanis)

    def dil_degisti(self, *_):
        yeni = self.dil.get()
        if yeni == dil_al():
            return
        dil_ayarla(yeni)
        self.ayarlari_kaydet()
        self.kok.destroy()
        yeni_kok = tk.Tk()
        yeni_kok.report_callback_exception = lambda t, d, iz: hata_yaz("".join(traceback.format_exception(t, d, iz)))
        yeni_pencere = Pencere(yeni_kok)
        yeni_pencere.dil.set(yeni)
        yeni_kok.mainloop()

    def mod_degisti(self, *_):
        mod = self.mod_var.get()
        self._tumu_guncelle = True
        if mod == t("mod_hizli"):
            self.yemek.set(True); self.gezi.set(True)
            self.alisveris.set(False); self.saglik.set(False)
            self.oto.set(False); self.konaklama.set(False); self.banka.set(False)
            self.tumu.set(False)
            self.izgara.set(False)
            self.sabit_izgara.set(False)
        elif mod == t("mod_normal"):
            self.yemek.set(True); self.gezi.set(True)
            self.alisveris.set(False); self.saglik.set(False)
            self.oto.set(False); self.konaklama.set(False); self.banka.set(False)
            self.tumu.set(False)
            self.izgara.set(True)
            self.sabit_izgara.set(False)
        elif mod == t("mod_yemek"):
            self.yemek.set(True)
            self.gezi.set(False); self.alisveris.set(False); self.saglik.set(False)
            self.oto.set(False); self.konaklama.set(False); self.banka.set(False)
            self.tumu.set(False)
            self.izgara.set(True)
            self.sabit_izgara.set(False)
        elif mod == t("mod_kapsamli"):
            for v in self.kategoriler.values():
                v.set(True)
            self.tumu.set(True)
            self.izgara.set(True)
            self.sabit_izgara.set(False)
        elif mod == t("mod_sabit"):
            self.sabit_izgara.set(True)
            self.izgara.set(False)
        else:
            self.sabit_izgara.set(False)
        self._tumu_guncelle = False
        self._hucre_km_durum_guncelle()

    def _hucre_km_durum_guncelle(self):
        durum = "normal" if self.mod_var.get() == t("mod_sabit") else "disabled"
        self.hucre_km_entry.configure(state=durum)

    def _paralel_oku(self):
        try:
            return max(1, min(3, int(self.paralel.get())))
        except Exception:
            return 1

    def _hucre_km_oku(self):
        try:
            return max(0.2, float(str(self.hucre_km.get()).replace(",", ".")))
        except Exception:
            return 1.0

    def _yemek_sadece_mi(self):
        """Sadece Yemek kutusu işaretliyse (etiketten bağımsız) yemek çıktısı üretilir."""
        diger = [self.gezi, self.alisveris, self.saglik, self.oto, self.konaklama, self.banka]
        return bool(self.yemek.get() and not any(k.get() for k in diger)
                    and not self.tumu.get() and not self.ozel_arama.get().strip())

    def ayarlar(self):
        return {
            "hizli": self.hizli.get(), "paralel": self._paralel_oku(), "tekrar": self.tekrar.get(),
            "verimsiz": self.verimsiz.get(), "il": self.il.get(), "ilce": self.ilce.get(), "mahalle": self.mahalle.get(),
            "yaricap": self.yaricap.get(), "puan": self.puan.get(), "oy": self.oy.get(),
            "ozel_arama": self.ozel_arama.get(), "tumu": self.tumu.get(),
            "mahalle_bul": self.mahalle_bul.get(), "goster": self.goster.get(),
            "izgara": self.izgara.get(), "ham": self.ham.get(), "devam": self.devam.get(),
            "sabit_izgara": self.sabit_izgara.get(), "hucre_km": self._hucre_km_oku(),
            "dil": self.dil.get(),
            "yemek_sadece": self._yemek_sadece_mi(),
            "kategori_esikleri": self._kategori_esikleri_kayitlik(),
            "tarama_modu": self.mod_var.get(),
            **{k: v.get() for k, v in self.kategoriler.items()},
        }

    def ayarlari_kaydet(self):
        try:
            with open(AYAR_DOSYASI, "w", encoding="utf-8") as f:
                json.dump(self.ayarlar(), f, ensure_ascii=False, indent=1)
        except Exception:
            pass

    def ayarlari_yukle(self, veri=None):
        if veri is None:
            try:
                a = json.load(open(AYAR_DOSYASI, encoding="utf-8"))
            except Exception:
                return
        else:
            a = veri

        global _aktif_dil
        dil_deger = a.get("dil", "tr")
        self.dil.set(dil_deger)
        dil_ayarla(dil_deger)

        self.il.set(a.get("il", self.il.get()))
        self.ilce.set(a.get("ilce", self.ilce.get()))
        self.mahalle.set(a.get("mahalle", ""))
        self.yaricap.set(a.get("yaricap", ""))
        self.puan.set(a.get("puan", "0"))
        self.oy.set(a.get("oy", "0"))
        self.ozel_arama.set(a.get("ozel_arama", ""))
        self.mahalle_bul.set(a.get("mahalle_bul", True))
        self.goster.set(a.get("goster", True))
        self.izgara.set(a.get("izgara", True))
        self.ham.set(a.get("ham", False))
        self.devam.set(a.get("devam", False))
        self.hizli.set(a.get("hizli", True))
        self.paralel.set(a.get("paralel", 1))
        self.tekrar.set(a.get("tekrar", False))
        self.verimsiz.set(a.get("verimsiz", False))

        sabit_izgara = bool(a.get("sabit_izgara", False))
        self.sabit_izgara.set(sabit_izgara)
        self.hucre_km.set(str(a.get("hucre_km", "1.0") or "1.0"))

        self.kategori_esikleri = self._kategori_esikleri_yukle_ve_normalize(a.get("kategori_esikleri"))

        self._tumu_guncelle = True
        for k, v in self.kategoriler.items():
            if k in a: v.set(bool(a[k]))
        if a.get("tumu") and all(v.get() for v in self.kategoriler.values()):
            self.tumu.set(True)
        else:
            self.tumu.set(False)
        self._tumu_guncelle = False
        kaydedilen_mod = a.get("tarama_modu", "")
        gecerli_modlar = [t("mod_ozel"), t("mod_hizli"), t("mod_normal"), t("mod_yemek"), t("mod_kapsamli"), t("mod_sabit")]
        
        # Eğer kaydedilmiş mod varsa ve dil değişmediyse onu yükle, yoksa mevcut mantıkla devam et
        if kaydedilen_mod and kaydedilen_mod in gecerli_modlar:
            self.mod_var.set(kaydedilen_mod)
        elif self.sabit_izgara.get():
            self.mod_var.set(t("mod_sabit"))
        else:
            self.mod_var.set(t("mod_ozel"))
            
        self._hucre_km_durum_guncelle()

    def profil_kaydet(self):
        ad = simpledialog.askstring("Profil Kaydet", "Bu ayarlar için bir profil adı girin:")
        if not ad: return
        try:
            try:
                profiller = json.load(open(PROFILLER_DOSYASI, encoding="utf-8"))
            except:
                profiller = {}
            profiller[ad] = self.ayarlar()
            with open(PROFILLER_DOSYASI, "w", encoding="utf-8") as f:
                json.dump(profiller, f, ensure_ascii=False, indent=1)
            messagebox.showinfo("Başarılı", f"'{ad}' profili kaydedildi.")
        except Exception as e:
            messagebox.showerror("Hata", f"Profil kaydedilemedi:\n{e}")

    def profil_yukle(self):
        try:
            try:
                profiller = json.load(open(PROFILLER_DOSYASI, encoding="utf-8"))
            except:
                messagebox.showwarning("Uyarı", "Henüz kaydedilmiş profil yok.")
                return
            ad = simpledialog.askstring("Profil Yükle", "Yüklenecek profili yazın:\n\nKayıtlılar:\n" + "\n".join(f"- {k}" for k in profiller.keys()))
            if ad and ad in profiller:
                self.ayarlari_yukle(veri=profiller[ad])
                self.yaz(f"Profil yüklendi: {ad}")
            elif ad:
                messagebox.showwarning("Bulunamadı", f"'{ad}' adında bir profil bulunamadı.")
        except Exception as e:
            messagebox.showerror("Hata", f"Profil yüklenemedi:\n{e}")

    def _kategori_esikleri_yukle_ve_normalize(self, veri=None):
        taban = {k: dict(v) for k, v in getattr(g, "VARSAYILAN_ESIKLER", {}).items()}
        if isinstance(veri, dict):
            for grup in taban.keys():
                secim = veri.get(grup)
                if not isinstance(secim, dict):
                    continue
                try:
                    puan = float(secim.get("puan", taban[grup].get("puan", 0.0)))
                except (TypeError, ValueError):
                    puan = float(taban[grup].get("puan", 0.0))
                try:
                    oy = int(secim.get("oy", taban[grup].get("oy", 0)))
                except (TypeError, ValueError):
                    oy = int(taban[grup].get("oy", 0))
                puansiz = bool(secim.get("puansiz", taban[grup].get("puansiz", False)))
                taban[grup] = {"puan": puan, "oy": oy, "puansiz": puansiz}
        return taban

    def _kategori_esikleri_kayitlik(self):
        return self._kategori_esikleri_yukle_ve_normalize(self.kategori_esikleri)

    def _openpyxl_acilis_uyarisi(self):
        try:
            import openpyxl  # noqa: F401
        except Exception:
            messagebox.showwarning("Bilgi", "Excel çıktısı için openpyxl gerekli. Kurmak için: pip install openpyxl")

    def _onay_sor(self, baslik, metin, timeout=25):
        bekle = threading.Event()
        sonuc = {"ok": False}
        self.kuyruk.put(("onay", baslik, metin, bekle, sonuc))
        tamam = bekle.wait(timeout=timeout)
        if not tamam:
            self.yaz("Onay penceresi zaman aşımına uğradı; işlem iptal edildi.")
            sonuc["ok"] = False
        return bool(sonuc.get("ok"))

    def _kategori_esikleri_varsayilana_don(self, satirlar):
        taban = {k: dict(v) for k, v in getattr(g, "VARSAYILAN_ESIKLER", {}).items()}
        self.kategori_esikleri = taban
        for grup, _, puan_v, oy_v, puansiz_v in satirlar:
            v = taban.get(grup, {})
            puan_v.set(str(v.get("puan", "")))
            oy_v.set(str(v.get("oy", "")))
            puansiz_v.set(bool(v.get("puansiz", False)))

    def kategori_esikleri_penceresi(self):
        if "g" not in globals() or not hasattr(g, "VARSAYILAN_ESIKLER"):
            messagebox.showerror("Hata", "Kategori eşikleri yüklenemedi.")
            return

        pen = tk.Toplevel(self.kok)
        pen.title("Kategori Eşikleri")
        pen.geometry("760x560")
        pen.transient(self.kok)

        kapsayici = ttk.Frame(pen, padding=10)
        kapsayici.pack(fill="both", expand=True)
        ttk.Label(kapsayici, text="Boş bırakılan hücrelerde ana penceredeki değerler varsayılan kabul edilir.", foreground="#555").pack(anchor="w", pady=(0, 8))

        canvas = tk.Canvas(kapsayici, highlightthickness=0)
        sb = ttk.Scrollbar(kapsayici, orient="vertical", command=canvas.yview)
        icerik = ttk.Frame(canvas)
        icerik.bind("<Configure>", lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=icerik, anchor="nw")
        canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        basliklar = ["Grup", "En az puan", "En az yorum", "Puansızlar da gelsin"]
        for c, baslik in enumerate(basliklar):
            ttk.Label(icerik, text=baslik, font=("Segoe UI", 9, "bold")).grid(row=0, column=c, sticky="w", padx=6, pady=(0, 6))

        aktif = self._kategori_esikleri_yukle_ve_normalize(self.kategori_esikleri)
        satirlar = []
        for i, grup in enumerate(getattr(g, "VARSAYILAN_ESIKLER", {}).keys(), start=1):
            mevcut = aktif.get(grup, {})
            ttk.Label(icerik, text=grup).grid(row=i, column=0, sticky="w", padx=6, pady=4)
            puan_v = tk.StringVar(value=str(mevcut.get("puan", "")))
            oy_v = tk.StringVar(value=str(mevcut.get("oy", "")))
            puansiz_v = tk.BooleanVar(value=bool(mevcut.get("puansiz", False)))
            ttk.Entry(icerik, textvariable=puan_v, width=14).grid(row=i, column=1, sticky="w", padx=6, pady=4)
            ttk.Entry(icerik, textvariable=oy_v, width=14).grid(row=i, column=2, sticky="w", padx=6, pady=4)
            ttk.Checkbutton(icerik, variable=puansiz_v).grid(row=i, column=3, sticky="w", padx=6, pady=4)
            satirlar.append((grup, mevcut, puan_v, oy_v, puansiz_v))

        alt = ttk.Frame(pen, padding=(10, 0, 10, 10))
        alt.pack(fill="x")

        def kaydet():
            yeni = self._kategori_esikleri_yukle_ve_normalize(self.kategori_esikleri)
            for grup, _m, puan_v, oy_v, puansiz_v in satirlar:
                pmetin = puan_v.get().strip()
                ometin = oy_v.get().strip()
                try:
                    puan = float(pmetin.replace(",", ".")) if pmetin else float(str(self.puan.get()).replace(",", "."))
                except ValueError:
                    messagebox.showerror("Hata", f"'{grup}' için puan değeri sayı olmalı.", parent=pen)
                    return
                try:
                    oy = int(ometin) if ometin else int(self.oy.get())
                except ValueError:
                    messagebox.showerror("Hata", f"'{grup}' için yorum değeri sayı olmalı.", parent=pen)
                    return
                yeni[grup] = {"puan": puan, "oy": oy, "puansiz": bool(puansiz_v.get())}
            self.kategori_esikleri = yeni
            self.ayarlari_kaydet()
            self.yaz("Kategori eşikleri kaydedildi.")
            pen.destroy()

        ttk.Button(alt, text="Kaydet", style="Start.TButton", command=kaydet).pack(side="left")
        ttk.Button(alt, text="Varsayılana Dön", command=lambda: self._kategori_esikleri_varsayilana_don(satirlar)).pack(side="left", padx=8)
        ttk.Button(alt, text="Kapat", command=pen.destroy).pack(side="right")

    def json_disari_aktar(self):
        if not self.ozet:
            self.yaz("Önce bir tarama sonucu üretin.")
            return
        csv_yolu = self.ozet.get("csv")
        if not csv_yolu or not os.path.exists(csv_yolu):
            self.yaz("JSON üretilemedi: sonucun CSV dosyası bulunamadı.")
            return
        try:
            with open(csv_yolu, encoding="utf-8-sig", newline="") as f:
                kayitlar = list(csv.DictReader(f))
            for r in kayitlar:
                puan_ham = str(r.get("Puan", "")).strip().lower()
                yorum_ham = str(r.get("Yorum Sayısı", "")).strip().lower()
                puansiz_mi = (puan_ham == "puansız" or yorum_ham == "puansız")
                if puansiz_mi:
                    r["_puansiz"] = True
                    r["Puan"] = None
                    r["Yorum Sayısı"] = None
                    r["Güvenilir Skor"] = None
            json_yolu = self.ozet.get("json") or os.path.splitext(csv_yolu)[0] + ".json"
            g.json_yaz(kayitlar, json_yolu)
            self.ozet["json"] = os.path.abspath(json_yolu)
            self.yaz(f"JSON yazıldı: {self.ozet['json']}")
        except Exception as e:
            self.yaz(f"JSON yazılamadı: {e}")

    def kapanis(self):
        self.ayarlari_kaydet()
        self.durdur.set()
        self.kok.destroy()

    def yaz(self, mesaj):
        self.gunluk.configure(state="normal")
        self.gunluk.insert("end", mesaj + "\n")
        self.gunluk.see("end")
        self.gunluk.configure(state="disabled")

    def kuyruk_oku(self):
        try:
            while True:
                tur, *veri = self.kuyruk.get_nowait()
                if tur == "log":
                    self.yaz(veri[0])
                elif tur == "ilerleme":
                    i, n, m = veri
                    self.cubuk.configure(maximum=max(n, 1), value=i)
                    self.son_ilerleme = (i, n)
                    self.damgalar.append(time.time())
                    self.damgalar = self.damgalar[-31:]
                    self.yaz(f"[{i}/{n}] {m}")
                elif tur == "bitti":
                    self.bitti(veri[0])
                elif tur == "hata":
                    self.bitti(None)
                    messagebox.showerror("📡 Local Radar · Hata", veri[0])
                elif tur == "onay":
                    baslik, metin, bekle, sonuc = veri
                    sonuc["ok"] = messagebox.askyesno(baslik, metin)
                    bekle.set()
                elif tur == "iptal":
                    self.baslat.configure(state="normal")
                    self.dur.configure(state="disabled")
                    self.t0 = None
                    if self.ozet:
                        for d in (self.excel, self.rehber, self.rehber_sade, self.json_btn, self.kml_btn, self.klasor_btn):
                            d.configure(state="normal")
        except queue.Empty:
            pass
        self.kok.after(200, self.kuyruk_oku)

    def kalan_saniye(self):
        i, n = self.son_ilerleme
        if n <= i or i < 3 or len(self.damgalar) < 4:
            return None
        hiz = (self.damgalar[-1] - self.damgalar[0]) / (len(self.damgalar) - 1)
        return hiz * (n - i)

    def sure_tikla(self):
        if self.t0 is None:
            return
        gecen = time.time() - self.t0
        i, n = self.son_ilerleme
        if dil_al() == "en":
            metin = f"Elapsed: {sure_yaz(gecen)}"
        else:
            metin = f"Geçen süre: {sure_yaz(gecen)}"
        if n:
            metin += f"   ·   {i}/{n}" + (" searches" if dil_al() == "en" else " arama")
            kalan = self.kalan_saniye()
            if kalan is not None:
                prefix = "Est. remaining: ~" if dil_al() == "en" else "Tahmini kalan: ~"
                metin += f"   ·   {prefix}{sure_yaz(kalan)}"
            else:
                msg = "Calculating remaining time..." if dil_al() == "en" else "Kalan süre hesaplanıyor..."
                metin += f"   ·   {msg}"
            metin += "   (may extend as dense areas split)" if dil_al() == "en" else "   (yoğun yerler bölününce uzayabilir)"
        self.sure.configure(text=metin)
        self.kok.after(1000, self.sure_tikla)

    def durdur_tikla(self):
        self.durdur.set()
        self.dur.configure(state="disabled")
        self.yaz("⏹ Durdurma sinyali gönderildi, mevcut adım tamamlanıyor...")

    def baslat_tikla(self):
        try:
            min_puan = float(self.puan.get().replace(",", "."))
            min_oy = int(self.oy.get())
            if self.yaricap.get().strip():
                float(self.yaricap.get().replace(",", "."))
        except ValueError:
            messagebox.showerror("Hata", "Puan, yorum sayısı ve yarıçap sayı olmalı.")
            return

        if not (any(v.get() for v in self.kategoriler.values()) or self.ozel_arama.get().strip()):
            messagebox.showerror("Hata", "En az bir kategori seçin ya da özel arama kelimesi yazın.")
            return
        if not self.ilce.get().strip():
            messagebox.showerror("Hata", "İlçe yaz.")
            return

        self.ayarlari_kaydet()
        self.durdur.clear()
        self.t0 = time.time()
        self.son_ilerleme = (0, 0)
        self.damgalar = []
        self.sure.configure(text="Elapsed: 0s" if dil_al() == "en" else "Geçen süre: 0 sn")
        self.sure_tikla()
        self.cubuk.configure(value=0)
        for d in (self.excel, self.rehber, self.rehber_sade, self.json_btn, self.kml_btn, self.klasor_btn):
            d.configure(state="disabled")
        self.baslat.configure(state="disabled")
        self.dur.configure(state="normal")

        try:
            hucre_km = float(str(self.hucre_km.get()).replace(",", "."))
        except ValueError:
            messagebox.showerror("Hata", "Hücre boyutu sayı olmalı.")
            self.baslat.configure(state="normal")
            self.dur.configure(state="disabled")
            self.t0 = None
            return

        v = dict(ilce=self.ilce.get().strip(), il=self.il.get().strip(), mahalle=self.mahalle.get(),
                 yaricap=self.yaricap.get().strip(), min_puan=min_puan, min_oy=min_oy,
                 yemek=self.yemek.get(), gezi=self.gezi.get(), alisveris=self.alisveris.get(),
                 yemek_sadece=self._yemek_sadece_mi(),
                 saglik=self.saglik.get(), oto=self.oto.get(), konaklama=self.konaklama.get(),
                 banka=self.banka.get(), tumu=self.tumu.get(), ozel_arama=self.ozel_arama.get(),
                 mahalle_bul=self.mahalle_bul.get(), goster=self.goster.get(),
                 izgara=self.izgara.get(), ham=self.ham.get(), devam=self.devam.get(),
                 hizli=self.hizli.get(), paralel=self._paralel_oku(), tekrar=self.tekrar.get(),
                 verimsiz=self.verimsiz.get(), sabit_izgara=self.sabit_izgara.get(),
                 hucre_km=max(0.2, hucre_km), kategori_esikleri=self._kategori_esikleri_kayitlik())

        threading.Thread(target=self.calis, args=(v,), daemon=True).start()

    def calis(self, v):
        import ctypes
        if os.name == "nt":
            ctypes.windll.kernel32.SetThreadExecutionState(0x80000000 | 0x00000001 | 0x00000002)
        try:
            if 'g' not in globals():
                raise RuntimeError("local_radar_core modülü yüklenemediği için arama yapılamaz.")

            ilce, il = v["ilce"], v["il"]
            mahalleler = [m.strip() for m in v["mahalle"].split(",") if m.strip()]
            # Türkçe karakterleri İngilizceye çevirip, ilk harfleri büyüterek dosya adı oluştur
            isim_havuzu = "_".join([ilce] + mahalleler)
            slug_ham = g.fold(isim_havuzu).replace(" ", "_")
            slug = re.sub(r"[^a-zA-Z0-9_]+", "", slug_ham).title()

            ham_yolu = f"{g.DOSYA_HAM_PREFIX}{slug}.json"
            ham_kullan = None
            if v["ham"]:
                ara_yolu = f"{g.DOSYA_ARA_KAYIT_PREFIX}{slug}.json"
                if os.path.exists(ham_yolu):
                    ham_kullan = ham_yolu
                elif os.path.exists(ara_yolu):
                    ham_kullan = ara_yolu
                    self.kuyruk.put(("log", "Tamamlanmış ham veri yok; yarım kalan taramanın ara kaydı kullanılıyor."))
                else:
                    raise RuntimeError(f"Bu arama için ham veri yok: {ham_yolu}\n"
                                       "Önce normal bir tarama yapın; ham veri her taramada otomatik kaydedilir.")

            hedefler = ([(m, [f"{m} Mahallesi, {ilce}, {il}", f"{m}, {ilce}, {il}",
                              f"{m} Mahallesi, {il}", f"{m}, {il}"]) for m in mahalleler]
                        or [(ilce, [f"{ilce}, {il}"])])
            elle = v["yaricap"]
            alanlar = []
            for ad, sorgular in hedefler:
                self.kuyruk.put(("log", f"Konum bulunuyor: {ad}"))
                s = g.alan_bul(ad, sorgular, ilce_geneli=not mahalleler)
                if not s:
                    raise RuntimeError(f"'{ad}' bulunamadı. Yazımı kontrol et ya da mahalle adını değiştir.")
                enlem, boylam, r, kaynak = s
                if elle:
                    r = float(elle.replace(",", "."))
                    kaynak = "elle girilen yarıçap"
                alanlar.append((enlem, boylam, r, g.zoom_sec(r)))
                self.kuyruk.put(("log", f"   Alan: {enlem:.4f}, {boylam:.4f} · yarıçap {r} km ({kaynak})"))

            if not v["ham"]:
                if v["izgara"]:
                    self.kuyruk.put(("log", "Akıllı bölme açık: yoğun yerler otomatik parçalanır, boş yerler tek aramada kapanır."))
                g.HIZLI_YUKLEME = g.HIZLI_KAYDIRMA = bool(v.get("hizli", True))
                g.PARALEL = max(1, int(v.get("paralel", 1)))
                g.TEKRAR_ONLEME_GUN = 30 if v.get("tekrar") else 0
                g.VERIMSIZ_ATLA = bool(v.get("verimsiz"))

            kategoriler, bolumler = [], []
            if v["tumu"]:
                kategoriler = g.TUMU
                bolumler = g.BOLUMLER
            else:
                if v["yemek"]:
                    kategoriler += g.YEMEK + ["kasap"]
                    bolumler += ["Kebap & Et", "Restoran", "Hızlı Atıştırmalık", "Tatlı & Pastane", "Kafe & Kahvaltı"]
                    if "Alışveriş" not in bolumler:
                        bolumler.append("Alışveriş")
                if v["gezi"]:
                    kategoriler += g.GEZI
                    if "Gezilecek yerler" not in bolumler:
                        bolumler.append("Gezilecek yerler")
                if v["alisveris"]:
                    kategoriler += g.ALISVERIS
                    if "Alışveriş" not in bolumler:
                        bolumler.append("Alışveriş")
                if v["saglik"]:
                    kategoriler += g.SAGLIK
                    if "Diğer" not in bolumler:
                        bolumler.append("Diğer")
                if v["oto"]:
                    kategoriler += g.OTO
                    if "Diğer" not in bolumler:
                        bolumler.append("Diğer")
                if v["konaklama"]:
                    kategoriler += g.KONAKLAMA
                    if "Diğer" not in bolumler:
                        bolumler.append("Diğer")
                if v["banka"]:
                    kategoriler += g.BANKA
                    if "Diğer" not in bolumler:
                        bolumler.append("Diğer")

            ozel_terimler = [x.strip() for x in v["ozel_arama"].split(",") if x.strip()]
            if ozel_terimler:
                kategoriler += ozel_terimler
                bolumler = g.BOLUMLER

            if v.get("tumu"):
                if v.get("sabit_izgara"):
                    hucre_sayisi = len(g.sabit_izgara_hucreleri(alanlar, v.get("hucre_km", 1.0)))
                    kelime_sayisi = len(kategoriler)
                    toplam = g.arama_sayisi_tahmini(alanlar, kelime_sayisi, v.get("hucre_km", 1.0))
                    metin = f"Bu seçim {toplam} arama yapacak ({hucre_sayisi} hücre × {kelime_sayisi} kelime). Devam edilsin mi?"
                else:
                    metin = ("TÜMÜNÜ ARA seçildi. Bu seçim çok sayıda arama yapacak ve saatler sürebilir. "
                             "Büyük ve yoğun ilçelerde süre birkaç katına çıkabilir.\n\nDevam edilsin mi?")
                if not self._onay_sor("Uzun sürecek tarama", metin):
                    self.kuyruk.put(("log", "Kullanıcı iptal etti."))
                    self.kuyruk.put(("iptal",))
                    return

            ayar = dict(
                baslik=(", ".join(mahalleler) + f" ({ilce})") if mahalleler else f"{ilce} · Local Radar",
                dosya=slug, ilce=ilce,
                merkez=alanlar[0][:2], yaricap=alanlar[0][2], alanlar=alanlar, bolgeler=[""],
                kategoriler=kategoriler, bolumler=bolumler,
                tam_tarama=not mahalleler, bolme=bool(v["izgara"]),
                sabit_izgara=bool(v.get("sabit_izgara")),
                hucre_km=float(v.get("hucre_km", 1.0)),
                kategori_esikleri=v.get("kategori_esikleri") or {},
                yemek_sadece=bool(v.get("yemek_sadece")),
                alisveris_acik=bool(v.get("alisveris") or v.get("tumu")),
            )

            g.esikleri_yukle(ayar)
            ozet = g.calistir(
                ayar,
                lambda i, n, m: self.kuyruk.put(("ilerleme", i, n, m)),
                self.durdur.is_set,
                birlestir=True,
                min_puan=v["min_puan"], min_oy=v["min_oy"],
                mahalle_aktif=v["mahalle_bul"], ekranda_goster=v["goster"],
                ham_kullan=ham_kullan, devam=v.get("devam", False),
            )
            self.kuyruk.put(("bitti", ozet))
        except Exception as e:
            hata_yaz(traceback.format_exc())
            self.kuyruk.put(("hata", str(e)))
        finally:
            if os.name == "nt":
                ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)

    def bitti(self, ozet):
        self.baslat.configure(state="normal")
        self.dur.configure(state="disabled")
        if self.t0 is not None:
            toplam_sure = sure_yaz(time.time() - self.t0)
            etiket = "Total time" if dil_al() == "en" else "Toplam süre"
            self.sure.configure(text=f"{etiket}: {toplam_sure}")
            self.yaz(f"{etiket}: {toplam_sure}")
        self.t0 = None

        try:
            import winsound; winsound.MessageBeep()
        except Exception:
            self.kok.bell()

        try:
            self.kok.deiconify(); self.kok.lift()
            self.kok.attributes("-topmost", True)
            self.kok.after(1500, lambda: self.kok.attributes("-topmost", False))
        except Exception:
            pass

        if ozet is None:
            return
        self.ozet = ozet
        self.yaz(f"\nBitti: {ozet['okunan']} yer okundu, {ozet['adet']} tanesi ölçütlere uydu.")
        self.yaz(f"Yeni: {ozet['yeni']}  |  Güncellenen: {ozet['guncellenen']}  |  Bu ilçede artık görünmeyen: {ozet.get('kayip', 0)}")
        if ozet["adet"] == 0:
            self.yaz("Sonuç çıkmadı. Puanı ya da yorum sayısını düşürmeyi dene.")
        for d in (self.excel, self.rehber, self.rehber_sade, self.json_btn, self.kml_btn, self.klasor_btn):
            d.configure(state="normal")
        messagebox.showinfo(
            "📡 Local Radar · Tarama tamamlandı",
            f"{ozet['adet']} yer listeye girdi.\n"
            f"Yeni: {ozet['yeni']} · Güncellenen: {ozet['guncellenen']} · Artık görünmeyen: {ozet.get('kayip', 0)}"
            f"\n\nDosyalar:\n{ozet['klasor']}",
        )

    def manuel_penceresi(self):
        pen = tk.Toplevel(self.kok)
        pen.title("Manuel Mekan Ekle")
        pen.transient(self.kok)
        pen.columnconfigure(1, weight=1)
        alanlar = [
            ("Mekan adı *", "ad", ""), ("Tür", "tur", ""),
            ("Puan *", "puan", ""), ("Yorum sayısı *", "yorum", ""),
            ("İlçe", "ilce", self.ilce.get().strip()), ("Mahalle", "mahalle", ""),
            ("Adres", "adres", ""), ("Telefon", "telefon", ""),
            ("Google Haritalar linki", "link", ""),
        ]
        vars_ = {}
        for i, (etiket, anahtar, varsayilan) in enumerate(alanlar):
            ttk.Label(pen, text=etiket).grid(row=i, column=0, sticky="w", padx=10, pady=4)
            v = tk.StringVar(value=varsayilan)
            ttk.Entry(pen, textvariable=v, width=44).grid(row=i, column=1, sticky="ew", padx=10, pady=4)
            vars_[anahtar] = v

        def kaydet():
            ad = vars_["ad"].get().strip()
            try:
                puan = float(vars_["puan"].get().replace(",", "."))
                yorum = int(vars_["yorum"].get().strip())
            except ValueError:
                messagebox.showerror("Hata", "Puan ve yorum sayısı sayı olmalı.", parent=pen)
                return
            if not ad:
                messagebox.showerror("Hata", "Mekan adı gerekli.", parent=pen)
                return
            veri = {"ad": ad, "puan": puan, "yorum": yorum}
            for k in ("tur", "ilce", "mahalle", "adres", "telefon", "link"):
                if vars_[k].get().strip():
                    veri[k] = vars_[k].get().strip()
            try:
                g.manuel_mekan_kaydet(veri)
                g.esikleri_yukle({"kategori_esikleri": self._kategori_esikleri_kayitlik()})
                sayi = g.hepsi_yenile({"ilce": veri.get("ilce", "")})
            except Exception as e:
                messagebox.showerror("Hata", str(e), parent=pen)
                return
            self.yaz(f"Manuel mekan eklendi: {ad}. HEPSİ rehberi yenilendi ({sayi} yer).")
            self.hepsi_rehber.configure(state="normal")
            pen.destroy()

        dg = ttk.Frame(pen)
        dg.grid(row=len(alanlar) + 1, column=0, columnspan=2, pady=10)
        ttk.Button(dg, text="Kaydet ve rehberi yenile", style="Start.TButton", command=kaydet).pack(side="left", padx=6)
        ttk.Button(dg, text="Vazgeç", command=pen.destroy).pack(side="left", padx=6)

    def havuz_temizle(self):
        if not messagebox.askyesno("Havuzu Sıfırla",
                                   "Tüm aramaların biriktiği havuz (pool.json) ve HEPSİ dosyaları silinsin mi?\n"
                                   "Bu işlem geri alınamaz; ilçe bazlı çıktı klasörlerine dokunulmaz."):
            return
        silinen = []
        for yol in ("pool.json", "local_radar_all.csv", "local_radar_all.xlsx",
                    "local_radar_all.kml", "local_radar_all.html", "local_radar_all_sade.html", "local_radar_all.json"):
            if os.path.exists(yol):
                try:
                    os.remove(yol)
                    silinen.append(yol)
                except Exception:
                    pass
        self.yaz("Havuz sıfırlandı: " + (", ".join(silinen) if silinen else "(zaten boştu)"))

    def ac(self, tur):
        if not self.ozet:
            if tur == "hepsi_html" and os.path.exists("local_radar_all.html"):
                webbrowser.open(pathlib.Path(os.path.abspath("local_radar_all.html")).as_uri())
            elif tur == "hepsi_html_sade" and os.path.exists("local_radar_all_sade.html"):
                webbrowser.open(pathlib.Path(os.path.abspath("local_radar_all_sade.html")).as_uri())
            return

        yol = self.ozet.get(tur)
        if not yol or not os.path.exists(yol):
            return

        if tur in ("html", "html_sade", "hepsi_html", "hepsi_html_sade"):
            webbrowser.open(pathlib.Path(yol).as_uri())
        elif tur == "kml":
            if hasattr(os, "startfile"):
                os.startfile(yol)
            else:
                klasor = self.ozet.get("klasor") if self.ozet else None
                hedef = pathlib.Path(klasor).as_uri() if klasor and os.path.isdir(klasor) else pathlib.Path(yol).as_uri()
                webbrowser.open(hedef)
        elif hasattr(os, "startfile"):
            os.startfile(yol)
        else:
            webbrowser.open(pathlib.Path(yol).as_uri())


if __name__ == "__main__":
    kok = tk.Tk()
    kok.report_callback_exception = lambda t, d, iz: hata_yaz("".join(traceback.format_exception(t, d, iz)))
    Pencere(kok)
    kok.mainloop()