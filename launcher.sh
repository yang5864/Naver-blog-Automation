#!/bin/bash
# NaverNeighborPro Launcher
# PyInstaller bootloader 문제를 우회하기 위한 launcher

# 스크립트가 있는 디렉토리 찾기
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
APP_DIR="$SCRIPT_DIR/NaverNeighborPro.app/Contents"

# Python 경로 찾기
if [ -f "$APP_DIR/MacOS/NaverNeighborPro" ]; then
    # 앱 내부의 Python 사용
    cd "$APP_DIR/MacOS"
    export PYTHONPATH="$APP_DIR/MacOS:$PYTHONPATH"
    python3 -c "
import sys
sys.path.insert(0, '$APP_DIR/MacOS')
import runpy
runpy.run_path('$APP_DIR/MacOS/NaverNeighborPro.py', run_name='__main__')
" "$@"
else
    echo "Error: NaverNeighborPro.app not found"
    exit 1
fi


