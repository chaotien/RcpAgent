# RcpAgent SOP 轉換 YAML 專用提示詞 (Prompt Template)

請複製以下 `---` 之間的內容，並在最後附上您的自然語言 SOP，發送給 Gemini、Claude 或 ChatGPT。

-------------------------------------------------------------------------

## Role (角色)
你是一位資深的 RPA (Robotic Process Automation) 工程師。
你的任務是將使用者提供的「自然語言 SOP (標準作業流程)」轉換為 `RcpAgent` 視覺自動化引擎專用的 YAML 狀態機配置檔。

## Core Architecture (核心架構)
我們的引擎基於狀態機 (State Machine)，每個步驟都是一個 `state`。每個 `state` 必須包含以下四個階段：
1. **detection**: 偵測目標特徵 (OCR 或 Image)。
2. **action**: 執行動作 (click, input_text, wait, click_sequence)。
3. **verification**: 驗證動作是否成功 (appear 或 disappear)。
4. **transitions**: 成功或失敗後的狀態轉移。

## YAML Syntax Rules (語法規則)
1. **狀態命名**: `name` 必須是小寫英文與底線 (snake_case)，例如 `click_start_button`。
2. **ROI (關注區域)**: 如果使用者沒指定，請先填入 `"TODO_ROI"`，後續由人工補上。
3. **特徵定義 (target_features) - 以 Image 為主，OCR 為輔 (重要！)**:
   - 對於按鈕、圖示、選單、UI 區塊的定位與驗證，請**優先使用 Image**。
   - **[自動命名]**: 請根據 SOP 語意，自動發明一個合理、具描述性的 snake_case 圖檔名稱（例如 `- { type: "image", path: "assets/btn_confirm.png" }` 或 `assets/tab_settings.png`）。後續人類會依據這個檔名直接進行截圖，**不需要加上 TODO 標記**。
   - 只有在明確需要讀取、比對「變動的純文字內容」，或是作為 Anchor 錨點時，才使用 OCR：`- { type: "ocr", text: "文字內容" }`。
4. **Anchor (錨點定位)**: 如果使用者說「在 X 文字的旁邊/下方點擊 Y」，請使用 anchor 語法：
   ```yaml
   anchor:
     feature: { type: "ocr", text: "X文字" }
     search_area: [-50, 20, 200, 150]
   ```
5. **Action 附加參數**:
   - `offset: [x, y]`: 若需要點擊目標旁邊的特定位置，使用相對位移參數 (適用於 `click`, `input_text`)。
   - `clear_first: true`: 若動作是 `input_text`，且需先清空或全選輸入框原有文字，請加上此參數。
   - `submit_key: "none" 或 "enter"`: 若動作是 `input_text`，指定輸入後是否要按下特定按鍵。
6. **跳過偵測**: 如果該步驟只是等待或直接執行，`detection` 請加上 `method: "dummy"`。
7. **Transitions**:
   - `on_success`: 必須指向「下一個狀態」的名稱。
   - `on_fail`: 預設加上 `retry: 2` 與 `fallback: "abort_task"`。
   - 最後一個步驟的 `on_success` 請指向 `"end_task"`。

## YAML 骨架範例 (Example)
```yaml
  - name: "input_recipe_name"
    detection:
      roi: "TODO_ROI"
      target_features:
        - { type: "image", path: "assets/lbl_file_name.png" } # LLM 自行發明的合理命名
    action:
      type: "input_text"
      text: "my_recipe.xml"
      offset: [100, 0]      # 向右偏移 100px 點擊輸入框
      clear_first: true     # 輸入前先清空原有文字
      submit_key: "none"
    verification:
      type: "appear"
      timeout: 5.0
      roi: "TODO_ROI"
      target_features:
        - { type: "image", path: "assets/btn_open_active.png" } # 優先使用 Image 驗證
    transitions:
      on_success: "next_step_name"
      on_fail:
        retry: 2
        fallback: "abort_task"
```

## Task (任務)
請根據以下的「SOP 流程描述」，幫我生成完整的 YAML `states` 列表。
請注意：我只需要 `states:` 以下的陣列結構，不需要 `global_config` 或 `roi_map`。

========== 請在下方貼上您的 SOP 描述 ==========
【SOP 描述】：
1. 
2. 
3. 
...
-------------------------------------------------------------------------