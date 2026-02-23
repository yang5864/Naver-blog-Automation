@echo off
setlocal EnableExtensions EnableDelayedExpansion

if not defined SIGN_ENABLE set "SIGN_ENABLE=1"
if not defined SIGN_REQUIRED set "SIGN_REQUIRED=0"
if not defined SIGN_TIMESTAMP_URL set "SIGN_TIMESTAMP_URL=http://timestamp.digicert.com"
if not defined SIGN_DESC set "SIGN_DESC=BlogCommentBot"
if not defined SIGN_URL set "SIGN_URL=https://github.com/yang5864/Naver-blog-Automation"

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

echo [INFO] Closing running BlogCommentBot if exists...
taskkill /F /IM BlogCommentBot.exe >nul 2>nul
timeout /t 1 /nobreak >nul

call :CLEAN_OLD_RANDOM_RUN_DIRS

set "DIST_OUT=dist_run"
set "WORK_OUT=build_run"

call :CLEAN_ACTIVE_RUN_DIRS

call :RUN_BUILD

if errorlevel 1 (
  echo [WARN] First build failed. Retrying once after cleanup...
  taskkill /F /IM BlogCommentBot.exe >nul 2>nul
  timeout /t 1 /nobreak >nul
  call :CLEAN_ACTIVE_RUN_DIRS
  call :RUN_BUILD
  if errorlevel 1 (
    echo.
    echo [ERROR] Build failed. Check log above.
    exit /b 1
  )
)

set "BUILT_EXE=%DIST_OUT%\BlogCommentBot\BlogCommentBot.exe"
if not exist "%BUILT_EXE%" (
  echo [ERROR] Built exe not found: %BUILT_EXE%
  exit /b 1
)

call :SIGN_ARTIFACT "%BUILT_EXE%"
if errorlevel 1 (
  echo [ERROR] Signing step failed.
  exit /b 1
)

echo.
echo [DONE] Build finished: %DIST_OUT%\BlogCommentBot\BlogCommentBot.exe
if exist dist_latest rmdir /s /q dist_latest
xcopy "%DIST_OUT%\BlogCommentBot" "dist_latest\BlogCommentBot\" /e /i /y >nul
echo [DONE] Latest copy: dist_latest\BlogCommentBot\BlogCommentBot.exe
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

:FIND_SIGNTOOL
set "SIGNTOOL_PATH="
for /f "delims=" %%I in ('where signtool.exe 2^>nul') do (
  set "SIGNTOOL_PATH=%%I"
  goto :FIND_SIGNTOOL_DONE
)
for /f "delims=" %%I in ('dir /b /s "%ProgramFiles(x86)%\Windows Kits\10\bin\*\x64\signtool.exe" 2^>nul') do (
  set "SIGNTOOL_PATH=%%I"
  goto :FIND_SIGNTOOL_DONE
)
for /f "delims=" %%I in ('dir /b /s "%ProgramFiles(x86)%\Windows Kits\10\bin\*\x86\signtool.exe" 2^>nul') do (
  set "SIGNTOOL_PATH=%%I"
  goto :FIND_SIGNTOOL_DONE
)
:FIND_SIGNTOOL_DONE
if defined SIGNTOOL_PATH (
  echo [INFO] SignTool: !SIGNTOOL_PATH!
)
exit /b 0

:SIGN_ARTIFACT
set "TARGET_EXE=%~1"

if /I "%SIGN_ENABLE%"=="0" (
  echo [INFO] Signing disabled ^(SIGN_ENABLE=0^). Skipping.
  exit /b 0
)

if not exist "%TARGET_EXE%" (
  echo [ERROR] Target not found for signing: %TARGET_EXE%
  exit /b 1
)

set "HAS_IDENTITY=0"
if defined SIGN_CERT_FILE set "HAS_IDENTITY=1"
if defined SIGN_CERT_SUBJECT set "HAS_IDENTITY=1"
if defined SIGN_CERT_SHA1 set "HAS_IDENTITY=1"

if "%HAS_IDENTITY%"=="0" (
  echo [WARN] Signing identity not configured.
  echo [WARN] Set one of: SIGN_CERT_FILE ^(PFX^), SIGN_CERT_SUBJECT, SIGN_CERT_SHA1
  if /I "%SIGN_REQUIRED%"=="1" (
    echo [ERROR] SIGN_REQUIRED=1 but no certificate identity was provided.
    exit /b 1
  )
  echo [WARN] Output remains unsigned.
  exit /b 0
)

call :FIND_SIGNTOOL
if not defined SIGNTOOL_PATH (
  echo [ERROR] signtool.exe not found. Install Windows SDK.
  if /I "%SIGN_REQUIRED%"=="1" exit /b 1
  echo [WARN] Output remains unsigned.
  exit /b 0
)

set SIGN_CMD=sign /fd SHA256 /td SHA256 /tr "%SIGN_TIMESTAMP_URL%" /d "%SIGN_DESC%" /du "%SIGN_URL%"
if defined SIGN_CERT_FILE set SIGN_CMD=!SIGN_CMD! /f "%SIGN_CERT_FILE%"
if defined SIGN_CERT_PASSWORD set SIGN_CMD=!SIGN_CMD! /p "%SIGN_CERT_PASSWORD%"
if defined SIGN_CERT_SHA1 set SIGN_CMD=!SIGN_CMD! /sha1 "%SIGN_CERT_SHA1%"
if defined SIGN_CERT_SUBJECT set SIGN_CMD=!SIGN_CMD! /n "%SIGN_CERT_SUBJECT%"
if defined SIGN_CERT_STORE set SIGN_CMD=!SIGN_CMD! /s "%SIGN_CERT_STORE%"
if /I "%SIGN_CERT_MACHINE%"=="1" set "SIGN_CMD=!SIGN_CMD! /sm"
if /I "%SIGN_APPEND%"=="1" set "SIGN_CMD=!SIGN_CMD! /as"
if not defined SIGN_CERT_SHA1 if not defined SIGN_CERT_SUBJECT if not defined SIGN_CERT_FILE set "SIGN_CMD=!SIGN_CMD! /a"

echo [INFO] Signing executable...
"!SIGNTOOL_PATH!" !SIGN_CMD! "%TARGET_EXE%"
if errorlevel 1 (
  echo [ERROR] Code signing failed.
  if /I "%SIGN_REQUIRED%"=="1" exit /b 1
  echo [WARN] Output remains unsigned.
  exit /b 0
)

echo [INFO] Verifying signature...
"!SIGNTOOL_PATH!" verify /pa /v "%TARGET_EXE%" >nul
if errorlevel 1 (
  echo [ERROR] Signature verification failed.
  if /I "%SIGN_REQUIRED%"=="1" exit /b 1
  echo [WARN] Signature verification failed but build will continue.
  exit /b 0
)

echo [DONE] Code signing completed.
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
      --name "BlogCommentBot" ^
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
      --name "BlogCommentBot" ^
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
      --name "BlogCommentBot" ^
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
      --name "BlogCommentBot" ^
      --add-data "config.json;." ^
      main.py
  )
)
exit /b %errorlevel%
