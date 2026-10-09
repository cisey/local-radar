import importlib.util
import os

# Locate the module folder automatically (Windows/Linux/Mac compatible)
KLASOR = os.path.dirname(os.path.abspath(__file__))
MODUL_YOLU = os.path.join(KLASOR, "local_radar_core.py")

# Check if the module file exists
if not os.path.exists(MODUL_YOLU):
    raise FileNotFoundError(
        f"local_radar_core.py not found!\n"
        f"Looking at: {MODUL_YOLU}\n"
        f"Make sure test_local_radar.py and local_radar_core.py are in the same folder."
    )

spec = importlib.util.spec_from_file_location("lrc", MODUL_YOLU)
g = importlib.util.module_from_spec(spec)
spec.loader.exec_module(g)

kayitlar = [
    {"Yer": "ATM 1", "Bölüm": "Diğer", "Grup": "Banka ve ATM", "Puan": 0.0, "Yorum Sayısı": 0, "Güvenilir Skor": 0.0, "_puansiz": True},
    {"Yer": "ATM 2", "Bölüm": "Diğer", "Grup": "Banka ve ATM", "Puan": 4.8, "Yorum Sayısı": 120, "Güvenilir Skor": 4.7, "_puansiz": False},
    {"Yer": "Düşük Kebap", "Bölüm": "Kebap & Et", "Grup": "Kebap", "Puan": 3.9, "Yorum Sayısı": 80, "Güvenilir Skor": 3.95, "_puansiz": False},
    {"Yer": "İyi Kebap", "Bölüm": "Kebap & Et", "Grup": "Kebap", "Puan": 4.5, "Yorum Sayısı": 120, "Güvenilir Skor": 4.48, "_puansiz": False},
    {"Yer": "Puansız Kebap", "Bölüm": "Kebap & Et", "Grup": "Kebap", "Puan": 0.0, "Yorum Sayısı": 0, "Güvenilir Skor": 0.0, "_puansiz": True},
    {"Yer": "A Kafe", "Bölüm": "Kafe & Kahvaltı", "Grup": "Kafe", "Puan": 4.6, "Yorum Sayısı": 80, "Güvenilir Skor": 4.55, "_puansiz": False},
    {"Yer": "B Kafe Puansız", "Bölüm": "Kafe & Kahvaltı", "Grup": "Kafe", "Puan": 0.0, "Yorum Sayısı": 0, "Güvenilir Skor": 0.0, "_puansiz": True},
]

sonuc = g.esik_uygula(kayitlar, 4.0, 50)
print("FILTRE_SONUCU_ADET", len(sonuc))
print("FILTRE_SONUCU_ISIMLER", [r["Yer"] for r in sonuc])

banka_puansiz_gecti = any(r["Yer"] == "ATM 1" for r in sonuc)
yemek_alt_elendi = all(r["Yer"] not in {"Düşük Kebap", "Puansız Kebap"} for r in sonuc)

kafe_sira = [r["Yer"] for r in sonuc if r["Bölüm"] == "Kafe & Kahvaltı"]
puansiz_grup_sonda = (kafe_sira == ["A Kafe"])

print("KONTROL_A_BANKA_PUANSIZ_GECTI", banka_puansiz_gecti)
print("KONTROL_B_YEMEK_4_0_50_ALTI_ELENDI", yemek_alt_elendi)
print("KONTROL_C_PUANSIZ_GRUP_SONUNA_DUSTU", puansiz_grup_sonda)

alanlar = [(37.01, 37.79, 1.2, None)]
hucreler = g.sabit_izgara_hucreleri(alanlar, 1.0)
tahmin = g.arama_sayisi_tahmini(alanlar, 3, 1.0)

print("SABIT_IZGARA_HUCRE_SAYISI", len(hucreler))
print("ARAMA_SAYISI_TAHMINI", tahmin)
print("TAHMIN_DOGRULAMA", tahmin == len(hucreler) * 3)
print("ILK_HUCRE_ORNEK", hucreler[0] if hucreler else None)