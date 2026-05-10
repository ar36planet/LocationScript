# 世界時區查詢 計畫

## 功能目標

輸入一個時間範圍（如 00:00 ～ 02:00），查出**現在哪些地區的當地時間落在這個範圍內**，並可一鍵將定位套用到該地區。

---

## 使用情境

- 想定位到「現在是深夜」的地區
- 想找某個特定時段的地區測試 app 行為
- 確認某個地區現在幾點，順便直接設定定位

---

## 技術方案

### 資料來源
使用 Python 內建 `zoneinfo.available_timezones()`，取得所有 IANA 時區名稱（約 600 個）。  
不需要外部 API，完全離線，DST 自動處理。

### 時間計算
```python
from zoneinfo import ZoneInfo
from datetime import datetime

def local_time_in(tz_name: str) -> datetime:
    return datetime.now(ZoneInfo(tz_name))
```

### 座標取得（點選套用時）
使用 Nominatim 正向地理編碼，從時區名稱中解析城市名再查座標。  
例如：`America/New_York` → 查詢 `"New York"` → `(40.7128, -74.0060)`

時區名稱到城市名的轉換：
```python
# "America/New_York" → "New York"
# "Asia/Taipei"      → "Taipei"
city = tz_name.split("/")[-1].replace("_", " ")
```

大多數情況可行，少數例外（如 `US/Eastern`）退化到直接查時區名稱。

---

## UI 設計

### 入口
主視窗工具列加一個按鈕「🌍 世界時區」，點開獨立彈窗。

### 彈窗佈局
```
┌─────────────────────────────────────────┐
│  🌍 世界時區查詢                          │
├─────────────────────────────────────────┤
│  從 [00] : [00]  到 [02] : [00]  [查詢]  │
├─────────────────────────────────────────┤
│  找到 47 個時區                           │
│  ┌───────────────────────────────────┐   │
│  │ 城市 / 時區          現在時間      │   │
│  │ New York (EST)       01:23       │   │
│  │ Toronto              01:23       │   │
│  │ Lima                 01:23       │   │
│  │ ...                              │   │
│  └───────────────────────────────────┘   │
│                                          │
│         [套用定位]   [關閉]              │
└─────────────────────────────────────────┘
```

### 互動細節
- 結果清單按當地時間排序（最接近範圍中間值的排前面）
- 點選列表項目後「套用定位」才可按
- 「套用定位」觸發 Nominatim 查座標 → 呼叫 `location.set_location_direct()`
- 查座標期間按鈕顯示 loading 狀態

---

## 實作規劃

### 新增檔案
`world_clock.py` — 獨立的彈窗類別 `WorldClockWindow`

### 對外介面
```python
class WorldClockWindow:
    def __init__(self, parent: tk.Tk, location_fn: callable, on_status: callable)
    # location_fn = location.set_location_direct
    # on_status = lambda text: status.config(text=text)
```

### `world_clock.py` 內部結構
```
WorldClockWindow
├── _build_ui()          # 建立彈窗 widget
├── _search()            # 讀取時間範圍，篩選時區，更新列表
├── _fetch_coords(tz)    # Nominatim 查座標（背景 thread）
└── _apply()             # 套用定位
```

### `app.py` 改動
- 加一個「🌍 世界時區」按鈕（位置：工具列右側，或收藏地點旁）
- 按鈕 callback 開啟 `WorldClockWindow`，singleton（已開就 lift）

---

## 實作順序

1. `world_clock.py` — `_build_ui()` 骨架，彈窗可開關
2. `_search()` — 時間範圍篩選邏輯（先測試不含 UI）
3. 結果列表顯示（城市名 + 當地時間）
4. `_fetch_coords()` — Nominatim 正向查詢
5. `_apply()` — 呼叫 `location_fn`
6. `app.py` 接入入口按鈕
7. 邊界情況處理（Nominatim 查無結果、網路失敗）

---

## 邊界情況

| 情況 | 處理方式 |
|------|----------|
| Nominatim 查不到城市座標 | 顯示提示「無法取得此地區座標」，不套用 |
| 時間範圍跨午夜（如 23:00 ～ 01:00）| 支援，比較時處理跨日邏輯 |
| 時區名稱難以解析城市（如 `UTC`、`US/Eastern`）| 顯示原始時區名稱，套用時以時區名稱查詢 |
| 沒有裝置連接時套用 | 地址 / 時間照常顯示（已有機制），裝置錯誤顯示在主視窗狀態列 |

---

## 不做的事
- 不顯示地圖
- 不支援使用者自訂城市清單（用 `zoneinfo` 取代）
- 不做即時時鐘更新（每次查詢取當下時間，不自動刷新）
