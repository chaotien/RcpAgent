import subprocess
import time
import sys
import os
import platform

def run_suite():
    # 1. 啟動模擬器 (非阻塞模式)
    print(">>> Starting Simulator...")
    if platform.system() == "Windows":
        sim_proc = subprocess.Popen([sys.executable, "tool_simulator_qt.py"], shell=False)
    else:
        sim_proc = subprocess.Popen([sys.executable, "tool_simulator_qt.py"])

    # 2. 給予緩衝時間讓 GUI 載入
    time.sleep(3)

    # 3. 啟動測試引擎 (阻塞模式，等待測試完成)
    print(">>> Starting Automation Engine...")
    try:
        subprocess.run([sys.executable, "auto_gui_engine.py"], check=False)
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