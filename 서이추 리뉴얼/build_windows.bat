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

if exist "WebView2Loader (1).dll" (
  echo [INFO] Normalizing WebView2 loader filename...
  copy /y "WebView2Loader (1).dll" "WebView2Loader.dll" >nul
)

echo [INFO] Closing running SeoiChuPro if exists...
taskkill /F /IM SeoiChuPro.exe >nul 2>nul
timeout /t 1 /nobreak >nul

call :CLEAN_OLD_RANDOM_RUN_DIRS

set "DIST_OUT=dist_run"
set "WORK_OUT=build_run"

call :CLEAN_ACTIVE_RUN_DIRS

call :RUN_BUILD

if errorlevel 1 (
  echo [WARN] First build failed. Retrying once after cleanup...
  taskkill /F /IM SeoiChuPro.exe >nul 2>nul
  timeout /t 1 /nobreak >nul
  call :CLEAN_ACTIVE_RUN_DIRS
  call :RUN_BUILD
  if errorlevel 1 (
    echo.
    echo [ERROR] Build failed. Check log above.
    exit /b 1
  )
)

echo.
echo [DONE] Build finished: %DIST_OUT%\SeoiChuPro\SeoiChuPro.exe
if exist dist_latest rmdir /s /q dist_latest
xcopy "%DIST_OUT%\SeoiChuPro" "dist_latest\SeoiChuPro\" /e /i /y >nul
echo [DONE] Latest copy: dist_latest\SeoiChuPro\SeoiChuPro.exe
endlocal
exit /b 0

:CLEAN_OLD_RANDOM_RUN_DIRS
for /d %%D in (dist_run_*) do (
  if exist "%%D" rmdir /s /q "%%D"
)
for /d %%D in (build_run_*) do (
  if exist "%%D" rmdir /s /q "%%D"
)
exit /b 0

:CLEAN_ACTIVE_RUN_DIRS
if exist "%DIST_OUT%" rmdir /s /q "%DIST_OUT%"
if exist "%WORK_OUT%" rmdir /s /q "%WORK_OUT%"
exit /b 0

:RUN_BUILD
if exist fonts (
  if exist "WebView2Loader.dll" (
    pyinstaller ^
      --noconfirm ^
      --clean ^
      --windowed ^
      --distpath "%DIST_OUT%" ^
      --workpath "%WORK_OUT%" ^
      --name "SeoiChuPro" ^
      --add-data "config.json;." ^
      --add-data "fonts;fonts" ^
      --add-data "WebView2Loader.dll;." ^
      main.py
  ) else (
    pyinstaller ^
      --noconfirm ^
      --clean ^
      --windowed ^
      --distpath "%DIST_OUT%" ^
      --workpath "%WORK_OUT%" ^
      --name "SeoiChuPro" ^
      --add-data "config.json;." ^
      --add-data "fonts;fonts" ^
      main.py
  )
) else (
  if exist "WebView2Loader.dll" (
    pyinstaller ^
      --noconfirm ^
      --clean ^
      --windowed ^
      --distpath "%DIST_OUT%" ^
      --workpath "%WORK_OUT%" ^
      --name "SeoiChuPro" ^
      --add-data "config.json;." ^
      --add-data "WebView2Loader.dll;." ^
      main.py
  ) else (
    pyinstaller ^
      --noconfirm ^
      --clean ^
      --windowed ^
      --distpath "%DIST_OUT%" ^
      --workpath "%WORK_OUT%" ^
      --name "SeoiChuPro" ^
      --add-data "config.json;." ^
      main.py
  )
)
exit /b %errorlevel%
