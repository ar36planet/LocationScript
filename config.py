import os
import sys
import shutil

_FROZEN = getattr(sys, 'frozen', False)

if _FROZEN:
    # macOS .app bundles don't inherit shell PATH, so search common install locations explicitly.
    # Prefer the system-installed pymobiledevice3 (pipx/brew) over the frozen bundle binary,
    # because the frozen binary may have SSL/dependency issues with the tunnel.
    _common_paths = os.pathsep.join([
        os.path.expanduser("~/.local/bin"),
        "/opt/homebrew/bin",
        "/usr/local/bin",
        "/usr/bin",
        os.environ.get("PATH", ""),
    ])
    _system = shutil.which("pymobiledevice3", path=_common_paths)
    _bundled = os.path.join(os.path.dirname(sys.executable), "pymobiledevice3")
    PYMOBILEDEVICE3 = _system or _bundled
else:
    PYMOBILEDEVICE3 = shutil.which("pymobiledevice3") or os.path.expanduser("~/.local/bin/pymobiledevice3")

if _FROZEN:
    SCRIPT_DIR = os.path.expanduser("~/Library/Application Support/iOS虛擬定位")
    os.makedirs(SCRIPT_DIR, exist_ok=True)
else:
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

FAVORITES_FILE = os.path.join(SCRIPT_DIR, "favorites.json")
HISTORY_DIR = os.path.join(SCRIPT_DIR, "history")
DEFAULT_UDID_FILE = os.path.join(SCRIPT_DIR, "default_device_udid.txt")
