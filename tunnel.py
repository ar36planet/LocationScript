from core import tunnel_service
from core.location_service import _connected_udids

_root = None
_status = None
_tunnel_status = None
_tunnel_check_id = None
_device_check_id = None
_last_udids: set = set()


def setup(root, status_label, tunnel_status_label):
    global _root, _status, _tunnel_status
    _root = root
    _status = status_label
    _tunnel_status = tunnel_status_label


def cancel_check():
    global _tunnel_check_id, _device_check_id
    if _tunnel_check_id is not None:
        _root.after_cancel(_tunnel_check_id)
        _tunnel_check_id = None
    if _device_check_id is not None:
        _root.after_cancel(_device_check_id)
        _device_check_id = None


def check_tunnel_status():
    global _tunnel_check_id
    if tunnel_service.is_running():
        _tunnel_status.config(text="🟢 Tunnel 運行中", fg="green")
    else:
        _tunnel_status.config(text="🔴 Tunnel 未啟動", fg="red")
    _tunnel_check_id = _root.after(2000, check_tunnel_status)


def _check_device_change():
    """Poll for device changes; auto-restart tunnel only on true device switch (remove+add)."""
    global _device_check_id, _last_udids
    current = set(_connected_udids())
    if _last_udids and current and tunnel_service.is_running():
        removed = _last_udids - current
        added = current - _last_udids
        if removed and added:
            # A real switch: old device gone, new device appeared
            _status.config(text="🔄 偵測到裝置切換，正在重啟 Tunnel...")
            _do_restart()
    _last_udids = current
    _device_check_id = _root.after(3000, _check_device_change)


def _do_restart():
    tunnel_service.stop_tunnel(headless=True)
    result = tunnel_service.start_tunnel(headless=True)
    if result.ok:
        _status.config(text="✅ Tunnel 已重啟（裝置切換）")
    else:
        _status.config(text=f"❌ Tunnel 重啟失敗：{result.message[:50]}")


def start_tunnel():
    # Try passwordless background start first
    result = tunnel_service.start_tunnel(headless=True)
    if result.ok:
        _status.config(text=f"✅ {result.message}")
        return
    # NOPASSWD not configured — fall back to Terminal window for password prompt
    if result.data.get("sudo_nopasswd_ok") is False:
        _status.config(text="🔑 需要輸入密碼，開啟終端機視窗...")
        result2 = tunnel_service.start_tunnel(headless=False)
        if result2.ok:
            _status.config(text=f"✅ {result2.message}")
        else:
            _status.config(text=f"❌ {result2.message[:60]}")
    else:
        _status.config(text=f"❌ {result.message[:60]}")


def stop_tunnel():
    result = tunnel_service.stop_tunnel(headless=True)
    if result.ok:
        _status.config(text=f"✅ {result.message}")
    else:
        _status.config(text=f"❌ {result.message[:50]}")


def is_running():
    return tunnel_service.is_running()
