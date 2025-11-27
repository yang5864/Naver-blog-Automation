import time
import random
import re
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchWindowException

# ==========================================
# [사용자 설정]
# ==========================================
TARGET_COUNT = 100          
APPLY_MESSAGE = "블로그 스타일이 너무 좋아요! 저도 다양한 주제로 글 쓰고 있어서 함께 소통하면 좋을 것 같아 이웃 신청드립니다:)"
# ==========================================

def connect_debugger_driver():
    """실행 중인 크롬에 연결"""
    chrome_options = Options()
    chrome_options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")
    chrome_options.page_load_strategy = 'eager' 
    try:
        return webdriver.Chrome(options=chrome_options)
    except:
        return None

def collect_ids_from_current_page(driver):
    """현재 페이지(검색결과)에서 ID만 추출하여 리스트로 반환"""
    ids = set()
    try:
        # 검색결과 탭인지 확인을 위해 짧게 대기
        driver.implicitly_wait(0.5)
        links = driver.find_elements(By.TAG_NAME, "a")
        for link in links:
            try:
                url = link.get_attribute("href")
                if url and "blog.naver.com" in url:
                    # blog.naver.com/아이디 형식 추출
                    match = re.search(r'blog\.naver\.com\/([a-zA-Z0-9_-]+)', url)
                    if match:
                        b_id = match.group(1)
                        if len(b_id) > 3: ids.add(b_id)
            except: continue
    except: pass
    finally:
        driver.implicitly_wait(5)
    return list(ids)

def perform_scroll_and_load(driver):
    """메인 탭에서 스크롤을 내려 새로운 내용을 로딩"""
    try:
        prev_height = driver.execute_script("return document.body.scrollHeight")
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(1.5) # 로딩 대기
        curr_height = driver.execute_script("return document.body.scrollHeight")
        
        # 스크롤이 더 이상 내려가지 않으면 False 반환
        return curr_height > prev_height
    except:
        return False

# =========================================================
# 서이추 로직 (새 탭 내부에서 동작)
# =========================================================
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
    """이웃추가 버튼을 재귀적으로 찾아 클릭"""
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

def process_logic_in_tab(driver, blog_id):
    """
    이미 새 탭이 열려있고, 해당 탭으로 포커스가 맞춰진 상태에서 실행되는 로직
    """
    try:
        # [차단 감지] 일시적인 오류 페이지 확인
        if "MobileErrorView" in driver.current_url or "일시적인 오류" in driver.page_source:
            return "BLOCK_DETECTED", "차단 감지(일시적 오류)"

        # 이미 이웃인지 확인
        src = driver.page_source
        if "이웃끊기" in src or ">이웃<" in src or "서로이웃<" in src:
            return False, "스킵(이미 이웃)"

        # 이웃추가 버튼 클릭
        clicked = False
        try:
            btn = driver.find_element(By.CSS_SELECTOR, "[data-click-area*='add']")
            driver.execute_script("arguments[0].click();", btn)
            clicked = True
        except:
            if click_neighbor_button_recursive(driver):
                clicked = True

        if not clicked: return False, "스킵(버튼 못찾음)"

        time.sleep(0.5)
        
        # 팝업 체크
        if check_layer_popup_loading(driver): return False, "스킵(서이추 신청 진행중)"
        alert_msg = check_alert(driver)
        if alert_msg:
            if "신청" in alert_msg: return False, "스킵(신청중)"
            if "5000" in alert_msg or "초과" in alert_msg: return False, "실패(상대 정원 초과)"
            if "하루" in alert_msg or "100명" in alert_msg: return "DONE_DAY", "완료(한도달성)"
            return False, f"스킵({alert_msg})"

        # 신청 페이지 로직 (Javascript)
        try:
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
            # 타임아웃 시 URL 강제 이동 시도
            driver.get(f"https://m.blog.naver.com/BuddyAddForm.naver?blogId={blog_id}")
            try: WebDriverWait(driver, 2.0).until(EC.presence_of_element_located((By.ID, "bothBuddyRadio")))
            except: return False, "스킵(로딩 Timeout)"

        # 메시지 입력
        try:
            textarea = WebDriverWait(driver, 2).until(EC.visibility_of_element_located((By.TAG_NAME, "textarea")))
            driver.execute_script("""
                var el = arguments[0];
                var txt = arguments[1];
                el.value = txt;
                el.dispatchEvent(new Event('input', { bubbles: true }));
                el.dispatchEvent(new Event('change', { bubbles: true }));
                el.dispatchEvent(new Event('blur', { bubbles: true }));
            """, textarea, APPLY_MESSAGE)
        except:
            try:
                textarea.click()
                textarea.send_keys(APPLY_MESSAGE)
            except: pass

        # 확인 버튼 클릭
        try:
            confirm_btn = driver.find_element(By.XPATH, "//*[text()='확인']")
            driver.execute_script("arguments[0].click();", confirm_btn)
        except: return False, "실패(확인 버튼 없음)"

        # 최종 결과 확인
        if check_html_limit_popup(driver): return False, "실패(상대 정원 5000명 초과)"
        final_alert = check_alert(driver)
        if final_alert:
            if "완료" in final_alert or "보냈습니다" in final_alert: return True, "성공"
            if "그룹" in final_alert and "가득" in final_alert: return "STOP_ERROR", f"중단(그룹꽉참)"
            if "하루" in final_alert or "100명" in final_alert: return "DONE_DAY", "완료(한도달성)"
            return False, f"실패(알림: {final_alert})"

        return True, "성공"

    except Exception as e:
        return False, f"에러({str(e)[:20]})"

# =========================================================
# 메인 실행부 (구조 개선됨)
# =========================================================
def main():
    driver = connect_debugger_driver()
    if not driver:
        print("❌ 크롬 연결 실패")
        return

    # [중요] 시작 시점의 윈도우 핸들(검색결과 탭)을 메인으로 저장
    main_window_handle = driver.current_window_handle
    print(f"📍 메인 탭 설정 완료: {driver.title}")

    print("🍃 서이추 봇 시작 (탭 분리 모드)")
    print(f"🎯 목표: {TARGET_COUNT}명")

    success_count = 0
    processed_ids = set()
    candidate_queue = [] # 작업할 ID 대기열

    while success_count < TARGET_COUNT:
        # 1. 대기열에 아이디가 부족하면 메인 탭에서 수집
        if len(candidate_queue) == 0:
            print("\n🔄 추가 ID 수집을 위해 메인 탭으로 이동...")
            
            # 메인 탭으로 확실하게 전환
            driver.switch_to.window(main_window_handle)
            
            # 스크롤을 내리며 새로운 아이디 찾기
            attempts = 0
            while len(candidate_queue) < 5 and attempts < 10: # 최소 5개 이상 찾을 때까지 스크롤
                new_ids = collect_ids_from_current_page(driver)
                # 이미 처리한 ID 제외하고 큐에 추가
                for nid in new_ids:
                    if nid not in processed_ids and nid not in candidate_queue:
                        candidate_queue.append(nid)
                
                if len(candidate_queue) < 5:
                    print(f"   [스크롤 {attempts+1}] 현재 대기열: {len(candidate_queue)}개 - 더 로딩합니다.")
                    scrolled = perform_scroll_and_load(driver)
                    if not scrolled:
                        print("   ⚠️ 더 이상 스크롤할 수 없습니다 (페이지 끝).")
                        break
                    attempts += 1
            
            print(f"✅ 수집 완료. 대기열: {len(candidate_queue)}명")
            
            if not candidate_queue:
                print("🏁 더 이상 작업할 블로그가 없습니다. 종료합니다.")
                break

        # 2. 대기열에서 아이디 꺼내서 작업 (새 탭 열기 -> 작업 -> 닫기)
        blog_id = candidate_queue.pop(0)
        processed_ids.add(blog_id)

        # 새 탭 열기 (URL 바로 이동)
        driver.execute_script(f"window.open('https://m.blog.naver.com/{blog_id}');")
        
        # 새로 열린 탭으로 포커스 이동 (가장 최근 핸들)
        driver.switch_to.window(driver.window_handles[-1])

        # 작업 수행
        res, msg = process_logic_in_tab(driver, blog_id)

        # 탭 닫기
        driver.close()
        
        # [중요] 메인 탭으로 포커스 복구
        driver.switch_to.window(main_window_handle)

        # 결과 처리
        if res == "BLOCK_DETECTED":
            print(f"\n🚨 {msg} -> 30초간 대기합니다...")
            time.sleep(30)
        elif res == "DONE_DAY":
            print(f"\n🎉 {msg}")
            return
        elif res == "STOP_ERROR":
            print(f"\n⛔ {msg}")
            return
        elif res is True:
            success_count += 1
            print(f"✅ [{success_count}/{TARGET_COUNT}] {blog_id}: {msg}")
        else:
            print(f"   ❌ {blog_id}: {msg}")

        # 랜덤 대기
        time.sleep(random.uniform(1.5, 2.5))

    print(f"🎉 목표 달성 완료!")

if __name__ == "__main__":
    main()