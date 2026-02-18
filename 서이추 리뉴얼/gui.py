import time
import platform
import threading
import tkinter as tk

import customtkinter as ctk

from config import AppConfig
from constants import IOS_COLORS, IOS_FONT_LARGE, IOS_FONT_MEDIUM, IOS_FONT_REGULAR, IOS_FONT_SMALL, IOS_FONT_MONO
from bot_logic import NaverBotLogic

try:
    from webview2_panel import WebView2PanelHost
except Exception:
    WebView2PanelHost = None


class App(ctk.CTk):
    def __init__(self, config: AppConfig):
        super().__init__()
        self.config = config
        self.title("네이버 블로그 서이추 Pro")
        self.geometry("1600x900")
        self.resizable(True, True)

        # iOS 스타일 배경색
        self.configure(fg_color=IOS_COLORS["background"])

        self.logic = NaverBotLogic(config, self.log_msg, self.update_prog, self.update_browser_status, gui_window=self)
        self.embed_browser_windows = bool(self.config.get("embed_browser_windows")) and platform.system() == "Windows"
        self.use_webview2_panel = bool(self.config.get("use_webview2_panel")) and platform.system() == "Windows"
        self._browser_embed_rect = (0, 0, 100, 100)
        self._browser_embed_hwnd = 0
        self._browser_embed_client_rect = (0, 0, 100, 100)
        self.webview2_host = None
        self._webview2_ready = False
        self._webview2_poll_count = 0
        self._webview2_settle_remaining = 0
        self._webview2_resize_job = None

        # 부드러운 스크롤 상태
        self._scroll_velocity = 0.0
        self._scroll_animating = False
        self._scrollable_textboxes = []  # 독립 스크롤 대상 텍스트박스 목록

        # 좌우 분할 레이아웃
        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # ========== 왼쪽 패널 (컨트롤) ==========
        self.left_panel = ctk.CTkFrame(
            self,
            width=420,
            fg_color=IOS_COLORS["background"],
            corner_radius=0,
        )
        self.left_panel.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)
        self.left_panel.grid_propagate(False)
        self.left_panel.grid_columnconfigure(0, weight=1)
        self.left_panel.grid_rowconfigure(1, weight=1)

        # 헤더 영역 (iOS 스타일) - 고정
        header_frame = ctk.CTkFrame(
            self.left_panel,
            fg_color=IOS_COLORS["background"],
            corner_radius=0,
            height=100,
        )
        header_frame.grid(row=0, column=0, sticky="ew", padx=0, pady=0)
        header_frame.grid_propagate(False)

        self.lbl_title = ctk.CTkLabel(
            header_frame,
            text="서이추 Pro",
            font=IOS_FONT_LARGE,
            text_color=IOS_COLORS["text_primary"],
        )
        self.lbl_title.pack(pady=(28, 4))

        self.lbl_credit = ctk.CTkLabel(
            header_frame,
            text="made by ysh",
            font=IOS_FONT_SMALL,
            text_color=IOS_COLORS["text_secondary"],
        )
        self.lbl_credit.pack(pady=(0, 24))

        # 스크롤 가능한 컨텐츠 영역
        self.scrollable_frame = ctk.CTkScrollableFrame(
            self.left_panel,
            fg_color=IOS_COLORS["background"],
            corner_radius=0,
        )
        self.scrollable_frame.grid(row=1, column=0, sticky="nsew", padx=0, pady=0)
        self.scrollable_frame.grid_columnconfigure(0, weight=1)

        # ---- 로그인 카드 ----
        self.frame_login = ctk.CTkFrame(
            self.scrollable_frame, fg_color=IOS_COLORS["card"], corner_radius=16
        )
        self.frame_login.grid(row=0, column=0, padx=20, pady=(20, 12), sticky="ew")

        ctk.CTkLabel(
            self.frame_login, text="로그인", font=IOS_FONT_MEDIUM, text_color=IOS_COLORS["text_primary"]
        ).pack(anchor="w", padx=20, pady=(20, 14))

        ctk.CTkLabel(
            self.frame_login,
            text="프로그램 실행 시 로그인 페이지가 자동으로 열립니다.",
            font=IOS_FONT_REGULAR,
            text_color=IOS_COLORS["text_secondary"],
        ).pack(anchor="w", padx=20, pady=(0, 10))

        self.lbl_login_hint = ctk.CTkLabel(
            self.frame_login,
            text="로그인 완료 후 '작업 시작'을 누르세요.",
            font=IOS_FONT_SMALL,
            text_color=IOS_COLORS["text_secondary"],
        )
        self.lbl_login_hint.pack(anchor="w", padx=20, pady=(0, 18))

        # ---- 검색 카드 ----
        self.frame_search = ctk.CTkFrame(
            self.scrollable_frame, fg_color=IOS_COLORS["card"], corner_radius=16
        )
        self.frame_search.grid(row=1, column=0, padx=20, pady=12, sticky="ew")
        self.frame_search.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            self.frame_search, text="검색", font=IOS_FONT_MEDIUM, text_color=IOS_COLORS["text_primary"]
        ).grid(row=0, column=0, columnspan=2, sticky="w", padx=20, pady=(20, 14))

        self.entry_keyword = ctk.CTkEntry(
            self.frame_search,
            placeholder_text="검색 키워드",
            corner_radius=10,
            height=48,
            font=IOS_FONT_REGULAR,
            fg_color=IOS_COLORS["input_bg"],
            border_width=0,
        )
        self.entry_keyword.grid(row=1, column=0, padx=(20, 10), pady=(0, 20), sticky="ew")

        self.btn_search = ctk.CTkButton(
            self.frame_search,
            text="이동",
            width=80,
            command=self.on_search,
            fg_color=IOS_COLORS["secondary"],
            hover_color="#4A4AC4",
            corner_radius=10,
            height=48,
            font=("SF Pro Text", 15, "bold"),
        )
        self.btn_search.grid(row=1, column=1, padx=(0, 20), pady=(0, 20))

        # ---- 설정 카드 ----
        self.frame_settings = ctk.CTkFrame(
            self.scrollable_frame, fg_color=IOS_COLORS["card"], corner_radius=16
        )
        self.frame_settings.grid(row=2, column=0, padx=20, pady=12, sticky="ew")

        ctk.CTkLabel(
            self.frame_settings, text="설정", font=IOS_FONT_MEDIUM, text_color=IOS_COLORS["text_primary"]
        ).pack(anchor="w", padx=20, pady=(20, 14))

        # 목표 개수
        target_row = ctk.CTkFrame(self.frame_settings, fg_color="transparent")
        target_row.pack(fill="x", padx=20, pady=(0, 20))
        ctk.CTkLabel(target_row, text="목표 개수", font=IOS_FONT_REGULAR, text_color=IOS_COLORS["text_primary"]).pack(side="left")
        self.entry_target = ctk.CTkEntry(
            target_row, placeholder_text="100", width=100, corner_radius=10, height=40,
            font=IOS_FONT_REGULAR, justify="center", fg_color=IOS_COLORS["input_bg"], border_width=0,
        )
        self.entry_target.pack(side="right")

        # ---- 메시지 카드 ----
        self.frame_msg = ctk.CTkFrame(
            self.scrollable_frame, fg_color=IOS_COLORS["card"], corner_radius=16
        )
        self.frame_msg.grid(row=3, column=0, padx=20, pady=12, sticky="ew")

        ctk.CTkLabel(
            self.frame_msg, text="메시지", font=IOS_FONT_MEDIUM, text_color=IOS_COLORS["text_primary"]
        ).pack(anchor="w", padx=20, pady=(20, 14))

        ctk.CTkLabel(
            self.frame_msg, text="서이추 메시지", font=IOS_FONT_SMALL, text_color=IOS_COLORS["text_secondary"]
        ).pack(anchor="w", padx=20, pady=(0, 8))

        self.txt_msg = ctk.CTkTextbox(
            self.frame_msg, height=75, corner_radius=10, font=IOS_FONT_SMALL,
            fg_color=IOS_COLORS["input_bg"], text_color=IOS_COLORS["text_primary"], border_width=0,
        )
        self.txt_msg.pack(fill="x", padx=20, pady=(0, 14))

        ctk.CTkLabel(
            self.frame_msg, text="댓글 메시지", font=IOS_FONT_SMALL, text_color=IOS_COLORS["text_secondary"]
        ).pack(anchor="w", padx=20, pady=(0, 8))

        self.txt_cmt = ctk.CTkTextbox(
            self.frame_msg, height=75, corner_radius=10, font=IOS_FONT_SMALL,
            fg_color=IOS_COLORS["input_bg"], text_color=IOS_COLORS["text_primary"], border_width=0,
        )
        self.txt_cmt.pack(fill="x", padx=20, pady=(0, 20))

        # ---- 액션 버튼 카드 ----
        action_frame = ctk.CTkFrame(
            self.scrollable_frame, fg_color=IOS_COLORS["card"], corner_radius=16
        )
        action_frame.grid(row=4, column=0, padx=20, pady=12, sticky="ew")

        self.btn_start = ctk.CTkButton(
            action_frame, text="작업 시작", command=self.on_start,
            fg_color=IOS_COLORS["success"], hover_color="#30B350",
            corner_radius=12, height=54, font=("SF Pro Text", 17, "bold"),
        )
        self.btn_start.pack(fill="x", padx=20, pady=(20, 12))

        self.btn_stop = ctk.CTkButton(
            action_frame, text="작업 정지", command=self.on_stop,
            fg_color=IOS_COLORS["danger"], hover_color="#E6342A",
            corner_radius=12, height=54, font=("SF Pro Text", 17, "bold"),
        )
        self.btn_stop.pack(fill="x", padx=20, pady=(0, 20))
        self.btn_stop.configure(state="disabled")

        # ---- 진행률 카드 ----
        progress_frame = ctk.CTkFrame(
            self.scrollable_frame, fg_color=IOS_COLORS["card"], corner_radius=16
        )
        progress_frame.grid(row=5, column=0, padx=20, pady=12, sticky="ew")

        ctk.CTkLabel(
            progress_frame, text="진행 상황", font=IOS_FONT_MEDIUM, text_color=IOS_COLORS["text_primary"]
        ).pack(anchor="w", padx=20, pady=(20, 14))

        self.progressbar = ctk.CTkProgressBar(
            progress_frame, progress_color=IOS_COLORS["primary"], height=8, corner_radius=4
        )
        self.progressbar.pack(fill="x", padx=20, pady=(0, 14))
        self.progressbar.set(0)

        self.lbl_browser_status = ctk.CTkLabel(
            progress_frame, text="브라우저: 대기 중", font=IOS_FONT_SMALL, text_color=IOS_COLORS["text_secondary"]
        )
        self.lbl_browser_status.pack(anchor="w", padx=20, pady=(0, 20))

        # ---- 로그 카드 ----
        log_frame = ctk.CTkFrame(
            self.scrollable_frame, fg_color=IOS_COLORS["card"], corner_radius=16
        )
        log_frame.grid(row=6, column=0, padx=20, pady=12, sticky="ew")
        log_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            log_frame, text="활동 로그", font=IOS_FONT_MEDIUM, text_color=IOS_COLORS["text_primary"]
        ).grid(row=0, column=0, sticky="w", padx=20, pady=(20, 14))

        self.txt_log = ctk.CTkTextbox(
            log_frame, state="disabled", font=IOS_FONT_MONO,
            fg_color=IOS_COLORS["input_bg"], text_color=IOS_COLORS["text_primary"],
            corner_radius=10, border_width=0,
        )
        self.txt_log.grid(row=1, column=0, padx=20, pady=(0, 20), sticky="nsew")

        # 독립 스크롤 대상 텍스트박스 등록
        self._scrollable_textboxes = [self.txt_log, self.txt_msg, self.txt_cmt]

        # ========== 오른쪽 패널 (브라우저 화면 영역) ==========
        self.right_panel = ctk.CTkFrame(
            self, fg_color=IOS_COLORS["background"], corner_radius=0
        )
        self.right_panel.grid(row=0, column=1, sticky="nsew", padx=0, pady=0)
        self.right_panel.grid_columnconfigure(0, weight=1)
        self.right_panel.grid_rowconfigure(0, weight=1)

        self.browser_placeholder = ctk.CTkFrame(
            self.right_panel, fg_color=IOS_COLORS["card"], corner_radius=24
        )
        self.browser_placeholder.grid(row=0, column=0, sticky="nsew", padx=30, pady=30)
        self.browser_placeholder.grid_columnconfigure(0, weight=1)
        self.browser_placeholder.grid_rowconfigure(0, weight=1)

        # WebView2 host는 별도 native tk.Frame HWND를 사용
        self.browser_native_host = tk.Frame(
            self.browser_placeholder,
            bg="#FFFFFF",
            bd=0,
            highlightthickness=0,
            takefocus=0,
        )
        self.browser_native_host.place(x=0, y=0, relwidth=1, relheight=1)
        self.browser_native_host.lower()
        self.browser_placeholder.bind("<Configure>", self._on_browser_host_configure, add="+")
        self.browser_native_host.bind("<Configure>", self._on_browser_host_configure, add="+")

        self.browser_center_container = ctk.CTkFrame(self.browser_placeholder, fg_color="transparent", corner_radius=0)
        self.browser_center_container.grid(row=0, column=0, sticky="")

        ctk.CTkLabel(self.browser_center_container, text="🌐", font=("SF Pro Display", 72), width=100, height=100).pack(pady=(50, 24))

        self.lbl_browser_placeholder = ctk.CTkLabel(
            self.browser_center_container, text="브라우저 화면",
            font=("SF Pro Display", 26, "bold"), text_color=IOS_COLORS["text_primary"],
        )
        self.lbl_browser_placeholder.pack(pady=(0, 14))

        placeholder_desc = "WebView2 브라우저가 이 영역에\n내장되어 실행됩니다" if self.use_webview2_panel else "크롬 창이 이 영역에\n자동으로 배치됩니다"
        ctk.CTkLabel(
            self.browser_center_container, text=placeholder_desc,
            font=IOS_FONT_REGULAR, text_color=IOS_COLORS["text_secondary"], justify="center",
        ).pack(pady=(0, 50))

        # GUI 창 이동 감지
        self._last_geometry = None
        self._position_update_scheduled = False
        self._last_update_time = 0
        self._update_throttle = 0.2
        self.bind("<Configure>", self._on_window_move)

        # config에서 값 복원
        self._load_from_config()
        self._cache_browser_embed_metrics(force_update=True)
        self.log_msg("프로그램 준비 완료.")
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        if self.use_webview2_panel:
            self._init_webview2_panel()

        # 마우스 휠: bind_all 대신 왼쪽 패널 위젯에만 직접 바인딩 (클릭 간섭 없음)
        self.after(100, lambda: self._bind_scroll_recursive(self.left_panel))
        self.after(140, lambda: self._bind_focus_recursive(self.left_panel))

        self.after(300, self._auto_open_login_page)

    # ------------------------------------------------------------------
    # config 로드/저장
    # ------------------------------------------------------------------
    def _load_from_config(self):
        """config에서 GUI 필드 복원."""
        keyword = self.config.get("keyword")
        if keyword:
            self.entry_keyword.insert(0, keyword)

        target = self.config.get("target_count")
        self.entry_target.insert(0, str(target))

        neighbor_msg = self.config.get("neighbor_msg")
        if neighbor_msg:
            self.txt_msg.insert("1.0", neighbor_msg)

        comment_msg = self.config.get("comment_msg")
        if comment_msg:
            self.txt_cmt.insert("1.0", comment_msg)

    def _save_to_config(self):
        """GUI 값을 config에 저장하고 JSON 기록."""
        self.config.set("keyword", self.entry_keyword.get().strip())
        try:
            self.config.set("target_count", int(self.entry_target.get() or "100"))
        except ValueError:
            self.config.set("target_count", 100)
        self.config.set("neighbor_msg", self.txt_msg.get("1.0", "end").strip())
        self.config.set("comment_msg", self.txt_cmt.get("1.0", "end").strip())
        self.config.save()

    # ------------------------------------------------------------------
    # 스레드 안전 UI 업데이트
    # ------------------------------------------------------------------
    def _do_log(self, msg):
        self.txt_log.configure(state="normal")
        timestamp = time.strftime("%H:%M:%S")
        self.txt_log.insert("end", f"[{timestamp}] {msg}\n")
        self.txt_log.see("end")
        self.txt_log.configure(state="disabled")

    def log_msg(self, msg):
        if threading.current_thread() is threading.main_thread():
            self._do_log(msg)
        else:
            self.after(0, self._do_log, msg)

    def _do_update_prog(self, val):
        self.progressbar.set(val)

    def update_prog(self, val):
        if threading.current_thread() is threading.main_thread():
            self._do_update_prog(val)
        else:
            self.after(0, self._do_update_prog, val)

    def _do_update_browser_status(self, status, color):
        color_map = {
            "green": IOS_COLORS["success"],
            "red": IOS_COLORS["danger"],
            "blue": IOS_COLORS["primary"],
            "orange": "#FF9500",
            "gray": IOS_COLORS["text_secondary"],
        }
        status_color = color_map.get(color, IOS_COLORS["text_secondary"])
        self.lbl_browser_status.configure(text=f"브라우저: {status}", text_color=status_color)
        if self.use_webview2_panel:
            if self.webview2_host and self.webview2_host.is_ready:
                self.browser_center_container.grid_remove()
            else:
                self.browser_center_container.grid()
            return
        if "연결됨" in status or "완료" in status:
            if self.embed_browser_windows:
                if hasattr(self.logic, "is_chrome_embedded") and self.logic.is_chrome_embedded():
                    self.browser_center_container.grid_remove()
                else:
                    self.browser_center_container.grid()
            else:
                self.browser_placeholder.grid_remove()

    def update_browser_status(self, status, color="gray"):
        if threading.current_thread() is threading.main_thread():
            self._do_update_browser_status(status, color)
        else:
            self.after(0, self._do_update_browser_status, status, color)

    def get_browser_embed_hwnd(self):
        """Windows에서 브라우저 임베드 대상 HWND 반환."""
        return int(self._browser_embed_hwnd)

    def get_browser_embed_rect(self):
        """브라우저 카드의 절대 좌표/크기 반환."""
        return self._browser_embed_rect

    def get_browser_embed_client_rect(self):
        """임베드 부모(hwnd) 기준 브라우저 영역 상대 좌표."""
        return self._browser_embed_client_rect

    def _cache_browser_embed_metrics(self, force_update=False):
        if force_update:
            self.update_idletasks()
            self.browser_native_host.update_idletasks()
        host_root_x = int(self.browser_native_host.winfo_rootx())
        host_root_y = int(self.browser_native_host.winfo_rooty())
        host_w = int(self.browser_native_host.winfo_width())
        host_h = int(self.browser_native_host.winfo_height())

        self._browser_embed_rect = (
            host_root_x,
            host_root_y,
            host_w,
            host_h,
        )
        # 임베드 부모는 native host HWND
        self._browser_embed_hwnd = int(self.browser_native_host.winfo_id())
        self._browser_embed_client_rect = (
            0,
            0,
            max(1, host_w),
            max(1, host_h),
        )

    def _init_webview2_panel(self):
        if not self.use_webview2_panel:
            return
        if WebView2PanelHost is None:
            self.log_msg("⚠️ WebView2 모듈 로드 실패. Chrome 임베드 모드로 동작합니다.")
            self.use_webview2_panel = False
            if hasattr(self.logic, "set_webview2_host"):
                self.logic.set_webview2_host(None)
            return
        self.webview2_host = WebView2PanelHost(self.log_msg)
        if not self.webview2_host.is_available:
            self.log_msg(f"⚠️ WebView2 사용 불가: {self.webview2_host.unavailable_reason}")
            self.use_webview2_panel = False
            self.webview2_host = None
            if hasattr(self.logic, "set_webview2_host"):
                self.logic.set_webview2_host(None)
            return
        if hasattr(self.logic, "set_webview2_host"):
            self.logic.set_webview2_host(self.webview2_host)
        self.log_msg("🌐 WebView2 내장 패널 초기화 준비")
        self.update_browser_status("WebView2 준비 중...", "blue")
        self.after(250, self._start_webview2_panel)

    def _start_webview2_panel(self):
        if not self.use_webview2_panel or not self.webview2_host:
            return
        self._cache_browser_embed_metrics(force_update=True)
        x, y, w, h = self.get_browser_embed_client_rect()
        started = self.webview2_host.start(
            self.get_browser_embed_hwnd(),
            (x, y, w, h),
            "https://nid.naver.com/nidlogin.login",
        )
        if not started:
            self.log_msg(f"⚠️ WebView2 시작 실패: {self.webview2_host.last_error}")
            self.use_webview2_panel = False
            self.webview2_host = None
            return
        self._webview2_poll_count = 0
        self.after(120, self._poll_webview2_ready)

    def _poll_webview2_ready(self):
        if not self.webview2_host:
            return
        self._webview2_poll_count += 1
        if self.webview2_host.is_ready:
            if not self._webview2_ready:
                self._webview2_ready = True
                self.browser_native_host.lift()
                self.browser_center_container.grid_remove()
                self.update_browser_status("WebView2 연결됨", "green")
                self.log_msg("🧩 WebView2 내장 브라우저 모드 활성화")
                self._webview2_settle_remaining = 12
                self.after(80, self._settle_webview2_bounds)
            self._schedule_webview2_resize()
            return
        if self._webview2_poll_count < 120:
            self.after(120, self._poll_webview2_ready)
            return
        self.log_msg("⚠️ WebView2 준비 시간 초과. Chrome 임베드 모드로 동작합니다.")
        self.use_webview2_panel = False
        self.webview2_host = None
        if hasattr(self.logic, "set_webview2_host"):
            self.logic.set_webview2_host(None)

    def _resize_webview2_panel(self):
        if not self.webview2_host:
            return
        self._cache_browser_embed_metrics()
        x, y, w, h = self.get_browser_embed_client_rect()
        self.webview2_host.resize(
            x,
            y,
            w,
            h,
            parent_hwnd=self.get_browser_embed_hwnd(),
        )

    def _settle_webview2_bounds(self):
        if not (self.use_webview2_panel and self.webview2_host and self.webview2_host.is_ready):
            return
        self._cache_browser_embed_metrics(force_update=True)
        self._resize_webview2_panel()
        self._webview2_settle_remaining -= 1
        if self._webview2_settle_remaining > 0:
            self.after(120, self._settle_webview2_bounds)

    def _on_close(self):
        try:
            if self._webview2_resize_job is not None:
                self.after_cancel(self._webview2_resize_job)
                self._webview2_resize_job = None
        except Exception:
            pass
        try:
            if self.webview2_host:
                self.webview2_host.close()
        except Exception:
            pass
        self.destroy()

    def _auto_open_login_page(self):
        if self.use_webview2_panel:
            self.log_msg("🔓 WebView2 패널에서 네이버 로그인을 진행하세요.")
            return
        threading.Thread(target=self._thread_open_login_page, daemon=True).start()

    # ------------------------------------------------------------------
    # 이벤트 핸들러
    # ------------------------------------------------------------------
    def _on_window_move(self, event):
        if event.widget != self:
            return
        if self.use_webview2_panel and self.webview2_host:
            self._schedule_webview2_resize()
            return
        current_time = time.time()
        if current_time - self._last_update_time < self._update_throttle:
            return
        self._cache_browser_embed_metrics()
        try:
            current_x = self.winfo_x()
            current_y = self.winfo_y()
            current_w = self.winfo_width()
            current_h = self.winfo_height()
        except Exception:
            return
        current_geometry = (current_x, current_y, current_w, current_h)
        if self._last_geometry and self._last_geometry == current_geometry:
            return
        self._last_geometry = current_geometry
        self._last_update_time = current_time
        if self.logic and self.logic.driver and not self._position_update_scheduled:
            self._position_update_scheduled = True
            self.after(80, self._update_chrome_position)

    def _update_chrome_position(self):
        self._position_update_scheduled = False
        if self.use_webview2_panel and self.webview2_host:
            self._cache_browser_embed_metrics()
            self._resize_webview2_panel()
            return
        if not self.logic.driver:
            return
        try:
            self._cache_browser_embed_metrics()
            self.logic._position_chrome_window(self)
        except Exception:
            pass

    def _on_browser_host_configure(self, _event=None):
        if not (self.use_webview2_panel and self.webview2_host):
            return
        self._schedule_webview2_resize()

    def _schedule_webview2_resize(self):
        if not (self.use_webview2_panel and self.webview2_host):
            return
        if self._webview2_resize_job is not None:
            return

        def _run():
            self._webview2_resize_job = None
            if not (self.use_webview2_panel and self.webview2_host):
                return
            self._resize_webview2_panel()

        self._webview2_resize_job = self.after_idle(_run)

    def _bind_scroll_recursive(self, widget):
        """위젯과 모든 자식에게 마우스 휠 바인딩 (bind_all 없이)."""
        widget.bind("<MouseWheel>", self._on_mousewheel, add="+")
        for child in widget.winfo_children():
            self._bind_scroll_recursive(child)

    def _bind_focus_recursive(self, widget):
        """입력 위젯 클릭 시 포커스를 실제 입력 컨트롤로 보정."""
        if isinstance(widget, (ctk.CTkEntry, ctk.CTkTextbox, tk.Entry, tk.Text)):
            widget.bind("<Button-1>", self._focus_left_widget, add="+")
        for child in widget.winfo_children():
            self._bind_focus_recursive(child)

    def _resolve_focus_target(self, widget):
        if isinstance(widget, ctk.CTkEntry):
            return getattr(widget, "_entry", widget)
        if isinstance(widget, ctk.CTkTextbox):
            return getattr(widget, "_textbox", widget)
        if isinstance(widget, (tk.Entry, tk.Text)):
            return widget
        return None

    def _focus_left_widget(self, event):
        try:
            target = self._resolve_focus_target(event.widget)
            if target is None:
                return
            if self.use_webview2_panel and self.webview2_host:
                self.webview2_host.release_focus()
            self.focus_force()
            self.after_idle(target.focus_set)
        except Exception:
            pass

    def _on_mousewheel(self, event):
        # 독립 스크롤 텍스트박스 위인지 확인
        widget_path = str(event.widget)
        for tb in self._scrollable_textboxes:
            tb_path = str(tb)
            if widget_path == tb_path or widget_path.startswith(tb_path + "."):
                return self._scroll_textbox(tb, event)

        # 메인 패널 스크롤
        self._handle_panel_scroll(event)

    def _scroll_textbox(self, textbox, event):
        """텍스트박스를 독립적으로 스크롤. 끝에 도달하면 부모 패널로 전파."""
        delta = event.delta if platform.system() == "Darwin" else event.delta / 120
        scrolling_up = delta > 0

        top, bottom = textbox._textbox.yview()

        if (scrolling_up and top <= 0.0) or (not scrolling_up and bottom >= 1.0):
            self._handle_panel_scroll(event)
            return

        units = -1 if scrolling_up else 1
        textbox._textbox.yview_scroll(units * 2, "units")

    def _handle_panel_scroll(self, event):
        """왼쪽 패널 부드러운 스크롤."""
        if platform.system() == "Darwin":
            delta = event.delta
        else:
            delta = event.delta / 120 * 4 if getattr(event, "delta", 0) else 0

        if delta == 0:
            return

        self._scroll_velocity += delta * -1.2

        if not self._scroll_animating:
            self._scroll_animating = True
            self._animate_scroll()

    def _animate_scroll(self):
        if not self._scroll_animating:
            return
        try:
            canvas = self.scrollable_frame._parent_canvas

            if abs(self._scroll_velocity) < 0.5:
                self._scroll_velocity = 0.0
                self._scroll_animating = False
                return

            top, bottom = canvas.yview()
            visible_fraction = bottom - top

            if visible_fraction >= 1.0:
                self._scroll_velocity = 0.0
                self._scroll_animating = False
                return

            total_height = canvas.winfo_height() / visible_fraction
            new_top = top + self._scroll_velocity / total_height
            new_top = max(0.0, min(1.0 - visible_fraction, new_top))

            canvas.yview_moveto(new_top)

            if (new_top <= 0.0 and self._scroll_velocity < 0) or \
               (new_top >= 1.0 - visible_fraction and self._scroll_velocity > 0):
                self._scroll_velocity = 0.0
                self._scroll_animating = False
                return

            self._scroll_velocity *= 0.82
            self.after(16, self._animate_scroll)
        except Exception:
            self._scroll_velocity = 0.0
            self._scroll_animating = False

    # ------------------------------------------------------------------
    # 버튼 액션
    # ------------------------------------------------------------------
    def _thread_open_login_page(self):
        ok = self.logic.open_login_page()
        if ok:
            self.log_msg("🔓 브라우저에서 네이버 로그인을 진행하세요.")

    def on_search(self):
        k = self.entry_keyword.get()
        if not k:
            self.log_msg("⚠️ 키워드를 입력하세요.")
            return
        if self.use_webview2_panel:
            if not self.webview2_host or not self.webview2_host.is_ready:
                self.log_msg("⚠️ WebView2가 아직 준비되지 않았습니다. 잠시 후 다시 시도하세요.")
                return
            self._save_to_config()
            query_url = f"https://search.naver.com/search.naver?where=blog&query={k}"
            if self.webview2_host.navigate(query_url):
                self.log_msg(f"🔍 WebView2 검색 이동: '{k}'")
                self.update_browser_status(f"검색: {k}", "blue")
            else:
                self.log_msg("⚠️ WebView2 검색 이동 실패")
            return
        self.btn_search.configure(state="disabled", text="검색 중...")
        self.update_idletasks()
        self.log_msg(f"🔍 '{k}' 검색 중...")
        threading.Thread(target=self._thread_search, args=(k,), daemon=True).start()

    def _thread_search(self, k):
        if not self.logic.driver:
            self.logic.connect_driver()
        self.logic.search_keyword(k)
        self.after(0, lambda: self.btn_search.configure(state="normal", text="이동"))

    def on_start(self):
        if self.use_webview2_panel and (not self.webview2_host or not self.webview2_host.is_ready):
            self.log_msg("⚠️ WebView2가 아직 준비되지 않았습니다. 잠시 후 다시 시도하세요.")
            return
        if self.logic.is_running:
            self.log_msg("⚠️ 이미 실행 중입니다.")
            return

        keyword = self.entry_keyword.get()
        if not keyword:
            self.log_msg("⚠️ 검색 키워드를 입력하세요.")
            return

        # GUI → config → JSON 저장
        self._save_to_config()

        try:
            target_count = int(self.entry_target.get() or "100")
        except ValueError:
            target_count = 100

        neighbor_msg = self.txt_msg.get("1.0", "end").strip()
        comment_msg = self.txt_cmt.get("1.0", "end").strip()

        if not neighbor_msg:
            neighbor_msg = self.config.get("neighbor_msg")
        if not comment_msg:
            comment_msg = self.config.get("comment_msg")

        self.btn_start.configure(state="disabled", text="시작 중...")
        self.btn_stop.configure(state="normal")
        self.update_idletasks()
        self.log_msg(f"🚀 작업 시작: '{keyword}' (목표: {target_count}개)")
        threading.Thread(
            target=self._thread_start, args=(keyword, target_count, neighbor_msg, comment_msg), daemon=True
        ).start()

    def _thread_start(self, keyword, target_count, neighbor_msg, comment_msg):
        self.logic.start_working(keyword, target_count, neighbor_msg, comment_msg)
        self.after(0, self._update_button_state)

    def _update_button_state(self):
        if not self.logic.is_running:
            self.btn_start.configure(state="normal", text="작업 시작")
            self.btn_stop.configure(state="disabled")
        else:
            self.btn_start.configure(state="disabled", text="작업 중...")
            self.btn_stop.configure(state="normal")

    def on_stop(self):
        if self.logic.is_running:
            self.logic.is_running = False
            self.log_msg("🛑 정지 요청됨...")
            self.btn_start.configure(state="normal", text="작업 시작")
            self.btn_stop.configure(state="disabled")
            self.update_idletasks()
        else:
            self.log_msg("실행 중 아님")
