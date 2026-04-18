import os
import subprocess
import sys

from config import PYMOBILEDEVICE3
from core.result import Result


def is_running() -> bool:
    for pattern in ["pymobiledevice3 remote tunneld", "ifly-tunneld remote tunneld"]:
        result = subprocess.run(["pgrep", "-f", pattern], capture_output=True, text=True)
        if result.stdout.strip():
            return True
    return False


def find_pymobiledevice3() -> str | None:
    if PYMOBILEDEVICE3 and os.path.isfile(PYMOBILEDEVICE3) and os.access(PYMOBILEDEVICE3, os.X_OK):
        return PYMOBILEDEVICE3

    if hasattr(sys, "_MEIPASS"):
        bundled = os.path.join(os.path.dirname(sys.executable), "pymobiledevice3")
        if os.path.isfile(bundled) and os.access(bundled, os.X_OK):
            return bundled

    for candidate in [
        "/usr/local/bin/pymobiledevice3",
        "/opt/homebrew/bin/pymobiledevice3",
        os.path.expanduser("~/.local/bin/pymobiledevice3"),
    ]:
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    return None


def start_tunnel(headless: bool = True) -> Result:
    if is_running():
        return Result(True, "TUNNEL_RUNNING", "tunneld is already running")

    cmd_path = find_pymobiledevice3()
    if cmd_path is None:
        return Result(False, "ENV_ERROR", "pymobiledevice3 not found, please install it")

    if headless:
        wrapper = "/usr/local/bin/ifly-tunneld"
        sudo_cmd = wrapper if (os.path.isfile(wrapper) and os.access(wrapper, os.X_OK)) else cmd_path
        try:
            proc = subprocess.Popen(
                ["sudo", "-n", sudo_cmd, "remote", "tunneld"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True,
                start_new_session=True,
            )
            try:
                _, stderr = proc.communicate(timeout=1)
            except subprocess.TimeoutExpired:
                stderr = ""
            if proc.poll() is not None and proc.returncode != 0:
                detail = (stderr or "").strip()
                msg = f"Cannot start tunneld without password sudo. Configure sudoers for `sudo -n {cmd_path} remote tunneld`."
                if detail:
                    msg = f"{msg} ({detail[:120]})"
                return Result(False, "ENV_ERROR", msg, data={"sudo_nopasswd_ok": False})
        except Exception as e:
            return Result(False, "ENV_ERROR", f"Start failed: {e}", data={"sudo_nopasswd_ok": False})

        if is_running():
            return Result(True, "TUNNEL_STARTED", "tunneld started in background")
        return Result(False, "EXEC_ERROR", "tunneld did not enter running state after start")

    script = f'''
    tell application "Terminal"
        activate
        do script "sudo {cmd_path} remote tunneld"
        return id of window 1
    end tell
    '''
    result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    if result.returncode != 0:
        stderr = (result.stderr or "").strip()
        return Result(False, "EXEC_ERROR", f"Failed to open Terminal: {stderr[:120]}")
    return Result(True, "TUNNEL_STARTED", "Terminal opened for tunneld", data={"window_id": result.stdout.strip()})


def stop_tunnel(headless: bool = True) -> Result:
    if not is_running():
        return Result(True, "OK", "No running tunneld found")

    if headless:
        subprocess.run(["sudo", "-n", "/usr/local/bin/ifly-tunneld-stop"], capture_output=True, text=True)
    else:
        script = """do shell script "pkill -9 -f 'pymobiledevice3 remote tunneld'; pkill -9 -f 'ifly-tunneld remote tunneld'" with administrator privileges"""
        r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
        if r.returncode != 0:
            return Result(False, "EXEC_ERROR", "Stop failed: user cancelled or insufficient permissions")

    if is_running():
        return Result(False, "EXEC_ERROR", "Stop failed: process still running")
    return Result(True, "TUNNEL_STOPPED", "tunneld stopped")


def status() -> Result:
    running = is_running()
    if running:
        return Result(True, "OK", "Tunnel is running", data={"running": True})
    return Result(True, "OK", "Tunnel is not running", data={"running": False})
