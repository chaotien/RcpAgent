import tkinter as tk
from tkinter import simpledialog
import pyautogui
from PIL import ImageTk, Image
import os
import time

def get_filename(root):
    """使用內建 tkinter 彈出輸入對話框"""
    root.attributes('-topmost', True) # 確保對話框在最上層
    name = simpledialog.askstring(
        "輸入目標名稱", 
        "請輸入此截圖的物件名稱 (例如: btn_start)\n留空則只計算 ROI 座標，不存圖:",
        parent=root
    )
    return name

class ROISelector:
    """純 Tkinter 的全螢幕框選工具，完全避開 OpenCV 與 PyQt5 的環境相容性問題"""
    def __init__(self, root, img):
        self.root = root
        self.root.attributes('-fullscreen', True)
        self.root.attributes('-topmost', True)
        self.root.config(cursor="cross")
        
        self.img = img
        self.tk_img = ImageTk.PhotoImage(self.img)
        
        self.canvas = tk.Canvas(self.root, width=self.img.width, height=self.img.height, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.create_image(0, 0, anchor="nw", image=self.tk_img)
        
        # 繪製半透明(或純色)提示背景與文字
        self.canvas.create_rectangle(20, 20, 750, 70, fill="black", outline="")
        self.canvas.create_text(385, 45, text="👉 請拖曳滑鼠框選目標，完成後按下 [Enter] 或 [空白鍵] 確認，[Esc] 取消", fill="white", font=("Arial", 14, "bold"))
        
        self.rect = None
        self.start_x = None
        self.start_y = None
        self.roi = None
        
        # 綁定滑鼠與鍵盤事件
        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.root.bind("<Return>", self.on_confirm)
        self.root.bind("<space>", self.on_confirm)
        self.root.bind("<Escape>", self.on_cancel)
        self.root.bind("c", self.on_cancel)

    def on_press(self, event):
        self.start_x = event.x
        self.start_y = event.y
        if self.rect:
            self.canvas.delete(self.rect)
        self.rect = self.canvas.create_rectangle(self.start_x, self.start_y, self.start_x, self.start_y, outline='red', width=3)

    def on_drag(self, event):
        self.canvas.coords(self.rect, self.start_x, self.start_y, event.x, event.y)

    def on_confirm(self, event=None):
        if self.rect:
            x0, y0, x1, y1 = self.canvas.coords(self.rect)
            x = min(x0, x1)
            y = min(y0, y1)
            w = abs(x1 - x0)
            h = abs(y1 - y0)
            if w > 0 and h > 0:
                self.roi = (int(x), int(y), int(w), int(h))
        self.root.quit()

    def on_cancel(self, event=None):
        self.roi = None
        self.root.quit()


def main():
    print("="*50)
    print("🚀 ROI Helper (純 Tkinter 穩健版) 啟動！")
    print("👉 請在 3 秒內將畫面切換到您的「目標軟體 (Simulator)」...")
    print("="*50)
    
    # 給予使用者 3 秒鐘切換視窗
    for i in range(3, 0, -1):
        print(f"倒數 {i} 秒...")
        time.sleep(1)
        
    print("\n📸 正在截取全螢幕... (請勿移動滑鼠)")
    try:
        screenshot = pyautogui.screenshot()
    except Exception as e:
        print(f"⚠️ 截圖失敗: {e}")
        return
        
    screen_w, screen_h = screenshot.size

    # 啟動 Tkinter 框選介面
    root = tk.Tk()
    selector = ROISelector(root, screenshot)
    root.mainloop() # 程式會在此暫停，等待使用者框選完畢
    
    roi = selector.roi
    
    if not roi:
        print("⚠️ 未框選有效範圍或已取消操作。")
        root.destroy()
        return

    x, y, w, h = roi
    
    # 將全螢幕取消，恢復成極小視窗來顯示輸入檔名對話框
    root.attributes('-fullscreen', False)
    root.geometry("0x0+0+0")
    root.update()
    
    # 詢問檔名
    name = get_filename(root)
    root.destroy()
    
    # 計算相對於螢幕的百分比 (取到小數點後三位)
    rx = round(x / screen_w, 3)
    ry = round(y / screen_h, 3)
    rw = round(w / screen_w, 3)
    rh = round(h / screen_h, 3)

    print("\n" + "="*60)
    print("🎉 框選完成！請將以下內容貼入您的 YAML 中：")
    print("="*60)
    
    if name:
        # 如果有輸入名稱，進行存圖
        save_dir = "assets"
        os.makedirs(save_dir, exist_ok=True)
        save_path = f"{save_dir}/{name}.png"
        
        # 裁切並儲存圖片 (直接使用 Pillow)
        crop_img = screenshot.crop((x, y, x+w, y+h))
        crop_img.save(save_path)
        print(f"✅ 圖片已成功儲存至: {save_path}\n")
        
        print(f"📌 [請貼入 roi_map 區塊]:")
        print(f"  {name}_area: [{rx}, {ry}, {rw}, {rh}]\n")
        
        print(f"📌 [請貼入 target_features 區塊]:")
        print(f"  - {{ type: \"image\", path: \"{save_path}\" }}")
    else:
        # 若未輸入名稱，只顯示 ROI
        print(f"\n📌 [純 ROI 座標 (百分比)]:")
        print(f"  [{rx}, {ry}, {rw}, {rh}]")
        
    print("="*60 + "\n")

if __name__ == "__main__":
    main()