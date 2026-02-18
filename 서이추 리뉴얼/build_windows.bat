@echo off
setlocal

if "%VIRTUAL_ENV%"=="" (
  echo [INFO] Creating local venv...
  python -m venv .venv
)

call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt pyinstaller

if not exist config.json (
  echo [INFO] config.json not found. Creating default config.json...
  python -c "import pathlib; pathlib.Path('config.json').write_text('{}\n', encoding='utf-8')"
)

if exist fonts (
  pyinstaller ^
    --noconfirm ^
    --clean ^
    --windowed ^
    --name "SeoiChuPro" ^
    --add-data "config.json;." ^
    --add-data "fonts;fonts" ^
    main.py
) else (
  pyinstaller ^
    --noconfirm ^
    --clean ^
    --windowed ^
    --name "SeoiChuPro" ^
    --add-data "config.json;." ^
    main.py
)

if errorlevel 1 (
  echo.
  echo [ERROR] Build failed. Check log above.
  exit /b 1
)

echo.
echo [DONE] Build finished: dist\SeoiChuPro\SeoiChuPro.exe
endlocal
