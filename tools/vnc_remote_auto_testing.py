import pyautogui
import time
import datetime
import os

def run_vnc_headless_test(duration_seconds=120, interval=5):
    """
    VNC 環境存活與解析度測試腳本
    將每隔 [interval] 秒記錄一次解析度並截圖，持續 [duration_seconds] 秒。
    """
    log_file = "vnc_test_log.txt"
    output_dir = "vnc_test_shots"
    
    # 建立截圖資料夾
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    print(f"[*] 開始 VNC 環境測試，預計執行 {duration_seconds} 秒...")
    print(f"[*] 測試期間請嘗試：1. 縮放 VNC 視窗 2. 斷開 VNC 連線\n")
    
    with open(log_file, "w", encoding="utf-8") as f:
        f.write("=== VNC 環境壓力測試 Log ===\n")
        f.write(f"開始時間: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

    start_time = time.time()
    iteration = 1

    while (time.time() - start_time) < duration_seconds:
        current_time_str = datetime.datetime.now().strftime('%H-%M-%S')
        log_entry = ""
        
        try:
            # 1. 紀錄解析度 (驗證 Q1)
            screen_w, screen_h = pyautogui.size()
            
            # 2. 微調滑鼠以證明控制權 (驗證 Q2)
            # 在中心點附近微幅晃動
            center_x, center_y = screen_w // 2, screen_h // 2
            pyautogui.moveTo(center_x + (iteration % 20), center_y + (iteration % 20))
            current_mouse = pyautogui.position()
            
            # 3. 截圖 (驗證畫面是否全黑或被鎖定)
            screenshot_path = os.path.join(output_dir, f"shot_{current_time_str}.png")
            pyautogui.screenshot(screenshot_path)
            
            log_entry = (f"[{current_time_str}] 迭代 {iteration:02d} | "
                         f"解析度: {screen_w}x{screen_h} | "
                         f"滑鼠座標: {current_mouse} | 截圖成功")
            
        except pyautogui.FailSafeException:
            log_entry = f"[{current_time_str}] 迭代 {iteration:02d} | 錯誤: 觸發 FailSafe (滑鼠被移至角落)"
            break
        except Exception as e:
            log_entry = f"[{current_time_str}] 迭代 {iteration:02d} | 嚴重錯誤: {str(e)} (可能無畫面可渲染)"
        
        # 雙重輸出：印在終端機並寫入檔案 (因為斷線時您看不到終端機)
        print(log_entry)
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(log_entry + "\n")
            
        iteration += 1
        time.sleep(interval)

    print("\n[*] 測試結束！請檢查 log 檔與截圖資料夾。")

if __name__ == "__main__":
    # 強制關閉 FailSafe 以免斷線時座標異常導致腳本誤判中止
    pyautogui.FAILSAFE = False 
    run_vnc_headless_test()