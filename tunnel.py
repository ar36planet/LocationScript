from core import tunnel_service

_root = None
_status = None
_tunnel_status = None
_tunnel_check_id = None
_tunnel_window_id = None


def setup(root, status_label, tunnel_status_label):
    global _root, _status, _tunnel_status
    _root = root
    _status = status_label
    _tunnel_status = tunnel_status_label


def cancel_check():
    global _tunnel_check_id
    if _tunnel_check_id is not None:
        _root.after_cancel(_tunnel_check_id)
        _tunnel_check_id = None


def check_tunnel_status():
    global _tunnel_check_id
    if tunnel_service.is_running():
        _tunnel_status.config(text="🟢 Tunnel 運行中", fg="green")
    else:
        _tunnel_status.config(text="🔴 Tunnel 未啟動", fg="red")
    _tunnel_check_id = _root.after(2000, check_tunnel_status)


def start_tunnel():
    global _tunnel_window_id
    result = tunnel_service.start_tunnel(headless=False)
    if result.ok:
        _tunnel_window_id = result.data.get("window_id")
        _status.config(text=f"✅ {result.message}")
    else:
        if result.code == "ENV_ERROR":
            _status.config(text=f"❌ {result.message}")
        else:
            _status.config(text=f"❌ {result.message[:50]}")


def stop_tunnel():
    global _tunnel_window_id
    result = tunnel_service.stop_tunnel(headless=False)
    _tunnel_window_id = None
    if result.ok:
        if "找不到" in result.message:
            _status.config(text=f"⚠️ {result.message}")
        else:
            _status.config(text=f"✅ {result.message}")
    else:
        _status.config(text=f"❌ {result.message[:50]}")


def is_running():
    return tunnel_service.is_running()
