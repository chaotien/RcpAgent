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

def run_suite():
    # 1. 啟動模擬器 (非阻塞模式)
    print(">>> Starting Simulator...")
    if platform.system() == "Windows":
        sim_proc = subprocess.Popen([sys.executable, "simulator/tool_simulator_qt.py"], shell=False)
    else:
        sim_proc = subprocess.Popen([sys.executable, "simulator/tool_simulator_qt.py"])

    # 2. 給予緩衝時間讓 GUI 載入
    time.sleep(3)

    # 3. 啟動測試引擎 (阻塞模式，等待測試完成)
    print(">>> Starting Automation Engine...")
    try:
        subprocess.run([sys.executable, "core/auto_gui_engine.py", "workflows/sop_tbs_001_workflow.yaml"], check=False)
    except Exception as e:
        print(f"Engine Error: {e}")
    finally:
        # 4. 測試結束後，關閉模擬器
        print(">>> Closing Simulator...")
        sim_proc.terminate()
        time.sleep(1)
        if sim_proc.poll() is None:
            sim_proc.kill()

if __name__ == "__main__":
    run_suite()