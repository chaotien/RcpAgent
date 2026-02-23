import os
import yaml
import time
import cv2
import numpy as np
import pyautogui
from tkinter import Tk, filedialog

# 設定 YAML 檔案名稱
YAML_FILE = "sop_tbs_001_workflow.yaml"
ASSET_DIR = "assets"

def extract_image_paths(data, paths=None):
    """遞迴搜尋 YAML 中所有的 image path"""
    if paths is None:
        paths = set()

    if isinstance(data, dict):
        # 檢查是否有 image type
        if data.get("type") == "image" and "path" in data:
            paths.add(data["path"])
        
        # 遞迴檢查所有 values
        for key, value in data.items():
            extract_image_paths(value, paths)
            
    elif isinstance(data, list):
        for item in data:
            extract_image_paths(item, paths)
            
    return paths

def capture_asset(filename):
    """截圖並讓使用者框選 ROI"""
    print(f"\n[Action Required] 準備截取: {filename}")
    print("1. 請將目標應用程式(Simulator)切換到前景，並確保目標可見。")
    print("2. 準備好後，請將焦點回到此 Terminal，並按下 [Enter] 鍵開始截圖...")
    input()

    # 隱藏 Console 視窗 (稍微等待一下讓使用者切換視窗，如果需要)
    # 這裡直接截全螢幕
    print(">>> 正在截取螢幕... (請勿移動滑鼠)")
    time.sleep(0.5) 
    screenshot = pyautogui.screenshot()
    img = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)

    # 彈出視窗讓使用者框選
    window_name = f"Select ROI for: {filename} (Drag & Press ENTER, 'c' to Cancel)"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    
    # 全螢幕顯示以便框選
    cv2.setWindowProperty(window_name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
    
    # 使用 OpenCV 內建的 ROI Selector
    # 操作方法：滑鼠拖曳框選 -> 按下 Space 或 Enter 確認 -> 按 c 取消
    print(f">>> 請在彈出的視窗中框選目標。完成後按 Space/Enter，取消按 c")
    r = cv2.selectROI(window_name, img, showCrosshair=True, fromCenter=False)
    cv2.destroyWindow(window_name)

    # r = (x, y, w, h)
    if r[2] > 0 and r[3] > 0:
        # Crop
        im_crop = img[int(r[1]):int(r[1]+r[3]), int(r[0]):int(r[0]+r[2])]
        
        # 確保目錄存在
        # 若 YAML path 只有檔名，則使用 ASSET_DIR；若已有路徑則使用該路徑
        if os.path.dirname(filename):
            full_path = filename
            target_dir = os.path.dirname(full_path)
        else:
            full_path = os.path.join(ASSET_DIR, filename)
            target_dir = ASSET_DIR

        if not os.path.exists(target_dir):
            print(f"建立目錄: {target_dir}")
            os.makedirs(target_dir)
            
        cv2.imwrite(full_path, im_crop)
        print(f"✅ 已儲存: {full_path}")
    else:
        print(f"⚠️  已取消截取: {filename}")

def main():
    if not os.path.exists(YAML_FILE):
        print(f"找不到設定檔: {YAML_FILE}")
        return

    print(f"正在讀取 {YAML_FILE}...")
    with open(YAML_FILE, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    # 1. 找出所有需要的圖片
    required_images = extract_image_paths(config)
    print(f"共發現 {len(required_images)} 個圖片資源引用。")

    # 2. 檢查已存在的圖片
    missing_images = []
    for img_path in required_images:
        # 若 img_path 是相對路徑且不包含目錄，檢查時也要考慮 ASSET_DIR
        check_path = img_path
        if not os.path.dirname(img_path):
             check_path = os.path.join(ASSET_DIR, img_path)

        if os.path.exists(check_path):
            print(f"  [Exist] {check_path}")
        else:
            print(f"  [MISSING] {check_path}")
            missing_images.append(img_path)

    if not missing_images:
        print("\n🎉 所有圖片資源皆已存在！無需操作。")
        return

    print(f"\n========================================")
    print(f"開始補齊 {len(missing_images)} 個缺失的圖片...")
    print(f"========================================")

    # 3. 逐一截圖
    for img_path in missing_images:
        capture_asset(img_path)

    print("\n所有操作完成。")

if __name__ == "__main__":
    main()