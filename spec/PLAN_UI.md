# UI 美化計畫

## 現況分析

### 框架
純 `tkinter`，使用系統預設樣式，在 macOS 上顯示為 Aqua 風格但缺乏一致性。

### 現有問題
- 字型、間距、顏色都依賴系統預設，沒有視覺層級
- 左欄（座標清單 + 巡邏）與右欄（輸入 + 按鈕）視覺重量不均衡
- 狀態列、地址、時間三個資訊塞在底部，資訊層級不清楚
- emoji 作為 icon 在不同系統渲染差異大
- 沒有深色模式支援

### 耦合現況
`core/` 完全無 UI 依賴，可直接保留。  
`location.py` 持有 tkinter widget 參考，換框架需改寫。  
`app.py` 是主要的 UI 定義，換框架等於重寫這個檔案。

---

## 框架選擇

### 方案 A：CustomTkinter（推薦）
- 圓角、深色/淺色模式、現代感，接近原生 macOS 設計語言
- API 與 tkinter 幾乎一對一（`CTkButton` 替換 `tk.Button` 等），遷移成本相對可控
- 需要 `pip install customtkinter`
- 缺點：部分複雜 widget（如 `Listbox`、`OptionMenu`）需要自己組合實作

### 方案 B：ttkbootstrap
- Bootstrap 風格主題，現成 theme 多
- 遷移成本最低，幾乎是 `import ttkbootstrap as ttk` 就有效果
- 缺點：視覺風格偏 Web，在 macOS 上稍顯突兀；深色模式支援較弱

### 結論
選 **CustomTkinter**，深色模式和 macOS 視覺相容性是主要原因。

---

## Stitch 草稿評估（2026-05-10）

使用 Stitch 產出三張草稿（Main Connected、Main Disconnected、World Timezone Popup）後進行審查。

### 保留
- **配色方向**：藍色主色（`#007AFF`）、白底、灰色次要文字，乾淨不誇張，符合工具定位
- **卡片分組方式**：Tunnel 控制、裝置各自一塊 card，視覺邊界清楚
- **按鈕樣式**：藍色主要動作、灰色次要動作的層級區分
- **世界時區彈窗**：城市名稱 + 時間對齊的列表呈現方式可直接參考
- **右側座標清單面板**比例與配置方向

### 捨棄
- **左側 Sidebar 導航**（Tunnel Control / Device / Favorites 三個分頁）：此工具所有操作在同一流程內，sidebar 增加操作層級、引入不必要的頁面切換概念，捨棄
- **地圖預覽圖**（Connected 狀態下座標輸入框下方的地景圖）：純裝飾、與工具定位不符，捨棄

### 佈局決策
維持現有**兩欄式**佈局，不引入 sidebar。左欄：輸入控制區，右欄：座標清單 + 巡邏控制。

---

## 設計方向

### 色彩系統
```
主色      #007AFF  (Apple System Blue，與 Stitch 草稿一致)
成功      #28C840  (綠)
警告      #FF9500  (橘)
錯誤      #FF3B30  (紅)
背景      #1C1C1E  (深色) / #F2F2F7  (淺色)
次要文字  #8E8E93
```

### 字型
macOS 使用系統字型 `SF Pro`（透過 `-apple-system` 等效替代），內文 13px，標題 15px bold。

### 間距規則
基本單位 4px，元件間距 8/16/24，區塊間距 16/24。

---

## 重構範圍

### 不動
- `core/` 全部
- `ifly.py`
- `patrol.py`、`storage.py`、`config.py` 等 backend

### 需改寫
| 檔案 | 工作量 | 說明 |
|------|--------|------|
| `app.py` | 大 | 主 UI 定義，全面替換 widget |
| `location.py` | 小 | widget 參考型別改為 CTk 對應型別 |
| `list_editor.py` | 中 | 獨立視窗，需同步更新 |
| `route_planner.py` | 中 | 獨立視窗，需同步更新 |

---

## 佈局調整

### 目前
```
[Tunnel 狀態列]
[裝置列]
[多裝置選單]
[收藏地點]
┌─────────────────┬──────────────────────┐
│  座標清單        │  Google Maps URL     │
│  巡邏控制        │  座標字串            │
│                 │  緯度 / 經度         │
│                 │  跨日警示 checkbox   │
│                 │  [設定] [清除] [還原] │
│                 │  狀態               │
│                 │  地址               │
│                 │  時間               │
└─────────────────┴──────────────────────┘
```

### 目標
- 左欄寬度固定，右欄 flex
- 狀態列整合成一個 toast 風格通知（不佔固定空間）
- 地址 + 時間改為 card 區塊，有背景色區隔
- 按鈕組改為 icon + 文字組合，視覺更清楚

---

## 實作順序

1. 安裝 CustomTkinter，確認環境與 build 流程相容（`PyInstaller` spec 需更新）
2. 建立 `ui/theme.py`，定義顏色常數與字型設定
3. `app.py` 骨架替換（main window、grid 結構）
4. 逐區塊替換 widget（Tunnel 列 → 裝置列 → 輸入區 → 按鈕 → 狀態）
5. `list_editor.py`、`route_planner.py` 同步更新
6. 深色 / 淺色模式切換（選單或自動跟隨系統）
7. `install.sh` 加入 `pip install customtkinter`

---

## 注意事項
- CustomTkinter 的 `CTkOptionMenu` 不支援動態 `add_command`，收藏地點下拉選單需改用 `CTkComboBox` 或自製
- PyInstaller 打包需要把 CustomTkinter 的資源目錄（字型、圖片）一起納入，spec 需調整 `datas`
- `install-cli.sh` 不受影響（CLI 不用 GUI 套件）
