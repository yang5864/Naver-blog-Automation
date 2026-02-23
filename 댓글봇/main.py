import sys
import os


def _base_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def _write_fatal_log(text):
    payload = str(text or "").strip() + "\n"
    paths = [
        os.path.join(_base_dir(), "error.log"),
        os.path.join(_base_dir(), "fatal_startup.log"),
    ]
    for path in paths:
        try:
            with open(path, "a", encoding="utf-8") as f:
                f.write(payload)
            return
        except Exception:
            continue


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
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(None, str(text), "실행 오류", 0x10)
        except Exception:
            pass


# ── import 단계 에러까지 잡기 위해 최상단에서 try/except ──────────────────
try:
    import traceback
    import warnings
    import logging
    import faulthandler

    # frozen(PyInstaller exe) 환경에서는 sys.path 조작 불필요
    if not getattr(sys, "frozen", False):
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

    import customtkinter as ctk
    from config import AppConfig
    from font_setup import register_private_fonts
    from gui import App

    warnings.filterwarnings("ignore", message=".*Tcl.*")
    warnings.filterwarnings("ignore", message=".*Tk.*")

    logging.basicConfig(
        filename=os.path.join(_base_dir(), "error.log"),
        level=logging.ERROR,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    try:
        _fh = open(os.path.join(_base_dir(), "fatal_startup.log"), "a", encoding="utf-8")
        faulthandler.enable(_fh)
    except Exception:
        pass

    ctk.set_appearance_mode("Light")
    ctk.set_default_color_theme("blue")

except Exception:
    import traceback
    err = traceback.format_exc()
    _write_fatal_log(err)
    _show_error(err)
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
        _write_fatal_log(err)
        _show_error(err)
        sys.exit(1)
