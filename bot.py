import json
import time
import os
import gc
import glob
import subprocess
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from groq import Groq

INTERVAL_HOURS = 3  # 3 နာရီတစ်ခါ

def load_data(filename):
    try:
        with open(filename, 'r') as f:
            return [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        print(f"Error: {filename} not found.")
        return []

def clean_cache():
    print("\n--- Cleaning cache and memory ---")
    # Chrome cache clean
    cache_dirs = [
        os.path.expanduser("~/.cache/google-chrome"),
        os.path.expanduser("~/.config/google-chrome/Default/Cache"),
        "/tmp/.org.chromium.*",
        "/tmp/chrome_*",
    ]
    for d in cache_dirs:
        subprocess.run(f"rm -rf {d}", shell=True)
    # Python garbage collection
    gc.collect()
    print("Cache cleaned. Memory freed.")

def run_account(account_file, proxies_list, apis_list, index):
    account_name = os.path.basename(account_file)
    print(f"\n========== [ Starting: {account_name} ] ==========")

    current_api = apis_list[index % len(apis_list)]
    groq_client = Groq(api_key=current_api)

    options = webdriver.ChromeOptions()

    if proxies_list:
        current_proxy = proxies_list[index % len(proxies_list)]
        print(f"Proxy: {current_proxy} | API: {current_api[:8]}...")
        options.add_argument(f'--proxy-server=http://{current_proxy}')
    else:
        print(f"Proxy: Not Used (Direct Connection) | API: {current_api[:8]}...")

    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--disable-extensions')
    options.add_argument('--no-first-run')
    options.add_argument('--disable-default-apps')

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    wait = WebDriverWait(driver, 15)

    try:
        driver.get("https://gpt.1zeni.com/")
        time.sleep(3)

        with open(account_file, 'r') as file:
            local_storage_data = json.load(file)

        if isinstance(local_storage_data, list):
            local_storage_data = local_storage_data[0]

        for key, value in local_storage_data.items():
            if isinstance(value, dict) or isinstance(value, list):
                value = json.dumps(value)
            driver.execute_script("window.localStorage.setItem(arguments[0], arguments[1]);", key, value)

        driver.refresh()
        time.sleep(5)
        print("Login successful via Local Storage.")

        print("Navigating to 'AI Tasks'...")
        try:
            ai_tasks_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//*[text()='AI Tasks' or contains(text(), 'AI Tasks')]")))
            driver.execute_script("arguments[0].click();", ai_tasks_btn)
            time.sleep(5)
            print("Reached AI Tasks page.")
        except Exception:
            print("AI Tasks button not found. Continuing...")

        print("\n--- Starting AI Micro-Tasks ---")
        quiz_count = 1
        while True:
            try:
                submit_btn = wait.until(EC.presence_of_element_located((By.XPATH, "//button[contains(text(), 'Submit')] | //div[contains(text(), 'Submit')]")))
                page_text = driver.find_element(By.TAG_NAME, "body").text
                options_elements = driver.find_elements(By.XPATH, "//*[starts-with(normalize-space(text()), 'A\u3001') or starts-with(normalize-space(text()), 'B\u3001') or starts-with(normalize-space(text()), 'C\u3001') or starts-with(normalize-space(text()), 'D\u3001') or starts-with(normalize-space(text()), 'E\u3001')]")

                if not options_elements:
                    print("No more options found. Quizzes finished.")
                    break

                options_text = "\n".join([opt.text for opt in options_elements])
                print(f"\n[Quiz {quiz_count}] Options found:\n{options_text}")

                prompt = f"Here is the text from a quiz webpage:\n\n{page_text}\n\nThe options are:\n{options_text}\n\nBased on the context, which option is the correct answer? Reply with ONLY the correct option letter (A, B, C, D, or E) without any explanation."

                chat_completion = groq_client.chat.completions.create(
                    messages=[{"role": "user", "content": prompt}],
                    model="llama3-8b-8192",
                )
                ai_answer = chat_completion.choices[0].message.content.strip().upper()
                if len(ai_answer) > 0:
                    ai_answer = ai_answer[0]
                print(f"Groq AI Answer: {ai_answer}")

                clicked = False
                for opt in options_elements:
                    if opt.text.upper().startswith(f"{ai_answer}\u3001"):
                        driver.execute_script("arguments[0].click();", opt)
                        clicked = True
                        break

                if not clicked:
                    print(f"Option {ai_answer} not found. Selecting the first option.")
                    driver.execute_script("arguments[0].click();", options_elements[0])

                time.sleep(1)
                driver.execute_script("arguments[0].click();", submit_btn)
                print("Submitted. Waiting for next quiz...")
                time.sleep(6)
                quiz_count += 1

            except Exception:
                print("Quizzes completed or no more questions.")
                break

        print("\n--- Starting Twitter Tasks ---")
        try:
            twitter_keywords = ['Like', 'Repost', 'Follow', 'Quote', 'Bookmark', 'Comment']
            xpath_conditions = " or ".join([f"contains(text(), '{kw}')" for kw in twitter_keywords])
            twitter_buttons = driver.find_elements(By.XPATH, f"//*[{xpath_conditions}]")

            if len(twitter_buttons) == 0:
                print("No Twitter tasks found.")
            else:
                print(f"Found {len(twitter_buttons)} Twitter tasks.")
                for i, btn in enumerate(twitter_buttons):
                    task_type = btn.text.strip()
                    print(f"Clicking Task {i + 1}: [{task_type}]...")
                    driver.execute_script("arguments[0].click();", btn)
                    time.sleep(4)

                    windows = driver.window_handles
                    if len(windows) > 1:
                        driver.switch_to.window(windows[1])
                        time.sleep(3)
                        driver.close()
                        driver.switch_to.window(windows[0])
                        time.sleep(2)

                    print(f"Task [{task_type}] done!")

        except Exception as e:
            print(f"Error in Twitter tasks: {e}")

        print(f"\n========== [ {account_name} Process Completed ] ==========")

    except Exception as e:
        print(f"Error in {account_name}: {e}")

    finally:
        driver.quit()
        gc.collect()
        time.sleep(3)

def main():
    run_count = 0
    while True:
        run_count += 1
        print(f"\n{'='*50}")
        print(f"  AUTO RUN #{run_count} started at {time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*50}")

        proxies_list = load_data('proxies.txt')
        apis_list = load_data('apis.txt')
        account_files = sorted(glob.glob('accounts/*.json'))  # အစဉ်လိုက်

        if not account_files:
            print("Error: No account files found in 'accounts' folder.")
        elif not apis_list:
            print("Error: API file is empty. Please add Groq API key in apis.txt")
        else:
            for index, account_file in enumerate(account_files):
                run_account(account_file, proxies_list, apis_list, index)

        # ၉ ကောင့်အားလုံး ပြီးရင် cache သန့်
        clean_cache()

        print(f"\n{'='*50}")
        print(f"  All accounts done. Waiting {INTERVAL_HOURS} hours for next run...")
        print(f"  Next run at: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time() + INTERVAL_HOURS * 3600))}")
        print(f"{'='*50}\n")

        time.sleep(INTERVAL_HOURS * 3600)  # 3 နာရီ စောင့်

if __name__ == "__main__":
    main()
