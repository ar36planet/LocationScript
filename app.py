import tkinter as tk
from tkinter import messagebox, simpledialog, filedialog
import subprocess
import re
import json
import os
import shutil
import urllib.request
import urllib.parse
import threading
import sys

# 偵測是否在 PyInstaller 打包的環境中執行
_FROZEN = getattr(sys, 'frozen', False)

# 取得 pymobiledevice3 路徑
if _FROZEN:
    # 打包後：pymobiledevice3 與主程式放在同一個 MacOS/ 目錄
    PYMOBILEDEVICE3 = os.path.join(os.path.dirname(sys.executable), "pymobiledevice3")
else:
    PYMOBILEDEVICE3 = shutil.which("pymobiledevice3") or os.path.expanduser("~/.local/bin/pymobiledevice3")

# 收藏檔案路徑
if _FROZEN:
    # 打包後：存放在 ~/Library/Application Support/iOS虛擬定位/
    SCRIPT_DIR = os.path.expanduser("~/Library/Application Support/iOS虛擬定位")
    os.makedirs(SCRIPT_DIR, exist_ok=True)
else:
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
FAVORITES_FILE = os.path.join(SCRIPT_DIR, "favorites.json")
HISTORY_DIR = os.path.join(SCRIPT_DIR, "history")

def save_to_history(lat, lng):
    from datetime import datetime
    os.makedirs(HISTORY_DIR, exist_ok=True)
    today = datetime.now().strftime("%Y%m%d")
    history_file = os.path.join(HISTORY_DIR, f"{today}.json")
    if os.path.exists(history_file):
        with open(history_file, "r", encoding="utf-8") as f:
            records = json.load(f)
    else:
        records = []
    records.append({
        "lat": lat,
        "lng": lng,
        "time": datetime.now().strftime("%H:%M:%S")
    })
    with open(history_file, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)

def load_favorites():
    if os.path.exists(FAVORITES_FILE):
        with open(FAVORITES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_favorites():
    with open(FAVORITES_FILE, "w", encoding="utf-8") as f:
        json.dump(favorites, f, ensure_ascii=False, indent=2)

def update_favorites_menu():
    fav_menu["menu"].delete(0, tk.END)
    fav_menu["menu"].add_command(label="-- 選擇收藏地點 --", command=lambda: fav_var.set(""))
    for name in favorites.keys():
        fav_menu["menu"].add_command(label=name, command=lambda n=name: select_favorite(n))

def select_favorite(name):
    if name not in favorites:
        return
    coords = favorites[name]
    lat_entry.delete(0, tk.END)
    lat_entry.insert(0, coords["lat"])
    lng_entry.delete(0, tk.END)
    lng_entry.insert(0, coords["lng"])
    fav_var.set(name)
    status.config(text=f"✅ 已載入：{name}")

def add_favorite():
    lat = lat_entry.get().strip()
    lng = lng_entry.get().strip()
    if not lat or not lng:
        status.config(text="❌ 請先輸入經緯度")
        return
    
    name = simpledialog.askstring("新增收藏", "請輸入地點名稱：")
    if name:
        favorites[name] = {"lat": lat, "lng": lng}
        save_favorites()
        update_favorites_menu()
        status.config(text=f"✅ 已收藏：{name}")

def delete_favorite():
    name = fav_var.get()
    if name and name in favorites:
        if messagebox.askyesno("刪除收藏", f"確定要刪除「{name}」嗎？"):
            del favorites[name]
            save_favorites()
            update_favorites_menu()
            fav_var.set("")
            status.config(text=f"✅ 已刪除：{name}")
    else:
        status.config(text="❌ 請先選擇要刪除的地點")

def import_favorites():
    filepath = filedialog.askopenfilename(
        title="匯入最愛",
        initialdir=SCRIPT_DIR,
        filetypes=[("JSON 檔案", "*.json"), ("所有檔案", "*.*")]
    )
    if not filepath:
        return
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        imported = {}
        if isinstance(data, dict):
            for name, coords in data.items():
                if "lat" in coords and "lng" in coords:
                    imported[name] = {"lat": str(coords["lat"]), "lng": str(coords["lng"])}
        elif isinstance(data, list):
            for item in data:
                if "lat" in item and "lng" in item:
                    name = item.get("name", f"{item['lat']}, {item['lng']}")
                    imported[name] = {"lat": str(item["lat"]), "lng": str(item["lng"])}
        if not imported:
            status.config(text="❌ 找不到可匯入的地點")
            return
        if favorites:
            replace = messagebox.askyesnocancel(
                "匯入最愛",
                f"找到 {len(imported)} 筆地點。\n\n「是」覆蓋現有收藏，「否」合併（重複名稱以匯入為準）"
            )
            if replace is None:
                return
            if replace:
                favorites.clear()
        favorites.update(imported)
        save_favorites()
        update_favorites_menu()
        status.config(text=f"✅ 已匯入 {len(imported)} 筆地點")
    except Exception as e:
        status.config(text=f"❌ 匯入失敗：{str(e)[:50]}")

_tunnel_check_id = None
_tunnel_window_id = None

# 定位 keep-alive（防止 iOS 自動跳回真實位置）
_keepalive_lat: str = ""
_keepalive_lng: str = ""
_keepalive_id = None
_KEEPALIVE_MS = 10_000  # 每 10 秒重送一次定位指令

def check_tunnel_status():
    global _tunnel_check_id
    result = subprocess.run(["pgrep", "-f", "pymobiledevice3 remote tunneld"], capture_output=True, text=True)
    if result.stdout.strip():
        tunnel_status.config(text="🟢 Tunnel 運行中", fg="green")
    else:
        tunnel_status.config(text="🔴 Tunnel 未啟動", fg="red")
    _tunnel_check_id = root.after(2000, check_tunnel_status)

def start_tunnel():
    global _tunnel_window_id
    result = subprocess.run(["pgrep", "-f", "pymobiledevice3 remote tunneld"], capture_output=True, text=True)
    if result.stdout.strip():
        status.config(text="⚠️ tunneld 已在執行中，無需重複啟動")
        return
    script = '''
    tell application "Terminal"
        activate
        do script "sudo pymobiledevice3 remote tunneld"
        return id of window 1
    end tell
    '''
    result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    _tunnel_window_id = result.stdout.strip()
    status.config(text="✅ 已開啟 Terminal 執行 tunneld")

def stop_tunnel():
    global _tunnel_window_id
    result = subprocess.run(["pgrep", "-f", "pymobiledevice3 remote tunneld"], capture_output=True, text=True)
    if not result.stdout.strip():
        status.config(text="⚠️ 找不到運行中的 tunneld")
        _tunnel_window_id = None
        return
    script = """do shell script "pkill -9 -f 'pymobiledevice3 remote tunneld'" with administrator privileges"""
    subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    _tunnel_window_id = None
    # 用 pgrep 確認程序是否真的消失（osascript exit code 不可靠）
    check = subprocess.run(["pgrep", "-f", "pymobiledevice3 remote tunneld"], capture_output=True, text=True)
    if not check.stdout.strip():
        status.config(text="✅ 已停止 tunneld")
    else:
        status.config(text="❌ 停止失敗（可能已取消授權）")

def parse_google_url():
    url = url_entry.get().strip()
    
    match = re.search(r'!3d([-\d.]+)!4d([-\d.]+)', url)
    if match:
        lat_entry.delete(0, tk.END)
        lat_entry.insert(0, match.group(1))
        lng_entry.delete(0, tk.END)
        lng_entry.insert(0, match.group(2))
        status.config(text="✅ 已解析地點座標")
        return
    
    match = re.search(r'@([-\d.]+),([-\d.]+)', url)
    if match:
        lat_entry.delete(0, tk.END)
        lat_entry.insert(0, match.group(1))
        lng_entry.delete(0, tk.END)
        lng_entry.insert(0, match.group(2))
        status.config(text="✅ 已解析地圖中心座標")
        return
    
    status.config(text="❌ 無法解析網址")

def parse_coords():
    text = coords_entry.get().strip()
    match = re.match(r'^([-\d.]+)[,\s]+([-\d.]+)$', text)
    if match:
        lat_entry.delete(0, tk.END)
        lat_entry.insert(0, match.group(1))
        lng_entry.delete(0, tk.END)
        lng_entry.insert(0, match.group(2))
        status.config(text="✅ 已解析座標")
    else:
        status.config(text="❌ 格式錯誤，請輸入如：25.112233,123.123123")

def _keepalive_tick():
    global _keepalive_id
    if not _keepalive_lat or not _keepalive_lng:
        return
    def run():
        try:
            proc = subprocess.Popen(
                [PYMOBILEDEVICE3, "developer", "dvt", "simulate-location", "set", "--",
                 _keepalive_lat, _keepalive_lng],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
        except Exception:
            pass
    threading.Thread(target=run, daemon=True).start()
    _keepalive_id = root.after(_KEEPALIVE_MS, _keepalive_tick)

def _start_keepalive(lat: str, lng: str):
    global _keepalive_lat, _keepalive_lng, _keepalive_id
    _keepalive_lat = lat
    _keepalive_lng = lng
    if _keepalive_id is not None:
        root.after_cancel(_keepalive_id)
    _keepalive_id = root.after(_KEEPALIVE_MS, _keepalive_tick)

def _stop_keepalive():
    global _keepalive_lat, _keepalive_lng, _keepalive_id
    _keepalive_lat = ""
    _keepalive_lng = ""
    if _keepalive_id is not None:
        root.after_cancel(_keepalive_id)
        _keepalive_id = None

def set_location_direct(lat: str, lng: str, save_history: bool = True, _fetch_name: bool = True):
    """直接以參數設定位置，可從任意執行緒安全呼叫。"""
    try:
        lat_f = float(lat)
        lng_f = float(lng)
    except ValueError:
        root.after(0, lambda: status.config(text="❌ 經緯度格式錯誤"))
        return

    if not (-90 <= lat_f <= 90):
        root.after(0, lambda: status.config(text="❌ 緯度範圍錯誤（需介於 -90 ~ 90）"))
        return
    if not (-180 <= lng_f <= 180):
        root.after(0, lambda: status.config(text="❌ 經度範圍錯誤（需介於 -180 ~ 180）"))
        return

    def run_set():
        try:
            proc = subprocess.Popen(
                [PYMOBILEDEVICE3, "developer", "dvt", "simulate-location", "set", "--", lat, lng],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
        except Exception:
            pass
    threading.Thread(target=run_set, daemon=True).start()
    if save_history:
        save_to_history(lat, lng)

    def update_ui():
        lat_entry.delete(0, tk.END)
        lat_entry.insert(0, lat)
        lng_entry.delete(0, tk.END)
        lng_entry.insert(0, lng)
        status.config(text=f"✅ 已設定：{lat}, {lng}")
        location_name_label.config(text="")
        _start_keepalive(lat, lng)
    root.after(0, update_ui)

    def fetch_name():
        try:
            url = (
                f"https://nominatim.openstreetmap.org/reverse"
                f"?lat={urllib.parse.quote(lat)}&lon={urllib.parse.quote(lng)}"
                f"&format=json&accept-language=zh-TW"
            )
            req = urllib.request.Request(url, headers={"User-Agent": "iOS-LocationScript/1.0"})
            with urllib.request.urlopen(req, timeout=6) as resp:
                data = json.loads(resp.read())
            if "error" in data:
                root.after(0, lambda: location_name_label.config(text="⚠️ 座標查無地點（可能為海洋或荒地）", fg="orange"))
                return
            name = data.get("display_name", "")
            if name:
                root.after(0, lambda: location_name_label.config(text=name, fg="gray"))
        except Exception:
            pass
    if _fetch_name:
        threading.Thread(target=fetch_name, daemon=True).start()

def set_location():
    lat = lat_entry.get().strip()
    lng = lng_entry.get().strip()
    if not lat or not lng:
        status.config(text="❌ 請輸入經緯度")
        return
    set_location_direct(lat, lng)

def clear_location():
    _stop_keepalive()
    result = subprocess.run(
        [PYMOBILEDEVICE3, "developer", "dvt", "simulate-location", "clear"],
        capture_output=True, text=True
    )
    if result.returncode == 0:
        status.config(text="✅ 已清除")
    else:
        status.config(text=f"❌ {result.stderr[:50]}")

def on_closing():
    global _tunnel_check_id
    if _tunnel_check_id is not None:
        root.after_cancel(_tunnel_check_id)
        _tunnel_check_id = None
    _stop_keepalive()
    if patrol_controller and patrol_controller.is_running:
        patrol_controller.stop()
    result = subprocess.run(["pgrep", "-f", "pymobiledevice3 remote tunneld"], capture_output=True, text=True)
    if result.stdout.strip():
        if messagebox.askyesno("結束", "要同時停止 tunneld 嗎？"):
            stop_tunnel()
    root.destroy()

# 座標清單資料
coord_list_items: list = []
coord_listbox: tk.Listbox
list_count_label: tk.Label
location_name_label: tk.Label

# 巡邏控制器全域單例
patrol_controller = None
_list_editor_win = None

def refresh_main_listbox():
    """根據 coord_list_items 重新渲染右側 Listbox 和筆數標籤。"""
    coord_listbox.delete(0, tk.END)
    for item in coord_list_items:
        coord_listbox.insert(tk.END, item["name"])
    list_count_label.config(text=f"共 {len(coord_list_items)} 筆")

def load_coord_list():
    initial = HISTORY_DIR if os.path.isdir(HISTORY_DIR) else SCRIPT_DIR
    filepath = filedialog.askopenfilename(
        title="選擇座標清單",
        initialdir=initial,
        filetypes=[("JSON 檔案", "*.json"), ("所有檔案", "*.*")]
    )
    if not filepath:
        return
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        coord_list_items.clear()
        coord_listbox.delete(0, tk.END)
        if isinstance(data, list):
            for item in data:
                if "lat" in item and "lng" in item:
                    name = item.get("name", f"{item['lat']}, {item['lng']}")
                    coord_list_items.append({"name": name, "lat": str(item["lat"]), "lng": str(item["lng"]), "dwell": int(item.get("dwell", 60))})
                    coord_listbox.insert(tk.END, name)
        elif isinstance(data, dict):
            for name, coords in data.items():
                if "lat" in coords and "lng" in coords:
                    coord_list_items.append({"name": name, "lat": str(coords["lat"]), "lng": str(coords["lng"]), "dwell": int(coords.get("dwell", 60))})
                    coord_listbox.insert(tk.END, name)
        list_count_label.config(text=f"共 {len(coord_list_items)} 筆")
        status.config(text=f"✅ 已載入 {len(coord_list_items)} 筆座標")
    except Exception as e:
        status.config(text=f"❌ 載入失敗：{str(e)[:50]}")

def clear_coord_list():
    if patrol_controller and patrol_controller.is_running:
        status.config(text="❌ 巡邏中，請先停止再清除清單")
        return
    coord_list_items.clear()
    coord_listbox.delete(0, tk.END)
    list_count_label.config(text="")
    status.config(text="✅ 已清除清單")

def on_coord_list_select(event):
    if patrol_controller and patrol_controller.is_running:
        return  # 巡邏中禁止手動選取，避免鍵盤誤觸打斷行程
    selection = coord_listbox.curselection()
    if not selection:
        return
    item = coord_list_items[selection[0]]
    lat_entry.delete(0, tk.END)
    lat_entry.insert(0, item["lat"])
    lng_entry.delete(0, tk.END)
    lng_entry.insert(0, item["lng"])
    set_location()

def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """回傳兩座標間的距離（公尺）。"""
    import math
    R = 6_371_000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))

# ── 巡邏控制器 ──────────────────────────────────────────────────────────────

class PatrolController:
    """控制自動巡邏執行緒的生命週期（暫停/繼續/停止）。"""

    def __init__(self):
        self._stop_event = threading.Event()
        self._pause_event = threading.Event()
        self._pause_event.set()  # 預設不暫停
        self._thread = None
        self.is_running = False
        self.on_tick = None     # callable(idx, name, remaining_secs)
        self.on_travel = None   # callable(idx_to, name_to, remaining_m)
        self.on_finish = None   # callable() 走完一輪且不循環時呼叫
        self._speed_kmh = 0.0
        self._mode = 'loop'  # 'loop' | 'once' | 'pingpong'

    def start(self, items, start_idx=0, speed_kmh=0.0, mode='loop'):
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._pause_event.set()
        self._speed_kmh = max(0.0, float(speed_kmh))
        self._mode = mode  # 'loop' | 'once' | 'pingpong'
        self.is_running = True
        self._thread = threading.Thread(
            target=self._run_loop,
            args=(list(items), start_idx),
            daemon=True
        )
        self._thread.start()

    def pause(self):
        self._pause_event.clear()

    def resume(self):
        self._pause_event.set()

    def stop(self):
        self._stop_event.set()
        self._pause_event.set()  # 解除可能的暫停阻塞
        self.is_running = False

    def _run_loop(self, items, start_idx):
        import time
        if not items:
            self.is_running = False
            return
        idx = start_idx
        direction = 1  # 1=正向, -1=反向（pingpong 用）
        prev_lat = prev_lng = None
        while not self._stop_event.is_set():
            if idx >= len(items):
                idx = 0  # loop mode reset（安全保護）
            if idx < 0:
                idx = 0
            item = items[idx]
            try:
                target_lat = float(item["lat"])
                target_lng = float(item["lng"])
            except (ValueError, KeyError):
                idx += 1
                continue
            # 模擬移動（有前一點且速度 > 0）
            if prev_lat is not None and self._speed_kmh > 0:
                if not self._travel_between(prev_lat, prev_lng, target_lat, target_lng, idx, item["name"]):
                    break
            else:
                set_location_direct(item["lat"], item["lng"], save_history=False, _fetch_name=False)
            if self._stop_event.is_set():
                break
            prev_lat, prev_lng = target_lat, target_lng
            # 停留倒數
            dwell = max(1, int(item.get("dwell", 60)))
            for remaining in range(dwell, 0, -1):
                if self._stop_event.is_set():
                    break
                self._pause_event.wait()
                if self._stop_event.is_set():
                    break
                if self.on_tick:
                    try:
                        self.on_tick(idx, item["name"], remaining)
                    except Exception:
                        pass
                for _ in range(10):
                    if self._stop_event.is_set():
                        break
                    time.sleep(0.1)
                if self._stop_event.is_set():
                    break
            if self._stop_event.is_set():
                break
            idx += direction
            if self._mode == 'pingpong':
                if idx >= len(items):
                    direction = -1
                    idx = max(0, len(items) - 2)
                elif idx < 0:
                    direction = 1
                    idx = min(len(items) - 1, 1)
            elif self._mode == 'once' and idx >= len(items):
                break  # 走完一輪停止
        self.is_running = False
        if not self._stop_event.is_set() and self.on_finish:
            try:
                self.on_finish()
            except Exception:
                pass

    def _travel_between(self, lat1, lng1, lat2, lng2, idx_to, name_to) -> bool:
        """從 (lat1,lng1) 以 self._speed_kmh 模擬移動至 (lat2,lng2)。
        回傳 True 表示正常抵達，False 表示中途停止。"""
        import time
        dist_m = _haversine(lat1, lng1, lat2, lng2)
        if dist_m < 5:
            set_location_direct(str(lat2), str(lng2), save_history=False, _fetch_name=False)
            return True
        speed_mps = self._speed_kmh * 1000 / 3600
        STEP_S = 5  # 每 5 秒送一次定位指令
        n_steps = max(1, round(dist_m / (speed_mps * STEP_S)))
        for step in range(1, n_steps + 1):
            if self._stop_event.is_set():
                return False
            self._pause_event.wait()
            if self._stop_event.is_set():
                return False
            t = step / n_steps
            lat = lat1 + (lat2 - lat1) * t
            lng = lng1 + (lng2 - lng1) * t
            set_location_direct(str(lat), str(lng), save_history=False, _fetch_name=False)
            if self.on_travel:
                try:
                    self.on_travel(idx_to, name_to, dist_m * (1 - t))
                except Exception:
                    pass
            for _ in range(STEP_S * 10):  # 0.1s × (STEP_S×10) = STEP_S 秒
                if self._stop_event.is_set():
                    return False
                time.sleep(0.1)
        return True

# ── 清單編輯器視窗 ───────────────────────────────────────────────────────────

class ListEditorWindow:
    """另開 Toplevel 視窗，提供多行座標輸入與解析，套用後可在主視窗清單面板巡邏。"""

    def __init__(self):
        self._items: list = []  # 本地解析結果 [{name, lat, lng, dwell}, ...]

        self.win = tk.Toplevel(root)
        self.win.title("清單編輯器")
        self.win.geometry("620x440")
        self.win.resizable(True, True)
        self.win.protocol("WM_DELETE_WINDOW", self.win.destroy)

        self._build_ui()

    # ── UI 建構 ──────────────────────────────────────────────────────────────

    def _build_ui(self):
        outer = tk.Frame(self.win, padx=12, pady=10)
        outer.pack(fill=tk.BOTH, expand=True)

        # 上：輸入區
        input_lf = tk.LabelFrame(outer, text="輸入座標（每行一筆）", padx=8, pady=8)
        input_lf.pack(fill=tk.BOTH, expand=True)

        hint_text = (
            "格式（每行一筆，# 開頭為註解）：\n"
            "  緯度,經度          →  25.033,121.565\n"
            "  緯度 經度          →  25.040 121.570\n"
            "  名稱 緯度 經度     →  台北車站 25.047924 121.517081"
        )
        tk.Label(input_lf, text=hint_text, fg="gray", font=("Menlo", 10), justify="left").pack(anchor="w", pady=(0, 4))

        text_frame = tk.Frame(input_lf)
        text_frame.pack(fill=tk.BOTH, expand=True)
        vsb = tk.Scrollbar(text_frame)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        self.text_input = tk.Text(text_frame, height=8, yscrollcommand=vsb.set, font=("Menlo", 12))
        self.text_input.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.config(command=self.text_input.yview)

        ctrl_row = tk.Frame(input_lf)
        ctrl_row.pack(fill=tk.X, pady=(6, 0))
        tk.Label(ctrl_row, text="預設停留秒數：").pack(side=tk.LEFT)
        self.dwell_entry = tk.Entry(ctrl_row, width=6)
        self.dwell_entry.insert(0, "60")
        self.dwell_entry.pack(side=tk.LEFT)
        tk.Button(ctrl_row, text="✅ 解析並載入", command=self._parse_and_load).pack(side=tk.LEFT, padx=10)

        # 下：結果清單
        result_lf = tk.LabelFrame(outer, text="解析結果", padx=8, pady=8)
        result_lf.pack(fill=tk.BOTH, expand=True, pady=(8, 0))

        list_top = tk.Frame(result_lf)
        list_top.pack(fill=tk.X)
        self.count_label = tk.Label(list_top, text="共 0 筆", fg="gray")
        self.count_label.pack(side=tk.LEFT)
        tk.Button(list_top, text="✅ 套用到主視窗", command=self._apply_to_main).pack(side=tk.RIGHT)
        tk.Button(list_top, text="💾 儲存 JSON", command=self._save_json).pack(side=tk.RIGHT, padx=4)

        lb_frame = tk.Frame(result_lf)
        lb_frame.pack(fill=tk.BOTH, expand=True, pady=(4, 0))
        lb_sb = tk.Scrollbar(lb_frame)
        lb_sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.result_lb = tk.Listbox(lb_frame, yscrollcommand=lb_sb.set, height=5, font=("Menlo", 12))
        self.result_lb.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        lb_sb.config(command=self.result_lb.yview)
        self.result_lb.bind("<<ListboxSelect>>", self._on_lb_select)

    # ── 帶入現有清單 ─────────────────────────────────────────────────────────

    def load_from_items(self, items: list):
        """以主視窗現有清單預填文字輸入區並觸發解析。"""
        if not items:
            return
        lines = []
        for it in items:
            name = it.get("name", "")
            lat = it.get("lat", "")
            lng = it.get("lng", "")
            # 若 name 只是預設的座標字串，改用 lat,lng 格式
            if name and name != f"{lat}, {lng}":
                lines.append(f"{name} {lat} {lng}")
            else:
                lines.append(f"{lat},{lng}")
        self.text_input.delete("1.0", tk.END)
        self.text_input.insert("1.0", "\n".join(lines))
        # 以第一筆的 dwell 作為預設停留秒數
        self.dwell_entry.delete(0, tk.END)
        self.dwell_entry.insert(0, str(items[0].get("dwell", 60)))
        self._parse_and_load()

    # ── 座標解析 ─────────────────────────────────────────────────────────────

    def _parse_lines(self, text: str, default_dwell: int) -> list:
        items = []
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            m = re.match(r'^([-\d.]+)\s*,\s*([-\d.]+)$', line)
            if m:
                lat, lng = m.group(1), m.group(2)
                items.append({"name": f"{lat}, {lng}", "lat": lat, "lng": lng, "dwell": default_dwell})
                continue
            parts = line.split()
            if len(parts) >= 2:
                try:
                    lng = parts[-1]
                    lat = parts[-2]
                    float(lat)
                    float(lng)
                    name = " ".join(parts[:-2]) if len(parts) > 2 else f"{lat}, {lng}"
                    items.append({"name": name, "lat": lat, "lng": lng, "dwell": default_dwell})
                except ValueError:
                    pass
        return items

    def _parse_and_load(self):
        try:
            default_dwell = max(1, int(self.dwell_entry.get().strip()))
        except ValueError:
            default_dwell = 60
        text = self.text_input.get("1.0", tk.END)
        self._items = self._parse_lines(text, default_dwell)
        self.result_lb.delete(0, tk.END)
        for item in self._items:
            self.result_lb.insert(tk.END, f"{item['name']}  ({item['dwell']}s)")
        self.count_label.config(text=f"共 {len(self._items)} 筆")

    # ── 互動動作 ─────────────────────────────────────────────────────────────

    def _on_lb_select(self, _event):
        sel = self.result_lb.curselection()
        if not sel:
            return
        item = self._items[sel[0]]
        set_location_direct(item["lat"], item["lng"])

    def _apply_to_main(self):
        coord_list_items.clear()
        coord_list_items.extend(self._items)
        refresh_main_listbox()
        status.config(text=f"✅ 已套用 {len(coord_list_items)} 筆到主視窗")

    def _save_json(self):
        if not self._items:
            messagebox.showwarning("清單為空", "請先解析座標", parent=self.win)
            return
        filepath = filedialog.asksaveasfilename(
            title="儲存座標清單",
            defaultextension=".json",
            filetypes=[("JSON 檔案", "*.json")],
            parent=self.win
        )
        if not filepath:
            return
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(self._items, f, ensure_ascii=False, indent=2)
            messagebox.showinfo("儲存成功", f"已儲存 {len(self._items)} 筆", parent=self.win)
        except Exception as e:
            messagebox.showerror("儲存失敗", str(e), parent=self.win)

# ── 主視窗巡邏控制函式 ───────────────────────────────────────────────────────

# 巡邏相關全域 UI 元件（在主視窗建立後賦值）
btn_main_patrol_start: tk.Button
btn_main_patrol_pause: tk.Button
btn_main_patrol_stop: tk.Button
patrol_status_label: tk.Label
patrol_speed_entry: tk.Entry
patrol_mode_var: tk.StringVar

def on_patrol_finish():
    def update():
        btn_main_patrol_start.config(state=tk.NORMAL)
        btn_main_patrol_pause.config(state=tk.DISABLED, text="⏸ 暫停")
        btn_main_patrol_stop.config(state=tk.DISABLED)
        patrol_status_label.config(text="✅ 巡邏完成")
    root.after(0, update)

def main_patrol_travel(idx_to, name_to, remaining_m):
    def update():
        dist_str = f"{remaining_m/1000:.1f}km" if remaining_m >= 1000 else f"{remaining_m:.0f}m"
        patrol_status_label.config(text=f"🚶 → {name_to}  {dist_str}")
        coord_listbox.selection_clear(0, tk.END)
        coord_listbox.selection_set(idx_to)
        coord_listbox.see(idx_to)
    root.after(0, update)

def main_patrol_tick(idx, name, remaining):
    def update():
        total = len(coord_list_items)
        patrol_status_label.config(text=f"[{idx+1}/{total}] {name}  {remaining}s")
        coord_listbox.selection_clear(0, tk.END)
        coord_listbox.selection_set(idx)
        coord_listbox.see(idx)
    root.after(0, update)

def start_main_patrol():
    global patrol_controller
    if not coord_list_items:
        status.config(text="❌ 清單為空，請先載入或套用座標")
        return
    if patrol_controller is None:
        patrol_controller = PatrolController()
    sel = coord_listbox.curselection()
    start_idx = sel[0] if sel else 0
    try:
        speed = max(0.0, float(patrol_speed_entry.get().strip()))
    except ValueError:
        speed = 20.0
    patrol_controller.on_tick = main_patrol_tick
    patrol_controller.on_travel = main_patrol_travel
    patrol_controller.on_finish = on_patrol_finish
    patrol_controller.start(coord_list_items, start_idx, speed_kmh=speed, mode=patrol_mode_var.get())
    btn_main_patrol_start.config(state=tk.DISABLED)
    btn_main_patrol_pause.config(state=tk.NORMAL, text="⏸ 暫停")
    btn_main_patrol_stop.config(state=tk.NORMAL)
    patrol_status_label.config(text="巡邏中...")

def pause_main_patrol():
    if not patrol_controller:
        return
    if btn_main_patrol_pause.cget("text") == "⏸ 暫停":
        patrol_controller.pause()
        btn_main_patrol_pause.config(text="▶ 繼續")
        patrol_status_label.config(text="已暫停")
    else:
        patrol_controller.resume()
        btn_main_patrol_pause.config(text="⏸ 暫停")

def stop_main_patrol():
    if patrol_controller:
        patrol_controller.stop()
    btn_main_patrol_start.config(state=tk.NORMAL)
    btn_main_patrol_pause.config(state=tk.DISABLED, text="⏸ 暫停")
    btn_main_patrol_stop.config(state=tk.DISABLED)
    patrol_status_label.config(text="")

# ── 開啟清單編輯器（單例） ───────────────────────────────────────────────────

def open_list_editor():
    global _list_editor_win
    if _list_editor_win is not None:
        try:
            if _list_editor_win.win.winfo_exists():
                _list_editor_win.win.lift()
                _list_editor_win.win.focus_force()
                return
        except Exception:
            pass
    _list_editor_win = ListEditorWindow()
    if coord_list_items:
        _list_editor_win.load_from_items(coord_list_items)

# 載入收藏
favorites = load_favorites()

# 主視窗
root = tk.Tk()
root.title("iOS 虛擬定位")
root.geometry("1080x540")
root.protocol("WM_DELETE_WINDOW", on_closing)

frame = tk.Frame(root, padx=20, pady=15)
frame.pack(fill=tk.BOTH, expand=True)

# Tunnel 狀態列
status_frame = tk.Frame(frame)
status_frame.grid(row=0, column=0, columnspan=4, sticky="ew", pady=(0, 10))
tunnel_status = tk.Label(status_frame, text="🔴 Tunnel 未啟動", fg="red", font=("", 12, "bold"))
tunnel_status.pack(side=tk.LEFT)

# Tunnel 控制
tunnel_frame = tk.LabelFrame(frame, text="Tunnel 控制（iOS 17+ 需要）", padx=10, pady=10)
tunnel_frame.grid(row=1, column=0, columnspan=4, sticky="ew", pady=(0, 10))
tk.Button(tunnel_frame, text="🚀 啟動", command=start_tunnel).pack(side=tk.LEFT, padx=5)
tk.Button(tunnel_frame, text="⏹️ 停止", command=stop_tunnel).pack(side=tk.LEFT)

# 收藏地點
fav_frame = tk.LabelFrame(frame, text="收藏地點", padx=10, pady=10)
fav_frame.grid(row=2, column=0, columnspan=4, sticky="ew", pady=(0, 10))

fav_var = tk.StringVar(value="")
fav_menu = tk.OptionMenu(fav_frame, fav_var, "-- 選擇收藏地點 --")
fav_menu.config(width=25)
fav_menu.pack(side=tk.LEFT)

tk.Button(fav_frame, text="⭐ 收藏", command=add_favorite).pack(side=tk.LEFT, padx=5)
tk.Button(fav_frame, text="🗑️ 刪除", command=delete_favorite).pack(side=tk.LEFT)
tk.Button(fav_frame, text="📥 匯入", command=import_favorites).pack(side=tk.LEFT, padx=5)

update_favorites_menu()

# 座標清單（右側欄）
list_frame = tk.LabelFrame(frame, text="座標清單", padx=10, pady=10)
list_frame.grid(row=0, column=5, rowspan=9, sticky="nsew", padx=(20, 0))

list_top = tk.Frame(list_frame)
list_top.pack(fill=tk.X, pady=(0, 5))
tk.Button(list_top, text="📂 載入清單", command=load_coord_list).pack(side=tk.LEFT)
tk.Button(list_top, text="✏️ 編輯清單", command=open_list_editor).pack(side=tk.LEFT, padx=4)
tk.Button(list_top, text="🗑️ 清除", command=clear_coord_list).pack(side=tk.LEFT)
list_count_label = tk.Label(list_top, text="")
list_count_label.pack(side=tk.LEFT, padx=8)

list_scroll_frame = tk.Frame(list_frame)
list_scroll_frame.pack(fill=tk.BOTH, expand=True)
scrollbar = tk.Scrollbar(list_scroll_frame)
scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
coord_listbox = tk.Listbox(list_scroll_frame, yscrollcommand=scrollbar.set, width=28, height=13, selectmode=tk.SINGLE)
coord_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
scrollbar.config(command=coord_listbox.yview)
coord_listbox.bind("<<ListboxSelect>>", on_coord_list_select)

# 巡邏控制列
patrol_ctrl_frame = tk.Frame(list_frame)
patrol_ctrl_frame.pack(fill=tk.X, pady=(5, 0))
btn_main_patrol_start = tk.Button(patrol_ctrl_frame, text="▶ 巡邏", command=start_main_patrol, width=6)
btn_main_patrol_start.pack(side=tk.LEFT, padx=(0, 2))
btn_main_patrol_pause = tk.Button(patrol_ctrl_frame, text="⏸ 暫停", command=pause_main_patrol, state=tk.DISABLED, width=6)
btn_main_patrol_pause.pack(side=tk.LEFT, padx=2)
btn_main_patrol_stop = tk.Button(patrol_ctrl_frame, text="⏹ 停止", command=stop_main_patrol, state=tk.DISABLED, width=6)
btn_main_patrol_stop.pack(side=tk.LEFT, padx=2)
patrol_status_label = tk.Label(list_frame, text="", fg="gray", font=("", 9), anchor="w")
patrol_status_label.pack(fill=tk.X, pady=(2, 0))

speed_row = tk.Frame(list_frame)
speed_row.pack(fill=tk.X, pady=(2, 0))
tk.Label(speed_row, text="速度：", font=("", 9)).pack(side=tk.LEFT)
patrol_speed_entry = tk.Entry(speed_row, width=5, font=("", 9))
patrol_speed_entry.insert(0, "20")
patrol_speed_entry.pack(side=tk.LEFT)
tk.Label(speed_row, text="km/h（0＝直跳）", font=("", 9), fg="gray").pack(side=tk.LEFT, padx=(2, 0))
patrol_mode_var = tk.StringVar(value="loop")
tk.Radiobutton(speed_row, text="循環", variable=patrol_mode_var, value="loop", font=("", 9)).pack(side=tk.LEFT, padx=(6, 0))
tk.Radiobutton(speed_row, text="來回", variable=patrol_mode_var, value="pingpong", font=("", 9)).pack(side=tk.LEFT, padx=(2, 0))
tk.Radiobutton(speed_row, text="單次", variable=patrol_mode_var, value="once", font=("", 9)).pack(side=tk.LEFT, padx=(2, 0))

# Google Maps 網址
tk.Label(frame, text="Google Maps 網址：").grid(row=3, column=0, sticky="w")
url_entry = tk.Entry(frame, width=40)
url_entry.grid(row=3, column=1, columnspan=2)
tk.Button(frame, text="解析", command=parse_google_url).grid(row=3, column=3, padx=5)

# 座標字串
tk.Label(frame, text="座標字串：").grid(row=4, column=0, sticky="w")
coords_entry = tk.Entry(frame, width=40)
coords_entry.grid(row=4, column=1, columnspan=2)
tk.Button(frame, text="解析", command=parse_coords).grid(row=4, column=3, padx=5)

# 經緯度
tk.Label(frame, text="緯度：").grid(row=5, column=0, sticky="w", pady=10)
lat_entry = tk.Entry(frame, width=15)
lat_entry.grid(row=5, column=1, sticky="w")
lat_entry.insert(0, "25.0330")

tk.Label(frame, text="經度：").grid(row=5, column=2, sticky="e")
lng_entry = tk.Entry(frame, width=15)
lng_entry.grid(row=5, column=3, sticky="w")
lng_entry.insert(0, "121.5654")

# 按鈕
btn_frame = tk.Frame(frame)
btn_frame.grid(row=6, column=0, columnspan=4, pady=15)
tk.Button(btn_frame, text="📍 設定位置", command=set_location, width=12).pack(side=tk.LEFT, padx=5)
tk.Button(btn_frame, text="🔄 清除", command=clear_location, width=12).pack(side=tk.LEFT, padx=5)

# 狀態
status = tk.Label(frame, text="就緒 — iOS 16 以下可跳過 Tunnel")
status.grid(row=7, column=0, columnspan=4)

# 地點名稱
location_name_label = tk.Label(frame, text="", fg="gray", wraplength=380, justify="center")
location_name_label.grid(row=8, column=0, columnspan=4, pady=(0, 5))

# 啟動狀態檢查
check_tunnel_status()

root.mainloop()