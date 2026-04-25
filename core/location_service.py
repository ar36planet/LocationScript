import json
import math
import os
import re
import subprocess
import sys
import time
import urllib.parse
import urllib.request

from config import PYMOBILEDEVICE3, DEFAULT_UDID_FILE
from core.result import Result


def _fetch_raw_devices() -> list[dict]:
    try:
        proc = subprocess.run(
            [PYMOBILEDEVICE3, "usbmux", "list"],
            capture_output=True, text=True, timeout=8,
        )
        return json.loads(proc.stdout or "[]")
    except Exception:
        return []


def _connected_udids() -> list[str]:
    """Unique UDIDs of connected devices (deduplicates same device on USB+WiFi)."""
    seen = {}
    for d in _fetch_raw_devices():
        if not isinstance(d, dict):
            continue
        udid = d.get("Identifier")
        if not udid:
            continue
        # Prefer USB over WiFi when the same UDID appears on both
        conn = d.get("ConnectionType", "")
        if udid not in seen or conn == "USB":
            seen[udid] = udid
    return list(seen.values())


def list_connected_devices() -> list[dict]:
    """Unique connected devices with name, ios version and connection type."""
    seen = {}
    for d in _fetch_raw_devices():
        if not isinstance(d, dict):
            continue
        udid = d.get("Identifier")
        if not udid:
            continue
        conn = d.get("ConnectionType", "")
        if udid not in seen or conn == "USB":
            seen[udid] = {
                "udid": udid,
                "name": d.get("DeviceName", ""),
                "ios": d.get("ProductVersion", ""),
                "connection": conn,
            }
    return list(seen.values())


def _udid_args() -> Result | list[str]:
    """Returns a list of CLI args, or a Result(ok=False) if device selection fails."""
    connected = _connected_udids()

    if not connected:
        return Result(False, "ENV_ERROR", "No device connected")

    # Single device: always use it directly, ignore saved default
    if len(connected) == 1:
        return ["--tunnel", connected[0]]

    # Multiple devices: require a saved default
    try:
        with open(DEFAULT_UDID_FILE) as f:
            saved = f.read().strip()
        if saved and saved in connected:
            return ["--tunnel", saved]
        if saved:
            return Result(False, "ENV_ERROR",
                          f"Default device {saved} is not connected. Run 'ifly device select <UDID> --default'")
    except FileNotFoundError:
        pass

    return Result(False, "ENV_ERROR",
                  "Multiple devices connected. Run 'ifly device select <UDID> --default' to specify one")

_PID_FILE = os.path.expanduser("~/.local/share/ifly/location.pid")
_MOVE_PID_FILE = os.path.expanduser("~/.local/share/ifly/move.pid")
_MOVE_INTERVAL = 5  # seconds between location updates during movement
_IFLY_SCRIPT = (
    sys.executable  # frozen: ifly binary IS the executable
    if getattr(sys, "frozen", False)
    else os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "ifly.py"))
)


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
    # Kill all simulate-location processes (not just the PID-file one)
    subprocess.run(
        ["pkill", "-9", "-f", "simulate-location set"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
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


def _write_move_state(pid: int, start_lat: float, start_lng: float,
                      end_lat: float, end_lng: float, eta_seconds: float) -> None:
    _ensure_dir()
    with open(_MOVE_PID_FILE, "w") as f:
        json.dump({
            "pid": pid,
            "start_lat": start_lat, "start_lng": start_lng,
            "end_lat": end_lat, "end_lng": end_lng,
            "start_time": time.time(),
            "eta_seconds": eta_seconds,
        }, f)


def _read_move_state() -> dict:
    try:
        with open(_MOVE_PID_FILE) as f:
            return json.load(f)
    except Exception:
        return {}


def _kill_move() -> None:
    state = _read_move_state()
    pid = state.get("pid")
    if pid:
        try:
            os.kill(pid, 9)
        except (ProcessLookupError, PermissionError):
            pass
    try:
        os.unlink(_MOVE_PID_FILE)
    except FileNotFoundError:
        pass


def _destination(lat: float, lng: float, bearing_deg: float, distance_km: float) -> tuple[float, float]:
    R = 6371.0
    phi1 = math.radians(lat)
    lam1 = math.radians(lng)
    theta = math.radians(bearing_deg)
    delta = distance_km / R
    phi2 = math.asin(math.sin(phi1) * math.cos(delta) + math.cos(phi1) * math.sin(delta) * math.cos(theta))
    lam2 = lam1 + math.atan2(
        math.sin(theta) * math.sin(delta) * math.cos(phi1),
        math.cos(delta) - math.sin(phi1) * math.sin(phi2),
    )
    return math.degrees(phi2), math.degrees(lam2)


def _set_location_raw(lat: str, lng: str) -> None:
    udid = _udid_args()
    if isinstance(udid, Result):
        return
    _kill_existing()
    try:
        proc = subprocess.Popen(
            [PYMOBILEDEVICE3, "developer", "dvt", "simulate-location", "set", *udid, "--", lat, lng],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        _write_pid_state(proc.pid, lat, lng)
    except (OSError, FileNotFoundError):
        pass


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

    udid = _udid_args()
    if isinstance(udid, Result):
        return udid

    _kill_existing()

    try:
        proc = subprocess.Popen(
            [PYMOBILEDEVICE3, "developer", "dvt", "simulate-location", "set", *udid, "--", lat, lng],
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
                data["addr"] = name
        except Exception:
            pass

    return Result(True, "LOCATION_SET", f"Location set: {lat}, {lng}", data=data)


def clear_location() -> Result:
    udid = _udid_args()
    if isinstance(udid, Result):
        return udid
    _kill_existing()
    try:
        proc = subprocess.Popen(
            [PYMOBILEDEVICE3, "developer", "dvt", "simulate-location", "clear", *udid],
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


def location_status() -> Result:
    state = _read_pid_state()
    if not state.get("lat") or not state.get("lng"):
        return Result(True, "LOCATION_IDLE", "No virtual location set", data={"active": False})

    pid = state.get("pid")
    alive = False
    if pid:
        try:
            os.kill(pid, 0)
            alive = True
        except (ProcessLookupError, PermissionError):
            pass

    return Result(
        True,
        "LOCATION_ACTIVE" if alive else "LOCATION_STALE",
        f"Location: {state['lat']}, {state['lng']}",
        data={"active": alive, "lat": state["lat"], "lng": state["lng"], "pid": pid},
    )


def move_location_run(start_lat: float, start_lng: float,
                      end_lat: float, end_lng: float,
                      speed_kmh: float, distance_km: float) -> Result:
    """Blocking interpolation loop — called by the background worker process."""
    total_seconds = (distance_km / speed_kmh) * 3600
    steps = max(1, int(total_seconds / _MOVE_INTERVAL))

    if steps == 1:
        return set_location(str(end_lat), str(end_lng), fetch_name=True)

    # First step: verify tunnel is working
    t = 1 / steps
    lat = str(round(start_lat + t * (end_lat - start_lat), 8))
    lng = str(round(start_lng + t * (end_lng - start_lng), 8))
    result = set_location(lat, lng, fetch_name=False)
    if not result.ok:
        return result

    for i in range(2, steps):
        time.sleep(_MOVE_INTERVAL - 2 if i == 2 else _MOVE_INTERVAL)
        t = i / steps
        _set_location_raw(
            str(round(start_lat + t * (end_lat - start_lat), 8)),
            str(round(start_lng + t * (end_lng - start_lng), 8)),
        )

    time.sleep(_MOVE_INTERVAL - 2 if steps == 2 else _MOVE_INTERVAL)
    return set_location(str(end_lat), str(end_lng), fetch_name=True)


def _build_move_script(pmd3: str, udid_args: list[str],
                        start_lat: float, start_lng: float,
                        end_lat: float, end_lng: float,
                        steps: int) -> str:
    """Generate a self-contained Python script for the move worker.
    Used in frozen mode to avoid spawning another PyInstaller binary."""
    return f"""
import subprocess, time, os, json

PMD3 = {pmd3!r}
UDID_ARGS = {udid_args!r}
PID_FILE = {_PID_FILE!r}
INTERVAL = {_MOVE_INTERVAL}

positions = [
    (
        {start_lat!r} + (i / {steps}) * ({end_lat!r} - {start_lat!r}),
        {start_lng!r} + (i / {steps}) * ({end_lng!r} - {start_lng!r}),
    )
    for i in range(1, {steps} + 1)
]

def kill_existing():
    subprocess.run(["pkill", "-9", "-f", "simulate-location set"], capture_output=True)
    try:
        os.unlink(PID_FILE)
    except FileNotFoundError:
        pass

def set_loc(lat, lng):
    kill_existing()
    proc = subprocess.Popen(
        [PMD3, "developer", "dvt", "simulate-location", "set",
         *UDID_ARGS, "--", str(round(lat, 8)), str(round(lng, 8))],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    with open(PID_FILE, "w") as f:
        json.dump({{"pid": proc.pid, "lat": str(round(lat, 8)), "lng": str(round(lng, 8))}}, f)
    time.sleep(2)
    if proc.poll() is not None and proc.returncode != 0:
        try:
            os.unlink(PID_FILE)
        except FileNotFoundError:
            pass
        return False
    return True

for i, (lat, lng) in enumerate(positions):
    if not set_loc(lat, lng):
        break
    if i < len(positions) - 1:
        time.sleep(max(0, INTERVAL - 2))
"""


def move_location_start(bearing_deg: float, distance_km: float, speed_kmh: float) -> Result:
    state = _read_pid_state()
    if not (state.get("lat") and state.get("lng")):
        return Result(False, "ENV_ERROR", "No current location. Use 'location set' first.")

    # Resolve device UDID before starting worker (worker has no UI to prompt)
    udid = _udid_args()
    if isinstance(udid, Result):
        return udid

    start_lat = float(state["lat"])
    start_lng = float(state["lng"])
    end_lat, end_lng = _destination(start_lat, start_lng, bearing_deg, distance_km)
    total_seconds = (distance_km / speed_kmh) * 3600

    _kill_move()

    log_path = os.path.join(os.path.dirname(_PID_FILE), "move_worker.log")
    try:
        log_file = open(log_path, "w")
        if getattr(sys, "frozen", False):
            # Frozen mode: spawning another PyInstaller onefile binary causes
            # "Failed to import encodings module". Use system python3 instead.
            import shutil as _shutil
            python3 = _shutil.which("python3") or _shutil.which("python")
            if not python3:
                return Result(False, "ENV_ERROR", "python3 not found — cannot start move worker")
            steps = max(1, int(total_seconds / _MOVE_INTERVAL))
            script = _build_move_script(PYMOBILEDEVICE3, udid, start_lat, start_lng,
                                        end_lat, end_lng, steps)
            proc = subprocess.Popen(
                [python3, "-c", script],
                stdout=log_file, stderr=log_file,
                stdin=subprocess.DEVNULL,
                start_new_session=True,
            )
        else:
            proc = subprocess.Popen(
                [sys.executable, _IFLY_SCRIPT, "_move_worker",
                 "--start-lat", str(start_lat), "--start-lng", str(start_lng),
                 "--end-lat", str(end_lat), "--end-lng", str(end_lng),
                 "--speed", str(speed_kmh), "--distance", str(distance_km)],
                stdout=log_file, stderr=log_file,
                stdin=subprocess.DEVNULL,
                start_new_session=True,
            )
    except (OSError, FileNotFoundError) as e:
        return Result(False, "EXEC_ERROR", f"Failed to start move worker: {e}")

    _write_move_state(proc.pid, start_lat, start_lng, end_lat, end_lng, total_seconds)

    return Result(True, "MOVE_STARTED", f"Moving {distance_km:.2f} km, ETA {int(total_seconds)}s", data={
        "pid": proc.pid,
        "eta_seconds": int(total_seconds),
        "destination": {"lat": round(end_lat, 8), "lng": round(end_lng, 8)},
    })


def move_location_stop() -> Result:
    state = _read_move_state()
    if not state.get("pid"):
        return Result(True, "MOVE_IDLE", "No move in progress")
    _kill_move()
    return Result(True, "MOVE_STOPPED", "Movement stopped")


def move_location_status() -> Result:
    state = _read_move_state()
    if not state.get("pid"):
        return Result(True, "MOVE_IDLE", "No move in progress", data={"running": False})

    pid = state["pid"]
    try:
        os.kill(pid, 0)
        running = True
    except (ProcessLookupError, PermissionError):
        running = False

    if not running:
        _kill_move()
        return Result(True, "MOVE_DONE", "Movement complete", data={"running": False})

    elapsed = time.time() - state.get("start_time", time.time())
    eta = state.get("eta_seconds", 0)
    remaining = max(0, eta - elapsed)

    return Result(True, "MOVE_RUNNING", f"Moving, ~{int(remaining)}s remaining", data={
        "running": True,
        "pid": pid,
        "progress": round(min(1.0, elapsed / eta) if eta else 1.0, 2),
        "eta_remaining_seconds": int(remaining),
        "destination": {"lat": state.get("end_lat"), "lng": state.get("end_lng")},
    })
