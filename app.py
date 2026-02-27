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

_tunnel_check_id = None

def check_tunnel_status():
    global _tunnel_check_id
    result = subprocess.run(["pgrep", "-f", "pymobiledevice3 remote tunneld"], capture_output=True, text=True)
    if result.stdout.strip():
        tunnel_status.config(text="🟢 Tunnel 運行中", fg="green")
    else:
        tunnel_status.config(text="🔴 Tunnel 未啟動", fg="red")
    _tunnel_check_id = root.after(2000, check_tunnel_status)

def start_tunnel():
    script = '''
    tell application "Terminal"
        activate
        do script "sudo pymobiledevice3 remote tunneld"
    end tell
    '''
    subprocess.run(["osascript", "-e", script])
    status.config(text="✅ 已開啟 Terminal 執行 tunneld")

def stop_tunnel():
    result = subprocess.run(["pgrep", "-f", "pymobiledevice3 remote tunneld"], capture_output=True, text=True)
    pids = result.stdout.strip().split("\n")
    if pids and pids[0]:
        for pid in pids:
            try:
                subprocess.run(["kill", "-9", pid])
            except:
                pass
        status.config(text="✅ 已停止 tunneld")
    else:
        status.config(text="⚠️ 找不到運行中的 tunneld")

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

def set_location():
    lat = lat_entry.get().strip()
    lng = lng_entry.get().strip()
    
    if not lat or not lng:
        status.config(text="❌ 請輸入經緯度")
        return
    
    try:
        lat_f = float(lat)
        lng_f = float(lng)
    except ValueError:
        status.config(text="❌ 經緯度格式錯誤")
        return

    if not (-90 <= lat_f <= 90):
        status.config(text="❌ 緯度範圍錯誤（需介於 -90 ~ 90）")
        return
    if not (-180 <= lng_f <= 180):
        status.config(text="❌ 經度範圍錯誤（需介於 -180 ~ 180）")
        return
    
    def run_set():
        subprocess.run(
            [PYMOBILEDEVICE3, "developer", "dvt", "simulate-location", "set", "--", lat, lng],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
    threading.Thread(target=run_set, daemon=True).start()
    save_to_history(lat, lng)
    status.config(text=f"✅ 已設定：{lat}, {lng}")
    location_name_label.config(text="")

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

    threading.Thread(target=fetch_name, daemon=True).start()

def clear_location():
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

def load_coord_list():
    filepath = filedialog.askopenfilename(
        title="選擇座標清單",
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
                    coord_list_items.append({"name": name, "lat": str(item["lat"]), "lng": str(item["lng"])})
                    coord_listbox.insert(tk.END, name)
        elif isinstance(data, dict):
            for name, coords in data.items():
                if "lat" in coords and "lng" in coords:
                    coord_list_items.append({"name": name, "lat": str(coords["lat"]), "lng": str(coords["lng"])})
                    coord_listbox.insert(tk.END, name)
        list_count_label.config(text=f"共 {len(coord_list_items)} 筆")
        status.config(text=f"✅ 已載入 {len(coord_list_items)} 筆座標")
    except Exception as e:
        status.config(text=f"❌ 載入失敗：{str(e)[:50]}")

def on_coord_list_select(event):
    selection = coord_listbox.curselection()
    if not selection:
        return
    item = coord_list_items[selection[0]]
    lat_entry.delete(0, tk.END)
    lat_entry.insert(0, item["lat"])
    lng_entry.delete(0, tk.END)
    lng_entry.insert(0, item["lng"])
    set_location()

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

update_favorites_menu()

# 座標清單（右側欄）
list_frame = tk.LabelFrame(frame, text="座標清單", padx=10, pady=10)
list_frame.grid(row=0, column=5, rowspan=9, sticky="nsew", padx=(20, 0))

list_top = tk.Frame(list_frame)
list_top.pack(fill=tk.X, pady=(0, 5))
tk.Button(list_top, text="📂 載入清單", command=load_coord_list).pack(side=tk.LEFT)
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