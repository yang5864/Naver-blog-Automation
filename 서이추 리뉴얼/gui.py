import time
import platform
import threading

import customtkinter as ctk

from config import AppConfig
from constants import IOS_COLORS, IOS_FONT_LARGE, IOS_FONT_MEDIUM, IOS_FONT_REGULAR, IOS_FONT_SMALL, IOS_FONT_MONO
from bot_logic import NaverBotLogic


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

        # 마우스 휠 이벤트 바인딩
        self.left_panel.bind("<MouseWheel>", self._on_mousewheel)
        self.left_panel.bind("<Button-4>", self._on_mousewheel)
        self.left_panel.bind("<Button-5>", self._on_mousewheel)
        self.scrollable_frame.bind("<MouseWheel>", self._on_mousewheel)
        self.scrollable_frame.bind("<Button-4>", self._on_mousewheel)
        self.scrollable_frame.bind("<Button-5>", self._on_mousewheel)

        # ---- 로그인 카드 ----
        self.frame_login = ctk.CTkFrame(
            self.scrollable_frame, fg_color=IOS_COLORS["card"], corner_radius=16
        )
        self.frame_login.grid(row=0, column=0, padx=20, pady=(20, 12), sticky="ew")

        ctk.CTkLabel(
            self.frame_login, text="로그인", font=IOS_FONT_MEDIUM, text_color=IOS_COLORS["text_primary"]
        ).pack(anchor="w", padx=20, pady=(20, 14))

        self.entry_id = ctk.CTkEntry(
            self.frame_login,
            placeholder_text="네이버 ID",
            corner_radius=10,
            height=48,
            font=IOS_FONT_REGULAR,
            fg_color=IOS_COLORS["input_bg"],
            border_width=0,
        )
        self.entry_id.pack(fill="x", padx=20, pady=(0, 10))

        self.entry_pw = ctk.CTkEntry(
            self.frame_login,
            placeholder_text="비밀번호",
            show="*",
            corner_radius=10,
            height=48,
            font=IOS_FONT_REGULAR,
            fg_color=IOS_COLORS["input_bg"],
            border_width=0,
        )
        self.entry_pw.pack(fill="x", padx=20, pady=(0, 20))

        self.btn_login = ctk.CTkButton(
            self.frame_login,
            text="로그인",
            command=self.on_login,
            fg_color=IOS_COLORS["primary"],
            hover_color="#0051D5",
            corner_radius=12,
            height=50,
            font=("SF Pro Text", 16, "bold"),
        )
        self.btn_login.pack(fill="x", padx=20, pady=(0, 20))

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

        # 내 블로그 ID
        blog_id_row = ctk.CTkFrame(self.frame_settings, fg_color="transparent")
        blog_id_row.pack(fill="x", padx=20, pady=(0, 10))
        ctk.CTkLabel(blog_id_row, text="내 블로그 ID", font=IOS_FONT_REGULAR, text_color=IOS_COLORS["text_primary"]).pack(side="left")
        self.entry_blog_id = ctk.CTkEntry(
            blog_id_row, placeholder_text="블로그 ID", width=160, corner_radius=10, height=40,
            font=IOS_FONT_REGULAR, justify="center", fg_color=IOS_COLORS["input_bg"], border_width=0,
        )
        self.entry_blog_id.pack(side="right")

        # 내 닉네임
        nickname_row = ctk.CTkFrame(self.frame_settings, fg_color="transparent")
        nickname_row.pack(fill="x", padx=20, pady=(0, 10))
        ctk.CTkLabel(nickname_row, text="내 닉네임", font=IOS_FONT_REGULAR, text_color=IOS_COLORS["text_primary"]).pack(side="left")
        self.entry_nickname = ctk.CTkEntry(
            nickname_row, placeholder_text="닉네임", width=160, corner_radius=10, height=40,
            font=IOS_FONT_REGULAR, justify="center", fg_color=IOS_COLORS["input_bg"], border_width=0,
        )
        self.entry_nickname.pack(side="right")

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

        self.browser_center_container = ctk.CTkFrame(self.browser_placeholder, fg_color="transparent", corner_radius=0)
        self.browser_center_container.grid(row=0, column=0, sticky="")

        ctk.CTkLabel(self.browser_center_container, text="🌐", font=("SF Pro Display", 72), width=100, height=100).pack(pady=(50, 24))

        self.lbl_browser_placeholder = ctk.CTkLabel(
            self.browser_center_container, text="브라우저 화면",
            font=("SF Pro Display", 26, "bold"), text_color=IOS_COLORS["text_primary"],
        )
        self.lbl_browser_placeholder.pack(pady=(0, 14))

        ctk.CTkLabel(
            self.browser_center_container, text="크롬 창이 이 영역에\n자동으로 배치됩니다",
            font=IOS_FONT_REGULAR, text_color=IOS_COLORS["text_secondary"], justify="center",
        ).pack(pady=(0, 50))

        # GUI 창 이동 감지
        self._last_position = None
        self._position_update_thread = None
        self._last_update_time = 0
        self._update_throttle = 0.5
        self.bind("<Configure>", self._on_window_move)

        # config에서 값 복원
        self._load_from_config()
        self.log_msg("프로그램 준비 완료.")

    # ------------------------------------------------------------------
    # config 로드/저장
    # ------------------------------------------------------------------
    def _load_from_config(self):
        """config에서 GUI 필드 복원."""
        blog_id = self.config.get("my_blog_id")
        if blog_id:
            self.entry_blog_id.insert(0, blog_id)

        nickname = self.config.get("my_nickname")
        if nickname:
            self.entry_nickname.insert(0, nickname)

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
        self.config.set("my_blog_id", self.entry_blog_id.get().strip())
        self.config.set("my_nickname", self.entry_nickname.get().strip())
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
        if "연결됨" in status or "완료" in status:
            if self.embed_browser_windows:
                self.browser_center_container.grid_remove()
            else:
                self.browser_placeholder.grid_remove()

    def update_browser_status(self, status, color="gray"):
        if threading.current_thread() is threading.main_thread():
            self._do_update_browser_status(status, color)
        else:
            self.after(0, self._do_update_browser_status, status, color)

    def get_browser_embed_hwnd(self):
        """Windows에서 브라우저 임베드 대상 HWND 반환."""
        self.update_idletasks()
        return int(self.browser_placeholder.winfo_id())

    # ------------------------------------------------------------------
    # 이벤트 핸들러
    # ------------------------------------------------------------------
    def _on_window_move(self, event):
        if event.widget != self:
            return
        current_time = time.time()
        if current_time - self._last_update_time < self._update_throttle:
            return
        try:
            current_x = self.winfo_x()
            current_y = self.winfo_y()
        except Exception:
            return
        if self._last_position and self._last_position == (current_x, current_y):
            return
        self._last_position = (current_x, current_y)
        self._last_update_time = current_time
        if self.logic and self.logic.driver:
            if self._position_update_thread is None or not self._position_update_thread.is_alive():
                self._position_update_thread = threading.Thread(target=self._update_chrome_position, daemon=True)
                self._position_update_thread.start()

    def _update_chrome_position(self):
        time.sleep(0.2)
        if self.logic.driver:
            try:
                self.logic._position_chrome_window(self)
            except Exception:
                pass

    def _on_mousewheel(self, event):
        try:
            widget = event.widget
            if widget != self.left_panel and widget != self.scrollable_frame:
                parent = widget
                while parent:
                    if parent == self.left_panel or parent == self.scrollable_frame:
                        break
                    try:
                        parent = parent.master
                    except Exception:
                        break
                else:
                    return

            if platform.system() == "Darwin":
                delta = event.delta
            elif event.num == 4:
                delta = 1
            elif event.num == 5:
                delta = -1
            else:
                delta = event.delta // 120

            if hasattr(self.scrollable_frame, "_parent_canvas"):
                self.scrollable_frame._parent_canvas.yview_scroll(int(-delta), "units")
        except Exception:
            pass

    # ------------------------------------------------------------------
    # 버튼 액션
    # ------------------------------------------------------------------
    def on_login(self):
        uid = self.entry_id.get()
        upw = self.entry_pw.get()
        if not uid or not upw:
            self.log_msg("⚠️ 아이디/비번을 입력하세요.")
            return
        self.btn_login.configure(state="disabled", text="로그인 중...")
        self.update_idletasks()
        self.log_msg("🔐 로그인 시도 중...")
        threading.Thread(target=self._thread_login, args=(uid, upw), daemon=True).start()

    def _thread_login(self, u, p):
        # 로그인 전에 blog_id/nickname 반영
        blog_id = self.entry_blog_id.get().strip()
        nickname = self.entry_nickname.get().strip()
        if blog_id:
            self.logic.my_blog_id = blog_id
        if nickname:
            self.logic.my_nickname = nickname

        if not self.logic.driver:
            if not self.logic.connect_driver():
                self.after(0, lambda: self.btn_login.configure(state="normal", text="로그인"))
                return
        if self.logic.login(u, p):
            self.after(0, lambda: self.btn_login.configure(
                state="normal", text="로그인 완료",
                fg_color=IOS_COLORS["text_secondary"], hover_color=IOS_COLORS["text_secondary"],
            ))
        else:
            self.after(0, lambda: self.btn_login.configure(state="normal", text="로그인"))

    def on_search(self):
        k = self.entry_keyword.get()
        if not k:
            self.log_msg("⚠️ 키워드를 입력하세요.")
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
        if self.logic.is_running:
            self.log_msg("⚠️ 이미 실행 중입니다.")
            return

        keyword = self.entry_keyword.get()
        if not keyword:
            self.log_msg("⚠️ 검색 키워드를 입력하세요.")
            return

        # 블로그 ID 검증
        blog_id = self.entry_blog_id.get().strip()
        if not blog_id:
            self.log_msg("⚠️ 설정에서 '내 블로그 ID'를 입력하세요.")
            return

        # GUI → config → JSON 저장
        self._save_to_config()

        # logic에 최신 설정 반영
        self.logic.my_blog_id = self.config.get("my_blog_id")
        self.logic.my_nickname = self.config.get("my_nickname")

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
