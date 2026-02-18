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

if not exist "msedgedriver.exe" (
  for /f "delims=" %%I in ('where msedgedriver 2^>nul') do (
    echo [INFO] Found msedgedriver at %%I
    copy /y "%%I" "msedgedriver.exe" >nul
    goto :EDGE_DRIVER_DONE
  )
)
:EDGE_DRIVER_DONE

if not exist "chromedriver.exe" (
  for /f "delims=" %%I in ('where chromedriver 2^>nul') do (
    echo [INFO] Found chromedriver at %%I
    copy /y "%%I" "chromedriver.exe" >nul
    goto :CHROME_DRIVER_DONE
  )
)
:CHROME_DRIVER_DONE

echo [INFO] Closing running SeoiChuPro if exists...
taskkill /F /IM SeoiChuPro.exe >nul 2>nul
timeout /t 1 /nobreak >nul

set "DIST_OUT=dist_run_%RANDOM%_%RANDOM%"
set "WORK_OUT=build_run_%RANDOM%_%RANDOM%"

call :RUN_BUILD

if errorlevel 1 (
  echo [WARN] First build failed. Retrying once after cleanup...
  taskkill /F /IM SeoiChuPro.exe >nul 2>nul
  timeout /t 1 /nobreak >nul
  set "DIST_OUT=dist_run_%RANDOM%_%RANDOM%"
  set "WORK_OUT=build_run_%RANDOM%_%RANDOM%"
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

:RUN_BUILD
set "DRIVER_BIN_ARGS="
if exist "msedgedriver.exe" set "DRIVER_BIN_ARGS=%DRIVER_BIN_ARGS% --add-binary msedgedriver.exe;."
if exist "chromedriver.exe" set "DRIVER_BIN_ARGS=%DRIVER_BIN_ARGS% --add-binary chromedriver.exe;."

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
      %DRIVER_BIN_ARGS% main.py
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
      %DRIVER_BIN_ARGS% main.py
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
      %DRIVER_BIN_ARGS% main.py
  ) else (
    pyinstaller ^
      --noconfirm ^
      --clean ^
      --windowed ^
      --distpath "%DIST_OUT%" ^
      --workpath "%WORK_OUT%" ^
      --name "SeoiChuPro" ^
      --add-data "config.json;." ^
      %DRIVER_BIN_ARGS% main.py
  )
)
exit /b %errorlevel%
