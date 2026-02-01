# iOS 虛擬定位工具

透過 `pymobiledevice3` 在 Mac 上模擬 iPhone 的 GPS 定位。

## 系統需求

- macOS（Apple Silicon 或 Intel）
- iPhone 透過 USB 連接至 Mac
- iOS 17+ 需開啟**開發者模式**（設定 > 隱私權與安全性 > 開發者模式）

## 安裝步驟

### 1. 開啟終端機

按 `Cmd + Space` 搜尋「終端機」或「Terminal」並開啟。

### 2. 切換到資料夾目錄

```bash
cd /path/to/LocationScript
```

將 `/path/to/LocationScript` 替換為資料夾實際所在的路徑。也可以輸入 `cd ` 後直接把資料夾拖進終端機視窗。

### 3. 允許執行安裝腳本

```bash
chmod +x install.sh
```

### 4. 執行安裝

```bash
./install.sh
```

安裝腳本會自動檢查並安裝以下依賴：

- [Homebrew](https://brew.sh)
- Python 3
- Tkinter
- pipx
- pymobiledevice3

安裝完成後會在資料夾內產生 **iOS虛擬定位.app**。

## 使用方式

### 1. 連接 iPhone

用 USB 線將 iPhone 連接到 Mac，並在 iPhone 上點選「信任此電腦」。

### 2. 開啟程式

雙擊 **iOS虛擬定位.app** 啟動。

### 3. 啟動 Tunnel（iOS 17+ 必須）

點擊「啟動」按鈕，會開啟 Terminal 並要求輸入 Mac 的登入密碼（sudo 權限）。

### 4. 設定虛擬定位

有三種方式輸入座標：

- **手動輸入**：直接在緯度、經度欄位輸入座標
- **Google Maps 網址**：貼上 Google Maps 網址後點「解析」自動擷取座標
- **收藏地點**：從已收藏的地點中選擇

輸入完成後點擊「設定位置」即可。

### 5. 清除虛擬定位

點擊「清除」按鈕。清除後需**重新開啟地圖 App** 才會恢復真實定位。

## 注意事項

- 首次執行 `.app` 時，macOS 可能會提示「無法打開」，請到「系統設定 > 隱私權與安全性」允許執行
- 關閉程式時會詢問是否同時停止 Tunnel
- 收藏的地點會儲存在資料夾內的 `favorites.json`
