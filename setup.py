"""
NaverNeighborPro py2app setup script
py2app은 macOS 전용으로 PyInstaller보다 더 나은 호환성을 제공합니다.
"""

from setuptools import setup
import py2app
import os
import customtkinter

# customtkinter assets 경로
ct_path = os.path.dirname(customtkinter.__file__)
assets_path = os.path.join(ct_path, 'assets')

APP = ['NaverNeighborPro_GUI.py']
DATA_FILES = [
    (assets_path, 'customtkinter/assets'),
]

OPTIONS = {
    'argv_emulation': False,
    'packages': [
        'customtkinter',
        'selenium',
        'selenium.webdriver',
        'selenium.webdriver.chrome',
        'selenium.webdriver.chrome.service',
        'selenium.webdriver.common',
        'selenium.webdriver.support',
        'pyperclip',
    ],
    'includes': [
        'AppKit',
        'tkinter',
        'tkinter.messagebox',
    ],
    'iconfile': None,
    'plist': {
        'NSPrincipalClass': 'NSApplication',
        'NSHighResolutionCapable': 'True',
        'CFBundleShortVersionString': '1.0.0',
        'CFBundleVersion': '1.0.0',
        'LSMinimumSystemVersion': '10.13',
    },
}

setup(
    app=APP,
    data_files=DATA_FILES,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)


