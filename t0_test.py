import pyautogui
import time
import sys

def setup_safety_protocols():
    """
    TPM 安全規範：
    1. FAILSAFE = True: 當滑鼠被強制移到螢幕四個角落時，會觸發 FailSafeException 強制中止程式。
    2. PAUSE = 0.5: 每個 pyautogui 動作之間強制暫停 0.5 秒，保留人類介入的緩衝時間。
    """
    pyautogui.FAILSAFE = True
    pyautogui.PAUSE = 0.5
    print("[*] 安全規範已啟動：FAILSAFE=ON, 全域延遲=0.5s")
    print("[!] 緊急中止方法：請將您的實體滑鼠快速甩至螢幕「最左上角 (0,0)」。\n")

def test_perception_layer():
    """測試 Agent 的感知能力 (解析度讀取與畫面擷取)"""
    print("=== 開始測試 Perception Layer (感知層) ===")
    
    # 1. 取得螢幕解析度 (這對未來的 Template Matching 至關重要)
    screen_width, screen_height = pyautogui.size()
    print(f"[*] 系統偵測螢幕解析度為: {screen_width} x {screen_height}")
    
    # 2. 測試視覺擷取能力
    test_image_name = "test_vision_capture.png"
    try:
        screenshot = pyautogui.screenshot()
        screenshot.save(test_image_name)
        print(f"[*] 視覺擷取成功：已儲存截圖至 '{test_image_name}'")
    except Exception as e:
        print(f"[x] 視覺擷取失敗: {e}")
        sys.exit(1)
        
    print("=== 感知層測試完成 ===\n")

def test_action_layer():
    """測試 Agent 的行動能力 (滑鼠精準控制)"""
    print("=== 開始測試 Action Layer (行動層) ===")
    print("[*] 警告：滑鼠將在 3 秒後自動接管並畫一個正方形。")
    print("[*] 倒數: 3..."); time.sleep(1)
    print("[*] 倒數: 2..."); time.sleep(1)
    print("[*] 倒數: 1..."); time.sleep(1)
    
    try:
        # 取得當下座標作為起點
        start_x, start_y = pyautogui.position()
        print(f"[*] 起始座標: ({start_x}, {start_y})")
        
        # 進行相對位移畫正方形 (參數 duration 讓移動變得平滑可視)
        move_distance = 150
        print("[*] 執行動作：向右移動...")
        pyautogui.move(move_distance, 0, duration=0.3)
        print("[*] 執行動作：向下移動...")
        pyautogui.move(0, move_distance, duration=0.3)
        print("[*] 執行動作：向左移動...")
        pyautogui.move(-move_distance, 0, duration=0.3)
        print("[*] 執行動作：向上移動 (回到原點)...")
        pyautogui.move(0, -move_distance, duration=0.3)
        
        end_x, end_y = pyautogui.position()
        print(f"[*] 結束座標: ({end_x}, {end_y})")
        print("=== 行動層測試成功完成 ===\n")
        
    except pyautogui.FailSafeException:
        print("\n[!] TPM 攔截：偵測到滑鼠移至角落，觸發安全中止機制！測試已中斷。")

if __name__ == "__main__":
    print("=========================================")
    print("  千手千眼 AI Agent - Local 環境驗證腳本")
    print("=========================================\n")
    
    setup_safety_protocols()
    test_perception_layer()
    test_action_layer()
    
    print("=========================================")
    print("  [SUCCESS] 基礎環境驗證 (Task 0.4) 通過！")
    print("=========================================")