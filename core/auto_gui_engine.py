import time
import yaml
import logging
import pyautogui
import cv2
import numpy as np
import os
import sys
from PIL import Image
from typing import Dict, List, Tuple, Optional, Any
from collections import defaultdict

# ==============================================================================
# Logging Setup
# ==============================================================================
if not os.path.exists('logs'):
    os.makedirs('logs')

log_filename = f"logs/agent_run_{time.strftime('%Y%m%d_%H%M%S')}.log"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(log_filename, encoding='utf-8')
    ]
)
logger = logging.getLogger("AgentEngine")
logger.info(f"🚀 Engine started. Logs: {log_filename}")

# ==============================================================================
# 1. Vision System (動態 OCR 開關與自動下載機制)
# ==============================================================================
class VisionSystem:
    def __init__(self, confidence_threshold=0.8, enable_ocr=False):
        self.confidence_threshold = confidence_threshold
        self.MOCK_MODE = False 
        self.reader = None
        
        if enable_ocr:
            self._init_easyocr()
        else:
            logger.info("ℹ️ OCR engine disabled by default. (Saves init time)")
            
        self.is_calibrated = False
        self.scale_factor = 1.0
        self.calibration_scales = [1.0, 1.25, 1.5, 1.75, 2.0, 0.8, 0.75, 0.5]

    def _init_easyocr(self):
        try:
            import easyocr 
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            model_dir = os.path.join(base_dir, "models", "easyocr")
            if not os.path.exists(model_dir):
                os.makedirs(model_dir)
                
            logger.info(f"⏳ Initializing OCR engine. Models directory: {model_dir}")
            logger.info("   (If models are missing, it will attempt to download them automatically...)")
            
            # [MODIFIED] download_enabled=True
            # 邏輯: 若本地已存在，直接離線載入; 若不存在，自動嘗試連網下載。
            self.reader = easyocr.Reader(
                ['en'], 
                gpu=False, 
                model_storage_directory=model_dir, 
                download_enabled=True 
            )
            logger.info("✅ OCR engine initialized successfully.")
        except Exception as e:
            # 捕捉網路未連線或下載失敗的情況，確保主程式不會崩潰
            logger.warning(f"⚠️ EasyOCR init failed (Network Error or Missing Model): {e}")
            logger.warning("   -> OCR features will be disabled for this run.")
            self.reader = None

    def detect(self, feature: Dict, roi: Optional[Tuple[int, int, int, int]] = None) -> Tuple[bool, Optional[Tuple[int, int]]]:
        f_type = feature.get("type")
        target_info = feature.get("text") or feature.get("path") or "unknown"
        
        use_edge_filter = feature.get("edge_filter", False)
        filter_msg = " [Edge Filter Enabled]" if use_edge_filter else ""
        
        logger.info(f"   👁️ Scanning [{f_type}]: '{target_info}' in ROI: {roi}{filter_msg}")

        if self.MOCK_MODE: return True, (100, 100)

        # 1. Image
        if f_type == "image":
            path = feature.get("path")
            conf = feature.get("confidence", self.confidence_threshold)
            try:
                if not os.path.exists(path):
                    logger.error(f"      ❌ File not found: {path}")
                    return False, None
                
                original_img = Image.open(path)
                scales_to_try = [self.scale_factor] if self.is_calibrated else self.calibration_scales
                
                screen_edges = None
                if use_edge_filter:
                    screen_img = pyautogui.screenshot(region=roi)
                    screen_gray = cv2.cvtColor(np.array(screen_img), cv2.COLOR_RGB2GRAY)
                    screen_edges = cv2.Canny(screen_gray, 50, 150)
                
                for scale in scales_to_try:
                    new_w = int(original_img.width * scale)
                    new_h = int(original_img.height * scale)
                    if new_w == 0 or new_h == 0: continue
                        
                    resized_img = original_img.resize((new_w, new_h), Image.LANCZOS)
                    
                    try:
                        if use_edge_filter:
                            template_gray = cv2.cvtColor(np.array(resized_img), cv2.COLOR_RGB2GRAY)
                            template_edges = cv2.Canny(template_gray, 50, 150)
                            if template_edges.shape[0] > screen_edges.shape[0] or template_edges.shape[1] > screen_edges.shape[1]:
                                continue
                                
                            res = cv2.matchTemplate(screen_edges, template_edges, cv2.TM_CCOEFF_NORMED)
                            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)
                            
                            if max_val >= conf:
                                center_x = max_loc[0] + (new_w // 2)
                                center_y = max_loc[1] + (new_h // 2)
                                if roi:
                                    center_x += roi[0]
                                    center_y += roi[1]
                                box = True
                            else:
                                box = False
                        else:
                            box = pyautogui.locateOnScreen(resized_img, region=roi, confidence=conf, grayscale=True)
                            if box:
                                center = pyautogui.center(box)
                                center_x, center_y = center.x, center.y
                                
                        if box:
                            if not self.is_calibrated:
                                self.is_calibrated = True
                                self.scale_factor = scale
                                logger.info(f"\n      🎯 [Calibration] UI Scale Factor locked at: {scale}x\n")
                            logger.info(f"      ✅ Found Image at ({center_x}, {center_y}) (Scale: {scale}x)")
                            return True, (center_x, center_y)
                            
                    except pyautogui.ImageNotFoundException:
                        pass
                        
                logger.info("      ❌ Image Not Found")
                return False, None
                
            except Exception as e:
                logger.warning(f"      ⚠️ Vision Error: {e}")

        # 2. OCR
        elif f_type == "ocr":
            if not self.reader: 
                logger.warning("      ⚠️ Cannot detect OCR: OCR engine is disabled or failed to initialize.")
                return False, None
            target_text = feature.get("text")
            try:
                screenshot = pyautogui.screenshot(region=roi)
                results = self.reader.readtext(np.array(screenshot))
                for (bbox, text, prob) in results:
                    if target_text.lower() in text.lower():
                        (tl, tr, br, bl) = bbox
                        cx = int((tl[0] + br[0]) / 2)
                        cy = int((tl[1] + br[1]) / 2)
                        global_x = (roi[0] + cx) if roi else cx
                        global_y = (roi[1] + cy) if roi else cy
                        logger.info(f"      ✅ Found OCR '{text}' at ({global_x}, {global_y})")
                        return True, (global_x, global_y)
            except Exception as e:
                logger.error(f"      ⚠️ OCR Error: {e}")

        logger.info("      ❌ Not Found")
        return False, None

# ==============================================================================
# 2. Screen Manager
# ==============================================================================
class ScreenManager:
    def __init__(self, custom_rois: Optional[Dict] = None):
        w, h = pyautogui.size()
        self.screen_size = (w, h)
        logger.info(f"🖥️ Target Screen Resolution: {w}x{h}")
        self.mapping = {}
        if custom_rois:
            for key, val in custom_rois.items():
                if isinstance(val, list) and len(val) == 4:
                    self.mapping[key] = tuple(val)

    def get_roi_rect(self, roi_config: Any) -> Optional[Tuple[int, int, int, int]]:
        w, h = self.screen_size
        if isinstance(roi_config, list) and len(roi_config) == 4:
            return (int(roi_config[0]*w), int(roi_config[1]*h), int(roi_config[2]*w), int(roi_config[3]*h))
        if roi_config in self.mapping:
            pct = self.mapping[roi_config]
            return (int(pct[0]*w), int(pct[1]*h), int(pct[2]*w), int(pct[3]*h))
        return None

# ==============================================================================
# 3. Action Executor
# ==============================================================================
class ActionExecutor:
    def __init__(self, global_config, vision, screen):
        self.delay = global_config.get("action_post_delay", 0.5)
        self.vision = vision
        self.screen = screen

    def _move_away(self):
        pyautogui.moveTo(10, 10) 

    def execute(self, config: Dict, coords: Tuple[int, int], roi=None):
        atype = config.get("type", "wait")
        logger.info(f"   🎬 Executing Action: {atype}")
        
        if atype == "wait":
            time.sleep(config.get("duration", 1.0))
        elif atype == "click":
            offset = config.get("offset", [0, 0])
            tx, ty = coords[0] + offset[0], coords[1] + offset[1]
            pyautogui.click(tx, ty)
            self._move_away()
        elif atype == "input_text":
            text = config.get("text", "")
            offset = config.get("offset", [0, 0])
            submit = config.get("submit_key", None)
            clear_first = config.get("clear_first", False)
            if coords: 
                fx, fy = coords[0] + offset[0], coords[1] + offset[1]
                pyautogui.click(fx, fy)
                time.sleep(0.2)
                if clear_first:
                    pyautogui.hotkey('ctrl', 'a')
                    time.sleep(0.1)
                    pyautogui.press('delete')
                    time.sleep(0.1)
            pyautogui.write(text)
            if submit and submit.lower() != "none":
                pyautogui.press(submit)
            self._move_away()
        elif atype == "click_sequence":
            base = coords
            for step in config.get("sequence", []):
                txt, img = step.get("text"), step.get("image")
                off = step.get("offset", [0, 0])
                found, step_coords = False, None
                if txt: found, step_coords = self.vision.detect({"type": "ocr", "text": txt}, roi=roi)
                elif img: found, step_coords = self.vision.detect({"type": "image", "path": img}, roi=roi)
                
                target = step_coords if found else base
                if target:
                    tx, ty = target[0] + off[0], target[1] + off[1]
                    pyautogui.click(tx, ty)
                    base = target 
                time.sleep(step.get("delay", 0.5))
            self._move_away()
        time.sleep(self.delay)

# ==============================================================================
# 4. Main Engine
# ==============================================================================
class AgentEngine:
    def __init__(self, config_path: str):
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)
        
        self.global_config = self.config.get("global_config", {})
        self.states_list = self.config.get("states", [])
        self.states = {s["name"]: s for s in self.states_list}
        self.interrupt_handlers = self.config.get("interrupt_handlers", [])
        self.interrupt_triggers = defaultdict(int)
        
        enable_ocr = self.global_config.get("enable_ocr", False)
        self.vision = VisionSystem(enable_ocr=enable_ocr)
        self.screen = ScreenManager(self.config.get("roi_map", {}))
        self.executor = ActionExecutor(self.global_config, self.vision, self.screen)
        
        self.loops = defaultdict(int)
        self.retries = defaultdict(int)

    def _save_debug(self, name, roi, return_path=False):
        try:
            fname = f"logs/debug_{time.strftime('%H%M%S')}_{name}.png"
            img = cv2.cvtColor(np.array(pyautogui.screenshot()), cv2.COLOR_RGB2BGR)
            if roi: cv2.rectangle(img, (roi[0], roi[1]), (roi[0]+roi[2], roi[1]+roi[3]), (0,0,255), 2)
            cv2.imwrite(fname, img)
            logger.warning(f"📸 Debug saved: {fname}")
            if return_path: return fname
        except: 
            return None

    def _report_api_status(self, state_name: str, status: str, message: str = "", screenshot_path: str = None):
        if not self.global_config.get("enable_api_reporting", False):
            return
            
        endpoint = self.global_config.get("api_endpoint", "http://localhost:8000/api/status")
        payload = {
            "app_name": self.global_config.get("app_name", "UnknownApp"),
            "state": state_name,
            "status": status,
            "message": message,
            "screenshot": screenshot_path,
            "timestamp": time.time()
        }
        try:
            import requests
            requests.post(endpoint, json=payload, timeout=3)
            logger.info(f"📡 API Report Sent: [{status}] {state_name}")
        except Exception as e:
            logger.debug(f"⚠️ API Report Failed: {e}")

    def _resolve_anchor(self, cfg, base_roi):
        if not cfg: return base_roi
        found, coords = self.vision.detect(cfg["feature"], roi=base_roi)
        if found and coords:
            ax, ay, aw, ah = cfg["search_area"]
            logger.info(f"   ⚓ Anchor locked. Offset ROI: {cfg['search_area']}")
            return (coords[0] + ax, coords[1] + ay, aw, ah)
        return base_roi

    def _attempt_recovery(self, state_name: str) -> bool:
        if not self.interrupt_handlers: return False
        for handler in self.interrupt_handlers:
            h_name = handler["name"]
            trigger_key = f"{state_name}_{h_name}"
            max_t = handler.get("max_triggers", 1)
            
            if self.interrupt_triggers[trigger_key] >= max_t: continue
            d_cfg = handler.get("detection", {})
            found, coords, used_roi = self._detect_with_retry(d_cfg, f"defense_{h_name}")
            
            if found:
                logger.warning(f"🚨 Defense Triggered: {h_name} ({self.interrupt_triggers[trigger_key]+1}/{max_t})")
                if "action" in handler:
                    self.executor.execute(handler["action"], coords or (0,0), roi=used_roi)
                self.interrupt_triggers[trigger_key] += 1
                return True
        return False

    def run(self, start_state: Optional[str] = None) -> dict:
        if start_state is None:
            if not self.states_list: raise ValueError("YAML 檔案中沒有定義任何 states！")
            start_state = self.states_list[0]["name"]

        curr = start_state
        self._report_api_status(curr, "started", "Task initiated")
        
        try:
            while curr not in ["end_task", "abort_task", "report_transfer_timeout"]:
                logger.info(f"\n📍 Entering State: [{curr}]")
                self._report_api_status(curr, "running")
                
                state_def = self.states.get(curr)
                if not state_def:
                    logger.error(f"⛔ FATAL: State '{curr}' not found!")
                    break

                self.loops[curr] += 1
                if self.loops[curr] > self.global_config.get("max_state_loops", 5):
                    logger.error(f"⛔ Infinite loop at {curr}")
                    break

                curr = self._process(state_def)
            
            success = (curr == "end_task")
            logger.info(f"🏁 Finished. Final State: {curr}")
            
            report = {
                "status": "success" if success else "failed",
                "final_state": curr,
                "screenshot_path": None
            }

            if success:
                report["screenshot_path"] = self._save_debug("task_success", None, return_path=True)
                self._report_api_status(curr, "success", "Task completed", report["screenshot_path"])
            else:
                report["screenshot_path"] = self._save_debug("task_failed", None, return_path=True)
                self._report_api_status(curr, "failed", "Task failed or aborted", report["screenshot_path"])

            return report

        except Exception as e:
            logger.exception(f"⛔ Crash: {e}")
            self._report_api_status(curr, "error", str(e))
            return {"status": "error", "final_state": curr, "screenshot_path": None}

    def _detect_with_retry(self, detect_cfg: Dict, state_name: str) -> Tuple[bool, Any, Any]:
        roi_key = detect_cfg.get("roi")
        base_roi = self.screen.get_roi_rect(roi_key)
        detection_roi = self._resolve_anchor(detect_cfg.get("anchor"), base_roi)
        
        if detect_cfg.get("method") == "dummy":
            return True, None, detection_roi

        features = detect_cfg.get("target_features", [])
        for feature in features:
            found, coords = self.vision.detect(feature, roi=detection_roi)
            if found:
                return True, coords, detection_roi
        
        self._save_debug(state_name + "_detect_fail", detection_roi)
        return False, None, detection_roi

    def _process(self, state):
        d_cfg = state.get("detection", {})
        found, coords, used_roi = self._detect_with_retry(d_cfg, state['name'])
        
        if not found:
            logger.warning(f"⚠️ Detection Failed for [{state['name']}]")
            if self._attempt_recovery(state['name']): return state['name']
            return self._handle_fail(state)

        if "action" in state:
            self.executor.execute(state["action"], coords or (0,0), roi=used_roi)

        if "verification" in state:
            if not self._verify(state["verification"], state['name']):
                logger.warning(f"⚠️ Verification Failed for [{state['name']}]")
                if self._attempt_recovery(state['name']): return state['name']
                return self._handle_fail(state)

        self.retries[state['name']] = 0 
        return state["transitions"]["on_success"]

    def _verify(self, v_cfg, name):
        roi_key = v_cfg.get("roi")
        base_roi = self.screen.get_roi_rect(roi_key)
        check_roi = self._resolve_anchor(v_cfg.get("anchor"), base_roi)
        timeout = v_cfg.get("timeout", 5.0)
        v_type = v_cfg.get("type", "appear")
        target_features = v_cfg.get("target_features", [])
        
        start = time.time()
        while time.time() - start < timeout:
            found_any = False
            for feat in target_features:
                if self.vision.detect(feat, roi=check_roi)[0]:
                    found_any = True
                    break
            
            if v_type == "appear" and found_any: return True
            elif v_type == "disappear" and not found_any: return True
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

        max_r = fail.get("retry", 0)
        if self.retries[name] < max_r:
            self.retries[name] += 1
            return name

        fallback = fail.get("fallback", "abort_task")
        return fallback

if __name__ == "__main__":
    yaml_file = "workflows/testing_dropdown_verify.yaml" if os.path.exists("workflows/") else "testing_dropdown_verify.yaml"
    if len(sys.argv) > 1: yaml_file = sys.argv[1]
    
    engine = AgentEngine(yaml_file)
    engine.run()