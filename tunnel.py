from core import tunnel_service
from core.location_service import _connected_udids
import threading

_root = None
_status = None
_tunnel_status = None
_tunnel_switch = None
_tunnel_check_id = None
_device_check_id = None
_last_udids: set = set()
_device_check_running = False


def setup(root, status_label, tunnel_status_label, tunnel_switch=None):
    global _root, _status, _tunnel_status, _tunnel_switch
    _root = root
    _status = status_label
    _tunnel_status = tunnel_status_label
    _tunnel_switch = tunnel_switch


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
    running = tunnel_service.is_running()
    if running:
        _tunnel_status.configure(text="🟢 Tunnel 運行中", text_color="green")
    else:
        _tunnel_status.configure(text="🔴 Tunnel 未啟動", text_color="red")
    if _tunnel_switch is not None:
        if running and not _tunnel_switch.get():
            _tunnel_switch.select()
        elif not running and _tunnel_switch.get():
            _tunnel_switch.deselect()
    _tunnel_check_id = _root.after(2000, check_tunnel_status)


def _check_device_change():
    """Poll for device changes; auto-restart tunnel only on true device switch (remove+add)."""
    global _device_check_id, _last_udids, _device_check_running
    if _device_check_running:
        _device_check_id = _root.after(3000, _check_device_change)
        return

    _device_check_running = True

    def run():
        try:
            current = set(_connected_udids())
        except Exception:
            current = set()

        def update_ui():
            global _last_udids, _device_check_running
            try:
                if _last_udids and current and tunnel_service.is_running():
                    removed = _last_udids - current
                    added = current - _last_udids
                    if removed and added:
                        _status.configure(text="🔄 偵測到裝置切換，正在重啟 Tunnel...")
                        _do_restart()
                _last_udids = current
            finally:
                _device_check_running = False

        _root.after(0, update_ui)

    threading.Thread(target=run, daemon=True).start()
    _device_check_id = _root.after(3000, _check_device_change)


def _do_restart():
    def run():
        tunnel_service.stop_tunnel(headless=True)
        result = tunnel_service.start_tunnel(headless=True)

        def update_ui():
            if result.ok:
                _status.configure(text="✅ Tunnel 已重啟（裝置切換）")
            else:
                _status.configure(text=f"❌ Tunnel 重啟失敗：{result.message[:50]}")

        _root.after(0, update_ui)

    threading.Thread(target=run, daemon=True).start()


def start_tunnel():
    _status.configure(text="⏳ 正在啟動 Tunnel...")

    def run():
        # Try passwordless background start first
        result = tunnel_service.start_tunnel(headless=True)

        def update_ui():
            if result.ok:
                _status.configure(text=f"✅ {result.message}")
                return
            # NOPASSWD not configured — fall back to Terminal window for password prompt
            if result.data.get("sudo_nopasswd_ok") is False:
                _status.configure(text="🔑 需要輸入密碼，開啟終端機視窗...")

                def run_terminal():
                    result2 = tunnel_service.start_tunnel(headless=False)

                    def update_ui2():
                        if result2.ok:
                            _status.configure(text=f"✅ {result2.message}")
                        else:
                            _status.configure(text=f"❌ {result2.message[:60]}")

                    _root.after(0, update_ui2)

                threading.Thread(target=run_terminal, daemon=True).start()
            else:
                _status.configure(text=f"❌ {result.message[:60]}")

        _root.after(0, update_ui)

    threading.Thread(target=run, daemon=True).start()


def stop_tunnel():
    _status.configure(text="⏳ 正在停止 Tunnel...")

    def run():
        result = tunnel_service.stop_tunnel(headless=True)

        def update_ui():
            if result.ok:
                _status.configure(text=f"✅ {result.message}")
            else:
                _status.configure(text=f"❌ {result.message[:50]}")

        _root.after(0, update_ui)

    threading.Thread(target=run, daemon=True).start()


def is_running():
    return tunnel_service.is_running()
