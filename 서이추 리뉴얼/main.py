import sys
import os


def _show_error(text):
    """콘솔이 없는 exe 환경에서도 에러를 팝업으로 표시."""
    try:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("실행 오류", text)
        root.destroy()
    except Exception:
        pass


# ── import 단계 에러까지 잡기 위해 최상단에서 try/except ──────────────────
try:
    import traceback
    import warnings
    import logging

    # frozen(PyInstaller exe) 환경에서는 sys.path 조작 불필요
    if not getattr(sys, "frozen", False):
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

    import customtkinter as ctk
    from config import AppConfig
    from font_setup import register_private_fonts
    from gui import App

    warnings.filterwarnings("ignore", message=".*Tcl.*")
    warnings.filterwarnings("ignore", message=".*Tk.*")

    # exe 실행 시 error.log를 exe 옆에 생성
    if getattr(sys, "frozen", False):
        _base_dir = os.path.dirname(sys.executable)
    else:
        _base_dir = os.path.dirname(os.path.abspath(__file__))

    logging.basicConfig(
        filename=os.path.join(_base_dir, "error.log"),
        level=logging.ERROR,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    ctk.set_appearance_mode("Light")
    ctk.set_default_color_theme("blue")

except Exception:
    import traceback
    _show_error(traceback.format_exc())
    sys.exit(1)


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
    except Exception:
        err = traceback.format_exc()
        logging.exception("치명적 오류")
        _show_error(err)
        sys.exit(1)
