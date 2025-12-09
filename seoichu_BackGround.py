import time
import random
import re
import subprocess
import os
import platform
import signal
import sys
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException, 
    UnexpectedAlertPresentException,
    NoSuchElementException,
    StaleElementReferenceException,
    WebDriverException
)
from selenium.webdriver.common.action_chains import ActionChains

# ==========================================
# [사용자 설정]
# ==========================================
TARGET_COUNT = 100
MY_BLOG_ID = "yang5864"  # 👈 본인 아이디 필수!
MY_NICKNAME = "알잘도"
SEARCH_KEYWORD = None  # 실행 시 입력받음

NEIGHBOR_MSG = "블로그 스타일이 너무 좋아요! 저도 다양한 주제로 글 쓰고 있어서 함께 소통하면 좋을 것 같아 이웃 신청드립니다:)"
COMMENT_MSG = "안녕하세요! 포스팅 잘 보고 갑니다. 좋은 하루 보내세요~"

def get_search_keyword():
    """검색 키워드 입력받기 (명령줄 인자 또는 직접 입력)"""
    global SEARCH_KEYWORD
    
    # 1. 명령줄 인자로 받은 경우: python seoichu_BackGround.py "키워드"
    if len(sys.argv) > 1:
        SEARCH_KEYWORD = sys.argv[1]
        return SEARCH_KEYWORD
    
    # 2. 직접 입력받기
    print("=" * 50)
    print("🔍 검색할 키워드를 입력하세요")
    print("   (예: 맛집, 여행, 육아, 재테크 등)")
    print("=" * 50)
    keyword = input("👉 키워드: ").strip()
    
    if not keyword:
        print("❌ 키워드가 입력되지 않았습니다. 기본값 '일상' 사용")
        keyword = "일상"
    
    SEARCH_KEYWORD = keyword
    return SEARCH_KEYWORD

# [성능 설정] - 필요시 조정
PAGE_LOAD_TIMEOUT = 15
ELEMENT_WAIT_TIMEOUT = 5
FAST_WAIT = 0.3
NORMAL_WAIT = 0.8
SLOW_WAIT = 1.5
# ==========================================

# 전역 드라이버 (종료 처리용)
_driver = None

def log(msg):
    """타임스탬프와 함께 로그를 즉시 출력"""
    timestamp = time.strftime("%H:%M:%S")
    print(f"[{timestamp}] {msg}", flush=True)

def safe_sleep(seconds):
    """안전한 대기 (0이면 스킵)"""
    if seconds > 0:
        time.sleep(seconds)

def cleanup_handler(signum, frame):
    """Ctrl+C 시 깔끔한 종료"""
    global _driver
    log("\n🛑 사용자에 의해 중단됨. 정리 중...")
    if _driver:
        try:
            _driver.quit()
        except:
            pass
    sys.exit(0)

# Ctrl+C 핸들러 등록
signal.signal(signal.SIGINT, cleanup_handler)
signal.signal(signal.SIGTERM, cleanup_handler)

def get_chrome_path():
    """OS별 크롬 경로 반환"""
    if platform.system() == "Darwin":  # Mac
        paths = [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            os.path.expanduser("~/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
        ]
    elif platform.system() == "Windows":
        paths = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe")
        ]
    else:  # Linux
        paths = ["/usr/bin/google-chrome", "/usr/bin/chromium-browser"]
    
    for path in paths:
        if os.path.exists(path):
            return path
    return paths[0]  # 기본값 반환

def is_chrome_running(port=9222):
    """9222 포트에서 크롬이 실행 중인지 확인"""
    import socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    result = sock.connect_ex(('127.0.0.1', port))
    sock.close()
    return result == 0

def open_chrome_debug_mode(headless=False):
    """크롬 디버깅 모드 자동 실행 (화면 모드 - headless는 네이버에서 로그인 불가)"""
    user_data_dir = os.path.expanduser("~/ChromeBotData")
    chrome_path = get_chrome_path()
    
    # 기존 프로세스 확인
    if is_chrome_running():
        log("✅ 이미 9222 포트에서 크롬이 실행 중입니다.")
        return True

    # 🚨 [중요] Headless 모드는 네이버에서 로그인이 안됨!
    # 항상 화면 모드로 실행하되, 창을 최소화 상태로 시작
    cmd = [
        chrome_path,
        "--remote-debugging-port=9222",
        f"--user-data-dir={user_data_dir}",
        "--no-first-run",
        "--no-default-browser-check",
        "--window-size=1920,1080",
        "--window-position=0,0",
        # 봇 감지 우회 옵션들
        "--disable-blink-features=AutomationControlled",
        "--disable-infobars",
        "--disable-dev-shm-usage",
        # User-Agent 설정
        "--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    ]
    
    log(f"🖥️  크롬 실행 중 (화면 모드 - 최소화 가능)...")
    log(f"   └ 데이터 경로: {user_data_dir}")
    log(f"   💡 크롬 창을 최소화하고 다른 작업을 하셔도 됩니다!")
    
    try:
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except Exception as e:
        log(f"❌ 크롬 실행 실패: {e}")
        return False

def connect_debugger_driver():
    """실행 중인 크롬에 연결 (재시도 로직 포함)"""
    global _driver
    
    # 디버거 모드 연결 시에는 최소한의 옵션만 사용
    chrome_options = Options()
    chrome_options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")
    chrome_options.page_load_strategy = 'eager'
    
    log("🔌 크롬 드라이버 연결 시도 중...")
    
    # 1차 시도: 기존 크롬에 연결
    try:
        driver = webdriver.Chrome(options=chrome_options)
        _driver = driver
        
        # 봇 감지 우회 스크립트 실행 (CDP 사용)
        try:
            driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
                "source": """
                    Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                    Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
                    Object.defineProperty(navigator, 'languages', {get: () => ['ko-KR', 'ko', 'en-US', 'en']});
                    window.chrome = {runtime: {}};
                """
            })
        except:
            pass  # CDP 실패해도 계속 진행
        
        driver.set_page_load_timeout(PAGE_LOAD_TIMEOUT)
        log("✅ 기존 크롬에 연결 성공!")
        return driver
    except Exception as e:
        log(f"   └ 1차 연결 실패: {str(e)[:50]}")
    
    # 2차 시도: 크롬 자동 실행 후 연결 (화면 모드 - headless는 네이버 로그인 불가!)
    log("⚠️  실행 중인 크롬 없음 → 크롬 자동 실행")
    if not open_chrome_debug_mode(headless=False):  # 화면 모드로 실행 (필수!)
        return None
    
    for i in range(8):  # 최대 8초 대기
        log(f"⏳ 크롬 실행 대기 중... ({i+1}/8)")
        safe_sleep(1.0)
        
        if is_chrome_running():
            try:
                driver = webdriver.Chrome(options=chrome_options)
                _driver = driver
                
                # 봇 감지 우회 스크립트
                try:
                    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
                        "source": """
                            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                            Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
                        """
                    })
                except:
                    pass
                
                driver.set_page_load_timeout(PAGE_LOAD_TIMEOUT)
                log("✅ 백그라운드 크롬에 연결 성공!")
                return driver
            except Exception as e:
                log(f"   └ 연결 재시도... ({str(e)[:40]})")
    
    log("❌ 크롬 연결 최종 실패")
    return None

def safe_get(driver, url, max_retries=2):
    """안전한 페이지 이동 (재시도 포함)"""
    for attempt in range(max_retries):
        try:
            driver.get(url)
            return True
        except TimeoutException:
            if attempt < max_retries - 1:
                log(f"   ⚠️ 페이지 로딩 타임아웃, 재시도 ({attempt+1}/{max_retries})")
                driver.execute_script("window.stop();")
            else:
                return False
        except Exception as e:
            if attempt < max_retries - 1:
                safe_sleep(0.5)
            else:
                return False
    return False

def safe_find_element(driver, by, value, timeout=ELEMENT_WAIT_TIMEOUT):
    """안전한 요소 찾기"""
    try:
        return WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((by, value))
        )
    except:
        return None

def safe_click(driver, element):
    """안전한 클릭 (JS 클릭 우선)"""
    try:
        driver.execute_script("arguments[0].click();", element)
        return True
    except:
        try:
            element.click()
            return True
        except:
            return False

def dismiss_alert_if_present(driver):
    """알림창이 있으면 닫기"""
    try:
        alert = driver.switch_to.alert
        text = alert.text
        alert.accept()
        return text
    except:
        return None

def check_login_status(driver):
    """로그인 여부 확인 (실제 API 테스트)"""
    try:
        # 1. 내 블로그 설정 페이지 접속 시도 (로그인 필수 페이지)
        if not safe_get(driver, f"https://m.blog.naver.com/{MY_BLOG_ID}"):
            log("   └ 블로그 페이지 접속 실패")
            return False
        safe_sleep(2.0)
        
        page_source = driver.page_source
        current_url = driver.current_url
        
        # 2. 로그인 페이지로 리다이렉트 되었는지 확인
        if "nidlogin" in current_url or "login" in current_url.lower():
            log("   └ 로그인 페이지로 리다이렉트됨")
            return False
        
        # 3. "글쓰기" 버튼이 보이면 로그인 상태 (내 블로그에서만 보임)
        if "글쓰기" in page_source or "write" in page_source.lower():
            log("   └ 내 블로그에서 글쓰기 버튼 확인됨")
            return True
        
        # 4. 쿠키 확인
        cookies = driver.get_cookies()
        login_cookies = ["NID_AUT", "NID_SES"]
        
        for cookie in cookies:
            if cookie.get('name') in login_cookies:
                log("   └ 로그인 쿠키 확인됨")
                return True
        
        # 5. 최종 확인: 이웃추가 양식 페이지 접근 테스트
        log("   └ 이웃추가 양식 접근 테스트...")
        if not safe_get(driver, f"https://m.blog.naver.com/BuddyAddForm.naver?blogId=naver"):
            return False
        safe_sleep(1.5)
        
        test_src = driver.page_source
        if "로그인이 필요" in test_src or "로그인해 주세요" in test_src:
            log("   └ 양식 페이지 접근 시 로그인 요구됨")
            return False
        
        return True
        
    except Exception as e:
        log(f"   └ 로그인 확인 중 오류: {e}")
        return False

def close_current_tab_safely(driver, main_window):
    """현재 탭을 안전하게 닫기"""
    try:
        # 알림창 먼저 처리
        dismiss_alert_if_present(driver)
        
        current = driver.current_window_handle
        handles = driver.window_handles
        
        # 메인 탭이 아니고, 탭이 2개 이상일 때만 닫기
        if current != main_window and len(handles) > 1:
            driver.close()
            
        # 메인 탭으로 복귀
        driver.switch_to.window(main_window)
        return True
    except Exception as e:
        # 복구 시도
        try:
            handles = driver.window_handles
            if handles:
                driver.switch_to.window(handles[0])
            return True
        except:
            return False

# ==========================================
# 서이추 로직 (최적화)
# ==========================================
def process_neighbor(driver, blog_id):
    """서로이웃 신청 처리"""
    try:
        # 1. 페이지 소스 확인 (이미 이웃인지)
        src = driver.page_source
        if "이웃끊기" in src or "서로이웃 취소" in src:
            return False, "스킵(이미 이웃)"

        # 2. 이웃추가 버튼 클릭
        clicked = False
        
        # 방법 1: data-click-area 속성
        try:
            btn = driver.find_element(By.CSS_SELECTOR, "[data-click-area='ebc.add']")
            safe_click(driver, btn)
            clicked = True
        except:
            pass
        
        # 방법 2: 이미 이웃 버튼 확인
        if not clicked:
            try:
                if driver.find_elements(By.CSS_SELECTOR, "[data-click-area='ebc.ngr']"):
                    return False, "스킵(이미 이웃)"
            except:
                pass
        
        # 방법 3: 텍스트로 찾기
        if not clicked:
            try:
                btn = driver.find_element(By.XPATH, "//*[contains(text(), '이웃추가')]")
                safe_click(driver, btn)
                clicked = True
            except:
                pass

        if not clicked:
            return False, "스킵(버튼 없음)"

        # 🔧 [핵심] 버튼 클릭 후 충분히 대기 (페이지 전환/팝업 로딩)
        safe_sleep(1.0)

        # 3. 팝업/상태 확인
        src_after = driver.page_source
        
        # 일일 한도 초과
        if "하루에 신청 가능한 이웃수" in src_after and "초과" in src_after:
            try:
                close_btn = driver.find_element(By.XPATH, "//button[contains(text(), '닫기')]")
                safe_click(driver, close_btn)
            except:
                pass
            return "DONE_DAY_LIMIT", "🎉 일일 한도 달성!"

        # 이미 신청 진행중
        if "서로이웃 신청 진행중입니다" in src_after:
            try:
                cancel_btns = driver.find_elements(By.XPATH, "//button[contains(text(), '취소')]")
                for btn in cancel_btns:
                    if btn.is_displayed():
                        safe_click(driver, btn)
                        safe_sleep(0.2)
                        return False, "스킵(이미 신청중)"
            except:
                pass
            return False, "스킵(이미 신청중)"

        # 구형 팝업 확인
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

        # 4. 신청 양식 페이지 확인 
        # 🔧 [핵심] URL 기반으로 페이지 전환 확인
        current_url = driver.current_url
        
        # 이미 양식 페이지에 있는지 확인
        if "BuddyAddForm" not in current_url:
            # 양식 페이지로 직접 이동
            if not safe_get(driver, f"https://m.blog.naver.com/BuddyAddForm.naver?blogId={blog_id}"):
                return False, "실패(양식 페이지 로드 실패)"
            safe_sleep(2.0)  # 페이지 로딩 대기
        
        # 5. 로그인 상태 재확인 (양식 페이지에서)
        page_src = driver.page_source
        if "로그인" in page_src and "로그인이 필요" in page_src:
            return False, "실패(로그인 필요)"
        
        # 6. 서로이웃 라디오 버튼 선택
        try:
            safe_sleep(0.5)
            
            # bothBuddyRadio가 있는지 먼저 확인
            radio_exists = driver.execute_script("""
                return document.getElementById('bothBuddyRadio') !== null;
            """)
            
            if not radio_exists:
                # 일반 이웃만 가능한 경우 (서로이웃 비활성화)
                one_way_radio = driver.execute_script("""
                    return document.getElementById('onewayBuddyRadio') !== null;
                """)
                if one_way_radio:
                    return False, "스킵(서이추 비활성화)"
                
                # 이미 신청 진행 중인지 확인
                if "진행 중" in page_src or "신청중" in page_src or "신청 진행" in page_src:
                    return False, "스킵(이미 신청중)"
                
                return False, "실패(양식 없음)"
            
            # 라디오 버튼 클릭
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

        # 6. 메시지 입력
        try:
            textarea = driver.find_element(By.TAG_NAME, "textarea")
            driver.execute_script("""
                var el = arguments[0];
                var txt = arguments[1];
                el.value = txt;
                el.dispatchEvent(new Event('input', { bubbles: true }));
                el.dispatchEvent(new Event('change', { bubbles: true }));
            """, textarea, NEIGHBOR_MSG)
        except:
            pass  # 메시지 입력 실패해도 진행

        # 7. 확인 버튼 클릭
        try:
            confirm_btn = driver.find_element(By.XPATH, "//*[text()='확인']")
            safe_click(driver, confirm_btn)
            safe_sleep(FAST_WAIT)
        except:
            return False, "실패(확인 버튼 없음)"

        # 8. 최종 결과 확인
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

        # 9. 알림창 확인
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

# ==========================================
# 공감(좋아요) 로직
# ==========================================
def process_like(driver):
    """공감 버튼 클릭"""
    try:
        # 공감 버튼 찾기
        wrapper = safe_find_element(driver, By.CSS_SELECTOR, "a.u_likeit_button", timeout=3)
        if not wrapper:
            return "공감 버튼 없음"

        # 이미 눌렀는지 확인
        is_pressed = wrapper.get_attribute("aria-pressed") == "true"
        class_list = wrapper.get_attribute("class") or ""
        
        if is_pressed or "on" in class_list.split():
            return "이미 공감함"

        # 내부 아이콘 클릭 시도
        try:
            icon = wrapper.find_element(By.CSS_SELECTOR, "span.u_likeit_icon")
            ActionChains(driver).move_to_element(icon).click().perform()
            safe_sleep(NORMAL_WAIT)
            
            # 클릭 확인
            if wrapper.get_attribute("aria-pressed") != "true":
                driver.execute_script("arguments[0].click();", icon)
                safe_sleep(FAST_WAIT)
            
            return "공감 ❤️"
        except:
            # 폴백: wrapper 직접 클릭
            safe_click(driver, wrapper)
            return "공감 ❤️"

    except Exception as e:
        return "공감 실패"

# ==========================================
# 댓글 로직
# ==========================================
def process_comment(driver, blog_id):
    """댓글 작성"""
    try:
        # 1. 댓글 버튼 클릭
        comment_btn = safe_find_element(
            driver, 
            By.CSS_SELECTOR, 
            "button[class*='comment_btn'], a.btn_comment",
            timeout=3
        )
        if not comment_btn:
            return "댓글 버튼 없음"
        
        safe_click(driver, comment_btn)
        safe_sleep(NORMAL_WAIT)

        # 2. 중복 확인 (이미 내 댓글이 있는지)
        try:
            existing_nicks = driver.find_elements(By.CSS_SELECTOR, "span.u_cbox_nick")
            for nick_el in existing_nicks:
                if MY_NICKNAME == nick_el.text.strip():
                    return f"스킵(이미 댓글 씀)"
        except:
            pass

        # 3. 입력창 찾기
        input_box = safe_find_element(
            driver,
            By.CSS_SELECTOR,
            ".u_cbox_text_mention, .u_cbox_inbox textarea",
            timeout=3
        )
        if not input_box:
            return "입력창 없음"

        # 4. 닉네임 추출
        target_nickname = blog_id
        try:
            name_el = driver.find_element(By.CSS_SELECTOR, ".user_name, .blogger_name")
            target_nickname = name_el.text.strip() or blog_id
        except:
            pass

        # 5. 댓글 입력
        final_msg = COMMENT_MSG.format(name=target_nickname)
        try:
            ActionChains(driver).move_to_element(input_box).click().send_keys(final_msg).perform()
        except:
            driver.execute_script("""
                arguments[0].value = arguments[1];
                arguments[0].dispatchEvent(new Event('input', {bubbles: true}));
            """, input_box, final_msg)
        
        safe_sleep(0.2)

        # 6. 등록 버튼 클릭
        submit_btn = safe_find_element(
            driver,
            By.CSS_SELECTOR,
            ".u_cbox_btn_upload, .u_cbox_btn_complete",
            timeout=2
        )
        if not submit_btn:
            return "등록 버튼 없음"
        
        safe_click(driver, submit_btn)

        # 7. 스팸 알림 확인
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

        safe_sleep(NORMAL_WAIT)
        return "댓글 💬"

    except Exception as e:
        return "댓글 실패"

# ==========================================
# ID 수집 로직 (블로그 탭 클릭 추가)
# ==========================================
def collect_blog_ids(driver, processed_ids, my_id_clean, blacklist, search_url):
    """검색 결과에서 블로그 ID 수집 - 블로그 탭 클릭 후 수집"""
    queue = []
    
    # 검색 페이지 확인 및 이동
    current_url = driver.current_url
    if "search.naver.com" not in current_url:
        log("   ↪ 검색 페이지로 이동...")
        if not safe_get(driver, search_url):
            return queue
        safe_sleep(2.0)
    
    # 🔧 [핵심] "블로그" 탭 클릭
    try:
        # 방법 1: role="tab"에서 블로그 텍스트 찾기
        blog_tab = None
        tabs = driver.find_elements(By.CSS_SELECTOR, "[role='tab'], .tab, .lnb_item a, .flick_bx a")
        for tab in tabs:
            try:
                if "블로그" in tab.text:
                    blog_tab = tab
                    break
            except:
                continue
        
        # 방법 2: 직접 텍스트로 찾기
        if not blog_tab:
            try:
                blog_tab = driver.find_element(By.XPATH, "//a[contains(text(), '블로그')]")
            except:
                pass
        
        # 방법 3: 클래스로 찾기 (네이버 검색의 탭 구조)
        if not blog_tab:
            try:
                blog_tab = driver.find_element(By.CSS_SELECTOR, "a.tab[href*='where=blog'], a[data-tab='blog']")
            except:
                pass
        
        if blog_tab:
            log("   ↪ '블로그' 탭 클릭...")
            safe_click(driver, blog_tab)
            safe_sleep(2.0)  # 탭 전환 후 로딩 대기
        else:
            log("   ⚠️ 블로그 탭을 찾지 못함 (URL로 직접 이동)")
            # 블로그 검색 전용 URL로 이동
            blog_search_url = search_url.replace("where=blog", "ssc=tab.blog.all&where=blog")
            if "ssc=" not in blog_search_url:
                blog_search_url = search_url + "&ssc=tab.blog.all"
            safe_get(driver, blog_search_url)
            safe_sleep(2.0)
            
    except Exception as e:
        log(f"   ⚠️ 탭 클릭 실패: {str(e)[:20]}")
    
    scroll_attempts = 0
    max_scroll = 7
    
    while len(queue) < 20 and scroll_attempts < max_scroll:
        # 스크롤
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        safe_sleep(2.0)  # 로딩 대기 시간 증가
        
        # 🔧 [핵심 수정] 모든 a 태그에서 링크 수집 (원본 방식)
        new_count = 0
        try:
            # 방법 1: 모든 a 태그 검색 (가장 포괄적)
            all_links = driver.find_elements(By.TAG_NAME, "a")
            
            for link in all_links:
                try:
                    href = link.get_attribute("href")
                    if not href:
                        continue
                    
                    # blog.naver.com 링크만 필터링
                    if "blog.naver.com" not in href:
                        continue
                    
                    # 블로그 ID 추출 (여러 패턴 지원)
                    match = re.search(r'blog\.naver\.com\/([a-zA-Z0-9_-]+)', href)
                    if not match:
                        continue
                    
                    bid = match.group(1)
                    bid_lower = bid.lower()
                    
                    # 필터링: 시스템 경로 제외
                    if bid_lower in blacklist or bid_lower == my_id_clean:
                        continue
                    if bid in processed_ids:
                        continue
                    if len(bid) <= 3:  # 너무 짧은 ID 제외
                        continue
                    if bid in queue:  # 이미 큐에 있으면 스킵
                        continue
                    # 숫자로만 된 것 제외 (포스트 번호일 수 있음)
                    if bid.isdigit():
                        continue
                    
                    queue.append(bid)
                    processed_ids.add(bid)
                    new_count += 1
                    
                except StaleElementReferenceException:
                    continue
                except:
                    continue
        except Exception as e:
            log(f"   ⚠️ 링크 수집 오류: {str(e)[:30]}")
        
        log(f"   ⬇️ 스크롤 {scroll_attempts+1}/{max_scroll} - 신규 {new_count}명 (대기열: {len(queue)}명)")
        
        # 충분히 모았으면 종료
        if len(queue) >= 20:
            break
        
        scroll_attempts += 1
        
        # 새로 못 찾으면 추가 스크롤 시도 (트릭)
        if new_count == 0:
            # "더보기" 버튼 클릭 시도
            try:
                more_btn = driver.find_element(By.CSS_SELECTOR, ".btn_more, .more_btn, [class*='more']")
                if more_btn.is_displayed():
                    safe_click(driver, more_btn)
                    safe_sleep(1.5)
            except:
                pass
            
            # 약간 위로 올렸다가 다시 내리기
            driver.execute_script("window.scrollBy(0, -500);")
            safe_sleep(0.5)
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight + 1000);")
            safe_sleep(1.0)
    
    return queue

# ==========================================
# 메인 로직
# ==========================================
def main():
    global _driver, SEARCH_KEYWORD
    
    # 🔧 검색 키워드 입력받기
    keyword = get_search_keyword()
    
    log("=" * 45)
    log("🚀 서이추 봇 시작")
    log(f"🔍 검색 키워드: {keyword}")
    log("=" * 45)
    
    # 드라이버 연결
    driver = connect_debugger_driver()
    if not driver:
        log("❌ 드라이버 연결 실패")
        return
    
    _driver = driver
    
    # 로그인 확인
    log("🔐 로그인 상태 확인 중...")
    if not check_login_status(driver):
        log("\n" + "=" * 45)
        log("⛔ [오류] 로그인이 필요합니다!")
        log("=" * 45)
        log("\n[해결 방법]")
        log("1. 먼저 화면이 보이는 모드로 로그인하세요:")
        if platform.system() == "Darwin":
            log('   터미널: /Applications/Google\\ Chrome.app/Contents/MacOS/Google\\ Chrome --user-data-dir=~/ChromeBotData')
        else:
            log('   CMD: chrome.exe --user-data-dir=%USERPROFILE%\\ChromeBotData')
        log("2. 네이버에 로그인")
        log("3. 브라우저 닫기")
        log("4. 이 프로그램 다시 실행")
        log("")
        driver.quit()
        return
    
    log("✅ 로그인 확인 완료!")
    
    # 설정 확인
    my_id_clean = MY_BLOG_ID.strip().lower()
    blacklist = {"myblog", "postlist", "buddyaddform", "likeit", "nvisitor", "blog", "domainid", "admin", "search"}
    search_url = f"https://search.naver.com/search.naver?where=blog&query={SEARCH_KEYWORD}"
    
    log(f"📋 설정: 목표 {TARGET_COUNT}명 / 키워드 '{SEARCH_KEYWORD}' / 제외 '{MY_BLOG_ID}'")
    
    # 검색 페이지 이동
    log(f"🌍 검색 페이지로 이동...")
    if not safe_get(driver, search_url):
        log("❌ 검색 페이지 로드 실패")
        return
    safe_sleep(SLOW_WAIT)
    
    main_window = driver.current_window_handle
    
    success_cnt = 0
    processed_ids = set()
    queue = []
    consecutive_errors = 0  # 연속 에러 카운터
    
    while success_cnt < TARGET_COUNT:
        # [A] 대기열 보충
        if not queue:
            log(f"🔄 ID 수집 중... (처리 완료: {len(processed_ids)}명)")
            
            try:
                if not driver.window_handles:
                    log("❌ 브라우저가 닫혔습니다.")
                    return
                driver.switch_to.window(main_window)
            except:
                log("❌ 메인 탭 접근 불가")
                return
            
            queue = collect_blog_ids(driver, processed_ids, my_id_clean, blacklist, search_url)
            
            if not queue:
                log("⚠️ 더 이상 수집할 블로그가 없습니다.")
                # 페이지 새로고침 후 재시도
                log("   ↪ 페이지 새로고침 후 재시도...")
                safe_get(driver, search_url)
                safe_sleep(SLOW_WAIT)
                queue = collect_blog_ids(driver, processed_ids, my_id_clean, blacklist, search_url)
                
                if not queue:
                    log("⚠️ 최종 종료: 수집 가능한 블로그 없음")
                    break
            
            log(f"   ✅ {len(queue)}명 수집 완료!")

        # [B] 작업 실행
        blog_id = queue.pop(0)
        
        # 필터링
        if blog_id.lower() == my_id_clean or blog_id.lower() in blacklist:
            continue

        log(f"\n▶️ [{success_cnt+1}/{TARGET_COUNT}] '{blog_id}' 작업 시작")
        
        # 새 탭 열기
        try:
            driver.switch_to.new_window('tab')
            if not safe_get(driver, f"https://m.blog.naver.com/{blog_id}"):
                log("   ❌ 페이지 로드 실패")
                close_current_tab_safely(driver, main_window)
                consecutive_errors += 1
                if consecutive_errors >= 5:
                    log("⚠️ 연속 5회 실패. 잠시 대기 후 계속...")
                    safe_sleep(5.0)
                    consecutive_errors = 0
                continue
        except Exception as e:
            log(f"   ⚠️ 탭 열기 실패: {str(e)[:20]}")
            close_current_tab_safely(driver, main_window)
            continue

        # 🔧 블로그 페이지 로드 대기 (충분히)
        safe_sleep(1.5)
        consecutive_errors = 0  # 성공적으로 진행되면 리셋

        # 에러 페이지 확인
        current_url = driver.current_url
        page_source = driver.page_source
        
        if "MobileErrorView" in current_url or "일시적인 오류" in page_source or "존재하지 않는" in page_source:
            log(f"   ❌ 접근 불가/없는 블로그 (Skip)")
            close_current_tab_safely(driver, main_window)
            continue

        # 1. 서이추 실행
        is_friend, msg_friend = process_neighbor(driver, blog_id)
        
        # 종료 조건 확인
        if is_friend == "DONE_DAY_LIMIT":
            log(f"\n{'🎉' * 10}")
            log("목표 달성! 오늘 할당량을 모두 채웠습니다!")
            log(f"{'🎉' * 10}")
            close_current_tab_safely(driver, main_window)
            break
            
        if is_friend == "STOP_GROUP_FULL":
            log(f"\n⛔ 내 이웃 그룹이 가득 찼습니다.")
            log("   이웃 그룹을 정리한 후 다시 실행하세요.")
            close_current_tab_safely(driver, main_window)
            break

        log(f"   └ 서이추: {msg_friend}")

        # 2. 홈으로 복귀 (신청 페이지에서)
        if "BuddyAddForm" in driver.current_url:
            safe_get(driver, f"https://m.blog.naver.com/{blog_id}")
            safe_sleep(NORMAL_WAIT)

        # 3. 공감 & 댓글 (서이추 성공 시에만)
        if is_friend is True:
            msg_like = process_like(driver)
            log(f"   └ 공감: {msg_like}")

            if "실패" not in msg_like and "없음" not in msg_like:
                msg_cmt = process_comment(driver, blog_id)
                log(f"   └ 댓글: {msg_cmt}")
            
            success_cnt += 1
            log(f"   ✅ 성공! (현재 {success_cnt}/{TARGET_COUNT})")

        # 4. 탭 닫기 및 메인 복귀
        if not close_current_tab_safely(driver, main_window):
            log("❌ 탭 관리 실패. 종료합니다.")
            return

        # 랜덤 대기 (봇 감지 방지)
        wait_time = random.uniform(0.8, 1.5)
        safe_sleep(wait_time)

    # 종료
    log("\n" + "=" * 45)
    log(f"🎉 프로그램 종료 (성공: {success_cnt}명)")
    log("=" * 45)

if __name__ == "__main__":
    main()
