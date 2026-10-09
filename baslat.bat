@echo off
chcp 65001 >nul
title Local Radar
cd /d "%~dp0"

echo.
echo ═══════════════════════════════════════════════════════════
echo   📡 Local Radar - Başlatılıyor...
echo ═══════════════════════════════════════════════════════════
echo.

REM Python kurulu mu kontrol et
python --version >nul 2>&1
if errorlevel 1 (
    echo [HATA] Python bulunamadi!
    echo Lutfen Python 3.10+ yukleyin: https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
)

REM Playwright kurulu mu kontrol et
python -c "import playwright" >nul 2>&1
if errorlevel 1 (
    echo [UYARI] Playwright kurulu degil. Yukleniyor...
    pip install playwright
    playwright install chromium
)

REM GUI'yi baslat
echo GUI baslatiliyor...
echo.
python local_radar_gui.py

REM Hata olduysa pencereyi açık tut
if errorlevel 1 (
    echo.
    echo [HATA] GUI baslatilamadi!
    pause
)