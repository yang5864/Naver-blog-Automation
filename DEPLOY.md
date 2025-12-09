# 배포 가이드

## 📦 배포 준비

### 1. 빌드 전 확인사항

- [ ] 프로그램이 정상적으로 실행되는지 확인
- [ ] 모든 기능이 작동하는지 테스트
- [ ] Chrome 브라우저 연결이 정상인지 확인
- [ ] 로그인 기능이 정상인지 확인

### 2. 빌드 실행

```bash
# 빌드 스크립트 실행
./build.sh
```

빌드가 완료되면 `dist/NaverNeighborPro.app` 파일이 생성됩니다.

### 3. 빌드된 앱 테스트

```bash
# 앱 실행 테스트
open dist/NaverNeighborPro.app
```

모든 기능이 정상 작동하는지 확인하세요.

## 🎯 배포 방법

### 방법 1: 직접 배포

1. `dist/NaverNeighborPro.app` 파일을 ZIP으로 압축
2. 배포 플랫폼에 업로드 (GitHub Releases, Google Drive 등)
3. 사용자에게 다운로드 링크 제공

### 방법 2: GitHub Releases

```bash
# Git 태그 생성
git tag -a v1.0.0 -m "Release version 1.0.0"
git push origin v1.0.0

# GitHub Releases에서:
# 1. 새 릴리스 생성
# 2. 태그 선택 (v1.0.0)
# 3. NaverNeighborPro.app.zip 업로드
# 4. 릴리스 노트 작성
```

### 방법 3: 코드 서명 (선택사항)

macOS 앱을 배포할 때 코드 서명을 하면 보안 경고를 줄일 수 있습니다.

```bash
# 개발자 인증서가 있는 경우
codesign --deep --force --verify --verbose --sign "Developer ID Application: Your Name" dist/NaverNeighborPro.app

# 공증 (선택사항)
xcrun notarytool submit dist/NaverNeighborPro.app --keychain-profile "AC_PASSWORD" --wait
```

## 📝 배포 체크리스트

- [ ] 빌드 완료 확인
- [ ] 앱 실행 테스트
- [ ] README.md 업데이트
- [ ] 버전 번호 확인
- [ ] 릴리스 노트 작성
- [ ] 사용자 가이드 확인

## 🔒 보안 고려사항

1. **코드 서명**: macOS Gatekeeper 경고를 줄이기 위해 코드 서명을 권장합니다.
2. **공증**: Apple의 공증을 받으면 더 안전하게 배포할 수 있습니다.
3. **사용자 안내**: 사용자에게 보안 설정 변경 방법을 안내하세요.

## 📊 배포 후 모니터링

- 사용자 피드백 수집
- 버그 리포트 확인
- 업데이트 계획 수립


