import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from PIL import Image, ImageTk
import pyautogui
import pyscreeze
import os
import importlib.util
import sys
import json
import inspect

# ==============================================================================
# [智慧路徑解析與工作目錄對齊]
# ==============================================================================
if getattr(sys, 'frozen', False):
    BASE_PATH = os.path.dirname(sys.executable)
    PROJECT_ROOT = os.path.dirname(BASE_PATH)
else:
    BASE_PATH = os.path.dirname(os.path.abspath(__file__))
    PROJECT_ROOT = os.path.dirname(BASE_PATH)

os.chdir(PROJECT_ROOT)

# ==============================================================================
# 1. 環境欺騙模組 (PyAutoGUI Mocker)
# ==============================================================================
class PyAutoGUIMocker:
    def __init__(self, pil_image: Image.Image):
        self.image = pil_image
        self._original_screenshot = pyautogui.screenshot
        self._original_locateOnScreen = pyautogui.locateOnScreen
        self._original_size = pyautogui.size

    def patch(self):
        pyautogui.screenshot = self.mock_screenshot
        pyautogui.locateOnScreen = self.mock_locateOnScreen
        pyautogui.size = self.mock_size

    def unpatch(self):
        pyautogui.screenshot = self._original_screenshot
        pyautogui.locateOnScreen = self._original_locateOnScreen
        pyautogui.size = self._original_size

    def mock_size(self):
        return self.image.size

    def mock_screenshot(self, region=None):
        if region:
            x, y, w, h = [int(v) for v in region]
            return self.image.crop((x, y, x + w, y + h))
        return self.image.copy()

    def mock_locateOnScreen(self, image, **kwargs):
        region = kwargs.get('region', None)
        confidence = kwargs.get('confidence', 0.999)
        grayscale = kwargs.get('grayscale', False)
        
        haystack = self.mock_screenshot(region)
        try:
            res = pyscreeze.locate(image, haystack, confidence=confidence, grayscale=grayscale)
            if res:
                if region:
                    return pyscreeze.Box(res.left + int(region[0]), res.top + int(region[1]), res.width, res.height)
                return res
            return None
        except pyscreeze.ImageNotFoundException:
            if hasattr(pyautogui, 'USE_IMAGE_NOT_FOUND_EXCEPTION') and pyautogui.USE_IMAGE_NOT_FOUND_EXCEPTION:
                raise pyautogui.ImageNotFoundException()
            return None

# ==============================================================================
# 2. 測試工具 GUI
# ==============================================================================
class StateTesterGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("🤖 RcpAgent 狀態機靜態測試工具 (State Tester)")
        self.geometry("1400x950") # 稍微加高以容納新欄位
        
        # 載入預設設定
        import yaml
        self.config_path = os.path.join(PROJECT_ROOT, "client", "minion_config.yaml")
        self.minion_config = self._load_config()
        
        # 狀態變數
        self.engine_class = None
        self.engine_instance = None
        self.mocker = None
        
        self.original_image = None
        self.display_image = None
        self.scale_factor = 1.0
        self.img_x_offset = 0
        self.img_y_offset = 0
        
        self.last_detected_coords = None
        
        self._init_ui()

    def _load_config(self):
        if os.path.exists(self.config_path):
            try:
                import yaml
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    return yaml.safe_load(f)
            except Exception:
                pass
        return {}

    def _init_ui(self):
        # --- Top Config Panel ---
        config_frame = tk.LabelFrame(self, text="1. 環境設定與載入 (Configuration Loader)", pady=5, padx=10)
        config_frame.pack(fill=tk.X, padx=10, pady=5)
        
        client_cfg = self.minion_config.get("client_config", {})
        default_wf = client_cfg.get("base_sop", "workflows/sop_wafer_load_template.yaml")
        default_engine = client_cfg.get("engine_script", "core/auto_gui_engine.py")
        default_class = client_cfg.get("engine_class", "AgentEngine")
        default_asset = client_cfg.get("default_asset_dir", "assets")

        # 第一排：路徑選擇
        row1 = tk.Frame(config_frame)
        row1.pack(fill=tk.X, pady=2)
        
        tk.Label(row1, text="Workflow:").pack(side=tk.LEFT)
        self.entry_wf = tk.Entry(row1, width=30)
        self.entry_wf.insert(0, default_wf)
        self.entry_wf.pack(side=tk.LEFT, padx=5)
        tk.Button(row1, text="...", command=self._browse_wf).pack(side=tk.LEFT)
        
        tk.Label(row1, text="Engine:").pack(side=tk.LEFT, padx=(15, 0))
        self.entry_engine = tk.Entry(row1, width=30)
        self.entry_engine.insert(0, default_engine)
        self.entry_engine.pack(side=tk.LEFT, padx=5)
        tk.Button(row1, text="...", command=self._browse_engine).pack(side=tk.LEFT)
        
        tk.Label(row1, text="Class:").pack(side=tk.LEFT, padx=(15, 0))
        self.entry_class = tk.Entry(row1, width=15)
        self.entry_class.insert(0, default_class)
        self.entry_class.pack(side=tk.LEFT, padx=5)

        # 第二排：Assets 與 變數注入
        row2 = tk.Frame(config_frame)
        row2.pack(fill=tk.X, pady=2)
        
        tk.Label(row2, text="Assets Dir:").pack(side=tk.LEFT)
        self.entry_asset = tk.Entry(row2, width=30)
        self.entry_asset.insert(0, default_asset)
        self.entry_asset.pack(side=tk.LEFT, padx=5)
        tk.Button(row2, text="...", command=self._browse_asset).pack(side=tk.LEFT)
        
        tk.Label(row2, text="注入變數(JSON):").pack(side=tk.LEFT, padx=(15, 0))
        self.entry_vars = tk.Entry(row2, width=40)
        self.entry_vars.insert(0, '{"recipe_name": "test.xml", "slot_offset": [0, 30]}')
        self.entry_vars.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)

        btn_load_engine = tk.Button(config_frame, text="📥 載入設定 (Load)", bg="#4CAF50", fg="white", font=("Arial", 10, "bold"), command=self.load_engine)
        btn_load_engine.pack(side=tk.RIGHT, padx=10, pady=5)

        # --- Main Layout (Sidebar + Canvas) ---
        paned = tk.PanedWindow(self, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # Sidebar
        sidebar = tk.Frame(paned, width=350)
        paned.add(sidebar, minsize=300)
        
        lbl_states = tk.LabelFrame(sidebar, text="2. 選擇測試 State", padx=5, pady=5)
        lbl_states.pack(fill=tk.BOTH, expand=True)
        
        self.listbox_states = tk.Listbox(lbl_states, font=("Consolas", 11), exportselection=False)
        self.listbox_states.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
        scrollbar = tk.Scrollbar(lbl_states, command=self.listbox_states.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.listbox_states.config(yscrollcommand=scrollbar.set)
        
        # Test Controls
        control_frame = tk.LabelFrame(sidebar, text="3. 測試操作 (Test Execution)", padx=5, pady=10)
        control_frame.pack(fill=tk.X, pady=10)
        
        btn_load_img = tk.Button(control_frame, text="🖼️ 載入測試截圖 (Load Image)", bg="#2196F3", fg="white", command=self.load_test_image)
        btn_load_img.pack(fill=tk.X, pady=5)
        
        self.btn_run_detect = tk.Button(control_frame, text="👁️ 執行 Detection (偵測)", bg="#FF9800", fg="white", command=self.run_detection)
        self.btn_run_detect.pack(fill=tk.X, pady=2)
        
        self.btn_run_action = tk.Button(control_frame, text="🎯 執行 Action (動作落點)", bg="#E91E63", fg="white", command=self.run_action)
        self.btn_run_action.pack(fill=tk.X, pady=2)
        
        self.btn_run_verify = tk.Button(control_frame, text="✅ 執行 Verification (驗證)", bg="#9C27B0", fg="white", command=self.run_verification)
        self.btn_run_verify.pack(fill=tk.X, pady=2)
        
        tk.Button(control_frame, text="🧹 清除畫布標記", command=self.clear_drawings).pack(fill=tk.X, pady=10)
        
        # Canvas Area
        canvas_frame = tk.Frame(paned, bg="gray")
        paned.add(canvas_frame)
        
        self.canvas = tk.Canvas(canvas_frame, bg="black", cursor="cross")
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.bind("<Configure>", self.on_resize)

    # ==========================================
    # File Browsing
    # ==========================================
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

    # ==========================================
    # Engine & Data Loading
    # ==========================================
    def load_engine(self):
        engine_path = self.entry_engine.get().strip()
        class_name = self.entry_class.get().strip()
        yaml_path = self.entry_wf.get().strip()
        asset_dir = self.entry_asset.get().strip()
        vars_json_str = self.entry_vars.get().strip()
        
        if not os.path.exists(engine_path) or not os.path.exists(yaml_path):
            messagebox.showerror("錯誤", "找不到 Engine 腳本或 YAML 檔案！請檢查路徑。")
            return
            
        # 解析動態變數
        dynamic_vars = {}
        try:
            if vars_json_str:
                dynamic_vars = json.loads(vars_json_str)
        except Exception as e:
            messagebox.showwarning("警告", f"注入變數 JSON 格式錯誤！\n{e}")
            return
            
        # 強制注入 asset_dir
        dynamic_vars["asset_dir"] = asset_dir

        try:
            # 動態匯入指定的 Engine Class
            module_name = "dynamic_auto_gui_engine"
            spec = importlib.util.spec_from_file_location(module_name, engine_path)
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)
            
            self.engine_class = getattr(module, class_name)
            
            # 檢查 Engine 是否支援 dynamic_vars
            sig = inspect.signature(self.engine_class.__init__)
            if "dynamic_vars" in sig.parameters:
                self.engine_instance = self.engine_class(yaml_path, dynamic_vars=dynamic_vars)
                msg = f"成功載入 Engine ({class_name}) 並注入變數！"
            else:
                self.engine_instance = self.engine_class(yaml_path)
                msg = f"⚠️ 警告: 所選的 Engine 不支援動態變數注入，已退回傳統模式。\n成功載入 Engine ({class_name})！"
            
            # 如果已經有載入圖片，要更新解析度設定
            if self.original_image:
                self.engine_instance.screen.screen_size = self.original_image.size
            
            # 填入 Listbox
            self.listbox_states.delete(0, tk.END)
            for state in self.engine_instance.states_list:
                self.listbox_states.insert(tk.END, state["name"])
                
            messagebox.showinfo("成功", f"{msg}\n共載入 {len(self.engine_instance.states_list)} 個 States。")
            
        except Exception as e:
            messagebox.showerror("載入失敗", f"載入 Engine 或 YAML 時發生錯誤:\n{e}")

    def load_test_image(self):
        filepath = filedialog.askopenfilename(title="選擇測試用截圖", filetypes=[("Image files", "*.png *.jpg *.jpeg")])
        if not filepath: return
        try:
            self.original_image = Image.open(filepath)
            self.mocker = PyAutoGUIMocker(self.original_image)
            
            if self.engine_instance:
                self.engine_instance.screen.screen_size = self.original_image.size
                
            self.clear_drawings()
            self.render_canvas()
        except Exception as e:
            messagebox.showerror("錯誤", f"載入圖片失敗: {e}")

    # ==========================================
    # Canvas Visualization
    # ==========================================
    def on_resize(self, event):
        if str(event.widget) == str(self.canvas) and self.original_image:
            self.after(100, self.render_canvas)

    def render_canvas(self):
        if not self.original_image: return
        
        c_width = self.canvas.winfo_width()
        c_height = self.canvas.winfo_height()
        if c_width <= 1 or c_height <= 1: return 

        o_width, o_height = self.original_image.size
        scale_w = c_width / o_width
        scale_h = c_height / o_height
        self.scale_factor = min(scale_w, scale_h) * 0.95 
        
        new_w = int(o_width * self.scale_factor)
        new_h = int(o_height * self.scale_factor)
        
        resized_img = self.original_image.resize((new_w, new_h), Image.LANCZOS)
        self.display_image = ImageTk.PhotoImage(resized_img)
        
        self.canvas.delete("bg_img")
        self.img_x_offset = (c_width - new_w) // 2
        self.img_y_offset = (c_height - new_h) // 2
        
        self.canvas.create_image(self.img_x_offset, self.img_y_offset, anchor=tk.NW, image=self.display_image, tags="bg_img")
        self.canvas.tag_lower("bg_img")

    def clear_drawings(self):
        self.canvas.delete("overlay")
        self.last_detected_coords = None

    def _to_canvas_coords(self, real_x, real_y):
        cx = int(real_x * self.scale_factor) + self.img_x_offset
        cy = int(real_y * self.scale_factor) + self.img_y_offset
        return cx, cy

    def draw_roi_box(self, roi_tuple, color, dash=(4,4), text="ROI"):
        if not roi_tuple: return
        x, y, w, h = roi_tuple
        cx1, cy1 = self._to_canvas_coords(x, y)
        cx2, cy2 = self._to_canvas_coords(x+w, y+h)
        
        self.canvas.create_rectangle(cx1, cy1, cx2, cy2, outline=color, width=2, dash=dash, tags="overlay")
        self.canvas.create_text(cx1, cy1-10, text=text, fill=color, font=("Arial", 10, "bold"), anchor=tk.SW, tags="overlay")

    def draw_point(self, coords, color, radius=5, text="Point"):
        if not coords: return
        cx, cy = self._to_canvas_coords(coords[0], coords[1])
        
        self.canvas.create_oval(cx-radius, cy-radius, cx+radius, cy+radius, fill=color, outline="white", width=2, tags="overlay")
        self.canvas.create_text(cx+radius+5, cy, text=f"{text}\n({coords[0]}, {coords[1]})", fill=color, font=("Arial", 10, "bold"), anchor=tk.W, tags="overlay")

    def get_selected_state(self):
        selection = self.listbox_states.curselection()
        if not selection:
            messagebox.showwarning("警告", "請先從清單中選擇一個 State！")
            return None
        return self.listbox_states.get(selection[0])

    # ==========================================
    # Test Executions
    # ==========================================
    def run_detection(self):
        state_name = self.get_selected_state()
        if not state_name or not self.engine_instance or not self.mocker: return
        
        state_def = self.engine_instance.states.get(state_name)
        d_cfg = state_def.get("detection", {})
        
        self.clear_drawings()
        
        self.mocker.patch()
        try:
            print(f"\n[Test] Running Detection for '{state_name}'...")
            found, coords, used_roi = self.engine_instance._detect_with_retry(d_cfg, state_name)
        finally:
            self.mocker.unpatch()

        self.draw_roi_box(used_roi, color="#00BFFF", text=f"Detection ROI")
        
        if found:
            self.draw_point(coords, color="#4CAF50", radius=8, text="Detected Center")
            self.last_detected_coords = coords
            print(f"✅ Target found at {coords}")
        else:
            messagebox.showinfo("偵測結果", "未找到目標 (Not Found)。\n可能是圖檔特徵不同或目標不在 ROI 內。")
            print("❌ Target not found.")

    def run_action(self):
        state_name = self.get_selected_state()
        if not state_name or not self.engine_instance: return
        
        state_def = self.engine_instance.states.get(state_name)
        a_cfg = state_def.get("action", {})
        atype = a_cfg.get("type", "wait")
        
        print(f"\n[Test] Action type: {atype}")
        
        if atype in ["click", "input_text"]:
            if not self.last_detected_coords:
                messagebox.showwarning("警告", "請先執行 Detection 並確保成功找到目標，才能計算 Action 落點！")
                return
            
            # 使用 Engine 內部的解析方法來解析 offset
            offset = self.engine_instance.executor._resolve_var(a_cfg.get("offset", [0, 0]))
            
            tx = self.last_detected_coords[0] + offset[0]
            ty = self.last_detected_coords[1] + offset[1]
            
            self.draw_point((tx, ty), color="#E91E63", radius=6, text="Action Point (w/ offset)")
            
            if atype == "input_text":
                text_to_type = self.engine_instance.executor._resolve_var(a_cfg.get('text', ''))
                print(f"⌨️ Simulation: Type text '{text_to_type}' at {tx, ty}")
            else:
                print(f"🖱️ Simulation: Click at {tx, ty}")
                
        elif atype == "click_sequence":
            messagebox.showinfo("提示", "click_sequence 包含多個步驟特徵，此工具目前僅標記動作類型，不執行連續圖形比對。")
        else:
            messagebox.showinfo("提示", f"動作類型為 '{atype}'，不涉及特定座標點擊。")

    def run_verification(self):
        state_name = self.get_selected_state()
        if not state_name or not self.engine_instance or not self.mocker: return
        
        state_def = self.engine_instance.states.get(state_name)
        v_cfg = state_def.get("verification", {})
        
        if not v_cfg:
            messagebox.showinfo("提示", f"State '{state_name}' 沒有定義 verification 區塊。")
            return
            
        self.mocker.patch()
        try:
            print(f"\n[Test] Running Verification for '{state_name}'...")
            
            roi_key = v_cfg.get("roi")
            base_roi = self.engine_instance.screen.get_roi_rect(roi_key)
            check_roi = self.engine_instance._resolve_anchor(v_cfg.get("anchor"), base_roi)
            
            self.draw_roi_box(check_roi, color="#FF9800", dash=(2,2), text="Verification ROI")
            
            target_features = v_cfg.get("target_features", [])
            found_any = False
            found_coords = None
            
            for feat in target_features:
                found, coords = self.engine_instance.vision.detect(feat, roi=check_roi)
                if found:
                    found_any = True
                    found_coords = coords
                    break
                    
        finally:
            self.mocker.unpatch()

        v_type = v_cfg.get("type", "appear")
        if v_type == "appear":
            if found_any:
                self.draw_point(found_coords, color="#9C27B0", radius=8, text="Verify (Appear) OK")
                print(f"✅ Verification Passed: Target Appeared at {found_coords}")
            else:
                messagebox.showwarning("驗證失敗", "Verification type: 'appear' 但未找到目標！")
        elif v_type == "disappear":
            if not found_any:
                print(f"✅ Verification Passed: Target Disappeared")
                messagebox.showinfo("驗證成功", "目標確實已消失 (Disappeared)！")
            else:
                self.draw_point(found_coords, color="red", radius=8, text="Verify Failed (Still Here)")
                messagebox.showerror("驗證失敗", "Verification type: 'disappear' 但目標依然存在！")

if __name__ == "__main__":
    app = StateTesterGUI()
    app.mainloop()