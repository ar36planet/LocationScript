import json
import os
import re
import subprocess
import time
import urllib.parse
import urllib.request

from config import PYMOBILEDEVICE3
from core.result import Result

_PID_FILE = os.path.expanduser("~/.local/share/ifly/location.pid")


def _ensure_dir():
    os.makedirs(os.path.dirname(_PID_FILE), exist_ok=True)


def _read_pid_state() -> dict:
    try:
        with open(_PID_FILE) as f:
            return json.load(f)
    except Exception:
        return {}


def _write_pid_state(pid: int, lat: str, lng: str):
    _ensure_dir()
    with open(_PID_FILE, "w") as f:
        json.dump({"pid": pid, "lat": lat, "lng": lng}, f)


def _kill_existing():
    state = _read_pid_state()
    pid = state.get("pid")
    if pid:
        try:
            os.kill(pid, 9)
        except (ProcessLookupError, PermissionError):
            pass
    try:
        os.unlink(_PID_FILE)
    except FileNotFoundError:
        pass


def parse_google_url(url: str) -> tuple | None:
    m = re.search(r"!3d([-\d.]+)!4d([-\d.]+)", url)
    if m:
        return m.group(1), m.group(2), "place"
    m = re.search(r"@([-\d.]+),([-\d.]+)", url)
    if m:
        return m.group(1), m.group(2), "map center"
    return None


def parse_coords(text: str) -> tuple | None:
    m = re.match(r"^([-\d.]+)[,\s]+([-\d.]+)$", text.strip())
    if m:
        return m.group(1), m.group(2)
    return None


def stop_keepalive() -> None:
    _kill_existing()


def set_location(lat: str, lng: str, keepalive: bool = False, fetch_name: bool = False) -> Result:
    try:
        lat_f = float(lat)
        lng_f = float(lng)
    except ValueError:
        return Result(False, "PARAM_ERROR", "Invalid lat/lng format")

    if not (-90 <= lat_f <= 90):
        return Result(False, "PARAM_ERROR", "Latitude out of range (-90 to 90)")
    if not (-180 <= lng_f <= 180):
        return Result(False, "PARAM_ERROR", "Longitude out of range (-180 to 180)")

    _kill_existing()

    try:
        proc = subprocess.Popen(
            [PYMOBILEDEVICE3, "developer", "dvt", "simulate-location", "set", "--", lat, lng],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except (OSError, FileNotFoundError) as e:
        return Result(False, "EXEC_ERROR", f"Subprocess error: {e}")

    # Wait briefly to catch immediate failures (e.g. tunnel not running)
    time.sleep(2)
    if proc.poll() is not None and proc.returncode > 0:
        return Result(False, "EXEC_ERROR", f"Failed to set location (exit {proc.returncode})")

    _write_pid_state(proc.pid, lat, lng)

    data = {"pid": proc.pid}
    if fetch_name:
        try:
            url = (
                "https://nominatim.openstreetmap.org/reverse"
                f"?lat={urllib.parse.quote(lat)}&lon={urllib.parse.quote(lng)}"
                "&format=json&accept-language=zh-TW"
            )
            req = urllib.request.Request(url, headers={"User-Agent": "iOS-LocationScript/1.0"})
            with urllib.request.urlopen(req, timeout=6) as resp:
                payload = json.loads(resp.read())
            name = payload.get("display_name", "")
            if name:
                data["name"] = name
        except Exception:
            pass

    return Result(True, "LOCATION_SET", f"Location set: {lat}, {lng}", data=data)


def clear_location() -> Result:
    _kill_existing()
    try:
        proc = subprocess.Popen(
            [PYMOBILEDEVICE3, "developer", "dvt", "simulate-location", "clear"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        time.sleep(2)
        if proc.poll() is None:
            proc.kill()
    except (OSError, FileNotFoundError) as e:
        return Result(False, "EXEC_ERROR", f"Subprocess error: {e}")

    return Result(True, "LOCATION_CLEARED", "Location cleared")
