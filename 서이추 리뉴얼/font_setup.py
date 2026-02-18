import os
import platform
from pathlib import Path


def _resource_base_dir() -> Path:
    # PyInstaller one-dir/one-file 모두에서 동작
    meipass = getattr(__import__("sys"), "_MEIPASS", None)
    if meipass:
        return Path(meipass)
    return Path(__file__).resolve().parent


def register_private_fonts() -> int:
    """Windows에서 fonts 폴더의 TTF/OTF를 앱 전용으로 등록."""
    if platform.system() != "Windows":
        return 0

    fonts_dir = _resource_base_dir() / "fonts"
    if not fonts_dir.exists():
        return 0

    try:
        import ctypes
        from ctypes import wintypes
    except Exception:
        return 0

    FR_PRIVATE = 0x10
    add_font = ctypes.windll.gdi32.AddFontResourceExW
    add_font.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.LPVOID]
    add_font.restype = wintypes.INT

    loaded = 0
    for ext in ("*.ttf", "*.otf"):
        for font_path in fonts_dir.glob(ext):
            try:
                res = add_font(str(font_path), FR_PRIVATE, 0)
                if res > 0:
                    loaded += 1
            except Exception:
                continue
    return loaded
