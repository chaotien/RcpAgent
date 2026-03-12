import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import yaml
import os
import time
import shutil
import threading
import importlib.util
import sys
import ctypes
from datetime import datetime

# ==============================================================================
# [智慧路徑解析與工作目錄對齊]
# ==============================================================================
if getattr(sys, 'frozen', False):
    # 產線模式: 被 PyInstaller 打包成 .exe 執行
    BASE_PATH = os.path.dirname(sys.executable)
    PROJECT_ROOT = BASE_PATH
else:
    # 開發模式: 直接透過 Python 直譯器執行 (.py)
    BASE_PATH = os.path.dirname(os.path.abspath(__file__))
    PROJECT_ROOT = os.path.dirname(BASE_PATH)

# 強制將工作目錄 (CWD) 切換到專案根目錄
os.chdir(PROJECT_ROOT)

class MinionClient(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("🤖 RcpAgent Minion - Task Runner")
        self.geometry("480x380") # 加大視窗以容納新的路徑選擇欄位
        self.resizable(False, False)
        
        # 設定視窗 Icon (支援 .ico 或 .png)
        ico_path = os.path.join(BASE_PATH, "minion.ico")
        png_path = os.path.join(BASE_PATH, "minion.png")
        try:
            if os.path.exists(ico_path):
                self.iconbitmap(ico_path)
            elif os.path.exists(png_path):
                icon_img = tk.PhotoImage(file=png_path)
                self.iconphoto(False, icon_img)
        except Exception as e:
            print(f"⚠️ 無法載入 Icon: {e}")
        
        # 綁定視窗關閉事件
        self.protocol("WM_DELETE_WINDOW", self._on_closing)
        
        # 載入 Config
        self.config_path = os.path.join(BASE_PATH, "minion_config.yaml")
        self.minion_config = self._load_config()
        
        self._init_ui()
        
        # 啟動 OS 級防閒置
        self._enable_windows_awake()

    def _enable_windows_awake(self):
        """呼叫 Windows API 防止螢幕鎖定與休眠"""
        if os.name == 'nt':
            try:
                ctypes.windll.kernel32.SetThreadExecutionState(0x80000000 | 0x00000002 | 0x00000001)
                self.lbl_idle.config(text="🛡️ OS 級防鎖定保護已啟動 (Active)", foreground="#4CAF50")
            except Exception as e:
                self.lbl_idle.config(text=f"⚠️ 防鎖定啟動失敗: {e}", foreground="red")

    def _disable_windows_awake(self):
        """還原 Windows 原本的休眠與鎖定設定"""
        if os.name == 'nt':
            try:
                ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)
            except Exception:
                pass

    def _on_closing(self):
        self._disable_windows_awake()
        self.destroy()

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

        ttk.Label(main_frame, text="Wafer Load SOP 執行器", font=("Arial", 14, "bold")).pack(pady=(0, 10))

        self.lbl_idle = ttk.Label(main_frame, text="🛡️ 防鎖定保護啟動中...", foreground="gray", font=("Arial", 9))
        self.lbl_idle.pack(pady=(0, 10))

        client_cfg = self.minion_config.get("client_config", {})
        default_wf = client_cfg.get("base_sop", "workflows/sop_wafer_load_template.yaml")
        default_engine = client_cfg.get("engine_script", "core/lite_gui_engine.py")

        # ==========================================
        # [NEW] Workflow 選擇
        # ==========================================
        frame_wf = ttk.Frame(main_frame)
        frame_wf.pack(fill=tk.X, pady=5)
        ttk.Label(frame_wf, text="Workflow:", width=12).pack(side=tk.LEFT)
        self.entry_wf = ttk.Entry(frame_wf)
        self.entry_wf.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.entry_wf.insert(0, default_wf)
        btn_browse_wf = ttk.Button(frame_wf, text="...", width=3, command=self._browse_wf)
        btn_browse_wf.pack(side=tk.LEFT, padx=(5, 0))

        # ==========================================
        # [NEW] Engine 選擇
        # ==========================================
        frame_engine = ttk.Frame(main_frame)
        frame_engine.pack(fill=tk.X, pady=5)
        ttk.Label(frame_engine, text="Engine:", width=12).pack(side=tk.LEFT)
        self.entry_engine = ttk.Entry(frame_engine)
        self.entry_engine.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.entry_engine.insert(0, default_engine)
        btn_browse_engine = ttk.Button(frame_engine, text="...", width=3, command=self._browse_engine)
        btn_browse_engine.pack(side=tk.LEFT, padx=(5, 0))

        ttk.Separator(main_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)

        # ==========================================
        # Recipe & Slot 輸入
        # ==========================================
        frame_recipe = ttk.Frame(main_frame)
        frame_recipe.pack(fill=tk.X, pady=5)
        ttk.Label(frame_recipe, text="Recipe Name:", width=12).pack(side=tk.LEFT)
        self.entry_recipe = ttk.Entry(frame_recipe)
        self.entry_recipe.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.entry_recipe.insert(0, "default_recipe.xml")

        frame_slot = ttk.Frame(main_frame)
        frame_slot.pack(fill=tk.X, pady=5)
        ttk.Label(frame_slot, text="Slot ID:", width=12).pack(side=tk.LEFT)
        self.entry_slot = ttk.Entry(frame_slot)
        self.entry_slot.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.entry_slot.insert(0, "1")

        self.lbl_status = ttk.Label(main_frame, text="準備就緒", foreground="gray")
        self.lbl_status.pack(pady=10)

        self.btn_run = ttk.Button(main_frame, text="▶ 開始執行 (Run)", command=self.start_execution)
        self.btn_run.pack(fill=tk.X, pady=5)

    def _browse_wf(self):
        path = filedialog.askopenfilename(
            initialdir=PROJECT_ROOT,
            title="選擇 Workflow 劇本檔",
            filetypes=[("YAML files", "*.yaml"), ("All files", "*.*")]
        )
        if path:
            # 轉換為相對路徑 (若在專案目錄下) 以保持畫面簡潔
            try: path = os.path.relpath(path, PROJECT_ROOT)
            except: pass
            self.entry_wf.delete(0, tk.END)
            self.entry_wf.insert(0, path)

    def _browse_engine(self):
        path = filedialog.askopenfilename(
            initialdir=os.path.join(PROJECT_ROOT, "core"),
            title="選擇 Engine 引擎檔",
            filetypes=[("Python files", "*.py"), ("All files", "*.*")]
        )
        if path:
            try: path = os.path.relpath(path, PROJECT_ROOT)
            except: pass
            self.entry_engine.delete(0, tk.END)
            self.entry_engine.insert(0, path)

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
        wf_path = self.entry_wf.get().strip()
        engine_path = self.entry_engine.get().strip()
        recipe = self.entry_recipe.get().strip()
        slot = self.entry_slot.get().strip()

        if not wf_path or not engine_path:
            messagebox.showwarning("警告", "Workflow 與 Engine 路徑不可為空！")
            return
        if not os.path.exists(wf_path):
            messagebox.showwarning("警告", f"找不到 Workflow 檔案: \n{wf_path}")
            return
        if not os.path.exists(engine_path):
            messagebox.showwarning("警告", f"找不到 Engine 檔案: \n{engine_path}")
            return
        if not recipe or not slot:
            messagebox.showwarning("警告", "Recipe Name 與 Slot ID 不可為空！")
            return

        slot_mapping = self.minion_config.get("slot_mapping", {})
        if slot not in slot_mapping:
            messagebox.showwarning("警告", f"未知的 Slot ID '{slot}'，請檢查 minion_config.yaml")
            return

        slot_offset = slot_mapping[slot]
        
        self.btn_run.config(state=tk.DISABLED)
        self.lbl_status.config(text="執行中... 視窗即將隱藏", foreground="blue")
        self.update()
        time.sleep(0.5) 
        
        self.withdraw()

        threading.Thread(
            target=self._run_engine_task, 
            args=(wf_path, engine_path, recipe, slot, slot_offset), 
            daemon=True
        ).start()

    def _run_engine_task(self, base_sop_path, engine_script, recipe, slot, slot_offset):
        client_cfg = self.minion_config.get("client_config", {})
        engine_class = client_cfg.get("engine_class", "AgentEngine") # 類別名稱通常保持不變
        result_base = client_cfg.get("result_base_dir", "results")

        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        result_dir = os.path.join(result_base, f"Run_{timestamp_str}")
        
        try:
            os.makedirs(result_dir, exist_ok=True)
            
            with open(base_sop_path, 'r', encoding='utf-8') as f:
                sop_data = yaml.safe_load(f)
                
            self._replace_placeholders(sop_data, recipe, slot_offset)
            
            run_yaml_path = os.path.join(result_dir, "executed_sop.yaml")
            with open(run_yaml_path, 'w', encoding='utf-8') as f:
                yaml.dump(sop_data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

            start_time = time.time()

            # 動態載入使用者選擇的 Engine
            spec = importlib.util.spec_from_file_location("dynamic_engine", engine_script)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            EngineClass = getattr(module, engine_class)
            
            engine_instance = EngineClass(run_yaml_path)
            report = engine_instance.run()
            
            # [FIX] 增加緩衝時間，確保 Engine 已經完全釋放 File Handles
            # 特別是 Python 的 logging module 有時會稍微延遲釋放
            time.sleep(1.0) 

            # [FIX] 優化的產物收集邏輯 (加入重試與忽略無法搬移的檔案)
            if os.path.exists("logs"):
                for filename in os.listdir("logs"):
                    filepath = os.path.join("logs", filename)
                    if os.path.isfile(filepath) and os.path.getmtime(filepath) >= start_time:
                        dest_path = os.path.join(result_dir, filename)
                        
                        # 加入重試機制
                        max_retries = 3
                        for i in range(max_retries):
                            try:
                                # 優先嘗試 move，若失敗可能是權限或鎖定問題
                                shutil.move(filepath, dest_path)
                                break # 成功就跳出重試迴圈
                            except PermissionError as e:
                                print(f"⚠️ [Log Move] Permission denied for {filename}, retrying ({i+1}/{max_retries})...")
                                time.sleep(0.5)
                            except Exception as e:
                                print(f"⚠️ [Log Move] Unexpected error moving {filename}: {e}")
                                # 若 move 一直失敗，嘗試用 copy 再刪除 (有時能繞過某些鎖定)
                                try:
                                    shutil.copy2(filepath, dest_path)
                                    # 注意：這裡不強制刪除來源檔，避免再次報錯，大不了留在 logs/ 裡
                                    break
                                except Exception:
                                    pass

            
            status_text = f"✅ 執行完成!\n結果: {report.get('status')}\n產物已存放於:\n{result_dir}"
            messagebox.showinfo("任務結束", status_text)

        except Exception as e:
            messagebox.showerror("執行錯誤", f"任務執行失敗:\n{e}")
        finally:
            self.after(0, self._restore_ui)

    def _restore_ui(self):
        self.deiconify() 
        self.btn_run.config(state=tk.NORMAL)
        self.lbl_status.config(text="等待下一次任務", foreground="gray")
        self.entry_recipe.delete(0, tk.END)
        self.entry_slot.delete(0, tk.END)
        
        self.attributes('-topmost', True)
        self.after(1000, lambda: self.attributes('-topmost', False))

if __name__ == "__main__":
    app = MinionClient()
    app.mainloop()