# Pikmin 地圖座標校準工具 規格書

## 功能概述

一個獨立的桌面工具，讓使用者能從 iPhone 上的 Pikmin Bloom 地圖取得任意點的真實地理座標。
透過「花」作為校準錨點，建立像素與地理座標的對應關係，並在工具內顯示真實地圖供使用者規劃路線。

---

## 使用情境

- 使用者在 Mac 上開啟 iPhone 鏡像（Apple 原生鏡像或 QuickTime）
- Pikmin Bloom 地圖顯示在鏡像視窗中
- 工具視窗並排於鏡像視窗旁
- 使用者校準後可查詢座標、記錄目標點、在地圖上規劃路線

---

## 使用者流程

### 1. 啟動與視窗偵測

```
工具啟動
→ 自動偵測螢幕上的 iPhone 鏡像視窗（iPhone Mirroring / QuickTime）
→ 顯示偵測結果，讓使用者確認
→ 記錄鏡像視窗的螢幕絕對位置與尺寸
```

### 2. 校準（至少 2 個錨點）

```
使用者點擊工具上的「開始校準」
→ 進入校準模式

使用者在 Pikmin 地圖上點一朵花
→ 工具記錄：點擊的螢幕絕對座標 → 換算為相對於鏡像視窗的像素座標
→ 工具提示：「請跳出至 Google Maps，取得該點座標後貼回」

使用者在 Pikmin 點花 → Google Maps 開啟 → 長按取得座標 → 貼回工具輸入欄
→ 工具記錄：像素座標 ↔ 地理座標（錨點 #1 完成）

重複以上步驟（錨點 #2）
→ 兩錨點距離夠遠時，比例尺計算完成
→ 校準完成，進入追蹤模式
→ 工具地圖自動跳到校準區域
```

> 錨點選擇建議：選畫面上相距較遠的兩朵花，誤差較小。
> 花優於蘑菇：花為點狀物件，座標精度較高。

### 3. 即時座標顯示

```
校準完成後
→ 滑鼠在鏡像視窗上移動 → 工具視窗即時顯示對應經緯度
→ 滑鼠停留 0.5 秒 → 座標鎖定，顯示「已鎖定」
→ 滑鼠移開鏡像視窗 → 保持最後鎖定值
```

### 4. 地圖移動後修正漂移

```
使用者在 Pikmin 地圖上滑動（含慣性滑動）
→ 座標系可能產生偏移

修正方式：
→ 使用者點一朵花取得新座標（同校準步驟，只需 1 個點）
→ 工具以新錨點修正原點（比例尺不變）
```

> 不使用自動截圖比對追蹤，省去 opencv 相依。漂移靠手動點花修正即可。

### 5. 記錄座標

```
使用者將滑鼠移到鏡像視窗上的目標點
→ 停留 0.5 秒 → 座標鎖定
→ 使用者點工具視窗上的「記錄」按鈕
→ 該筆直接加入列表，不跳確認視窗
→ 新加入項目高亮 1 秒（讓使用者確認剛才記了什麼）
→ 若記錯，點列表旁的 [✕] 刪除
→ 點擊「記錄」後解除鎖定，恢復即時追蹤
```

> **工具視窗採 Non-activating Panel**：點按鈕不會搶走 iPhone 鏡像視窗的 focus，Pikmin 操作不中斷。
> **不使用全域熱鍵**：避免與系統或其他 App 衝突。

### 6. 地圖檢視與路線規劃

```
工具視窗下半部顯示 OSM 真實地圖（tkintermapview）
→ 記錄的點位自動在地圖上標記
→ 使用者可在地圖上點擊新增路線點
→ 多個路線點連成路線（polyline）
→ 路線可匯出為 LocationScript 相容格式，直接送進 patrol 執行
```

---

## 技術架構

```
┌─────────────────────────────────────────────┐
│               PikminCalibrator              │
│                                             │
│  WindowDetector   → 找鏡像視窗位置         │
│  MouseHook        → 監聽全域滑鼠事件       │
│  CoordMapper      → 像素 ↔ 經緯度換算      │
│  CalibrationMgr   → 管理錨點與校準狀態     │
│  MapView          → OSM 地圖顯示與路線編輯 │
│  UI               → CustomTkinter 工具視窗 │
└─────────────────────────────────────────────┘
```

---

## 套件清單

### 需要新安裝

| 套件 | 用途 | 大小 |
|------|------|------|
| `tkintermapview` | OSM 地圖 widget，支援標記與路線 | ~150KB |
| `requests` | tkintermapview 相依，下載地圖圖磚 | ~500KB |
| `Pillow` | tkintermapview 相依，圖磚圖像處理 | ~15MB |
| `pynput` | 全域滑鼠事件監聽 | ~1MB |
| `mss` | 截圖（靜止偵測備用） | ~500KB |

### 已有（不需新裝）

| 套件 | 用途 |
|------|------|
| `customtkinter` | UI 視窗框架 |
| `pyobjc` | 視窗偵測（pymobiledevice3 相依）|

### 刻意排除

| 套件 | 原因 |
|------|------|
| `opencv-python` (~60MB) + `numpy` (~20MB) | 只用於自動位移追蹤，改為手動修正，不值得引入 |

## 地圖圖資

- 來源：**OpenStreetMap（OSM）**，由 `tkintermapview` 自動下載
- 圖磚按需下載，看過的區域快取至本機 SQLite
- 離線可用已快取區域，首次需要網路
- Pikmin Bloom 底圖同樣基於 OSM，視覺一致，方便對照校準

---

## 核心模組說明

### WindowDetector
- 使用 `pyobjc` 的 `CGWindowListCopyWindowInfo` 掃描所有視窗
- 比對視窗名稱（「iPhone Mirroring」、「QuickTime Player」等）
- 回傳視窗的螢幕矩形 `(x, y, width, height)`

### MouseHook
- 使用 `pynput` 監聽全域滑鼠事件（需要 macOS Accessibility 權限）
- 事件類型：`move`、`click`、`drag_start`、`drag_end`
- 過濾只處理落在鏡像視窗範圍內的事件
- 計算相對座標：`rel_x = abs_x - window_x`

### CoordMapper
- 輸入：兩個錨點（像素座標、地理座標）
- 計算：
  - `pixels_per_deg_x = Δpx / Δlon`
  - `pixels_per_deg_y = Δpy / Δlat`
- 轉換：`lat = anchor_lat + (py - anchor_py) / pixels_per_deg_y`
- 支援單點原點更新（漂移修正，比例尺不變）

### CalibrationMgr
- 狀態機：`IDLE → CALIBRATING → READY`
- 管理錨點佇列（至少 2 個才能完成校準）
- 完成後呼叫 CoordMapper 建立映射

### MapView
- 使用 `tkintermapview` 嵌入工具視窗
- 顯示記錄的點位（marker）
- 支援點擊新增路線點、連線顯示（polyline）
- 校準完成後自動跳到對應區域

---

## 資料結構

```python
@dataclass
class Anchor:
    pixel: tuple[int, int]        # 相對於鏡像視窗的像素座標
    coord: tuple[float, float]    # (latitude, longitude)

@dataclass
class SavedPoint:
    coord: tuple[float, float]
    label: str = ""
    timestamp: str = ""

@dataclass
class Route:
    points: list[tuple[float, float]]  # 依序的經緯度列表
```

---

## UI 設計（工具視窗）

工具視窗為 **Non-activating Panel**（macOS NSPanel），永遠懸浮於頂層，點擊按鈕不會搶走 iPhone 鏡像視窗的 focus。

```
┌────────────────────────────────┐
│  Pikmin 座標校準工具            │
├────────────────────────────────┤
│  鏡像視窗：iPhone Mirroring ✓  │
├────────────────────────────────┤
│  [開始校準]  狀態：校準完成 ✓  │
│  錨點 #1：25.0456, 121.5123 ✓  │
│  錨點 #2：25.0490, 121.5201 ✓  │
├────────────────────────────────┤
│  目前座標（鎖定）：             │
│  25.0478° N, 121.5170° E       │
│  [記錄]  [修正漂移]            │
├────────────────────────────────┤
│  ┌──────────────────────────┐  │
│  │                          │  │
│  │     OSM 地圖             │  │
│  │     ● 標記點             │  │
│  │     ─ 路線               │  │
│  │                          │  │
│  └──────────────────────────┘  │
├────────────────────────────────┤
│  點位列表：                    │
│  ● 25.0480, 121.5168 [複製][✕] │
│  ● 25.0463, 121.5201 [複製][✕] │
│  [匯出 CSV]  [匯出路線]        │
└────────────────────────────────┘
```

### 座標顯示狀態

| 狀態 | 顯示行為 |
|------|----------|
| 滑鼠在鏡像視窗內移動 | 即時跟隨滑鼠更新 |
| 滑鼠停留 0.5 秒 | 鎖定，停止更新，提示「已鎖定」|
| 滑鼠移開鏡像視窗 | 保持最後鎖定值 |
| 點擊「記錄」後 | 解除鎖定，恢復即時追蹤 |

---

## 匯出格式

### CSV（點位列表）
```
latitude,longitude,label,timestamp
25.0480,121.5168,,2026-05-11T10:23:00
```

### 路線（LocationScript patrol 相容）
```json
[
  {"lat": 25.0480, "lng": 121.5168},
  {"lat": 25.0463, "lng": 121.5201}
]
```

---

## 限制與注意事項

| 項目 | 說明 |
|------|------|
| 地圖投影 | Pikmin Bloom 使用 Web Mercator，高緯度誤差略大，台灣地區可忽略 |
| 慣性漂移 | 大幅滑動後建議點花執行「修正漂移」 |
| 縮放變更 | 若使用者在 Pikmin 內改變縮放層級，比例尺失效，需重新校準 |
| 地圖需網路 | 首次載入各區域需要連線，已看過區域可離線使用 |

---

## 獨立性與串接

- 不依賴 LocationScript 主程式，可單獨執行：`python pikmin_calibrator.py`
- 匯出路線格式與 LocationScript patrol 功能相容，可直接送入執行
- 日後若有需要，可整合至主程式作為獨立頁籤

---

## 實作優先順序

1. `WindowDetector` — 偵測鏡像視窗
2. `MouseHook` — 監聽點擊與拖曳
3. `CalibrationMgr` + `CoordMapper` — 校準與座標換算
4. UI 基本框架（Non-activating Panel + 座標顯示）
5. `MapView` — OSM 地圖嵌入、標記點顯示
6. 路線編輯與匯出
