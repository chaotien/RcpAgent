import argparse
import sys
import os
import importlib.util
from core.auto_gui_engine import AgentEngine

def main():
    parser = argparse.ArgumentParser(description="🚀 RcpAgent CLI Launcher (動態變數注入版)")
    
    # 核心檔案設定
    parser.add_argument("--workflow", "-w", type=str, default="workflows/sop_wafer_load_template.yaml", help="SOP YAML 的路徑")
    parser.add_argument("--engine", "-e", type=str, default="core/auto_gui_engine.py", help="執行引擎 .py 的路徑")
    
    # 常用動態變數
    parser.add_argument("--asset_dir", "-a", type=str, default="assets", help="目標機台截圖包的資料夾路徑 (例如: assets/model_B)")
    parser.add_argument("--recipe", "-r", type=str, default="test_recipe.xml", help="Recipe 名稱 (替換 $recipe_name)")
    
    # 為了方便 CLI 輸入，Slot Offset 用逗號分隔輸入，例如: --offset 0,428
    parser.add_argument("--offset", "-o", type=str, default="0,0", help="Slot 的點擊位移，格式: x,y (替換 $slot_offset)")
    
    args = parser.parse_args()

    # 檢查檔案是否存在
    if not os.path.exists(args.workflow):
        print(f"❌ 錯誤: 找不到 Workflow 檔案 -> {args.workflow}")
        sys.exit(1)
        
    if not os.path.exists(args.engine):
        print(f"❌ 錯誤: 找不到 Engine 檔案 -> {args.engine}")
        sys.exit(1)
        
    if not os.path.exists(args.asset_dir):
        print(f"⚠️ 警告: 找不到 Asset 資料夾 -> {args.asset_dir} (辨識時可能會失敗)")

    # 解析 Offset
    try:
        slot_offset = [int(v.strip()) for v in args.offset.split(',')]
    except Exception:
        print("❌ 錯誤: Offset 格式錯誤，必須為 x,y (例如: 0,428)")
        sys.exit(1)

    # 準備注入的變數字典
    dynamic_vars = {
        "asset_dir": args.asset_dir,
        "recipe_name": args.recipe,
        "slot_offset": slot_offset
    }

    print("==================================================")
    print("🤖 RcpAgent CLI Launcher 已啟動")
    print(f"📂 Workflow: {args.workflow}")
    print(f"⚙️ Engine: {args.engine}")
    print(f"🧩 注入變數 (Dynamic Vars): {dynamic_vars}")
    print("==================================================")

    # 動態載入使用者選擇的 Engine
    try:
        spec = importlib.util.spec_from_file_location("dynamic_engine", args.engine)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        # 假設所有的 Engine Class 都叫 AgentEngine
        EngineClass = getattr(module, "AgentEngine")
        
        # 執行
        engine = EngineClass(args.workflow, dynamic_vars=dynamic_vars)
        report = engine.run()
        
        print("\n==================================================")
        print(f"✅ 執行完畢! 狀態: {report.get('status')}")
        print(f"🏁 最終階段: {report.get('final_state')}")
        print("==================================================")

    except Exception as e:
        print(f"\n⛔ 啟動或執行過程發生嚴重錯誤:\n{e}")
        sys.exit(1)

if __name__ == "__main__":
    main()