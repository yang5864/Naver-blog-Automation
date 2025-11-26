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
# [User Settings]
# ==========================================
TARGET_COUNT = 100          
APPLY_MESSAGE = "블로그 스타일이 너무 좋아요! 저도 다양한 주제로 글 쓰고 있어서 함께 소통하면 좋을 것 같아 이웃 신청드립니다:)"
# ==========================================

def connect_debugger_driver():
    chrome_options = Options()
    chrome_options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")
    # [Speed] 'eager' strategy loads DOM content only, skipping heavy images
    chrome_options.page_load_strategy = 'eager' 
    try:
        return webdriver.Chrome(options=chrome_options)
    except:
        return None

def extract_blog_ids(driver):
    ids = set()
    try:
        # [Speed] Filter links via CSS Selector in the browser engine (much faster than Python loop)
        driver.implicitly_wait(0.1)
        links = driver.find_elements(By.CSS_SELECTOR, "a[href*='blog.naver.com']")
        
        for link in links:
            try:
                url = link.get_attribute("href")
                # Regex extraction remains same
                match = re.search(r'blog\.naver\.com\/([a-zA-Z0-9_-]+)', url)
                if match:
                    b_id = match.group(1)
                    if len(b_id) > 3: ids.add(b_id)
            except: continue
    except: pass
    finally:
        driver.implicitly_wait(3) # Restore default wait
    return list(ids)

def prepare_enough_ids(driver, target_need, collected_ids):
    retry_scroll = 0
    while True:
        current_ids = extract_blog_ids(driver)
        new_ids_count = len([i for i in current_ids if i not in collected_ids])
        print(f"   >>> Loaded IDs: {len(current_ids)} (New: {new_ids_count})")
        if new_ids_count >= 30: return current_ids
        
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        # [Speed] Reduced scroll wait time
        time.sleep(1.2)
        retry_scroll += 1
        if retry_scroll > 10: return current_ids

def check_alert(driver):
    try:
        # [Speed] Check for alert almost instantly (0.1s)
        WebDriverWait(driver, 0.1).until(EC.alert_is_present())
        alert = driver.switch_to.alert
        text = alert.text
        alert.accept()
        return text
    except: return None

def check_html_limit_popup(driver):
    """Check for 5000 limit popup via JS"""
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
    """Check for 'Request in progress' popup via JS"""
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
    """Find 'Add Neighbor' button using JS/XPath"""
    try:
        # [Speed] Try clicking the data-click-area first (Most accurate & fast)
        btn = driver.execute_script("""
            var btn = document.querySelector("[data-click-area*='add']");
            if(btn) { btn.click(); return true; }
            return false;
        """)
        if btn: return True

        # Fallback: Text search
        xpath = "//*[contains(text(), '이웃추가')]"
        elements = driver.find_elements(By.XPATH, xpath)
        for elem in elements:
            if not elem.is_displayed(): continue
            driver.execute_script("arguments[0].click();", elem)
            return True
    except: return False
    return False

def process_neighbor_natural(driver, blog_id):
    try:
        driver.execute_script("window.open('');")
        driver.switch_to.window(driver.window_handles[-1])
        
        # 1. Go to Profile
        driver.get(f"https://m.blog.naver.com/{blog_id}")
        # [Speed] Removed fixed sleep. Immediate check.

        # 2. Check Block/Error/Already Neighbor via Page Source (Fastest)
        src = driver.page_source
        if "MobileErrorView" in driver.current_url: return "BLOCK_DETECTED", "Error Page"
        if "이웃끊기" in src or ">이웃<" in src or "서로이웃<" in src: return False, "Skip (Already Neighbor)"

        # 3. Click Button
        if not click_neighbor_button_recursive(driver):
            return False, "Skip (Button Not Found)"

        # Check popups immediately
        if check_layer_popup_loading(driver): return False, "Skip (In Progress)"
        
        alert_msg = check_alert(driver)
        if alert_msg:
            if "신청" in alert_msg: return False, "Skip (In Progress)"
            if "5000" in alert_msg or "초과" in alert_msg: return False, "Fail (Limit Reached)"
            if "하루" in alert_msg or "100명" in alert_msg: return "DONE_DAY", "Limit Reached"
            return False, f"Skip ({alert_msg})"

        # 4. Wait for Form & Select Option (JS One-Shot)
        try:
            # Wait max 2s for form to appear
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
            
            if js_result == 'BLOCKED': return False, "Skip (Blocked)"
            if js_result == 'NOT_FOUND': return False, "Skip (Load Fail)"

        except TimeoutException:
            # Only use fallback URL injection if normal flow fails
            driver.get(f"https://m.blog.naver.com/BuddyAddForm.naver?blogId={blog_id}")
            try:
                WebDriverWait(driver, 2.0).until(EC.presence_of_element_located((By.ID, "bothBuddyRadio")))
            except:
                return False, "Skip (Timeout)"

        # 5. Message Input (With Fix)
        if "5000" in driver.page_source and "초과" in driver.page_source: return False, "Fail (Limit)"

        try:
            textarea = WebDriverWait(driver, 2).until(EC.presence_of_element_located((By.TAG_NAME, "textarea")))
            
            # [Fix] Force update value and trigger events
            driver.execute_script("""
                var el = arguments[0];
                var txt = arguments[1];
                el.value = txt;
                el.dispatchEvent(new Event('input', { bubbles: true }));
                el.dispatchEvent(new Event('change', { bubbles: true }));
                el.dispatchEvent(new Event('blur', { bubbles: true }));
            """, textarea, APPLY_MESSAGE)
            
        except: pass

        # 6. Click Confirm
        try:
            confirm_btn = driver.find_element(By.XPATH, "//*[text()='확인']")
            driver.execute_script("arguments[0].click();", confirm_btn)
        except: return False, "Fail (No Confirm Btn)"

        # Final Check
        if check_html_limit_popup(driver): return False, "Fail (5000 Limit)"

        final_alert = check_alert(driver)
        if final_alert:
            if "완료" in final_alert or "보냈습니다" in final_alert: return True, "Success"
            if "하루" in final_alert: return "DONE_DAY", "Daily Limit"
            return False, f"Fail ({final_alert})"

        return True, "Success"

    except Exception as e:
        return False, f"Error ({str(e)[:20]})"
    
    finally:
        try:
            if len(driver.window_handles) > 1: driver.close()
            driver.switch_to.window(driver.window_handles[0])
        except: pass

def main():
    driver = connect_debugger_driver()
    if not driver:
        print("❌ Chrome Connection Failed")
        return

    print("⚡️ Neighbor Bot (Speed Optimized)")
    print(f"🎯 Target: {TARGET_COUNT}")

    success_count = 0
    processed_ids = set()

    while success_count < TARGET_COUNT:
        print("\n🔄 Refreshing List...")
        current_batch = prepare_enough_ids(driver, 30, processed_ids)
        new_ids = [i for i in current_batch if i not in processed_ids]
        
        print(f"🔍 Queue: {len(new_ids)}")
        
        if not new_ids:
            print("   No more IDs found.")
            break

        for blog_id in new_ids:
            if success_count >= TARGET_COUNT: break
            
            processed_ids.add(blog_id)
            res, msg = process_neighbor_natural(driver, blog_id)
            
            if res == "BLOCK_DETECTED":
                print(f"\n🚨 {msg} -> Waiting 30s...")
                time.sleep(30)
                continue
            
            elif res == "DONE_DAY":
                print(f"\n🎉 {msg}")
                return
            elif res is True:
                success_count += 1
                print(f"✅ [{success_count}] {blog_id}: {msg}")
            else:
                print(f"   ❌ {blog_id}: {msg}")
            
            # Minimized delay for speed
            time.sleep(random.uniform(0.8, 1.5))

    print(f"🎉 Finished!")

if __name__ == "__main__":
    main()