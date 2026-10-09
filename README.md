# 📡 Local Radar

**Scan, discover, plan.** — Find the best local places around you.

Local Radar is a personal travel guide generator. It scrapes Google Maps for highly-rated places in a given district or neighborhood, filters them by rating and review count, categorizes them automatically, and generates an interactive HTML guide.

## ✨ Features

- 🗺️ **Interactive map** — Leaflet + OpenStreetMap, no API key needed
- 📅 **Day planner** — Assign places to G1, G2, G3, G4, G5 and filter by day
- 💰 **Budget tracker** — Total, per person, and per day cost estimation
- ⭐ **Favorites & tracking** — Mark places as favorites, visited, add notes
- 📤 **Share & route** — WhatsApp share and Google Maps multi-stop route
- 🌙 **Dark mode** — Automatic based on system preference
- 📱 **Mobile-friendly** — Responsive design for phones and tablets
- 🌍 **Multi-language ready** — All output filenames and branding in English

## 🎯 What It Does

1. **Location lookup** — Nominatim (OpenStreetMap) resolves the district to coordinates
2. **Grid generation** — Slippy-map tiles divide the area into searchable cells
3. **Search** — Playwright navigates to each Google Maps search URL and scrolls the feed
4. **Extraction** — Parses name, rating, review count, address, and coordinates
5. **Filtering** — Removes permanently closed, out-of-area, low-rated, and low-review places
6. **Categorization** — Rule-based classifier with over 200 keywords
7. **Neighborhood detection** — OpenStreetMap boundaries + address parsing + Nominatim fallback
8. **Deduplication** — Same name + coordinates merged automatically
9. **Export** — CSV, XLSX, JSON, KML, and interactive HTML

## 🚀 Quick Start

### Requirements

- Python 3.10 or newer
- Windows, Linux, or macOS
- Playwright (Chromium or Edge)
- openpyxl (for Excel output)

### Installation

```bash
git clone https://github.com/cisey/local-radar.git
cd local-radar
pip install -r requirements.txt
playwright install chromium
python pencere_v4.py
```

### First Scan

1. Open the GUI
2. Select **City** and **District** (or type a custom location)
3. Choose a mode: Fast, Normal, or Comprehensive
4. Set minimum rating and review count
5. Click **Start**

Wait 5 to 20 minutes depending on the area.

## 📁 Project Structure

```
local-radar/
├── gezi_rehberi_v4.py      # Core engine
├── pencere_v4.py           # Tkinter GUI
├── test_gezi_v4_core.py    # Test suite
├── requirements.txt        # Dependencies
├── README.md               # This file
├── LICENSE                 # MIT License
└── .gitignore              # Excludes personal data
```

## 📊 Output Formats

| Format | Purpose |
|--------|---------|
| HTML | Interactive guide with map and filters |
| CSV | Raw data for spreadsheet analysis |
| XLSX | Formatted Excel with color-coded ratings |
| JSON | Programmatic use |
| KML | Opens in Google Earth and My Maps |

## ⚠️ Disclaimer

This tool scrapes publicly available data from Google Maps. Use it responsibly:

- Personal use only — respect Google's Terms of Service
- Do not run aggressive parallel scans
- Google may change its DOM at any time
- Not affiliated with Google

## 📜 License

MIT License — see the LICENSE file.

## 💡 Acknowledgments

- Playwright — browser automation
- OpenStreetMap / Nominatim / Overpass — map data
- Leaflet — interactive maps
- Openpyxl — Excel output

Made with ❤️ for travelers and foodies.