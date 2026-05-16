import tkinter as tk
from tkinter import messagebox, simpledialog, filedialog
import json
import os
import urllib.request
import urllib.error
import webbrowser
import threading
from datetime import datetime

import customtkinter as ctk

import config
import storage
import tunnel
import location
import patrol as patrol_module
from world_clock import WorldClockWindow
from core.location_service import (
    get_last_device_scan_error, list_connected_devices,
    set_session_udid, clear_session_udid, fetch_timezone_time,
)
from list_editor import ListEditorWindow
from route_preview import RoutePreviewWindow
from version import __version__
from ui.theme import (
    apply as _apply_theme, PRIMARY, SECONDARY,
    FONT_BODY, FONT_BOLD, FONT_TITLE, FONT_SMALL, FONT_MONO,
    PAD_SM, PAD_MD, CORNER_RADIUS, BUTTON_HEIGHT, BTN_SECONDARY, BTN_SECONDARY_HOVER, BTN_TEXT,
)

GITHUB_REPO = "ar36planet/LocationScript"

# ── 全域狀態 ──────────────────────────────────────────────────────────────────

favorites = storage.load_favorites()
coord_list_items: list = []
_list_editor_win = None
_world_clock_win = None
_coord_row_buttons: list[ctk.CTkButton] = []
_coord_selected_idx: int | None = None
patrol_controller = None
_patrol_paused = False
_session_devices: list[dict] = []
_device_label_timer_id = None
_device_label_running = False


# ── 收藏地點 ──────────────────────────────────────────────────────────────────

def update_favorites_menu():
    values = list(favorites.keys())
    fav_combo.configure(values=values if values else [""])
    if not values:
        fav_combo.set("")


def _on_fav_selected(choice):
    if choice:
        select_favorite(choice)


def select_favorite(name):
    if name not in favorites:
        return
    coords = favorites[name]
    lat_entry.delete(0, "end")
    lat_entry.insert(0, coords["lat"])
    lng_entry.delete(0, "end")
    lng_entry.insert(0, coords["lng"])
    fav_combo.set(name)
    status.configure(text=f"✅ 已載入：{name}")


def add_favorite():
    lat = lat_entry.get().strip()
    lng = lng_entry.get().strip()
    if not lat or not lng:
        status.configure(text="❌ 請先輸入經緯度")
        return
    name = simpledialog.askstring("新增收藏", "請輸入地點名稱：")
    if name:
        favorites[name] = {"lat": lat, "lng": lng}
        storage.save_favorites(favorites)
        update_favorites_menu()
        status.configure(text=f"✅ 已收藏：{name}")


def delete_favorite():
    name = fav_combo.get()
    if name and name in favorites:
        if messagebox.askyesno("刪除收藏", f"確定要刪除「{name}」嗎？"):
            del favorites[name]
            storage.save_favorites(favorites)
            update_favorites_menu()
            fav_combo.set("")
            status.configure(text=f"✅ 已刪除：{name}")
    else:
        status.configure(text="❌ 請先選擇要刪除的地點")


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
            status.configure(text="❌ 找不到可匯入的地點")
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
        status.configure(text=f"✅ 已匯入 {len(imported)} 筆地點")
    except Exception as e:
        status.configure(text=f"❌ 匯入失敗：{str(e)[:50]}")


# ── 座標清單 ──────────────────────────────────────────────────────────────────

def refresh_main_listbox():
    global _coord_selected_idx
    for btn in _coord_row_buttons:
        btn.destroy()
    _coord_row_buttons.clear()
    _coord_selected_idx = None
    _update_start_label()

    for idx, item in enumerate(coord_list_items):
        btn = ctk.CTkButton(
            _coord_scrollable,
            text=item["name"],
            font=FONT_MONO,
            anchor="w",
            fg_color="transparent",
            text_color=("black", "white"),
            hover_color=("gray85", "gray25"),
            height=26,
            command=lambda i=idx: _select_coord_row(i),
        )
        btn.grid(row=idx, column=0, sticky="ew", pady=1)
        _coord_row_buttons.append(btn)

    list_count_label.configure(text=f"共 {len(coord_list_items)} 筆")


def _select_coord_row(idx: int):
    global _coord_selected_idx
    if patrol_controller and patrol_controller.is_running:
        return
    if _coord_selected_idx is not None and _coord_selected_idx < len(_coord_row_buttons):
        _coord_row_buttons[_coord_selected_idx].configure(fg_color="transparent")
    _coord_selected_idx = idx
    if idx < len(_coord_row_buttons):
        _coord_row_buttons[idx].configure(fg_color=(PRIMARY, PRIMARY))
    _update_start_label()
    item = coord_list_items[idx]
    lat_entry.delete(0, "end")
    lat_entry.insert(0, item["lat"])
    lng_entry.delete(0, "end")
    lng_entry.insert(0, item["lng"])
    set_location()


def _update_start_label():
    try:
        if _coord_selected_idx is not None and _coord_selected_idx < len(coord_list_items):
            name = coord_list_items[_coord_selected_idx].get("name", f"#{_coord_selected_idx + 1}")
            patrol_start_label.configure(text=f"起 {name}")
        else:
            patrol_start_label.configure(text="起 #1")
    except NameError:
        pass


def _highlight_coord_row(idx: int):
    global _coord_selected_idx
    if _coord_selected_idx is not None and _coord_selected_idx < len(_coord_row_buttons):
        _coord_row_buttons[_coord_selected_idx].configure(fg_color="transparent")
    _coord_selected_idx = idx
    if idx < len(_coord_row_buttons):
        _coord_row_buttons[idx].configure(fg_color=("gray75", "gray30"))


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
        status.configure(text=f"✅ 已載入 {len(coord_list_items)} 筆座標")
    except Exception as e:
        status.configure(text=f"❌ 載入失敗：{str(e)[:50]}")


def preview_coord_list():
    if not coord_list_items:
        messagebox.showwarning("清單為空", "請先載入座標清單")
        return
    waypoints = [(float(it["lat"]), float(it["lng"])) for it in coord_list_items]
    RoutePreviewWindow(root, waypoints, flowers=waypoints)


def clear_coord_list():
    if patrol_controller and patrol_controller.is_running:
        status.configure(text="❌ 巡邏中，請先停止再清除清單")
        return
    coord_list_items.clear()
    refresh_main_listbox()
    list_count_label.configure(text="")
    status.configure(text="✅ 已清除清單")


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
    def _world_clock_set(lat: str, lng: str):
        lat_entry.delete(0, "end")
        lat_entry.insert(0, lat)
        lng_entry.delete(0, "end")
        lng_entry.insert(0, lng)

    _world_clock_win = WorldClockWindow(
        root,
        location_fn=_world_clock_set,
        on_status=lambda text: status.configure(text=text),
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
        on_status=lambda text: status.configure(text=text),
    )
    if coord_list_items:
        _list_editor_win.load_from_items(coord_list_items)


# ── UI 輸入包裝 ────────────────────────────────────────────────────────────────

def set_location():
    lat = lat_entry.get().strip()
    lng = lng_entry.get().strip()
    if not lat or not lng:
        status.configure(text="❌ 請輸入經緯度")
        return

    if cross_day_var.get():
        status.configure(text="⏳ 查詢目標時區…")

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
                            status.configure(text="已取消")
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
        lat_entry.delete(0, "end")
        lat_entry.insert(0, lat)
        lng_entry.delete(0, "end")
        lng_entry.insert(0, lng)
        status.configure(text=f"✅ 已解析{label}")
    else:
        status.configure(text="❌ 無法解析網址")


def do_parse_coords():
    text = coords_entry.get().strip()
    result = location.parse_coords(text)
    if result:
        lat, lng = result
        lat_entry.delete(0, "end")
        lat_entry.insert(0, lat)
        lng_entry.delete(0, "end")
        lng_entry.insert(0, lng)
        status.configure(text="✅ 已解析座標")
    else:
        status.configure(text="❌ 格式錯誤，請輸入如：25.112233,123.123123")


# ── 巡邏 UI ────────────────────────────────────────────────────────────────────

def on_patrol_finish():
    def update():
        global _patrol_paused
        btn_main_patrol_start.configure(state="normal")
        btn_main_patrol_pause.configure(state="disabled", text="⏸ 暫停")
        btn_main_patrol_stop.configure(state="disabled")
        patrol_status_label.configure(text="✅ 巡邏完成")
        _patrol_paused = False
    root.after(0, update)


def main_patrol_travel(idx_to, name_to, remaining_m):
    def update():
        dist_str = f"{remaining_m/1000:.1f}km" if remaining_m >= 1000 else f"{remaining_m:.0f}m"
        patrol_status_label.configure(text=f"🚶 → {name_to}  {dist_str}")
        _highlight_coord_row(idx_to)
    root.after(0, update)


def main_patrol_tick(idx, name, remaining):
    def update():
        total = len(coord_list_items)
        patrol_status_label.configure(text=f"[{idx+1}/{total}] {name}  {remaining}s")
        _highlight_coord_row(idx)
    root.after(0, update)


def start_main_patrol():
    global patrol_controller
    if not coord_list_items:
        status.configure(text="❌ 清單為空，請先載入或套用座標")
        return
    if patrol_controller is None:
        patrol_controller = patrol_module.PatrolController(location.set_location_direct)
    start_idx = _coord_selected_idx if _coord_selected_idx is not None else 0
    try:
        speed = max(0.0, float(patrol_speed_entry.get().strip()))
    except ValueError:
        speed = 20.0
    patrol_controller.on_tick = main_patrol_tick
    patrol_controller.on_travel = main_patrol_travel
    patrol_controller.on_finish = on_patrol_finish
    patrol_controller.start(coord_list_items, start_idx, speed_kmh=speed, mode=patrol_mode_var.get())
    btn_main_patrol_start.configure(state="disabled")
    btn_main_patrol_pause.configure(state="normal", text="⏸ 暫停")
    btn_main_patrol_stop.configure(state="normal")
    patrol_status_label.configure(text="巡邏中...")


def pause_main_patrol():
    global _patrol_paused
    if not patrol_controller:
        return
    if not _patrol_paused:
        patrol_controller.pause()
        btn_main_patrol_pause.configure(text="▶ 繼續")
        patrol_status_label.configure(text="已暫停")
        _patrol_paused = True
    else:
        patrol_controller.resume()
        btn_main_patrol_pause.configure(text="⏸ 暫停")
        _patrol_paused = False


def stop_main_patrol():
    global _patrol_paused
    if patrol_controller:
        patrol_controller.stop()
    btn_main_patrol_start.configure(state="normal")
    btn_main_patrol_pause.configure(state="disabled", text="⏸ 暫停")
    btn_main_patrol_stop.configure(state="disabled")
    patrol_status_label.configure(text="")
    _patrol_paused = False


def restore_all():
    stop_main_patrol()
    location.stop_keepalive()
    location.clear_location()
    status.configure(text="還原中：停止巡邏與清除虛擬定位...")


def check_for_update(btn: ctk.CTkButton):
    btn.configure(state="disabled", text="檢查中...")

    def run():
        try:
            url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
            req = urllib.request.Request(url, headers={"User-Agent": "LocationScript-updater"})
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = json.loads(resp.read().decode())
            tag = data.get("tag_name", "").lstrip("v")
            release_url = data.get("html_url", f"https://github.com/{GITHUB_REPO}/releases/latest")

            def update_ui():
                btn.configure(state="normal", text="🔄 檢查更新")
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
                btn.configure(state="normal", text="🔄 檢查更新"),
                messagebox.showerror("網路錯誤", "無法連線至 GitHub，請確認網路連線。"),
            ))
        except Exception as e:
            root.after(0, lambda: (
                btn.configure(state="normal", text="🔄 檢查更新"),
                messagebox.showerror("錯誤", str(e)[:120]),
            ))

    threading.Thread(target=run, daemon=True).start()


def _toggle_tunnel():
    if tunnel_switch.get():
        tunnel.start_tunnel()
    else:
        tunnel.stop_tunnel()


def on_closing():
    tunnel.cancel_check()
    location.stop_keepalive()
    if patrol_controller and patrol_controller.is_running:
        patrol_controller.stop()
    if tunnel.is_running():
        if messagebox.askyesno("結束", "要同時停止 tunneld 嗎？"):
            tunnel.stop_tunnel()
    root.destroy()


# ── 裝置輪詢 ──────────────────────────────────────────────────────────────────

def _on_session_device_select(choice: str):
    for d in _session_devices:
        if _device_display(d) == choice:
            set_session_udid(d["udid"])
            status.configure(text=f"✅ 本次使用：{d['name']}")
            break


def _device_display(d: dict) -> str:
    conn = f" [{d['connection']}]" if d.get("connection") else ""
    return f"{d['name']} (iOS {d['ios']}){conn}"


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
            global _device_label_running, _session_devices, _device_label_timer_id
            try:
                scan_error = get_last_device_scan_error()
                if not devices:
                    _device_selector_frame.pack_forget()
                    if scan_error:
                        hint = "（請確認 iPhone 已信任、或終端可執行 `pymobiledevice3 usbmux list`）"
                        device_label.configure(
                            text=f"⚠️ 裝置偵測失敗：{scan_error} {hint}",
                            text_color="orange",
                        )
                    else:
                        device_label.configure(text="📵 未偵測到裝置", text_color=SECONDARY)
                elif len(devices) == 1:
                    _device_selector_frame.pack_forget()
                    d = devices[0]
                    conn = f"  [{d['connection']}]" if d.get("connection") else ""
                    udid_short = d["udid"][:8] + "…"
                    device_label.configure(
                        text=f"📱 {d['name']}  iOS {d['ios']}{conn}  {udid_short}",
                        text_color="green",
                    )
                else:
                    _session_devices = devices
                    labels = [_device_display(d) for d in devices]
                    _device_combo.configure(values=labels)
                    if _device_combo.get() not in labels:
                        _device_combo.set(labels[0])
                    device_label.configure(
                        text=f"⚠️ 偵測到 {len(devices)} 台裝置，請選擇：",
                        text_color="orange",
                    )
                    _device_selector_frame.pack(fill="x", padx=PAD_MD, pady=(0, PAD_SM))
            finally:
                _device_label_running = False
                _device_label_timer_id = root.after(3000, _update_device_label)

        root.after(0, update_ui)

    threading.Thread(target=run, daemon=True).start()


# ── 主視窗 ─────────────────────────────────────────────────────────────────────

_apply_theme()

root = ctk.CTk()
root.title(f"iOS 虛擬定位 v{__version__}")
root.geometry("1280x660")
root.resizable(True, False)
root.minsize(900, 560)
root.protocol("WM_DELETE_WINDOW", on_closing)

frame = ctk.CTkFrame(root, fg_color="transparent")
frame.pack(fill="both", expand=True, padx=20, pady=15)
frame.columnconfigure(1, weight=1)
frame.columnconfigure(5, weight=0)

# ── 頂部工具列：Tunnel / 版本 ────────────────────────────────────────────────
top_row = ctk.CTkFrame(frame, fg_color="transparent")
top_row.grid(row=0, column=0, columnspan=4, sticky="ew", pady=(0, 10))

# Tunnel 卡片
tunnel_frame = ctk.CTkFrame(top_row, corner_radius=CORNER_RADIUS)
tunnel_frame.pack(side="left")

tunnel_status = ctk.CTkLabel(tunnel_frame, text="🔴 Tunnel 未啟動",
                              text_color="red", font=FONT_BOLD)
tunnel_status.pack(side="left", padx=(PAD_MD, PAD_SM), pady=PAD_SM)

tunnel_switch = ctk.CTkSwitch(
    tunnel_frame, text="",
    command=_toggle_tunnel,
)
tunnel_switch.pack(side="left", padx=(0, PAD_MD), pady=PAD_SM)

# 版本卡片
version_card = ctk.CTkFrame(top_row, corner_radius=CORNER_RADIUS)
version_card.pack(side="left", padx=(PAD_SM, 0))

ctk.CTkLabel(version_card, text=f"v{__version__}",
             text_color=SECONDARY, font=FONT_SMALL).pack(
    side="left", padx=(PAD_MD, PAD_SM), pady=PAD_SM
)
_update_btn = ctk.CTkButton(
    version_card, text="🔄 檢查更新", font=FONT_SMALL,
    height=28, fg_color=BTN_SECONDARY, hover_color=BTN_SECONDARY_HOVER, text_color=BTN_TEXT,
)
_update_btn.configure(command=lambda: check_for_update(_update_btn))
_update_btn.pack(side="left", padx=(0, PAD_MD), pady=PAD_SM)

# ── 裝置狀態 ──────────────────────────────────────────────────────────────────
device_frame = ctk.CTkFrame(frame, corner_radius=CORNER_RADIUS)
device_frame.grid(row=1, column=0, columnspan=4, sticky="ew", pady=(0, 8))

_device_header = ctk.CTkFrame(device_frame, fg_color="transparent")
_device_header.pack(fill="x", padx=PAD_MD, pady=PAD_SM)
device_label = ctk.CTkLabel(_device_header, text="偵測中...",
                             text_color=SECONDARY, font=FONT_BODY, anchor="w")
device_label.pack(side="left", fill="x", expand=True)
ctk.CTkButton(
    _device_header, text="🔍 重新偵測",
    command=lambda: _update_device_label(reset_timer=True),
    height=28, font=FONT_SMALL, fg_color=BTN_SECONDARY, hover_color=BTN_SECONDARY_HOVER, text_color=BTN_TEXT,
).pack(side="right")

_device_selector_frame = ctk.CTkFrame(device_frame, fg_color="transparent")
_device_combo = ctk.CTkComboBox(
    _device_selector_frame, values=[], width=280,
    command=_on_session_device_select, font=FONT_BODY,
)
_device_combo.pack(side="left")
ctk.CTkLabel(_device_selector_frame, text="（本次）",
             text_color=SECONDARY, font=FONT_SMALL).pack(side="left", padx=(4, 8))
ctk.CTkButton(
    _device_selector_frame, text="✕ 重設預設", font=FONT_SMALL,
    height=28, fg_color=BTN_SECONDARY, hover_color=BTN_SECONDARY_HOVER, text_color=BTN_TEXT,
    command=lambda: (
        clear_session_udid(),
        _device_combo.set(""),
        status.configure(text="✅ 已重設為預設裝置"),
    ),
).pack(side="left")

# ── 收藏地點 ──────────────────────────────────────────────────────────────────
fav_frame = ctk.CTkFrame(frame, corner_radius=CORNER_RADIUS)
fav_frame.grid(row=2, column=0, columnspan=4, sticky="ew", pady=(0, 10))

_fav_row = ctk.CTkFrame(fav_frame, fg_color="transparent")
_fav_row.pack(fill="x", padx=PAD_MD, pady=PAD_SM)

ctk.CTkLabel(_fav_row, text="收藏地點：", font=FONT_BODY).pack(side="left")
fav_combo = ctk.CTkComboBox(
    _fav_row, values=[], width=220, height=BUTTON_HEIGHT,
    command=_on_fav_selected, font=FONT_BODY,
)
fav_combo.set("")
fav_combo.pack(side="left", padx=(PAD_SM, PAD_MD))
ctk.CTkButton(_fav_row, text="⭐ 收藏", command=add_favorite,
              height=BUTTON_HEIGHT, font=FONT_BODY).pack(side="left", padx=(0, PAD_SM))
ctk.CTkButton(_fav_row, text="🗑️ 刪除", command=delete_favorite,
              height=BUTTON_HEIGHT, font=FONT_BODY,
              fg_color=BTN_SECONDARY, hover_color=BTN_SECONDARY_HOVER, text_color=BTN_TEXT).pack(side="left")
ctk.CTkButton(_fav_row, text="📥 匯入", command=import_favorites,
              height=BUTTON_HEIGHT, font=FONT_BODY,
              fg_color=BTN_SECONDARY, hover_color=BTN_SECONDARY_HOVER, text_color=BTN_TEXT).pack(side="left", padx=(PAD_SM, 0))
update_favorites_menu()

# ── 右側：座標清單 ────────────────────────────────────────────────────────────
list_frame = ctk.CTkFrame(frame, corner_radius=CORNER_RADIUS)
list_frame.grid(row=0, column=5, rowspan=12, sticky="nsew", padx=(20, 0))
list_frame.rowconfigure(2, weight=1)
list_frame.columnconfigure(0, weight=1)

ctk.CTkLabel(list_frame, text="座標清單", font=FONT_TITLE).pack(
    anchor="w", padx=PAD_MD, pady=(PAD_MD, PAD_SM)
)

list_top = ctk.CTkFrame(list_frame, fg_color="transparent")
list_top.pack(fill="x", padx=PAD_MD, pady=(0, PAD_SM))
ctk.CTkButton(list_top, text="📂 載入清單", command=load_coord_list,
              height=28, font=FONT_SMALL).pack(side="left")
ctk.CTkButton(list_top, text="✏️ 編輯清單", command=open_list_editor,
              height=28, font=FONT_SMALL,
              fg_color=BTN_SECONDARY, hover_color=BTN_SECONDARY_HOVER, text_color=BTN_TEXT).pack(side="left", padx=(4, 0))
ctk.CTkButton(list_top, text="🗑️ 清除", command=clear_coord_list,
              height=28, font=FONT_SMALL,
              fg_color=BTN_SECONDARY, hover_color=BTN_SECONDARY_HOVER, text_color=BTN_TEXT).pack(side="left", padx=(4, 0))
ctk.CTkButton(list_top, text="👁 預覽", command=preview_coord_list,
              height=28, font=FONT_SMALL,
              fg_color=BTN_SECONDARY, hover_color=BTN_SECONDARY_HOVER, text_color=BTN_TEXT).pack(side="left", padx=(4, 0))
list_count_label = ctk.CTkLabel(list_top, text="", font=FONT_SMALL, text_color=SECONDARY)
list_count_label.pack(side="left", padx=(PAD_SM, 0))

_coord_scrollable = ctk.CTkScrollableFrame(list_frame, width=220)
_coord_scrollable.pack(fill="both", expand=True, padx=PAD_MD)
_coord_scrollable.columnconfigure(0, weight=1)

# 巡邏控制
patrol_ctrl_frame = ctk.CTkFrame(list_frame, fg_color="transparent")
patrol_ctrl_frame.pack(fill="x", padx=PAD_MD, pady=(PAD_SM, 2))

btn_main_patrol_start = ctk.CTkButton(
    patrol_ctrl_frame, text="▶ 巡邏", command=start_main_patrol,
    width=70, height=BUTTON_HEIGHT, font=FONT_BODY,
)
btn_main_patrol_start.pack(side="left", padx=(0, 4))
btn_main_patrol_pause = ctk.CTkButton(
    patrol_ctrl_frame, text="⏸ 暫停", command=pause_main_patrol,
    width=70, height=BUTTON_HEIGHT, font=FONT_BODY,
    state="disabled", fg_color=BTN_SECONDARY, hover_color=BTN_SECONDARY_HOVER, text_color=BTN_TEXT,
)
btn_main_patrol_pause.pack(side="left", padx=(0, 4))
btn_main_patrol_stop = ctk.CTkButton(
    patrol_ctrl_frame, text="⏹ 停止", command=stop_main_patrol,
    width=70, height=BUTTON_HEIGHT, font=FONT_BODY,
    state="disabled", fg_color=BTN_SECONDARY, hover_color=BTN_SECONDARY_HOVER, text_color=BTN_TEXT,
)
btn_main_patrol_stop.pack(side="left")
patrol_start_label = ctk.CTkLabel(
    patrol_ctrl_frame, text="起 #1",
    font=FONT_SMALL, text_color=SECONDARY,
)
patrol_start_label.pack(side="left", padx=(8, 0))

patrol_status_label = ctk.CTkLabel(list_frame, text="", font=FONT_SMALL,
                                    text_color=SECONDARY, anchor="w")
patrol_status_label.pack(fill="x", padx=PAD_MD, pady=(2, 0))

speed_row = ctk.CTkFrame(list_frame, fg_color="transparent")
speed_row.pack(fill="x", padx=PAD_MD, pady=(2, PAD_MD))
ctk.CTkLabel(speed_row, text="速度：", font=FONT_SMALL).pack(side="left")
patrol_speed_entry = ctk.CTkEntry(speed_row, width=48, height=26, font=FONT_SMALL)
patrol_speed_entry.insert(0, "20")
patrol_speed_entry.pack(side="left")
ctk.CTkLabel(speed_row, text="km/h（0＝直跳）",
             font=FONT_SMALL, text_color=SECONDARY).pack(side="left", padx=(4, 0))

patrol_mode_var = tk.StringVar(value="loop")
ctk.CTkRadioButton(speed_row, text="循環", variable=patrol_mode_var, value="loop",
                    font=FONT_SMALL).pack(side="left", padx=(PAD_SM, 0))
ctk.CTkRadioButton(speed_row, text="來回", variable=patrol_mode_var, value="pingpong",
                    font=FONT_SMALL).pack(side="left", padx=(4, 0))
ctk.CTkRadioButton(speed_row, text="單次", variable=patrol_mode_var, value="once",
                    font=FONT_SMALL).pack(side="left", padx=(4, 0))

# ── 左側輸入區 ────────────────────────────────────────────────────────────────

ctk.CTkLabel(frame, text="Google Maps 網址：", font=FONT_BODY).grid(
    row=3, column=0, sticky="w", pady=(PAD_SM, 0)
)
url_entry = ctk.CTkEntry(frame, width=300, height=BUTTON_HEIGHT, font=FONT_BODY)
url_entry.grid(row=3, column=1, columnspan=2, sticky="ew", pady=(PAD_SM, 0))
ctk.CTkButton(frame, text="解析", command=do_parse_google_url,
              width=60, height=BUTTON_HEIGHT, font=FONT_BODY).grid(
    row=3, column=3, padx=(PAD_SM, 0), pady=(PAD_SM, 0)
)

ctk.CTkLabel(frame, text="座標字串：", font=FONT_BODY).grid(
    row=4, column=0, sticky="w", pady=(PAD_SM, 0)
)
coords_entry = ctk.CTkEntry(frame, width=300, height=BUTTON_HEIGHT, font=FONT_BODY)
coords_entry.grid(row=4, column=1, columnspan=2, sticky="ew", pady=(PAD_SM, 0))
ctk.CTkButton(frame, text="解析", command=do_parse_coords,
              width=60, height=BUTTON_HEIGHT, font=FONT_BODY).grid(
    row=4, column=3, padx=(PAD_SM, 0), pady=(PAD_SM, 0)
)

cross_day_var = tk.BooleanVar(value=False)
_coord_row = ctk.CTkFrame(frame, fg_color="transparent")
_coord_row.grid(row=5, column=0, columnspan=4, sticky="w", pady=10)
ctk.CTkLabel(_coord_row, text="緯度：", font=FONT_BODY).pack(side="left")
lat_entry = ctk.CTkEntry(_coord_row, width=120, height=BUTTON_HEIGHT, font=FONT_BODY)
lat_entry.pack(side="left")
lat_entry.insert(0, "25.0330")
ctk.CTkLabel(_coord_row, text="經度：", font=FONT_BODY).pack(side="left", padx=(PAD_MD, 0))
lng_entry = ctk.CTkEntry(_coord_row, width=120, height=BUTTON_HEIGHT, font=FONT_BODY)
lng_entry.pack(side="left")
lng_entry.insert(0, "121.5654")
ctk.CTkSwitch(_coord_row, text="跨日警示", variable=cross_day_var,
              font=FONT_BODY).pack(side="left", padx=(PAD_MD, 0))

btn_frame = ctk.CTkFrame(frame, fg_color="transparent")
btn_frame.grid(row=7, column=0, columnspan=4, pady=PAD_MD)
ctk.CTkButton(btn_frame, text="📍 設定位置", command=set_location,
              width=120, height=BUTTON_HEIGHT, font=FONT_BODY).pack(side="left", padx=5)
ctk.CTkButton(btn_frame, text="🔄 清除", command=location.clear_location,
              width=100, height=BUTTON_HEIGHT, font=FONT_BODY,
              fg_color=BTN_SECONDARY, hover_color=BTN_SECONDARY_HOVER, text_color=BTN_TEXT).pack(side="left", padx=5)
ctk.CTkButton(btn_frame, text="♻️ 還原", command=restore_all,
              width=100, height=BUTTON_HEIGHT, font=FONT_BODY,
              fg_color=BTN_SECONDARY, hover_color=BTN_SECONDARY_HOVER, text_color=BTN_TEXT).pack(side="left", padx=5)
ctk.CTkButton(btn_frame, text="🌍 世界時區", command=open_world_clock,
              height=BUTTON_HEIGHT, font=FONT_BODY,
              fg_color=BTN_SECONDARY, hover_color=BTN_SECONDARY_HOVER, text_color=BTN_TEXT).pack(side="left", padx=5)

status = ctk.CTkLabel(frame, text="就緒 — iOS 16 以下可跳過 Tunnel", font=FONT_BODY)
status.grid(row=8, column=0, columnspan=4)

location_name_label = ctk.CTkLabel(frame, text="", text_color=SECONDARY,
                                    wraplength=380, font=FONT_BODY, justify="center")
location_name_label.grid(row=9, column=0, columnspan=4, pady=(0, 2))

location_time_label = ctk.CTkLabel(frame, text="", text_color=SECONDARY,
                                    font=FONT_BODY, justify="center")
location_time_label.grid(row=10, column=0, columnspan=4, pady=(0, 5))

# ── 初始化各模組 ──────────────────────────────────────────────────────────────

tunnel.setup(root, status, tunnel_status, tunnel_switch)
location.setup(root, status, lat_entry, lng_entry, location_name_label, location_time_label)

tunnel.check_tunnel_status()
tunnel._check_device_change()
_update_device_label()

root.mainloop()
