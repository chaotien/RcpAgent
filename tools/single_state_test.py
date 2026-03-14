import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import yaml
import os
import sys
import json
import time
import threading
import importlib.util
import inspect

# ==============================================================================
# [智慧路徑解析與工作目錄對齊]
# ==============================================================================
if getattr(sys, 'frozen', False):
    BASE_PATH = os.path.dirname(sys.executable)
    PROJECT_ROOT = os.path.dirname(BASE_PATH)
else:
    BASE_PATH = os.path.dirname(os.path.abspath(__file__))
    # 因為這個腳本在 tools/ 底下，所以專案根目錄是上一層
    PROJECT_ROOT = os.path.dirname(BASE_PATH)

os.chdir(PROJECT_ROOT)

class StateTestingTool(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("🧪 RcpAgent 狀態單步測試工具 (State Testing Tool)")
        self.geometry("550x550")
        self.resizable(False, False)
        
        # 嘗試載入 Minion Config 取得預設值
        self.config_path = os.path.join(PROJECT_ROOT, "client", "minion_config.yaml")
        self.minion_config = self._load_config()
        
        self.engine_instance = None
        self._init_ui()

    def _load_config(self):
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    return yaml.safe_load(f)
            except Exception:
                pass
        return {}

    def _init_ui(self):
        main_frame = ttk.Frame(self, padding="20 20 20 20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="SOP 節點單步除錯器", font=("Arial", 14, "bold")).pack(pady=(0, 15))

        client_cfg = self.minion_config.get("client_config", {})
        default_wf = client_cfg.get("base_sop", "workflows/sop_wafer_load_template.yaml")
        default_engine = client_cfg.get("engine_script", "core/auto_gui_engine_lite.py")
        default_asset = client_cfg.get("default_asset_dir", "assets")

        # 1. Workflow
        frame_wf = ttk.Frame(main_frame)
        frame_wf.pack(fill=tk.X, pady=5)
        ttk.Label(frame_wf, text="Workflow:", width=12).pack(side=tk.LEFT)
        self.entry_wf = ttk.Entry(frame_wf)
        self.entry_wf.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.entry_wf.insert(0, default_wf)
        ttk.Button(frame_wf, text="...", width=3, command=self._browse_wf).pack(side=tk.LEFT, padx=(5, 0))

        # 2. Engine
        frame_engine = ttk.Frame(main_frame)
        frame_engine.pack(fill=tk.X, pady=5)
        ttk.Label(frame_engine, text="Engine:", width=12).pack(side=tk.LEFT)
        self.entry_engine = ttk.Entry(frame_engine)
        self.entry_engine.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.entry_engine.insert(0, default_engine)
        ttk.Button(frame_engine, text="...", width=3, command=self._browse_engine).pack(side=tk.LEFT, padx=(5, 0))

        # 3. Asset Directory
        frame_asset = ttk.Frame(main_frame)
        frame_asset.pack(fill=tk.X, pady=5)
        ttk.Label(frame_asset, text="Assets Dir:", width=12).pack(side=tk.LEFT)
        self.entry_asset = ttk.Entry(frame_asset)
        self.entry_asset.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.entry_asset.insert(0, default_asset)
        ttk.Button(frame_asset, text="...", width=3, command=self._browse_asset).pack(side=tk.LEFT, padx=(5, 0))

        # 4. Dynamic Vars (JSON)
        frame_vars = ttk.Frame(main_frame)
        frame_vars.pack(fill=tk.X, pady=5)
        ttk.Label(frame_vars, text="注入變數(JSON):", width=12).pack(side=tk.LEFT)
        self.entry_vars = ttk.Entry(frame_vars)
        self.entry_vars.pack(side=tk.LEFT, fill=tk.X, expand=True)
        # 預設放入測試用的假資料
        self.entry_vars.insert(0, '{"recipe_name": "test.xml", "slot_offset": [0, 30]}')

        ttk.Separator(main_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=15)

        # 5. Load States Button
        self.btn_load = ttk.Button(main_frame, text="🔄 解析並載入 Workflow 狀態 (Load States)", command=self.load_states)
        self.btn_load.pack(fill=tk.X, pady=5)

        # 6. State Dropdown
        frame_state = ttk.Frame(main_frame)
        frame_state.pack(fill=tk.X, pady=5)
        ttk.Label(frame_state, text="選擇測試節點:", width=12).pack(side=tk.LEFT)
        self.combo_states = ttk.Combobox(frame_state, state="readonly")
        self.combo_states.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # 7. Test Action
        self.btn_test = ttk.Button(main_frame, text="⚡ 單步執行此狀態 (Test State)", command=self.test_state, state=tk.DISABLED)
        self.btn_test.pack(fill=tk.X, pady=10)

        # 8. Output Result
        ttk.Label(main_frame, text="執行結果 (Result Next State):").pack(anchor=tk.W)
        self.lbl_result = ttk.Label(main_frame, text="-", font=("Consolas", 12, "bold"), foreground="blue")
        self.lbl_result.pack(anchor=tk.W, pady=5)

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
        path = filedialog.askdirectory(initialdir=os.path.join(PROJECT_ROOT, "assets"))
        if path:
            try: path = os.path.relpath(path, PROJECT_ROOT)
            except: pass
            self.entry_asset.delete(0, tk.END)
            self.entry_asset.insert(0, path)

    def load_states(self):
        wf_path = self.entry_wf.get().strip()
        if not os.path.exists(wf_path):
            messagebox.showwarning("警告", f"找不到 Workflow 檔案: \n{wf_path}")
            return
            
        try:
            with open(wf_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
            
            states_list = data.get("states", [])
            if not states_list:
                messagebox.showinfo("提示", "此 YAML 中沒有定義任何 'states'")
                return
                
            state_names = [s.get("name") for s in states_list if "name" in s]
            self.combo_states['values'] = state_names
            
            if state_names:
                self.combo_states.current(0)
                self.btn_test.config(state=tk.NORMAL)
                messagebox.showinfo("成功", f"成功解析 {len(state_names)} 個狀態節點！")
                
        except Exception as e:
            messagebox.showerror("解析失敗", f"讀取 YAML 發生錯誤:\n{e}")

    def test_state(self):
        selected_state = self.combo_states.get()
        if not selected_state: return

        wf_path = self.entry_wf.get().strip()
        engine_path = self.entry_engine.get().strip()
        asset_dir = self.entry_asset.get().strip()
        vars_json_str = self.entry_vars.get().strip()

        # 解析 JSON 變數
        dynamic_vars = {}
        try:
            if vars_json_str:
                dynamic_vars = json.loads(vars_json_str)
        except Exception as e:
            messagebox.showwarning("警告", f"注入變數 JSON 格式錯誤！\n{e}")
            return

        # 強制注入 asset_dir
        dynamic_vars["asset_dir"] = asset_dir

        self.btn_test.config(state=tk.DISABLED)
        self.lbl_result.config(text="執行中... (請勿操作滑鼠)", foreground="orange")
        self.update()
        
        # 開啟獨立執行緒進行測試，避免卡死 GUI
        threading.Thread(
            target=self._run_single_state, 
            args=(wf_path, engine_path, dynamic_vars, selected_state), 
            daemon=True
        ).start()

    def _run_single_state(self, wf_path, engine_path, dynamic_vars, target_state_name):
        engine_class_name = self.minion_config.get("client_config", {}).get("engine_class", "AgentEngine")
        
        try:
            # 1. 動態載入 Engine
            spec = importlib.util.spec_from_file_location("dynamic_engine", engine_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            EngineClass = getattr(module, engine_class_name)
            
            # 2. 初始化引擎 (包含全域變數替換)
            sig = inspect.signature(EngineClass.__init__)
            if "dynamic_vars" in sig.parameters:
                engine = EngineClass(wf_path, dynamic_vars=dynamic_vars)
            else:
                engine = EngineClass(wf_path)
                
            # 3. 抓取特定的 State 定義
            state_def = engine.states.get(target_state_name)
            if not state_def:
                raise ValueError(f"在引擎中找不到狀態: {target_state_name}")
                
            # 4. 直接呼叫底層的 _process 進行單步執行 (偵測 -> 點擊 -> 驗證 -> 回傳下個狀態)
            next_state = engine._process(state_def)
            
            self.after(0, self._show_result, next_state, "green")

        except Exception as e:
            self.after(0, self._show_result, f"錯誤: {e}", "red")

    def _show_result(self, result_text, color):
        self.lbl_result.config(text=result_text, foreground=color)
        self.btn_test.config(state=tk.NORMAL)
        
        # 讓視窗強迫置頂提醒使用者任務結束
        self.attributes('-topmost', True)
        self.after(1000, lambda: self.attributes('-topmost', False))

if __name__ == "__main__":
    app = StateTestingTool()
    app.mainloop()