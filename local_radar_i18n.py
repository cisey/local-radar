"""
Local Radar - Internationalization (i18n)
Language strings for the GUI.
"""

_aktif_dil = "tr"


def dil_ayarla(dil):
    """Set the active language."""
    global _aktif_dil
    if dil in METINLER:
        _aktif_dil = dil


def dil_al():
    """Get the current language code."""
    return _aktif_dil


def t(anahtar):
    """Get the translated string for the given key."""
    return METINLER.get(_aktif_dil, METINLER["tr"]).get(anahtar, anahtar)


# ═══════════════════════════════════════════════════════════
# TRANSLATIONS
# ═══════════════════════════════════════════════════════════
METINLER = {
    "tr": {
        # Window
        "baslik": "📡 Local Radar · v4.3",
        # Form labels
        "il": "İl",
        "ilce": "İlçe",
        "mahalle": "Mahalle",
        "mahalle_ipucu": "Tüm ilçe için boş bırakın. Virgülle ayırarak çoklu arama yapabilirsiniz (Örn: Karataş, Akkent)",
        "yaricap": "Yarıçap (km)",
        "yaricap_ipucu": "Boş bırakırsanız sistem otomatik belirler",
        "min_puan": "En az puan",
        "min_yorum": "En az yorum",
        "ozel_arama": "Özel Arama",
        "ozel_arama_ipucu": "Listede olmayan bir şey aramak için (Örn: Noter, Halı Saha)",
        # Scan mode
        "tarama_modu": "Tarama Modu:",
        "hucre_km": "Hücre boyutu (km):",
        # Categories
        "kategoriler": "Kategoriler",
        "yemek": "Yemek (Restoran, Kafe)",
        "gezi": "Gezilecek Yerler",
        "alisveris": "Alışveriş (Market, Giyim)",
        "saglik": "Sağlık (Hastane, Eczane)",
        "oto": "Oto & Ulaşım (Tamir, Lastik)",
        "konaklama": "Konaklama (Otel)",
        "banka": "Banka & Kargo",
        "tumu": "TÜMÜNÜ ARA (DİKKAT: saatler sürebilir!)",
        # Options
        "mahalle_bul": "Yerlerin mahallesini bul",
        "goster": "Tarayıcı penceresini göster",
        "izgara": "Yoğun yerleri otomatik parçala (kapsamlı)",
        "ham_kullan": "Tarama yapma, son taramayı (ham veri) kullan",
        "devam": "Yarım kalan taramaya devam et",
        "hizli": "Hızlı mod (resim engelle, kısa bekleme)",
        "tekrar": "Son 30 günde yapılan aramaları atla",
        "verimsiz": "Verimsiz kelimeleri atla",
        "paralel": "Paralel:",
        # Buttons
        "baslat": "Başlat",
        "durdur": "Durdur",
        "havuz_sifirla": "Havuzu Sıfırla",
        "manuel_ekle": "Manuel Mekan Ekle",
        "klasor_ac": "Klasörü Aç",
        "excel_ac": "Excel'i Aç",
        "json_btn": "JSON",
        "kml_btn": "KML",
        "ilce_rehberi": "📍 İlçe Haritası",
        "hepsi_rehberi": "📡 HEPSİ (Local Radar)",
        "kategori_esikleri": "Kategori Eşikleri...",
        "profil_kaydet": "Ayarları Profile Kaydet",
        "profil_yukle": "Profil Yükle",
        # Status
        "sure": "Süre: –",
        # Language selector
        "dil": "Dil:",
        # Messages
        "hazir": "📡 Local Radar hazır. Çoklu ilçe taramalarında sonuçlar 'local_radar_all.html' dosyasında birikir.",
        "ipucu": "İpucu: 'Tarama yapma' seçeneğiyle son taramayı saniyeler içinde farklı filtrelerle işleyebilirsiniz.",
        # Scan modes
        "mod_ozel": "Özel Seçim",
        "mod_hizli": "Hızlı (yemek ve gezi, tek parça)",
        "mod_normal": "Normal (yemek ve gezi, ızgaralı)",
        "mod_kapsamli": "Kapsamlı (her şey, ızgaralı)",
        "mod_sabit": "Sabit ızgara (hücre boyutu km)",
    },
    "en": {
        # Window
        "baslik": "📡 Local Radar · v4.3",
        # Form labels
        "il": "City",
        "ilce": "District",
        "mahalle": "Neighborhood",
        "mahalle_ipucu": "Leave empty for the whole district. Separate with commas for multiple (e.g. Karataş, Akkent)",
        "yaricap": "Radius (km)",
        "yaricap_ipucu": "Leave empty for auto-detection",
        "min_puan": "Min rating",
        "min_yorum": "Min reviews",
        "ozel_arama": "Custom search",
        "ozel_arama_ipucu": "Search for something not in the list (e.g. Notary, Sports Field)",
        # Scan mode
        "tarama_modu": "Scan mode:",
        "hucre_km": "Cell size (km):",
        # Categories
        "kategoriler": "Categories",
        "yemek": "Food (Restaurants, Cafes)",
        "gezi": "Attractions",
        "alisveris": "Shopping (Market, Clothing)",
        "saglik": "Health (Hospital, Pharmacy)",
        "oto": "Auto & Transport (Repair, Tires)",
        "konaklama": "Accommodation (Hotel)",
        "banka": "Bank & Cargo",
        "tumu": "SCAN EVERYTHING (WARNING: may take hours!)",
        # Options
        "mahalle_bul": "Detect neighborhoods",
        "goster": "Show browser window",
        "izgara": "Auto-split dense areas (comprehensive)",
        "ham_kullan": "Skip scan, use last raw data",
        "devam": "Resume incomplete scan",
        "hizli": "Fast mode (block images, short waits)",
        "tekrar": "Skip searches from last 30 days",
        "verimsiz": "Skip inefficient keywords",
        "paralel": "Parallel:",
        # Buttons
        "baslat": "Start",
        "durdur": "Stop",
        "havuz_sifirla": "Reset Pool",
        "manuel_ekle": "Add Manual Place",
        "klasor_ac": "Open Folder",
        "excel_ac": "Open Excel",
        "json_btn": "JSON",
        "kml_btn": "KML",
        "ilce_rehberi": "📍 District Map",
        "hepsi_rehberi": "📡 ALL (Local Radar)",
        "kategori_esikleri": "Category Thresholds...",
        "profil_kaydet": "Save Settings as Profile",
        "profil_yukle": "Load Profile",
        # Status
        "sure": "Time: –",
        # Language selector
        "dil": "Language:",
        # Messages
        "hazir": "📡 Local Radar ready. Multi-district scans accumulate results in 'local_radar_all.html'.",
        "ipucu": "Tip: Use 'Skip scan' to re-process the last scan with different filters in seconds.",
        # Scan modes
        "mod_ozel": "Custom Selection",
        "mod_hizli": "Fast (food + attractions, single pass)",
        "mod_normal": "Normal (food + attractions, grid)",
        "mod_kapsamli": "Comprehensive (everything, grid)",
        "mod_sabit": "Fixed grid (cell size in km)",
    }
}