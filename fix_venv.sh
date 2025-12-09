#!/bin/bash
# venv 재생성 및 필요한 패키지만 설치 (PyInstaller 제외)

echo "🔧 venv 재생성 중..."

# 기존 venv 백업
if [ -d "venv" ]; then
    mv venv venv_backup_$(date +%Y%m%d_%H%M%S)
fi

# 새 venv 생성
python3 -m venv venv
source venv/bin/activate

# pip 업그레이드
pip install --upgrade pip

# PyInstaller 제외하고 필요한 패키지만 설치
echo "📦 필요한 패키지 설치 중..."
pip install customtkinter selenium pyperclip

# PyInstaller는 설치하지 않음
echo "✅ venv 재생성 완료 (PyInstaller 제외)"


