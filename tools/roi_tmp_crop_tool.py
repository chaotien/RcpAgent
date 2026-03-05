import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import cv2
import numpy as np
from PIL import Image, ImageTk
import os

# [NEW] 嘗試匯入 ruamel.yaml 以支援無損 YAML 讀寫 (保留註解與排版)
try:
    from ruamel.yaml import YAML
    from ruamel.yaml.comments import CommentedSeq
    HAS_RUAMEL = True
except ImportError:
    import yaml
    HAS_RUAMEL = False

class Task:
    def __init__(self, task_type, name, desc=""):
        self.task_type = task_type  # 'ROI' or 'IMAGE'
        self.name = name
        self.desc = desc

class ROITask(Task):
    def __init__(self, name, current_val):
        super().__init__('ROI', name, f"Setup ROI: {name}")
        self.current_val = current_val

class ImageTask(Task):
    def __init__(self, state_name, phase, path):
        super().__init__('IMAGE', os.path.basename(path), f"State: {state_name} | Phase: {phase}")
        self.state_name = state_name
        self.phase = phase
        self.path = path

class SOPSetupTool(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("🤖 RcpAgent SOP Setup Tool")
        self.geometry("1200x800")
        
        # 狀態變數
        self.yaml_path = None
        self.yaml_data = {}
        self.assets_dir = None
        
        self.tasks = []
        self.current_task_idx = -1
        
        self.original_screenshot = None  # PIL Image
        self.display_image = None        # ImageTk
        self.scale_factor = 1.0
        
        # 畫布狀態
        self.start_x = None
        self.start_y = None
        self.current_rect = None
        self.roi_coords = None # (x, y, w, h) in original image scale
        
        # [NEW] 初始化 ruamel.yaml 解析器
        if HAS_RUAMEL:
            self.yaml_parser = YAML()
            self.yaml_parser.preserve_quotes = True
            self.yaml_parser.indent(mapping=2, sequence=4, offset=2)
            self.yaml_parser.width = 4096 # 防止超長字串被自動換行
            
        self._init_ui()
        self.after(500, self._check_dependencies) # 啟動後檢查套件

    def _check_dependencies(self):
        if not HAS_RUAMEL:
            messagebox.showwarning(
                "建議安裝套件", 
                "未偵測到 'ruamel.yaml' 套件！\n\n"
                "目前將使用標準 'pyyaml'，這會導致存檔時 YAML 的「註解」與「排版」跑掉。\n\n"
                "強烈建議在終端機執行：\n"
                "pip install ruamel.yaml\n\n"
                "安裝後重新啟動，即可完美保留原本的 YAML 格式！"
            )

    def _init_ui(self):
        # --- Top Control Panel ---
        top_frame = tk.Frame(self, pady=10, padx=10)
        top_frame.pack(fill=tk.X)
        
        tk.Button(top_frame, text="📂 Load .yaml", command=self.load_yaml, width=15).grid(row=0, column=0, padx=5)
        self.lbl_yaml = tk.Label(top_frame, text="No YAML loaded", fg="gray")
        self.lbl_yaml.grid(row=0, column=1, sticky=tk.W)
        
        tk.Button(top_frame, text="📁 Select Assets Dir", command=self.select_assets, width=15).grid(row=1, column=0, padx=5, pady=5)
        self.lbl_assets = tk.Label(top_frame, text="No Assets Dir selected", fg="gray")
        self.lbl_assets.grid(row=1, column=1, sticky=tk.W)
        
        tk.Button(top_frame, text="💾 Save .yaml", command=self.save_yaml, bg="#4CAF50", fg="white", width=15).grid(row=0, column=2, rowspan=2, padx=20)

        # --- Task Navigation Panel ---
        nav_frame = tk.Frame(self, bd=2, relief=tk.GROOVE, pady=5, padx=10)
        nav_frame.pack(fill=tk.X, padx=10)
        
        tk.Button(nav_frame, text="◀ Previous", command=self.prev_task, width=10).pack(side=tk.LEFT)
        self.lbl_task_info = tk.Label(nav_frame, text="Please load YAML first.", font=("Arial", 12, "bold"))
        self.lbl_task_info.pack(side=tk.LEFT, expand=True)
        tk.Button(nav_frame, text="Next ▶", command=self.next_task, width=10).pack(side=tk.RIGHT)

        # --- Action Panel ---
        action_frame = tk.Frame(self, pady=5, padx=10)
        action_frame.pack(fill=tk.X)
        
        tk.Button(action_frame, text="🖼️ Load Screenshot for BBox", command=self.load_screenshot, bg="#2196F3", fg="white").pack(side=tk.LEFT, padx=5)
        tk.Button(action_frame, text="✂️ Crop & Save / Update ROI", command=self.process_bbox, bg="#FF9800", fg="white").pack(side=tk.LEFT, padx=5)
        tk.Button(action_frame, text="🧪 Test Detection Match", command=self.test_match, bg="#9C27B0", fg="white").pack(side=tk.LEFT, padx=5)
        
        self.lbl_existing_img = tk.Label(action_frame, text="")
        self.lbl_existing_img.pack(side=tk.RIGHT, padx=10)

        # --- Canvas Area ---
        canvas_frame = tk.Frame(self, bg="gray")
        canvas_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        self.canvas = tk.Canvas(canvas_frame, bg="black", cursor="cross")
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        self.canvas.bind("<ButtonPress-1>", self.on_mouse_down)
        self.canvas.bind("<B1-Motion>", self.on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_mouse_up)
        
        # Window Resize Event
        self.bind("<Configure>", self.on_resize)

    # ==========================================
    # YAML & Task Management
    # ==========================================
    def load_yaml(self):
        filepath = filedialog.askopenfilename(filetypes=[("YAML files", "*.yaml"), ("All files", "*.*")])
        if not filepath: return
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                if HAS_RUAMEL:
                    self.yaml_data = self.yaml_parser.load(f)
                else:
                    self.yaml_data = yaml.safe_load(f)
                    
            self.yaml_path = filepath
            self.lbl_yaml.config(text=filepath, fg="black")
            
            # Default assets dir
            potential_assets = os.path.join(os.path.dirname(filepath), "assets")
            if os.path.exists(potential_assets):
                self.assets_dir = potential_assets
                self.lbl_assets.config(text=potential_assets, fg="black")
                
            self.build_task_list()
            messagebox.showinfo("Success", f"Loaded YAML. Found {len(self.tasks)} tasks.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load YAML:\n{e}")

    def select_assets(self):
        d = filedialog.askdirectory()
        if d:
            self.assets_dir = d
            self.lbl_assets.config(text=d, fg="black")
            self.update_ui()

    def build_task_list(self):
        self.tasks = []
        
        # 1. Parse ROIs
        roi_map = self.yaml_data.get("roi_map", {})
        for name, val in roi_map.items():
            self.tasks.append(ROITask(name, val))
            
        # 2. Parse States for Images
        states = self.yaml_data.get("states", [])
        for state in states:
            s_name = state.get("name", "Unknown")
            
            def extract_images(features, phase):
                for f in features:
                    if f.get("type") == "image" and "path" in f:
                        clean_path = os.path.basename(f["path"])
                        self.tasks.append(ImageTask(s_name, phase, clean_path))
            
            det_features = state.get("detection", {}).get("target_features", [])
            extract_images(det_features, "Detection")
            
            ver_features = state.get("verification", {}).get("target_features", [])
            extract_images(ver_features, "Verification")
            
            err_branches = state.get("transitions", {}).get("on_fail", {}).get("error_branches", [])
            for br in err_branches:
                cond = br.get("condition", {})
                if cond.get("type") == "image" and "path" in cond:
                    clean_path = os.path.basename(cond["path"])
                    self.tasks.append(ImageTask(s_name, "Error Branch", clean_path))
                    
        if self.tasks:
            self.current_task_idx = 0
            self.update_ui()

    def prev_task(self):
        if self.current_task_idx > 0:
            self.current_task_idx -= 1
            self.update_ui()

    def next_task(self):
        if self.current_task_idx < len(self.tasks) - 1:
            self.current_task_idx += 1
            self.update_ui()

    def update_ui(self):
        if self.current_task_idx < 0 or self.current_task_idx >= len(self.tasks):
            return
            
        task = self.tasks[self.current_task_idx]
        progress = f"({self.current_task_idx + 1}/{len(self.tasks)})"
        self.lbl_task_info.config(text=f"{progress} {task.desc} | Target: {task.name}")
        
        # Clear existing image label
        self.lbl_existing_img.config(image='', text="")
        
        if task.task_type == 'IMAGE' and self.assets_dir:
            full_path = os.path.join(self.assets_dir, task.name)
            if os.path.exists(full_path):
                try:
                    img = Image.open(full_path)
                    img.thumbnail((100, 100)) # Show small thumbnail
                    photo = ImageTk.PhotoImage(img)
                    self.lbl_existing_img.config(image=photo, text="Existing File:")
                    self.lbl_existing_img.image = photo # Keep reference
                except:
                    self.lbl_existing_img.config(text="File exists but cannot display")
            else:
                self.lbl_existing_img.config(text="File not found in assets")
                
        # Reset canvas BBox
        self.clear_bbox()

    # ==========================================
    # Canvas & Screenshot Operations
    # ==========================================
    def load_screenshot(self):
        filepath = filedialog.askopenfilename(title="Select Screenshot", filetypes=[("Image files", "*.png *.jpg *.jpeg")])
        if not filepath: return
        try:
            self.original_screenshot = Image.open(filepath)
            self.render_canvas()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load image: {e}")

    def on_resize(self, event):
        if str(event.widget) == str(self.canvas):
            if self.original_screenshot:
                self.after(100, self.render_canvas)

    def render_canvas(self):
        if not self.original_screenshot: return
        
        c_width = self.canvas.winfo_width()
        c_height = self.canvas.winfo_height()
        if c_width <= 1 or c_height <= 1: return 

        o_width, o_height = self.original_screenshot.size
        
        scale_w = c_width / o_width
        scale_h = c_height / o_height
        self.scale_factor = min(scale_w, scale_h) * 0.95 
        
        new_w = int(o_width * self.scale_factor)
        new_h = int(o_height * self.scale_factor)
        
        resized_img = self.original_screenshot.resize((new_w, new_h), Image.LANCZOS)
        self.display_image = ImageTk.PhotoImage(resized_img)
        
        self.canvas.delete("all")
        x_offset = (c_width - new_w) // 2
        y_offset = (c_height - new_h) // 2
        
        self.canvas.create_image(x_offset, y_offset, anchor=tk.NW, image=self.display_image, tags="bg_img")
        
        self.img_x_offset = x_offset
        self.img_y_offset = y_offset

    def on_mouse_down(self, event):
        if not self.original_screenshot: return
        self.start_x = event.x
        self.start_y = event.y
        self.clear_bbox()
        self.current_rect = self.canvas.create_rectangle(self.start_x, self.start_y, self.start_x, self.start_y, outline="red", width=2, tags="bbox")

    def on_mouse_drag(self, event):
        if not self.original_screenshot or not self.current_rect: return
        self.canvas.coords(self.current_rect, self.start_x, self.start_y, event.x, event.y)

    def on_mouse_up(self, event):
        if not self.original_screenshot or not self.current_rect: return
        end_x, end_y = event.x, event.y
        
        x1 = (min(self.start_x, end_x) - self.img_x_offset) / self.scale_factor
        y1 = (min(self.start_y, end_y) - self.img_y_offset) / self.scale_factor
        x2 = (max(self.start_x, end_x) - self.img_x_offset) / self.scale_factor
        y2 = (max(self.start_y, end_y) - self.img_y_offset) / self.scale_factor
        
        o_w, o_h = self.original_screenshot.size
        x1, y1 = max(0, min(x1, o_w)), max(0, min(y1, o_h))
        x2, y2 = max(0, min(x2, o_w)), max(0, min(y2, o_h))
        
        w, h = x2 - x1, y2 - y1
        if w > 5 and h > 5:
            self.roi_coords = (int(x1), int(y1), int(w), int(h))
        else:
            self.clear_bbox()

    def clear_bbox(self):
        self.canvas.delete("bbox")
        self.canvas.delete("match_box")
        self.roi_coords = None

    # ==========================================
    # Core Operations
    # ==========================================
    def process_bbox(self):
        if not self.roi_coords:
            messagebox.showwarning("Warning", "Please select a bounding box first!")
            return
            
        task = self.tasks[self.current_task_idx]
        x, y, w, h = self.roi_coords
        
        if task.task_type == 'ROI':
            o_w, o_h = self.original_screenshot.size
            rx = round(x / o_w, 3)
            ry = round(y / o_h, 3)
            rw = round(w / o_w, 3)
            rh = round(h / o_h, 3)
            
            if "roi_map" not in self.yaml_data: 
                self.yaml_data["roi_map"] = {}
                
            # [NEW] 使用 ruamel.yaml 的 CommentedSeq 強制將陣列寫成單行 [x, y, w, h]
            if HAS_RUAMEL:
                seq = CommentedSeq([rx, ry, rw, rh])
                seq.fa.set_flow_style() # Flow Style: 確保在一行內顯示
                self.yaml_data["roi_map"][task.name] = seq
            else:
                self.yaml_data["roi_map"][task.name] = [rx, ry, rw, rh]
            
            messagebox.showinfo("ROI Saved", f"Updated ROI '{task.name}': [{rx}, {ry}, {rw}, {rh}]")
            self.next_task()
            
        elif task.task_type == 'IMAGE':
            if not self.assets_dir:
                messagebox.showerror("Error", "Please select Assets Directory first!")
                return
                
            save_path = os.path.join(self.assets_dir, task.name)
            
            crop_img = self.original_screenshot.crop((x, y, x+w, y+h))
            crop_img.save(save_path)
            
            self._update_yaml_image_path(task, f"assets/{task.name}")
            
            messagebox.showinfo("Image Saved", f"Saved cropped image to:\n{save_path}")
            self.update_ui()
            self.next_task()

    def _update_yaml_image_path(self, task: ImageTask, new_rel_path: str):
        states = self.yaml_data.get("states", [])
        for state in states:
            if state.get("name") == task.state_name:
                if task.phase == "Detection":
                    for f in state.get("detection", {}).get("target_features", []):
                        if f.get("type") == "image" and os.path.basename(f.get("path", "")) == task.name:
                            f["path"] = new_rel_path
                elif task.phase == "Verification":
                    for f in state.get("verification", {}).get("target_features", []):
                        if f.get("type") == "image" and os.path.basename(f.get("path", "")) == task.name:
                            f["path"] = new_rel_path

    def test_match(self):
        if not self.original_screenshot:
            messagebox.showwarning("Warning", "Please load a screenshot to test against.")
            return
            
        task = self.tasks[self.current_task_idx]
        if task.task_type != 'IMAGE':
            messagebox.showwarning("Warning", "Test match is only available for IMAGE tasks.")
            return
            
        if not self.assets_dir: return
        full_path = os.path.join(self.assets_dir, task.name)
        
        if not os.path.exists(full_path):
            messagebox.showerror("Error", f"Target image not found:\n{full_path}")
            return
            
        try:
            screen_cv = cv2.cvtColor(np.array(self.original_screenshot), cv2.COLOR_RGB2BGR)
            template_cv = cv2.imread(full_path)
            
            res = cv2.matchTemplate(screen_cv, template_cv, cv2.TM_CCOEFF_NORMED)
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)
            
            if max_val >= 0.8:
                tw, th = template_cv.shape[1], template_cv.shape[0]
                top_left = max_loc
                
                cx = (top_left[0] * self.scale_factor) + self.img_x_offset
                cy = (top_left[1] * self.scale_factor) + self.img_y_offset
                cw = tw * self.scale_factor
                ch = th * self.scale_factor
                
                self.canvas.delete("match_box")
                self.canvas.create_rectangle(cx, cy, cx+cw, cy+ch, outline="#00FF00", width=4, tags="match_box")
                self.canvas.create_text(cx, cy-10, text=f"Match: {max_val:.2f}", fill="#00FF00", font=("Arial", 12, "bold"), tags="match_box")
                
                messagebox.showinfo("Match Success", f"Found match with confidence: {max_val:.2f}")
            else:
                messagebox.showwarning("Match Failed", f"Could not find a strong match. Max confidence: {max_val:.2f}")
                
        except Exception as e:
            messagebox.showerror("Error", f"Matching failed: {e}")

    def save_yaml(self):
        if not self.yaml_path or not self.yaml_data: return
        
        save_path = filedialog.asksaveasfilename(
            defaultextension=".yaml",
            initialfile=os.path.basename(self.yaml_path),
            filetypes=[("YAML files", "*.yaml")]
        )
        
        if save_path:
            try:
                with open(save_path, 'w', encoding='utf-8') as f:
                    if HAS_RUAMEL:
                        self.yaml_parser.dump(self.yaml_data, f)
                    else:
                        yaml.dump(self.yaml_data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
                messagebox.showinfo("Success", f"Saved YAML to:\n{save_path}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save YAML:\n{e}")

if __name__ == "__main__":
    app = SOPSetupTool()
    app.mainloop()