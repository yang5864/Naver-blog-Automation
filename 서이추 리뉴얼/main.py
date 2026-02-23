import sys
import os
import warnings
import logging

# 스크립트 디렉토리를 sys.path 맨 앞에 추가 (Windows 더블클릭 실행 등 대비)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import customtkinter as ctk

from config import AppConfig
from font_setup import register_private_fonts
from gui import App

# macOS Tcl/Tk 호환성 경고만 선택 억제
warnings.filterwarnings("ignore", message=".*Tcl.*")
warnings.filterwarnings("ignore", message=".*Tk.*")

# 에러 로깅 (stderr 리다이렉트 대신 파일 로깅)
logging.basicConfig(
    filename="error.log",
    level=logging.ERROR,
    format="%(asctime)s %(levelname)s %(message)s",
)

ctk.set_appearance_mode("Light")
ctk.set_default_color_theme("blue")


def main():
    loaded = register_private_fonts()
    if loaded:
        logging.info("Loaded private fonts: %s", loaded)
    config = AppConfig()
    app = App(config)
    app.mainloop()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logging.exception("치명적 오류")
        print(f"에러 발생: {e}", file=sys.stderr)
        raise
