# -*- coding: utf-8 -*-
"""
Local Radar - gerçek ilçe ataması (ADIM 1: indirme + RAPOR).
Bu dosya rehber HTML'lerine HİÇBİR ŞEY YAZMAZ. Sadece sınır verisini indirir ve rapor üretir.

Veri: geoBoundaries (gbOpen, CC BY 4.0) il (ADM1) ve ilçe (ADM2) sınırları, GitHub'dan bir kere indirilir.
Çıktılar (bu klasöre): ilce_rapor.txt (okunur rapor), ilce_atama.json (sonraki adım için atamalar)
Menüden: gece_tarama.py -> 8
"""
import os, re, sys, json, math, collections, urllib.request

KLASOR = os.path.dirname(os.path.abspath(__file__))
SINIR_KLASORU = os.path.join(KLASOR, "sinir_verisi")
_ADRES = "https://media.githubusercontent.com/media/wmgeolab/geoBoundaries/main/releaseData/gbOpen/TUR/{k}/geoBoundaries-TUR-{k}.geojson"
ESIK_YAKIN_M = 250       # poligon dışında ama bu kadar yakınsa en yakın ilçeye ata
ESIK_UZAK_M = 1000       # bundan uzaksa karantina (yurt dışı / bozuk koordinat)
MIN_MEKAN = 20           # ilçe rehberi için asgari mekan (rapor eşiği)

_TR = str.maketrans({"İ": "i", "I": "i", "ı": "i", "Ğ": "g", "ğ": "g", "Ü": "u", "ü": "u", "Ş": "s", "ş": "s",
                     "Ö": "o", "ö": "o", "Ç": "c", "ç": "c", "â": "a", "Â": "a", "î": "i", "û": "u"})


def fold(s):
    return re.sub(r"[^a-z0-9]", "", str(s).translate(_TR).lower())


def ilce_anahtar(il, ilce):
    """İlçe adını karşılaştırılabilir hale getirir; 'XMerkez', 'X (Merkez)', 'X District' hepsi 'merkez' olur."""
    i, c = fold(il), fold(ilce)
    ozel = {"princeislands": "adalar", "imbros": "gokceada", "karakeceli": "karakecili", "gedizmerkez": "gediz"}
    c = ozel.get(c, c)
    if c.endswith("district"):
        c = c[:-8]
    if c == i or "merkez" in c or c == i + "merkez":
        c = "merkez"
    return i + "|" + c


def indir():
    os.makedirs(SINIR_KLASORU, exist_ok=True)
    for k in ("ADM1", "ADM2"):
        yol = os.path.join(SINIR_KLASORU, k + ".geojson")
        if os.path.exists(yol) and os.path.getsize(yol) > 1_000_000:
            continue
        print(f"{k} sınırları indiriliyor (bir kereye mahsus)...")
        urllib.request.urlretrieve(_ADRES.format(k=k), yol)
        if os.path.getsize(yol) < 1_000_000:
            os.remove(yol)
            raise RuntimeError(f"{k} dosyası indirilemedi (çok küçük geldi).")
    return True


def _xy(lon, lat):
    return lon * 111320.0 * math.cos(math.radians(39)), lat * 110574.0


def sinirlari_yukle():
    from shapely.geometry import shape
    from shapely.ops import transform
    from shapely.strtree import STRtree
    f = lambda x, y, z=None: _xy(x, y)
    il_geo = []
    for ft in json.load(open(os.path.join(SINIR_KLASORU, "ADM1.geojson"), encoding="utf-8"))["features"]:
        il_geo.append((transform(f, shape(ft["geometry"]).buffer(0)), ft["properties"]["shapeName"]))
    il_ag = STRtree([x[0] for x in il_geo])
    liste = []
    for ft in json.load(open(os.path.join(SINIR_KLASORU, "ADM2.geojson"), encoding="utf-8"))["features"]:
        g = transform(f, shape(ft["geometry"]).buffer(0))
        p = g.representative_point()
        il = None
        for k in il_ag.query(p):
            if il_geo[k][0].contains(p):
                il = il_geo[k][1]
                break
        if il is None:                              # nadir: en yakın il
            il = il_geo[il_ag.nearest(p)][1]
        liste.append((il, ft["properties"]["shapeName"], g))
    ag = STRtree([x[2] for x in liste])
    return liste, ag


def yer_bul(liste, ag, lat, lon):
    """-> (il, ilçe, mesafe_m). İçindeyse 0; dışındaysa en yakın ilçeye olan uzaklık."""
    from shapely.geometry import Point
    p = Point(*_xy(lon, lat))
    for k in ag.query(p):
        if liste[k][2].contains(p):
            return liste[k][0], liste[k][1], 0.0
    k = int(ag.nearest(p))
    return liste[k][0], liste[k][1], float(liste[k][2].distance(p))


def _yer_id(link):
    m = re.search(r"!1s(0x[0-9a-f]+:0x[0-9a-f]+)", link or "")
    return m.group(1) if m else (link or "")


def rehber_oku(yol):
    try:
        t = open(yol, encoding="utf-8").read()
        j = t.index("const V=") + 8
        return json.JSONDecoder().raw_decode(t[j:])[0].get("I", [])
    except Exception:
        return None


def rapor(rehber_klasoru, il_ilce, dosya_haritasi, cikti_klasoru=None):
    cikti_klasoru = cikti_klasoru or KLASOR
    indir()
    print("Sınırlar yükleniyor...")
    liste, ag = sinirlari_yukle()
    yeni_adlar = {ilce_anahtar(il, ilce): (il, ilce) for il, ilce, _ in liste}
    yeni_anahtarlar = set(yeni_adlar)
    site_anahtarlar = {}
    for il, ilces in il_ilce.items():
        for ilce in ilces:
            site_anahtarlar[ilce_anahtar(il, ilce)] = (il, ilce)

    dosyalar = sorted(x for x in os.listdir(rehber_klasoru) if x.lower().endswith(".html"))
    havuz = {}                                       # yer_id -> kayıt
    dosya_ozet = {}                                  # dosya -> sayaçlar
    il_atlayan = collections.Counter()
    olc = collections.Counter()                      # ic / yakin / orta / uzak
    uzaklar = []
    print(f"{len(dosyalar)} rehber taranıyor...")
    for n, ad in enumerate(dosyalar, 1):
        kayitlar = rehber_oku(os.path.join(rehber_klasoru, ad))
        if not kayitlar:
            continue
        tum_il = ad.endswith("-Tum-Ilceler.html")
        if tum_il:
            kaynak_il = fold(ad[:-len("-Tum-Ilceler.html")])
            kaynak_ilce = None
        else:
            hedef = dosya_haritasi.get(ad)
            if not hedef:
                continue
            kaynak_il, kaynak_ilce = fold(hedef[0]), ilce_anahtar(*hedef)
        s = {"toplam": 0, "ilce_degisti": 0, "il_degisti": 0, "yok": 0, "dag": collections.Counter(), "tur": "il" if tum_il else "ilce"}
        for x in kayitlar:
            try:
                lat, lon = float(x["e"]), float(x["b"])
            except Exception:
                s["yok"] += 1
                continue
            il, ilce, mesafe = yer_bul(liste, ag, lat, lon)
            s["toplam"] += 1
            s["dag"][ilce_anahtar(il, ilce)] += 1
            kategori = "ic" if mesafe == 0 else "yakin" if mesafe <= ESIK_YAKIN_M else "orta" if mesafe <= ESIK_UZAK_M else "uzak"
            olc[kategori] += 1
            if fold(il) != kaynak_il:
                s["il_degisti"] += 1
                il_atlayan[(kaynak_il, fold(il))] += 1
            if not tum_il and ilce_anahtar(il, ilce) != kaynak_ilce:
                s["ilce_degisti"] += 1
            yid = _yer_id(x.get("l"))
            if kategori == "uzak" and len(uzaklar) < 40:
                uzaklar.append(f"{x.get('n','?')[:40]} ({ad}) {int(mesafe)} m, en yakın: {il}/{ilce}")
            if yid and yid not in havuz:
                havuz[yid] = {"il": il, "ilce": ilce, "m": round(mesafe), "k": kategori, "n": x.get("n", "")[:60],
                              "kaynak": ad}
        dosya_ozet[ad] = s
        if n % 50 == 0:
            print(f"   {n}/{len(dosyalar)}")

    # havuzdaki gerçek ilçe sayıları
    sayac = collections.Counter(ilce_anahtar(v["il"], v["ilce"]) for v in havuz.values() if v["k"] != "uzak")
    mevcut = {}
    for ad, s in dosya_ozet.items():
        if s["tur"] == "ilce":
            mevcut[ilce_anahtar(*dosya_haritasi[ad])] = (ad, s["toplam"])
    altinda = sorted(((mevcut[k][0], mevcut[k][1], sayac.get(k, 0)) for k in mevcut if sayac.get(k, 0) < MIN_MEKAN),
                     key=lambda r: r[2])
    yeni_acilacak = sorted(((k, v) for k, v in sayac.items() if k not in mevcut and v >= MIN_MEKAN), key=lambda r: -r[1])

    satir = []
    A = satir.append
    toplam = sum(v for v in olc.values())
    A("LOCAL RADAR - İLÇE ATAMA RAPORU (rehber dosyalarına dokunulmadı)")
    A("=" * 60)
    A(f"İncelenen mekan kaydı: {toplam:,}   Tekil mekan (Place ID): {len(havuz):,}")
    A("")
    A("1) POLİGON UYUMU")
    A(f"   İlçe sınırı içinde      : {olc['ic']:,}")
    A(f"   Dışında, 0-{ESIK_YAKIN_M} m yakın   : {olc['yakin']:,}  (en yakın ilçeye atanır)")
    A(f"   {ESIK_YAKIN_M}-{ESIK_UZAK_M} m arası       : {olc['orta']:,}  (kontrol listesi)")
    A(f"   {ESIK_UZAK_M} m'den uzak       : {olc['uzak']:,}  (karantina: yurt dışı / bozuk koordinat)")
    if uzaklar:
        A("   Uzak örnekler:")
        for u in uzaklar:
            A("     - " + u)
    A("")
    A("2) İL DEĞİŞTİREN MEKANLAR (dosyanın ili -> gerçek il)")
    if not il_atlayan:
        A("   Yok.")
    for (a, b), c in il_atlayan.most_common(40):
        A(f"   {a} -> {b}: {c:,}")
    A("")
    A("3) İSİM UYUŞMAZLIKLARI")
    yeni_yok = sorted(k for k in yeni_anahtarlar if k not in site_anahtarlar)
    site_yok = sorted(k for k in site_anahtarlar if k not in yeni_anahtarlar)
    A(f"   Sınır verisinde var, bizim ilçe listemizde yok ({len(yeni_yok)}): " + ", ".join(yeni_yok[:60]))
    A(f"   Bizim listede var, sınır verisinde yok ({len(site_yok)}): " + ", ".join(
        f"{site_anahtarlar[k][0]}/{site_anahtarlar[k][1]}" for k in site_yok[:60]))
    A("")
    A("4) İLÇE REHBERLERİNDE ETKİ (ilçe dosyaları)")
    il_dosyalar = [(ad, s) for ad, s in dosya_ozet.items() if s["tur"] == "il"]
    ilce_dosyalar = [(ad, s) for ad, s in dosya_ozet.items() if s["tur"] == "ilce"]
    A(f"   İl rehberi dosyası: {len(il_dosyalar)}   İlçe rehberi dosyası: {len(ilce_dosyalar)}")
    t = sum(s["toplam"] for _, s in ilce_dosyalar)
    d = sum(s["ilce_degisti"] for _, s in ilce_dosyalar)
    A(f"   İlçe rehberlerindeki mekanların {d:,} / {t:,} tanesi ({(100*d/t if t else 0):.0f}%) başka ilçeye ait çıktı.")
    en_cok = sorted(ilce_dosyalar, key=lambda r: -r[1]["ilce_degisti"])[:15]
    A("   En çok yanlış ilçeli mekan içeren rehberler:")
    for ad, s in en_cok:
        A(f"     {ad}: {s['ilce_degisti']:,} / {s['toplam']:,}")
    A("")
    A("4b) İÇERİĞİ DOSYA ADIYLA UYUŞMAYAN İLÇE REHBERLERİ (kendi ilçesine düşen mekan %25'ten az)")
    sorunlu = []
    for ad, s in ilce_dosyalar:
        if s["toplam"] >= 5 and s["dag"]:
            k, say = s["dag"].most_common(1)[0]
            kendi = s["dag"].get(ilce_anahtar(*dosya_haritasi[ad]), 0)
            if k != ilce_anahtar(*dosya_haritasi[ad]) and kendi / s["toplam"] < 0.25:
                sorunlu.append((ad, s["toplam"], yeni_adlar.get(k, (k, k))[1], say))
    for ad, top, k, say in sorted(sorunlu, key=lambda r: -r[1]):
        A(f"     {ad}: {top:,} mekanın en çoğu ({say:,}) aslında '{k}' ilçesinde")
    if not sorunlu:
        A("   Yok.")
    A("")
    A("4c) KOORDİNATI OLMAYAN KAYITLARI ÇOK OLAN REHBERLER (eski biçim ya da boş tarama; yeniden taranmalı)")
    koordsuz = [(ad, s["yok"], s["yok"] + s["toplam"]) for ad, s in dosya_ozet.items() if s["yok"] and s["yok"] >= 0.5 * (s["yok"] + s["toplam"])]
    for ad, y, t in sorted(koordsuz, key=lambda r: -r[1]):
        A(f"     {ad}: {y:,} / {t:,} kayıtta koordinat yok")
    if not koordsuz:
        A("   Yok.")
    A("")
    A(f"5) {MIN_MEKAN} MEKANIN ALTINA DÜŞECEK MEVCUT İLÇE REHBERLERİ ({len(altinda)} adet)")
    A("   (dosya, şimdiki mekan sayısı, taşıma sonrası mekan sayısı)")
    for ad, once, sonra in altinda[:80]:
        A(f"     {ad}: {once:,} -> {sonra:,}")
    A("")
    A(f"6) YENİ İLÇE REHBERİ OLABİLECEKLER (şu an rehberi yok, havuzda >= {MIN_MEKAN} mekan: {len(yeni_acilacak)} adet)")
    for k, v in yeni_acilacak[:60]:
        il_, ilce_ = yeni_adlar.get(k, (k, ""))
        A(f"     {il_} / {ilce_}: {v:,}")
    metin = "\n".join(satir)
    with open(os.path.join(cikti_klasoru, "ilce_rapor.txt"), "w", encoding="utf-8") as f:
        f.write(metin)
    with open(os.path.join(cikti_klasoru, "ilce_atama.json"), "w", encoding="utf-8") as f:
        json.dump(havuz, f, ensure_ascii=False)
    print(metin[:6000])
    print(f"\nRapor kaydedildi: ilce_rapor.txt  (atamalar: ilce_atama.json)")
    return metin


if __name__ == "__main__":
    import gece_tarama as t
    klasor = os.path.join(t.DEPO_KLASORU, t.DEPO_ALT_KLASOR) if t.DEPO_ALT_KLASOR else t.DEPO_KLASORU
    rapor(klasor, t.IL_ILCE, t._ilce_dosya_haritasi())
