import tkinter as tk
from tkinter import ttk, messagebox
import yaml
import os
import time
import shutil
import threading
import importlib.util
import sys
from datetime import datetime

# ==============================================================================
# [NEW] 智慧路徑解析與工作目錄對齊 (Smart Path Resolution)
# ==============================================================================
if getattr(sys, 'frozen', False):
    # 產線模式: 被 PyInstaller 打包成 .exe 執行
    # 基準路徑就是 .exe 所在的資料夾
    BASE_PATH = os.path.dirname(sys.executable)
    PROJECT_ROOT = BASE_PATH
else:
    # 開發模式: 直接透過 Python 直譯器執行 (.py)
    # 基準路徑是這個 .py 檔所在的 client/ 資料夾
    BASE_PATH = os.path.dirname(os.path.abspath(__file__))
    # 專案根目錄是 client/ 的上一層 (即 RcpAgent/)
    PROJECT_ROOT = os.path.dirname(BASE_PATH)

# 強制將工作目錄 (CWD) 切換到專案根目錄
# 這樣 Engine 裡所有的相對路徑 (如 assets/, core/, workflows/, logs/) 絕對不會迷路！
os.chdir(PROJECT_ROOT)

class MinionClient(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("🤖 RcpAgent Minion - Wafer Load")
        self.geometry("380x250")
        self.resizable(False, False)
        
        # 設定檔永遠跟著 minion_client (.py 或 .exe) 放在同一個資料夾
        self.config_path = os.path.join(BASE_PATH, "minion_config.yaml")
        self.minion_config = self._load_config()
        
        self._init_ui()

    def _load_config(self):
        if not os.path.exists(self.config_path):
            messagebox.showerror("錯誤", f"找不到設定檔:\n{self.config_path}\n\n請確保設定檔與程式放在同一個目錄下。")
            self.destroy()
            return {}
        with open(self.config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)

    def _init_ui(self):
        main_frame = ttk.Frame(self, padding="20 20 20 20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="Wafer Load SOP 執行器", font=("Arial", 14, "bold")).pack(pady=(0, 15))

        # Recipe Name Input
        frame_recipe = ttk.Frame(main_frame)
        frame_recipe.pack(fill=tk.X, pady=5)
        ttk.Label(frame_recipe, text="Recipe Name:", width=12).pack(side=tk.LEFT)
        self.entry_recipe = ttk.Entry(frame_recipe)
        self.entry_recipe.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.entry_recipe.insert(0, "default_recipe.xml")

        # Slot ID Input
        frame_slot = ttk.Frame(main_frame)
        frame_slot.pack(fill=tk.X, pady=5)
        ttk.Label(frame_slot, text="Slot ID:", width=12).pack(side=tk.LEFT)
        self.entry_slot = ttk.Entry(frame_slot)
        self.entry_slot.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.entry_slot.insert(0, "1")

        # Status Label
        self.lbl_status = ttk.Label(main_frame, text="準備就緒", foreground="gray")
        self.lbl_status.pack(pady=10)

        # Run Button
        self.btn_run = ttk.Button(main_frame, text="▶ 開始執行 (Run)", command=self.start_execution)
        self.btn_run.pack(fill=tk.X, pady=5)

    def _replace_placeholders(self, data, recipe_name, slot_offset_val):
        """遞迴遍歷 YAML 資料，替換 {recipe_name} 與 {slot_offset}"""
        if isinstance(data, dict):
            for k, v in data.items():
                if isinstance(v, str):
                    if v == "{slot_offset}":
                        data[k] = slot_offset_val
                    elif "{recipe_name}" in v:
                        data[k] = v.replace("{recipe_name}", recipe_name)
                else:
                    self._replace_placeholders(v, recipe_name, slot_offset_val)
        elif isinstance(data, list):
            for i, v in enumerate(data):
                if isinstance(v, str):
                    if v == "{slot_offset}":
                        data[i] = slot_offset_val
                    elif "{recipe_name}" in v:
                        data[i] = v.replace("{recipe_name}", recipe_name)
                else:
                    self._replace_placeholders(v, recipe_name, slot_offset_val)

    def start_execution(self):
        recipe = self.entry_recipe.get().strip()
        slot = self.entry_slot.get().strip()

        if not recipe or not slot:
            messagebox.showwarning("警告", "Recipe Name 與 Slot ID 不可為空！")
            return

        slot_mapping = self.minion_config.get("slot_mapping", {})
        if slot not in slot_mapping:
            messagebox.showwarning("警告", f"未知的 Slot ID '{slot}'，請檢查 minion_config.yaml")
            return

        slot_offset = slot_mapping[slot]
        
        # 防止重複點擊，隱藏視窗
        self.btn_run.config(state=tk.DISABLED)
        self.lbl_status.config(text="執行中... 視窗即將隱藏", foreground="blue")
        self.update()
        time.sleep(0.5) 
        
        # 收下/隱藏視窗
        self.withdraw()

        # 開啟獨立執行緒執行 SOP，避免阻塞 GUI
        threading.Thread(
            target=self._run_engine_task, 
            args=(recipe, slot, slot_offset), 
            daemon=True
        ).start()

    def _run_engine_task(self, recipe, slot, slot_offset):
        client_cfg = self.minion_config.get("client_config", {})
        base_sop_path = client_cfg.get("base_sop", "workflows/sop_tbs_002_workflow.yaml")
        engine_script = client_cfg.get("engine_script", "core/lite_gui_engine.py")
        engine_class = client_cfg.get("engine_class", "AgentEngine")
        result_base = client_cfg.get("result_base_dir", "results")

        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        result_dir = os.path.join(result_base, f"Run_{timestamp_str}")
        
        try:
            # 1. 建立當次 Result 資料夾
            os.makedirs(result_dir, exist_ok=True)
            
            # 2. 載入基礎 SOP 並置換參數
            with open(base_sop_path, 'r', encoding='utf-8') as f:
                sop_data = yaml.safe_load(f)
                
            self._replace_placeholders(sop_data, recipe, slot_offset)
            
            # 3. 另存本次執行的 YAML 到 Result 資料夾
            run_yaml_path = os.path.join(result_dir, "executed_sop.yaml")
            with open(run_yaml_path, 'w', encoding='utf-8') as f:
                yaml.dump(sop_data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

            # 4. 紀錄執行前時間 (用來過濾稍後產生的 log/截圖)
            start_time = time.time()

            # 5. 動態載入 Engine
            spec = importlib.util.spec_from_file_location("dynamic_engine", engine_script)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            EngineClass = getattr(module, engine_class)
            
            # 6. 初始化並執行
            engine_instance = EngineClass(run_yaml_path)
            report = engine_instance.run()

            # 7. 整理產物：將 engine 剛才在 logs/ 底下產生的檔案搬到 result_dir
            if os.path.exists("logs"):
                for filename in os.listdir("logs"):
                    filepath = os.path.join("logs", filename)
                    # 只要是這次執行期間新產生/修改的檔案，就搬過去
                    if os.path.isfile(filepath) and os.path.getmtime(filepath) >= start_time:
                        shutil.move(filepath, os.path.join(result_dir, filename))
            
            status_text = f"✅ 執行完成!\n結果: {report.get('status')}\n產物已存放於:\n{result_dir}"
            messagebox.showinfo("任務結束", status_text)

        except Exception as e:
            messagebox.showerror("執行錯誤", f"任務執行失敗:\n{e}")
        finally:
            # 任務結束，透過 tkinter 的 after 方法安全地在主執行緒還原視窗
            self.after(0, self._restore_ui)

    def _restore_ui(self):
        self.deiconify() # 重新顯示視窗
        self.btn_run.config(state=tk.NORMAL)
        self.lbl_status.config(text="等待下一次任務", foreground="gray")
        self.entry_recipe.delete(0, tk.END)
        self.entry_slot.delete(0, tk.END)
        
        # 讓視窗強迫置頂提醒使用者任務結束
        self.attributes('-topmost', True)
        self.after(1000, lambda: self.attributes('-topmost', False))

if __name__ == "__main__":
    app = MinionClient()
    app.mainloop()