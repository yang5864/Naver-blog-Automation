import json
import os
import platform


class AppConfig:
    """JSON 기반 설정 관리. 첫 저장 시 config.json 자동 생성."""

    DEFAULTS = {
        "my_blog_id": "",
        "my_nickname": "",
        "neighbor_msg": "블로그 스타일이 너무 좋아요! 저도 다양한 주제로 글 쓰고 있어서 함께 소통하면 좋을 것 같아 이웃 신청드립니다:)",
        "comment_msg": "핵심 내용에 공감하는 짧은 댓글로 작성",
        "keyword": "",
        "feed_url": "https://m.blog.naver.com/",
        "target_count": 100,
        "persona_profile": "30대 직장인, 공감 위주로 짧고 자연스럽게 댓글 작성",
        "gemini_api_key": "",
        "gemini_model": "gemini-2.0-flash",
        "comment_max_chars": 90,
        "chrome_debug_port": 9222,
        "page_load_timeout": 15,
        "element_wait_timeout": 5,
        "fast_wait": 0.2,
        "normal_wait": 0.5,
        "slow_wait": 1.0,
        "embed_browser_windows": True,
        "use_webview2_panel": True,
    }

    def __init__(self):
        self._path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
        self._data: dict = dict(self.DEFAULTS)
        self.load()

    def load(self):
        if os.path.exists(self._path):
            # Windows에서 생성된 파일(UTF-16/CP949 등)도 읽을 수 있게 인코딩 순차 시도
            for enc in ("utf-8", "utf-8-sig", "utf-16", "cp949"):
                try:
                    with open(self._path, "r", encoding=enc) as f:
                        stored = json.load(f)
                    self._data.update(stored)
                    break
                except (UnicodeDecodeError, json.JSONDecodeError, OSError):
                    continue

    def save(self):
        try:
            with open(self._path, "w", encoding="utf-8") as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
        except OSError:
            pass

    def get(self, key: str):
        return self._data.get(key, self.DEFAULTS.get(key))

    def set(self, key: str, value):
        self._data[key] = value

    @staticmethod
    def get_chrome_path() -> str:
        system = platform.system()
        if system == "Darwin":
            return "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
        elif system == "Windows":
            return r"C:\Program Files\Google\Chrome\Application\chrome.exe"
        else:
            return "/usr/bin/google-chrome"
