import os
import threading
import tkinter as tk

import customtkinter as ctk

import config
from core import location_service
from core.location_service import list_connected_devices, fetch_name_time
from storage import save_to_history
from ui.theme import SECONDARY, PAD_SM, PAD_MD, BUTTON_HEIGHT

_root = None
_status = None
_lat_entry = None
_lng_entry = None
_location_name_label = None
_location_time_label = None


def setup(root, status, lat_entry, lng_entry, location_name_label, location_time_label):
    global _root, _status, _lat_entry, _lng_entry, _location_name_label, _location_time_label
    _root = root
    _status = status
    _lat_entry = lat_entry
    _lng_entry = lng_entry
    _location_name_label = location_name_label
    _location_time_label = location_time_label


def parse_google_url(url: str):
    return location_service.parse_google_url(url)


def parse_coords(text: str):
    return location_service.parse_coords(text)


def stop_keepalive():
    location_service.stop_keepalive()


def _show_device_picker(on_selected):
    """彈出裝置選擇視窗，選完後呼叫 on_selected(udid)。"""
    devices = list_connected_devices()
    if not devices:
        _status.configure(text="❌ 沒有裝置連接")
        return

    dialog = ctk.CTkToplevel(_root)
    dialog.title("選擇裝置")
    dialog.resizable(False, False)
    dialog.grab_set()

    ctk.CTkLabel(dialog, text="偵測到多台裝置，請選擇要使用的裝置：").pack(
        anchor="w", padx=PAD_MD, pady=(PAD_MD, PAD_SM)
    )

    var = tk.StringVar(value=devices[0]["udid"])
    for d in devices:
        label = f"{d['name']}  iOS {d['ios']}\n{d['udid']}"
        ctk.CTkRadioButton(dialog, text=label, variable=var, value=d["udid"]).pack(
            anchor="w", padx=PAD_MD, pady=2
        )

    def confirm():
        selected = var.get()
        try:
            os.makedirs(os.path.dirname(config.DEFAULT_UDID_FILE), exist_ok=True)
            with open(config.DEFAULT_UDID_FILE, "w", encoding="utf-8") as f:
                f.write(selected)
        except Exception:
            pass
        dialog.destroy()
        on_selected()

    ctk.CTkButton(dialog, text="確定", command=confirm, width=80, height=BUTTON_HEIGHT).pack(
        pady=PAD_MD
    )
    dialog.wait_window()


def set_location_direct(lat: str, lng: str, save_history: bool = True, _fetch_name: bool = True):
    try:
        lat_f, lng_f = float(lat), float(lng)
    except ValueError:
        _root.after(0, lambda: _status.configure(text="❌ 無效的座標格式"))
        return
    if not (-90 <= lat_f <= 90 and -180 <= lng_f <= 180):
        _root.after(0, lambda: _status.configure(text="❌ 座標超出範圍"))
        return

    if _fetch_name:
        def fetch_info():
            info = fetch_name_time(lat, lng)
            def update_info():
                _location_name_label.configure(text=info.get("addr", ""), text_color=SECONDARY)
                lt = info.get("local_time", "")
                tz = info.get("timezone", "")
                _location_time_label.configure(
                    text=f"🕐 當地時間 {lt}（{tz}）" if lt else "",
                    text_color=SECONDARY,
                )
            _root.after(0, update_info)
        threading.Thread(target=fetch_info, daemon=True).start()

    def run():
        result = location_service.set_location(lat, lng, keepalive=True, fetch_name=False)

        def update_ui():
            if not result.ok:
                if result.code == "ENV_ERROR" and "Multiple devices" in result.message:
                    _show_device_picker(
                        on_selected=lambda: set_location_direct(lat, lng, save_history, _fetch_name)
                    )
                elif result.code == "PARAM_ERROR":
                    _status.configure(text=f"❌ {result.message}")
                else:
                    _status.configure(text=f"❌ {result.message[:60]}")
                return

            if save_history:
                save_to_history(lat, lng)

            _lat_entry.delete(0, "end")
            _lat_entry.insert(0, lat)
            _lng_entry.delete(0, "end")
            _lng_entry.insert(0, lng)
            _status.configure(text=f"✅ {result.message}")

        _root.after(0, update_ui)

    threading.Thread(target=run, daemon=True).start()


def clear_location():
    def run():
        result = location_service.clear_location()

        def update_ui():
            if result.ok:
                _status.configure(text="✅ 已清除")
                _location_name_label.configure(text="", text_color=SECONDARY)
                _location_time_label.configure(text="", text_color=SECONDARY)
            else:
                _status.configure(text=f"❌ {result.message[:50]}")

        _root.after(0, update_ui)

    threading.Thread(target=run, daemon=True).start()
