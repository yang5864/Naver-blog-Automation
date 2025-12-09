# 빠른 시작 가이드

## 🚀 5분 안에 시작하기

### 1단계: 빌드

```bash
./build.sh
```

### 2단계: 앱 실행

```bash
open dist/NaverNeighborPro.app
```

### 3단계: 사용

1. 로그인 버튼 클릭
2. 네이버 아이디/비밀번호 입력
3. 검색 키워드 입력
4. 서이추 메시지 입력
5. 작업 시작 버튼 클릭

끝! 🎉

## ⚡ 빠른 빌드 (개발자용)

```bash
# 가상환경 없이 직접 빌드
pip install pyinstaller
pyinstaller build_app.spec
```

## 🐛 문제 발생 시

1. **빌드 실패**: `pip install --upgrade pyinstaller` 실행
2. **앱 실행 안 됨**: `xattr -cr dist/NaverNeighborPro.app` 실행
3. **Chrome 연결 실패**: Chrome 브라우저 재시작

더 자세한 내용은 [README.md](README.md)를 참고하세요.


