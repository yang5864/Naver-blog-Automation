# 문제 해결 가이드

## 현재 문제: "macOS 26 (2601) or later required, have instead 16 (1601) !"

이 에러는 PyInstaller bootloader의 macOS 버전 호환성 문제입니다.

### 해결 방법

1. **앱이 실제로 작동하는지 확인**
   - 에러 메시지가 나와도 GUI가 뜰 수 있습니다
   - Finder에서 `dist/NaverNeighborPro.app`을 더블클릭해보세요

2. **venv 재생성** (이미 완료)
   ```bash
   ./fix_venv.sh
   ```

3. **직접 Python 스크립트 실행**
   ```bash
   source venv/bin/activate
   python3 NaverNeighborPro_GUI.py
   ```

4. **시스템 Python 사용**
   - 시스템 Python에 필요한 패키지 설치:
   ```bash
   /usr/bin/python3 -m pip install --user customtkinter selenium pyperclip
   ```

### 대안: 다른 패키징 도구 사용

- **py2app**: macOS 전용 패키징 도구
- **cx_Freeze**: 크로스 플랫폼 패키징
- **Nuitka**: Python을 C++로 컴파일

### 임시 해결책

에러 메시지를 무시하고 앱을 사용할 수 있습니다. launcher 스크립트에서 에러를 리다이렉트:

```bash
exec "$PYTHON" "$SCRIPT" "$@" 2>/dev/null
```

하지만 이렇게 하면 실제 에러를 볼 수 없으므로 권장하지 않습니다.


