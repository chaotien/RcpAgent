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
# 1. Vision System
# ==============================================================================
class VisionSystem:
    def __init__(self, confidence_threshold=0.8):
        self.confidence_threshold = confidence_threshold
        self.MOCK_MODE = False 
        self.reader = None
        self._init_easyocr()

    def _init_easyocr(self):
        try:
            import easyocr 
            self.reader = easyocr.Reader(['en'], gpu=False)
        except Exception as e:
            logger.warning(f"⚠️ EasyOCR init warning: {e}")

    def detect(self, feature: Dict, roi: Optional[Tuple[int, int, int, int]] = None) -> Tuple[bool, Optional[Tuple[int, int]]]:
        f_type = feature.get("type")
        target_info = feature.get("text") or feature.get("path") or "unknown"
        
        logger.info(f"   👁️ Scanning [{f_type}]: '{target_info}' in ROI: {roi}")

        if self.MOCK_MODE: return True, (100, 100)

        # 1. Image
        if f_type == "image":
            path = feature.get("path")
            conf = feature.get("confidence", self.confidence_threshold)
            try:
                if not os.path.exists(path):
                    logger.error(f"      ❌ File not found: {path}")
                    return False, None
                
                box = pyautogui.locateOnScreen(path, region=roi, confidence=conf, grayscale=True)
                if box:
                    center = pyautogui.center(box)
                    logger.info(f"      ✅ Found Image at {center}")
                    return True, (center.x, center.y)
            except Exception as e:
                logger.warning(f"      ⚠️ Vision Error: {e}")

        # 2. OCR
        elif f_type == "ocr":
            if not self.reader: return False, None
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
        logger.info(f"🖥️ Screen Resolution: {w}x{h}")
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
            clear_first = config.get("clear_first", False) # [NEW] 讀取是否需要清空
            
            if coords:
                fx, fy = coords[0] + offset[0], coords[1] + offset[1]
                pyautogui.click(fx, fy)
                time.sleep(0.2)
                
                # [NEW] 執行全選並刪除的動作
                if clear_first:
                    logger.info(f"   🧹 Clearing existing text (Ctrl+A -> Del)")
                    pyautogui.hotkey('ctrl', 'a')
                    time.sleep(0.1)
                    pyautogui.press('delete')
                    time.sleep(0.1)
                    
            logger.info(f"   ⌨️ Action: Typing '{text}'")
            pyautogui.write(text) # 輸入新文字
            
            if submit and submit.lower() != "none":
                logger.info(f"   ⏎ Action: Pressing key '{submit}'")
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
        self.states = {s["name"]: s for s in self.config.get("states", [])}
        
        self.vision = VisionSystem()
        self.screen = ScreenManager(self.config.get("roi_map", {}))
        self.executor = ActionExecutor(self.global_config, self.vision, self.screen)
        
        self.loops = defaultdict(int)
        self.retries = defaultdict(int)

    def _save_debug(self, name, roi):
        try:
            fname = f"logs/debug_{time.strftime('%H%M%S')}_{name}.png"
            img = cv2.cvtColor(np.array(pyautogui.screenshot()), cv2.COLOR_RGB2BGR)
            if roi: cv2.rectangle(img, (roi[0], roi[1]), (roi[0]+roi[2], roi[1]+roi[3]), (0,0,255), 2)
            cv2.imwrite(fname, img)
            logger.warning(f"📸 Debug saved: {fname}")
        except: pass

    def _resolve_anchor(self, cfg, base_roi):
        if not cfg: return base_roi
        found, coords = self.vision.detect(cfg["feature"], roi=base_roi)
        if found and coords:
            ax, ay, aw, ah = cfg["search_area"]
            logger.info(f"   ⚓ Anchor locked. Offset ROI: {cfg['search_area']}")
            return (coords[0] + ax, coords[1] + ay, aw, ah)
        logger.warning("   ⚠️ Anchor not found, using base ROI")
        return base_roi

    def run(self, start_state="check_system_connection"):
        curr = start_state
        try:
            while curr not in ["end_task", "abort_task"]:
                logger.info(f"\n📍 Entering State: [{curr}]")
                
                state_def = self.states.get(curr)
                if not state_def:
                    logger.error(f"⛔ FATAL: State '{curr}' not found!")
                    break

                self.loops[curr] += 1
                if self.loops[curr] > self.global_config.get("max_state_loops", 5):
                    logger.error(f"⛔ Infinite loop at {curr}")
                    break

                curr = self._process(state_def)
            
            # [NEW] 任務成功結束後的截圖
            logger.info(f"🏁 Finished. Final: {curr}")
            if curr == "end_task":
                logger.info("📸 Capturing success screenshot...")
                self._save_debug("task_success", None)
            
        except Exception as e:
            logger.exception(f"⛔ Crash: {e}")

    def _detect_with_retry(self, detect_cfg: Dict, state_name: str) -> Tuple[bool, Any, Any]:
        """
        [Refactor] 封裝 ROI 解析與特徵偵測邏輯
        Return: (found, coords, final_used_roi)
        """
        # 1. 取得基礎 ROI
        roi_key = detect_cfg.get("roi")
        base_roi = self.screen.get_roi_rect(roi_key)
        
        # 2. 解析 Anchor (如果有) -> 得到最終偵測用的 ROI
        detection_roi = self._resolve_anchor(detect_cfg.get("anchor"), base_roi)
        
        # 3. 處理 Dummy
        if detect_cfg.get("method") == "dummy":
            return True, None, detection_roi

        # 4. 掃描 Target Features
        features = detect_cfg.get("target_features", [])
        for feature in features:
            found, coords = self.vision.detect(feature, roi=detection_roi)
            if found:
                return True, coords, detection_roi
        
        # [NEW] 失敗時截圖，使用計算後的 detection_roi
        self._save_debug(state_name + "_detect_fail", detection_roi)
                
        return False, None, detection_roi

    def _process(self, state):
        # 1. Detection (呼叫重構後的函式)
        d_cfg = state.get("detection", {})
        found, coords, used_roi = self._detect_with_retry(d_cfg, state['name'])
        
        if not found:
            logger.warning(f"⚠️ Detection Failed for [{state['name']}]")
            return self._handle_fail(state)

        # 2. Action (傳入 used_roi 給 click_sequence 使用)
        if "action" in state:
            self.executor.execute(state["action"], coords or (0,0), roi=used_roi)

        # 3. Verification
        if "verification" in state:
            if not self._verify(state["verification"], state['name']):
                logger.warning(f"⚠️ Verification Failed for [{state['name']}]")
                return self._handle_fail(state)

        self.retries[state['name']] = 0 
        return state["transitions"]["on_success"]

    def _verify(self, v_cfg, name):
        """Verification Logic (Aligned with Detection)"""
        # 1. Resolve ROI (Reuse logic)
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
            
            if v_type == "appear" and found_any:
                logger.info(f"   ✅ Verification Passed (Appeared)")
                return True
            elif v_type == "disappear" and not found_any:
                logger.info(f"   ✅ Verification Passed (Disappeared)")
                return True
            
            time.sleep(0.5)
            
        # 失敗時截圖，使用計算後的 check_roi
        self._save_debug(name+"_verify_fail", check_roi)
        return False

    def _handle_fail(self, state):
        name = state['name']
        fail = state["transitions"]["on_fail"]
        
        for br in fail.get("error_branches", []):
            roi = self.screen.get_roi_rect(br["condition"].get("roi"))
            if self.vision.detect(br["condition"], roi=roi)[0]:
                logger.info(f"🔀 Error Branch matched: {br['next_state']}")
                return br['next_state']

        max_r = fail.get("retry", 0)
        if self.retries[name] < max_r:
            self.retries[name] += 1
            logger.warning(f"🔄 Retrying [{name}] ({self.retries[name]}/{max_r})...")
            return name

        fallback = fail.get("fallback", "abort_task")
        logger.error(f"💀 State [{name}] failed. Fallback: {fallback}")
        return fallback

if __name__ == "__main__":
    yaml_file = "workflows/sop_tbs_001_workflow.yaml"
    if len(sys.argv) > 1: yaml_file = sys.argv[1]
    
    engine = AgentEngine(yaml_file)
    logger.info("⏳ Starting in 3s...")
    time.sleep(3)
    engine.run()