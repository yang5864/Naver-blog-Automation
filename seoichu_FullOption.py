import time
import random
import re
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import UnexpectedAlertPresentException

# ==========================================
# [사용자 설정]
# ==========================================
TARGET_COUNT = 100
MY_BLOG_ID = "yang5864"  # 👈 여기에 본인의 블로그 아이디를 꼭 적어주세요! (예: myid1234)
MY_NICKNAME = "알잘도"       # 내 닉네임 (댓글 중복 방지용)

# 서이추 멘트
NEIGHBOR_MSG = "블로그 스타일이 너무 좋아요! 저도 다양한 주제로 글 쓰고 있어서 함께 소통하면 좋을 것 같아 이웃 신청드립니다:)"
# 댓글 멘트 ({name} 부분은 블로거 닉네임으로 자동 치환됩니다)
COMMENT_MSG = "안녕하세요! 포스팅 잘 보고 갑니다. 좋은 하루 보내세요~"
# ==========================================

def connect_debugger_driver():
    """실행 중인 크롬(9222포트)에 연결"""
    chrome_options = Options()
    chrome_options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")
    chrome_options.page_load_strategy = 'eager'
    
    # 🚀 [수정] log 대신 print 사용 + flush=True 추가 (즉시 출력)
    try:
        driver = webdriver.Chrome(options=chrome_options)
        return driver
    except Exception as e:
        print("❌ 크롬 연결 실패! 디버깅 모드로 크롬이 실행 중인지 확인하세요.", flush=True)
        return None

# ==========================================
# 1. 서이추 로직 (HTML 팝업 감지 기능 추가)
# ==========================================
def process_neighbor(driver, blog_id):
    """
    [일일 한도 초과(DONE_DAY_LIMIT) 감지 로직 추가]
    """
    try:
        # 1. [초고속 확인] 페이지 소스로 먼저 거르기
        src = driver.page_source
        if "이웃끊기" in src or "서로이웃 취소" in src:
            return False, "스킵(이미 이웃)"

        # 2. 버튼 클릭
        clicked = False
        try:
            btn = driver.find_element(By.CSS_SELECTOR, "[data-click-area='ebc.add']")
            driver.execute_script("arguments[0].click();", btn)
            clicked = True
        except:
            try:
                # 예비책: 이미 이웃 버튼 확인
                if driver.find_elements(By.CSS_SELECTOR, "[data-click-area='ebc.ngr']"):
                     return False, "스킵(이미 이웃/서로이웃)"
                
                xpath = "//*[contains(text(), '이웃추가')]"
                btn = driver.find_element(By.XPATH, xpath)
                driver.execute_script("arguments[0].click();", btn)
                clicked = True
            except: pass

        if not clicked: return False, "스킵(버튼 못찾음)"

        time.sleep(0.5)

        # =================================================================
        # 🚨 3. [핵심 수정] "하루 할당량 초과" 팝업 최우선 감지
        # =================================================================
        src_after_click = driver.page_source
        
        # 스크린샷 텍스트: "하루에 신청 가능한 이웃수가 초과되어"
        if "하루에 신청 가능한 이웃수" in src_after_click and "초과" in src_after_click:
            # 깔끔한 종료를 위해 '닫기' 버튼 눌러주기 (선택사항)
            try:
                close_btn = driver.find_element(By.XPATH, "//button[contains(text(), '닫기')]")
                driver.execute_script("arguments[0].click();", close_btn)
            except: pass
            
            return "DONE_DAY_LIMIT", "🎉 일일 신청 한도(100명) 달성!"

        # [신청 진행중] 신형 팝업 감지
        if "서로이웃 신청 진행중입니다" in src_after_click:
            try:
                cancel_btns = driver.find_elements(By.XPATH, "//button[contains(text(), '취소')]")
                for btn in cancel_btns:
                    if btn.is_displayed():
                        driver.execute_script("arguments[0].click();", btn)
                        time.sleep(0.2)
                        return False, "스킵(서로이웃 신청 진행중)"
            except: pass

        # 4. 구형 팝업 체크
        layer_popup = driver.execute_script("""
            var layer = document.getElementById('_alertLayer');
            if (layer && layer.style.display !== 'none') {
                var msg = layer.querySelector('.dsc').innerText;
                return msg;
            }
            return null;
        """)
        
        if layer_popup:
            # 구형 팝업에서도 하루 한도 초과가 뜰 수 있음
            if "하루" in layer_popup and "초과" in layer_popup:
                 return "DONE_DAY_LIMIT", "🎉 일일 신청 한도(100명) 달성!"
            
            if "선택 그룹" in layer_popup: 
                return "STOP_GROUP_FULL", layer_popup
            
            driver.execute_script("document.getElementById('_alertLayerClose').click();")
            if "5,000" in layer_popup or "5000" in layer_popup:
                return False, "스킵(상대방 5000명 초과)"
            
            return False, f"스킵({layer_popup})"

        # 5. 신청 페이지 진입 확인
        try:
            WebDriverWait(driver, 1.5).until(EC.presence_of_element_located((By.ID, "bothBuddyRadio")))
        except TimeoutException:
            driver.get(f"https://m.blog.naver.com/BuddyAddForm.naver?blogId={blog_id}")
            time.sleep(0.5)

        # 6. 신청 양식 작성
        try:
            result = driver.execute_script("""
                try {
                    var radio = document.getElementById('bothBuddyRadio');
                    var label = document.querySelector("label[for='bothBuddyRadio']");
                    
                    if (!radio) return 'NOT_FOUND';
                    if (radio.disabled || radio.getAttribute('disabled')) return 'DISABLED';
                    if (!radio.checked) label.click();
                    return 'OK';
                } catch(e) { return 'ERROR'; }
            """)
            
            if result == 'DISABLED': return False, "스킵(서로이웃 신청 불가/닫힘)"
            if result == 'NOT_FOUND': 
                if "진행 중" in driver.page_source: return False, "스킵(서로이웃 신청 진행중)"
                return False, "실패(양식 못찾음)"
            
        except: return False, "서로이웃 불가"

        # 7. 메시지 입력
        try:
            textarea = driver.find_element(By.TAG_NAME, "textarea")
            driver.execute_script("""
                var el = arguments[0];
                var txt = arguments[1];
                el.value = txt;
                el.dispatchEvent(new Event('input', { bubbles: true }));
                el.dispatchEvent(new Event('change', { bubbles: true }));
                el.dispatchEvent(new Event('blur', { bubbles: true }));
            """, textarea, NEIGHBOR_MSG)
        except: pass

        # 8. 확인 버튼 클릭
        try:
            confirm_btn = driver.find_element(By.XPATH, "//*[text()='확인']")
            driver.execute_script("arguments[0].click();", confirm_btn)
            
            time.sleep(0.3) 
            
            final_layer_check = driver.execute_script("""
                var layer = document.getElementById('_alertLayer');
                if (layer && layer.style.display !== 'none') {
                    var msg = layer.querySelector('.dsc').innerText;
                    return msg;
                }
                return null;
            """)
            
            if final_layer_check:
                if "하루" in final_layer_check and "초과" in final_layer_check:
                    return "DONE_DAY_LIMIT", "🎉 일일 신청 한도(100명) 달성!"
                if "선택 그룹" in final_layer_check:
                    return "STOP_GROUP_FULL", final_layer_check
                
                driver.execute_script("document.getElementById('_alertLayerClose').click();")
                if "5,000" in final_layer_check or "5000" in final_layer_check:
                    return False, "스킵(상대방 5000명 초과)"
                return False, f"실패(팝업: {final_layer_check})"

        except: return False, "확인 버튼 없음"
        
        # 9. 최종 알림
        try:
            WebDriverWait(driver, 0.3).until(EC.alert_is_present())
            alert = driver.switch_to.alert
            txt = alert.text
            alert.accept()
            
            if "하루" in txt and "초과" in txt:
                return "DONE_DAY_LIMIT", txt
            if "선택 그룹" in txt and "초과" in txt:
                return "STOP_GROUP_FULL", txt
            if "5,000" in txt or "5000" in txt:
                return False, "스킵(상대방 5000명 초과)"
            
            if "신청" in txt or "완료" in txt: return True, "신청 완료"
            return False, f"알림: {txt}"
        except:
            return True, "신청 완료(빠른복귀)"

    except Exception as e:
        return False, f"에러: {str(e)[:15]}"

# ==========================================
# 2. 공감(좋아요) 로직 (내부 아이콘 직접 타격)
# ==========================================
def process_like(driver):
    try:
        # 1. 겉껍데기(Button Wrapper) 찾기 - 상태 확인용
        wait = WebDriverWait(driver, 3)
        wrapper = wait.until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, "a.u_likeit_button"))
        )

        # 2. 상태 확인 (aria-pressed가 'true'면 이미 누른 것)
        # 클래스에 'on'이 있거나 aria-pressed가 true면 스킵
        is_pressed = wrapper.get_attribute("aria-pressed") == "true"
        class_list = wrapper.get_attribute("class").split()
        if is_pressed or "on" in class_list:
            return "이미 공감함"

        # -----------------------------------------------------------
        # 🚀 [핵심 수정] 겉이 아니라 '속'을 누른다
        # 사용자가 말한 'u_likeit_icon' 클래스를 가진 span을 찾습니다.
        # -----------------------------------------------------------
        try:
            # 껍데기 안에 있는 실제 아이콘 요소 찾기
            # (__reaction__zeroface 같은 클래스는 변할 수 있으니 앞부분인 u_likeit_icon만 타겟팅)
            inner_icon = wrapper.find_element(By.CSS_SELECTOR, "span.u_likeit_icon")
            
            # [방법 1] ActionChains로 아이콘 정중앙 클릭 (가장 사람 같음)
            actions = ActionChains(driver)
            actions.move_to_element(inner_icon).click().perform()
            time.sleep(1.0) # 반응 대기
            
            # [검증] 클릭 후에도 aria-pressed가 false라면? -> JS로 강제 클릭 시도
            if wrapper.get_attribute("aria-pressed") != "true":
                # [방법 2] JS로 아이콘 직접 클릭
                driver.execute_script("arguments[0].click();", inner_icon)
                time.sleep(0.5)

            return "공감 ❤️"
            
        except Exception as e:
            # 내부 아이콘을 못 찾았거나 실패했을 경우 -> 껍데기라도 누르기 (최후의 수단)
            driver.execute_script("arguments[0].click();", wrapper)
            return "공감 ❤️ (Wrapper)"

    except Exception as e:
        return f"공감 실패"

# ==========================================
# 3. 댓글 로직 (대기 시간 단축: 3초 -> 0.5초)
# ==========================================
def process_comment(driver, blog_id):
    try:
        # 1. 댓글 버튼 클릭
        try:
            comment_btn = WebDriverWait(driver, 3).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "button[class*='comment_btn'], a.btn_comment"))
            )
            driver.execute_script("arguments[0].click();", comment_btn)
        except:
            return "댓글 버튼 없음"
        
        # 2. 댓글 목록 로딩 대기
        time.sleep(1.0) # 목록 로딩 (네트워크 빠르면 1.0도 충분)

        # [중복 방지]
        try:
            existing_nicks = driver.find_elements(By.CSS_SELECTOR, "span.u_cbox_nick")
            for nick_el in existing_nicks:
                if MY_NICKNAME == nick_el.text.strip():
                    return f"스킵(이미 댓글 씀: {MY_NICKNAME})"
        except: pass

        # 3. 입력창 찾기
        try:
            input_box = WebDriverWait(driver, 3).until(
                EC.visibility_of_element_located((By.CSS_SELECTOR, ".u_cbox_text_mention, .u_cbox_inbox textarea"))
            )
        except:
            return "댓글 입력창 못찾음"

        # 4. 닉네임 추출 및 입력
        target_nickname = blog_id
        try:
            name_el = driver.find_element(By.CSS_SELECTOR, ".user_name, .blogger_name")
            target_nickname = name_el.text.strip()
        except: pass
        
        final_msg = COMMENT_MSG.format(name=target_nickname)

        actions = ActionChains(driver)
        actions.move_to_element(input_box).click().send_keys(final_msg).perform()
        time.sleep(0.2) # 입력 딜레이 최소화

        # 5. 등록 버튼 클릭
        submit_btn = driver.find_element(By.CSS_SELECTOR, ".u_cbox_btn_upload, .u_cbox_btn_complete")
        driver.execute_script("arguments[0].click();", submit_btn)
        
        # 🚨 [속도 개선] 3초 -> 0.5초로 변경
        # 스팸 알림은 보통 누르자마자 뜹니다. 0.5초만 봐도 충분합니다.
        try:
            WebDriverWait(driver, 0.5).until(EC.alert_is_present())
            alert = driver.switch_to.alert
            alert_text = alert.text
            alert.accept() # 닫기
            
            if "차단" in alert_text or "스팸" in alert_text:
                return f"실패(스팸차단됨)"
            return f"실패(알림: {alert_text})"
            
        except TimeoutException:
            # 0.5초 안에 안 떴으면 성공으로 간주하고 바로 리턴
            pass

        # 등록 완료되는 시간 아주 잠깐 대기 (너무 빨리 닫으면 등록 안됨)
        time.sleep(1.0) 
        return "댓글 💬"

    except Exception as e:
        return f"댓글 실패"

# ==========================================
# 메인 통합 로직
# ==========================================
# 이 줄을 파일 맨 위에 추가해야 합니다 (없다면)
def main():
    print("===================================", flush=True)
    print("🚀 봇 가동 시퀀스 시작", flush=True)
    print("===================================", flush=True)
    
    driver = connect_debugger_driver()
    if not driver:
        print("❌ 드라이버 연결 실패로 종료합니다.", flush=True)
        return

    # 메인 윈도우 핸들 저장 (ID)
    main_window = driver.current_window_handle
    
    my_id_clean = MY_BLOG_ID.strip().lower()
    BLACKLIST = {"myblog", "postlist", "buddyaddform", "likeit", "nvisitor", "blog", "domainid", "admin"}
    
    print(f"📋 설정 확인: 타겟 {TARGET_COUNT}명 / 제외 ID '{MY_BLOG_ID}'", flush=True)

    success_cnt = 0
    processed_ids = set()
    queue = []

    while success_cnt < TARGET_COUNT:
        # [A] 대기열 보충
        if not queue:
            print(f"🔄 대기열이 비었습니다. ID 수집을 시작합니다... (현재 처리완료: {len(processed_ids)}명)", flush=True)
            
            try:
                # 메인 탭으로 전환하기 전에 브라우저가 살아있는지 확인
                if not driver.window_handles:
                    print("❌ 브라우저가 닫혀있습니다. 종료합니다.", flush=True)
                    return
                driver.switch_to.window(main_window)
            except Exception as e:
                print(f"❌ 메인 탭 접근 불가 (종료됨): {e}", flush=True)
                return
            
            for i in range(3):
                print(f"   ⬇️ 스크롤 내리는 중 ({i+1}/3)...", flush=True)
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(0.5)

            found_count = 0
            for link in driver.find_elements(By.TAG_NAME, "a"):
                try:
                    href = link.get_attribute("href")
                    if href and "blog.naver.com" in href:
                        match = re.search(r'blog\.naver\.com\/([a-zA-Z0-9_-]+)', href)
                        if match:
                            bid = match.group(1)
                            bid_l = bid.lower()
                            if bid_l in BLACKLIST or bid_l == my_id_clean: continue
                            if bid not in processed_ids and len(bid) > 3:
                                queue.append(bid)
                                processed_ids.add(bid)
                                found_count += 1
                except: continue
            
            print(f"   ✅ {found_count}개의 새로운 ID 발견! (현재 대기열: {len(queue)}명)", flush=True)
            
            if not queue:
                print("⚠️ 더 이상 수집할 블로그가 없습니다. 종료합니다.", flush=True)
                break

        # [B] 작업 시작
        blog_id = queue.pop(0)
        if blog_id.lower() == my_id_clean or blog_id.lower() in BLACKLIST: continue

        print(f"\n▶️ [{success_cnt+1}/{TARGET_COUNT}] '{blog_id}' 작업 시작", flush=True)
        
        # 1. 새 탭 열기 (Selenium 내장 기능 사용 - 가장 안정적)
        try:
            # 탭을 열면서 동시에 스위치까지 한 번에 처리
            driver.switch_to.new_window('tab')
            
            # 주소 이동
            driver.get(f"https://m.blog.naver.com/{blog_id}")
            
        except Exception as e:
            print(f"   ⚠️ 탭 진입 실패({blog_id}): {e}", flush=True)
            # 실패 시 현재 탭 닫고 메인으로 복귀 시도
            try: 
                if len(driver.window_handles) > 1: driver.close()
                driver.switch_to.window(main_window)
            except: pass
            continue

        time.sleep(1.0)

        # 🚨 [MobileErrorView 처리 수정] - 여기가 문제였음
        if "MobileErrorView" in driver.current_url or "일시적인 오류" in driver.page_source:
            print(f"   ❌ 접근 불가/차단된 블로그 (Skip)", flush=True)
            try:
                # [핵심] 현재 탭이 메인 탭이 아닐 때만 닫는다!
                if driver.current_window_handle != main_window and len(driver.window_handles) > 1:
                    driver.close()
                driver.switch_to.window(main_window)
            except Exception as e:
                print(f"   ⚠️ 탭 닫기 중 오류 발생 (무시하고 진행): {e}", flush=True)
                try: driver.switch_to.window(main_window)
                except: return # 메인 탭도 없으면 종료
            continue

        # 2. 서이추 실행
        is_friend, msg_friend = process_neighbor(driver, blog_id)
        
        if is_friend == "DONE_DAY_LIMIT":
            print(f"\n🎉🎉🎉 목표 달성! 오늘 할당량을 모두 채웠습니다. 🎉🎉🎉", flush=True)
            try:
                if driver.current_window_handle != main_window: driver.close()
                driver.switch_to.window(main_window)
            except: pass
            break
            
        if is_friend == "STOP_GROUP_FULL":
            print(f"\n⛔ 내 이웃 그룹이 가득 찼습니다. 정리 후 실행하세요.", flush=True)
            try:
                if driver.current_window_handle != main_window: driver.close()
                driver.switch_to.window(main_window)
            except: pass
            break

        print(f"   └ 서이추: {msg_friend}", flush=True)

        # 3. 홈 복귀
        if "BuddyAddForm" in driver.current_url:
            driver.get(f"https://m.blog.naver.com/{blog_id}")
            time.sleep(0.8)

        # 4. 공감 & 댓글
        if "실패" not in msg_friend and "에러" not in msg_friend and "스킵" not in msg_friend:
            msg_like = process_like(driver)
            print(f"   └ 공감: {msg_like}", flush=True)

            if "실패" in msg_like or "없음" in msg_like:
                print("   └ 댓글: 스킵(공감 실패)", flush=True)
            else:
                msg_cmt = process_comment(driver, blog_id)
                print(f"   └ 댓글: {msg_cmt}", flush=True)

            if is_friend is True: success_cnt += 1

        # 5. 탭 닫기 (안전장치 강화)
        try:
            # 알림창 있으면 닫기
            try: driver.switch_to.alert.accept()
            except: pass
            
            # 메인 탭이 아닐 때만 close
            if driver.current_window_handle != main_window and len(driver.window_handles) > 1:
                driver.close()
                
        except Exception as e:
            # 이미 닫혔거나 에러나면 무시
            pass

        # 메인 탭 복귀
        try:
            driver.switch_to.window(main_window)
        except Exception as e:
            print("❌ 메인 탭으로 돌아갈 수 없습니다. (브라우저 종료됨)", flush=True)
            return

        wait_t = random.uniform(0.5, 1.2)
        time.sleep(wait_t)

    print("🎉 프로그램 종료", flush=True)

if __name__ == "__main__":
    main()