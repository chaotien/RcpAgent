# Copyright 2026 chaotien
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import subprocess
import time
import sys
import os
import platform
import argparse
import importlib.util

def run_suite():
    # ==========================================
    # 1. 解析命令列參數 (CLI Arguments)
    # ==========================================
    parser = argparse.ArgumentParser(description="🚀 RcpAgent Test Suite Launcher (含模擬器與動態變數)")
    
    parser.add_argument("--workflow", "-w", type=str, default="workflows/sop_wafer_load_template.yaml", help="SOP YAML 的路徑")
    parser.add_argument("--engine", "-e", type=str, default="core/auto_gui_engine.py", help="執行引擎 .py 的路徑")
    parser.add_argument("--asset_dir", "-a", type=str, default="assets/simulator", help="目標機台截圖包的資料夾路徑")
    parser.add_argument("--recipe", "-r", type=str, default="test_recipe.xml", help="Recipe 名稱 (替換 $recipe_name)")
    parser.add_argument("--offset", "-o", type=str, default="0,0", help="Slot 的點擊位移，格式: x,y (替換 $slot_offset)")
    
    args = parser.parse_args()

    # 檢查核心檔案
    if not os.path.exists(args.workflow):
        print(f"❌ 錯誤: 找不到 Workflow 檔案 -> {args.workflow}")
        sys.exit(1)
    if not os.path.exists(args.engine):
        print(f"❌ 錯誤: 找不到 Engine 檔案 -> {args.engine}")
        sys.exit(1)

    # 解析 Offset
    try:
        slot_offset = [int(v.strip()) for v in args.offset.split(',')]
    except Exception:
        print("❌ 錯誤: Offset 格式錯誤，必須為 x,y (例如: 0,428)")
        sys.exit(1)

    # 準備要注入的變數字典
    dynamic_vars = {
        "asset_dir": args.asset_dir,
        "recipe_name": args.recipe,
        "slot_offset": slot_offset
    }

    print("==================================================")
    print("🤖 RcpAgent Test Suite 已啟動")
    print(f"📂 Workflow: {args.workflow}")
    print(f"⚙️ Engine:   {args.engine}")
    print(f"🖼️ Assets:   {args.asset_dir}")
    print(f"🧩 Variables: {dynamic_vars}")
    print("==================================================")

    # ==========================================
    # 2. 啟動模擬器 (非阻塞模式)
    # ==========================================
    print("\n>>> [1/3] Starting Simulator...")
    if platform.system() == "Windows":
        sim_proc = subprocess.Popen([sys.executable, "simulator/tool_simulator_qt.py"], shell=False)
    else:
        sim_proc = subprocess.Popen([sys.executable, "simulator/tool_simulator_qt.py"])

    # 給予緩衝時間讓 GUI 載入
    print(">>> [2/3] Waiting for Simulator to load (3s)...")
    time.sleep(3)

    # ==========================================
    # 3. 啟動測試引擎 (動態載入，阻塞模式)
    # ==========================================
    print(">>> [3/3] Starting Automation Engine...")
    try:
        # 使用 importlib 動態載入使用者選擇的 Engine
        spec = importlib.util.spec_from_file_location("dynamic_engine", args.engine)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        # 假設 Engine 的 Class 名稱皆為 AgentEngine
        EngineClass = getattr(module, "AgentEngine")
        
        # 實例化 Engine，並將動態變數注入！
        engine = EngineClass(args.workflow, dynamic_vars=dynamic_vars)
        report = engine.run()
        
        print("\n==================================================")
        print(f"✅ 執行完畢! 狀態: {report.get('status')}")
        print(f"🏁 最終階段: {report.get('final_state')}")
        print("==================================================")
        
    except Exception as e:
        print(f"\n⛔ Engine Error: {e}")
    finally:
        # ==========================================
        # 4. 測試結束後，安全關閉模擬器
        # ==========================================
        print("\n>>> Closing Simulator...")
        sim_proc.terminate()
        time.sleep(1)
        if sim_proc.poll() is None:
            sim_proc.kill()
        print(">>> Test Suite Finished.")

if __name__ == "__main__":
    run_suite()