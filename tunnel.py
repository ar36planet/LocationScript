import os
import subprocess
import sys

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
    result = subprocess.run(["pgrep", "-f", "pymobiledevice3 remote tunneld"], capture_output=True, text=True)
    if result.stdout.strip():
        _tunnel_status.config(text="🟢 Tunnel 運行中", fg="green")
    else:
        _tunnel_status.config(text="🔴 Tunnel 未啟動", fg="red")
    _tunnel_check_id = _root.after(2000, check_tunnel_status)


def _get_pymobiledevice3_path():
    # 打包版：使用 bundle 內的執行檔
    if hasattr(sys, '_MEIPASS'):
        bundled = os.path.join(os.path.dirname(sys.executable), 'pymobiledevice3')
        if os.path.isfile(bundled) and os.access(bundled, os.X_OK):
            return bundled
        return None
    # 開發模式：從系統找
    result = subprocess.run(["which", "pymobiledevice3"], capture_output=True, text=True)
    path = result.stdout.strip()
    if path:
        return path
    for candidate in [
        "/usr/local/bin/pymobiledevice3",
        "/opt/homebrew/bin/pymobiledevice3",
        os.path.expanduser("~/.local/bin/pymobiledevice3"),
    ]:
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    return None


def start_tunnel():
    global _tunnel_window_id
    result = subprocess.run(["pgrep", "-f", "pymobiledevice3 remote tunneld"], capture_output=True, text=True)
    if result.stdout.strip():
        _status.config(text="⚠️ tunneld 已在執行中，無需重複啟動")
        return
    cmd_path = _get_pymobiledevice3_path()
    if cmd_path is None:
        _status.config(text="❌ 找不到 pymobiledevice3，請先安裝")
        return
    script = f'''
    tell application "Terminal"
        activate
        do script "sudo {cmd_path} remote tunneld"
        return id of window 1
    end tell
    '''
    result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    _tunnel_window_id = result.stdout.strip()
    _status.config(text="✅ 已開啟 Terminal 執行 tunneld")


def stop_tunnel():
    global _tunnel_window_id
    result = subprocess.run(["pgrep", "-f", "pymobiledevice3 remote tunneld"], capture_output=True, text=True)
    if not result.stdout.strip():
        _status.config(text="⚠️ 找不到運行中的 tunneld")
        _tunnel_window_id = None
        return
    script = """do shell script "pkill -9 -f 'pymobiledevice3 remote tunneld'" with administrator privileges"""
    subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    _tunnel_window_id = None
    check = subprocess.run(["pgrep", "-f", "pymobiledevice3 remote tunneld"], capture_output=True, text=True)
    if not check.stdout.strip():
        _status.config(text="✅ 已停止 tunneld")
    else:
        _status.config(text="❌ 停止失敗（可能已取消授權）")


def is_running():
    result = subprocess.run(["pgrep", "-f", "pymobiledevice3 remote tunneld"], capture_output=True, text=True)
    return bool(result.stdout.strip())
