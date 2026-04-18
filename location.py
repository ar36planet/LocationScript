import threading

from core import location_service
from storage import save_to_history

_root = None
_status = None
_lat_entry = None
_lng_entry = None
_location_name_label = None


def setup(root, status, lat_entry, lng_entry, location_name_label):
    global _root, _status, _lat_entry, _lng_entry, _location_name_label
    _root = root
    _status = status
    _lat_entry = lat_entry
    _lng_entry = lng_entry
    _location_name_label = location_name_label


def parse_google_url(url: str):
    return location_service.parse_google_url(url)


def parse_coords(text: str):
    return location_service.parse_coords(text)


def stop_keepalive():
    location_service.stop_keepalive()


def set_location_direct(lat: str, lng: str, save_history: bool = True, _fetch_name: bool = True):
    def run():
        result = location_service.set_location(lat, lng, keepalive=True, fetch_name=_fetch_name)

        def update_ui():
            if not result.ok:
                if result.code == "PARAM_ERROR":
                    _status.config(text=f"❌ {result.message}")
                else:
                    _status.config(text=f"❌ {result.message[:50]}")
                return

            if save_history:
                save_to_history(lat, lng)

            _lat_entry.delete(0, "end")
            _lat_entry.insert(0, lat)
            _lng_entry.delete(0, "end")
            _lng_entry.insert(0, lng)
            _status.config(text=f"✅ {result.message}")
            if _fetch_name:
                name = result.data.get("name", "")
                _location_name_label.config(text=name, fg="gray")
            else:
                _location_name_label.config(text="")

        _root.after(0, update_ui)

    threading.Thread(target=run, daemon=True).start()


def clear_location():
    result = location_service.clear_location()
    if result.ok:
        _status.config(text="✅ 已清除")
    else:
        _status.config(text=f"❌ {result.message[:50]}")
