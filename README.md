# iOS 虛擬定位工具

透過 `pymobiledevice3` 在 Mac 上模擬 iPhone 的 GPS 定位。

## 版本選擇

| 版本 | 適合對象 | 入口 |
|------|----------|------|
| **打包版**（.app） | 一般使用者，雙擊開啟 | `iOS虛擬定位.app` |
| **原始碼版** | 開發者，直接執行 Python | `python3 app.py` |
| **CLI**（ifly） | 自動化、腳本整合 | `ifly <指令>` |

---

## 系統需求

- macOS（Apple Silicon 或 Intel）
- iPhone 透過 USB 連接至 Mac
- iOS 17+ 需開啟**開發者模式**（設定 > 隱私權與安全性 > 開發者模式）

---

## 安裝

### 打包版 / 原始碼版

1. 開啟終端機（`Cmd + Space` 搜尋「終端機」）

2. 切換到資料夾目錄：

   ```bash
   cd /path/to/LocationScript
   ```

   也可輸入 `cd ` 後直接把資料夾拖進終端機視窗。

3. 執行安裝：

   ```bash
   chmod +x install.sh && ./install.sh
   ```

   安裝腳本會自動安裝以下依賴：Homebrew、Python 3、Tkinter、pipx、pymobiledevice3，並產生 **iOS虛擬定位.app**。

> 若無法啟動 .app，可改用 `python3 app.py` 直接執行。
>
> **更新原始碼後重新打包**：修改 `app.py` 後執行 `./build.sh`，不需重新執行 `install.sh`。若 spec 結構有大改，先清除舊的 build：
> ```bash
> rm -rf build dist && ./build.sh
> ```

---

### CLI（ifly）

從 [GitHub Releases](../../releases) 下載最新的 `ifly` binary，執行一次安裝指令：

```bash
./ifly install
```

安裝程式會自動完成：
1. 確認／安裝 `pymobiledevice3`（若未安裝，透過 pipx 自動安裝）
2. 將 `ifly` 複製到 `/usr/local/bin/ifly`
3. 建立 `/usr/local/bin/ifly-tunneld` 與 `ifly-tunneld-stop` wrapper
4. 設定 `/etc/sudoers.d/ifly`（免密碼啟動 / 停止 Tunnel）

完成後驗證設定：

```bash
ifly doctor
```

> **開發者（原始碼）**：執行 `bash setup.sh` 進行設定。

### AI Agent 整合（MCP）

安裝完成後，可選擇將 ifly 註冊為 MCP server，讓 AI 工具直接呼叫：

```bash
ifly agent-setup gemini    # Gemini CLI
ifly agent-setup claude    # Claude Code
ifly agent-setup codex     # OpenAI Codex
```

設定完成後，AI 工具啟動時會自動載入 ifly 的 16 個工具（定位、移動、Tunnel、收藏等），無需手動輸入指令。

---

## 使用方式

### 圖形介面（打包版 / 原始碼版）

#### 1. 連接 iPhone

用 USB 線連接 iPhone，並點選「信任此電腦」。

#### 2. 開啟程式

雙擊 **iOS虛擬定位.app**，或執行 `python3 app.py`。

#### 3. 啟動 Tunnel（iOS 17+ 必須）

點擊「啟動」按鈕。若已執行過 `ifly install`，Tunnel 會在背景靜默啟動；否則會開啟 Terminal 視窗要求輸入 sudo 密碼。

#### 4. 設定虛擬定位

支援六種輸入方式：

- **手動輸入**：直接填入緯度、經度欄位
- **Google Maps 網址**：貼上後點「解析」自動擷取座標
- **座標字串**：貼上 `緯度,經度` 格式後點「解析」
- **收藏地點**：從已收藏清單中選擇
- **座標清單**：載入 JSON 檔案，點選即前往
- **清單編輯器**：點「✏️ 編輯清單」批量輸入與管理

輸入完成後點「設定位置」。定位成功後會顯示對應地址；每 10 秒自動重送定位，防止 iOS 跳回真實位置。

#### 5. 清除虛擬定位

點「清除」按鈕。清除後需**重新開啟地圖 App** 才會恢復真實定位；若未恢復，可切換飛航模式後關閉。

---

### CLI（ifly）

#### 基本語法

```
ifly [--json] <群組> <動作> [選項]
```

加上 `--json` 可輸出機器可讀的 JSON（適合腳本整合）。

#### 指令總覽

**裝置管理**

```bash
ifly device list                        # 列出已連接的 iOS 裝置
ifly device select <UDID> --default     # 設為預設裝置（多台同時連接時必須）
```

> 只連一台時自動選擇，無需設定。多台同時連接時需指定預設裝置。換裝置後執行 `ifly tunnel restart`。

**安裝與診斷**

```bash
ifly install                            # 一鍵安裝（首次使用）
ifly doctor                             # 檢查 pymobiledevice3、Tunnel、sudo 權限
```

**Tunnel 管理**

```bash
ifly tunnel start                       # 背景啟動 Tunnel（需設定 NOPASSWD sudo）
ifly tunnel start --interactive         # 互動模式（手動輸入 sudo 密碼）
ifly tunnel start --wait                # 啟動並等待裝置就緒
ifly tunnel stop                        # 停止 Tunnel
ifly tunnel restart                     # 重啟 Tunnel（換裝置後使用）
ifly tunnel status                      # 查看 Tunnel 狀態
```

**定位控制**

```bash
ifly location set --lat 25.033 --lng 121.565   # 設定座標
ifly location set --name "台北101"              # 前往收藏地點
ifly location status                            # 查看目前虛擬定位狀態
ifly location clear                             # 清除虛擬定位
ifly location parse --coords "25.033,121.565"  # 解析座標字串並直接前往
ifly location parse --google-url "<URL>"       # 解析 Google Maps 網址並直接前往
```

**移動模擬**

```bash
ifly location move start --direction N --distance 1.5 --speed 5   # 向北移動 1.5km，時速 5km/h
ifly location move start --direction 45 --distance 2 --speed 10   # 方位角 45° 移動
ifly location move status                                          # 查看移動進度
ifly location move stop                                            # 停止移動
```

**收藏地點**

```bash
ifly favorites list                              # 列出所有收藏
ifly favorites add --name "台北101" --lat 25.033 --lng 121.565
ifly favorites delete --name "台北101"
ifly favorites import --file my_locations.json
```

#### 基本使用流程

```bash
# 啟動 Tunnel（背景，無需密碼）
ifly tunnel start

# 設定虛擬定位
ifly location set --lat 25.033 --lng 121.565

# 清除定位
ifly location clear

# 停止 Tunnel
ifly tunnel stop
```

> iPhone 第一次連線時需插 USB；Tunnel 建立後可切換為 WiFi 使用。

#### 腳本整合範例（JSON 模式）

```bash
# 解析座標後取得 lat/lng
ifly --json location parse --coords "25.033,121.565"

# 解析 Google Maps 網址
ifly --json location parse --google-url "<URL>"
```

---

## 清單編輯器（批量輸入座標）

點擊右側面板的「✏️ 編輯清單」開啟編輯器視窗：

1. 在文字框貼上多筆座標，每行一筆，支援以下格式：
   ```
   25.033,121.565
   25.040 121.570
   台北車站 25.047924 121.517081
   ```
   以 `#` 開頭的行視為註解。

2. 設定「預設停留秒數」（巡邏時每個地點的停留時間，預設 60 秒）

3. 點「✅ 解析並載入」確認解析結果

4. 點「✅ 套用到主視窗」或「💾 儲存 JSON」存成檔案

---

## 路線規劃

解析座標後，可用以下三種演算法自動排列巡邏順序。**速度欄**輸入巡邏時速（km/h），用於計算預估時間。

### 🌸 規劃最佳路線（種花模式）

適用於在有效時間內最大化經過的點數（如 Pokémon GO 種花）。

- 封閉循環，自動回起點
- 每個點以半徑 40 公尺為有效圓，路線經過即計入
- 5 分鐘內不可走重複路徑
- 算法：貪婪最近鄰 + 2-opt 改良，取覆蓋最多、距離最短者
- 建議巡邏模式：**循環**

### 🔄 外圈巡邏（種花模式）

沿所有點的外圍邊界繞行，形成大橢圓或圓角多邊形路線。

- 封閉循環，計算凸包後生成圓弧路線
- 安全半徑自動計算：`安全半徑 = √(40² − (最長相鄰間距 / 2)²)`
- 建議巡邏模式：**循環**

| 點數量 | 路線形狀 |
|--------|---------|
| 1 | 圓形 |
| 2 | 橢圓（體育場形）|
| 3 | 圓角三角形 |
| 4+ | 圓角多邊形 |

### 🍎 種果路線（種果模式）

以最短總距離單向依序經過所有座標。

- 開放單向，不回起點，無時間與交叉限制
- 建議巡邏模式：**單次**

---

## 自動巡邏

載入或套用座標清單後，右側面板下方會出現巡邏控制列：

- **▶ 巡邏**：從目前選取的地點開始，依序自動切換定位
- **⏸ 暫停 / ▶ 繼續**：暫停或繼續巡邏
- **⏹ 停止**：立即停止巡邏

**速度設定**：輸入移動時速（km/h）。設為 `0` 則瞬間跳點；大於 0 時以線性插值逐步移動，每 5 秒更新一次位置。

**巡邏模式**：

| 模式 | 行為 |
|------|------|
| 循環 | A → B → C → A → B → C … 無限重複 |
| 來回 | A → B → C → B → A … 無限來回，端點只停留一次 |
| 單次 | A → B → C 走完即停止 |

---

## 注意事項

- 首次執行 `.app` 時，macOS 可能提示「無法打開」，請到「系統設定 > 隱私權與安全性」允許執行
- 關閉程式時會詢問是否同時停止 Tunnel
- 座標清單支援兩種 JSON 格式：
  - 物件格式：`{"地點名稱": {"lat": "...", "lng": "..."}}`
  - 陣列格式：`[{"name": "地點名稱", "lat": "...", "lng": "...", "dwell": 60}]`
- 手動設定的定位紀錄會寫入歷史紀錄，巡邏切換不計入
- GUI（app.py）與 CLI 共用同一套 core service，**Tunnel 狀態互通**，兩者可混用

### CLI 定位行為補充

- `ifly location set` 會在背景維持一個 DVT session process，PID 記錄於 `~/.local/share/ifly/location.pid`
- `ifly location clear` 會同時 kill 該 process 並送出 clear 指令給裝置

### 三個版本的差異

| | 原始碼版（`python3 app.py`） | 打包版（.app） | CLI（ifly） |
|---|---|---|---|
| 收藏地點 (`favorites.json`) | 專案資料夾內 | `~/Library/Application Support/iOS虛擬定位/` | `~/Library/Application Support/iOS虛擬定位/`（與打包版共用）|
| 歷史紀錄 (`history/`) | 專案資料夾內 | `~/Library/Application Support/iOS虛擬定位/history/` | — |
| 重新打包 | 不需要 | 修改後執行 `./build.sh` | 不需要 |
| 圖形介面 | 有 | 有 | 無 |
| 腳本整合 | 不適合 | 不適合 | 適合（支援 `--json`）|
