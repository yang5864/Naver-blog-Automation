#!/bin/bash

# 네이버 서이추 Pro 빌드 스크립트

echo "🚀 네이버 서이추 Pro 빌드 시작..."

# 가상환경 확인 및 생성
if [ ! -d "venv" ]; then
    echo "📦 가상환경 생성 중..."
    python3 -m venv venv
fi

# 가상환경 활성화
echo "🔌 가상환경 활성화 중..."
source venv/bin/activate

# 의존성 설치
echo "📥 의존성 패키지 설치 중..."
pip install --upgrade pip
pip install -r requirements.txt
pip install pyinstaller

# 기존 빌드 파일 정리
echo "🧹 기존 빌드 파일 정리 중..."
rm -rf build dist __pycache__
# build_app.spec은 유지 (PyInstaller가 생성하는 다른 .spec 파일만 삭제)
find . -maxdepth 1 -name "*.spec" ! -name "build_app.spec" -delete

# PyInstaller로 빌드
echo "🔨 앱 빌드 중..."
pyinstaller build_app.spec

# 빌드 완료 확인
if [ -d "dist/NaverNeighborPro.app" ]; then
    echo ""
    echo "✅ 빌드 완료!"
    echo "📦 앱 위치: dist/NaverNeighborPro.app"
    echo ""
    echo "💡 실행 방법:"
    echo "   open dist/NaverNeighborPro.app"
    echo ""
    echo "📝 배포 전 확인사항:"
    echo "   1. Chrome 브라우저가 설치되어 있어야 합니다"
    echo "   2. ChromeDriver가 필요할 수 있습니다 (Selenium이 자동으로 관리)"
    echo "   3. macOS 보안 설정에서 앱 실행을 허용해야 할 수 있습니다"
else
    echo "❌ 빌드 실패! 오류를 확인하세요."
    exit 1
fi

