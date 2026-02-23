import time
import random
import re
import os
import subprocess
import platform
import socket
import json
import threading
import urllib.request
import urllib.parse
import urllib.error


from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    WebDriverException,
    NoSuchElementException,
    StaleElementReferenceException,
)

from config import AppConfig

try:
    import websocket
except Exception:
    websocket = None


class NaverBotLogic:
    def __init__(self, config: AppConfig, log_func, progress_func, status_func, gui_window=None):
        self.config = config
        self.driver = None
        self.is_running = False
        self.log = log_func
        self.update_progress = progress_func
        self.update_status = status_func
        self.gui_window = gui_window
        self.target_count = config.get("target_count")
        self.current_count = 0
        self.neighbor_msg = config.get("neighbor_msg")
        self.persona_profile = str(config.get("persona_profile") or "").strip()
        self.gemini_api_key = str(config.get("gemini_api_key") or "").strip()
        self.comment_guide = str(config.get("comment_msg") or "").strip()
        self.gemini_model = str(config.get("gemini_model") or "gemini-2.0-flash").strip()
        self.my_blog_id = str(config.get("my_blog_id") or "").strip()
        self.embed_browser_windows = bool(config.get("embed_browser_windows"))
        self._is_windows = platform.system() == "Windows"
        self._embedded_chrome_hwnd = None
        self._embed_parent_hwnd = None
        self._chrome_process_id = None
        self._chrome_user_data_dir = None
        self._embed_attempt_count = 0
        self._webview2_mode = bool(config.get("use_webview2_panel")) and self._is_windows
        self._cdp_ws = None
        self._cdp_lock = threading.Lock()
        self._cdp_msg_id = 0

        # 성능 설정
        self.page_load_timeout = config.get("page_load_timeout")
        self.element_wait_timeout = config.get("element_wait_timeout")
        self.fast_wait = config.get("fast_wait")
        self.normal_wait = config.get("normal_wait")
        self.slow_wait = config.get("slow_wait")

    # ------------------------------------------------------------------
    # 헬퍼
    # ------------------------------------------------------------------
    def safe_sleep(self, seconds):
        if seconds > 0:
            time.sleep(seconds)

    def set_webview2_mode(self, enabled):
        self._webview2_mode = bool(enabled) and self._is_windows
        if not self._webview2_mode:
            self._close_cdp()

    def _close_cdp(self):
        ws = self._cdp_ws
        self._cdp_ws = None
        self._cdp_msg_id = 0
        if ws:
            try:
                ws.close()
            except Exception:
                pass

    def _get_webview_debug_port(self):
        if self.gui_window:
            host = getattr(self.gui_window, "webview2_host", None)
            if host:
                try:
                    p = int(getattr(host, "debug_port", 0) or 0)
                    if p > 0:
                        return p
                except Exception:
                    pass
        return self._get_debug_port()

    def _read_json_url(self, url):
        with urllib.request.urlopen(url, timeout=2.0) as resp:
            raw = resp.read().decode("utf-8", errors="ignore")
        return json.loads(raw)

    def _pick_cdp_target(self, debug_port):
        try:
            targets = self._read_json_url(f"http://127.0.0.1:{int(debug_port)}/json/list")
        except Exception:
            try:
                targets = self._read_json_url(f"http://127.0.0.1:{int(debug_port)}/json")
            except Exception:
                return None

        if not isinstance(targets, list):
            return None

        page_targets = [t for t in targets if isinstance(t, dict) and t.get("type") == "page"]
        if not page_targets:
            return None

        for t in page_targets:
            url = str(t.get("url") or "")
            if "naver.com" in url:
                return t
        return page_targets[0]

    def _ensure_cdp_connected(self, force_restart=False):
        if websocket is None:
            self.log("❌ CDP 연결 실패: websocket-client 미설치")
            return False

        if self._cdp_ws and not force_restart:
            try:
                _ = self._cdp_eval("return location.href;", timeout=2.0)
                self.driver = self._cdp_ws
                return True
            except Exception:
                self._close_cdp()

        debug_port = self._get_webview_debug_port()
        if debug_port <= 0:
            self.log("❌ CDP 연결 실패: debug port 없음")
            return False

        for _ in range(60):
            if self._is_debug_port_open(debug_port):
                break
            time.sleep(0.2)

        if not self._is_debug_port_open(debug_port):
            self.log(f"❌ CDP 연결 실패: 포트 미오픈 ({debug_port})")
            return False

        target = self._pick_cdp_target(debug_port)
        if not target:
            self.log(f"❌ CDP 연결 실패: page target 없음 ({debug_port})")
            return False

        ws_url = target.get("webSocketDebuggerUrl")
        if not ws_url:
            self.log("❌ CDP 연결 실패: webSocketDebuggerUrl 없음")
            return False

        try:
            self._cdp_ws = self._open_cdp_socket(ws_url)
            self._cdp_msg_id = 0
            try:
                self._cdp_cmd("Runtime.enable", timeout=2.0)
            except Exception:
                pass
            try:
                self._cdp_cmd("Page.enable", timeout=2.0)
            except Exception:
                pass
            try:
                self._cdp_cmd("Network.enable", timeout=2.0)
            except Exception:
                pass
            self.driver = self._cdp_ws
            self.log(f"✅ WebView2 CDP 연결 성공: {debug_port}")
            return True
        except Exception as e:
            self._close_cdp()
            err_text = str(e)
            if "403" in err_text:
                self.log("   ↪ 핸드셰이크 403: Origin 제한 가능성")
            self.log(f"❌ CDP 소켓 연결 실패: {err_text[:180]}")
            return False

    def _open_cdp_socket(self, ws_url):
        strategies = [
            {"suppress_origin": True},
            {"origin": "http://127.0.0.1"},
            {"origin": "http://localhost"},
            {"origin": "null"},
            {},
        ]
        last_error = None
        for extra in strategies:
            try:
                kwargs = {
                    "timeout": 8.0,
                    "enable_multithread": True,
                }
                kwargs.update(extra)
                return websocket.create_connection(ws_url, **kwargs)
            except Exception as e:
                last_error = e
                continue
        if last_error:
            raise last_error
        raise RuntimeError("CDP 소켓 연결 실패")

    def _cdp_cmd(self, method, params=None, timeout=8.0):
        if not self._cdp_ws:
            raise RuntimeError("CDP 미연결")
        with self._cdp_lock:
            self._cdp_msg_id += 1
            req_id = self._cdp_msg_id
            payload = {
                "id": req_id,
                "method": str(method),
                "params": params or {},
            }
            self._cdp_ws.settimeout(timeout)
            self._cdp_ws.send(json.dumps(payload, ensure_ascii=False))
            while True:
                raw = self._cdp_ws.recv()
                data = json.loads(raw)
                if not isinstance(data, dict):
                    continue
                if data.get("id") != req_id:
                    continue
                if "error" in data:
                    err = data.get("error") or {}
                    raise RuntimeError(err.get("message") or str(err))
                return data.get("result") or {}

    def _cdp_eval(self, script, timeout=8.0):
        expr = f"(() => {{ {script} }})()"
        result = self._cdp_cmd(
            "Runtime.evaluate",
            {
                "expression": expr,
                "returnByValue": True,
                "awaitPromise": True,
            },
            timeout=timeout,
        )
        if result.get("exceptionDetails"):
            detail = result["exceptionDetails"]
            text = ""
            if isinstance(detail, dict):
                text = str(detail.get("text") or detail.get("exception", {}).get("description") or "")
            raise RuntimeError(text or "Runtime.evaluate 실패")
        value = (result.get("result") or {}).get("value")
        return value

    def _cdp_navigate(self, url):
        self._cdp_cmd("Page.navigate", {"url": str(url)}, timeout=10.0)
        deadline = time.time() + 15.0
        while time.time() < deadline:
            try:
                state = self._cdp_eval("return document.readyState;", timeout=3.0)
                if state in ("interactive", "complete"):
                    return True
            except Exception:
                pass
            time.sleep(0.2)
        return False

    def _find_text_in_body(self, keyword):
        try:
            body_text = self._cdp_eval("return (document.body && document.body.innerText) ? document.body.innerText : '';", timeout=4.0) or ""
            return str(keyword) in str(body_text)
        except Exception:
            return False

    def _get_current_url(self):
        if self._webview2_mode:
            try:
                return str(self._cdp_eval("return location.href || '';", timeout=3.0) or "")
            except Exception:
                return ""
        try:
            return str(self.driver.current_url or "")
        except Exception:
            return ""

    def _get_page_source(self):
        if self._webview2_mode:
            try:
                return str(
                    self._cdp_eval(
                        "return document.documentElement ? document.documentElement.outerHTML : '';",
                        timeout=5.0,
                    )
                    or ""
                )
            except Exception:
                return ""
        try:
            return str(self.driver.page_source or "")
        except Exception:
            return ""

    def _ensure_my_blog_id(self):
        """my_blog_id가 비어 있으면 로그인 세션으로 자동 감지."""
        if str(self.my_blog_id or "").strip():
            return self.my_blog_id
        if not self.driver:
            return ""
        try:
            if not self.safe_get(self.driver, "https://m.blog.naver.com/MyBlog.naver"):
                return ""
            current_url = self._get_current_url()
            match = re.search(r"m\.blog\.naver\.com\/([a-zA-Z0-9_-]+)", current_url or "", re.IGNORECASE)
            if not match:
                return ""
            detected = (match.group(1) or "").strip()
            detected_lower = detected.lower()
            if detected and detected_lower not in {"myblog", "myblog.naver"}:
                self.my_blog_id = detected
                self.log(f"   ↪ 내 블로그 ID 자동 감지: {self.my_blog_id}")
                return self.my_blog_id
        except Exception:
            pass
        return ""

    def _append_blog_ids_from_links(self, links, processed_ids, queue, blacklist):
        new_count = 0
        my_id_clean = str(self.my_blog_id or "").strip().lower()
        if not isinstance(links, list):
            return new_count
        for href in links:
            try:
                href = str(href or "")
                if not href or "blog.naver.com" not in href:
                    continue
                match = re.search(r"blog\.naver\.com\/([a-zA-Z0-9_-]+)", href)
                if not match:
                    continue
                bid = match.group(1)
                bid_lower = bid.lower()
                if bid_lower in blacklist:
                    continue
                if my_id_clean and bid_lower == my_id_clean:
                    continue
                if bid in processed_ids or len(bid) <= 3:
                    continue
                if bid in queue or bid.isdigit():
                    continue
                queue.append(bid)
                processed_ids.add(bid)
                new_count += 1
            except Exception:
                continue
        return new_count

    def _get_layer_popup_text_webview2(self):
        try:
            return self._cdp_eval(
                """
                var layer = document.getElementById('_alertLayer');
                if (layer && layer.style.display !== 'none') {
                    var dsc = layer.querySelector('.dsc');
                    return dsc ? (dsc.innerText || '').trim() : null;
                }
                return null;
                """,
                timeout=3.0,
            )
        except Exception:
            return None

    def _close_layer_popup_webview2(self):
        try:
            self._cdp_eval(
                """
                var btn = document.getElementById('_alertLayerClose');
                if (btn) { btn.click(); return true; }
                return false;
                """,
                timeout=2.0,
            )
        except Exception:
            pass

    def _process_neighbor_webview2(self, blog_id):
        try:
            src = self._get_page_source()
            if "이웃끊기" in src or "서로이웃 취소" in src:
                return False, "스킵(이미 이웃)"

            clicked = self._cdp_eval(
                """
                try {
                    var addBtn = document.querySelector("[data-click-area='ebc.add']");
                    if (addBtn) { addBtn.click(); return 'CLICKED'; }
                    if (document.querySelector("[data-click-area='ebc.ngr']")) return 'ALREADY';
                    var nodes = Array.from(document.querySelectorAll("a,button,span,div"));
                    var textBtn = nodes.find(function(el){
                        var txt = (el.innerText || el.textContent || '').trim();
                        return txt.indexOf('이웃추가') >= 0;
                    });
                    if (textBtn) { textBtn.click(); return 'CLICKED'; }
                    return 'NONE';
                } catch (e) {
                    return 'ERROR:' + (e && e.message ? e.message : '');
                }
                """,
                timeout=4.0,
            )
            if clicked == "ALREADY":
                return False, "스킵(이미 이웃)"
            if isinstance(clicked, str) and clicked.startswith("ERROR:"):
                return False, f"실패({clicked[:20]})"
            if clicked != "CLICKED":
                return False, "스킵(버튼 없음)"

            self.safe_sleep(0.35)

            src_after = self._get_page_source()
            if "하루에 신청 가능한 이웃수" in src_after and "초과" in src_after:
                try:
                    self._cdp_eval(
                        """
                        var closeBtn = Array.from(document.querySelectorAll("button,a"))
                            .find(function(el){ return (el.innerText || '').indexOf('닫기') >= 0; });
                        if (closeBtn) closeBtn.click();
                        return true;
                        """,
                        timeout=2.0,
                    )
                except Exception:
                    pass
                return "DONE_DAY_LIMIT", "🎉 일일 한도 달성!"

            if "서로이웃 신청 진행중입니다" in src_after:
                try:
                    self._cdp_eval(
                        """
                        var cancelBtn = Array.from(document.querySelectorAll("button,a"))
                            .find(function(el){ return (el.innerText || '').indexOf('취소') >= 0; });
                        if (cancelBtn) cancelBtn.click();
                        return true;
                        """,
                        timeout=2.0,
                    )
                except Exception:
                    pass
                return False, "스킵(이미 신청중)"

            layer_popup = self._get_layer_popup_text_webview2()
            if layer_popup:
                if "하루" in layer_popup and "초과" in layer_popup:
                    return "DONE_DAY_LIMIT", "🎉 일일 한도 달성!"
                if "선택 그룹" in layer_popup:
                    return "STOP_GROUP_FULL", layer_popup
                self._close_layer_popup_webview2()
                if "5,000" in layer_popup or "5000" in layer_popup:
                    return False, "스킵(상대 5000명)"
                return False, f"스킵({layer_popup[:20]})"

            current_url = self._get_current_url()
            if "BuddyAddForm" not in current_url:
                if not self.safe_get(self.driver, f"https://m.blog.naver.com/BuddyAddForm.naver?blogId={blog_id}"):
                    return False, "실패(양식 페이지 로드 실패)"
                self.safe_sleep(1.0)

            page_src = self._get_page_source()
            if "로그인" in page_src and "로그인이 필요" in page_src:
                return False, "실패(로그인 필요)"

            form_state = self._cdp_eval(
                """
                try {
                    var both = document.getElementById('bothBuddyRadio');
                    if (!both) {
                        if (document.getElementById('onewayBuddyRadio')) return 'ONEWAY_ONLY';
                        return 'NO_FORM';
                    }
                    if (both.disabled || both.getAttribute('disabled')) return 'DISABLED';
                    if (!both.checked) {
                        var label = document.querySelector("label[for='bothBuddyRadio']");
                        if (label) label.click();
                        else both.click();
                    }
                    return 'OK';
                } catch (e) {
                    return 'ERROR:' + (e && e.message ? e.message : '');
                }
                """,
                timeout=4.0,
            )
            if form_state == "ONEWAY_ONLY":
                return False, "스킵(서이추 비활성화)"
            if form_state == "NO_FORM":
                if "진행 중" in page_src or "신청중" in page_src:
                    return False, "스킵(이미 신청중)"
                return False, "실패(양식 없음)"
            if form_state == "DISABLED":
                return False, "스킵(서이추 불가)"
            if isinstance(form_state, str) and form_state.startswith("ERROR:"):
                return False, f"실패({form_state[:20]})"

            msg_json = json.dumps(self.neighbor_msg or "")
            self._cdp_eval(
                f"""
                var el = document.querySelector("textarea");
                if (!el) return false;
                el.focus();
                el.value = {msg_json};
                el.dispatchEvent(new Event('input', {{ bubbles: true }}));
                el.dispatchEvent(new Event('change', {{ bubbles: true }}));
                return true;
                """,
                timeout=4.0,
            )

            clicked_confirm = self._cdp_eval(
                """
                var btn = Array.from(document.querySelectorAll("button,a,input[type='button'],input[type='submit']"))
                    .find(function(el){
                        var txt = (el.innerText || el.value || '').trim();
                        return txt === '확인' || txt.indexOf('확인') >= 0;
                    });
                if (!btn) return false;
                btn.click();
                return true;
                """,
                timeout=4.0,
            )
            if not clicked_confirm:
                return False, "실패(확인 버튼 없음)"

            self.safe_sleep(self.fast_wait)

            final_popup = self._get_layer_popup_text_webview2()
            if final_popup:
                if "하루" in final_popup and "초과" in final_popup:
                    return "DONE_DAY_LIMIT", "🎉 일일 한도 달성!"
                if "선택 그룹" in final_popup:
                    return "STOP_GROUP_FULL", final_popup
                self._close_layer_popup_webview2()
                if "5,000" in final_popup or "5000" in final_popup:
                    return False, "스킵(상대 5000명)"
                if "신청" in final_popup or "완료" in final_popup:
                    return True, "신청 완료"
                return False, f"실패({final_popup[:20]})"

            return True, "신청 완료"
        except Exception as e:
            return False, f"에러: {str(e)[:15]}"

    def _close_tab_and_return(self, main_window):
        """현재 탭 닫고 메인 윈도우로 복귀."""
        try:
            if len(self.driver.window_handles) > 1:
                self.driver.close()
            self.driver.switch_to.window(main_window)
        except WebDriverException:
            pass

    def _navigate_to_blog_search(self, keyword):
        """네이버 블로그 검색 페이지로 이동."""
        search_url = f"https://search.naver.com/search.naver?where=blog&query={keyword}"
        if self._webview2_mode:
            if not self._cdp_navigate(search_url):
                return False
            self.safe_sleep(1.0)
            return True
        if not self.safe_get(self.driver, search_url):
            return False
        self.safe_sleep(1.0)
        return True

    def _click_blog_tab(self):
        """검색 결과에서 '블로그' 탭 클릭."""
        if self._webview2_mode:
            for _ in range(5):
                try:
                    clicked_state = self._cdp_eval(
                        """
                        try {
                            var blogTab = null;
                            var tabs = Array.from(document.querySelectorAll("[role='tab'], .tab, .lnb_item a"));
                            for (var i = 0; i < tabs.length; i++) {
                                var txt = (tabs[i].innerText || tabs[i].textContent || '').trim();
                                if (txt.indexOf('블로그') >= 0) {
                                    blogTab = tabs[i];
                                    break;
                                }
                            }
                            if (!blogTab) {
                                var candidates = Array.from(document.querySelectorAll("a[href*='search.naver.com/search.naver']"));
                                blogTab = candidates.find(function(el){
                                    var txt = (el.innerText || el.textContent || '').trim();
                                    return txt.indexOf('블로그') >= 0;
                                }) || null;
                            }
                            if (!blogTab) return "NONE";
                            blogTab.click();
                            return "CLICKED";
                        } catch (e) {
                            return "ERROR";
                        }
                        """,
                        timeout=4.0,
                    )
                    if clicked_state == "CLICKED":
                        self.log("   ↪ '블로그' 탭 클릭...")
                        self.safe_sleep(1.0)
                        return
                except Exception:
                    pass
                self.safe_sleep(0.3)

            # 클릭 실패 시 검색어를 유지한 채 블로그 결과로 강제 이동
            try:
                forced = self._cdp_eval(
                    """
                    try {
                        var q = '';
                        var u = new URL(location.href);
                        q = u.searchParams.get('query') || '';
                        if (!q) {
                            var input = document.querySelector("input[name='query'], input#nx_query");
                            q = input ? (input.value || '').trim() : '';
                        }
                        if (!q) return false;
                        location.href = "https://search.naver.com/search.naver?where=blog&query=" + encodeURIComponent(q);
                        return true;
                    } catch (e) {
                        return false;
                    }
                    """,
                    timeout=4.0,
                )
                if forced:
                    self.log("   ↪ '블로그' 탭 강제 이동...")
                    self.safe_sleep(1.0)
            except Exception:
                pass
            return
        try:
            blog_tab = None
            tabs = self.driver.find_elements(By.CSS_SELECTOR, "[role='tab'], .tab, .lnb_item a")
            for tab in tabs:
                try:
                    if "블로그" in tab.text:
                        blog_tab = tab
                        break
                except (StaleElementReferenceException, NoSuchElementException):
                    continue

            if not blog_tab:
                candidates = self.driver.find_elements(By.XPATH, "//a[contains(text(), '블로그')]")
                for cand in candidates:
                    try:
                        href = (cand.get_attribute("href") or "").lower()
                        if "search.naver.com/search.naver" in href or "where=blog" in href:
                            blog_tab = cand
                            break
                    except (StaleElementReferenceException, NoSuchElementException):
                        continue
                if not blog_tab and candidates:
                    blog_tab = candidates[0]

            if blog_tab:
                self.log("   ↪ '블로그' 탭 클릭...")
                self.safe_click(self.driver, blog_tab)
                self.safe_sleep(1.0)
                return

            # 클릭 실패 시 검색어를 유지한 채 블로그 결과로 강제 이동
            q = ""
            try:
                m = re.search(r"[?&]query=([^&]+)", self.driver.current_url or "")
                if m:
                    q = urllib.parse.unquote_plus(m.group(1))
            except Exception:
                q = ""
            if not q:
                try:
                    q_input = self.driver.find_element(By.CSS_SELECTOR, "input[name='query'], input#nx_query")
                    q = (q_input.get_attribute("value") or "").strip()
                except (NoSuchElementException, StaleElementReferenceException):
                    q = ""
            if q:
                self.log("   ↪ '블로그' 탭 강제 이동...")
                self.safe_get(self.driver, f"https://search.naver.com/search.naver?where=blog&query={q}")
                self.safe_sleep(1.0)
        except (NoSuchElementException, StaleElementReferenceException):
            pass

    # ------------------------------------------------------------------
    # Selenium 유틸
    # ------------------------------------------------------------------
    def safe_get(self, driver, url, max_retries=2):
        if self._webview2_mode:
            for attempt in range(max_retries):
                try:
                    if self._cdp_navigate(url):
                        return True
                except Exception:
                    pass
                if attempt < max_retries - 1:
                    self.safe_sleep(0.5)
            return False
        for attempt in range(max_retries):
            try:
                driver.get(url)
                return True
            except TimeoutException:
                if attempt < max_retries - 1:
                    driver.execute_script("window.stop();")
                else:
                    return False
            except WebDriverException:
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
        except (TimeoutException, NoSuchElementException):
            return None

    def safe_click(self, driver, element):
        try:
            driver.execute_script("arguments[0].click();", element)
            return True
        except WebDriverException:
            try:
                element.click()
                return True
            except WebDriverException:
                return False

    # ------------------------------------------------------------------
    # 크롬 연결
    # ------------------------------------------------------------------
    def _is_debug_port_open(self, port):
        try:
            with socket.create_connection(("127.0.0.1", int(port)), timeout=0.2):
                return True
        except OSError:
            return False

    def _get_debug_port(self):
        return int(self.config.get("chrome_debug_port") or 9222)

    def _get_chrome_user_data_dir(self):
        if self._chrome_user_data_dir:
            return self._chrome_user_data_dir
        self._chrome_user_data_dir = os.path.expanduser("~/ChromeBotData")
        os.makedirs(self._chrome_user_data_dir, exist_ok=True)
        return self._chrome_user_data_dir

    def _is_chrome_widget_window_class(self, class_name):
        return str(class_name).startswith("Chrome_WidgetWin_")

    def _launch_chrome_process(self, debug_port, initial_url=None):
        user_data_dir = self._get_chrome_user_data_dir()
        chrome_path = AppConfig.get_chrome_path()

        self._embedded_chrome_hwnd = None
        self._embed_parent_hwnd = None
        self._embed_attempt_count = 0

        if self.gui_window:
            chrome_x, chrome_y, chrome_width, chrome_height = self._get_browser_bounds(self.gui_window)
        else:
            chrome_x, chrome_y = 800, 0
            chrome_width, chrome_height = 1000, 900

        cmd = [
            chrome_path,
            f"--remote-debugging-port={debug_port}",
            f"--user-data-dir={user_data_dir}",
            "--no-first-run",
            "--no-default-browser-check",
            f"--window-size={chrome_width},{chrome_height}",
            f"--window-position={chrome_x},{chrome_y}",
        ]
        if initial_url:
            cmd.append(initial_url)

        proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self._chrome_process_id = proc.pid
        return True

    def connect_driver(self, force_restart=False, initial_url=None):
        """크롬 연결 (GUI 오른쪽 패널 위치에 배치)"""
        if self._webview2_mode:
            port = self._get_webview_debug_port()
            self.log(f"🌐 WebView2 자동화 연결 시도: {port}")
            try:
                ok = self._ensure_cdp_connected(force_restart=force_restart)
                if ok:
                    self.update_status("브라우저 연결됨", "green")
                    return True
                self.driver = None
                self.update_status("브라우저 연결 실패", "red")
                return False
            except Exception as e:
                self.log(f"❌ WebView2 연결 실패: {str(e)[:60]}")
                self.driver = None
                self.update_status("브라우저 연결 실패", "red")
                return False

        debug_port = self._get_debug_port()

        if self.driver and not force_restart:
            try:
                _ = self.driver.window_handles
                if self.gui_window:
                    self._position_chrome_window(self.gui_window)
                return True
            except WebDriverException:
                self.log("⚠️ 기존 연결이 끊어졌습니다. 재연결합니다...")
                self.driver = None

        self.log("🖥️ 크롬 브라우저 실행 중...")
        try:
            if not self._is_debug_port_open(debug_port):
                self._launch_chrome_process(debug_port, initial_url=initial_url)

            # 디버그 포트가 실제로 열릴 때까지 대기 (최대 15초)
            for _ in range(30):
                if self._is_debug_port_open(debug_port):
                    break
                time.sleep(0.5)

            # 디버그 포트 준비 후 attach
            self.driver = None
            for _ in range(20):
                try:
                    chrome_options = Options()
                    chrome_options.add_experimental_option("debuggerAddress", f"127.0.0.1:{debug_port}")
                    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
                    chrome_options.add_experimental_option("useAutomationExtension", False)
                    chrome_options.page_load_strategy = "eager"
                    self.driver = webdriver.Chrome(options=chrome_options)
                    break
                except WebDriverException:
                    time.sleep(0.5)

            if not self.driver:
                raise RuntimeError("크롬 디버그 포트 연결 실패")

            self.driver.set_page_load_timeout(self.page_load_timeout)

            if self.gui_window:
                self._position_chrome_window(self.gui_window)

            self.log("✅ 브라우저 연결 성공!")
            self.update_status("브라우저 연결됨", "green")
            return True
        except Exception as e:
            self.log(f"❌ 실행 실패: {e}")
            self.driver = None
            self.update_status("브라우저 연결 실패", "red")
            return False

    def _position_chrome_window(self, gui_window=None):
        """크롬 창을 GUI 영역에 맞게 배치 (Windows는 임베드 모드 지원)."""
        if not self.driver:
            return
        if not gui_window:
            gui_window = self.gui_window
        if not gui_window:
            return
        try:
            chrome_x, chrome_y, chrome_width, chrome_height = self._get_browser_bounds(gui_window)
            if self._is_windows and self.embed_browser_windows:
                if self._ensure_chrome_embedded(gui_window, chrome_x, chrome_y, chrome_width, chrome_height):
                    return
                if self._embed_attempt_count <= 3:
                    self.log("⚠️ 임베드 미적용 상태: 외부 창 모드로 동작")
            self.driver.set_window_position(chrome_x, chrome_y)
            self.driver.set_window_size(chrome_width, chrome_height)
        except WebDriverException as e:
            self.log(f"⚠️ 창 위치 조정 실패: {str(e)[:30]}")

    def is_chrome_embedded(self):
        return bool(self._is_windows and self.embed_browser_windows and self._embedded_chrome_hwnd)

    def _get_browser_bounds(self, gui_window):
        if hasattr(gui_window, "get_browser_embed_rect"):
            rx, ry, rw, rh = gui_window.get_browser_embed_rect()
            chrome_x = int(rx)
            chrome_y = int(ry)
            chrome_width = int(rw)
            chrome_height = int(rh)
        else:
            gui_x = gui_window.winfo_x()
            gui_y = gui_window.winfo_y()
            gui_width = gui_window.winfo_width()
            gui_height = gui_window.winfo_height()
            left_panel_width = 420
            padding_x = 15
            chrome_x = gui_x + left_panel_width + padding_x
            chrome_y = gui_y
            chrome_width = gui_width - left_panel_width - (padding_x * 2)
            chrome_height = gui_height
        return chrome_x, chrome_y, chrome_width, chrome_height

    def _ensure_chrome_embedded(self, gui_window, chrome_x, chrome_y, chrome_width, chrome_height):
        if not self._is_windows:
            return False
        try:
            import ctypes
            from ctypes import wintypes
        except Exception:
            return False

        self._embed_attempt_count += 1

        if not hasattr(gui_window, "get_browser_embed_hwnd"):
            if self._embed_attempt_count <= 3:
                self.log("⚠️ 임베드 실패: GUI에 임베드 핸들 getter 없음")
            return False

        target_hwnd = gui_window.get_browser_embed_hwnd()
        if not target_hwnd:
            if self._embed_attempt_count <= 3:
                self.log("⚠️ 임베드 실패: target HWND가 0")
            return False

        embed_client_rect = None
        if hasattr(gui_window, "get_browser_embed_client_rect"):
            embed_client_rect = gui_window.get_browser_embed_client_rect()

        user32 = ctypes.windll.user32
        GWL_STYLE = -16
        GWL_EXSTYLE = -20
        WS_CHILD = 0x40000000
        WS_POPUP = 0x80000000
        WS_CAPTION = 0x00C00000
        WS_THICKFRAME = 0x00040000
        WS_MINIMIZEBOX = 0x00020000
        WS_MAXIMIZEBOX = 0x00010000
        WS_SYSMENU = 0x00080000
        WS_VISIBLE = 0x10000000
        WS_EX_TOOLWINDOW = 0x00000080
        WS_EX_APPWINDOW = 0x00040000
        WS_EX_WINDOWEDGE = 0x00000100
        WS_EX_CLIENTEDGE = 0x00000200
        WS_EX_STATICEDGE = 0x00020000
        SWP_NOZORDER = 0x0004
        SWP_NOACTIVATE = 0x0010
        SWP_FRAMECHANGED = 0x0020
        SWP_SHOWWINDOW = 0x0040
        SW_HIDE = 0
        SW_SHOW = 5
        SW_RESTORE = 9

        if not user32.IsWindow(int(target_hwnd)):
            if self._embed_attempt_count <= 3:
                self.log(f"⚠️ 임베드 실패: target HWND invalid ({int(target_hwnd)})")
            return False

        if self._embed_attempt_count <= 3:
            self.log(
                f"   ↪ 임베드 시도 #{self._embed_attempt_count}: target={int(target_hwnd)}, "
                f"rect=({int(chrome_x)},{int(chrome_y)},{int(chrome_width)},{int(chrome_height)})"
            )

        if self._embedded_chrome_hwnd and not user32.IsWindow(self._embedded_chrome_hwnd):
            self._embedded_chrome_hwnd = None
            self._embed_parent_hwnd = None

        if not self._embedded_chrome_hwnd:
            hwnd = self._find_chrome_hwnd(user32, chrome_x, chrome_y, chrome_width, chrome_height)
            if not hwnd:
                self.log("⚠️ 임베드 실패: Chrome 윈도우를 찾을 수 없음")
                if self._embed_attempt_count <= 3:
                    self.log(f"   ↪ 후보 Chrome 창 수: {self._count_top_level_chrome_windows(user32)}")
                self._recover_chrome_window_position(chrome_x, chrome_y, chrome_width, chrome_height)
                return False
            self.log(f"   ↪ HWND 연결: chrome={int(hwnd)} -> target={int(target_hwnd)}")

            # 임베드 전 즉시 숨겨서 별도 창이 보이는 현상 방지
            user32.ShowWindow(hwnd, SW_HIDE)

            style = user32.GetWindowLongW(hwnd, GWL_STYLE)
            style = (style | WS_CHILD | WS_VISIBLE) & ~WS_POPUP
            style = style & ~WS_CAPTION & ~WS_THICKFRAME & ~WS_MINIMIZEBOX & ~WS_MAXIMIZEBOX & ~WS_SYSMENU
            user32.SetWindowLongW(hwnd, GWL_STYLE, style)
            ex_style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            ex_style = (ex_style | WS_EX_TOOLWINDOW) & ~WS_EX_APPWINDOW & ~WS_EX_WINDOWEDGE & ~WS_EX_CLIENTEDGE & ~WS_EX_STATICEDGE
            user32.SetWindowLongW(hwnd, GWL_EXSTYLE, ex_style)
            user32.SetParent(hwnd, target_hwnd)
            if user32.GetParent(hwnd) != target_hwnd:
                self.log("⚠️ 임베드 실패: SetParent 호출 실패")
                self._embedded_chrome_hwnd = None
                self._embed_parent_hwnd = None
                self._recover_chrome_window_position(chrome_x, chrome_y, chrome_width, chrome_height)
                return False
            self._embedded_chrome_hwnd = hwnd
            self._embed_parent_hwnd = target_hwnd
            self.log("🧩 Windows 내장 브라우저 모드 활성화")

        # 부모가 바뀐 경우 재설정
        if self._embed_parent_hwnd != target_hwnd:
            user32.SetParent(self._embedded_chrome_hwnd, target_hwnd)
            if user32.GetParent(self._embedded_chrome_hwnd) != target_hwnd:
                self._embedded_chrome_hwnd = None
                self._embed_parent_hwnd = None
                return False
            self._embed_parent_hwnd = target_hwnd

        if embed_client_rect:
            x, y, w, h = embed_client_rect
            pos_x = max(0, int(x))
            pos_y = max(0, int(y))
            width = max(1, int(w))
            height = max(1, int(h))
        else:
            pos_x = 0
            pos_y = 0
            width = max(1, int(chrome_width))
            height = max(1, int(chrome_height))

        # 초기 레이아웃 타이밍 이슈로 1px로 고정되는 문제 방지
        if width < 80 or height < 80:
            pos_x = 0
            pos_y = 0
            width = max(300, int(chrome_width))
            height = max(300, int(chrome_height))

        user32.SetWindowPos(
            self._embedded_chrome_hwnd,
            0,
            pos_x,
            pos_y,
            width,
            height,
            SWP_NOACTIVATE | SWP_FRAMECHANGED | SWP_SHOWWINDOW,
        )
        user32.ShowWindow(self._embedded_chrome_hwnd, SW_RESTORE)
        user32.ShowWindow(self._embedded_chrome_hwnd, SW_SHOW)
        return True

    def _count_top_level_chrome_windows(self, user32):
        try:
            import ctypes
            from ctypes import wintypes
        except Exception:
            return 0

        count = {"n": 0}
        EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

        def _callback(hwnd, _lparam):
            class_name = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(hwnd, class_name, 256)
            if not self._is_chrome_widget_window_class(class_name.value):
                return True
            if user32.GetParent(hwnd) != 0:
                return True
            count["n"] += 1
            return True

        user32.EnumWindows(EnumWindowsProc(_callback), 0)
        return int(count["n"])

    def _find_chrome_hwnd(self, user32, expected_x, expected_y, expected_width, expected_height):
        try:
            import ctypes
            from ctypes import wintypes
        except Exception:
            return None

        rect = (expected_x, expected_y, expected_x + expected_width, expected_y + expected_height)
        found = {"hwnd": None, "score": 10**9}
        GW_OWNER = 4

        EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

        def _callback(hwnd, _lparam):
            class_name = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(hwnd, class_name, 256)
            if not self._is_chrome_widget_window_class(class_name.value):
                return True

            # 이미 다른 창에 임베드된 Chrome 창은 제외
            if user32.GetParent(hwnd) != 0:
                return True

            rc = wintypes.RECT()
            if not user32.GetWindowRect(hwnd, ctypes.byref(rc)):
                return True

            # 예상 위치와 가까운 창 우선 선택
            score = abs(rc.left - rect[0]) + abs(rc.top - rect[1])
            if not user32.IsWindowVisible(hwnd):
                score += 2000
            if user32.GetWindow(hwnd, GW_OWNER) != 0:
                score += 1500
            if score < found["score"]:
                found["score"] = score
                found["hwnd"] = hwnd
            return True

        # 연결 직후 창 생성/전환 지연을 고려한 재시도
        for _ in range(15):
            user32.EnumWindows(EnumWindowsProc(_callback), 0)
            if found["hwnd"]:
                return found["hwnd"]
            time.sleep(0.3)
        return None

    def _recover_chrome_window_position(self, chrome_x, chrome_y, chrome_width, chrome_height):
        """임베드 실패 시 숨겨진 Chrome 창을 원래 위치로 복구."""
        # ShowWindow로 숨긴 창 복구
        try:
            import ctypes
            from ctypes import wintypes
            user32 = ctypes.windll.user32

            EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
            def _show_callback(hwnd, _lparam):
                class_name = ctypes.create_unicode_buffer(256)
                user32.GetClassNameW(hwnd, class_name, 256)
                if not self._is_chrome_widget_window_class(class_name.value) or user32.GetParent(hwnd) != 0:
                    return True
                user32.ShowWindow(hwnd, 5)  # SW_SHOW
                return True
            user32.EnumWindows(EnumWindowsProc(_show_callback), 0)
        except Exception:
            pass
        # Selenium으로도 위치 복구
        if not self.driver:
            return
        try:
            self.driver.set_window_position(chrome_x, chrome_y)
            self.driver.set_window_size(chrome_width, chrome_height)
        except WebDriverException:
            pass

    # ------------------------------------------------------------------
    # 로그인 / 검색
    # ------------------------------------------------------------------
    def check_login_status(self):
        if not self.driver:
            return False
        if self._webview2_mode:
            try:
                current_url = self._get_current_url().lower()
                if "nid.naver.com/nidlogin" in current_url:
                    return False
                try:
                    self._cdp_cmd("Network.enable", timeout=2.0)
                except Exception:
                    pass
                cookie_data = self._cdp_cmd(
                    "Network.getCookies",
                    {"urls": ["https://nid.naver.com", "https://m.blog.naver.com", "https://blog.naver.com"]},
                    timeout=4.0,
                )
                cookies = cookie_data.get("cookies") or []
                for cookie in cookies:
                    name = str((cookie or {}).get("name") or "")
                    if name in ("NID_AUT", "NID_SES"):
                        return True
                if self._find_text_in_body("로그아웃"):
                    return True
                return False
            except Exception:
                return False
        try:
            current_url = (self.driver.current_url or "").lower()
            if "nid.naver.com/nidlogin" in current_url:
                return False
            cookies = self.driver.get_cookies()
            for cookie in cookies:
                if cookie.get("name") in ("NID_AUT", "NID_SES"):
                    return True
            return False
        except WebDriverException:
            return False

    def open_login_page(self):
        login_url = "https://nid.naver.com/nidlogin.login"
        home_url = "https://m.blog.naver.com/"

        if not self.connect_driver(initial_url=home_url):
            return False

        try:
            if self.check_login_status():
                self.log("✅ 이전 로그인 세션 감지: 자동 로그인 완료")
                self.update_status("자동 로그인됨", "green")
                try:
                    self.safe_get(self.driver, home_url)
                except Exception:
                    pass
                return True
        except Exception as e:
            self.log(f"⚠️ 로그인 상태 확인 실패: {str(e)[:30]}")

        self.log("🔓 최초 1회 로그인 필요: 네이버 로그인 페이지로 이동합니다.")
        if self.safe_get(self.driver, login_url):
            self.update_status("로그인 페이지", "blue")
            return True

        self.log("❌ 로그인 페이지 이동 실패")
        self.driver = None
        self.update_status("브라우저 오류", "red")
        return False

    def search_keyword(self, keyword):
        if not self.connect_driver():
            return
        self.log(f"🔍 '{keyword}' 검색 중...")
        try:
            if not self._navigate_to_blog_search(keyword):
                self.log("❌ 검색 페이지 이동 실패")
                return
            self._click_blog_tab()
            self.update_status(f"검색: {keyword}", "blue")
        except (WebDriverException, RuntimeError):
            self.log("❌ 이동 실패. 브라우저 재연결 필요.")
            self.driver = None

    # ------------------------------------------------------------------
    # 모바일 홈 포스트 수집/처리
    # ------------------------------------------------------------------
    def _normalize_post_url(self, raw_url):
        url_text = str(raw_url or "").strip()
        if not url_text:
            return None

        if url_text.startswith("//"):
            url_text = f"https:{url_text}"
        elif url_text.startswith("/"):
            url_text = urllib.parse.urljoin("https://m.blog.naver.com/", url_text)

        parsed = urllib.parse.urlparse(url_text)
        if not parsed.scheme:
            url_text = urllib.parse.urljoin("https://m.blog.naver.com/", url_text)
            parsed = urllib.parse.urlparse(url_text)

        if "blog.naver.com" not in (parsed.netloc or "").lower():
            return None

        query = urllib.parse.parse_qs(parsed.query or "")
        blog_id = str((query.get("blogId") or [""])[0] or "").strip()
        log_no = str((query.get("logNo") or [""])[0] or "").strip()

        if not blog_id or not log_no:
            parts = [part for part in (parsed.path or "").split("/") if part]
            if len(parts) >= 2:
                possible_blog = parts[-2]
                possible_log = parts[-1]
                if re.fullmatch(r"\d{5,}", possible_log):
                    blog_id = blog_id or possible_blog
                    log_no = log_no or possible_log

        if not blog_id or not log_no:
            return None

        blog_id = re.sub(r"[^a-zA-Z0-9_-]", "", blog_id)
        log_no = re.sub(r"[^0-9]", "", log_no)
        if len(blog_id) < 3 or len(log_no) < 5:
            return None

        key = f"{blog_id.lower()}:{log_no}"
        canonical_url = f"https://m.blog.naver.com/PostView.naver?blogId={blog_id}&logNo={log_no}"
        return {"key": key, "blog_id": blog_id, "log_no": log_no, "url": canonical_url}

    def _collect_post_links_from_page(self):
        if not self.driver:
            return []

        if self._webview2_mode:
            try:
                links = self._cdp_eval(
                    """
                    return Array.from(document.querySelectorAll('a[href]')).map(function(a){
                        return a.getAttribute('href') || a.href || '';
                    });
                    """,
                    timeout=6.0,
                )
                if isinstance(links, list):
                    return links
            except Exception:
                return []
            return []

        try:
            result = []
            for anchor in self.driver.find_elements(By.CSS_SELECTOR, "a[href]"):
                try:
                    href = anchor.get_attribute("href")
                    if href:
                        result.append(href)
                except (StaleElementReferenceException, NoSuchElementException):
                    continue
            return result
        except WebDriverException:
            return []

    def _scroll_feed_once(self):
        if self._webview2_mode:
            try:
                self._cdp_eval(
                    """
                    var move = Math.max(window.innerHeight * 0.9, 700);
                    window.scrollBy(0, move);
                    var clicked = false;
                    var labels = ['더보기', '새 글', '다음'];
                    var nodes = Array.from(document.querySelectorAll("button,a,span,div"));
                    for (var i = 0; i < nodes.length; i++) {
                        var el = nodes[i];
                        var txt = (el.innerText || el.textContent || '').replace(/\\s+/g, ' ').trim();
                        if (!txt) continue;
                        if (!labels.some(function(w){ return txt.indexOf(w) >= 0; })) continue;
                        var rect = el.getBoundingClientRect();
                        if (rect.width <= 0 || rect.height <= 0) continue;
                        el.click();
                        clicked = true;
                        break;
                    }
                    return clicked;
                    """,
                    timeout=4.0,
                )
            except Exception:
                pass
            return

        try:
            self.driver.execute_script("window.scrollBy(0, Math.max(window.innerHeight * 0.9, 700));")
            for btn in self.driver.find_elements(By.XPATH, "//button|//a"):
                try:
                    label = (btn.text or "").strip()
                    if label and ("더보기" in label or "새 글" in label or "다음" in label):
                        self.safe_click(self.driver, btn)
                        break
                except (StaleElementReferenceException, NoSuchElementException):
                    continue
        except WebDriverException:
            pass

    def _collect_feed_posts(self, seen_post_keys):
        queue = []
        max_scroll = 10
        max_queue = 30
        my_id_clean = str(self.my_blog_id or "").strip().lower()

        for idx in range(max_scroll):
            raw_links = self._collect_post_links_from_page()
            added_count = 0
            for raw_link in raw_links:
                normalized = self._normalize_post_url(raw_link)
                if not normalized:
                    continue
                if my_id_clean and normalized["blog_id"].lower() == my_id_clean:
                    continue
                if normalized["key"] in seen_post_keys:
                    continue

                seen_post_keys.add(normalized["key"])
                queue.append(normalized)
                added_count += 1
                if len(queue) >= max_queue:
                    break

            self.log(f"   ⬇️ 피드 스캔 {idx+1}/{max_scroll} - 신규 {added_count}개 (대기열: {len(queue)}개)")
            if len(queue) >= max_queue:
                break

            self._scroll_feed_once()
            self.safe_sleep(0.9)

        return queue

    def _extract_post_payload(self):
        script = """
        var pick = function(selectors){
            for (var i = 0; i < selectors.length; i++) {
                var el = document.querySelector(selectors[i]);
                if (!el) continue;
                var txt = (el.innerText || el.textContent || '').replace(/\\s+/g, ' ').trim();
                if (txt) return txt;
            }
            return '';
        };

        var title = '';
        var meta = document.querySelector("meta[property='og:title']");
        if (meta && meta.content) title = String(meta.content || '').replace(/\\s+/g, ' ').trim();
        if (!title) {
            title = pick(['.se-title-text', '.htitle', '.post_title', 'h1', 'h2']);
        }

        var body = pick([
            '#postViewArea',
            '.se-main-container',
            '.post_ct',
            '.post-view',
            '.post_content'
        ]);
        if (!body && document.body) {
            body = (document.body.innerText || '').replace(/\\s+/g, ' ').trim();
        }
        if (body.length > 3500) {
            body = body.slice(0, 3500);
        }

        return {title: title, body: body};
        """

        if self._webview2_mode:
            try:
                data = self._cdp_eval(script, timeout=6.0)
                if isinstance(data, dict):
                    return data
            except Exception:
                return {"title": "", "body": ""}
            return {"title": "", "body": ""}

        try:
            data = self.driver.execute_script(script)
            if isinstance(data, dict):
                return data
        except WebDriverException:
            pass
        return {"title": "", "body": ""}

    def _build_fallback_comment(self, title):
        title_clean = str(title or "").strip()
        if title_clean:
            return f"좋은 글 감사합니다. {title_clean[:18]} 내용 특히 공감됐어요."
        return "좋은 글 잘 읽었습니다. 핵심을 쉽게 정리해주셔서 도움이 됐어요."

    def _sanitize_comment_text(self, raw_text, fallback_text):
        text = str(raw_text or "").strip()
        if not text:
            return fallback_text

        text = text.replace("```", " ").replace("\r", "\n")
        text = re.sub(r"^\s*(댓글|추천 댓글|답글)\s*[:：]\s*", "", text)
        text = re.sub(r"\s+", " ", text).strip(" \"'")
        if not text:
            return fallback_text

        max_chars = int(self.config.get("comment_max_chars") or 90)
        if max_chars < 40:
            max_chars = 40
        if len(text) > max_chars:
            text = text[:max_chars].rstrip(" ,.!?") + "..."
        if len(text) < 8:
            return fallback_text
        return text

    def _extract_gemini_text(self, response_data):
        if not isinstance(response_data, dict):
            return ""
        candidates = response_data.get("candidates") or []
        for cand in candidates:
            content = (cand or {}).get("content") or {}
            parts = content.get("parts") or []
            for part in parts:
                text = str((part or {}).get("text") or "").strip()
                if text:
                    return text
        return ""

    def _generate_comment_with_gemini(self, title, body_text):
        fallback = self._build_fallback_comment(title)
        api_key = str(self.gemini_api_key or "").strip()
        if not api_key:
            self.log("⚠️ Gemini API 키가 비어 있어 기본 댓글을 사용합니다.")
            return fallback

        persona = str(self.persona_profile or "").strip() or "예의 있고 공감 중심의 블로그 방문자"
        guide = str(self.comment_guide or "").strip()
        body_excerpt = str(body_text or "").strip()
        if len(body_excerpt) > 1400:
            body_excerpt = body_excerpt[:1400]

        prompt = (
            "너는 네이버 블로그 방문자 댓글 작성 도우미다.\n"
            "아래 정보를 참고해서 한국어 댓글 1개만 작성해.\n"
            "- 길이: 1~2문장\n"
            "- 톤: 자연스럽고 공손하게\n"
            "- 출력: 댓글 문장만\n\n"
            f"[페르소나]\n{persona}\n\n"
            f"[게시글 제목]\n{title or '제목 없음'}\n\n"
            f"[게시글 본문]\n{body_excerpt or '본문 추출 실패'}\n\n"
            f"[추가 가이드]\n{guide or '핵심에 공감하는 짧은 댓글'}\n"
        )

        requested_model = str(self.gemini_model or "").strip() or "gemini-2.0-flash"
        model_candidates = []
        for model_name in [
            requested_model,
            "gemini-2.0-flash",
            "gemini-2.0-flash-exp",
            "gemini-1.5-flash",
            "gemini-1.5-flash-latest",
        ]:
            if model_name and model_name not in model_candidates:
                model_candidates.append(model_name)

        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.8,
                "maxOutputTokens": 160,
            },
        }

        endpoints = [
            "https://generativelanguage.googleapis.com/v1/models/{model}:generateContent",
            "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        ]
        last_error = ""

        for model_name in model_candidates:
            for endpoint in endpoints:
                url = endpoint.format(model=model_name)
                req = urllib.request.Request(
                    url,
                    data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                    headers={
                        "Content-Type": "application/json",
                        "x-goog-api-key": api_key,
                    },
                    method="POST",
                )
                try:
                    with urllib.request.urlopen(req, timeout=20.0) as resp:
                        data = json.loads(resp.read().decode("utf-8", errors="ignore") or "{}")
                    text = self._extract_gemini_text(data)
                    if text:
                        return self._sanitize_comment_text(text, fallback)
                    last_error = f"빈 응답 (model={model_name})"
                except urllib.error.HTTPError as e:
                    try:
                        detail = e.read().decode("utf-8", errors="ignore")
                    except Exception:
                        detail = str(e)
                    short_detail = re.sub(r"\s+", " ", detail).strip()[:140]
                    last_error = f"HTTP {e.code} ({model_name}): {short_detail}"
                except Exception as e:
                    last_error = f"{model_name}: {str(e)[:120]}"

        if last_error:
            self.log(f"⚠️ Gemini 응답 실패: {last_error}")
        else:
            self.log("⚠️ Gemini 응답 실패: 원인 미확인")
        self.log("   ↪ 기본 댓글 템플릿으로 대체합니다.")
        return fallback

    def _click_like_on_current_post(self):
        script = """
        var docs = [document];
        Array.from(document.querySelectorAll("iframe")).forEach(function(frame){
            try {
                if (frame.contentDocument && frame.contentDocument.body) {
                    docs.push(frame.contentDocument);
                }
            } catch (e) {}
        });

        var textOf = function(el) {
            return (el.innerText || el.textContent || '').replace(/\\s+/g, ' ').trim();
        };
        var isVisible = function(el) {
            if (!el) return false;
            var rect = el.getBoundingClientRect();
            return rect.width > 0 && rect.height > 0;
        };
        var getClickable = function(el) {
            var node = el;
            var guard = 0;
            while (node && guard < 4) {
                var tag = (node.tagName || '').toUpperCase();
                if (tag === 'BUTTON' || tag === 'A') return node;
                node = node.parentElement;
                guard += 1;
            }
            return el;
        };
        var isAlreadyOn = function(el) {
            var aria = (el.getAttribute('aria-pressed') || '').toLowerCase();
            var cls = (typeof el.className === 'string' ? el.className : '').toLowerCase();
            return aria === 'true' || /(is_on|_on|active|selected|u_likeit_list_btn_on)/.test(cls);
        };
        var tryClick = function(el, doc) {
            if (!el) return false;
            var target = getClickable(el);
            try { target.click(); } catch (e) {}
            try {
                var view = doc.defaultView || window;
                target.dispatchEvent(new view.MouseEvent('click', {bubbles: true, cancelable: true}));
            } catch (e) {}
            return true;
        };

        var selectors = [
            "button.u_likeit_list_btn",
            "a.u_likeit_list_btn",
            "button[class*='likeit'][class*='btn']",
            "a[class*='likeit'][class*='btn']",
            "[data-click-area*='like']",
            "button[aria-label*='공감']",
            "a[aria-label*='공감']",
            "button[aria-label*='좋아요']",
            "a[aria-label*='좋아요']"
        ];

        for (var d = 0; d < docs.length; d++) {
            var doc = docs[d];
            for (var s = 0; s < selectors.length; s++) {
                var nodes = Array.from(doc.querySelectorAll(selectors[s]));
                for (var i = 0; i < nodes.length; i++) {
                    var el = nodes[i];
                    if (!isVisible(el)) continue;
                    if (isAlreadyOn(el)) return {state: 'already', source: selectors[s]};
                    if (tryClick(el, doc)) return {state: 'liked', source: selectors[s]};
                }
            }
        }

        for (var d2 = 0; d2 < docs.length; d2++) {
            var doc2 = docs[d2];
            var all = Array.from(doc2.querySelectorAll("button,a,[role='button'],span,div"));
            for (var j = 0; j < Math.min(all.length, 400); j++) {
                var node = all[j];
                if (!isVisible(node)) continue;
                var txt = textOf(node);
                if (!txt || txt.length > 30) continue;
                if (!/(공감|좋아요)/.test(txt)) continue;
                if (/(댓글|답글|공유|이웃|구독|신고)/.test(txt)) continue;
                if (isAlreadyOn(node)) return {state: 'already', source: 'text-match'};
                if (tryClick(node, doc2)) return {state: 'liked', source: 'text-match'};
            }
        }
        return {state: 'not_found', source: ''};
        """
        for _ in range(3):
            try:
                if self._webview2_mode:
                    result = self._cdp_eval(script, timeout=5.0)
                else:
                    result = self.driver.execute_script(script)
            except Exception as e:
                return "error", f"실패({str(e)[:24]})"

            state = str((result or {}).get("state") or "")
            source = str((result or {}).get("source") or "")
            if state == "liked":
                if source:
                    return "liked", f"완료({source})"
                return "liked", "완료"
            if state == "already":
                return "already", "이미 누름"
            if state == "not_found":
                self.safe_sleep(0.5)
                continue
            return "error", f"실패({state or 'unknown'})"

        return "not_found", "버튼 없음"

    def _submit_comment_on_current_post(self, comment_text):
        safe_comment = json.dumps(str(comment_text or ""), ensure_ascii=False)
        script = f"""
        var text = {safe_comment};
        if (!text) return {{state: 'empty'}};

        var docs = [document];
        Array.from(document.querySelectorAll("iframe")).forEach(function(frame) {{
            try {{
                if (frame.contentDocument && frame.contentDocument.body) {{
                    docs.push(frame.contentDocument);
                }}
            }} catch (e) {{}}
        }});

        var textOf = function(el) {{
            return (el.innerText || el.textContent || '').replace(/\\s+/g, ' ').trim();
        }};
        var isVisible = function(el) {{
            if (!el) return false;
            var rect = el.getBoundingClientRect();
            return rect.width > 0 && rect.height > 0;
        }};
        var clickNode = function(el, doc) {{
            if (!el) return;
            try {{ el.click(); }} catch (e) {{}}
            try {{
                var view = doc.defaultView || window;
                el.dispatchEvent(new view.MouseEvent('click', {{bubbles: true, cancelable: true}}));
            }} catch (e) {{}}
        }};
        var openCommentEditor = function() {{
            for (var d = 0; d < docs.length; d++) {{
                var doc = docs[d];
                var nodes = Array.from(doc.querySelectorAll("button,a,[role='button'],span,div"));
                for (var i = 0; i < Math.min(nodes.length, 400); i++) {{
                    var el = nodes[i];
                    if (!isVisible(el)) continue;
                    var txt = textOf(el);
                    if (!txt || txt.length > 30) continue;
                    if (!/(댓글|답글)/.test(txt)) continue;
                    if (/(닫기|접기|취소)/.test(txt)) continue;
                    clickNode(el, doc);
                    return true;
                }}
            }}
            return false;
        }};
        var findEditor = function() {{
            var inputSelectors = [
                "textarea.u_cbox_text",
                "textarea#comment",
                "textarea[name='comment']",
                "textarea",
                "div[contenteditable='true'][role='textbox']",
                "div[contenteditable='true'].u_cbox_text_wrap",
                "div[contenteditable='true']"
            ];
            for (var d = 0; d < docs.length; d++) {{
                var doc = docs[d];
                for (var s = 0; s < inputSelectors.length; s++) {{
                    var el = doc.querySelector(inputSelectors[s]);
                    if (el && isVisible(el)) return {{el: el, doc: doc}};
                }}
            }}
            return null;
        }};

        var editorPair = findEditor();
        if (!editorPair) {{
            openCommentEditor();
            editorPair = findEditor();
        }}
        if (!editorPair) return {{state: 'no_input'}};

        var editor = editorPair.el;
        var editorDoc = editorPair.doc;
        try {{
            editor.focus();
            if ((editor.tagName || '').toUpperCase() === 'TEXTAREA') {{
                editor.value = text;
            }} else {{
                editor.textContent = text;
            }}
            editor.dispatchEvent(new Event('input', {{ bubbles: true }}));
            editor.dispatchEvent(new Event('change', {{ bubbles: true }}));
            editor.dispatchEvent(new KeyboardEvent('keyup', {{ bubbles: true, key: 'a' }}));
        }} catch (e) {{
            return {{state: 'input_error'}};
        }}

        var submitSelectors = [
            "button.u_cbox_btn_upload",
            "button[class*='upload']",
            "button[class*='submit']",
            "a[class*='upload']",
            "input[type='submit']",
            "input[type='button']"
        ];
        var submit = null;
        for (var ss = 0; ss < submitSelectors.length; ss++) {{
            var cand = editorDoc.querySelector(submitSelectors[ss]);
            if (cand && isVisible(cand)) {{
                submit = cand;
                break;
            }}
        }}
        if (!submit) {{
            var nodes2 = Array.from(editorDoc.querySelectorAll("button,a,input[type='button'],input[type='submit']"));
            for (var n = 0; n < nodes2.length; n++) {{
                var el2 = nodes2[n];
                if (!isVisible(el2)) continue;
                var txt2 = textOf(el2) || (el2.value || '').trim();
                if (!txt2) continue;
                if (/(등록|작성|올리기|확인)/.test(txt2) && !/(취소|삭제|닫기)/.test(txt2)) {{
                    submit = el2;
                    break;
                }}
            }}
        }}
        if (!submit) return {{state: 'no_submit'}};
        if (submit.disabled || submit.getAttribute('aria-disabled') === 'true') return {{state: 'disabled'}};

        try {{
            clickNode(submit, editorDoc);
            return {{state: 'posted'}};
        }} catch (e) {{
            return {{state: 'submit_error'}};
        }}
        """
        last_state = "error"
        for _ in range(4):
            try:
                if self._webview2_mode:
                    result = self._cdp_eval(script, timeout=6.0)
                else:
                    result = self.driver.execute_script(script)
            except Exception as e:
                return "error", f"실패({str(e)[:24]})"

            state = str((result or {}).get("state") or "")
            last_state = state or "error"
            if state == "posted":
                return "posted", "등록 완료"
            if state == "empty":
                return "empty", "댓글 비어 있음"
            if state == "disabled":
                return "disabled", "등록 버튼 비활성화"
            if state in {"no_input", "no_submit"}:
                self.safe_sleep(0.6)
                continue
            if state in {"input_error", "submit_error"}:
                self.safe_sleep(0.4)
                continue
            break

        message_map = {
            "no_input": "입력창 없음",
            "no_submit": "등록 버튼 없음",
            "input_error": "입력 실패",
            "submit_error": "등록 클릭 실패",
            "disabled": "등록 버튼 비활성화",
        }
        return "error", message_map.get(last_state, "실패")

    def _process_post_item(self, post_item):
        if not self.safe_get(self.driver, post_item["url"]):
            return {"completed": False, "fatal": False, "reason": "페이지 로드 실패"}

        self.safe_sleep(1.1)

        current_url = self._get_current_url().lower()
        page_source = self._get_page_source()
        if "nid.naver.com/nidlogin" in current_url:
            return {"completed": False, "fatal": True, "reason": "로그인이 만료되었습니다."}
        if "MobileErrorView" in current_url or "일시적인 오류" in page_source:
            return {"completed": False, "fatal": False, "reason": "접근 불가 포스트"}

        payload = self._extract_post_payload()
        title = str(payload.get("title") or "").strip()
        body = str(payload.get("body") or "").strip()

        self.log(f"   ├ 포스트: {post_item['blog_id']}/{post_item['log_no']}")
        if title:
            self.log(f"   ├ 제목: {title[:40]}")

        like_state, like_msg = self._click_like_on_current_post()
        self.log(f"   ├ 좋아요: {like_msg}")
        self.safe_sleep(0.35)

        generated_comment = self._generate_comment_with_gemini(title, body)
        comment_state, comment_msg = self._submit_comment_on_current_post(generated_comment)
        self.log(f"   ├ 댓글: {comment_msg}")
        self.log(f"   └ 생성 댓글: {generated_comment}")

        if comment_state == "posted":
            self.safe_sleep(self.fast_wait)

        completed = (like_state in {"liked", "already"}) or (comment_state == "posted")
        if completed:
            return {"completed": True, "fatal": False, "reason": "완료"}
        return {"completed": False, "fatal": False, "reason": "좋아요/댓글 모두 실패"}

    def _run_feed_loop(self):
        feed_url = str(self.config.get("feed_url") or "https://m.blog.naver.com/").strip()
        if not feed_url:
            feed_url = "https://m.blog.naver.com/"

        seen_post_keys = set()
        queue = []
        consecutive_errors = 0

        while self.is_running:
            if not queue:
                self.log(f"🔄 모바일 홈 포스트 수집 중... (누적 처리: {self.current_count}개)")
                if not self.safe_get(self.driver, feed_url):
                    self.log("❌ 모바일 홈 진입 실패. 3초 후 재시도합니다.")
                    self.safe_sleep(3.0)
                    continue
                self.safe_sleep(1.0)

                queue = self._collect_feed_posts(seen_post_keys)
                if not queue:
                    self.log("⚠️ 처리 가능한 포스트를 찾지 못했습니다. 5초 후 다시 탐색합니다.")
                    self.safe_sleep(5.0)
                    if len(seen_post_keys) > 6000:
                        seen_post_keys.clear()
                    continue
                self.log(f"   ✅ {len(queue)}개 포스트 수집 완료")

            post_item = queue.pop(0)
            self.log(f"\n▶️ #{self.current_count+1} 포스트 작업 시작")
            result = self._process_post_item(post_item)

            if result.get("fatal"):
                self.log(f"❌ 작업 중단: {result.get('reason')}")
                break

            if result.get("completed"):
                consecutive_errors = 0
                self.current_count += 1
                self.update_progress((self.current_count % 100) / 100.0)
                self.log(f"   ✅ 완료 (누적 {self.current_count}개)")
            else:
                consecutive_errors += 1
                self.log(f"   ⚠️ 스킵: {result.get('reason')}")
                if consecutive_errors >= 5:
                    self.log("⚠️ 연속 실패 5회. 5초 대기 후 계속합니다.")
                    self.safe_sleep(5.0)
                    consecutive_errors = 0

            self.safe_sleep(random.uniform(0.9, 1.6))

    def start_working(self, persona_profile, gemini_api_key, comment_guide=""):
        if not self.connect_driver():
            self.log("❌ 브라우저 연결 실패")
            return

        if not self.check_login_status():
            self.log("❌ 로그인이 필요합니다. 최초 1회 로그인 후 다시 시작하세요.")
            self.open_login_page()
            return

        self.persona_profile = str(persona_profile or "").strip()
        self.gemini_api_key = str(gemini_api_key or "").strip()
        self.comment_guide = str(comment_guide or "").strip()
        self.gemini_model = str(self.config.get("gemini_model") or "gemini-2.0-flash").strip()
        self.config.set("persona_profile", self.persona_profile)
        self.config.set("gemini_api_key", self.gemini_api_key)
        self.config.set("comment_msg", self.comment_guide)
        self.config.save()

        self.my_blog_id = str(self.config.get("my_blog_id") or "").strip()
        if not self.my_blog_id:
            self._ensure_my_blog_id()

        self.is_running = True
        self.current_count = 0
        self.update_progress(0)

        self.log("🚀 자동 좋아요/댓글 작업 시작")
        self.update_status("작업 실행 중...", "blue")

        try:
            self._run_feed_loop()
        finally:
            self.is_running = False
            self.update_status("작업 완료", "green")
            self.log("🏁 작업 종료")
