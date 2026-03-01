import platform
import ctypes

class SystemAwakeManager:
    """
    千手千眼 AI Agent - 系統狀態管理模組
    負責與作業系統底層 API 溝通，確保 Agent 執行期間：
    1. 系統不會進入睡眠或休眠。
    2. 顯示器不會關閉，確保 GUI 持續渲染。
    3. 螢幕保護程式不會啟動。
    """

    # Windows API 常數定義 (參考微軟官方文件)
    # 宣告狀態需持續維持
    ES_CONTINUOUS = 0x80000000
    # 強制系統保持喚醒 (防止睡眠/休眠)
    ES_SYSTEM_REQUIRED = 0x00000001
    # 強制顯示器保持開啟 (防止關閉螢幕/螢幕保護程式)
    ES_DISPLAY_REQUIRED = 0x00000002

    def __init__(self):
        self.is_windows = platform.system() == "Windows"
        self.is_awake = False

    def keep_awake(self):
        """
        啟動防閒置機制，鎖定系統與顯示器狀態。
        """
        if not self.is_windows:
            print("[SystemAwakeManager] 非 Windows 系統，略過底層喚醒設定。")
            return

        try:
            # 組合 Flags：持續狀態 + 系統喚醒 + 顯示器喚醒
            flags = self.ES_CONTINUOUS | self.ES_SYSTEM_REQUIRED | self.ES_DISPLAY_REQUIRED
            
            # 呼叫 kernel32.dll 的 SetThreadExecutionState
            result = ctypes.windll.kernel32.SetThreadExecutionState(flags)
            
            if result == 0:
                print("[SystemAwakeManager] 警告：無法成功呼叫 SetThreadExecutionState。")
            else:
                self.is_awake = True
                print("[SystemAwakeManager] 🛡️ 防閒置機制已啟動：已鎖定系統不睡眠，且強制顯示器保持開啟 (防黑屏/防螢幕保護)。")
        except Exception as e:
            print(f"[SystemAwakeManager] ❌ 啟動防閒置機制時發生未預期錯誤: {e}")

    def release(self):
        """
        解除防閒置機制，允許系統恢復正常的電源管理設定。
        """
        if not self.is_windows or not self.is_awake:
            return

        try:
            # 只傳入 ES_CONTINUOUS，代表清除之前設定的 REQUIRED 狀態
            result = ctypes.windll.kernel32.SetThreadExecutionState(self.ES_CONTINUOUS)
            
            if result == 0:
                print("[SystemAwakeManager] 警告：無法成功釋放執行狀態。")
            else:
                self.is_awake = False
                print("[SystemAwakeManager] 🔓 防閒置機制已解除：系統已恢復正常的電源與顯示器休眠設定。")
        except Exception as e:
            print(f"[SystemAwakeManager] ❌ 解除防閒置機制時發生未預期錯誤: {e}")

# ---------------------------------------------------------
# 單元測試 (僅供本機執行此檔案時測試驗證)
# ---------------------------------------------------------
if __name__ == "__main__":
    import time
    
    print("=== 系統防閒置管理模組測試 ===")
    awake_manager = SystemAwakeManager()
    
    # 啟動保護
    awake_manager.keep_awake()
    
    print("\n[測試] 進入模擬工作狀態 (10秒)...")
    print("在此期間，您可以嘗試手動啟動螢幕保護程式，或者觀察系統是否會自動休眠 (如果您的設定低於10秒)。")
    for i in range(10, 0, -1):
        print(f"工作倒數: {i} 秒", end="\r")
        time.sleep(1)
    
    print("\n\n[測試] 工作結束，準備釋放資源...")
    # 解除保護
    awake_manager.release()
    print("=== 測試完成 ===")