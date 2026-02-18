import sys
import warnings
import logging

import customtkinter as ctk

from config import AppConfig
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
