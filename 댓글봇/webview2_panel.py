import os
import platform
import sys
import ctypes
from ctypes import wintypes


IS_WINDOWS = platform.system() == "Windows"


if IS_WINDOWS:
    try:
        import comtypes
        from comtypes import GUID, COMMETHOD, COMObject, HRESULT, IUnknown, POINTER

        COMTYPES_AVAILABLE = True
        COMTYPES_IMPORT_ERROR = ""
    except Exception as exc:
        comtypes = None
        GUID = None
        COMMETHOD = None
        COMObject = object
        HRESULT = ctypes.c_long
        IUnknown = object
        POINTER = None
        COMTYPES_AVAILABLE = False
        COMTYPES_IMPORT_ERROR = str(exc)
else:
    comtypes = None
    GUID = None
    COMMETHOD = None
    COMObject = object
    HRESULT = ctypes.c_long
    IUnknown = object
    POINTER = None
    COMTYPES_AVAILABLE = False
    COMTYPES_IMPORT_ERROR = "Windows 전용 기능"


class WebView2PanelHost:
    """Tk/CTk 패널 HWND에 WebView2를 생성하는 최소 호스트."""

    def __init__(self, log_func=None):
        self._log = log_func or (lambda _msg: None)
        self._available = bool(IS_WINDOWS and COMTYPES_AVAILABLE)
        self._available_reason = COMTYPES_IMPORT_ERROR if not self._available else ""

        self._loader = None
        self._create_env_func = None

        self._parent_hwnd = 0
        self._bounds = (0, 0, 1, 1)
        self._initial_url = ""

        self._env = None
        self._controller = None
        self._webview = None

        self._started = False
        self._ready = False
        self._coinit_done = False

        self._env_handler_obj = None
        self._env_handler_ptr = None
        self._controller_handler_obj = None
        self._controller_handler_ptr = None

        self._last_error = ""

        self._debug_port = 0
        self._user_data_folder = ""

    @property
    def debug_port(self):
        return int(self._debug_port or 0)

    @property
    def is_ready(self):
        return bool(self._ready)

    @property
    def is_available(self):
        return bool(self._available)

    @property
    def unavailable_reason(self):
        return self._available_reason

    @property
    def last_error(self):
        return self._last_error

    def _set_error(self, message):
        self._last_error = str(message)
        self._log(f"⚠️ WebView2: {message}")

    def _log_info(self, message):
        self._log(f"🌐 WebView2: {message}")

    def _resource_dirs(self):
        dirs = []
        if hasattr(sys, "_MEIPASS"):
            dirs.append(getattr(sys, "_MEIPASS"))
        dirs.append(os.path.dirname(os.path.abspath(__file__)))
        dirs.append(os.getcwd())
        return dirs

    def _resolve_loader_candidates(self):
        env_path = os.environ.get("WEBVIEW2_LOADER_PATH", "").strip()
        candidates = []
        if env_path:
            candidates.append(env_path)

        for base in self._resource_dirs():
            candidates.append(os.path.join(base, "WebView2Loader.dll"))
            candidates.append(os.path.join(base, "WebView2Loader (1).dll"))

        # 시스템 경로 fallback
        candidates.append("WebView2Loader.dll")
        return candidates

    def _load_loader(self):
        for path in self._resolve_loader_candidates():
            try:
                lib = ctypes.WinDLL(path)
                self._log_info(f"Loader 사용: {path}")
                return lib
            except OSError:
                continue
        return None

    def _co_initialize(self):
        if self._coinit_done:
            return True
        COINIT_APARTMENTTHREADED = 0x2
        ole32 = ctypes.windll.ole32
        hr = ole32.CoInitializeEx(None, COINIT_APARTMENTTHREADED)
        # S_OK(0), S_FALSE(1) 허용
        if hr not in (0, 1):
            self._set_error(f"CoInitializeEx 실패 (hr=0x{int(hr) & 0xFFFFFFFF:08X})")
            return False
        self._coinit_done = True
        return True

    def _apply_debug_env_args(self):
        if self._debug_port <= 0:
            return
        current = (os.environ.get("WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS", "") or "").strip()
        required_flags = [
            f"--remote-debugging-port={int(self._debug_port)}",
            "--remote-debugging-address=127.0.0.1",
            "--remote-allow-origins=*",
        ]
        for flag in required_flags:
            if flag not in current:
                current = f"{current} {flag}".strip()
        os.environ["WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS"] = current

    def start(self, parent_hwnd, bounds, initial_url="about:blank",
              debug_port=None, user_data_folder=None):
        """WebView2 생성 시작(비동기)."""
        if not self._available:
            self._set_error(f"사용 불가: {self._available_reason}")
            return False

        if not self._co_initialize():
            return False

        self._parent_hwnd = int(parent_hwnd or 0)
        bx, by, bw, bh = bounds
        self._bounds = (int(bx), int(by), max(1, int(bw)), max(1, int(bh)))
        self._initial_url = str(initial_url or "about:blank")

        if self._parent_hwnd <= 0:
            self._set_error("부모 HWND가 유효하지 않습니다")
            return False

        if self._started:
            # 이미 시작된 경우에는 URL/크기만 갱신
            self.resize(*self._bounds)
            if self._ready:
                self.navigate(self._initial_url)
            return True

        if not self._loader:
            self._loader = self._load_loader()
        if not self._loader:
            self._set_error("WebView2Loader.dll 로드 실패")
            return False

        if not self._create_env_func:
            try:
                create_env = self._loader.CreateCoreWebView2EnvironmentWithOptions
                create_env.argtypes = [
                    ctypes.c_wchar_p,
                    ctypes.c_wchar_p,
                    ctypes.c_void_p,
                    POINTER(ICoreWebView2CreateCoreWebView2EnvironmentCompletedHandler),
                ]
                create_env.restype = HRESULT
                self._create_env_func = create_env
            except Exception as exc:
                self._set_error(f"CreateCoreWebView2EnvironmentWithOptions 준비 실패: {exc}")
                return False

        try:
            self._debug_port = int(debug_port or 9222)
            self._user_data_folder = str(user_data_folder or os.path.expanduser("~/WebView2BotData"))
            os.makedirs(self._user_data_folder, exist_ok=True)
            self._apply_debug_env_args()
            self._log_info(f"임베드 세션 포트: {self._debug_port}")

            self._env_handler_obj = _EnvironmentCompletedHandler(self)
            self._env_handler_ptr = self._env_handler_obj.QueryInterface(
                ICoreWebView2CreateCoreWebView2EnvironmentCompletedHandler
            )
            hr = self._create_env_func(None, self._user_data_folder, None, self._env_handler_ptr)
        except Exception as exc:
            self._set_error(f"환경 생성 요청 실패: {exc}")
            return False

        if hr != 0:
            self._set_error(f"환경 생성 호출 실패 (hr=0x{int(hr) & 0xFFFFFFFF:08X})")
            return False

        self._started = True
        self._log_info("환경 생성 요청 완료")
        return True

    def resize(self, x, y, width, height, parent_hwnd=None):
        self._bounds = (int(x), int(y), max(1, int(width)), max(1, int(height)))
        if parent_hwnd is not None:
            next_parent = int(parent_hwnd or 0)
            if next_parent > 0:
                self._parent_hwnd = next_parent
        if not self._controller:
            return
        try:
            if self._parent_hwnd > 0:
                self._controller.put_ParentWindow(wintypes.HWND(self._parent_hwnd))
            bx, by, bw, bh = self._bounds
            rect = self._get_parent_client_rect()
            if rect is None:
                rect = RECT(int(bx), int(by), int(bx + bw), int(by + bh))
            else:
                client_w = max(1, int(rect.right - rect.left))
                client_h = max(1, int(rect.bottom - rect.top))
                left = max(0, min(int(bx), client_w - 1))
                top = max(0, min(int(by), client_h - 1))
                width = max(1, min(int(bw), client_w - left))
                height = max(1, min(int(bh), client_h - top))
                rect = RECT(left, top, left + width, top + height)
            self._controller.put_Bounds(rect)
            self._controller.NotifyParentWindowPositionChanged()
        except Exception as exc:
            self._set_error(f"리사이즈 실패: {exc}")

    def navigate(self, url):
        if not self._webview:
            return False
        try:
            self._webview.Navigate(str(url))
            return True
        except Exception as exc:
            self._set_error(f"Navigate 실패: {exc}")
            return False

    def release_focus(self):
        if not self._controller:
            return
        try:
            # COREWEBVIEW2_MOVE_FOCUS_REASON_PROGRAMMATIC = 0
            self._controller.MoveFocus(0)
        except Exception:
            pass

    def close(self):
        try:
            if self._controller:
                self._controller.Close()
        except Exception:
            pass
        self._controller = None
        self._webview = None
        self._env = None
        self._ready = False

    def _get_parent_client_rect(self):
        if not self._parent_hwnd:
            return None
        try:
            user32 = ctypes.windll.user32
            rc = RECT()
            ok = user32.GetClientRect(wintypes.HWND(self._parent_hwnd), ctypes.byref(rc))
            if not ok:
                return None
            w = max(1, int(rc.right - rc.left))
            h = max(1, int(rc.bottom - rc.top))
            return RECT(0, 0, w, h)
        except Exception:
            return None

    def _on_environment_completed(self, error_code, created_environment):
        if error_code != 0 or not created_environment:
            self._set_error(f"환경 생성 콜백 실패 (hr=0x{int(error_code) & 0xFFFFFFFF:08X})")
            return 0

        self._env = created_environment
        self._log_info("환경 생성 완료")

        try:
            self._controller_handler_obj = _ControllerCompletedHandler(self)
            self._controller_handler_ptr = self._controller_handler_obj.QueryInterface(
                ICoreWebView2CreateCoreWebView2ControllerCompletedHandler
            )
            hr = self._env.CreateCoreWebView2Controller(
                wintypes.HWND(self._parent_hwnd),
                self._controller_handler_ptr,
            )
            if hr != 0:
                self._set_error(f"컨트롤러 생성 호출 실패 (hr=0x{int(hr) & 0xFFFFFFFF:08X})")
        except Exception as exc:
            self._set_error(f"컨트롤러 생성 요청 실패: {exc}")

        return 0

    def _on_controller_completed(self, error_code, created_controller):
        if error_code != 0 or not created_controller:
            self._set_error(f"컨트롤러 생성 콜백 실패 (hr=0x{int(error_code) & 0xFFFFFFFF:08X})")
            return 0

        self._controller = created_controller
        self._log_info("컨트롤러 생성 완료")

        try:
            self._controller.put_IsVisible(1)
            self._controller.put_ParentWindow(wintypes.HWND(self._parent_hwnd))
            self.resize(*self._bounds)
            self._webview = self._controller.get_CoreWebView2()
            try:
                self._controller.put_ZoomFactor(1.0)
            except Exception:
                pass
            if self._initial_url:
                self._log_info(f"Navigate 요청: {self._initial_url}")
                self._webview.Navigate(self._initial_url)
            self._ready = True
            self._log_info("패널 연결 완료")
        except Exception as exc:
            self._set_error(f"컨트롤러 초기화 실패: {exc}")

        return 0


if IS_WINDOWS and COMTYPES_AVAILABLE:
    class ICoreWebView2EnvironmentOptions(IUnknown):
        _iid_ = GUID("{2FDE08A8-1E9A-4766-8C05-95A9CEB9D1C5}")

    ICoreWebView2EnvironmentOptions._methods_ = [
        COMMETHOD([], HRESULT, "get_AdditionalBrowserArguments",
                  (["out"], POINTER(ctypes.c_wchar_p), "value")),
        COMMETHOD([], HRESULT, "put_AdditionalBrowserArguments",
                  (["in"], ctypes.c_wchar_p, "value")),
        COMMETHOD([], HRESULT, "get_AllowSingleSignOnUsingOSPrimaryAccount",
                  (["out"], POINTER(ctypes.c_int), "allow")),
        COMMETHOD([], HRESULT, "put_AllowSingleSignOnUsingOSPrimaryAccount",
                  (["in"], ctypes.c_int, "allow")),
    ]

    class _EnvironmentOptions(COMObject):
        _com_interfaces_ = [ICoreWebView2EnvironmentOptions]

        def __init__(self, additional_args=""):
            super().__init__()
            self._additional_args = additional_args

        def get_AdditionalBrowserArguments(self, value):
            value[0] = ctypes.c_wchar_p(self._additional_args)
            return 0

        def put_AdditionalBrowserArguments(self, value):
            self._additional_args = str(value or "")
            return 0

        def get_AllowSingleSignOnUsingOSPrimaryAccount(self, allow):
            allow[0] = 0
            return 0

        def put_AllowSingleSignOnUsingOSPrimaryAccount(self, allow):
            return 0

    class EventRegistrationToken(ctypes.Structure):
        _fields_ = [("value", ctypes.c_longlong)]


    class RECT(ctypes.Structure):
        _fields_ = [
            ("left", ctypes.c_long),
            ("top", ctypes.c_long),
            ("right", ctypes.c_long),
            ("bottom", ctypes.c_long),
        ]


    class ICoreWebView2(IUnknown):
        _iid_ = GUID("{76ECEACB-0462-4D94-AC83-423A6793775E}")


    class ICoreWebView2Controller(IUnknown):
        _iid_ = GUID("{4D00C0D1-9434-4EB6-8078-8697A560334F}")


    class ICoreWebView2CreateCoreWebView2ControllerCompletedHandler(IUnknown):
        _iid_ = GUID("{6C4819F3-C9B7-4260-8127-C9F5BDE7F68C}")


    class ICoreWebView2Environment(IUnknown):
        _iid_ = GUID("{B96D755E-0319-4E92-A296-23436F46A1FC}")


    class ICoreWebView2CreateCoreWebView2EnvironmentCompletedHandler(IUnknown):
        _iid_ = GUID("{4E8A3389-C9D8-4BD2-B6B5-124FEE6CC14D}")


    ICoreWebView2CreateCoreWebView2EnvironmentCompletedHandler._methods_ = [
        COMMETHOD(
            [],
            HRESULT,
            "Invoke",
            (["in"], HRESULT, "errorCode"),
            (["in"], POINTER(ICoreWebView2Environment), "createdEnvironment"),
        )
    ]


    ICoreWebView2CreateCoreWebView2ControllerCompletedHandler._methods_ = [
        COMMETHOD(
            [],
            HRESULT,
            "Invoke",
            (["in"], HRESULT, "errorCode"),
            (["in"], POINTER(ICoreWebView2Controller), "createdController"),
        )
    ]


    ICoreWebView2Environment._methods_ = [
        COMMETHOD(
            [],
            HRESULT,
            "CreateCoreWebView2Controller",
            (["in"], wintypes.HWND, "parentWindow"),
            (["in"], POINTER(ICoreWebView2CreateCoreWebView2ControllerCompletedHandler), "handler"),
        ),
    ]


    ICoreWebView2Controller._methods_ = [
        COMMETHOD([], HRESULT, "get_IsVisible", (["out"], POINTER(ctypes.c_int), "isVisible")),
        COMMETHOD([], HRESULT, "put_IsVisible", (["in"], ctypes.c_int, "isVisible")),
        COMMETHOD([], HRESULT, "get_Bounds", (["out"], POINTER(RECT), "bounds")),
        COMMETHOD([], HRESULT, "put_Bounds", (["in"], RECT, "bounds")),
        COMMETHOD([], HRESULT, "get_ZoomFactor", (["out"], POINTER(ctypes.c_double), "zoomFactor")),
        COMMETHOD([], HRESULT, "put_ZoomFactor", (["in"], ctypes.c_double, "zoomFactor")),
        COMMETHOD([], HRESULT, "add_ZoomFactorChanged", (["in"], ctypes.c_void_p, "eventHandler"), (["out"], POINTER(EventRegistrationToken), "token")),
        COMMETHOD([], HRESULT, "remove_ZoomFactorChanged", (["in"], EventRegistrationToken, "token")),
        COMMETHOD([], HRESULT, "SetBoundsAndZoomFactor", (["in"], RECT, "bounds"), (["in"], ctypes.c_double, "zoomFactor")),
        COMMETHOD([], HRESULT, "MoveFocus", (["in"], ctypes.c_int, "reason")),
        COMMETHOD([], HRESULT, "add_MoveFocusRequested", (["in"], ctypes.c_void_p, "eventHandler"), (["out"], POINTER(EventRegistrationToken), "token")),
        COMMETHOD([], HRESULT, "remove_MoveFocusRequested", (["in"], EventRegistrationToken, "token")),
        COMMETHOD([], HRESULT, "add_GotFocus", (["in"], ctypes.c_void_p, "eventHandler"), (["out"], POINTER(EventRegistrationToken), "token")),
        COMMETHOD([], HRESULT, "remove_GotFocus", (["in"], EventRegistrationToken, "token")),
        COMMETHOD([], HRESULT, "add_LostFocus", (["in"], ctypes.c_void_p, "eventHandler"), (["out"], POINTER(EventRegistrationToken), "token")),
        COMMETHOD([], HRESULT, "remove_LostFocus", (["in"], EventRegistrationToken, "token")),
        COMMETHOD([], HRESULT, "add_AcceleratorKeyPressed", (["in"], ctypes.c_void_p, "eventHandler"), (["out"], POINTER(EventRegistrationToken), "token")),
        COMMETHOD([], HRESULT, "remove_AcceleratorKeyPressed", (["in"], EventRegistrationToken, "token")),
        COMMETHOD([], HRESULT, "get_ParentWindow", (["out"], POINTER(wintypes.HWND), "parentWindow")),
        COMMETHOD([], HRESULT, "put_ParentWindow", (["in"], wintypes.HWND, "parentWindow")),
        COMMETHOD([], HRESULT, "NotifyParentWindowPositionChanged"),
        COMMETHOD([], HRESULT, "Close"),
        COMMETHOD([], HRESULT, "get_CoreWebView2", (["out"], POINTER(POINTER(ICoreWebView2)), "coreWebView2")),
    ]


    ICoreWebView2._methods_ = [
        COMMETHOD([], HRESULT, "get_Settings", (["out"], POINTER(ctypes.c_void_p), "settings")),
        COMMETHOD([], HRESULT, "get_Source", (["out"], POINTER(ctypes.c_wchar_p), "uri")),
        COMMETHOD([], HRESULT, "Navigate", (["in"], ctypes.c_wchar_p, "uri")),
        COMMETHOD([], HRESULT, "NavigateToString", (["in"], ctypes.c_wchar_p, "htmlContent")),
    ]


    class _EnvironmentCompletedHandler(COMObject):
        _com_interfaces_ = [ICoreWebView2CreateCoreWebView2EnvironmentCompletedHandler]

        def __init__(self, host):
            super().__init__()
            self._host = host

        def Invoke(self, errorCode, createdEnvironment):
            return self._host._on_environment_completed(errorCode, createdEnvironment)


    class _ControllerCompletedHandler(COMObject):
        _com_interfaces_ = [ICoreWebView2CreateCoreWebView2ControllerCompletedHandler]

        def __init__(self, host):
            super().__init__()
            self._host = host

        def Invoke(self, errorCode, createdController):
            return self._host._on_controller_completed(errorCode, createdController)

else:
    class RECT(ctypes.Structure):
        _fields_ = [
            ("left", ctypes.c_long),
            ("top", ctypes.c_long),
            ("right", ctypes.c_long),
            ("bottom", ctypes.c_long),
        ]
