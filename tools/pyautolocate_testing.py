import pyautogui
import os
import time
from PIL import ImageDraw, Image

def test_dropdown_location():
    # 1. 設定參數
    path = "assets/dropdown_port2_done_3.png"
    roi = (177, 432, 200, 150)
    conf = 0.9  # 建議先從 0.9 開始測試
    
    print(f"--- 開始測試定位 ---")
    
    # 2. 檢查圖檔是否存在
    if not os.path.exists(path):
        print(f"❌ 錯誤：找不到圖檔於 {path}")
        return

    # 3. 執行定位並計時
    start_time = time.time()
    box = pyautogui.locateOnScreen(
        path, 
        region=roi, 
        confidence=conf, 
        grayscale=True
    )
    end_time = time.time()
    
    duration = end_time - start_time

    # 4. 結果判定
    if box is not None:
        print(f"✅ 成功找到目標！")
        print(f"位置資訊: {box}")
        print(f"耗時: {duration:.4f} 秒")
        
        # 額外動作：移動滑鼠去確認位置是否精確
        pyautogui.moveTo(box)
        print("滑鼠已移至目標中心點。")
    else:
        print(f"❌ 定位失敗。")
        print(f"搜尋範圍 (ROI): {roi}")
        print(f"請確認該區域目前是否有顯示與 {path} 相同的內容。")
        
        # 輔助除錯：截下目前的 ROI 區域看看到底長怎樣
        debug_img = pyautogui.screenshot(region=roi)
        debug_img.save("debug_roi_capture.png")
        print("已存取目前 ROI 截圖至 'debug_roi_capture.png' 以供對比。")

if __name__ == "__main__":
    test_dropdown_location()