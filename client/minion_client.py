try: # 僅供 PyInstaller 掃描用，實際邏輯不會用到
    import pyautogui
    import cv2
    import numpy
    import PIL
    import yaml
except ImportError:
    pass
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
import json
import inspect
from datetime import datetime

# ==============================================================================
# [智慧路徑解析與工作目錄對齊]
# ==============================================================================
if getattr(sys, 'frozen', False):
    BASE_PATH = os.path.dirname(sys.executable)
    PROJECT_ROOT = BASE_PATH
else:
    BASE_PATH = os.path.dirname(os.path.abspath(__file__))
    PROJECT_ROOT = os.path.dirname(BASE_PATH)

os.chdir(PROJECT_ROOT)

class MinionClient(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("yRcpMinion 🤖")
        self.geometry("480x420") # 加高視窗以容納 Asset 路徑欄位
        self.resizable(False, False)
        
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
        
        self.protocol("WM_DELETE_WINDOW", self._on_closing)
        self.config_path = os.path.join(BASE_PATH, "minion_config.yaml")
        self.minion_config = self._load_config()
        self._init_ui()
        self._enable_windows_awake()

    def _enable_windows_awake(self):
        if os.name == 'nt':
            try:
                ctypes.windll.kernel32.SetThreadExecutionState(0x80000000 | 0x00000002 | 0x00000001)
                self.lbl_idle.config(text="🛡️ OS 級防鎖定保護已啟動 (Active)", foreground="#4CAF50")
            except Exception as e:
                self.lbl_idle.config(text=f"⚠️ 防鎖定啟動失敗: {e}", foreground="red")

    def _disable_windows_awake(self):
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

        ttk.Label(main_frame, text="SOP Executor", font=("Arial", 14, "bold")).pack(pady=(0, 10))
        self.lbl_idle = ttk.Label(main_frame, text="🛡️ 防鎖定保護啟動中...", foreground="gray", font=("Arial", 9))
        self.lbl_idle.pack(pady=(0, 10))

        client_cfg = self.minion_config.get("client_config", {})
        default_wf = client_cfg.get("base_sop", "workflows/sop_wafer_load_template.yaml")
        default_engine = client_cfg.get("engine_script", "core/auto_gui_engine_lite.py")
        default_asset = client_cfg.get("default_asset_dir", "assets")

        # 1. Workflow 選擇
        frame_wf = ttk.Frame(main_frame)
        frame_wf.pack(fill=tk.X, pady=5)
        ttk.Label(frame_wf, text="Workflow:", width=12).pack(side=tk.LEFT)
        self.entry_wf = ttk.Entry(frame_wf)
        self.entry_wf.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.entry_wf.insert(0, default_wf)
        ttk.Button(frame_wf, text="...", width=3, command=self._browse_wf).pack(side=tk.LEFT, padx=(5, 0))

        # 2. Engine 選擇
        frame_engine = ttk.Frame(main_frame)
        frame_engine.pack(fill=tk.X, pady=5)
        ttk.Label(frame_engine, text="Engine:", width=12).pack(side=tk.LEFT)
        self.entry_engine = ttk.Entry(frame_engine)
        self.entry_engine.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.entry_engine.insert(0, default_engine)
        ttk.Button(frame_engine, text="...", width=3, command=self._browse_engine).pack(side=tk.LEFT, padx=(5, 0))

        # 3. [NEW] Asset Directory 選擇
        frame_asset = ttk.Frame(main_frame)
        frame_asset.pack(fill=tk.X, pady=5)
        ttk.Label(frame_asset, text="Assets Dir:", width=12).pack(side=tk.LEFT)
        self.entry_asset = ttk.Entry(frame_asset)
        self.entry_asset.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.entry_asset.insert(0, default_asset)
        ttk.Button(frame_asset, text="...", width=3, command=self._browse_asset).pack(side=tk.LEFT, padx=(5, 0))

        ttk.Separator(main_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)

        # Recipe Name
        frame_recipe = ttk.Frame(main_frame)
        frame_recipe.pack(fill=tk.X, pady=5)
        ttk.Label(frame_recipe, text="Recipe Name:", width=12).pack(side=tk.LEFT)
        self.entry_recipe = ttk.Entry(frame_recipe)
        self.entry_recipe.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.entry_recipe.insert(0, "default_recipe.xml")

        # Slot ID
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
        path = filedialog.askopenfilename(initialdir=PROJECT_ROOT, filetypes=[("YAML", "*.yaml"), ("All", "*.*")])
        if path:
            try: path = os.path.relpath(path, PROJECT_ROOT)
            except: pass
            self.entry_wf.delete(0, tk.END)
            self.entry_wf.insert(0, path)

    def _browse_engine(self):
        path = filedialog.askopenfilename(initialdir=os.path.join(PROJECT_ROOT, "core"), filetypes=[("Python", "*.py"), ("All", "*.*")])
        if path:
            try: path = os.path.relpath(path, PROJECT_ROOT)
            except: pass
            self.entry_engine.delete(0, tk.END)
            self.entry_engine.insert(0, path)

    def _browse_asset(self):
        # 選擇資料夾 (Directory)
        path = filedialog.askdirectory(initialdir=os.path.join(PROJECT_ROOT, "assets"), title="選擇機台截圖包資料夾")
        if path:
            try: path = os.path.relpath(path, PROJECT_ROOT)
            except: pass
            self.entry_asset.delete(0, tk.END)
            self.entry_asset.insert(0, path)

    def start_execution(self):
        wf_path = self.entry_wf.get().strip()
        engine_path = self.entry_engine.get().strip()
        asset_dir = self.entry_asset.get().strip()
        recipe = self.entry_recipe.get().strip()
        slot = self.entry_slot.get().strip()

        if not all([wf_path, engine_path, asset_dir, recipe, slot]):
            messagebox.showwarning("警告", "所有欄位皆不可為空！")
            return
        if not os.path.exists(asset_dir):
            messagebox.showwarning("警告", f"找不到截圖包目錄: \n{asset_dir}")
            return

        slot_mapping = self.minion_config.get("slot_mapping", {})
        if slot not in slot_mapping:
            messagebox.showwarning("警告", f"未知的 Slot ID '{slot}'")
            return

        slot_offset = slot_mapping[slot]
        
        self.btn_run.config(state=tk.DISABLED)
        self.lbl_status.config(text="執行中... 視窗即將隱藏", foreground="blue")
        self.update()
        time.sleep(0.5) 
        self.withdraw()

        threading.Thread(
            target=self._run_engine_task, 
            args=(wf_path, engine_path, asset_dir, recipe, slot_offset), 
            daemon=True
        ).start()

    def _run_engine_task(self, base_sop_path, engine_script, asset_dir, recipe, slot_offset):
        client_cfg = self.minion_config.get("client_config", {})
        engine_class = client_cfg.get("engine_class", "AgentEngine") 
        result_base = client_cfg.get("result_base_dir", "results")

        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        result_dir = os.path.join(result_base, f"Run_{timestamp_str}")
        
        try:
            os.makedirs(result_dir, exist_ok=True)
            
            run_yaml_path = os.path.join(result_dir, "executed_sop.yaml")
            shutil.copy2(base_sop_path, run_yaml_path)

            # ========================================================
            # [核心升級] 將 asset_dir 注入到 dynamic_vars 中
            # ========================================================
            dynamic_vars = {
                "asset_dir": asset_dir,     # 給 VisionSystem 找圖用
                "recipe_name": recipe,      # 給 Action 輸入文字用
                "slot_offset": slot_offset  # 給 Action 點擊位移用
            }
            
            with open(os.path.join(result_dir, "run_params.json"), "w", encoding="utf-8") as f:
                json.dump(dynamic_vars, f, indent=4, ensure_ascii=False)

            start_time = time.time()

            spec = importlib.util.spec_from_file_location("dynamic_engine", engine_script)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            EngineClass = getattr(module, engine_class)
            
            sig = inspect.signature(EngineClass.__init__)
            if "dynamic_vars" in sig.parameters:
                engine_instance = EngineClass(run_yaml_path, dynamic_vars=dynamic_vars)
            else:
                print("⚠️ [Warning] 所選的 Engine 不支援 dynamic_vars，將退回傳統模式。")
                engine_instance = EngineClass(run_yaml_path)
                
            report = engine_instance.run()
            time.sleep(1.0) 

            if os.path.exists("logs"):
                for filename in os.listdir("logs"):
                    filepath = os.path.join("logs", filename)
                    if os.path.isfile(filepath) and os.path.getmtime(filepath) >= start_time:
                        dest_path = os.path.join(result_dir, filename)
                        for i in range(3):
                            try:
                                shutil.move(filepath, dest_path)
                                break 
                            except Exception:
                                time.sleep(0.5)
                        else:
                            try: shutil.copy2(filepath, dest_path)
                            except: pass

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
        self.attributes('-topmost', True)
        self.after(1000, lambda: self.attributes('-topmost', False))

if __name__ == "__main__":
    app = MinionClient()
    app.mainloop()