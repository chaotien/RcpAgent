import time
import yaml
import logging
import pyautogui
import cv2
import numpy as np
import os
import sys
import ctypes
from PIL import Image
from typing import Dict, List, Tuple, Optional, Any
from collections import defaultdict

if not os.path.exists('logs'): os.makedirs('logs')
log_filename = f"logs/agent_run_{time.strftime('%Y%m%d_%H%M%S')}.log"

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)-8s | %(message)s',
    handlers=[logging.StreamHandler(), logging.FileHandler(log_filename, encoding='utf-8')])
logger = logging.getLogger("AgentEngine")

class VisionSystem:
    def __init__(self, confidence_threshold=0.8, enable_ocr=False):
        self.confidence_threshold = confidence_threshold
        self.MOCK_MODE = False 
        self.reader = None
        if enable_ocr: self._init_easyocr()
        self.is_calibrated = False
        self.scale_factor = 1.0
        self.calibration_scales = [1.0, 1.25, 1.5, 1.75, 2.0, 0.8, 0.75, 0.5]

    def _init_easyocr(self):
        try:
            import easyocr 
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            model_dir = os.path.join(base_dir, "models", "easyocr")
            os.makedirs(model_dir, exist_ok=True)
            self.reader = easyocr.Reader(['en'], gpu=False, model_storage_directory=model_dir, download_enabled=True)
        except Exception as e:
            logger.warning(f"⚠️ EasyOCR init failed: {e}")
            self.reader = None

    def detect(self, feature: Dict, roi: Optional[Tuple[int, int, int, int]] = None) -> Tuple[bool, Optional[Tuple[int, int]]]:
        f_type = feature.get("type")
        if self.MOCK_MODE: return True, (100, 100)

        if f_type == "image":
            path = feature.get("path")
            conf = feature.get("confidence", self.confidence_threshold)
            try:
                if not os.path.exists(path): return False, None
                original_img = Image.open(path)
                scales_to_try = [self.scale_factor] if self.is_calibrated else self.calibration_scales
                
                for scale in scales_to_try:
                    new_w, new_h = int(original_img.width * scale), int(original_img.height * scale)
                    if new_w == 0 or new_h == 0: continue
                    resized_img = original_img.resize((new_w, new_h), Image.LANCZOS)
                    try:
                        box = pyautogui.locateOnScreen(resized_img, region=roi, confidence=conf, grayscale=True)
                        if box:
                            center = pyautogui.center(box)
                            if not self.is_calibrated:
                                self.is_calibrated = True; self.scale_factor = scale
                            return True, (center.x, center.y)
                    except pyautogui.ImageNotFoundException: pass
            except Exception: pass
            return False, None
            
        elif f_type == "ocr":
            if not self.reader: return False, None
            target_text = feature.get("text")
            try:
                screenshot = pyautogui.screenshot(region=roi)
                results = self.reader.readtext(np.array(screenshot))
                for (bbox, text, prob) in results:
                    if target_text.lower() in text.lower():
                        cx = int((bbox[0][0] + bbox[2][0]) / 2)
                        cy = int((bbox[0][1] + bbox[2][1]) / 2)
                        return True, ((roi[0] + cx) if roi else cx, (roi[1] + cy) if roi else cy)
            except Exception: pass
        return False, None

class ScreenManager:
    def __init__(self, custom_rois: Optional[Dict] = None):
        w, h = pyautogui.size()
        self.screen_size = (w, h)
        self.mapping = {k: tuple(v) for k, v in (custom_rois or {}).items() if len(v) == 4}

    def get_roi_rect(self, roi_config: Any) -> Optional[Tuple[int, int, int, int]]:
        w, h = self.screen_size
        if isinstance(roi_config, list) and len(roi_config) == 4:
            return (int(roi_config[0]*w), int(roi_config[1]*h), int(roi_config[2]*w), int(roi_config[3]*h))
        if roi_config in self.mapping:
            pct = self.mapping[roi_config]
            return (int(pct[0]*w), int(pct[1]*h), int(pct[2]*w), int(pct[3]*h))
        return None

class ActionExecutor:
    # [NEW] 接收 dynamic_vars 變數字典
    def __init__(self, global_config, vision, screen, dynamic_vars=None):
        self.delay = global_config.get("action_post_delay", 0.5)
        self.vision = vision
        self.screen = screen
        self.dynamic_vars = dynamic_vars or {}

    # [NEW] 變數解析器
    def _resolve_var(self, val):
        """將設定中的 $變數 替換成實際的值 (支援物件替換與字串內插)"""
        if isinstance(val, str):
            # 1. 完整替換 (用來替換整個 Array，例如 $slot_offset -> [0, 428])
            if val.startswith("$") and val[1:] in self.dynamic_vars:
                return self.dynamic_vars[val[1:]]
            # 2. 字串內插 (用來替換部分文字，例如 recipe_$recipe_name -> recipe_abc)
            if "$" in val:
                res = val
                for k, v in self.dynamic_vars.items():
                    if isinstance(v, str):
                        res = res.replace(f"${k}", v)
                return res
        return val

    def _move_away(self):
        pyautogui.moveTo(10, 10) 

    def _execute_click_strategy(self, x, y, strategy):
        if strategy == "slow":
            pyautogui.mouseDown(x, y); time.sleep(0.15); pyautogui.mouseUp(x, y)
        elif strategy == "ctypes":
            pyautogui.moveTo(x, y); time.sleep(0.1)
            ctypes.windll.user32.mouse_event(0x0002, 0, 0, 0, 0); time.sleep(0.1)
            ctypes.windll.user32.mouse_event(0x0004, 0, 0, 0, 0)
        else:
            pyautogui.click(x, y)

    def execute(self, config: Dict, coords: Tuple[int, int], roi=None):
        atype = config.get("type", "wait")
        should_move_away = config.get("move_away", True)
        strategy = config.get("click_strategy", "standard")
        
        logger.info(f"   🎬 Executing Action: {atype}")
        
        if atype == "wait":
            time.sleep(config.get("duration", 1.0))
            
        elif atype == "click":
            # 透過 _resolve_var 解析 offset
            offset = self._resolve_var(config.get("offset", [0, 0]))
            tx, ty = coords[0] + offset[0], coords[1] + offset[1]
            self._execute_click_strategy(tx, ty, strategy)
            if should_move_away: self._move_away()
                
        elif atype == "input_text":
            # 透過 _resolve_var 解析文字與 offset
            text = self._resolve_var(config.get("text", ""))
            offset = self._resolve_var(config.get("offset", [0, 0]))
            submit = config.get("submit_key", None)
            
            if coords: 
                fx, fy = coords[0] + offset[0], coords[1] + offset[1]
                self._execute_click_strategy(fx, fy, strategy)
                time.sleep(0.2)
                if config.get("clear_first", False):
                    pyautogui.hotkey('ctrl', 'a'); time.sleep(0.1)
                    pyautogui.press('delete'); time.sleep(0.1)
            
            pyautogui.write(text)
            if submit and submit.lower() != "none": pyautogui.press(submit)
            if should_move_away: self._move_away()

class AgentEngine:
    # [NEW] 建構子現在多吃一個 dynamic_vars
    def __init__(self, config_path: str, dynamic_vars: dict = None):
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)
        
        self.global_config = self.config.get("global_config", {})
        self.states_list = self.config.get("states", [])
        self.states = {s["name"]: s for s in self.states_list}
        self.interrupt_handlers = self.config.get("interrupt_handlers", [])
        self.interrupt_triggers = defaultdict(int)
        
        # 保存動態變數
        self.dynamic_vars = dynamic_vars or {}
        
        enable_ocr = self.global_config.get("enable_ocr", False)
        self.vision = VisionSystem(enable_ocr=enable_ocr)
        self.screen = ScreenManager(self.config.get("roi_map", {}))
        
        # 傳遞給 Executor
        self.executor = ActionExecutor(self.global_config, self.vision, self.screen, self.dynamic_vars)
        
        self.loops = defaultdict(int)
        self.retries = defaultdict(int)

    # ... 以下執行邏輯保持不變 ...
    def _save_debug(self, name, roi, return_path=False):
        try:
            fname = f"logs/debug_{time.strftime('%H%M%S')}_{name}.png"
            img = cv2.cvtColor(np.array(pyautogui.screenshot()), cv2.COLOR_RGB2BGR)
            if roi: cv2.rectangle(img, (roi[0], roi[1]), (roi[0]+roi[2], roi[1]+roi[3]), (0,0,255), 2)
            cv2.imwrite(fname, img)
            if return_path: return fname
        except: return None

    def _resolve_anchor(self, cfg, base_roi):
        if not cfg: return base_roi
        found, coords = self.vision.detect(cfg["feature"], roi=base_roi)
        if found and coords:
            ax, ay, aw, ah = cfg["search_area"]
            return (coords[0] + ax, coords[1] + ay, aw, ah)
        return base_roi

    def run(self, start_state: Optional[str] = None) -> dict:
        if start_state is None: start_state = self.states_list[0]["name"]
        curr = start_state
        try:
            while curr not in ["end_task", "abort_task", "report_transfer_timeout"]:
                logger.info(f"\n📍 Entering State: [{curr}]")
                state_def = self.states.get(curr)
                if not state_def: break
                self.loops[curr] += 1
                if self.loops[curr] > self.global_config.get("max_state_loops", 5): break
                curr = self._process(state_def)
            
            success = (curr == "end_task")
            return {"status": "success" if success else "failed", "final_state": curr}
        except Exception as e:
            logger.exception(f"⛔ Crash: {e}")
            return {"status": "error", "final_state": curr}

    def _detect_with_retry(self, detect_cfg: Dict, state_name: str) -> Tuple[bool, Any, Any]:
        base_roi = self.screen.get_roi_rect(detect_cfg.get("roi"))
        detection_roi = self._resolve_anchor(detect_cfg.get("anchor"), base_roi)
        if detect_cfg.get("method") == "dummy": return True, None, detection_roi

        for feature in detect_cfg.get("target_features", []):
            found, coords = self.vision.detect(feature, roi=detection_roi)
            if found: return True, coords, detection_roi
        
        self._save_debug(state_name + "_detect_fail", detection_roi)
        return False, None, detection_roi

    def _process(self, state):
        found, coords, used_roi = self._detect_with_retry(state.get("detection", {}), state['name'])
        if not found: return self._handle_fail(state)

        if "action" in state:
            self.executor.execute(state["action"], coords or (0,0), roi=used_roi)

        if "verification" in state:
            if not self._verify(state["verification"], state['name']):
                return self._handle_fail(state)

        self.retries[state['name']] = 0 
        return state["transitions"]["on_success"]

    def _verify(self, v_cfg, name):
        check_roi = self._resolve_anchor(v_cfg.get("anchor"), self.screen.get_roi_rect(v_cfg.get("roi")))
        timeout = v_cfg.get("timeout", 5.0)
        v_type = v_cfg.get("type", "appear")
        
        start = time.time()
        while time.time() - start < timeout:
            found_any = any(self.vision.detect(f, roi=check_roi)[0] for f in v_cfg.get("target_features", []))
            if (v_type == "appear" and found_any) or (v_type == "disappear" and not found_any): return True
            time.sleep(0.5)
            
        self._save_debug(name+"_verify_fail", check_roi)
        return False

    def _handle_fail(self, state):
        name = state['name']
        fail = state["transitions"]["on_fail"]
        for br in fail.get("error_branches", []):
            roi = self.screen.get_roi_rect(br["condition"].get("roi"))
            if self.vision.detect(br["condition"], roi=roi)[0]:
                return br['next_state']

        if self.retries[name] < fail.get("retry", 0):
            self.retries[name] += 1
            return name
        return fail.get("fallback", "abort_task")