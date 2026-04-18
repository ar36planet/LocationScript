# AI Agent CLI / Plugin 可行性評估（以 LocationScript 為基礎）

## 1) 結論（先講重點）

**可行，而且建議優先做 CLI，再做 Plugin（MCP / Tool Adapter）。**

- 目前專案核心能力已經存在：
  - 可直接設定/清除虛擬定位（透過 `pymobiledevice3 ... simulate-location`）
  - 有 tunnel 啟停
  - 有座標字串/Google URL 解析
  - 有收藏與座標清單讀寫
- 這些能力大多已在 `location.py`、`tunnel.py`、`storage.py`、`loc.sh` 中，邏輯與 UI 可分離程度高。
- 目前主要阻力不是演算法，而是**UI 與 side effect（Tk、subprocess、OS 權限）耦合**；先抽象成 service 層即可解。

---

## 2) 現況盤點（對 Agent 友善度）

### 已有優勢

1. **已有準 CLI 雛形**：`loc.sh` 已提供 `set/go/clear/list/tunnel`，可作為正式 CLI 的行為藍本。  
2. **核心功能可程式化呼叫**：`location.set_location_direct()` 與 `clear_location()` 已是明確 API。  
3. **資料層獨立**：收藏與歷史紀錄在 `storage.py`，可直接被 CLI/Plugin 重用。  
4. **路線與巡邏能力存在**：有 `route_planner.py` 與 `patrol.py`（可成為 agent 的高階任務能力）。

### 目前限制

1. **UI 依賴注入不足**：`location.py` 依賴 Tk 元件（`_root/_status/_entry`）與 `after()` 事件循環。  
2. **tunnel 啟動流程偏 GUI/macOS**：`tunnel.py` 透過 AppleScript 打開 Terminal，對 headless agent 不友善。  
3. **錯誤回傳偏 UI 字串**：以 label 更新為主，缺少穩定 machine-readable exit code / JSON。  
4. **平台耦合**：安裝與啟動主要針對 macOS + zsh。

---

## 3) 目標型態：CLI 與 Plugin 應如何切分

### A. CLI（第一階段）

建議新增 `ifly`（Python argparse / typer 皆可），最少包含：

- `ifly device list`
- `ifly device select <udid>` 或 `--default` 設定預設裝置
- `ifly tunnel start|stop|status`
- `ifly location set --lat ... --lng ...`
- `ifly location clear`
- `ifly location parse --google-url ...` 或 `--coords ...`
- `ifly favorites list|add|delete|import`
- `ifly route optimize --mode flower|fruit|outer-loop --input file.json`
- `ifly patrol run --input file.json --mode loop|pingpong|once --speed-kmh ...`
- `ifly doctor`（檢查環境：pymobiledevice3 版本、USB 配對、開發者模式、tunnel 狀態、sudo 權限）

**設計原則**：
- 預設裝置可透過 `device select --default` 或環境變數 `LOCATIONSCRIPT_DEVICE` 設定；多裝置時未指定裝置則報錯。
- 預設人類可讀輸出；加 `--json` 提供 agent 可解析輸出。
- 所有指令提供一致 exit code：
  - `0` 成功
  - `1` 未預期的一般錯誤（例外未捕獲、內部邏輯錯誤）
  - `2` 參數錯誤
  - `3` 環境錯誤（缺 `pymobiledevice3`、未連線、sudo 權限不足）
  - `4` 執行失敗（命令失敗/timeout）

### B. Plugin（第二階段）

建議採用 **MCP Server** 作為唯一 plugin 介面。

#### 為何選 MCP（跨平台相容性）

| 平台 | MCP 支援狀況 |
|------|-------------|
| **Claude Code** | 原生支援（Anthropic 自家協定） |
| **Gemini** | 2025 年初起支援（Gemini 2.0+、Google AI Studio、Vertex AI） |
| **OpenAI / Codex** | 2025 年 3 月起 Agents SDK 與 ChatGPT Desktop 支援 |

MCP 是目前三大主流 LLM 平台的共同語言；若改用 OpenAI Tool Adapter（function calling 格式），則只有 OpenAI 原生支援，Gemini 與 Claude 各需額外 adapter，維護成本高且容易出現行為差異。

#### MCP Server 規格

- 提供工具：`set_location`, `clear_location`, `tunnel_status`, `plan_route`, `run_patrol`
- 內部直接呼叫 CLI（穩定、可 observability）或 Python service（低延遲）
- **安全考量**：
  - 綁定 localhost 或 Unix socket，不對外暴露
  - 敏感操作（set/clear/patrol）加 `--confirm` token 或 allowlist 限制呼叫來源
  - 所有操作寫入審計 log（含 caller identity、timestamp、參數）

**建議順序**：`核心 service → CLI → MCP`，降低重工。

---

## 4) 需要的重構（最小可行）

### 4.1 抽出 Core Service（不依賴 Tk）

新增例如：

- `core/location_service.py`
  - `set_location(lat, lng, keepalive=False, fetch_name=False) -> Result`
  - `clear_location() -> Result`
  - `parse_google_url(url) -> ParsedCoords | None`
  - `parse_coords(text) -> ParsedCoords | None`
- `core/tunnel_service.py`
  - `start_tunnel(headless=True) -> Result`
  - `stop_tunnel() -> Result`
  - `status() -> TunnelStatus`
- `core/storage_service.py`
  - 包裝 favorites/history/list 檔案操作

Tk app 與 CLI 都只呼叫 service。

### 4.2 統一結果格式

```json
{
  "ok": true,
  "code": "LOCATION_SET",
  "message": "Location updated",
  "data": {"lat": 25.033, "lng": 121.5654}
}
```

### 4.3 Headless 友善 tunnel 流程

- 保留 GUI 模式 AppleScript；
- 新增 headless 模式：直接 `sudo -n` 檢查、必要時引導使用者先完成 sudo 權限準備。

### 4.4 tunnel 密碼與授權策略（CLI 必要規格）

- 原則：CLI 預設不進行互動式密碼輸入，避免卡住自動化流程與 agent 執行。
- `tunnel start` 執行順序：
  - 先檢查是否已在執行（避免重複啟動）。
  - 先跑 `sudo -n <tunneld-wrapper>` 測試免密碼能力。
  - 可執行則直接啟動；不可執行則回傳明確錯誤與設定指引。
- 建議使用 `sudoers` 最小權限白名單（`NOPASSWD`）：
  - 不直接放行整個 `pymobiledevice3`。
  - 使用固定路徑 wrapper（例如 `/usr/local/bin/ifly-tunneld`）再授權該 wrapper。
- fallback：提供 `tunnel start --interactive` 供人工輸入密碼；預設維持 non-interactive。
- 錯誤碼建議：
  - `3` 環境/權限未就緒（例如 `sudo -n` 失敗、缺少 wrapper、缺少 `pymobiledevice3`）。
  - `4` 指令已送出但 `tunneld` 啟動失敗或超時。

---

## 5) 風險與對策

1. **iOS / pymobiledevice3 版本相容風險**  
   - 對策：`ifly doctor`（已列入 CLI 規格）檢查版本、USB 配對、開發者模式、tunnel 狀態，並輸出可複製的修復指引。

2. **權限與安全風險（sudo、定位操作）**  
   - 對策：以 `sudoers + wrapper` 實作最小授權、預設 `sudo -n` 非互動、提供 `--interactive` fallback、加 `--confirm` 與審計 log。

3. **Agent 誤操作風險（重複 set、巡邏暴走）**  
   - 對策：rate limit、idempotency key、`patrol stop` 高優先中斷。

4. **跨平台風險**  
   - 對策：先宣告 macOS-only；CLI 輸出明確錯誤碼。

---

## 6) 建議里程碑（2~4 週）

### Milestone 1（3~5 天）
- 抽 `core` service（location/tunnel/storage）
- 讓現有 Tk app 改用 service（行為不變）

### Milestone 2（3~5 天）
- 建立 `ifly` CLI
- 完成 `set/clear/tunnel/status/parse/favorites`
- 加 `--json` 與 exit code 規格

### Milestone 3（4~7 天）
- 加 `route optimize` / `patrol run`
- 補整合測試：mock `core` service interface（而非底層 subprocess），搭配 fixture JSON 驗證 CLI 輸出格式與 exit code

### Milestone 4（3~5 天）
- MCP server（或 tool adapter）
- 增加 observability（結構化 log、操作 trace id）

---

## 7) 可行性評級

- **技術可行性：高（8.5/10）**
- **落地成本：中（需要一次乾淨抽層）**
- **Agent 整合價值：高（可把 GUI 工具升級成可編排任務節點）**

> 總評：這個專案非常適合演進為 **「CLI-first + Agent Plugin-ready」** 的定位自動化工具。優先把 UI 耦合拆掉，就能快速接入各種 AI agent 生態。
