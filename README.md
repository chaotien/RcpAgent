# 🤖 RcpAgent (Vision-Based GUI Automation Engine)

RcpAgent 是一個基於「視覺感知 (Computer Vision)」與「狀態機 (State Machine)」架構的通用型 GUI 自動化測試與執行引擎。
本專案不依賴底層 API 或 DOM 結構，完全以「人類視角（看螢幕、點滑鼠、敲鍵盤）」來驅動目標應用程式。

## 🌟 引擎設計亮點 (Design Highlights)

1. **Config-Driven Architecture (設定驅動)**
   * 業務邏輯與執行機制完全解耦。所有的流程、點擊位置、驗證條件都寫在 `.yaml` 中。
   * 擴充新的 SOP 完全不需要修改 `auto_gui_engine.py` 任何一行程式碼。

2. **Multi-Feature Anchoring (多重特徵與錨點定位)**
   * 支援 `Image (Template Matching)` 與 `OCR (EasyOCR)` 雙引擎感知。
   * 獨創 **Anchor (錨點)** 機制：先鎖定畫面上的靜態特徵（如標籤），再基於該錨點的相對位置建立動態 ROI 進行互動，徹底解決 UI 元件漂移或長相相似的問題。

3. **Self-Healing & Robustness (自我修復與高強健性)**
   * 內建 `Error Branches (錯誤分支)` 機制：當預期畫面未出現時，引擎會掃描錯誤分支，並自動導航至復原步驟（例如：發現處於 Manual 模式，會自動切換至 Auto 模式再重試）。
   * **自動除錯截圖**：當 Detection 或 Verification 失敗時，會自動截取當下全螢幕，並用紅框標示出當時判斷的 ROI，存放於 `logs/` 供事後分析。

4. **Human-like Interaction (擬人化互動)**
   * 執行點擊或輸入後，滑鼠會自動移開 (Move away)，避免游標遮擋 UI 狀態（如 Hover 效果或文字變化）導致驗證失敗。

## 🚀 快速啟動 (Getting Started)

### 1. 環境準備
* Python 3.10+
* 下載並安裝 [Visual C++ Redistributable](https://aka.ms/vs/17/release/vc_redist.x64.exe) (EasyOCR 依賴項)

### 2. 安裝依賴
```bash
pip install -r requirements.txt
# 主要依賴包含: pyautogui, opencv-python, numpy, easyocr, pyyaml, pillow, PyQt5
```

### 3. 執行測試
使用 Launcher 一鍵啟動模擬器與自動化引擎：
```bash
python launcher.py
```
*(注意：執行期間請勿隨意移動實體滑鼠。若需緊急中止，請將滑鼠快速移動至螢幕左上角 (0,0) 觸發 FailSafe)*

## 🛠️ 開發工具 (Tooling)
* **`tools/asset_helper.py`**: 當您在 YAML 中新增了新的圖片路徑 (如 `$asset_dir/new_btn.png`)，執行此腳本，它會自動引導您在螢幕上框選並存檔，告別手動截圖的痛苦。

## 📖 SOP YAML 語法指南 (Workflow Reference)
每個工作流程定義為一個 YAML 檔案。包含三個主要區塊：`global_config`, `roi_map`, 與 `states`。

### 1. ROI Map (區域定義)
定義畫面上的關注區域 (Region of Interest)，格式為 `[x_pct, y_pct, width_pct, height_pct]` (以螢幕解析度百分比計算)。
```yaml
roi_map:
  top_menu:        [0.0, 0.0,  1.0,  0.10]
  dialog_center:   [0.25, 0.25, 0.50, 0.50]
```

### 2. State Definition (狀態定義)
每個步驟就是一個 State，遵循 `Detection -> Action -> Verification -> Transition` 的生命週期。

#### 範例：選擇下拉選單
```yaml
  - name: "click_port_2_option"
    # [1] 偵測目標在哪裡
    detection:
      roi: "engineering_pnl"
      # 使用 Anchor 鎖定標籤下方的相對區域
      anchor:
        feature: { type: "ocr", text: "Select Port:" }
        search_area: [-50, 20, 200, 150] 
      target_features:
        - { type: "image", path: "$asset_dir/dropdown_port2.png" }

    # [2] 對目標做什麼
    action:
      type: "click"
      offset: [0, 0] # 相對目標中心的位移

    # [3] 驗證動作是否成功
    verification:
      type: "appear" # 期待出現 (另有 disappear)
      timeout: 5.0
      roi: "engineering_pnl"
      anchor:
        feature: { type: "ocr", text: "Select Port:" }
        search_area: [-50, 20, 200, 50]
      target_features:
        - { type: "ocr", text: "2" }

    # [4] 狀態轉移與錯誤處理
    transitions:
      on_success: "next_state_name"
      on_fail:
        retry: 2 # 允許失敗重試次數
        error_branches: # 條件分支
          - condition: { type: "ocr", text: "Not Ready", roi: "engineering_pnl" }
            next_state: "fix_not_ready_state"
        fallback: "abort_task" # 最終防線
```

## License

This project is licensed under the Apache License 2.0. 

- **Commercial Use Allowed:** You can use this project for commercial purposes.  
- **Patent Protection Included:** The license protects you from patent claims.  
- **Freedom to Modify:** You are free to modify and distribute this project.  
- **No Warranty:** The software is provided "as is" without any warranty of any kind.  

For more details, see the [LICENSE](LICENSE) file.