import sys
import time
import random
import threading
import subprocess
import os
import pyperclip

import customtkinter as ctk
from tkinter import messagebox

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import WebDriverException
from webdriver_manager.chrome import ChromeDriverManager

# =============================================================================
# [Logic] 서이추 봇 핵심 로직
# =============================================================================
class NaverBotLogic:
    def __init__(self, log_func, progress_func):
        self.driver = None
        self.is_running = False
        self.log = log_func
        self.update_progress = progress_func
        self.target_count = 100
        self.current_count = 0

    def connect_driver(self, force_restart=False):
        """
        크롬 연결 (좀비 프로세스 방지 로직 추가)
        force_restart=True면 무조건 새로 켭니다.
        """
        # 1. 기존 연결 생존 확인
        if self.driver and not force_restart:
            try:
                # 창 개수를 세어보며 통신 테스트
                _ = self.driver.window_handles
                return True
            except:
                self.log("⚠️ 기존 연결이 끊어졌습니다. 재연결합니다...")
                self.driver = None # 연결 끊기

        # 2. 새로 연결
        self.log("🖥️ 크롬 브라우저 실행 중...")
        try:
            # 이미 켜져있는 디버깅 크롬에 붙기 시도
            chrome_options = Options()
            chrome_options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")
            chrome_options.page_load_strategy = 'eager'
            
            self.driver = webdriver.Chrome(options=chrome_options)
            self.log("✅ 브라우저 연결 성공!")
            return True
        except:
            # 실패 시, 새로 프로세스 실행
            self.log("⚠️ 새 브라우저 창을 엽니다...")
            try:
                if sys.platform == "darwin":
                    subprocess.Popen(['/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', '--remote-debugging-port=9222', '--user-data-dir=/tmp/chrome_debug_temp'])
                else:
                    subprocess.Popen(['C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe', '--remote-debugging-port=9222', '--user-data-dir=C:\\chrometemp'])
                
                time.sleep(3) # 실행 대기
                
                # 다시 연결 시도
                chrome_options = Options()
                chrome_options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")
                chrome_options.page_load_strategy = 'eager'
                self.driver = webdriver.Chrome(options=chrome_options)
                self.log("✅ 새 브라우저 연결 성공!")
                return True
            except Exception as e:
                self.log(f"❌ 실행 실패: {e}\n크롬을 모두 끄고 다시 시도해주세요.")
                self.driver = None
                return False

    def login(self, uid, upw):
        # 로그인 할 때는 확실하게 연결 확인
        if not self.connect_driver(): return
        
        self.log("🌐 네이버 접속 중...")
        try:
            self.driver.get("https://www.naver.com")
            time.sleep(1.0)
            
            if "로그아웃" in self.driver.page_source or "내정보" in self.driver.page_source:
                self.log("✅ 이미 로그인 되어 있습니다!")
                return True

            self.log("🔑 로그인 페이지 이동...")
            self.driver.get("https://nid.naver.com/nidlogin.login")
            
            wait = WebDriverWait(self.driver, 10) # 대기 시간 넉넉하게
            elem_id = wait.until(EC.presence_of_element_located((By.ID, "id")))
            
            cmd_key = Keys.COMMAND if sys.platform == "darwin" else Keys.CONTROL
            
            # ID 입력
            self.log("⌨️ 정보 입력 중...")
            elem_id.click()
            elem_id.send_keys(cmd_key, "a")
            elem_id.send_keys(Keys.DELETE)
            pyperclip.copy(uid)
            elem_id.send_keys(cmd_key, 'v')
            time.sleep(0.5)

            # PW 입력
            elem_pw = self.driver.find_element(By.ID, 'pw')
            elem_pw.click()
            elem_pw.send_keys(cmd_key, "a")
            elem_pw.send_keys(Keys.DELETE)
            pyperclip.copy(upw)
            elem_pw.send_keys(cmd_key, 'v')
            time.sleep(0.5)

            # 로그인 버튼
            self.driver.find_element(By.ID, "log.login").click()
            self.log("⏳ 로그인 처리 중...")
            
            try:
                # URL 변경 감지 (최대 10초)
                WebDriverWait(self.driver, 10).until(EC.url_changes("https://nid.naver.com/nidlogin.login"))
                self.log("✅ 로그인 성공!")
                return True
            except:
                self.log("ℹ️ 2단계 인증이나 캡차가 떴습니다. 직접 해결해주세요.")
                return False
                
        except Exception as e:
            self.log(f"❌ 로그인 에러: {str(e)[:30]}")
            # 에러 나면 드라이버 초기화 (다음 시도 때 새로 연결)
            self.driver = None
            return False

    def search_keyword(self, keyword):
        if not self.connect_driver(): return
        self.log(f"🔍 '{keyword}' 검색 중...")
        try:
            self.driver.get(f"https://search.naver.com/search.naver?where=blog&query={keyword}")
        except:
            self.log("❌ 이동 실패. 브라우저 재연결 필요.")
            self.driver = None

    # --- 봇 유틸리티 ---
    def check_alert(self):
        try:
            WebDriverWait(self.driver, 0.3).until(EC.alert_is_present())
            alert = self.driver.switch_to.alert
            text = alert.text
            alert.accept()
            return text
        except: return None

    def check_html_limit_popup(self):
        try:
            return self.driver.execute_script("""
                var xpath = "//*[contains(text(), '5,000명이 초과') or contains(text(), '이웃수가 5,000명')]";
                var popup = document.evaluate(xpath, document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
                if (popup) {
                    var closeBtn = document.getElementById('_alertLayerClose');
                    if (closeBtn) closeBtn.click();
                    return true;
                }
                return false;
            """)
        except: return False

    def check_layer_popup_loading(self):
        try:
            return self.driver.execute_script("""
                var xpath = "//*[contains(text(), '서로이웃 신청 진행중')]";
                var popup = document.evaluate(xpath, document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
                if (popup) {
                    var cancelBtn = document.evaluate("//button[contains(text(), '취소')] | //a[contains(text(), '취소')]", document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
                    if (cancelBtn) cancelBtn.click();
                    return true;
                }
                return false;
            """)
        except: return False

    def click_neighbor_button_recursive(self):
        try:
            xpath = "//*[contains(text(), '이웃추가')]"
            elements = self.driver.find_elements(By.XPATH, xpath)
            for elem in elements:
                if not elem.is_displayed(): continue
                parent = elem
                clicked = False
                for _ in range(5):
                    tag = parent.tag_name.lower()
                    if tag in ['a', 'button'] or parent.get_attribute("onclick") or parent.get_attribute("role") == "button":
                        self.driver.execute_script("arguments[0].click();", parent)
                        clicked = True
                        break
                    try: parent = parent.find_element(By.XPATH, "..")
                    except: break
                if clicked: return True
                self.driver.execute_script("arguments[0].click();", elem)
                return True
        except: return False
        return False

    def process_neighbor(self, blog_id, message):
        driver = self.driver
        try:
            driver.execute_script("window.open('');")
            driver.switch_to.window(driver.window_handles[-1])
            driver.get(f"https://m.blog.naver.com/{blog_id}")
            time.sleep(1.0)

            if "MobileErrorView" in driver.current_url or "일시적인 오류" in driver.page_source:
                return "BLOCK", "차단 감지(일시적 오류)"

            src = driver.page_source
            if "이웃끊기" in src or ">이웃<" in src or "서로이웃<" in src: return False, "이미 이웃"

            clicked = False
            try:
                btn = driver.find_element(By.CSS_SELECTOR, "[data-click-area*='add']")
                driver.execute_script("arguments[0].click();", btn)
                clicked = True
            except:
                if self.click_neighbor_button_recursive(): clicked = True

            if not clicked: return False, "버튼 못찾음"

            time.sleep(0.5)
            
            if self.check_layer_popup_loading(): return False, "신청 진행중"
            
            alert = self.check_alert()
            if alert: return False, f"알림: {alert}"

            try:
                WebDriverWait(driver, 2.0).until(EC.presence_of_element_located((By.ID, "bothBuddyRadio")))
                res = driver.execute_script("""
                    try {
                        var r = document.getElementById('bothBuddyRadio');
                        var l = document.querySelector("label[for='bothBuddyRadio']");
                        if(!r || !l) return 'NO';
                        if(r.disabled || r.getAttribute('ng-disabled')=='true') return 'BLOCK';
                        l.click(); return 'OK';
                    } catch(e) { return 'ERR'; }
                """)
                if res == 'BLOCK':
                    try: driver.execute_script("document.evaluate(\"//*[text()='취소']\", document, null, 9, null).singleNodeValue.click();")
                    except: pass
                    return False, "서로이웃 막힘"
                if res != 'OK': return False, "옵션 오류"

            except: return False, "로딩 Timeout"

            if "5000" in driver.page_source and "초과" in driver.page_source: return False, "상대 정원 초과"

            try:
                driver.execute_script(f"document.querySelector('textarea').value = '{message}';")
                driver.execute_script("document.evaluate(\"//*[text()='확인']\", document, null, 9, null).singleNodeValue.click();")
            except: return False, "전송 실패"

            try:
                alert = driver.switch_to.alert
                txt = alert.text
                alert.accept()
                if "완료" in txt or "보냈습니다" in txt: return True, "성공"
                if "하루" in txt: return "DONE_DAY", "일일 한도"
                return False, f"결과: {txt}"
            except: pass

            if self.check_html_limit_popup(): return False, "5000명 초과"

            return True, "성공"

        except Exception as e:
            return False, f"Err: {str(e)[:10]}"
        finally:
            try:
                if len(driver.window_handles) > 1: driver.close()
                driver.switch_to.window(driver.window_handles[0])
            except: pass

    def start_working(self, message):
        # 시작 전 강력한 연결 확인
        if not self.connect_driver():
            self.log("❌ 브라우저 연결 실패")
            return

        self.is_running = True
        self.current_count = 0
        self.log("🚀 작업 시작")
        processed = set()
        scroll_try = 0

        while self.is_running:
            if self.current_count >= self.target_count:
                self.log("🎉 목표 달성!")
                break

            ids = []
            try:
                # [핵심 수정] 루프 돌 때마다 브라우저 생존 확인
                _ = self.driver.title
                
                links = self.driver.find_elements(By.TAG_NAME, "a")
                for link in links:
                    href = link.get_attribute("href")
                    if href and "blog.naver.com" in href and "Search" not in h:
                        m = re.search(r'blog\.naver\.com\/([a-zA-Z0-9_-]+)', href)
                        if m: ids.append(m.group(1))
            except Exception:
                self.log("⚠️ 브라우저 연결 끊김! 재연결 시도...")
                self.driver = None # 좀비 객체 삭제
                if not self.connect_driver(): # 재연결 실패시 종료
                    self.log("❌ 재연결 실패. 작업을 중단합니다.")
                    break
                continue # 재연결 성공시 루프 처음으로
            
            new_ids = [x for x in ids if x not in processed]
            
            if not new_ids:
                self.log(f"🔄 스크롤 다운... ({scroll_try})")
                try:
                    self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                    time.sleep(1.5)
                except:
                    self.log("⚠️ 스크롤 실패")
                    break
                scroll_try += 1
                if scroll_try > 5: break
                continue
            
            scroll_try = 0
            self.log(f"🔍 대기열: {len(new_ids)}명")

            for bid in new_ids:
                if not self.is_running: break
                if self.current_count >= self.target_count: break
                
                processed.add(bid)
                
                # 개별 작업 수행
                # 여기서도 연결 끊기면 에러 잡아서 처리
                try:
                    ok, msg = self.process_neighbor(bid, message)
                except Exception:
                    self.log("⚠️ 작업 중 오류 발생. 재연결 확인...")
                    self.driver = None
                    if not self.connect_driver():
                        self.is_running = False
                        break
                    continue

                if ok == "DONE_DAY":
                    self.log(f"⛔ {msg}")
                    self.is_running = False
                    return
                elif ok is True:
                    self.current_count += 1
                    self.log(f"✅ [{self.current_count}] {bid}: {msg}")
                    self.update_progress(self.current_count / self.target_count)
                else:
                    self.log(f"   Pass {bid}: {msg}")
                
                time.sleep(random.uniform(1.0, 1.8))
            
        self.is_running = False
        self.log("🏁 작업 종료")


# =============================================================================
# [UI] Modern CustomTkinter GUI
# =============================================================================
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("네이버 블로그 서이추 Pro")
        self.geometry("400x700")
        self.resizable(False, False)

        self.logic = NaverBotLogic(self.log_msg, self.update_prog)

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(5, weight=1)

        # 1. 타이틀
        self.lbl_title = ctk.CTkLabel(self, text="NAVER NEIGHBOR PRO", font=("Arial Bold", 20))
        self.lbl_title.grid(row=0, column=0, padx=20, pady=(20, 0))

        self.lbl_credit = ctk.CTkLabel(self, text="made by ysh", font=("Arial", 10), text_color="gray")
        self.lbl_credit.grid(row=1, column=0, padx=20, pady=(0, 10), sticky="n")

        # 2. 로그인 프레임
        self.frame_login = ctk.CTkFrame(self)
        self.frame_login.grid(row=2, column=0, padx=20, pady=10, sticky="ew")
        
        self.entry_id = ctk.CTkEntry(self.frame_login, placeholder_text="네이버 ID")
        self.entry_id.pack(fill="x", padx=15, pady=(15, 5))
        
        self.entry_pw = ctk.CTkEntry(self.frame_login, placeholder_text="비밀번호", show="*")
        self.entry_pw.pack(fill="x", padx=15, pady=5)
        
        self.btn_login = ctk.CTkButton(self.frame_login, text="접속 및 로그인", command=self.on_login)
        self.btn_login.pack(fill="x", padx=15, pady=(5, 15))

        # 3. 검색 프레임
        self.frame_search = ctk.CTkFrame(self)
        self.frame_search.grid(row=3, column=0, padx=20, pady=5, sticky="ew")
        self.frame_search.grid_columnconfigure(0, weight=1)
        
        self.entry_keyword = ctk.CTkEntry(self.frame_search, placeholder_text="검색 키워드 (예: 주식)")
        self.entry_keyword.grid(row=0, column=0, padx=(15, 5), pady=15, sticky="ew")
        
        self.btn_search = ctk.CTkButton(self.frame_search, text="이동", width=60, command=self.on_search)
        self.btn_search.grid(row=0, column=1, padx=(5, 15), pady=15)

        # 4. 메시지 및 실행
        self.frame_msg = ctk.CTkFrame(self)
        self.frame_msg.grid(row=4, column=0, padx=20, pady=5, sticky="ew")

        self.lbl_msg = ctk.CTkLabel(self.frame_msg, text="신청 메시지:", font=("Arial", 12))
        self.lbl_msg.pack(anchor="w", padx=15, pady=(10, 0))

        self.txt_msg = ctk.CTkTextbox(self.frame_msg, height=80)
        self.txt_msg.pack(fill="x", padx=15, pady=5)
        self.txt_msg.insert("1.0", "블로그 글이 너무 좋아서 이웃 신청합니다! 소통해요 :)")

        self.btn_start = ctk.CTkButton(self.frame_msg, text="▶ 작업 시작", fg_color="green", hover_color="darkgreen", command=self.on_start)
        self.btn_start.pack(fill="x", padx=15, pady=(5, 5))

        self.btn_stop = ctk.CTkButton(self.frame_msg, text="⏹ 작업 정지", fg_color="red", hover_color="darkred", command=self.on_stop)
        self.btn_stop.pack(fill="x", padx=15, pady=(0, 15))

        # 5. 진행률
        self.progressbar = ctk.CTkProgressBar(self)
        self.progressbar.grid(row=5, column=0, padx=20, pady=10, sticky="ew")
        self.progressbar.set(0)

        # 6. 로그창
        self.txt_log = ctk.CTkTextbox(self, state="disabled", font=("Consolas", 11))
        self.txt_log.grid(row=6, column=0, padx=20, pady=(0, 20), sticky="nsew")
        self.log_msg("프로그램 준비 완료.")

    def log_msg(self, msg):
        self.txt_log.configure(state="normal")
        self.txt_log.insert("end", f"{msg}\n")
        self.txt_log.see("end")
        self.txt_log.configure(state="disabled")

    def update_prog(self, val):
        self.progressbar.set(val)

    def on_login(self):
        uid = self.entry_id.get()
        upw = self.entry_pw.get()
        if not uid or not upw:
            self.log_msg("⚠️ 아이디/비번을 입력하세요.")
            return
        
        self.btn_login.configure(state="disabled", text="접속 중...")
        threading.Thread(target=self._thread_login, args=(uid, upw), daemon=True).start()

    def _thread_login(self, u, p):
        if not self.logic.driver:
            if not self.logic.connect_driver():
                self.btn_login.configure(state="normal", text="접속 및 로그인")
                return
        
        if self.logic.login(u, p):
            self.btn_login.configure(state="normal", text="로그인 완료", fg_color="gray")
        else:
            self.btn_login.configure(state="normal", text="접속 및 로그인")

    def on_search(self):
        k = self.entry_keyword.get()
        if not k:
            self.log_msg("⚠️ 키워드를 입력하세요.")
            return
        threading.Thread(target=self._thread_search, args=(k,), daemon=True).start()

    def _thread_search(self, k):
        if not self.logic.driver: self.logic.connect_driver()
        self.logic.search_keyword(k)

    def on_start(self):
        if self.logic.is_running:
            self.log_msg("⚠️ 이미 실행 중입니다.")
            return
        m = self.txt_msg.get("1.0", "end").strip()
        if not m:
            self.log_msg("⚠️ 메시지를 입력하세요.")
            return
        threading.Thread(target=self._thread_start, args=(m,), daemon=True).start()

    def _thread_start(self, m):
        if not self.logic.driver: self.logic.connect_driver()
        self.logic.start_working(m)

    def on_stop(self):
        if self.logic.is_running:
            self.logic.is_running = False
            self.log_msg("🛑 정지 요청됨...")
        else:
            self.log_msg("실행 중 아님")

if __name__ == "__main__":
    app = App()
    app.mainloop()