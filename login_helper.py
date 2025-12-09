import os
import time
import subprocess
import platform

def manual_login():
    print("=======================================")
    print("🔐 로그인 데이터 생성을 시작합니다.")
    print("=======================================")

    # 1. 봇과 동일한 경로 설정
    user_data_dir = os.path.expanduser("~/ChromeBotData")
    
    # 2. 맥 크롬 경로
    chrome_path = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    
    # 3. 크롬 실행 (화면이 보이게!)
    # --headless 옵션을 뺐으므로 화면이 보입니다.
    cmd = [
        chrome_path,
        "--remote-debugging-port=9222",
        f"--user-data-dir={user_data_dir}",
        "--no-first-run",
        "--no-default-browser-check"
        # "--headless=new"  <-- 이걸 뺐습니다.
    ]
    
    print(f"🖥️  크롬 창이 열리면 네이버 로그인을 진행해주세요.")
    print(f"⚠️  주의: 반드시 [로그인 상태 유지]를 체크하세요!")
    
    # 크롬 실행
    proc = subprocess.Popen(cmd)
    
    # 사용자가 로그인할 시간을 줌
    try:
        print("\n⏳ 크롬이 실행되었습니다.")
        input("👉 로그인을 완료하고 네이버 메인화면이 나오면, [엔터 키]를 눌러주세요...")
    except:
        pass
    
    print("\n💾 로그인 정보를 저장하고 종료합니다...")
    proc.terminate()
    time.sleep(2)
    print("✅ 설정 완료! 이제 본 프로그램을 실행하시면 됩니다.")

if __name__ == "__main__":
    manual_login()