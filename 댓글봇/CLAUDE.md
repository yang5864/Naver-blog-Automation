# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

네이버 블로그 서로이웃(서이추) 자동화 프로그램.
Selenium + CustomTkinter 기반, macOS 우선 지원 (Windows/Linux 경로도 포함).

## File Structure

```
서이추 리뉴얼/
  main.py          # 진입점 (~30줄): 로깅, ctk 테마, AppConfig → App 실행
  config.py        # AppConfig: JSON 로드/저장, 기본값, 플랫폼별 Chrome 경로 (~60줄)
  constants.py     # IOS_COLORS, IOS_FONT_* UI 상수 (~20줄)
  bot_logic.py     # NaverBotLogic: Selenium 자동화 로직 (~500줄)
  gui.py           # App(ctk.CTk): iOS 스타일 GUI (~400줄)
  config.json      # 첫 작업 시작 시 자동 생성 (설정 영속화)
```

## Running

```bash
python main.py
```

### Dependencies

- `customtkinter`, `selenium`, `pyperclip`
- Chrome 브라우저 필수 (디버깅 포트 9222 사용, `config.json`에서 변경 가능)

## Architecture

- **`AppConfig`** (`config.py`): JSON 기반 설정 관리. `my_blog_id`, `my_nickname`, 메시지, 타이밍 상수 등
- **`NaverBotLogic`** (`bot_logic.py`): Selenium 자동화 로직
  - `AppConfig` 객체로부터 설정 읽기 (하드코딩 제거)
  - Chrome 디버깅 모드 연결 (`127.0.0.1:9222`)
  - 로그인 → 키워드 검색 → 블로그 ID 수집 → 서이추 신청 + 공감 + 댓글
  - `_close_tab_and_return()`: 탭 닫기+복귀 헬퍼 (중복 제거)
  - `_navigate_to_blog_search()` + `_click_blog_tab()`: 검색 로직 헬퍼 (중복 제거)
  - bare `except:` → 구체적 Selenium 예외 타입으로 변경
- **`App(ctk.CTk)`** (`gui.py`): iOS 스타일 GUI
  - 왼쪽 패널(420px 고정): 로그인, 검색, 설정(블로그ID/닉네임 입력), 메시지, 액션 버튼, 진행률, 로그
  - 오른쪽 패널: Chrome 창 자동 배치 영역
  - 스레드 안전: `log_msg()`, `update_prog()`, `update_browser_status()`가 `self.after()`로 UI 업데이트
  - 작업 시작 시 GUI 값 → config → JSON 자동 저장; 시작 시 config에서 복원
- Chrome 사용자 데이터 디렉토리: `~/ChromeBotData`
