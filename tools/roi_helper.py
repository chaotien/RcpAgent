import sys
import os
import pyautogui
from PyQt5.QtWidgets import QApplication, QWidget, QInputDialog
from PyQt5.QtCore import Qt, QRect
from PyQt5.QtGui import QPainter, QColor, QPen

class SnippingWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet("background-color: rgba(0, 0, 0, 100);") # 半透明黑底
        
        # 取得全螢幕尺寸並設置視窗
        self.screen_geometry = QApplication.primaryScreen().geometry()
        self.setGeometry(self.screen_geometry)
        
        self.begin = None
        self.end = None
        self.setCursor(Qt.CrossCursor)

    def paintEvent(self, event):
        if self.begin and self.end:
            painter = QPainter(self)
            painter.setPen(QPen(QColor(255, 0, 0), 2))
            painter.setBrush(QColor(0, 0, 0, 0)) # 透明框內部
            rect = QRect(self.begin, self.end).normalized()
            painter.drawRect(rect)

    def mousePressEvent(self, event):
        self.begin = event.pos()
        self.end = self.begin
        self.update()

    def mouseMoveEvent(self, event):
        self.end = event.pos()
        self.update()

    def mouseReleaseEvent(self, event):
        self.close()
        rect = QRect(self.begin, self.end).normalized()
        self.process_selection(rect)

    def process_selection(self, rect):
        if rect.width() < 10 or rect.height() < 10:
            print("❌ 選取範圍太小，已取消。")
            return

        # 1. 儲存圖片
        if not os.path.exists("../assets"):
            os.makedirs("../assets")
            
        name, ok = QInputDialog.getText(self, '儲存圖檔', '請輸入圖片名稱 (不含副檔名, 例: roi_menu):')
        if not ok or not name:
            name = "temp_capture"
            
        filepath = f"../assets/{name}.png"
        
        # PyAutoGUI 截取實際畫面
        img = pyautogui.screenshot(region=(rect.x(), rect.y(), rect.width(), rect.height()))
        img.save(filepath)

        # 2. 計算 ROI 百分比
        sw, sh = self.screen_geometry.width(), self.screen_geometry.height()
        rx = round(rect.x() / sw, 3)
        ry = round(rect.y() / sh, 3)
        rw = round(rect.width() / sw, 3)
        rh = round(rect.height() / sh, 3)

        print("\n" + "="*50)
        print("🎉 截圖成功！請將以下內容貼入您的 YAML 中：")
        print("="*50)
        print("\n📌 [放入 roi_map 區塊]:")
        print(f"  {name}_area: [{rx}, {ry}, {rw}, {rh}]")
        print("\n📌 [放入 target_features 區塊]:")
        print(f"  - {{ type: \"image\", path: \"assets/{name}.png\" }}")
        print("\n" + "="*50 + "\n")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = SnippingWidget()
    ex.show()
    sys.exit(app.exec_())