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

echo [INFO] Closing running SeoiChuPro if exists...
taskkill /F /IM SeoiChuPro.exe >nul 2>nul
timeout /t 1 /nobreak >nul

if exist dist\SeoiChuPro rmdir /s /q dist\SeoiChuPro >nul 2>nul
if exist build\SeoiChuPro rmdir /s /q build\SeoiChuPro >nul 2>nul

call :RUN_BUILD

if errorlevel 1 (
  echo [WARN] First build failed. Retrying once after cleanup...
  taskkill /F /IM SeoiChuPro.exe >nul 2>nul
  timeout /t 1 /nobreak >nul
  if exist dist\SeoiChuPro rmdir /s /q dist\SeoiChuPro >nul 2>nul
  if exist build\SeoiChuPro rmdir /s /q build\SeoiChuPro >nul 2>nul
  call :RUN_BUILD
  if errorlevel 1 (
    echo.
    echo [ERROR] Build failed. Check log above.
    exit /b 1
  )
)

echo.
echo [DONE] Build finished: dist\SeoiChuPro\SeoiChuPro.exe
endlocal
exit /b 0

:RUN_BUILD
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
exit /b %errorlevel%
