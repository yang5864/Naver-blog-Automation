import time
import random
import re
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

# ==========================================
# [사용자 설정]
# ==========================================
TARGET_COUNT = 100          
APPLY_MESSAGE = "블로그 스타일이 너무 좋아요! 저도 다양한 주제로 글 쓰고 있어서 함께 소통하면 좋을 것 같아 이웃 신청드립니다:)"
# ==========================================

def connect_debugger_driver():
    chrome_options = Options()
    chrome_options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")
    chrome_options.page_load_strategy = 'eager' 
    try:
        return webdriver.Chrome(options=chrome_options)
    except:
        return None

def extract_blog_ids(driver):
    ids = set()
    try:
        driver.implicitly_wait(0.5)
        links = driver.find_elements(By.TAG_NAME, "a")
        for link in links:
            try:
                url = link.get_attribute("href")
                if url and "blog.naver.com" in url:
                    match = re.search(r'blog\.naver\.com\/([a-zA-Z0-9_-]+)', url)
                    if match:
                        b_id = match.group(1)
                        if len(b_id) > 3: ids.add(b_id)
            except: continue
    except: pass
    finally:
        driver.implicitly_wait(5)
    return list(ids)

def prepare_enough_ids(driver, target_need, collected_ids):
    retry_scroll = 0
    while True:
        current_ids = extract_blog_ids(driver)
        new_ids_count = len([i for i in current_ids if i not in collected_ids])
        print(f"   >>> 현재 로딩된 ID {len(current_ids)}개 (신규: {new_ids_count}개)")
        if new_ids_count >= 30: return current_ids
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(1.5)
        retry_scroll += 1
        if retry_scroll > 10: return current_ids

def check_alert(driver):
    try:
        WebDriverWait(driver, 0.3).until(EC.alert_is_present())
        alert = driver.switch_to.alert
        text = alert.text
        alert.accept()
        return text
    except: return None

def check_html_limit_popup(driver):
    try:
        return driver.execute_script("""
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

def check_layer_popup_loading(driver):
    try:
        return driver.execute_script("""
            var xpath = "//*[contains(text(), '서로이웃 신청 진행중')]";
            var popup = document.evaluate(xpath, document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
            if (popup) {
                var cancelXpath = "//button[contains(text(), '취소')] | //a[contains(text(), '취소')]";
                var cancelBtn = document.evaluate(cancelXpath, document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
                if (cancelBtn) cancelBtn.click();
                return true;
            }
            return false;
        """)
    except: return False

def click_neighbor_button_recursive(driver):
    """텍스트 기반 버튼 탐색 및 클릭"""
    try:
        xpath = "//*[contains(text(), '이웃추가')]"
        elements = driver.find_elements(By.XPATH, xpath)
        for elem in elements:
            if not elem.is_displayed(): continue
            parent = elem
            clicked = False
            for _ in range(5):
                tag = parent.tag_name.lower()
                if tag in ['a', 'button'] or parent.get_attribute("onclick") or parent.get_attribute("role") == "button":
                    driver.execute_script("arguments[0].click();", parent)
                    clicked = True
                    break
                try: parent = parent.find_element(By.XPATH, "..")
                except: break
            if clicked: return True
            driver.execute_script("arguments[0].click();", elem)
            return True
    except: return False
    return False

def process_neighbor_natural(driver, blog_id):
    try:
        driver.execute_script("window.open('');")
        driver.switch_to.window(driver.window_handles[-1])
        
        # 1. [정석] 프로필 페이지로 먼저 이동
        driver.get(f"https://m.blog.naver.com/{blog_id}")
        time.sleep(1.0) # 로딩 대기

        # 2. [차단 감지] 일시적인 오류 페이지인지 확인
        if "MobileErrorView" in driver.current_url or "일시적인 오류" in driver.page_source:
            return "BLOCK_DETECTED", "차단 감지(일시적 오류)"

        # 3. 이미 이웃인지 확인
        src = driver.page_source
        if "이웃끊기" in src or ">이웃<" in src or "서로이웃<" in src:
            return False, "스킵(이미 이웃)"

        # 4. 이웃추가 버튼 클릭 (URL 이동 X -> 클릭 O)
        clicked = False
        
        # 4-1. data-click-area 우선 시도
        try:
            btn = driver.find_element(By.CSS_SELECTOR, "[data-click-area*='add']")
            driver.execute_script("arguments[0].click();", btn)
            clicked = True
        except:
            # 4-2. 텍스트 재귀 탐색
            if click_neighbor_button_recursive(driver):
                clicked = True

        if not clicked:
            return False, "스킵(버튼 못찾음)"

        # --------------------------------------------------------
        # 클릭 후 페이지 전환 대기 및 팝업 체크
        # --------------------------------------------------------
        time.sleep(0.5)
        
        if check_layer_popup_loading(driver): return False, "스킵(서이추 신청 진행중)"
        
        alert_msg = check_alert(driver)
        if alert_msg:
            if "신청" in alert_msg: return False, "스킵(신청중)"
            if "5000" in alert_msg or "초과" in alert_msg: return False, "실패(상대 정원 초과)"
            if "하루" in alert_msg or "100명" in alert_msg: return "DONE_DAY", "완료(한도달성)"
            return False, f"스킵({alert_msg})"

        # --------------------------------------------------------
        # 5. 신청 페이지 로직 (JS 원샷)
        # --------------------------------------------------------
        try:
            # 2초 기다림 (페이지 전환)
            WebDriverWait(driver, 2.0).until(EC.presence_of_element_located((By.ID, "bothBuddyRadio")))
            
            js_result = driver.execute_script("""
                try {
                    var radio = document.getElementById('bothBuddyRadio');
                    var label = document.querySelector("label[for='bothBuddyRadio']");
                    var cancelBtn = document.evaluate("//*[text()='취소']", document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
                    
                    if (!radio || !label) return 'NOT_FOUND';
                    if (radio.disabled || radio.getAttribute('ng-disabled') == 'true') {
                        if(cancelBtn) cancelBtn.click();
                        return 'BLOCKED';
                    }
                    label.click();
                    return 'SUCCESS';
                } catch(e) { return 'JS_ERROR'; }
            """)
            
            if js_result == 'BLOCKED': return False, "스킵(서로이웃 막힘)"
            if js_result == 'NOT_FOUND': return False, "스킵(로딩 실패/옵션 없음)"

        except TimeoutException:
            # 클릭했는데 안 넘어갔으면 -> 여기서만 구조대(URL이동) 사용 (최후의 수단)
            driver.get(f"https://m.blog.naver.com/BuddyAddForm.naver?blogId={blog_id}")
            try:
                WebDriverWait(driver, 2.0).until(EC.presence_of_element_located((By.ID, "bothBuddyRadio")))
            except:
                return False, "스킵(로딩 Timeout)"

        # -------------------------------------------------------
        # 6. 메시지 전송 (수정됨)
        # -------------------------------------------------------
        if "5000" in driver.page_source and "초과" in driver.page_source: return False, "실패(상대 정원 초과)"

        try:
            # 텍스트 영역 찾기
            textarea = WebDriverWait(driver, 2).until(EC.visibility_of_element_located((By.TAG_NAME, "textarea")))
            
            # [핵심 수정] 값 입력 후 'input' 이벤트를 강제로 발생시켜야 네이버가 인식함
            driver.execute_script("""
                var el = arguments[0];
                var txt = arguments[1];
                el.value = txt;
                el.dispatchEvent(new Event('input', { bubbles: true }));
                el.dispatchEvent(new Event('change', { bubbles: true }));
                el.dispatchEvent(new Event('blur', { bubbles: true }));
            """, textarea, APPLY_MESSAGE)
            
        except: 
            # JS 실패 시, 최후의 수단으로 타이핑 시도 (느리지만 확실함)
            try:
                textarea.click()
                textarea.clear()
                textarea.send_keys(APPLY_MESSAGE)
            except: pass

        try:
            confirm_btn = driver.find_element(By.XPATH, "//*[text()='확인']")
            driver.execute_script("arguments[0].click();", confirm_btn)
        except: return False, "실패(확인 버튼 없음)"

        # 최종 검증
        if check_html_limit_popup(driver): return False, "실패(상대 정원 5000명 초과)"

        final_alert = check_alert(driver)
        if final_alert:
            if "완료" in final_alert or "보냈습니다" in final_alert: return True, "성공"
            if "그룹" in final_alert and "가득" in final_alert: return "STOP_ERROR", f"중단(그룹꽉참)"
            if "하루" in final_alert or "100명" in final_alert: return "DONE_DAY", "완료(한도달성)"
            if "5,000" in final_alert or "초과" in final_alert: return False, f"실패(상대 5000명 초과)"
            return False, f"실패(알림: {final_alert})"

        return True, "성공"

    except Exception as e:
        return False, f"에러({str(e)[:20]})"
    
    finally:
        try:
            if len(driver.window_handles) > 1: driver.close()
            driver.switch_to.window(driver.window_handles[0])
        except: pass

def main():
    driver = connect_debugger_driver()
    if not driver:
        print("❌ 크롬 연결 실패")
        return

    print("🍃 서이추 봇 (Natural 모드: 프로필 경유 + 차단 감지)")
    print(f"🎯 목표: {TARGET_COUNT}명")

    success_count = 0
    processed_ids = set()

    while success_count < TARGET_COUNT:
        print("\n🔄 목록 갱신 중...")
        current_batch = prepare_enough_ids(driver, 30, processed_ids)
        new_ids = [i for i in current_batch if i not in processed_ids]
        
        print(f"🔍 대기열: {len(new_ids)}명")
        
        if not new_ids:
            print("   더 이상 ID가 없습니다.")
            break

        for blog_id in new_ids:
            if success_count >= TARGET_COUNT: break
            
            processed_ids.add(blog_id)
            res, msg = process_neighbor_natural(driver, blog_id)
            
            # [중요] 차단 감지 시 쿨타임 적용
            if res == "BLOCK_DETECTED":
                print(f"\n🚨 {msg} -> 30초간 대기 후 재시도합니다...")
                time.sleep(30)
                continue # 이번 ID는 넘어가고 다음부터 다시
            
            elif res == "DONE_DAY":
                print(f"\n🎉 {msg}")
                return
            elif res == "STOP_ERROR":
                print(f"\n⛔ {msg}")
                return
            elif res is True:
                success_count += 1
                print(f"✅ [{success_count}] {blog_id}: {msg}")
            else:
                print(f"   ❌ {blog_id}: {msg}")
            
            # 봇 탐지 회피를 위한 랜덤 대기 (1.5초 ~ 2.5초)
            time.sleep(random.uniform(1.5, 2.5))

    print(f"🎉 완료!")

if __name__ == "__main__":
    main()