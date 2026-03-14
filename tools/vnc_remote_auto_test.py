import pyautogui
import time
import os
from datetime import datetime

# 建立測試產出資料夾
OUTPUT_DIR = "vnc_test_results"
os.makedirs(OUTPUT_DIR, exist_ok=True)

def log_event(message):
    """同時輸出到 Console 與 Log 檔，確保斷線時的紀錄能保留"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    formatted_msg = f"[{timestamp}] {message}"
    print(formatted_msg)
    with open(os.path.join(OUTPUT_DIR, "test_log.txt"), "a", encoding="utf-8") as f:
        f.write(formatted_msg + "\n")

def take_snapshot(phase_name, step):
    """擷取螢幕並記錄當下解析度"""
    try:
        width, height = pyautogui.size()
        img_name = f"{phase_name}_step{step}_{width}x{height}.png"
        img_path = os.path.join(OUTPUT_DIR, img_name)
        
        screenshot = pyautogui.screenshot()
        screenshot.save(img_path)
        log_event(f"成功截圖: {img_name} (解析度: {width}x{height})")
    except Exception as e:
        log_event(f"🚨 !! 截圖失敗 (可能是 GUI 渲染已停止) !! ❌ 錯誤: {e}")

def phase_1_resolution_test():
    log_event("=== [階段一] 解析度與 Client 干擾測試 ===")
    log_event("請在接下來的 15 秒內，嘗試『縮放您的 VNC 視窗』或『改變 Client 解析度』...")
    
    for i in range(1, 4):
        log_event(f"Phase 1 - 擷取第 {i}/3 張狀態...")
        take_snapshot("Phase1", i)
        time.sleep(5) # 給使用者 5 秒鐘調整視窗
        
def phase_2_disconnect_test():
    log_event("\n=== [階段二] 斷線盲幹測試 (Headless Survivability) ===")
    log_event("🚨 警告：請在 10 秒內『完全斷開並關閉您的 VNC Client』！ 🚨")
    
    for i in range(10, 0, -1):
        log_event(f"倒數斷線: {i} 秒...")
        time.sleep(1)
        
    log_event("--- 進入假設的斷線狀態 (黑暗期 30 秒) ---")
    
    # 在斷線期間執行 3 次動作與截圖
    for i in range(1, 4):
        time.sleep(10)
        log_event(f"黑暗期第 {i} 次行動：嘗試相對移動滑鼠 (x+50, y+50) 並截圖...")
        try:
            pyautogui.move(50, 50, duration=0.5)
            log_event("滑鼠移動指令執行完畢，無報錯。")
        except Exception as e:
            log_event(f"🚨 !! 滑鼠移動失敗 !! ❌ 錯誤: {e}")
            
        take_snapshot("Phase2_Dark", i)
        
    log_event("--- 黑暗期結束 ---")
    log_event("✅ 測試完成！您可以重新連上 VNC 了。")
    log_event("請檢查資料夾中的 Log 與圖片，確認 Agent 在您離開時是否還活著。")

if __name__ == "__main__":
    # 清空舊的 log
    log_path = os.path.join(OUTPUT_DIR, "test_log.txt")
    if os.path.exists(log_path):
        os.remove(log_path)
        
    pyautogui.FAILSAFE = False # 測試期間暫時關閉，避免斷線時滑鼠亂飄觸發防護
    
    log_event("啟動 VNC 環境壓力測試...")
    phase_1_resolution_test()
    phase_2_disconnect_test()
    
    pyautogui.FAILSAFE = True # 恢復安全設定