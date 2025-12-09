#!/bin/bash
# Python 스크립트를 직접 실행하는 앱 번들 생성
# bootloader 문제를 완전히 우회

APP_NAME="NaverNeighborPro"
APP_DIR="dist/${APP_NAME}.app"
CONTENTS_DIR="${APP_DIR}/Contents"
MACOS_DIR="${CONTENTS_DIR}/MacOS"
RESOURCES_DIR="${CONTENTS_DIR}/Resources"

# 기존 앱 삭제
rm -rf "$APP_DIR"

# 디렉토리 생성
mkdir -p "$MACOS_DIR"
mkdir -p "$RESOURCES_DIR"

# Python 스크립트 복사
cp NaverNeighborPro_GUI.py "$RESOURCES_DIR/"

# Launcher 스크립트 생성
cat > "$MACOS_DIR/${APP_NAME}" << 'EOF'
#!/bin/bash
# 앱 번들 내부의 Python 스크립트 실행

# 절대 경로로 변환
SCRIPT_PATH="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
APP_DIR="$( cd "$SCRIPT_PATH/../.." && pwd )"
RESOURCES_DIR="$APP_DIR/Contents/Resources"
SCRIPT="$RESOURCES_DIR/NaverNeighborPro_GUI.py"

# 스크립트 존재 확인
if [ ! -f "$SCRIPT" ]; then
    osascript -e 'display dialog "스크립트 파일을 찾을 수 없습니다: '"$SCRIPT"'" buttons {"OK"} default button "OK"'
    exit 1
fi

# Python 경로 찾기
# 1. venv의 Python 시도 (상위 디렉토리에서 venv 찾기)
SCRIPT_DIR="$(dirname "$APP_DIR")"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"  # dist의 상위 디렉토리 (프로젝트 루트)
if [ -d "$PROJECT_DIR/venv" ] && [ -f "$PROJECT_DIR/venv/bin/python3" ]; then
    VENV_PYTHON="$PROJECT_DIR/venv/bin/python3"
    # 실제 Python인지 확인 (PyInstaller bootloader가 아닌지)
    if [ -L "$VENV_PYTHON" ] || [ -f "$VENV_PYTHON" ]; then
        # Python 버전 확인으로 실제 Python인지 검증
        if "$VENV_PYTHON" --version > /dev/null 2>&1; then
            PYTHON="$VENV_PYTHON"
        fi
    fi
fi

# 2. venv Python이 없거나 실패하면 시스템 Python 시도
if [ -z "$PYTHON" ] || [ ! -f "$PYTHON" ]; then
    for py in /usr/bin/python3 /opt/homebrew/bin/python3 /usr/local/bin/python3; do
        if [ -f "$py" ] && "$py" --version > /dev/null 2>&1; then
            PYTHON="$py"
            break
        fi
    done
fi

# 3. 마지막으로 command -v 사용
if [ -z "$PYTHON" ] || [ ! -f "$PYTHON" ]; then
    if command -v python3 &> /dev/null; then
        PYTHON="$(command -v python3)"
    else
        PYTHON="python3"
    fi
fi

# Python 존재 확인
if [ ! -f "$PYTHON" ] && ! command -v "$PYTHON" &> /dev/null; then
    osascript -e 'display dialog "Python을 찾을 수 없습니다. Python 3이 설치되어 있어야 합니다." buttons {"OK"} default button "OK"'
    exit 1
fi

# 스크립트 실행
cd "$RESOURCES_DIR"
export PYTHONPATH="$RESOURCES_DIR:$PYTHONPATH"

# 디버깅: 에러 발생 시 로그 파일에 기록
LOG_FILE="$APP_DIR/Contents/Resources/error.log"
echo "Python: $PYTHON" >> "$LOG_FILE" 2>&1
echo "Script: $SCRIPT" >> "$LOG_FILE" 2>&1
echo "Date: $(date)" >> "$LOG_FILE" 2>&1

# 스크립트 실행 (에러도 로그에 기록)
exec "$PYTHON" "$SCRIPT" "$@" >> "$LOG_FILE" 2>&1
EOF

chmod +x "$MACOS_DIR/${APP_NAME}"

chmod +x "$MACOS_DIR/${APP_NAME}"

# Info.plist 생성
cat > "$CONTENTS_DIR/Info.plist" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key>
    <string>${APP_NAME}</string>
    <key>CFBundleIdentifier</key>
    <string>com.naverneighborpro.app</string>
    <key>CFBundleName</key>
    <string>${APP_NAME}</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0.0</string>
    <key>CFBundleVersion</key>
    <string>1.0.0</string>
    <key>LSMinimumSystemVersion</key>
    <string>10.13</string>
    <key>NSHighResolutionCapable</key>
    <true/>
    <key>NSPrincipalClass</key>
    <string>NSApplication</string>
</dict>
</plist>
EOF

echo "✅ 앱 번들 생성 완료: $APP_DIR"
echo "💡 실행 방법: open $APP_DIR"

