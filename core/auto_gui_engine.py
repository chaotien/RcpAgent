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
# 1. Vision System (新增 Scale Calibration 機制)
# ==============================================================================
class VisionSystem:
    def __init__(self, confidence_threshold=0.8):
        self.confidence_threshold = confidence_threshold
        self.MOCK_MODE = False 
        self.reader = None
        self._init_easyocr()
        
        # [NEW] 解析度/縮放自動校正參數
        self.is_calibrated = False
        self.scale_factor = 1.0
        # 涵蓋常見的 Windows 縮放比例: 100%, 125%, 150%, 175%, 200%, 及縮小比例
        self.calibration_scales = [1.0, 1.25, 1.5, 1.75, 2.0, 0.8, 0.75, 0.5]

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

        # 1. Image (Template Matching 支援 Scale Calibration)
        if f_type == "image":
            path = feature.get("path")
            conf = feature.get("confidence", self.confidence_threshold)
            try:
                if not os.path.exists(path):
                    logger.error(f"      ❌ File not found: {path}")
                    return False, None
                
                original_img = Image.open(path)
                
                # [NEW] 決定要掃描的縮放比例
                # 如果尚未校正，掃描整個 calibration_scales；如果已校正，只用鎖定的 scale_factor
                scales_to_try = [self.scale_factor] if self.is_calibrated else self.calibration_scales
                
                for scale in scales_to_try:
                    new_w = int(original_img.width * scale)
                    new_h = int(original_img.height * scale)
                    
                    if new_w == 0 or new_h == 0:
                        continue
                        
                    # 縮放範本圖片 (使用 LANCZOS 確保縮放品質)
                    resized_img = original_img.resize((new_w, new_h), Image.LANCZOS)
                    
                    try:
                        box = pyautogui.locateOnScreen(resized_img, region=roi, confidence=conf, grayscale=True)
                        if box:
                            # 如果是第一次成功匹配，鎖定此縮放係數！
                            if not self.is_calibrated:
                                self.is_calibrated = True
                                self.scale_factor = scale
                                logger.info(f"\n      🎯 [Calibration Success] UI Scale Factor locked at: {scale}x")
                                logger.info(f"      👉 All subsequent image matchings will use this scale.\n")
                                
                            center = pyautogui.center(box)
                            logger.info(f"      ✅ Found Image at {center} (Scale used: {scale}x)")
                            return True, (center.x, center.y)
                    except pyautogui.ImageNotFoundException:
                        pass # 繼續嘗試下一個縮放比例
                        
                # 如果所有 scale 都掃過還是找不到
                logger.info("      ❌ Image Not Found (Tried all scales)" if not self.is_calibrated else "      ❌ Image Not Found")
                return False, None
                
            except Exception as e:
                logger.warning(f"      ⚠️ Vision Error: {e}")

        # 2. OCR (本來就具有一定的 Scale Invariance，但回傳的座標仍需配合縮放後的 ROI)
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
                    logger.info(f"   🧹 Clearing existing text (Ctrl+A -> Del)")
                    pyautogui.hotkey('ctrl', 'a')
                    time.sleep(0.1)
                    pyautogui.press('delete')
                    time.sleep(0.1)
                    
            logger.info(f"   ⌨️ Action: Typing '{text}'")
            pyautogui.write(text)
            
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
        
        # 保存狀態陣列，以維持 YAML 中的順序
        self.states_list = self.config.get("states", [])
        self.states = {s["name"]: s for s in self.states_list}
        
        self.interrupt_handlers = self.config.get("interrupt_handlers", [])
        self.interrupt_triggers = defaultdict(int)
        
        self.vision = VisionSystem()
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

    def _resolve_anchor(self, cfg, base_roi):
        if not cfg: return base_roi
        found, coords = self.vision.detect(cfg["feature"], roi=base_roi)
        if found and coords:
            ax, ay, aw, ah = cfg["search_area"]
            logger.info(f"   ⚓ Anchor locked. Offset ROI: {cfg['search_area']}")
            return (coords[0] + ax, coords[1] + ay, aw, ah)
        logger.warning("   ⚠️ Anchor not found, using base ROI")
        return base_roi

    def _attempt_recovery(self, state_name: str) -> bool:
        if not self.interrupt_handlers:
            return False
            
        logger.info(f"🛡️ Entering Defense Mode for state [{state_name}]...")
        for handler in self.interrupt_handlers:
            h_name = handler["name"]
            trigger_key = f"{state_name}_{h_name}"
            max_t = handler.get("max_triggers", 1)
            
            if self.interrupt_triggers[trigger_key] >= max_t:
                continue
                
            d_cfg = handler.get("detection", {})
            found, coords, used_roi = self._detect_with_retry(d_cfg, f"defense_{h_name}")
            
            if found:
                logger.warning(f"🚨 Defense Triggered: {h_name} ({self.interrupt_triggers[trigger_key]+1}/{max_t})")
                if "action" in handler:
                    self.executor.execute(handler["action"], coords or (0,0), roi=used_roi)
                self.interrupt_triggers[trigger_key] += 1
                return True
                
        logger.info("🛡️ Defense failed or not applicable. Proceeding to fail handlers.")
        return False

    # [NEW] 將 start_state 預設改為 None，並自動抓取第一個 state
    def run(self, start_state: Optional[str] = None) -> dict:
        if start_state is None:
            if not self.states_list:
                raise ValueError("YAML 檔案中沒有定義任何 states！")
            start_state = self.states_list[0]["name"]
            logger.info(f"👉 偵測到 YAML 初始起點，自動設定 start_state = '{start_state}'")

        curr = start_state
        try:
            while curr not in ["end_task", "abort_task", "report_transfer_timeout"]:
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
            
            # 將執行結果打包，供未來 Agent 呼叫使用
            success = (curr == "end_task")
            logger.info(f"🏁 Finished. Final State: {curr}")
            
            report = {
                "status": "success" if success else "failed",
                "final_state": curr,
                "screenshot_path": None
            }

            if success:
                logger.info("📸 Capturing success screenshot...")
                report["screenshot_path"] = self._save_debug("task_success", None, return_path=True)
            else:
                report["screenshot_path"] = self._save_debug("task_failed", None, return_path=True)

            return report

        except Exception as e:
            logger.exception(f"⛔ Crash: {e}")
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
            if self._attempt_recovery(state['name']):
                logger.info(f"🔄 Defense completed. Restarting state [{state['name']}]")
                time.sleep(1.0)
                return state['name']
            return self._handle_fail(state)

        if "action" in state:
            self.executor.execute(state["action"], coords or (0,0), roi=used_roi)

        if "verification" in state:
            if not self._verify(state["verification"], state['name']):
                logger.warning(f"⚠️ Verification Failed for [{state['name']}]")
                if self._attempt_recovery(state['name']):
                    logger.info(f"🔄 Defense completed. Restarting state [{state['name']}]")
                    time.sleep(1.0)
                    return state['name']
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
            
            if v_type == "appear" and found_any:
                logger.info(f"   ✅ Verification Passed (Appeared)")
                return True
            elif v_type == "disappear" and not found_any:
                logger.info(f"   ✅ Verification Passed (Disappeared)")
                return True
            
            time.sleep(0.5)
            
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
    yaml_file = "workflows/testing_dropdown_verify.yaml" if os.path.exists("workflows/") else "testing_dropdown_verify.yaml"
    if len(sys.argv) > 1: yaml_file = sys.argv[1]
    
    engine = AgentEngine(yaml_file)
    logger.info("⏳ Starting in 3s...")
    time.sleep(3)
    
    # [NEW] 不帶入參數，讓引擎自動決定從 YAML 第一個 state 開始
    engine.run()