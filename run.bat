@echo off
chcp 65001 >nul
title 📡 Local Radar
cd /d "%~dp0"

cls
echo.
echo  ╔══════════════════════════════════════════════════════════╗
echo  ║                                                          ║
echo  ║              📡  Local Radar                             ║
echo  ║              Scan, discover, plan.                       ║
echo  ║                                                          ║
echo  ╚══════════════════════════════════════════════════════════╝
echo.

REM Python kontrolü
python --version >nul 2>&1
if errorlevel 1 (
    echo  [HATA] Python bulunamadi!
    echo.
    echo  Lutfen Python 3.10+ yukleyin:
    echo  https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
)

REM Playwright kontrolü
python -c "import playwright" >nul 2>&1
if errorlevel 1 (
    echo  [BILGI] Playwright yukleniyor...
    pip install playwright
    playwright install chromium
    echo.
)

echo  GUI baslatiliyor...
echo.
python local_radar_gui.py

if errorlevel 1 (
    echo.
    echo  [HATA] GUI baslatilamadi!
    echo  Hata detaylari icin yukariya bakin.
    echo.
    pause
)