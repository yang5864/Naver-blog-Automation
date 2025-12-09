import sys
import time
import random
import re
import threading
import subprocess
import os
import platform
import pyperclip

import customtkinter as ctk
from tkinter import messagebox
try:
    from AppKit import NSWindow, NSApplication
    MAC_AVAILABLE = True
except:
    MAC_AVAILABLE = False

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    WebDriverException,
    NoSuchElementException,
    StaleElementReferenceException
)
from selenium.webdriver.common.action_chains import ActionChains

# =============================================================================
# [Logic] 서이추 봇 핵심 로직 (seoichu_BackGround.py 통합)
# =============================================================================
class NaverBotLogic:
    def __init__(self, log_func, progress_func, status_func, gui_window=None):
        self.driver = None
        self.is_running = False
        self.log = log_func
        self.update_progress = progress_func
        self.update_status = status_func
        self.gui_window = gui_window  # GUI 창 참조 저장
        self.target_count = 100
        self.current_count = 0
        self.my_blog_id = "yang5864"
        self.my_nickname = "알잘도"
        self.neighbor_msg = "블로그 스타일이 너무 좋아요! 저도 다양한 주제로 글 쓰고 있어서 함께 소통하면 좋을 것 같아 이웃 신청드립니다:)"
        self.comment_msg = "안녕하세요! 포스팅 잘 보고 갑니다. 좋은 하루 보내세요~"
        
        # 성능 설정
        self.page_load_timeout = 15
        self.element_wait_timeout = 5
        self.fast_wait = 0.2  # 더 빠른 처리
        self.normal_wait = 0.5  # 더 빠른 처리
        self.slow_wait = 1.0    # 더 빠른 처리

    def safe_sleep(self, seconds):
        if seconds > 0:
            time.sleep(seconds)

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
            except:
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
        except:
            return None

    def safe_click(self, driver, element):
        try:
            driver.execute_script("arguments[0].click();", element)
            return True
        except:
            try:
                element.click()
                return True
            except:
                return False

    def connect_driver(self, force_restart=False):
        """크롬 연결 (GUI 오른쪽 패널 위치에 배치)"""
        if self.driver and not force_restart:
            try:
                _ = self.driver.window_handles
                # GUI 위치에 맞춰 크롬 창 위치 조정
                if self.gui_window:
                    self._position_chrome_window(self.gui_window)
                return True
            except:
                self.log("⚠️ 기존 연결이 끊어졌습니다. 재연결합니다...")
                self.driver = None

        self.log("🖥️ 크롬 브라우저 실행 중...")
        try:
            # 디버깅 모드 크롬에 연결 시도
            chrome_options = Options()
            chrome_options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")
            chrome_options.page_load_strategy = 'eager'
            
            self.driver = webdriver.Chrome(options=chrome_options)
            self.driver.set_page_load_timeout(self.page_load_timeout)
            
            # GUI 오른쪽 패널 위치에 크롬 창 배치
            if self.gui_window:
                self._position_chrome_window(self.gui_window)
            
            self.log("✅ 브라우저 연결 성공!")
            self.update_status("브라우저 연결됨", "green")
            return True
        except:
            # 새로 프로세스 실행
            self.log("⚠️ 새 브라우저 창을 엽니다...")
            try:
                user_data_dir = os.path.expanduser("~/ChromeBotData")
                chrome_path = self.get_chrome_path()
                
                # GUI 위치 계산
                if self.gui_window:
                    self.gui_window.update_idletasks()
                    gui_x = self.gui_window.winfo_x()
                    gui_y = self.gui_window.winfo_y()
                    gui_width = self.gui_window.winfo_width()
                    gui_height = self.gui_window.winfo_height()
                    left_panel_width = 420
                    padding_x = 15  # 오른쪽 패널 하얀색 카드 패딩 (크롬 창 크기를 키우기 위해 축소)
                    padding_y = 0   # 높이는 GUI와 동일하게
                    chrome_x = gui_x + left_panel_width + padding_x  # 하얀색 카드 영역 시작
                    chrome_y = gui_y + padding_y
                    chrome_width = gui_width - left_panel_width - (padding_x * 2)
                    chrome_height = gui_height
                else:
                    chrome_x, chrome_y = 800, 0
                    chrome_width = 1000
                    chrome_height = 900
                
                cmd = [
                    chrome_path,
                    "--remote-debugging-port=9222",
                    f"--user-data-dir={user_data_dir}",
                    "--no-first-run",
                    "--no-default-browser-check",
                    f"--window-size={chrome_width},{chrome_height}",
                    f"--window-position={chrome_x},{chrome_y}",
                    "--disable-blink-features=AutomationControlled",
                ]
                
                subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                time.sleep(2.5)  # 크롬 시작 대기 (약간 단축)
                
                chrome_options = Options()
                chrome_options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")
                chrome_options.page_load_strategy = 'eager'
                self.driver = webdriver.Chrome(options=chrome_options)
                self.driver.set_page_load_timeout(self.page_load_timeout)
                
                # GUI 위치에 맞춰 크롬 창 위치 조정
                if self.gui_window:
                    self._position_chrome_window(self.gui_window)
                
                self.log("✅ 새 브라우저 연결 성공!")
                self.update_status("브라우저 연결됨", "green")
                return True
            except Exception as e:
                self.log(f"❌ 실행 실패: {e}")
                self.driver = None
                self.update_status("브라우저 연결 실패", "red")
                return False
    
    def _position_chrome_window(self, gui_window=None):
        """크롬 창을 GUI 오른쪽 패널 하얀색 카드 영역에 정확히 배치"""
        if not self.driver:
            return
        
        if not gui_window:
            gui_window = self.gui_window
        
        if not gui_window:
            return
        
        try:
            # GUI 창 위치와 크기 가져오기
            gui_window.update_idletasks()
            gui_x = gui_window.winfo_x()
            gui_y = gui_window.winfo_y()
            gui_width = gui_window.winfo_width()
            gui_height = gui_window.winfo_height()
            
            # 왼쪽 패널 너비 (고정값)
            left_panel_width = 420
            
            # 오른쪽 패널 하얀색 카드 패딩 (크롬 창 크기를 키우기 위해 패딩 축소)
            padding_x = 15  # 30 -> 15로 줄여서 크롬 창 더 넓게
            padding_y = 0   # 높이는 GUI와 동일하게
            
            # 크롬 창 위치 계산 (하얀색 카드 영역에 맞춤)
            chrome_x = gui_x + left_panel_width + padding_x
            chrome_y = gui_y + padding_y
            
            # 크롬 창 크기 (하얀색 카드 영역 크기에 맞춤, 높이는 GUI와 동일)
            chrome_width = gui_width - left_panel_width - (padding_x * 2)
            chrome_height = gui_height
            
            # 크롬 창 위치 및 크기 설정
            self.driver.set_window_position(chrome_x, chrome_y)
            self.driver.set_window_size(chrome_width, chrome_height)
        except Exception as e:
            self.log(f"⚠️ 창 위치 조정 실패: {str(e)[:30]}")

    def get_chrome_path(self):
        if platform.system() == "Darwin":
            return "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
        elif platform.system() == "Windows":
            return r"C:\Program Files\Google\Chrome\Application\chrome.exe"
        else:
            return "/usr/bin/google-chrome"

    def check_login_status(self):
        """로그인 상태 확인"""
        if not self.driver:
            return False
        
        try:
            if not self.safe_get(self.driver, f"https://m.blog.naver.com/{self.my_blog_id}"):
                return False
            self.safe_sleep(1.0)  # 2.0 -> 1.0으로 단축
            
            page_source = self.driver.page_source
            current_url = self.driver.current_url
            
            if "nidlogin" in current_url or "login" in current_url.lower():
                return False
            
            if "글쓰기" in page_source or "write" in page_source.lower():
                return True
            
            cookies = self.driver.get_cookies()
            for cookie in cookies:
                if cookie.get('name') in ["NID_AUT", "NID_SES"]:
                    return True
            
            return False
        except:
            return False

    def login(self, uid, upw):
        if not self.connect_driver():
            return False
        
        self.log("🌐 네이버 접속 중...")
        try:
            self.driver.get("https://www.naver.com")
            self.safe_sleep(0.5)  # 1.0 -> 0.5로 단축
            
            if self.check_login_status():
                self.log("✅ 이미 로그인 되어 있습니다!")
                self.update_status("로그인 완료", "green")
                return True

            self.log("🔑 로그인 페이지 이동...")
            self.driver.get("https://nid.naver.com/nidlogin.login")
            
            wait = WebDriverWait(self.driver, 10)
            elem_id = wait.until(EC.presence_of_element_located((By.ID, "id")))
            
            cmd_key = Keys.COMMAND if sys.platform == "darwin" else Keys.CONTROL
            
            self.log("⌨️ 정보 입력 중...")
            elem_id.click()
            elem_id.send_keys(cmd_key, "a")
            elem_id.send_keys(Keys.DELETE)
            pyperclip.copy(uid)
            elem_id.send_keys(cmd_key, 'v')
            self.safe_sleep(0.2)  # 0.5 -> 0.2로 단축

            elem_pw = self.driver.find_element(By.ID, 'pw')
            elem_pw.click()
            elem_pw.send_keys(cmd_key, "a")
            elem_pw.send_keys(Keys.DELETE)
            pyperclip.copy(upw)
            elem_pw.send_keys(cmd_key, 'v')
            self.safe_sleep(0.2)  # 0.5 -> 0.2로 단축

            self.driver.find_element(By.ID, "log.login").click()
            self.log("⏳ 로그인 처리 중...")
            
            try:
                WebDriverWait(self.driver, 10).until(EC.url_changes("https://nid.naver.com/nidlogin.login"))
                self.log("✅ 로그인 성공!")
                self.update_status("로그인 완료", "green")
                return True
            except:
                self.log("ℹ️ 2단계 인증이나 캡차가 떴습니다. 직접 해결해주세요.")
                self.update_status("인증 필요", "orange")
                return False
        except Exception as e:
            self.log(f"❌ 로그인 에러: {str(e)[:30]}")
            self.driver = None
            self.update_status("로그인 실패", "red")
            return False

    def search_keyword(self, keyword):
        if not self.connect_driver():
            return
        self.log(f"🔍 '{keyword}' 검색 중...")
        try:
            search_url = f"https://search.naver.com/search.naver?where=blog&query={keyword}"
            if not self.safe_get(self.driver, search_url):
                self.log("❌ 검색 페이지 이동 실패")
                return
            self.safe_sleep(1.0)  # 2.0 -> 1.0으로 단축
            
            # 블로그 탭 클릭
            try:
                blog_tab = None
                tabs = self.driver.find_elements(By.CSS_SELECTOR, "[role='tab'], .tab, .lnb_item a")
                for tab in tabs:
                    try:
                        if "블로그" in tab.text:
                            blog_tab = tab
                            break
                    except:
                        continue
                
                if not blog_tab:
                    blog_tab = self.driver.find_element(By.XPATH, "//a[contains(text(), '블로그')]")
                
                if blog_tab:
                    self.log("   ↪ '블로그' 탭 클릭...")
                    self.safe_click(self.driver, blog_tab)
                    self.safe_sleep(1.0)  # 2.0 -> 1.0으로 단축
            except:
                pass
            
            self.update_status(f"검색: {keyword}", "blue")
        except:
            self.log("❌ 이동 실패. 브라우저 재연결 필요.")
            self.driver = None

    def collect_blog_ids(self, processed_ids):
        """블로그 ID 수집"""
        queue = []
        blacklist = {"myblog", "postlist", "buddyaddform", "likeit", "nvisitor", "blog", "domainid", "admin", "search"}
        my_id_clean = self.my_blog_id.strip().lower()
        
        scroll_attempts = 0
        max_scroll = 7
        
        while len(queue) < 20 and scroll_attempts < max_scroll:
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            self.safe_sleep(1.0)  # 2.0 -> 1.0으로 단축
            
            new_count = 0
            try:
                all_links = self.driver.find_elements(By.TAG_NAME, "a")
                
                for link in all_links:
                    try:
                        href = link.get_attribute("href")
                        if not href or "blog.naver.com" not in href:
                            continue
                        
                        match = re.search(r'blog\.naver\.com\/([a-zA-Z0-9_-]+)', href)
                        if not match:
                            continue
                        
                        bid = match.group(1)
                        bid_lower = bid.lower()
                        
                        if bid_lower in blacklist or bid_lower == my_id_clean:
                            continue
                        if bid in processed_ids or len(bid) <= 3:
                            continue
                        if bid in queue or bid.isdigit():
                            continue
                        
                        queue.append(bid)
                        processed_ids.add(bid)
                        new_count += 1
                    except:
                        continue
            except:
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
                        self.safe_sleep(0.8)  # 1.5 -> 0.8로 단축
                except:
                    pass
        
        return queue

    def process_neighbor(self, blog_id):
        """서로이웃 신청 처리"""
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
            except:
                try:
                    if driver.find_elements(By.CSS_SELECTOR, "[data-click-area='ebc.ngr']"):
                        return False, "스킵(이미 이웃)"
                    btn = driver.find_element(By.XPATH, "//*[contains(text(), '이웃추가')]")
                    self.safe_click(driver, btn)
                    clicked = True
                except:
                    pass

            if not clicked:
                return False, "스킵(버튼 없음)"

            self.safe_sleep(0.3)  # 1.0 -> 0.3으로 단축

            src_after = driver.page_source
            if "하루에 신청 가능한 이웃수" in src_after and "초과" in src_after:
                try:
                    close_btn = driver.find_element(By.XPATH, "//button[contains(text(), '닫기')]")
                    self.safe_click(driver, close_btn)
                except:
                    pass
                return "DONE_DAY_LIMIT", "🎉 일일 한도 달성!"

            if "서로이웃 신청 진행중입니다" in src_after:
                try:
                    cancel_btns = driver.find_elements(By.XPATH, "//button[contains(text(), '취소')]")
                    for btn in cancel_btns:
                        if btn.is_displayed():
                            self.safe_click(driver, btn)
                            self.safe_sleep(0.1)  # 0.2 -> 0.1로 단축
                            return False, "스킵(이미 신청중)"
                except:
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
                except:
                    pass
                if "5,000" in layer_popup or "5000" in layer_popup:
                    return False, "스킵(상대 5000명)"
                return False, f"스킵({layer_popup[:20]})"

            current_url = driver.current_url
            if "BuddyAddForm" not in current_url:
                if not self.safe_get(driver, f"https://m.blog.naver.com/BuddyAddForm.naver?blogId={blog_id}"):
                    return False, "실패(양식 페이지 로드 실패)"
                self.safe_sleep(1.0)  # 2.0 -> 1.0으로 단축
            
            page_src = driver.page_source
            if "로그인" in page_src and "로그인이 필요" in page_src:
                return False, "실패(로그인 필요)"
            
            try:
                self.safe_sleep(0.2)  # 0.5 -> 0.2로 단축
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
                
                if result == 'DISABLED':
                    return False, "스킵(서이추 불가)"
                if result and result.startswith('ERROR'):
                    return False, f"실패({result})"
            except Exception as e:
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
            except:
                pass

            try:
                confirm_btn = driver.find_element(By.XPATH, "//*[text()='확인']")
                self.safe_click(driver, confirm_btn)
                self.safe_sleep(self.fast_wait)
            except:
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
                except:
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
            except:
                return True, "신청 완료"

        except Exception as e:
            return False, f"에러: {str(e)[:15]}"

    def process_like(self, driver):
        """공감 버튼 클릭"""
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
            except:
                self.safe_click(driver, wrapper)
                return "공감 ❤️"
        except:
            return "공감 실패"

    def process_comment(self, driver, blog_id):
        """댓글 작성"""
        try:
            comment_btn = self.safe_find_element(
                driver, By.CSS_SELECTOR, "button[class*='comment_btn'], a.btn_comment", timeout=3
            )
            if not comment_btn:
                return "댓글 버튼 없음"
            
            self.safe_click(driver, comment_btn)
            self.safe_sleep(self.normal_wait)

            try:
                existing_nicks = driver.find_elements(By.CSS_SELECTOR, "span.u_cbox_nick")
                for nick_el in existing_nicks:
                    if self.my_nickname == nick_el.text.strip():
                        return f"스킵(이미 댓글 씀)"
            except:
                pass

            input_box = self.safe_find_element(
                driver, By.CSS_SELECTOR, ".u_cbox_text_mention, .u_cbox_inbox textarea", timeout=3
            )
            if not input_box:
                return "입력창 없음"

            target_nickname = blog_id
            try:
                name_el = driver.find_element(By.CSS_SELECTOR, ".user_name, .blogger_name")
                target_nickname = name_el.text.strip() or blog_id
            except:
                pass

            final_msg = self.comment_msg.format(name=target_nickname)
            try:
                ActionChains(driver).move_to_element(input_box).click().send_keys(final_msg).perform()
            except:
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
            except:
                pass

            self.safe_sleep(self.normal_wait)
            return "댓글 💬"
        except:
            return "댓글 실패"

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
        
        # 검색 페이지로 이동
        search_url = f"https://search.naver.com/search.naver?where=blog&query={keyword}"
        if not self.safe_get(self.driver, search_url):
            self.log("❌ 검색 페이지 로드 실패")
            return
        self.safe_sleep(1.0)  # 2.0 -> 1.0으로 단축
        
        # 블로그 탭 클릭
        try:
            blog_tab = None
            tabs = self.driver.find_elements(By.CSS_SELECTOR, "[role='tab'], .tab, .lnb_item a")
            for tab in tabs:
                try:
                    if "블로그" in tab.text:
                        blog_tab = tab
                        break
                except:
                    continue
            
            if not blog_tab:
                blog_tab = self.driver.find_element(By.XPATH, "//a[contains(text(), '블로그')]")
            
            if blog_tab:
                self.log("   ↪ '블로그' 탭 클릭...")
                self.safe_click(self.driver, blog_tab)
                self.safe_sleep(1.0)  # 2.0 -> 1.0으로 단축
        except:
            pass
        
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
                except:
                    self.log("❌ 메인 탭 접근 불가")
                    break
                
                queue = self.collect_blog_ids(processed_ids)
                
                if not queue:
                    self.log("⚠️ 더 이상 수집할 블로그가 없습니다.")
                    break
                
                self.log(f"   ✅ {len(queue)}명 수집 완료!")

            blog_id = queue.pop(0)
            blacklist = {"myblog", "postlist", "buddyaddform", "likeit", "nvisitor", "blog", "domainid", "admin", "search"}
            if blog_id.lower() == self.my_blog_id.lower() or blog_id.lower() in blacklist:
                continue

            self.log(f"\n▶️ [{self.current_count+1}/{self.target_count}] '{blog_id}' 작업 시작")
            
            try:
                self.driver.switch_to.new_window('tab')
                if not self.safe_get(self.driver, f"https://m.blog.naver.com/{blog_id}"):
                    self.log("   ❌ 페이지 로드 실패")
                    try:
                        if len(self.driver.window_handles) > 1:
                            self.driver.close()
                        self.driver.switch_to.window(main_window)
                    except:
                        pass
                    consecutive_errors += 1
                    if consecutive_errors >= 5:
                        self.log("⚠️ 연속 5회 실패. 잠시 대기...")
                        self.safe_sleep(5.0)
                        consecutive_errors = 0
                    continue
            except Exception as e:
                self.log(f"   ⚠️ 탭 열기 실패: {str(e)[:20]}")
                try:
                    if len(self.driver.window_handles) > 1:
                        self.driver.close()
                    self.driver.switch_to.window(main_window)
                except:
                    pass
                continue

            self.safe_sleep(1.5)
            consecutive_errors = 0

            current_url = self.driver.current_url
            page_source = self.driver.page_source
            
            if "MobileErrorView" in current_url or "일시적인 오류" in page_source:
                self.log(f"   ❌ 접근 불가 블로그 (Skip)")
                try:
                    if len(self.driver.window_handles) > 1:
                        self.driver.close()
                    self.driver.switch_to.window(main_window)
                except:
                    pass
                continue

            is_friend, msg_friend = self.process_neighbor(blog_id)
            
            if is_friend == "DONE_DAY_LIMIT":
                self.log(f"\n🎉 목표 달성! 오늘 할당량을 모두 채웠습니다!")
                try:
                    if len(self.driver.window_handles) > 1:
                        self.driver.close()
                    self.driver.switch_to.window(main_window)
                except:
                    pass
                break
                
            if is_friend == "STOP_GROUP_FULL":
                self.log(f"\n⛔ 내 이웃 그룹이 가득 찼습니다.")
                try:
                    if len(self.driver.window_handles) > 1:
                        self.driver.close()
                    self.driver.switch_to.window(main_window)
                except:
                    pass
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

            try:
                if len(self.driver.window_handles) > 1:
                    self.driver.close()
                self.driver.switch_to.window(main_window)
            except:
                pass

            wait_time = random.uniform(0.8, 1.5)
            self.safe_sleep(wait_time)
        
        self.is_running = False
        self.log("🏁 작업 종료")
        self.update_status("작업 완료", "green")


# =============================================================================
# [UI] iOS 스타일 GUI
# =============================================================================
ctk.set_appearance_mode("Light")  # iOS는 밝은 모드
ctk.set_default_color_theme("blue")

# iOS 스타일 색상 (더 세련된 팔레트)
IOS_COLORS = {
    "background": "#F5F5F7",  # 더 부드러운 배경색
    "card": "#FFFFFF",  # 카드 배경
    "primary": "#007AFF",  # iOS 파란색
    "secondary": "#5856D6",  # 보라색
    "success": "#34C759",  # 초록색
    "danger": "#FF3B30",  # 빨간색
    "text_primary": "#1D1D1F",  # 더 부드러운 검정
    "text_secondary": "#86868B",  # 더 부드러운 회색
    "separator": "#D2D2D7",
    "input_bg": "#F5F5F7",  # 입력 필드 배경
}

# iOS 스타일 폰트 (CustomTkinter는 튜플 형식만 지원)
IOS_FONT_LARGE = ("SF Pro Display", 28, "bold")
IOS_FONT_MEDIUM = ("SF Pro Display", 17, "bold")
IOS_FONT_REGULAR = ("SF Pro Text", 15)
IOS_FONT_SMALL = ("SF Pro Text", 13)
IOS_FONT_MONO = ("SF Mono", 11)

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("네이버 블로그 서이추 Pro")
        self.geometry("1600x900")
        self.resizable(True, True)
        
        # iOS 스타일 배경색
        self.configure(fg_color=IOS_COLORS["background"])

        self.logic = NaverBotLogic(self.log_msg, self.update_prog, self.update_browser_status, gui_window=self)

        # 좌우 분할 레이아웃
        self.grid_columnconfigure(0, weight=0)  # 왼쪽 패널 (고정 너비)
        self.grid_columnconfigure(1, weight=1)   # 오른쪽 패널 (확장)
        self.grid_rowconfigure(0, weight=1)

        # ========== 왼쪽 패널 (컨트롤) ==========
        self.left_panel = ctk.CTkFrame(
            self, 
            width=420,
            fg_color=IOS_COLORS["background"],
            corner_radius=0
        )
        self.left_panel.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)
        self.left_panel.grid_propagate(False)
        self.left_panel.grid_columnconfigure(0, weight=1)
        self.left_panel.grid_rowconfigure(1, weight=1)  # 스크롤 영역에 weight 부여

        # 헤더 영역 (iOS 스타일) - 고정
        header_frame = ctk.CTkFrame(
            self.left_panel,
            fg_color=IOS_COLORS["background"],
            corner_radius=0,
            height=100
        )
        header_frame.grid(row=0, column=0, sticky="ew", padx=0, pady=0)
        header_frame.grid_propagate(False)
        
        # 타이틀 (iOS 스타일 큰 폰트)
        self.lbl_title = ctk.CTkLabel(
            header_frame, 
            text="서이추 Pro", 
            font=IOS_FONT_LARGE,
            text_color=IOS_COLORS["text_primary"]
        )
        self.lbl_title.pack(pady=(28, 4))

        self.lbl_credit = ctk.CTkLabel(
            header_frame, 
            text="made by ysh", 
            font=IOS_FONT_SMALL,
            text_color=IOS_COLORS["text_secondary"]
        )
        self.lbl_credit.pack(pady=(0, 24))

        # 스크롤 가능한 컨텐츠 영역
        self.scrollable_frame = ctk.CTkScrollableFrame(
            self.left_panel,
            fg_color=IOS_COLORS["background"],
            corner_radius=0
        )
        self.scrollable_frame.grid(row=1, column=0, sticky="nsew", padx=0, pady=0)
        self.scrollable_frame.grid_columnconfigure(0, weight=1)
        
        # 마우스 휠 이벤트 바인딩 (스크롤 개선) - 왼쪽 패널에만 적용
        self.left_panel.bind("<MouseWheel>", self._on_mousewheel)
        self.left_panel.bind("<Button-4>", self._on_mousewheel)  # Linux
        self.left_panel.bind("<Button-5>", self._on_mousewheel)  # Linux
        self.scrollable_frame.bind("<MouseWheel>", self._on_mousewheel)
        self.scrollable_frame.bind("<Button-4>", self._on_mousewheel)  # Linux
        self.scrollable_frame.bind("<Button-5>", self._on_mousewheel)  # Linux

        # 로그인 카드 (iOS 스타일)
        self.frame_login = ctk.CTkFrame(
            self.scrollable_frame,
            fg_color=IOS_COLORS["card"],
            corner_radius=16
        )
        self.frame_login.grid(row=0, column=0, padx=20, pady=(20, 12), sticky="ew")
        
        login_title = ctk.CTkLabel(
            self.frame_login,
            text="로그인",
            font=IOS_FONT_MEDIUM,
            text_color=IOS_COLORS["text_primary"]
        )
        login_title.pack(anchor="w", padx=20, pady=(20, 14))
        
        self.entry_id = ctk.CTkEntry(
            self.frame_login,
            placeholder_text="네이버 ID",
            corner_radius=10,
            height=48,
            font=IOS_FONT_REGULAR,
            fg_color=IOS_COLORS["input_bg"],
            border_width=0
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
            border_width=0
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
            font=("SF Pro Text", 16, "bold")
        )
        self.btn_login.pack(fill="x", padx=20, pady=(0, 20))

        # 검색 카드
        self.frame_search = ctk.CTkFrame(
            self.scrollable_frame,
            fg_color=IOS_COLORS["card"],
            corner_radius=16
        )
        self.frame_search.grid(row=1, column=0, padx=20, pady=12, sticky="ew")
        self.frame_search.grid_columnconfigure(0, weight=1)
        
        search_title = ctk.CTkLabel(
            self.frame_search,
            text="검색",
            font=IOS_FONT_MEDIUM,
            text_color=IOS_COLORS["text_primary"]
        )
        search_title.grid(row=0, column=0, columnspan=2, sticky="w", padx=20, pady=(20, 14))
        
        self.entry_keyword = ctk.CTkEntry(
            self.frame_search,
            placeholder_text="검색 키워드",
            corner_radius=10,
            height=48,
            font=IOS_FONT_REGULAR,
            fg_color=IOS_COLORS["input_bg"],
            border_width=0
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
            font=("SF Pro Text", 15, "bold")
        )
        self.btn_search.grid(row=1, column=1, padx=(0, 20), pady=(0, 20))

        # 설정 카드
        self.frame_settings = ctk.CTkFrame(
            self.scrollable_frame,
            fg_color=IOS_COLORS["card"],
            corner_radius=16
        )
        self.frame_settings.grid(row=2, column=0, padx=20, pady=12, sticky="ew")
        
        settings_title = ctk.CTkLabel(
            self.frame_settings,
            text="설정",
            font=IOS_FONT_MEDIUM,
            text_color=IOS_COLORS["text_primary"]
        )
        settings_title.pack(anchor="w", padx=20, pady=(20, 14))
        
        target_row = ctk.CTkFrame(self.frame_settings, fg_color="transparent")
        target_row.pack(fill="x", padx=20, pady=(0, 20))
        
        self.lbl_target = ctk.CTkLabel(
            target_row,
            text="목표 개수",
            font=IOS_FONT_REGULAR,
            text_color=IOS_COLORS["text_primary"]
        )
        self.lbl_target.pack(side="left")
        
        self.entry_target = ctk.CTkEntry(
            target_row,
            placeholder_text="100",
            width=100,
            corner_radius=10,
            height=40,
            font=IOS_FONT_REGULAR,
            justify="center",
            fg_color=IOS_COLORS["input_bg"],
            border_width=0
        )
        self.entry_target.pack(side="right")
        self.entry_target.insert(0, "100")

        # 메시지 카드
        self.frame_msg = ctk.CTkFrame(
            self.scrollable_frame,
            fg_color=IOS_COLORS["card"],
            corner_radius=16
        )
        self.frame_msg.grid(row=3, column=0, padx=20, pady=12, sticky="ew")

        msg_title = ctk.CTkLabel(
            self.frame_msg,
            text="메시지",
            font=IOS_FONT_MEDIUM,
            text_color=IOS_COLORS["text_primary"]
        )
        msg_title.pack(anchor="w", padx=20, pady=(20, 14))

        self.lbl_msg = ctk.CTkLabel(
            self.frame_msg,
            text="서이추 메시지",
            font=IOS_FONT_SMALL,
            text_color=IOS_COLORS["text_secondary"]
        )
        self.lbl_msg.pack(anchor="w", padx=20, pady=(0, 8))

        self.txt_msg = ctk.CTkTextbox(
            self.frame_msg,
            height=75,
            corner_radius=10,
            font=IOS_FONT_SMALL,
            fg_color=IOS_COLORS["input_bg"],
            text_color=IOS_COLORS["text_primary"],
            border_width=0
        )
        self.txt_msg.pack(fill="x", padx=20, pady=(0, 14))
        self.txt_msg.insert("1.0", "블로그 스타일이 너무 좋아요! 저도 다양한 주제로 글 쓰고 있어서 함께 소통하면 좋을 것 같아 이웃 신청드립니다:)")

        self.lbl_cmt = ctk.CTkLabel(
            self.frame_msg,
            text="댓글 메시지",
            font=IOS_FONT_SMALL,
            text_color=IOS_COLORS["text_secondary"]
        )
        self.lbl_cmt.pack(anchor="w", padx=20, pady=(0, 8))

        self.txt_cmt = ctk.CTkTextbox(
            self.frame_msg,
            height=75,
            corner_radius=10,
            font=IOS_FONT_SMALL,
            fg_color=IOS_COLORS["input_bg"],
            text_color=IOS_COLORS["text_primary"],
            border_width=0
        )
        self.txt_cmt.pack(fill="x", padx=20, pady=(0, 20))
        self.txt_cmt.insert("1.0", "안녕하세요! 포스팅 잘 보고 갑니다. 좋은 하루 보내세요~")

        # 액션 버튼 카드
        action_frame = ctk.CTkFrame(
            self.scrollable_frame,
            fg_color=IOS_COLORS["card"],
            corner_radius=16
        )
        action_frame.grid(row=4, column=0, padx=20, pady=12, sticky="ew")

        self.btn_start = ctk.CTkButton(
            action_frame,
            text="작업 시작",
            command=self.on_start,
            fg_color=IOS_COLORS["success"],
            hover_color="#30B350",
            corner_radius=12,
            height=54,
            font=("SF Pro Text", 17, "bold")
        )
        self.btn_start.pack(fill="x", padx=20, pady=(20, 12))

        self.btn_stop = ctk.CTkButton(
            action_frame,
            text="작업 정지",
            command=self.on_stop,
            fg_color=IOS_COLORS["danger"],
            hover_color="#E6342A",
            corner_radius=12,
            height=54,
            font=("SF Pro Text", 17, "bold")
        )
        self.btn_stop.pack(fill="x", padx=20, pady=(0, 20))

        # 진행률 카드
        progress_frame = ctk.CTkFrame(
            self.scrollable_frame,
            fg_color=IOS_COLORS["card"],
            corner_radius=16
        )
        progress_frame.grid(row=5, column=0, padx=20, pady=12, sticky="ew")
        
        progress_title = ctk.CTkLabel(
            progress_frame,
            text="진행 상황",
            font=IOS_FONT_MEDIUM,
            text_color=IOS_COLORS["text_primary"]
        )
        progress_title.pack(anchor="w", padx=20, pady=(20, 14))
        
        self.progressbar = ctk.CTkProgressBar(
            progress_frame,
            progress_color=IOS_COLORS["primary"],
            height=8,
            corner_radius=4
        )
        self.progressbar.pack(fill="x", padx=20, pady=(0, 14))
        self.progressbar.set(0)
        
        # 브라우저 상태
        self.lbl_browser_status = ctk.CTkLabel(
            progress_frame,
            text="브라우저: 대기 중",
            font=IOS_FONT_SMALL,
            text_color=IOS_COLORS["text_secondary"]
        )
        self.lbl_browser_status.pack(anchor="w", padx=20, pady=(0, 20))

        # 로그 카드
        log_frame = ctk.CTkFrame(
            self.scrollable_frame,
            fg_color=IOS_COLORS["card"],
            corner_radius=16
        )
        log_frame.grid(row=6, column=0, padx=20, pady=12, sticky="ew")
        log_frame.grid_columnconfigure(0, weight=1)
        
        log_title = ctk.CTkLabel(
            log_frame,
            text="활동 로그",
            font=IOS_FONT_MEDIUM,
            text_color=IOS_COLORS["text_primary"]
        )
        log_title.grid(row=0, column=0, sticky="w", padx=20, pady=(20, 14))
        
        self.txt_log = ctk.CTkTextbox(
            log_frame,
            state="disabled",
            font=IOS_FONT_MONO,
            fg_color=IOS_COLORS["input_bg"],
            text_color=IOS_COLORS["text_primary"],
            corner_radius=10,
            border_width=0
        )
        self.txt_log.grid(row=1, column=0, padx=20, pady=(0, 20), sticky="nsew")
        self.log_msg("프로그램 준비 완료.")

        # ========== 오른쪽 패널 (브라우저 화면 영역) ==========
        self.right_panel = ctk.CTkFrame(
            self,
            fg_color=IOS_COLORS["background"],
            corner_radius=0
        )
        self.right_panel.grid(row=0, column=1, sticky="nsew", padx=0, pady=0)
        self.right_panel.grid_columnconfigure(0, weight=1)
        self.right_panel.grid_rowconfigure(0, weight=1)

        # 브라우저 화면 안내 (iOS 스타일) - 넓은 영역
        self.browser_placeholder = ctk.CTkFrame(
            self.right_panel,
            fg_color=IOS_COLORS["card"],
            corner_radius=24
        )
        self.browser_placeholder.grid(row=0, column=0, sticky="nsew", padx=30, pady=30)
        self.browser_placeholder.grid_columnconfigure(0, weight=1)
        self.browser_placeholder.grid_rowconfigure(0, weight=1)
        
        # 중앙 정렬을 위한 컨테이너
        center_container = ctk.CTkFrame(
            self.browser_placeholder,
            fg_color="transparent",
            corner_radius=0
        )
        center_container.grid(row=0, column=0, sticky="")
        
        # 아이콘 영역
        icon_label = ctk.CTkLabel(
            center_container,
            text="🌐",
            font=("SF Pro Display", 72),
            width=100,
            height=100
        )
        icon_label.pack(pady=(50, 24))
        
        self.lbl_browser_placeholder = ctk.CTkLabel(
            center_container,
            text="브라우저 화면",
            font=("SF Pro Display", 26, "bold"),
            text_color=IOS_COLORS["text_primary"]
        )
        self.lbl_browser_placeholder.pack(pady=(0, 14))
        
        desc_label = ctk.CTkLabel(
            center_container,
            text="크롬 창이 이 영역에\n자동으로 배치됩니다",
            font=IOS_FONT_REGULAR,
            text_color=IOS_COLORS["text_secondary"],
            justify="center"
        )
        desc_label.pack(pady=(0, 50))
        
        # GUI 창 이동 감지하여 크롬 창도 함께 이동 (throttle 적용)
        self._last_position = None
        self._position_update_thread = None
        self._last_update_time = 0
        self._update_throttle = 0.5  # 최대 0.5초에 한 번만 업데이트
        self.bind('<Configure>', self._on_window_move)

    def log_msg(self, msg):
        self.txt_log.configure(state="normal")
        timestamp = time.strftime("%H:%M:%S")
        self.txt_log.insert("end", f"[{timestamp}] {msg}\n")
        self.txt_log.see("end")
        self.txt_log.configure(state="disabled")

    def update_prog(self, val):
        self.progressbar.set(val)

    def update_browser_status(self, status, color="gray"):
        # iOS 스타일 색상 매핑
        color_map = {
            "green": IOS_COLORS["success"],
            "red": IOS_COLORS["danger"],
            "blue": IOS_COLORS["primary"],
            "orange": "#FF9500",
            "gray": IOS_COLORS["text_secondary"]
        }
        status_color = color_map.get(color, IOS_COLORS["text_secondary"])
        
        self.lbl_browser_status.configure(
            text=f"브라우저: {status}",
            text_color=status_color
        )
        
        # 브라우저 연결되면 안내 메시지 숨기기
        if "연결됨" in status or "완료" in status:
            self.browser_placeholder.grid_remove()
    
    def _on_window_move(self, event):
        """GUI 창 이동 시 크롬 창도 함께 이동 (throttle 적용)"""
        if event.widget != self:
            return
        
        # Throttle: 너무 자주 업데이트하지 않도록 제한
        current_time = time.time()
        if current_time - self._last_update_time < self._update_throttle:
            return
        
        # 창 위치가 실제로 변경되었는지 확인
        try:
            current_x = self.winfo_x()
            current_y = self.winfo_y()
        except:
            return
        
        if self._last_position and self._last_position == (current_x, current_y):
            return
        
        self._last_position = (current_x, current_y)
        self._last_update_time = current_time
        
        # 크롬 창 위치 업데이트 (쓰레드로 처리하여 GUI 블로킹 방지)
        if self.logic and self.logic.driver:
            # 쓰레드가 없거나 종료된 경우에만 새로 시작
            if self._position_update_thread is None or not self._position_update_thread.is_alive():
                self._position_update_thread = threading.Thread(target=self._update_chrome_position, daemon=True)
                self._position_update_thread.start()
    
    def _update_chrome_position(self):
        """크롬 창 위치를 GUI 오른쪽에 맞춤"""
        time.sleep(0.2)  # GUI 업데이트 대기 (약간 증가)
        if self.logic.driver:
            try:
                self.logic._position_chrome_window(self)
            except:
                pass
    
    def _on_mousewheel(self, event):
        """마우스 휠 이벤트 처리 (스크롤 개선)"""
        try:
            # 이벤트가 발생한 위젯이 왼쪽 패널 또는 스크롤 가능한 프레임인지 확인
            widget = event.widget
            if widget != self.left_panel and widget != self.scrollable_frame:
                # 위젯의 부모 체인 확인
                parent = widget
                while parent:
                    if parent == self.left_panel or parent == self.scrollable_frame:
                        break
                    try:
                        parent = parent.master
                    except:
                        break
                else:
                    return  # 왼쪽 패널과 관련 없는 위젯
            
            # 델타 계산
            if platform.system() == "Darwin":  # macOS
                delta = event.delta
            elif event.num == 4:  # Linux 위로
                delta = 1
            elif event.num == 5:  # Linux 아래로
                delta = -1
            else:  # Windows
                delta = event.delta // 120
            
            # 스크롤 가능한 프레임의 캔버스에 스크롤 적용
            if hasattr(self.scrollable_frame, '_parent_canvas'):
                self.scrollable_frame._parent_canvas.yview_scroll(int(-delta), "units")
        except:
            pass

    def on_login(self):
        uid = self.entry_id.get()
        upw = self.entry_pw.get()
        if not uid or not upw:
            self.log_msg("⚠️ 아이디/비번을 입력하세요.")
            return
        
        # 즉시 UI 피드백
        self.btn_login.configure(state="disabled", text="로그인 중...")
        self.update_idletasks()  # GUI 즉시 업데이트
        self.log_msg("🔐 로그인 시도 중...")
        threading.Thread(target=self._thread_login, args=(uid, upw), daemon=True).start()

    def _thread_login(self, u, p):
        if not self.logic.driver:
            if not self.logic.connect_driver():
                self.after(0, lambda: self.btn_login.configure(state="normal", text="로그인"))
                return
        
        if self.logic.login(u, p):
            self.after(0, lambda: self.btn_login.configure(
                state="normal",
                text="로그인 완료",
                fg_color=IOS_COLORS["text_secondary"],
                hover_color=IOS_COLORS["text_secondary"]
            ))
        else:
            self.after(0, lambda: self.btn_login.configure(state="normal", text="로그인"))

    def on_search(self):
        k = self.entry_keyword.get()
        if not k:
            self.log_msg("⚠️ 키워드를 입력하세요.")
            return
        
        # 즉시 UI 피드백
        self.btn_search.configure(state="disabled", text="검색 중...")
        self.update_idletasks()  # GUI 즉시 업데이트
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
        
        try:
            target_count = int(self.entry_target.get() or "100")
        except:
            target_count = 100
        
        neighbor_msg = self.txt_msg.get("1.0", "end").strip()
        comment_msg = self.txt_cmt.get("1.0", "end").strip()
        
        if not neighbor_msg:
            neighbor_msg = "블로그 스타일이 너무 좋아요! 저도 다양한 주제로 글 쓰고 있어서 함께 소통하면 좋을 것 같아 이웃 신청드립니다:)"
        if not comment_msg:
            comment_msg = "안녕하세요! 포스팅 잘 보고 갑니다. 좋은 하루 보내세요~"
        
        # 즉시 UI 피드백
        self.btn_start.configure(state="disabled", text="시작 중...")
        self.btn_stop.configure(state="normal")
        self.update_idletasks()  # GUI 즉시 업데이트
        self.log_msg(f"🚀 작업 시작: '{keyword}' (목표: {target_count}개)")
        threading.Thread(target=self._thread_start, args=(keyword, target_count, neighbor_msg, comment_msg), daemon=True).start()

    def _thread_start(self, keyword, target_count, neighbor_msg, comment_msg):
        self.logic.start_working(keyword, target_count, neighbor_msg, comment_msg)
        # 작업이 완료되면 버튼 상태 업데이트
        self.after(0, lambda: self._update_button_state())
    
    def _update_button_state(self):
        """작업 상태에 따라 버튼 상태 업데이트"""
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
            # 즉시 버튼 상태 업데이트
            self.btn_start.configure(state="normal", text="작업 시작")
            self.btn_stop.configure(state="disabled")
            self.update_idletasks()  # GUI 즉시 업데이트
        else:
            self.log_msg("실행 중 아님")

if __name__ == "__main__":
    import sys
    import warnings
    # macOS 26.1 Tcl/Tk 호환성 경고 무시
    warnings.filterwarnings("ignore")
    # stderr를 리다이렉트하여 bootloader 에러 메시지 숨기기
    import os
    devnull = open(os.devnull, 'w')
    sys.stderr = devnull
    
    try:
        app = App()
        app.mainloop()
    except Exception as e:
        # 에러 발생 시 원래 stderr로 복원하여 실제 에러 표시
        sys.stderr = sys.__stderr__
        print(f"에러 발생: {e}")
        import traceback
        traceback.print_exc()
        raise
