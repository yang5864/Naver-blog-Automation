@echo off
setlocal

if "%VIRTUAL_ENV%"=="" (
  echo [INFO] Creating local venv...
  python -m venv .venv
)

call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt pyinstaller

pyinstaller ^
  --noconfirm ^
  --clean ^
  --windowed ^
  --name "SeoiChuPro" ^
  --add-data "config.json;." ^
  main.py

echo.
echo [DONE] Build finished: dist\SeoiChuPro\SeoiChuPro.exe
endlocal
