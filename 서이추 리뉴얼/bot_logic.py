import time
import random
import re
import os
import subprocess
import platform
import socket
import sys
import json
import urllib.request


from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    WebDriverException,
    NoSuchElementException,
    StaleElementReferenceException,
)
from selenium.webdriver.common.action_chains import ActionChains

from config import AppConfig


class NaverBotLogic:
    def __init__(self, config: AppConfig, log_func, progress_func, status_func, gui_window=None):
        self.config = config
        self.driver = None
        self.is_running = False
        self.log = log_func
        self.update_progress = progress_func
        self.update_status = status_func
        self.gui_window = gui_window
        self.target_count = config.get("target_count")
        self.current_count = 0
        self.neighbor_msg = config.get("neighbor_msg")
        self.comment_msg = config.get("comment_msg")
        self.embed_browser_windows = bool(config.get("embed_browser_windows"))
        self._is_windows = platform.system() == "Windows"
        self._embedded_chrome_hwnd = None
        self._embed_parent_hwnd = None
        self._chrome_process_id = None
        self._chrome_user_data_dir = None
        self._embed_attempt_count = 0
        self.webview2_host = None
        self.webview2_mode = False
        self._last_attach_errors = []

        # 성능 설정
        self.page_load_timeout = config.get("page_load_timeout")
        self.element_wait_timeout = config.get("element_wait_timeout")
        self.fast_wait = config.get("fast_wait")
        self.normal_wait = config.get("normal_wait")
        self.slow_wait = config.get("slow_wait")

    # ------------------------------------------------------------------
    # 헬퍼
    # ------------------------------------------------------------------
    def safe_sleep(self, seconds):
        if seconds > 0:
            time.sleep(seconds)

    def set_webview2_host(self, host):
        prev_mode = self.webview2_mode
        self.webview2_host = host
        self.webview2_mode = bool(host)
        if prev_mode != self.webview2_mode:
            self.driver = None

    def _close_tab_and_return(self, main_window):
        """현재 탭 닫고 메인 윈도우로 복귀."""
        try:
            if len(self.driver.window_handles) > 1:
                self.driver.close()
            self.driver.switch_to.window(main_window)
        except WebDriverException:
            pass

    def _navigate_to_blog_search(self, keyword):
        """네이버 블로그 검색 페이지로 이동."""
        search_url = f"https://search.naver.com/search.naver?where=blog&query={keyword}"
        if not self.safe_get(self.driver, search_url):
            return False
        self.safe_sleep(1.0)
        return True

    def _click_blog_tab(self):
        """검색 결과에서 '블로그' 탭 클릭."""
        try:
            blog_tab = None
            tabs = self.driver.find_elements(By.CSS_SELECTOR, "[role='tab'], .tab, .lnb_item a")
            for tab in tabs:
                try:
                    if "블로그" in tab.text:
                        blog_tab = tab
                        break
                except (StaleElementReferenceException, NoSuchElementException):
                    continue

            if not blog_tab:
                blog_tab = self.driver.find_element(By.XPATH, "//a[contains(text(), '블로그')]")

            if blog_tab:
                self.log("   ↪ '블로그' 탭 클릭...")
                self.safe_click(self.driver, blog_tab)
                self.safe_sleep(1.0)
        except (NoSuchElementException, StaleElementReferenceException):
            pass

    # ------------------------------------------------------------------
    # Selenium 유틸
    # ------------------------------------------------------------------
    def safe_get(self, driver, url, max_retries=2):
        for attempt in range(max_retries):
            try:
                driver.get(url)
                return True
            except TimeoutException:
                if attempt < max_retries - 1:
                    driver.execute_script("window.stop();")
                else:
                    return False
            except WebDriverException:
                if attempt < max_retries - 1:
                    self.safe_sleep(0.5)
                else:
                    return False
        return False

    def safe_find_element(self, driver, by, value, timeout=None):
        if timeout is None:
            timeout = self.element_wait_timeout
        try:
            return WebDriverWait(driver, timeout).until(
                EC.presence_of_element_located((by, value))
            )
        except (TimeoutException, NoSuchElementException):
            return None

    def safe_click(self, driver, element):
        try:
            driver.execute_script("arguments[0].click();", element)
            return True
        except WebDriverException:
            try:
                element.click()
                return True
            except WebDriverException:
                return False

    # ------------------------------------------------------------------
    # 크롬 연결
    # ------------------------------------------------------------------
    def _is_debug_port_open(self, port):
        try:
            with socket.create_connection(("127.0.0.1", int(port)), timeout=0.2):
                return True
        except OSError:
            return False

    def _get_debug_port(self):
        return int(self.config.get("chrome_debug_port") or 9222)

    def _fetch_devtools_version(self, debug_port):
        try:
            with urllib.request.urlopen(
                f"http://127.0.0.1:{int(debug_port)}/json/version",
                timeout=1.0,
            ) as resp:
                raw = resp.read().decode("utf-8", errors="ignore")
            data = json.loads(raw)
            if isinstance(data, dict):
                return data
            return None
        except Exception:
            return None

    def _wait_devtools_ready(self, debug_port, timeout_sec=12.0):
        deadline = time.time() + float(timeout_sec)
        info = None
        while time.time() < deadline:
            if not self._is_debug_port_open(debug_port):
                time.sleep(0.1)
                continue
            info = self._fetch_devtools_version(debug_port)
            if info and info.get("webSocketDebuggerUrl"):
                return info
            time.sleep(0.15)
        return info

    def _candidate_driver_paths(self, filename):
        roots = []
        if hasattr(sys, "_MEIPASS"):
            roots.append(getattr(sys, "_MEIPASS"))
        if getattr(sys, "frozen", False):
            try:
                roots.append(os.path.dirname(sys.executable))
            except Exception:
                pass
        roots.append(os.path.dirname(os.path.abspath(__file__)))
        roots.append(os.getcwd())
        for root in roots:
            try:
                path = os.path.join(root, filename)
                if os.path.isfile(path):
                    yield path
            except Exception:
                continue

    def _extract_edge_major(self, browser_name):
        try:
            text = str(browser_name or "")
            match = re.search(r"Edg/(\d+)\.", text)
            if match:
                return int(match.group(1))
        except Exception:
            pass
        return None

    def _detect_driver_major(self, driver_path):
        try:
            proc = subprocess.run(
                [driver_path, "--version"],
                capture_output=True,
                text=True,
                timeout=2.0,
                check=False,
            )
            output = f"{proc.stdout}\n{proc.stderr}"
            match = re.search(r"(\d+)\.", output)
            if match:
                return int(match.group(1))
        except Exception:
            pass
        return None

    def _attach_debugger_driver(self, debug_port, browser_name=None):
        debugger_address = f"127.0.0.1:{int(debug_port)}"
        errors = []
        edge_major = self._extract_edge_major(browser_name)

        def _edge_options():
            from selenium.webdriver.edge.options import Options as EdgeOptions

            opts = EdgeOptions()
            opts.use_chromium = True
            opts.add_experimental_option("debuggerAddress", debugger_address)
            return opts

        try:
            driver = webdriver.Edge(options=_edge_options())
            self.log("   ↪ msedgedriver attach 성공")
            return driver
        except Exception as exc:
            errors.append(f"Edge(default): {str(exc)[:260]}")

        try:
            from selenium.webdriver.edge.service import Service as EdgeService

            for path in self._candidate_driver_paths("msedgedriver.exe"):
                try:
                    driver_major = self._detect_driver_major(path)
                    if edge_major and driver_major and driver_major != edge_major:
                        errors.append(
                            f"Edge(local:{os.path.basename(path)}): version mismatch driver={driver_major}, edge={edge_major}"
                        )
                        continue
                    driver = webdriver.Edge(service=EdgeService(executable_path=path), options=_edge_options())
                    self.log(f"   ↪ msedgedriver(local) attach 성공: {path}")
                    return driver
                except Exception as exc:
                    errors.append(f"Edge(local:{os.path.basename(path)}): {str(exc)[:260]}")
        except Exception as exc:
            errors.append(f"Edge(service-import): {str(exc)[:260]}")

        try:
            from selenium.webdriver.edge.service import Service as EdgeService
            from webdriver_manager.microsoft import EdgeChromiumDriverManager

            driver_path = None
            if edge_major:
                version_hint = f"{edge_major}.0.0.0"
                try:
                    driver_path = EdgeChromiumDriverManager(driver_version=version_hint).install()
                except TypeError:
                    driver_path = EdgeChromiumDriverManager(version=version_hint).install()
                except Exception:
                    driver_path = None
            if not driver_path:
                driver_path = EdgeChromiumDriverManager().install()
            driver = webdriver.Edge(service=EdgeService(executable_path=driver_path), options=_edge_options())
            self.log("   ↪ msedgedriver(manager) attach 성공")
            return driver
        except Exception as exc:
            errors.append(f"Edge(manager): {str(exc)[:260]}")

        self._last_attach_errors = errors
        return None

    def _connect_driver_webview2(self, force_restart=False):
        if self.driver and not force_restart:
            try:
                _ = self.driver.current_url
                return True
            except WebDriverException:
                self.driver = None

        if not self.webview2_host:
            self.log("❌ WebView2 자동화 대상이 없습니다.")
            return False
        if not self.webview2_host.is_ready:
            self.log("❌ WebView2가 아직 준비되지 않았습니다.")
            return False

        debug_port = int(getattr(self.webview2_host, "devtools_port", 0) or 0)
        if debug_port <= 0:
            self.log("❌ WebView2 DevTools 포트를 찾을 수 없습니다.")
            return False

        info = self._wait_devtools_ready(debug_port, timeout_sec=15.0)
        if not info:
            self.log(f"❌ WebView2 DevTools 준비 실패: {debug_port}")
            return False

        browser_name = info.get("Browser", "unknown")
        self.log(f"   ↪ DevTools browser: {browser_name}")

        self.log(f"🌐 WebView2 자동화 연결 시도: {debug_port}")
        self.driver = self._attach_debugger_driver(debug_port, browser_name=browser_name)
        if not self.driver:
            self.log("❌ WebView2 자동화 연결 실패 (드라이버 attach 실패)")
            for err in self._last_attach_errors[:6]:
                self.log(f"   ↪ {err}")
            edge_major = self._extract_edge_major(browser_name)
            if edge_major:
                self.log(
                    f"   ↪ 해결: msedgedriver {edge_major}.x 버전을 exe 폴더에 두고 다시 실행"
                )
            return False

        try:
            self.driver.set_page_load_timeout(self.page_load_timeout)
        except Exception:
            pass

        self.update_status("브라우저 연결됨", "green")
        return True

    def _get_chrome_user_data_dir(self):
        if self._chrome_user_data_dir:
            return self._chrome_user_data_dir
        self._chrome_user_data_dir = os.path.expanduser("~/ChromeBotData")
        os.makedirs(self._chrome_user_data_dir, exist_ok=True)
        return self._chrome_user_data_dir

    def _is_chrome_widget_window_class(self, class_name):
        return str(class_name).startswith("Chrome_WidgetWin_")

    def _launch_chrome_process(self, debug_port, initial_url=None):
        user_data_dir = self._get_chrome_user_data_dir()
        chrome_path = AppConfig.get_chrome_path()

        self._embedded_chrome_hwnd = None
        self._embed_parent_hwnd = None
        self._embed_attempt_count = 0

        if self.gui_window:
            chrome_x, chrome_y, chrome_width, chrome_height = self._get_browser_bounds(self.gui_window)
        else:
            chrome_x, chrome_y = 800, 0
            chrome_width, chrome_height = 1000, 900

        cmd = [
            chrome_path,
            f"--remote-debugging-port={debug_port}",
            f"--user-data-dir={user_data_dir}",
            "--no-first-run",
            "--no-default-browser-check",
            f"--window-size={chrome_width},{chrome_height}",
            f"--window-position={chrome_x},{chrome_y}",
        ]
        if initial_url:
            cmd.append(initial_url)

        proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self._chrome_process_id = proc.pid
        return True

    def connect_driver(self, force_restart=False, initial_url=None):
        """크롬 연결 (GUI 오른쪽 패널 위치에 배치)"""
        if self.webview2_mode:
            return self._connect_driver_webview2(force_restart=force_restart)

        debug_port = self._get_debug_port()

        if self.driver and not force_restart:
            try:
                _ = self.driver.window_handles
                if self.gui_window:
                    self._position_chrome_window(self.gui_window)
                return True
            except WebDriverException:
                self.log("⚠️ 기존 연결이 끊어졌습니다. 재연결합니다...")
                self.driver = None

        self.log("🖥️ 크롬 브라우저 실행 중...")
        try:
            # 포트가 닫혀있으면 크롬 프로세스 실행
            if not self._is_debug_port_open(debug_port):
                self._launch_chrome_process(debug_port, initial_url=initial_url)

            # 디버그 포트가 실제로 열릴 때까지 대기 (최대 15초)
            for _ in range(30):
                if self._is_debug_port_open(debug_port):
                    break
                time.sleep(0.5)

            # 디버그 포트 준비 후 attach
            self.driver = None
            for _ in range(20):
                try:
                    chrome_options = Options()
                    chrome_options.add_experimental_option("debuggerAddress", f"127.0.0.1:{debug_port}")
                    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
                    chrome_options.add_experimental_option("useAutomationExtension", False)
                    chrome_options.page_load_strategy = "eager"
                    self.driver = webdriver.Chrome(options=chrome_options)
                    break
                except WebDriverException:
                    time.sleep(0.5)

            if not self.driver:
                raise RuntimeError("크롬 디버그 포트 연결 실패")

            self.driver.set_page_load_timeout(self.page_load_timeout)

            if self.gui_window:
                self._position_chrome_window(self.gui_window)

            self.log("✅ 브라우저 연결 성공!")
            self.update_status("브라우저 연결됨", "green")
            return True
        except Exception as e:
            self.log(f"❌ 실행 실패: {e}")
            self.driver = None
            self.update_status("브라우저 연결 실패", "red")
            return False

    def _position_chrome_window(self, gui_window=None):
        """크롬 창을 GUI 영역에 맞게 배치 (Windows는 임베드 모드 지원)."""
        if not self.driver:
            return
        if not gui_window:
            gui_window = self.gui_window
        if not gui_window:
            return
        try:
            chrome_x, chrome_y, chrome_width, chrome_height = self._get_browser_bounds(gui_window)
            if self._is_windows and self.embed_browser_windows:
                if self._ensure_chrome_embedded(gui_window, chrome_x, chrome_y, chrome_width, chrome_height):
                    return
                if self._embed_attempt_count <= 3:
                    self.log("⚠️ 임베드 미적용 상태: 외부 창 모드로 동작")
            self.driver.set_window_position(chrome_x, chrome_y)
            self.driver.set_window_size(chrome_width, chrome_height)
        except WebDriverException as e:
            self.log(f"⚠️ 창 위치 조정 실패: {str(e)[:30]}")

    def is_chrome_embedded(self):
        return bool(self._is_windows and self.embed_browser_windows and self._embedded_chrome_hwnd)

    def _get_browser_bounds(self, gui_window):
        if hasattr(gui_window, "get_browser_embed_rect"):
            rx, ry, rw, rh = gui_window.get_browser_embed_rect()
            chrome_x = int(rx)
            chrome_y = int(ry)
            chrome_width = int(rw)
            chrome_height = int(rh)
        else:
            gui_x = gui_window.winfo_x()
            gui_y = gui_window.winfo_y()
            gui_width = gui_window.winfo_width()
            gui_height = gui_window.winfo_height()
            left_panel_width = 420
            padding_x = 15
            chrome_x = gui_x + left_panel_width + padding_x
            chrome_y = gui_y
            chrome_width = gui_width - left_panel_width - (padding_x * 2)
            chrome_height = gui_height
        return chrome_x, chrome_y, chrome_width, chrome_height

    def _ensure_chrome_embedded(self, gui_window, chrome_x, chrome_y, chrome_width, chrome_height):
        if not self._is_windows:
            return False
        try:
            import ctypes
            from ctypes import wintypes
        except Exception:
            return False

        self._embed_attempt_count += 1

        if not hasattr(gui_window, "get_browser_embed_hwnd"):
            if self._embed_attempt_count <= 3:
                self.log("⚠️ 임베드 실패: GUI에 임베드 핸들 getter 없음")
            return False

        target_hwnd = gui_window.get_browser_embed_hwnd()
        if not target_hwnd:
            if self._embed_attempt_count <= 3:
                self.log("⚠️ 임베드 실패: target HWND가 0")
            return False

        embed_client_rect = None
        if hasattr(gui_window, "get_browser_embed_client_rect"):
            embed_client_rect = gui_window.get_browser_embed_client_rect()

        user32 = ctypes.windll.user32
        GWL_STYLE = -16
        GWL_EXSTYLE = -20
        WS_CHILD = 0x40000000
        WS_POPUP = 0x80000000
        WS_CAPTION = 0x00C00000
        WS_THICKFRAME = 0x00040000
        WS_MINIMIZEBOX = 0x00020000
        WS_MAXIMIZEBOX = 0x00010000
        WS_SYSMENU = 0x00080000
        WS_VISIBLE = 0x10000000
        WS_EX_TOOLWINDOW = 0x00000080
        WS_EX_APPWINDOW = 0x00040000
        WS_EX_WINDOWEDGE = 0x00000100
        WS_EX_CLIENTEDGE = 0x00000200
        WS_EX_STATICEDGE = 0x00020000
        SWP_NOZORDER = 0x0004
        SWP_NOACTIVATE = 0x0010
        SWP_FRAMECHANGED = 0x0020
        SWP_SHOWWINDOW = 0x0040
        SW_HIDE = 0
        SW_SHOW = 5
        SW_RESTORE = 9

        if not user32.IsWindow(int(target_hwnd)):
            if self._embed_attempt_count <= 3:
                self.log(f"⚠️ 임베드 실패: target HWND invalid ({int(target_hwnd)})")
            return False

        if self._embed_attempt_count <= 3:
            self.log(
                f"   ↪ 임베드 시도 #{self._embed_attempt_count}: target={int(target_hwnd)}, "
                f"rect=({int(chrome_x)},{int(chrome_y)},{int(chrome_width)},{int(chrome_height)})"
            )

        if self._embedded_chrome_hwnd and not user32.IsWindow(self._embedded_chrome_hwnd):
            self._embedded_chrome_hwnd = None
            self._embed_parent_hwnd = None

        if not self._embedded_chrome_hwnd:
            hwnd = self._find_chrome_hwnd(user32, chrome_x, chrome_y, chrome_width, chrome_height)
            if not hwnd:
                self.log("⚠️ 임베드 실패: Chrome 윈도우를 찾을 수 없음")
                if self._embed_attempt_count <= 3:
                    self.log(f"   ↪ 후보 Chrome 창 수: {self._count_top_level_chrome_windows(user32)}")
                self._recover_chrome_window_position(chrome_x, chrome_y, chrome_width, chrome_height)
                return False
            self.log(f"   ↪ HWND 연결: chrome={int(hwnd)} -> target={int(target_hwnd)}")

            # 임베드 전 즉시 숨겨서 별도 창이 보이는 현상 방지
            user32.ShowWindow(hwnd, SW_HIDE)

            style = user32.GetWindowLongW(hwnd, GWL_STYLE)
            style = (style | WS_CHILD | WS_VISIBLE) & ~WS_POPUP
            style = style & ~WS_CAPTION & ~WS_THICKFRAME & ~WS_MINIMIZEBOX & ~WS_MAXIMIZEBOX & ~WS_SYSMENU
            user32.SetWindowLongW(hwnd, GWL_STYLE, style)
            ex_style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            ex_style = (ex_style | WS_EX_TOOLWINDOW) & ~WS_EX_APPWINDOW & ~WS_EX_WINDOWEDGE & ~WS_EX_CLIENTEDGE & ~WS_EX_STATICEDGE
            user32.SetWindowLongW(hwnd, GWL_EXSTYLE, ex_style)
            user32.SetParent(hwnd, target_hwnd)
            if user32.GetParent(hwnd) != target_hwnd:
                self.log("⚠️ 임베드 실패: SetParent 호출 실패")
                self._embedded_chrome_hwnd = None
                self._embed_parent_hwnd = None
                self._recover_chrome_window_position(chrome_x, chrome_y, chrome_width, chrome_height)
                return False
            self._embedded_chrome_hwnd = hwnd
            self._embed_parent_hwnd = target_hwnd
            self.log("🧩 Windows 내장 브라우저 모드 활성화")

        # 부모가 바뀐 경우 재설정
        if self._embed_parent_hwnd != target_hwnd:
            user32.SetParent(self._embedded_chrome_hwnd, target_hwnd)
            if user32.GetParent(self._embedded_chrome_hwnd) != target_hwnd:
                self._embedded_chrome_hwnd = None
                self._embed_parent_hwnd = None
                return False
            self._embed_parent_hwnd = target_hwnd

        if embed_client_rect:
            x, y, w, h = embed_client_rect
            pos_x = max(0, int(x))
            pos_y = max(0, int(y))
            width = max(1, int(w))
            height = max(1, int(h))
        else:
            pos_x = 0
            pos_y = 0
            width = max(1, int(chrome_width))
            height = max(1, int(chrome_height))

        # 초기 레이아웃 타이밍 이슈로 1px로 고정되는 문제 방지
        if width < 80 or height < 80:
            pos_x = 0
            pos_y = 0
            width = max(300, int(chrome_width))
            height = max(300, int(chrome_height))

        user32.SetWindowPos(
            self._embedded_chrome_hwnd,
            0,
            pos_x,
            pos_y,
            width,
            height,
            SWP_NOACTIVATE | SWP_FRAMECHANGED | SWP_SHOWWINDOW,
        )
        user32.ShowWindow(self._embedded_chrome_hwnd, SW_RESTORE)
        user32.ShowWindow(self._embedded_chrome_hwnd, SW_SHOW)
        return True

    def _count_top_level_chrome_windows(self, user32):
        try:
            import ctypes
            from ctypes import wintypes
        except Exception:
            return 0

        count = {"n": 0}
        EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

        def _callback(hwnd, _lparam):
            class_name = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(hwnd, class_name, 256)
            if not self._is_chrome_widget_window_class(class_name.value):
                return True
            if user32.GetParent(hwnd) != 0:
                return True
            count["n"] += 1
            return True

        user32.EnumWindows(EnumWindowsProc(_callback), 0)
        return int(count["n"])

    def _find_chrome_hwnd(self, user32, expected_x, expected_y, expected_width, expected_height):
        try:
            import ctypes
            from ctypes import wintypes
        except Exception:
            return None

        rect = (expected_x, expected_y, expected_x + expected_width, expected_y + expected_height)
        found = {"hwnd": None, "score": 10**9}
        GW_OWNER = 4

        EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

        def _callback(hwnd, _lparam):
            class_name = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(hwnd, class_name, 256)
            if not self._is_chrome_widget_window_class(class_name.value):
                return True

            # 이미 다른 창에 임베드된 Chrome 창은 제외
            if user32.GetParent(hwnd) != 0:
                return True

            rc = wintypes.RECT()
            if not user32.GetWindowRect(hwnd, ctypes.byref(rc)):
                return True

            # 예상 위치와 가까운 창 우선 선택
            score = abs(rc.left - rect[0]) + abs(rc.top - rect[1])
            if not user32.IsWindowVisible(hwnd):
                score += 2000
            if user32.GetWindow(hwnd, GW_OWNER) != 0:
                score += 1500
            if score < found["score"]:
                found["score"] = score
                found["hwnd"] = hwnd
            return True

        # 연결 직후 창 생성/전환 지연을 고려한 재시도
        for _ in range(15):
            user32.EnumWindows(EnumWindowsProc(_callback), 0)
            if found["hwnd"]:
                return found["hwnd"]
            time.sleep(0.3)
        return None

    def _recover_chrome_window_position(self, chrome_x, chrome_y, chrome_width, chrome_height):
        """임베드 실패 시 숨겨진 Chrome 창을 원래 위치로 복구."""
        # ShowWindow로 숨긴 창 복구
        try:
            import ctypes
            from ctypes import wintypes
            user32 = ctypes.windll.user32

            EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
            def _show_callback(hwnd, _lparam):
                class_name = ctypes.create_unicode_buffer(256)
                user32.GetClassNameW(hwnd, class_name, 256)
                if not self._is_chrome_widget_window_class(class_name.value) or user32.GetParent(hwnd) != 0:
                    return True
                user32.ShowWindow(hwnd, 5)  # SW_SHOW
                return True
            user32.EnumWindows(EnumWindowsProc(_show_callback), 0)
        except Exception:
            pass
        # Selenium으로도 위치 복구
        if not self.driver:
            return
        try:
            self.driver.set_window_position(chrome_x, chrome_y)
            self.driver.set_window_size(chrome_width, chrome_height)
        except WebDriverException:
            pass

    # ------------------------------------------------------------------
    # 로그인 / 검색
    # ------------------------------------------------------------------
    def check_login_status(self):
        if not self.driver:
            return False
        try:
            current_url = (self.driver.current_url or "").lower()
            if "nid.naver.com/nidlogin" in current_url:
                return False
            cookies = self.driver.get_cookies()
            for cookie in cookies:
                if cookie.get("name") in ("NID_AUT", "NID_SES"):
                    return True
            return False
        except WebDriverException:
            return False

    def open_login_page(self):
        login_url = "https://nid.naver.com/nidlogin.login"
        debug_port = self._get_debug_port()

        # 먼저 로그인 URL로 크롬 프로세스를 띄워 UI 노출 속도를 우선 확보
        if not self.driver and not self._is_debug_port_open(debug_port):
            try:
                self._launch_chrome_process(debug_port, initial_url=login_url)
            except Exception:
                pass

        if not self.connect_driver(initial_url=login_url):
            return False

        self.log("🌐 네이버 로그인 페이지 열기...")
        try:
            if "nid.naver.com/nidlogin.login" not in (self.driver.current_url or ""):
                self.driver.get(login_url)
            self.update_status("로그인 페이지", "blue")
            return True
        except Exception as e:
            self.log(f"❌ 로그인 페이지 이동 실패: {str(e)[:30]}")
            self.driver = None
            self.update_status("브라우저 오류", "red")
            return False

    def search_keyword(self, keyword):
        if not self.connect_driver():
            return
        self.log(f"🔍 '{keyword}' 검색 중...")
        try:
            if not self._navigate_to_blog_search(keyword):
                self.log("❌ 검색 페이지 이동 실패")
                return
            self._click_blog_tab()
            self.update_status(f"검색: {keyword}", "blue")
        except WebDriverException:
            self.log("❌ 이동 실패. 브라우저 재연결 필요.")
            self.driver = None

    # ------------------------------------------------------------------
    # 블로그 ID 수집
    # ------------------------------------------------------------------
    def collect_blog_ids(self, processed_ids):
        queue = []
        blacklist = {"myblog", "postlist", "buddyaddform", "likeit", "nvisitor", "blog", "domainid", "admin", "search"}

        scroll_attempts = 0
        max_scroll = 7

        while len(queue) < 20 and scroll_attempts < max_scroll:
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            self.safe_sleep(1.0)

            new_count = 0
            try:
                all_links = self.driver.find_elements(By.TAG_NAME, "a")

                for link in all_links:
                    try:
                        href = link.get_attribute("href")
                        if not href or "blog.naver.com" not in href:
                            continue

                        match = re.search(r"blog\.naver\.com\/([a-zA-Z0-9_-]+)", href)
                        if not match:
                            continue

                        bid = match.group(1)
                        bid_lower = bid.lower()

                        if bid_lower in blacklist:
                            continue
                        if bid in processed_ids or len(bid) <= 3:
                            continue
                        if bid in queue or bid.isdigit():
                            continue

                        queue.append(bid)
                        processed_ids.add(bid)
                        new_count += 1
                    except (StaleElementReferenceException, NoSuchElementException):
                        continue
            except WebDriverException:
                pass

            self.log(f"   ⬇️ 스크롤 {scroll_attempts+1}/{max_scroll} - 신규 {new_count}명 (대기열: {len(queue)}명)")

            if len(queue) >= 20:
                break

            scroll_attempts += 1

            if new_count == 0:
                try:
                    more_btn = self.driver.find_element(By.CSS_SELECTOR, ".btn_more, .more_btn")
                    if more_btn.is_displayed():
                        self.safe_click(self.driver, more_btn)
                        self.safe_sleep(0.8)
                except (NoSuchElementException, StaleElementReferenceException):
                    pass

        return queue

    # ------------------------------------------------------------------
    # 서이추 신청
    # ------------------------------------------------------------------
    def process_neighbor(self, blog_id):
        driver = self.driver
        try:
            src = driver.page_source
            if "이웃끊기" in src or "서로이웃 취소" in src:
                return False, "스킵(이미 이웃)"

            clicked = False
            try:
                btn = driver.find_element(By.CSS_SELECTOR, "[data-click-area='ebc.add']")
                self.safe_click(driver, btn)
                clicked = True
            except (NoSuchElementException, StaleElementReferenceException):
                try:
                    if driver.find_elements(By.CSS_SELECTOR, "[data-click-area='ebc.ngr']"):
                        return False, "스킵(이미 이웃)"
                    btn = driver.find_element(By.XPATH, "//*[contains(text(), '이웃추가')]")
                    self.safe_click(driver, btn)
                    clicked = True
                except (NoSuchElementException, StaleElementReferenceException):
                    pass

            if not clicked:
                return False, "스킵(버튼 없음)"

            self.safe_sleep(0.3)

            src_after = driver.page_source
            if "하루에 신청 가능한 이웃수" in src_after and "초과" in src_after:
                try:
                    close_btn = driver.find_element(By.XPATH, "//button[contains(text(), '닫기')]")
                    self.safe_click(driver, close_btn)
                except (NoSuchElementException, StaleElementReferenceException):
                    pass
                return "DONE_DAY_LIMIT", "🎉 일일 한도 달성!"

            if "서로이웃 신청 진행중입니다" in src_after:
                try:
                    cancel_btns = driver.find_elements(By.XPATH, "//button[contains(text(), '취소')]")
                    for btn in cancel_btns:
                        if btn.is_displayed():
                            self.safe_click(driver, btn)
                            self.safe_sleep(0.1)
                            return False, "스킵(이미 신청중)"
                except (NoSuchElementException, StaleElementReferenceException):
                    pass
                return False, "스킵(이미 신청중)"

            layer_popup = driver.execute_script("""
                var layer = document.getElementById('_alertLayer');
                if (layer && layer.style.display !== 'none') {
                    var dsc = layer.querySelector('.dsc');
                    return dsc ? dsc.innerText : null;
                }
                return null;
            """)

            if layer_popup:
                if "하루" in layer_popup and "초과" in layer_popup:
                    return "DONE_DAY_LIMIT", "🎉 일일 한도 달성!"
                if "선택 그룹" in layer_popup:
                    return "STOP_GROUP_FULL", layer_popup
                try:
                    driver.execute_script("document.getElementById('_alertLayerClose').click();")
                except WebDriverException:
                    pass
                if "5,000" in layer_popup or "5000" in layer_popup:
                    return False, "스킵(상대 5000명)"
                return False, f"스킵({layer_popup[:20]})"

            current_url = driver.current_url
            if "BuddyAddForm" not in current_url:
                if not self.safe_get(driver, f"https://m.blog.naver.com/BuddyAddForm.naver?blogId={blog_id}"):
                    return False, "실패(양식 페이지 로드 실패)"
                self.safe_sleep(1.0)

            page_src = driver.page_source
            if "로그인" in page_src and "로그인이 필요" in page_src:
                return False, "실패(로그인 필요)"

            try:
                self.safe_sleep(0.2)
                radio_exists = driver.execute_script("return document.getElementById('bothBuddyRadio') !== null;")

                if not radio_exists:
                    one_way_radio = driver.execute_script("return document.getElementById('onewayBuddyRadio') !== null;")
                    if one_way_radio:
                        return False, "스킵(서이추 비활성화)"
                    if "진행 중" in page_src or "신청중" in page_src:
                        return False, "스킵(이미 신청중)"
                    return False, "실패(양식 없음)"

                result = driver.execute_script("""
                    try {
                        var radio = document.getElementById('bothBuddyRadio');
                        var label = document.querySelector("label[for='bothBuddyRadio']");
                        if (radio.disabled || radio.getAttribute('disabled')) return 'DISABLED';
                        if (!radio.checked && label) label.click();
                        return 'OK';
                    } catch(e) { return 'ERROR:' + e.message; }
                """)

                if result == "DISABLED":
                    return False, "스킵(서이추 불가)"
                if result and result.startswith("ERROR"):
                    return False, f"실패({result})"
            except WebDriverException as e:
                return False, f"실패(라디오: {str(e)[:10]})"

            try:
                textarea = driver.find_element(By.TAG_NAME, "textarea")
                driver.execute_script("""
                    var el = arguments[0];
                    var txt = arguments[1];
                    el.value = txt;
                    el.dispatchEvent(new Event('input', { bubbles: true }));
                    el.dispatchEvent(new Event('change', { bubbles: true }));
                """, textarea, self.neighbor_msg)
            except (NoSuchElementException, StaleElementReferenceException):
                pass

            try:
                confirm_btn = driver.find_element(By.XPATH, "//*[text()='확인']")
                self.safe_click(driver, confirm_btn)
                self.safe_sleep(self.fast_wait)
            except (NoSuchElementException, StaleElementReferenceException):
                return False, "실패(확인 버튼 없음)"

            final_popup = driver.execute_script("""
                var layer = document.getElementById('_alertLayer');
                if (layer && layer.style.display !== 'none') {
                    var dsc = layer.querySelector('.dsc');
                    return dsc ? dsc.innerText : null;
                }
                return null;
            """)

            if final_popup:
                if "하루" in final_popup and "초과" in final_popup:
                    return "DONE_DAY_LIMIT", "🎉 일일 한도 달성!"
                if "선택 그룹" in final_popup:
                    return "STOP_GROUP_FULL", final_popup
                try:
                    driver.execute_script("document.getElementById('_alertLayerClose').click();")
                except WebDriverException:
                    pass
                if "5,000" in final_popup or "5000" in final_popup:
                    return False, "스킵(상대 5000명)"
                return False, f"실패({final_popup[:20]})"

            try:
                WebDriverWait(driver, 0.5).until(EC.alert_is_present())
                alert = driver.switch_to.alert
                txt = alert.text
                alert.accept()

                if "하루" in txt and "초과" in txt:
                    return "DONE_DAY_LIMIT", txt
                if "선택 그룹" in txt:
                    return "STOP_GROUP_FULL", txt
                if "5,000" in txt or "5000" in txt:
                    return False, "스킵(상대 5000명)"
                if "신청" in txt or "완료" in txt:
                    return True, "신청 완료"
                return False, f"알림: {txt[:15]}"
            except (TimeoutException, NoSuchElementException):
                return True, "신청 완료"

        except Exception as e:
            return False, f"에러: {str(e)[:15]}"

    # ------------------------------------------------------------------
    # 공감 / 댓글
    # ------------------------------------------------------------------
    def process_like(self, driver):
        try:
            wrapper = self.safe_find_element(driver, By.CSS_SELECTOR, "a.u_likeit_button", timeout=3)
            if not wrapper:
                return "공감 버튼 없음"

            is_pressed = wrapper.get_attribute("aria-pressed") == "true"
            class_list = wrapper.get_attribute("class") or ""

            if is_pressed or "on" in class_list.split():
                return "이미 공감함"

            try:
                icon = wrapper.find_element(By.CSS_SELECTOR, "span.u_likeit_icon")
                ActionChains(driver).move_to_element(icon).click().perform()
                self.safe_sleep(self.normal_wait)

                if wrapper.get_attribute("aria-pressed") != "true":
                    driver.execute_script("arguments[0].click();", icon)
                    self.safe_sleep(self.fast_wait)

                return "공감 ❤️"
            except (NoSuchElementException, StaleElementReferenceException):
                self.safe_click(driver, wrapper)
                return "공감 ❤️"
        except WebDriverException:
            return "공감 실패"

    def process_comment(self, driver, blog_id):
        try:
            comment_btn = self.safe_find_element(
                driver, By.CSS_SELECTOR, "button[class*='comment_btn'], a.btn_comment", timeout=3
            )
            if not comment_btn:
                return "댓글 버튼 없음"

            self.safe_click(driver, comment_btn)
            self.safe_sleep(self.normal_wait)

            input_box = self.safe_find_element(
                driver, By.CSS_SELECTOR, ".u_cbox_text_mention, .u_cbox_inbox textarea", timeout=3
            )
            if not input_box:
                return "입력창 없음"

            target_nickname = blog_id
            try:
                name_el = driver.find_element(By.CSS_SELECTOR, ".user_name, .blogger_name")
                target_nickname = name_el.text.strip() or blog_id
            except (NoSuchElementException, StaleElementReferenceException):
                pass

            final_msg = self.comment_msg.format(name=target_nickname)
            try:
                ActionChains(driver).move_to_element(input_box).click().send_keys(final_msg).perform()
            except WebDriverException:
                driver.execute_script("""
                    arguments[0].value = arguments[1];
                    arguments[0].dispatchEvent(new Event('input', {bubbles: true}));
                """, input_box, final_msg)

            self.safe_sleep(0.2)

            submit_btn = self.safe_find_element(
                driver, By.CSS_SELECTOR, ".u_cbox_btn_upload, .u_cbox_btn_complete", timeout=2
            )
            if not submit_btn:
                return "등록 버튼 없음"

            self.safe_click(driver, submit_btn)

            try:
                WebDriverWait(driver, 0.5).until(EC.alert_is_present())
                alert = driver.switch_to.alert
                alert_text = alert.text
                alert.accept()

                if "차단" in alert_text or "스팸" in alert_text:
                    return "실패(스팸 차단)"
                return f"실패({alert_text[:10]})"
            except (TimeoutException, NoSuchElementException):
                pass

            self.safe_sleep(self.normal_wait)
            return "댓글 💬"
        except WebDriverException:
            return "댓글 실패"

    def _run_single_tab_loop(self, keyword):
        search_url = f"https://search.naver.com/search.naver?where=blog&query={keyword}"
        processed_ids = set()
        queue = []
        consecutive_errors = 0

        while self.is_running and self.current_count < self.target_count:
            if not queue:
                self.log(f"🔄 ID 수집 중... (처리 완료: {len(processed_ids)}명)")
                if not self.safe_get(self.driver, search_url):
                    self.log("❌ 검색 페이지 재진입 실패")
                    break
                self.safe_sleep(1.0)
                self._click_blog_tab()
                queue = self.collect_blog_ids(processed_ids)
                if not queue:
                    self.log("⚠️ 더 이상 수집할 블로그가 없습니다.")
                    break
                self.log(f"   ✅ {len(queue)}명 수집 완료!")

            blog_id = queue.pop(0)
            blacklist = {"myblog", "postlist", "buddyaddform", "likeit", "nvisitor", "blog", "domainid", "admin", "search"}
            if blog_id.lower() in blacklist:
                continue

            self.log(f"\n▶️ [{self.current_count+1}/{self.target_count}] '{blog_id}' 작업 시작")
            if not self.safe_get(self.driver, f"https://m.blog.naver.com/{blog_id}"):
                self.log("   ❌ 페이지 로드 실패")
                consecutive_errors += 1
                if consecutive_errors >= 5:
                    self.log("⚠️ 연속 5회 실패. 잠시 대기...")
                    self.safe_sleep(5.0)
                    consecutive_errors = 0
                continue

            self.safe_sleep(1.2)
            consecutive_errors = 0

            current_url = self.driver.current_url
            page_source = self.driver.page_source
            if "MobileErrorView" in current_url or "일시적인 오류" in page_source:
                self.log("   ❌ 접근 불가 블로그 (Skip)")
                continue

            is_friend, msg_friend = self.process_neighbor(blog_id)
            if is_friend == "DONE_DAY_LIMIT":
                self.log("\n🎉 목표 달성! 오늘 할당량을 모두 채웠습니다!")
                break
            if is_friend == "STOP_GROUP_FULL":
                self.log("\n⛔ 내 이웃 그룹이 가득 찼습니다.")
                break

            self.log(f"   └ 서이추: {msg_friend}")

            if "BuddyAddForm" in self.driver.current_url:
                self.safe_get(self.driver, f"https://m.blog.naver.com/{blog_id}")
                self.safe_sleep(self.normal_wait)

            if is_friend is True:
                msg_like = self.process_like(self.driver)
                self.log(f"   └ 공감: {msg_like}")

                if "실패" not in msg_like and "없음" not in msg_like:
                    msg_cmt = self.process_comment(self.driver, blog_id)
                    self.log(f"   └ 댓글: {msg_cmt}")

                self.current_count += 1
                self.log(f"   ✅ 성공! (현재 {self.current_count}/{self.target_count})")
                self.update_progress(self.current_count / self.target_count)

            wait_time = random.uniform(0.8, 1.5)
            self.safe_sleep(wait_time)

    # ------------------------------------------------------------------
    # 메인 자동화 루프
    # ------------------------------------------------------------------
    def start_working(self, keyword, target_count, neighbor_msg, comment_msg):
        if not self.connect_driver():
            self.log("❌ 브라우저 연결 실패")
            return

        if not self.check_login_status():
            self.log("❌ 로그인이 필요합니다!")
            self.update_status("로그인 필요", "red")
            return

        self.neighbor_msg = neighbor_msg
        self.comment_msg = comment_msg
        self.target_count = target_count
        self.is_running = True
        self.current_count = 0

        self.log("🚀 작업 시작")
        self.update_status("작업 실행 중...", "blue")

        if not self._navigate_to_blog_search(keyword):
            self.log("❌ 검색 페이지 로드 실패")
            self.is_running = False
            self.update_status("검색 실패", "red")
            return

        self._click_blog_tab()

        if self.webview2_mode:
            self._run_single_tab_loop(keyword)
            self.is_running = False
            self.log("🏁 작업 종료")
            self.update_status("작업 완료", "green")
            return

        main_window = self.driver.current_window_handle
        processed_ids = set()
        queue = []
        consecutive_errors = 0

        while self.is_running and self.current_count < self.target_count:
            if not queue:
                self.log(f"🔄 ID 수집 중... (처리 완료: {len(processed_ids)}명)")

                try:
                    if not self.driver.window_handles:
                        self.log("❌ 브라우저가 닫혔습니다.")
                        break
                    self.driver.switch_to.window(main_window)
                except WebDriverException:
                    self.log("❌ 메인 탭 접근 불가")
                    break

                queue = self.collect_blog_ids(processed_ids)

                if not queue:
                    self.log("⚠️ 더 이상 수집할 블로그가 없습니다.")
                    break

                self.log(f"   ✅ {len(queue)}명 수집 완료!")

            blog_id = queue.pop(0)
            blacklist = {"myblog", "postlist", "buddyaddform", "likeit", "nvisitor", "blog", "domainid", "admin", "search"}
            if blog_id.lower() in blacklist:
                continue

            self.log(f"\n▶️ [{self.current_count+1}/{self.target_count}] '{blog_id}' 작업 시작")

            try:
                self.driver.switch_to.new_window("tab")
                if not self.safe_get(self.driver, f"https://m.blog.naver.com/{blog_id}"):
                    self.log("   ❌ 페이지 로드 실패")
                    self._close_tab_and_return(main_window)
                    consecutive_errors += 1
                    if consecutive_errors >= 5:
                        self.log("⚠️ 연속 5회 실패. 잠시 대기...")
                        self.safe_sleep(5.0)
                        consecutive_errors = 0
                    continue
            except WebDriverException as e:
                self.log(f"   ⚠️ 탭 열기 실패: {str(e)[:20]}")
                self._close_tab_and_return(main_window)
                continue

            self.safe_sleep(1.5)
            consecutive_errors = 0

            current_url = self.driver.current_url
            page_source = self.driver.page_source

            if "MobileErrorView" in current_url or "일시적인 오류" in page_source:
                self.log("   ❌ 접근 불가 블로그 (Skip)")
                self._close_tab_and_return(main_window)
                continue

            is_friend, msg_friend = self.process_neighbor(blog_id)

            if is_friend == "DONE_DAY_LIMIT":
                self.log("\n🎉 목표 달성! 오늘 할당량을 모두 채웠습니다!")
                self._close_tab_and_return(main_window)
                break

            if is_friend == "STOP_GROUP_FULL":
                self.log("\n⛔ 내 이웃 그룹이 가득 찼습니다.")
                self._close_tab_and_return(main_window)
                break

            self.log(f"   └ 서이추: {msg_friend}")

            if "BuddyAddForm" in self.driver.current_url:
                self.safe_get(self.driver, f"https://m.blog.naver.com/{blog_id}")
                self.safe_sleep(self.normal_wait)

            if is_friend is True:
                msg_like = self.process_like(self.driver)
                self.log(f"   └ 공감: {msg_like}")

                if "실패" not in msg_like and "없음" not in msg_like:
                    msg_cmt = self.process_comment(self.driver, blog_id)
                    self.log(f"   └ 댓글: {msg_cmt}")

                self.current_count += 1
                self.log(f"   ✅ 성공! (현재 {self.current_count}/{self.target_count})")
                self.update_progress(self.current_count / self.target_count)

            self._close_tab_and_return(main_window)

            wait_time = random.uniform(0.8, 1.5)
            self.safe_sleep(wait_time)

        self.is_running = False
        self.log("🏁 작업 종료")
        self.update_status("작업 완료", "green")
