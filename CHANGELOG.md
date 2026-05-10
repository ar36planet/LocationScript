# Changelog

## v3.3

### 新功能

- **GPX 匯入**：清單編輯器加入「📂 匯入 GPX」按鈕，可直接從 `.gpx` 檔案匯入路線座標。支援 `<trkpt>`、`<rtept>`、`<wpt>` 格式，相容 iAnyGo、Strava 等工具匯出的檔案。
- **命令列 GPX 轉換工具**（`gpx_to_route.py`）：可將 GPX 批次轉換為專案 JSON 格式，支援自訂停留秒數。
- **多裝置 Session 切換**：同時連接多台裝置（如 iPhone + iPad）時，裝置欄出現下拉選單。選擇後本次執行的定位指令發送至指定裝置，不寫入預設設定，關閉程式後自動還原。
- **版本更新檢查**：視窗右上角新增「🔄 檢查更新」按鈕，連線至 GitHub Releases API 查詢最新版本，有更新時可直接開啟下載頁面。



## v3.2

- 新增 MCP server 整合
- 新增 `ifly agent-setup` 指令（Gemini / Claude / Codex）
- 修正 move worker 異常
- 升級 pymobiledevice3 版本
- 修復 GUI 延遲問題

## v3.1

- 新增 `ifly install` 一鍵安裝指令
- 新增裝置狀態顯示
- 加入 GitHub Actions 自動發版流程

## v3.0

- 新增 CLI（`ifly`）
- 拆分 core service 層（location、tunnel、patrol）
- GUI 與 CLI 共用同一套 core，Tunnel 狀態互通

## v2.x

- 新增路線規劃功能（最佳路線、外圈巡邏、種果路線）
- 新增清單編輯器
- 巡邏速度插值移動
- 修復定位 process 無法正常關閉的問題
