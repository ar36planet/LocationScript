import tkinter as tk
from tkinter import messagebox, simpledialog, filedialog
import json
import os
import urllib.request
import urllib.error
import webbrowser

import config
import storage
import tunnel
import location
import patrol as patrol_module
from world_clock import WorldClockWindow
from core.location_service import get_last_device_scan_error, list_connected_devices, set_session_udid, clear_session_udid, fetch_timezone_time
from list_editor import ListEditorWindow
from version import __version__
import threading
from datetime import datetime

GITHUB_REPO = "ar36planet/LocationScript"

# ── 收藏地點 ─────────────────────────────────────────────────────────────────

favorites = storage.load_favorites()


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
        storage.save_favorites(favorites)
        update_favorites_menu()
        status.config(text=f"✅ 已收藏：{name}")


def delete_favorite():
    name = fav_var.get()
    if name and name in favorites:
        if messagebox.askyesno("刪除收藏", f"確定要刪除「{name}」嗎？"):
            del favorites[name]
            storage.save_favorites(favorites)
            update_favorites_menu()
            fav_var.set("")
            status.config(text=f"✅ 已刪除：{name}")
    else:
        status.config(text="❌ 請先選擇要刪除的地點")


def import_favorites():
    filepath = filedialog.askopenfilename(
        title="匯入最愛",
        initialdir=config.SCRIPT_DIR,
        filetypes=[("JSON 檔案", "*.json"), ("所有檔案", "*.*")],
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
                f"找到 {len(imported)} 筆地點。\n\n「是」覆蓋現有收藏，「否」合併（重複名稱以匯入為準）",
            )
            if replace is None:
                return
            if replace:
                favorites.clear()
        favorites.update(imported)
        storage.save_favorites(favorites)
        update_favorites_menu()
        status.config(text=f"✅ 已匯入 {len(imported)} 筆地點")
    except Exception as e:
        status.config(text=f"❌ 匯入失敗：{str(e)[:50]}")


# ── 座標清單 ─────────────────────────────────────────────────────────────────

coord_list_items: list = []
_list_editor_win = None


def refresh_main_listbox():
    coord_listbox.delete(0, tk.END)
    for item in coord_list_items:
        coord_listbox.insert(tk.END, item["name"])
    list_count_label.config(text=f"共 {len(coord_list_items)} 筆")


def load_coord_list():
    initial = config.HISTORY_DIR if os.path.isdir(config.HISTORY_DIR) else config.SCRIPT_DIR
    filepath = filedialog.askopenfilename(
        title="選擇座標清單",
        initialdir=initial,
        filetypes=[("JSON 檔案", "*.json"), ("所有檔案", "*.*")],
    )
    if not filepath:
        return
    try:
        items = storage.parse_coord_list_file(filepath)
        coord_list_items.clear()
        coord_list_items.extend(items)
        refresh_main_listbox()
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


_world_clock_win = None


def open_world_clock():
    global _world_clock_win
    if _world_clock_win is not None:
        try:
            if _world_clock_win.win.winfo_exists():
                _world_clock_win.win.lift()
                _world_clock_win.win.focus_force()
                return
        except Exception:
            pass
    _world_clock_win = WorldClockWindow(
        root,
        location_fn=location.set_location_direct,
        on_status=lambda text: status.config(text=text),
    )


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
    _list_editor_win = ListEditorWindow(
        root,
        location_fn=location.set_location_direct,
        coord_list_items=coord_list_items,
        on_apply=refresh_main_listbox,
        on_status=lambda text: status.config(text=text),
    )
    if coord_list_items:
        _list_editor_win.load_from_items(coord_list_items)


# ── UI 輸入包裝 ───────────────────────────────────────────────────────────────

def set_location():
    lat = lat_entry.get().strip()
    lng = lng_entry.get().strip()
    if not lat or not lng:
        status.config(text="❌ 請輸入經緯度")
        return

    if cross_day_var.get():
        status.config(text="⏳ 查詢目標時區…")

        def check_then_set():
            tz = fetch_timezone_time(lat, lng)
            year = tz.get("year")
            month = tz.get("month")
            day = tz.get("day")
            timezone = tz.get("timeZone", "")

            def proceed():
                location.set_location_direct(lat, lng)

            def on_result():
                if year and month and day:
                    local_date = datetime.now().date()
                    target_date = datetime(year, month, day).date()
                    if target_date != local_date:
                        local_str = local_date.strftime("%Y-%m-%d")
                        target_str = target_date.strftime("%Y-%m-%d")
                        confirmed = messagebox.askokcancel(
                            "跨日警示",
                            f"目標地點目前日期為 {target_str}（{timezone}），\n"
                            f"與本地日期 {local_str} 不同。\n\n"
                            "確定要設定位置嗎？",
                        )
                        if confirmed:
                            proceed()
                        else:
                            status.config(text="已取消")
                        return
                proceed()

            root.after(0, on_result)

        threading.Thread(target=check_then_set, daemon=True).start()
    else:
        location.set_location_direct(lat, lng)


def do_parse_google_url():
    url = url_entry.get().strip()
    result = location.parse_google_url(url)
    if result:
        lat, lng, label = result
        lat_entry.delete(0, tk.END)
        lat_entry.insert(0, lat)
        lng_entry.delete(0, tk.END)
        lng_entry.insert(0, lng)
        status.config(text=f"✅ 已解析{label}")
    else:
        status.config(text="❌ 無法解析網址")


def do_parse_coords():
    text = coords_entry.get().strip()
    result = location.parse_coords(text)
    if result:
        lat, lng = result
        lat_entry.delete(0, tk.END)
        lat_entry.insert(0, lat)
        lng_entry.delete(0, tk.END)
        lng_entry.insert(0, lng)
        status.config(text="✅ 已解析座標")
    else:
        status.config(text="❌ 格式錯誤，請輸入如：25.112233,123.123123")


# ── 巡邏 UI ──────────────────────────────────────────────────────────────────

patrol_controller = None


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
        patrol_controller = patrol_module.PatrolController(location.set_location_direct)
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


def restore_all():
    # 1) Stop patrol/movement tasks first
    stop_main_patrol()
    # 2) Stop location keepalive worker
    location.stop_keepalive()
    # 3) Clear simulated location (async UI update handled in location.clear_location)
    location.clear_location()
    status.config(text="還原中：停止巡邏與清除虛擬定位...")


def check_for_update(btn: tk.Button):
    btn.config(state=tk.DISABLED, text="檢查中...")

    def run():
        try:
            url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
            req = urllib.request.Request(url, headers={"User-Agent": "LocationScript-updater"})
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = json.loads(resp.read().decode())
            tag = data.get("tag_name", "").lstrip("v")
            release_url = data.get("html_url", f"https://github.com/{GITHUB_REPO}/releases/latest")

            def update_ui():
                btn.config(state=tk.NORMAL, text="🔄 檢查更新")
                try:
                    current = tuple(int(x) for x in __version__.split("."))
                    latest = tuple(int(x) for x in tag.split("."))
                except ValueError:
                    messagebox.showinfo("更新", f"最新版本：{tag}\n當前版本：{__version__}\n\n無法比較版本號，請手動確認。")
                    return
                if latest > current:
                    if messagebox.askyesno("發現新版本", f"最新版本：v{tag}\n當前版本：v{__version__}\n\n是否前往下載頁面？"):
                        webbrowser.open(release_url)
                else:
                    messagebox.showinfo("已是最新版本", f"當前版本 v{__version__} 已是最新版本。")

            root.after(0, update_ui)
        except urllib.error.URLError:
            root.after(0, lambda: (
                btn.config(state=tk.NORMAL, text="🔄 檢查更新"),
                messagebox.showerror("網路錯誤", "無法連線至 GitHub，請確認網路連線。"),
            ))
        except Exception as e:
            root.after(0, lambda: (
                btn.config(state=tk.NORMAL, text="🔄 檢查更新"),
                messagebox.showerror("錯誤", str(e)[:120]),
            ))

    threading.Thread(target=run, daemon=True).start()


def on_closing():
    tunnel.cancel_check()
    location.stop_keepalive()
    if patrol_controller and patrol_controller.is_running:
        patrol_controller.stop()
    if tunnel.is_running():
        if messagebox.askyesno("結束", "要同時停止 tunneld 嗎？"):
            tunnel.stop_tunnel()
    root.destroy()


# ── 主視窗 ───────────────────────────────────────────────────────────────────

root = tk.Tk()
root.title(f"iOS 虛擬定位 v{__version__}")
root.geometry("1280x640")
root.resizable(True, False)
root.minsize(900, 540)
root.protocol("WM_DELETE_WINDOW", on_closing)

frame = tk.Frame(root, padx=20, pady=15)
frame.pack(fill=tk.BOTH, expand=True)

# Tunnel 狀態列
status_frame = tk.Frame(frame)
status_frame.grid(row=0, column=0, columnspan=4, sticky="ew", pady=(0, 10))
tunnel_status = tk.Label(status_frame, text="🔴 Tunnel 未啟動", fg="red", font=("", 12, "bold"))
tunnel_status.pack(side=tk.LEFT)
tk.Button(status_frame, text="🌍 世界時區", font=("", 9), command=open_world_clock).pack(side=tk.RIGHT, padx=(0, 6))
version_frame = tk.Frame(status_frame)
version_frame.pack(side=tk.RIGHT, padx=(0, 6))
tk.Label(version_frame, text=f"v{__version__}", fg="gray", font=("", 9)).pack(side=tk.LEFT, padx=(0, 4))
_update_btn = tk.Button(version_frame, text="🔄 檢查更新", font=("", 9))
_update_btn.config(command=lambda: check_for_update(_update_btn))
_update_btn.pack(side=tk.LEFT)

# Tunnel 控制
tunnel_frame = tk.LabelFrame(frame, text="Tunnel 控制（iOS 17+ 需要）", padx=10, pady=10)
tunnel_frame.grid(row=1, column=0, columnspan=4, sticky="ew", pady=(0, 10))
tk.Button(tunnel_frame, text="🚀 啟動", command=tunnel.start_tunnel).pack(side=tk.LEFT, padx=5)
tk.Button(tunnel_frame, text="⏹️ 停止", command=tunnel.stop_tunnel).pack(side=tk.LEFT)

# 裝置狀態
device_frame = tk.LabelFrame(frame, text="裝置", padx=10, pady=6)
device_frame.grid(row=2, column=0, columnspan=4, sticky="ew", pady=(0, 10))
device_label = tk.Label(device_frame, text="偵測中...", fg="gray", anchor="w")
device_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
tk.Button(device_frame, text="🔍 重新偵測", command=lambda: _update_device_label(reset_timer=True)).pack(side=tk.RIGHT)

# 多裝置選擇列（有多台時才顯示）
_device_selector_frame = tk.Frame(device_frame)
_session_device_var = tk.StringVar(value="")
_device_menu = tk.OptionMenu(_device_selector_frame, _session_device_var, "")
_device_menu.config(width=28)
_device_menu.pack(side=tk.LEFT)
tk.Label(_device_selector_frame, text="（本次）", fg="gray", font=("", 9)).pack(side=tk.LEFT, padx=(2, 6))
tk.Button(_device_selector_frame, text="✕ 重設預設", font=("", 9),
          command=lambda: (clear_session_udid(), _session_device_var.set(""), status.config(text="✅ 已重設為預設裝置"))).pack(side=tk.LEFT)
_session_devices: list[dict] = []

def _on_session_device_select(*_):
    label = _session_device_var.get()
    for d in _session_devices:
        if _device_display(d) == label:
            set_session_udid(d["udid"])
            status.config(text=f"✅ 本次使用：{d['name']}")
            break

_session_device_var.trace_add("write", _on_session_device_select)

def _device_display(d: dict) -> str:
    conn = f" [{d['connection']}]" if d.get("connection") else ""
    return f"{d['name']} (iOS {d['ios']}){conn}"

# 收藏地點
fav_frame = tk.LabelFrame(frame, text="收藏地點", padx=10, pady=10)
fav_frame.grid(row=3, column=0, columnspan=4, sticky="ew", pady=(0, 10))
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
list_frame.grid(row=0, column=5, rowspan=10, sticky="nsew", padx=(20, 0))

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
tk.Label(frame, text="Google Maps 網址：").grid(row=4, column=0, sticky="w")
url_entry = tk.Entry(frame, width=40)
url_entry.grid(row=4, column=1, columnspan=2)
tk.Button(frame, text="解析", command=do_parse_google_url).grid(row=4, column=3, padx=5)

# 座標字串
tk.Label(frame, text="座標字串：").grid(row=5, column=0, sticky="w")
coords_entry = tk.Entry(frame, width=40)
coords_entry.grid(row=5, column=1, columnspan=2)
tk.Button(frame, text="解析", command=do_parse_coords).grid(row=5, column=3, padx=5)

# 經緯度
tk.Label(frame, text="緯度：").grid(row=6, column=0, sticky="w", pady=10)
lat_entry = tk.Entry(frame, width=15)
lat_entry.grid(row=6, column=1, sticky="w")
lat_entry.insert(0, "25.0330")

tk.Label(frame, text="經度：").grid(row=6, column=2, sticky="e")
lng_entry = tk.Entry(frame, width=15)
lng_entry.grid(row=6, column=3, sticky="w")
lng_entry.insert(0, "121.5654")

# 跨日警示
cross_day_var = tk.BooleanVar(value=False)
tk.Checkbutton(frame, text="跨日警示", variable=cross_day_var).grid(
    row=7, column=0, columnspan=4, sticky="w", padx=4,
)

# 按鈕
btn_frame = tk.Frame(frame)
btn_frame.grid(row=8, column=0, columnspan=4, pady=15)
tk.Button(btn_frame, text="📍 設定位置", command=set_location, width=12).pack(side=tk.LEFT, padx=5)
tk.Button(btn_frame, text="🔄 清除", command=location.clear_location, width=12).pack(side=tk.LEFT, padx=5)
tk.Button(btn_frame, text="♻️ 還原", command=restore_all, width=12).pack(side=tk.LEFT, padx=5)

# 狀態
status = tk.Label(frame, text="就緒 — iOS 16 以下可跳過 Tunnel")
status.grid(row=9, column=0, columnspan=4)

# 地點名稱
location_name_label = tk.Label(frame, text="", fg="gray", wraplength=380, justify="center")
location_name_label.grid(row=10, column=0, columnspan=4, pady=(0, 2))

# 當地時間
location_time_label = tk.Label(frame, text="", fg="gray", justify="center")
location_time_label.grid(row=11, column=0, columnspan=4, pady=(0, 5))

_device_label_timer_id = None
_device_label_running = False

def _update_device_label(reset_timer: bool = False):
    global _device_label_timer_id, _device_label_running
    if reset_timer and _device_label_timer_id is not None:
        root.after_cancel(_device_label_timer_id)
        _device_label_timer_id = None

    if _device_label_running:
        _device_label_timer_id = root.after(3000, _update_device_label)
        return

    _device_label_running = True

    def run():
        try:
            devices = list_connected_devices()
        except Exception:
            devices = []

        def update_ui():
            global _device_label_running, _session_devices
            try:
                scan_error = get_last_device_scan_error()
                if not devices:
                    _device_selector_frame.pack_forget()
                    if scan_error:
                        hint = "（請確認 iPhone 已信任、或終端可執行 `pymobiledevice3 usbmux list`）"
                        device_label.config(text=f"⚠️ 裝置偵測失敗：{scan_error} {hint}", fg="orange")
                    else:
                        device_label.config(text="📵 未偵測到裝置", fg="gray")
                elif len(devices) == 1:
                    _device_selector_frame.pack_forget()
                    d = devices[0]
                    conn = f"  [{d['connection']}]" if d.get("connection") else ""
                    udid_short = d["udid"][:8] + "…"
                    device_label.config(text=f"📱 {d['name']}  iOS {d['ios']}{conn}  {udid_short}", fg="green")
                else:
                    _session_devices = devices
                    labels = [_device_display(d) for d in devices]
                    # rebuild OptionMenu choices
                    menu = _device_menu["menu"]
                    menu.delete(0, "end")
                    for lbl in labels:
                        menu.add_command(label=lbl, command=lambda v=lbl: _session_device_var.set(v))
                    # set current selection if not yet chosen
                    if _session_device_var.get() not in labels:
                        _session_device_var.set(labels[0])
                    device_label.config(text=f"⚠️ 偵測到 {len(devices)} 台裝置，請選擇：", fg="orange")
                    _device_selector_frame.pack(side=tk.LEFT, fill=tk.X, pady=(4, 0))
            finally:
                _device_label_running = False
                _device_label_timer_id = root.after(3000, _update_device_label)

        root.after(0, update_ui)

    threading.Thread(target=run, daemon=True).start()


# 初始化各模組（widget 建立後才能傳入）
tunnel.setup(root, status, tunnel_status)
location.setup(root, status, lat_entry, lng_entry, location_name_label, location_time_label)

# 啟動輪詢
tunnel.check_tunnel_status()
tunnel._check_device_change()
_update_device_label()

root.mainloop()
